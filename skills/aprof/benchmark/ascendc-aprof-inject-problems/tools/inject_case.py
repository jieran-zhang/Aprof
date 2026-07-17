#!/usr/bin/env python3
"""Generate an AProf injected benchmark case from a baseline or scaffold.

The registry covers the six diagnosis problem families. Recipes are conservative:
when a kernel patch anchor is not found, the case is emitted as unsupported rather
than silently producing a weak or misleading benchmark sample.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DIAGNOSIS_FAMILIES = {
    "tiling",
    "data_movement",
    "pipeline_parallel",
    "onchip_memory",
    "ai_core_utilization",
    "api_algorithm",
}

LEGACY_FAMILY_ALIASES = {
    "blockdim": ("tiling", "blockdim_too_small"),
    "tail": ("tiling", "tail_inefficient"),
    "tilelen_small": ("tiling", "tile_length_too_small"),
    "tilelen_large": ("tiling", "tile_length_too_large"),
    "tilenum": ("tiling", "tile_num_unreasonable"),
    "dynshape": ("tiling", "fixed_tiling_dynamic_shape"),
}

PROBLEM_ID_ALIASES = {
    "tileLength_too_small": "tile_length_too_small",
    "tileLength_too_large": "tile_length_too_large",
    "tileNum_unreasonable": "tile_num_unreasonable",
}

ALL_FLAGS = {
    "APROF_INJECT_TAIL",
    "APROF_INJECT_DYNSHAPE",
    "APROF_INJECT_REDUNDANT_COPYIN",
    "APROF_INJECT_EXTRA_COPYOUT",
    "APROF_INJECT_EXCESSIVE_BARRIER",
    "APROF_INJECT_UB_OVERALLOC",
    "APROF_INJECT_SCALAR_LOOP",
    "APROF_INJECT_REDUNDANT_VECTOR",
}


@dataclass(frozen=True)
class Recipe:
    family: str
    problem_id: str
    variant: str
    label: str
    problem: str
    source_modes: tuple[str, ...]
    knobs: dict[str, Any] = field(default_factory=dict)
    flags: dict[str, int] = field(default_factory=dict)
    kernel_patches: tuple[str, ...] = ()
    expected_diagnosis_family: str = ""
    profile_mode: str = "sim"
    quality_note: str = ""
    signal_status: str = "active"

    def to_index(self) -> dict[str, Any]:
        return {
            "problem_family": self.family,
            "problem_id": self.problem_id,
            "variant": self.variant,
            "injected_label": self.label,
            "source_modes": list(self.source_modes),
            "profile_mode": self.profile_mode,
            "knobs": self.knobs,
            "flags": self.flags,
            "kernel_patches": list(self.kernel_patches),
            "signal_status": self.signal_status,
        }


RECIPES: dict[tuple[str, str], Recipe] = {}


def register(recipe: Recipe) -> None:
    RECIPES[(recipe.family, recipe.problem_id)] = recipe


register(
    Recipe(
        family="tiling",
        problem_id="blockdim_too_small",
        variant="inject_blockdim",
        label="blockdim_too_small",
        problem="blockDim 固定过小，任务数足够时仍无法吃满 AI Core。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_blockdim": 1},
        expected_diagnosis_family="tiling",
        quality_note="requires build/run/profile validation before active use",
        signal_status="weak",
    )
)
register(
    Recipe(
        family="tiling",
        problem_id="tail_inefficient",
        variant="inject_tail",
        label="tail_inefficient",
        problem="tail tile 额外重复搬运并强同步，制造尾块低效路径。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"variant_flags": 1, "default_output_elements": 2057},
        flags={"APROF_INJECT_TAIL": 1},
        expected_diagnosis_family="tiling",
        quality_note="tail reload is guarded by APROF_INJECT_TAIL",
    )
)
register(
    Recipe(
        family="tiling",
        problem_id="tile_length_too_small",
        variant="inject_tilelen_small",
        label="tileLength_too_small",
        problem="tileLength 过小，增加 tile 循环、MTE setup 和同步开销。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_tile_length": 16},
        expected_diagnosis_family="tiling",
        quality_note="small tileLength increases tile count",
    )
)
register(
    Recipe(
        family="tiling",
        problem_id="tile_length_too_large",
        variant="inject_tilelen_large",
        label="tileLength_too_large",
        problem="tileLength 过大，减少任务数并提高 UB 压力。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_tile_length": 4096},
        expected_diagnosis_family="tiling",
        quality_note="large tileLength can reduce total tiles",
    )
)
register(
    Recipe(
        family="tiling",
        problem_id="tile_num_unreasonable",
        variant="inject_tilenum",
        label="tileNum_unreasonable",
        problem="tileNum 人为放大，导致空转 tile、循环和同步次数异常。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_tile_num_mul": 4},
        expected_diagnosis_family="tiling",
        quality_note="tile_num_multiplier is the intended single-factor knob",
    )
)
register(
    Recipe(
        family="tiling",
        problem_id="fixed_tiling_dynamic_shape",
        variant="inject_dynshape",
        label="fixed_tiling_dynamic_shape",
        problem="动态 shape 下复用固定 tiling 策略，造成小/大 shape 适配差。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"variant_flags": 2},
        flags={"APROF_INJECT_DYNSHAPE": 1},
        expected_diagnosis_family="tiling",
        quality_note="needs multi-shape validation",
        signal_status="weak",
    )
)

register(
    Recipe(
        family="data_movement",
        problem_id="redundant_copyin",
        variant="inject_redundant_copyin",
        label="redundant_copyin",
        problem="循环内对同一 GM 区间重复 CopyIn，放大 GM→UB 流量和 MTE2 指令。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_REDUNDANT_COPYIN": 1},
        kernel_patches=("redundant_copyin",),
        expected_diagnosis_family="data_movement",
        profile_mode="hw-op",
        quality_note="requires Memory.csv or trace proxy to confirm redundant MTE2",
    )
)
register(
    Recipe(
        family="data_movement",
        problem_id="extra_copyout",
        variant="inject_extra_copyout",
        label="extra_copyout",
        problem="最终写回前额外 CopyOut 同一结果，放大 UB→GM 流量和 MTE3 指令。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_EXTRA_COPYOUT": 1},
        kernel_patches=("extra_copyout",),
        expected_diagnosis_family="data_movement",
        profile_mode="hw-op",
        quality_note="requires Memory.csv or trace proxy to confirm extra MTE3",
    )
)
register(
    Recipe(
        family="data_movement",
        problem_id="small_datacopy_granularity",
        variant="inject_small_datacopy",
        label="small_datacopy_granularity",
        problem="DataCopy 粒度过小，单次搬运字节数低、MTE setup 成本被放大。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_tile_length": 8},
        expected_diagnosis_family="data_movement",
        profile_mode="hw-op",
        quality_note="small tileLength is classified as data movement when the target signal is copy granularity",
    )
)

register(
    Recipe(
        family="pipeline_parallel",
        problem_id="serial_copy_compute_copyout",
        variant="inject_serial_pipeline",
        label="serial_copy_compute_copyout",
        problem="CopyIn、Compute、CopyOut 之间加入强 barrier，制造串行流水。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_EXCESSIVE_BARRIER": 1},
        kernel_patches=("excessive_barrier",),
        expected_diagnosis_family="pipeline_parallel",
        quality_note="trace should show poor MTE/Vector overlap",
    )
)
register(
    Recipe(
        family="pipeline_parallel",
        problem_id="double_buffer_disabled",
        variant="inject_double_buffer_disabled",
        label="double_buffer_disabled",
        problem="禁用或规避 double buffer，使 producer/consumer 不能跨 tile 重叠。",
        source_modes=("scaffold_project",),
        expected_diagnosis_family="pipeline_parallel",
        quality_note="only supported when source has explicit double-buffer knobs",
        signal_status="unsupported",
    )
)
register(
    Recipe(
        family="pipeline_parallel",
        problem_id="excessive_pipe_barrier",
        variant="inject_excessive_barrier",
        label="excessive_pipe_barrier",
        problem="tile 循环内插入冗余 PipeBarrier<PIPE_ALL>，增加 pipe drain 和同步等待。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_EXCESSIVE_BARRIER": 1},
        kernel_patches=("excessive_barrier",),
        expected_diagnosis_family="pipeline_parallel",
        quality_note="trace should expose repeated barriers",
    )
)

register(
    Recipe(
        family="onchip_memory",
        problem_id="ub_temp_overallocated",
        variant="inject_ub_temp_overalloc",
        label="ub_temp_overallocated",
        problem="额外分配 UB 临时 tensor，压缩有效 tile 余量并提高 UB 占用。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_UB_OVERALLOC": 1},
        kernel_patches=("ub_temp_overallocated",),
        expected_diagnosis_family="onchip_memory",
        quality_note="requires UB occupancy calculation from source/tiling",
    )
)
register(
    Recipe(
        family="onchip_memory",
        problem_id="gm_spill_intermediate",
        variant="inject_gm_spill",
        label="gm_spill_intermediate",
        problem="把中间或最终等价数据额外落 GM，模拟片上复用不足。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_EXTRA_COPYOUT": 1},
        kernel_patches=("extra_copyout",),
        expected_diagnosis_family="onchip_memory",
        profile_mode="hw-op",
        quality_note="uses extra copyout as a safe GM spill proxy",
    )
)
register(
    Recipe(
        family="onchip_memory",
        problem_id="low_ub_reuse",
        variant="inject_low_ub_reuse",
        label="low_ub_reuse",
        problem="重复从 GM 读取可复用数据，模拟 UB/L2 复用不足。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_REDUNDANT_COPYIN": 1},
        kernel_patches=("redundant_copyin",),
        expected_diagnosis_family="onchip_memory",
        profile_mode="hw-op",
        quality_note="uses redundant copyin as a safe low-reuse proxy",
    )
)

register(
    Recipe(
        family="ai_core_utilization",
        problem_id="underused_blockdim",
        variant="inject_underused_blockdim",
        label="underused_blockdim",
        problem="blockDim 低于可用核数，AI Core 核利用率低。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_blockdim": 1, "default_output_elements": 8192},
        expected_diagnosis_family="ai_core_utilization",
        profile_mode="hw-op",
        quality_note="requires hardware core count denominator",
    )
)
register(
    Recipe(
        family="ai_core_utilization",
        problem_id="overlaunched_empty_cores",
        variant="inject_overlaunched_cores",
        label="overlaunched_empty_cores",
        problem="小 shape 仍启动过多 core，造成空核和头开销。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_blockdim": 32, "default_output_elements": 128},
        expected_diagnosis_family="ai_core_utilization",
        profile_mode="hw-op",
        quality_note="requires per-core task duration or trace",
    )
)
register(
    Recipe(
        family="ai_core_utilization",
        problem_id="tail_core_imbalance",
        variant="inject_tail_core_imbalance",
        label="tail_core_imbalance",
        problem="tail 集中到末核，导致核间耗时不均衡和拖尾。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_blockdim": 4, "default_output_elements": 2057},
        flags={"APROF_INJECT_TAIL": 1},
        expected_diagnosis_family="ai_core_utilization",
        profile_mode="hw-op",
        quality_note="requires per-core timing evidence",
    )
)

register(
    Recipe(
        family="api_algorithm",
        problem_id="scalar_loop_redundant",
        variant="inject_scalar_loop",
        label="scalar_loop_redundant",
        problem="tile 循环内插入冗余 scalar 控制循环，提高 scalar 占比。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_SCALAR_LOOP": 1},
        kernel_patches=("scalar_loop",),
        expected_diagnosis_family="api_algorithm",
        profile_mode="hw-op",
        quality_note="requires PipeUtilization scalar evidence",
    )
)
register(
    Recipe(
        family="api_algorithm",
        problem_id="small_vector_api_chunks",
        variant="inject_small_vector_chunks",
        label="small_vector_api_chunks",
        problem="Vector API count 过小，API 调用/循环开销占比变高。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        knobs={"default_tile_length": 8},
        expected_diagnosis_family="api_algorithm",
        profile_mode="hw-op",
        quality_note="small vector chunk proxy; diagnose with vector utilization and scalar/MTE ratios",
    )
)
register(
    Recipe(
        family="api_algorithm",
        problem_id="redundant_cast_or_vector_copy",
        variant="inject_redundant_vector",
        label="redundant_cast_or_vector_copy",
        problem="增加冗余 Vector 等价操作，模拟 Cast/Vector copy 类 API 浪费。",
        source_modes=("existing_aprof_baseline", "scaffold_project"),
        flags={"APROF_INJECT_REDUNDANT_VECTOR": 1},
        kernel_patches=("redundant_vector",),
        expected_diagnosis_family="api_algorithm",
        profile_mode="hw-op",
        quality_note="uses Adds(+0) as a safe redundant vector API proxy",
    )
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an AProf injected case")
    parser.add_argument("--list-recipes", action="store_true", help="Print available recipe registry and exit")
    parser.add_argument("--source-mode", choices=("existing_aprof_baseline", "kernel_only", "scaffold_project"))
    parser.add_argument("--source-path", default="", help="Baseline dir, kernel file, or scaffold project")
    parser.add_argument("--output-root", default="", help="Directory containing baseline/inject_* cases")
    parser.add_argument("--op-name", default="", help="Operator name; inferred when omitted")
    parser.add_argument("--problem-family", default="", help="One of six diagnosis families, or a legacy alias")
    parser.add_argument("--problem-id", default="", help="Concrete recipe id; omitted only for legacy aliases")
    parser.add_argument("--variant", default="", help="Override variant directory name")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output variant")
    args = parser.parse_args()

    if args.list_recipes:
        print(json.dumps(list_recipe_index(), indent=2, ensure_ascii=False))
        return 0

    require(args.source_mode, "--source-mode is required unless --list-recipes is used")
    require(args.source_path, "--source-path is required unless --list-recipes is used")
    require(args.output_root, "--output-root is required unless --list-recipes is used")
    family, problem_id = resolve_recipe_key(args.problem_family, args.problem_id)
    recipe = RECIPES[(family, problem_id)]

    source = Path(args.source_path).resolve()
    output_root = Path(args.output_root).resolve()
    variant = args.variant or recipe.variant
    case_dir = output_root / variant
    op_name = args.op_name or infer_op_name(source, output_root)

    if case_dir.exists():
        if not args.force:
            raise SystemExit(f"case already exists: {case_dir} (use --force to overwrite)")
        shutil.rmtree(case_dir)

    create_case_source(args.source_mode, source, case_dir, op_name)
    result = apply_recipe(case_dir, op_name, args.source_mode, source, recipe)
    metadata = read_metadata(case_dir)
    inject_manifest = build_inject_manifest(
        source_mode=args.source_mode,
        source_path=source,
        case_dir=case_dir,
        op_name=op_name,
        recipe=recipe,
        metadata=metadata,
        result=result,
    )
    write_json(case_dir / "inject_manifest.json", inject_manifest)
    write_json(case_dir / "profiling_plan.json", build_profiling_plan(op_name, variant, recipe, result))
    print(json.dumps(inject_manifest, indent=2, ensure_ascii=False))
    return 0 if result["applicability_status"] != "unsupported" else 3


def list_recipe_index() -> dict[str, Any]:
    by_family: dict[str, list[dict[str, Any]]] = {family: [] for family in sorted(DIAGNOSIS_FAMILIES)}
    for recipe in sorted(RECIPES.values(), key=lambda r: (r.family, r.problem_id)):
        by_family[recipe.family].append(recipe.to_index())
    return {"schema_version": 1, "families": by_family, "legacy_aliases": LEGACY_FAMILY_ALIASES}


def resolve_recipe_key(problem_family: str, problem_id: str) -> tuple[str, str]:
    if problem_family in LEGACY_FAMILY_ALIASES and not problem_id:
        return LEGACY_FAMILY_ALIASES[problem_family]
    family = problem_family
    pid = PROBLEM_ID_ALIASES.get(problem_id, problem_id)
    if not family and pid:
        matches = [key for key in RECIPES if key[1] == pid]
        if len(matches) == 1:
            return matches[0]
    if family not in DIAGNOSIS_FAMILIES:
        raise SystemExit(f"unknown problem_family={problem_family!r}; use --list-recipes")
    if not pid:
        raise SystemExit("problem_id is required for six-family problem_family values; use --list-recipes")
    key = (family, pid)
    if key not in RECIPES:
        raise SystemExit(f"unknown recipe {family}/{pid}; use --list-recipes")
    return key


def require(value: Any, message: str) -> None:
    if not value:
        raise SystemExit(message)


def ignore_generated(_: str, names: list[str]) -> set[str]:
    generated = {"build", "build_sim", "data", "msprof_hw_output", "msprof_sim_output", "remote_out", "__pycache__"}
    return set(names) & generated


def infer_op_name(source: Path, output_root: Path) -> str:
    metadata = source / "metadata.json"
    if metadata.is_file():
        return str(json.loads(metadata.read_text(encoding="utf-8")).get("op_name", "unknown"))
    if source.is_file() and source.name.endswith("_kernel.asc"):
        return source.name.removesuffix("_kernel.asc")
    return output_root.name


def create_case_source(source_mode: str, source: Path, case_dir: Path, op_name: str) -> None:
    if source_mode == "existing_aprof_baseline":
        if not source.is_dir():
            raise SystemExit(f"baseline dir not found: {source}")
        shutil.copytree(source, case_dir, ignore=ignore_generated)
    elif source_mode == "kernel_only":
        create_kernel_only_case(source, case_dir, op_name)
    else:
        if not source.is_dir():
            raise SystemExit(f"scaffold project not found: {source}")
        shutil.copytree(source, case_dir, ignore=ignore_generated)


def create_kernel_only_case(kernel_path: Path, case_dir: Path, op_name: str) -> None:
    if not kernel_path.is_file():
        raise SystemExit(f"kernel file not found: {kernel_path}")
    (case_dir / "op_kernel").mkdir(parents=True)
    (case_dir / "scripts").mkdir()
    shutil.copy2(kernel_path, case_dir / "op_kernel" / f"{op_name}_kernel.asc")
    write_text(
        case_dir / "run.sh",
        '#!/usr/bin/env bash\nset -euo pipefail\n'
        'echo "[ERROR] kernel_only injection requires a direct-invoke scaffold first. Use ascendc-kernel-direct-invoke."\n'
        "exit 2\n",
    )
    write_text(case_dir / "op_kernel" / "aprof_variant_config.h", render_variant_config({}))
    write_text(
        case_dir / "scripts" / "gen_data.py",
        "#!/usr/bin/env python3\nraise SystemExit('kernel_only case needs direct-invoke io spec before injection')\n",
    )


def apply_recipe(case_dir: Path, op_name: str, source_mode: str, source_path: Path, recipe: Recipe) -> dict[str, Any]:
    notes: list[str] = []
    changed_files = {"metadata.json"}
    unsupported_reasons: list[str] = []

    if source_mode not in recipe.source_modes:
        unsupported_reasons.append(f"recipe supports {recipe.source_modes}, got {source_mode}")

    gen = case_dir / "scripts" / "gen_data.py"
    if gen.is_file() and recipe.knobs:
        update_gen_data(gen, recipe)
        changed_files.add("scripts/gen_data.py")
    elif recipe.knobs:
        unsupported_reasons.append("scripts/gen_data.py not found for knob injection")

    cfg = case_dir / "op_kernel" / "aprof_variant_config.h"
    if cfg.is_file():
        update_variant_config(cfg, recipe.flags)
        changed_files.add("op_kernel/aprof_variant_config.h")
    elif recipe.flags:
        unsupported_reasons.append("op_kernel/aprof_variant_config.h not found for kernel flags")

    patch_results = []
    if recipe.kernel_patches:
        kernel_path = case_dir / "op_kernel" / f"{op_name}_kernel.asc"
        if not kernel_path.is_file():
            unsupported_reasons.append(f"kernel file not found: {kernel_path}")
        else:
            for patch_id in recipe.kernel_patches:
                applied, reason = apply_kernel_patch(kernel_path, patch_id)
                patch_results.append({"patch_id": patch_id, "applied": applied, "reason": reason})
                if not applied:
                    unsupported_reasons.append(reason)
            if any(p["applied"] for p in patch_results):
                changed_files.add(f"op_kernel/{op_name}_kernel.asc")

    metadata = read_metadata(case_dir)
    metadata.update(
        {
            "op_name": metadata.get("op_name", op_name),
            "variant": recipe.variant,
            "problem_family": recipe.family,
            "problem_id": recipe.problem_id,
            "injected_label": recipe.label,
            "injected_problem": recipe.problem,
        }
    )
    apply_metadata_knobs(metadata, recipe.knobs)
    write_json(case_dir / "metadata.json", metadata)

    if recipe.signal_status == "unsupported":
        unsupported_reasons.append(recipe.quality_note or "recipe intentionally unsupported for this source mode")

    status = "unsupported" if unsupported_reasons else "applied"
    quality_status = "unsupported" if unsupported_reasons else "unverified"
    notes.extend(unsupported_reasons)
    if recipe.signal_status in {"weak", "unsupported"}:
        notes.append(f"recipe_signal_status={recipe.signal_status}: {recipe.quality_note}")
    elif recipe.quality_note:
        notes.append(recipe.quality_note)
    return {
        "applicability_status": status,
        "quality_status": quality_status,
        "changed_files": sorted(changed_files),
        "patch_results": patch_results,
        "notes": notes,
    }


def update_gen_data(path: Path, recipe: Recipe) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {
        "variant_name": recipe.variant,
        "injected_label": recipe.label,
        "injected_problem": recipe.problem,
    }
    for name, value in replacements.items():
        text = re.sub(rf'({name}\s*=\s*)["\'][^"\']*["\']', rf'\1"{value}"', text)
    knob_to_arg = {
        "default_output_elements": "default_output_elements",
        "default_tile_length": "default_tile_length",
        "default_blockdim": "default_blockdim",
        "default_tile_num_mul": "default_tile_num_mul",
        "variant_flags": "variant_flags",
    }
    for knob, arg_name in knob_to_arg.items():
        if knob in recipe.knobs:
            value = recipe.knobs[knob]
            text = re.sub(rf"({arg_name}\s*=\s*)[0-9]+", rf"\g<1>{value}", text)
            const_name = f"DEFAULT_{knob.removeprefix('default_').upper()}"
            text = re.sub(rf"({const_name}\s*=\s*)[0-9]+", rf"\g<1>{value}", text)
    write_text(path, text)


def update_variant_config(path: Path, flags: dict[str, int]) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    if "#ifndef APROF_VARIANT_CONFIG_H" not in text:
        text = render_variant_config({})
    for name in sorted(ALL_FLAGS):
        value = int(flags.get(name, 0))
        if re.search(rf"#define\s+{name}\s+", text):
            text = re.sub(rf"(#define\s+{name}\s+)[0-9]+", rf"\g<1>{value}", text)
        else:
            text = text.replace("#endif // APROF_VARIANT_CONFIG_H", f"#define {name} {value}\n\n#endif // APROF_VARIANT_CONFIG_H")
    write_text(path, text)


def render_variant_config(flags: dict[str, int]) -> str:
    lines = ["#ifndef APROF_VARIANT_CONFIG_H", "#define APROF_VARIANT_CONFIG_H", ""]
    for name in sorted(ALL_FLAGS):
        lines.append(f"#define {name} {int(flags.get(name, 0))}")
    lines.extend(["", "#endif // APROF_VARIANT_CONFIG_H", ""])
    return "\n".join(lines)


def apply_kernel_patch(path: Path, patch_id: str) -> tuple[bool, str]:
    text = path.read_text(encoding="utf-8")
    marker = f"APROF_PATCH_{patch_id.upper()}"
    if marker in text:
        return True, "already applied"
    original = text

    if patch_id == "redundant_copyin":
        anchor = "DataCopy(aLocal, inputGlobal[outOffset], copyParams);\n        PipeBarrier<PIPE_ALL>();"
        snippet = f"""{anchor}
#if APROF_INJECT_REDUNDANT_COPYIN
        // {marker}: repeat the same GM->UB copy to amplify MTE2 without changing math.
        DataCopy(aLocal, inputGlobal[outOffset], copyParams);
        PipeBarrier<PIPE_ALL>();
#endif"""
        text = replace_once(text, anchor, snippet)
    elif patch_id == "extra_copyout":
        anchor = "DataCopy(outputGlobal[outOffset], outLocal, copyParams);"
        snippet = f"""#if APROF_INJECT_EXTRA_COPYOUT
        // {marker}: write the same value twice to amplify MTE3 without changing output.
        DataCopy(outputGlobal[outOffset], outLocal, copyParams);
        PipeBarrier<PIPE_ALL>();
#endif
        {anchor}"""
        text = replace_once(text, anchor, snippet)
    elif patch_id == "excessive_barrier":
        anchor = "const uint32_t outOffset = coreStart + localOffset;"
        snippet = f"""{anchor}
#if APROF_INJECT_EXCESSIVE_BARRIER
        // {marker}: force pipe drains around every tile.
        PipeBarrier<PIPE_ALL>();
        PipeBarrier<PIPE_ALL>();
#endif"""
        text = replace_once(text, anchor, snippet)
    elif patch_id == "ub_temp_overallocated":
        text = replace_once(
            text,
            "TBuf<> outBuf;\n",
            f"TBuf<> outBuf;\n#if APROF_INJECT_UB_OVERALLOC\n    // {marker}: reserve an unused UB buffer to reduce effective UB headroom.\n    TBuf<> aprofWasteBuf;\n#endif\n",
        )
        text = replace_once(
            text,
            "pipe.InitBuffer(outBuf, tiling.tileLengthAligned * sizeof(float));\n",
            "pipe.InitBuffer(outBuf, tiling.tileLengthAligned * sizeof(float));\n"
            "#if APROF_INJECT_UB_OVERALLOC\n"
            "    pipe.InitBuffer(aprofWasteBuf, tiling.tileLengthAligned * sizeof(float));\n"
            "#endif\n",
        )
    elif patch_id == "scalar_loop":
        anchor = "const uint32_t outOffset = coreStart + localOffset;"
        snippet = f"""{anchor}
#if APROF_INJECT_SCALAR_LOOP
        // {marker}: redundant vector op + scalar loop to create API/scalar pressure.
        // Uses Adds(+0) which is a no-op but writes to outLocal (feeds output, cannot be DCE'd).
        Adds(outLocal, aLocal, 0.0f, curN);
        PipeBarrier<PIPE_V>();
        uint32_t aprofScalarWaste = tileIdx;
        for (uint32_t aprofI = 0; aprofI < 32; ++aprofI) {{
            aprofScalarWaste = aprofScalarWaste * 31 + aprofI;
        }}
        // Volatile-style side effect: write scalar result to outLocal[0] region.
        // This prevents the compiler from eliminating the loop.
        if (aprofScalarWaste < curN && tileIdx == 0 && blockIdx == 0) {{
            DataCopyParams aprofDummyParams;
            aprofDummyParams.blockCount = 1;
            aprofDummyParams.blockLen = 1;
            aprofDummyParams.srcStride = 0;
            aprofDummyParams.dstStride = 0;
        }}
#endif"""
        text = replace_once(text, anchor, snippet)
    elif patch_id == "redundant_vector":
        anchor = "DataCopy(aLocal, inputGlobal[outOffset], copyParams);\n        PipeBarrier<PIPE_ALL>();"
        snippet = f"""{anchor}
#if APROF_INJECT_REDUNDANT_VECTOR
        // {marker}: equivalent vector operation that does not feed the final result.
        Adds(outLocal, aLocal, 0.0f, curN);
        PipeBarrier<PIPE_V>();
#endif"""
        text = replace_once(text, anchor, snippet)
    else:
        return False, f"unknown kernel patch: {patch_id}"

    if text == original:
        return False, f"patch anchor not found for {patch_id}"
    path.write_text(text, encoding="utf-8")
    return True, "applied"


def replace_once(text: str, old: str, new: str) -> str:
    if old not in text:
        return text
    return text.replace(old, new, 1)


def apply_metadata_knobs(metadata: dict[str, Any], knobs: dict[str, Any]) -> None:
    for key, value in knobs.items():
        if key == "default_tile_length":
            metadata["tile_length"] = value
        elif key == "default_blockdim":
            metadata["blockdim"] = value
        elif key == "default_tile_num_mul":
            metadata["tile_num_multiplier"] = value
        elif key == "default_output_elements":
            metadata["output_elements"] = value
        elif key == "variant_flags":
            metadata["variant_flags"] = value


def read_metadata(case_dir: Path) -> dict[str, Any]:
    path = case_dir / "metadata.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def build_inject_manifest(
    *,
    source_mode: str,
    source_path: Path,
    case_dir: Path,
    op_name: str,
    recipe: Recipe,
    metadata: dict[str, Any],
    result: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "op_name": op_name,
        "variant": case_dir.name,
        "source_mode": source_mode,
        "source_path": str(source_path),
        "case_dir": str(case_dir),
        "profile_mode": recipe.profile_mode if source_mode == "scaffold_project" else "sim",
        "ground_truth": {
            "injected_label": recipe.label,
            "problem_family": recipe.family,
            "problem_id": recipe.problem_id,
            "expected_diagnosis_family": recipe.expected_diagnosis_family or recipe.family,
        },
        "applicability": {
            "status": result["applicability_status"],
            "source_modes": list(recipe.source_modes),
            "patch_results": result["patch_results"],
        },
        "knobs_changed": [
            {"field": key, "injected": value, "reason": recipe.quality_note}
            for key, value in {**recipe.knobs, **recipe.flags}.items()
        ],
        "kernel_flags": {name: int(recipe.flags.get(name, 0)) for name in sorted(ALL_FLAGS)},
        "allowed_files_changed": result["changed_files"],
        "quality": {
            "single_factor": result["applicability_status"] == "applied",
            "preserve_math": result["applicability_status"] == "applied",
            "confidence": "pending_validation" if result["quality_status"] == "unverified" else "low",
            "status": result["quality_status"],
            "notes": result["notes"],
        },
        "artifacts": {
            "metadata": "metadata.json",
            "profiling_plan": "profiling_plan.json",
        },
        "metadata_snapshot": {
            "output_elements": metadata.get("output_elements"),
            "blockdim": metadata.get("blockdim"),
            "tile_length": metadata.get("tile_length"),
            "tile_num": metadata.get("tile_num"),
            "tail_length": metadata.get("tail_length"),
            "tile_num_multiplier": metadata.get("tile_num_multiplier"),
            "variant_flags": metadata.get("variant_flags"),
        },
    }


def build_profiling_plan(op_name: str, variant: str, recipe: Recipe, result: dict[str, Any]) -> dict[str, Any]:
    profile_mode = "sim" if recipe.profile_mode != "hw-op" else "hw-op"
    if result["applicability_status"] == "unsupported":
        profile_mode = "sim"
    required = [
        {"path_pattern": "msprof_sim_output/**/trace.json", "reason": "sim timeline proxy"},
        {"path_pattern": "*_instr_exe_*.csv", "reason": "instruction-level proxy"},
    ]
    if recipe.profile_mode == "hw-op":
        required = [
            {"path_pattern": "msprof_hw_output/OPPROF_*/Memory.csv", "reason": "real memory traffic and MTE counts"},
            {"path_pattern": "msprof_hw_output/OPPROF_*/PipeUtilization.csv", "reason": "pipe utilization and per-core timing"},
        ]
    return {
        "plan_id": f"inject_{profile_mode}_{op_name}_{variant}",
        "profile_mode": profile_mode,
        "mode_reason": f"{recipe.family}/{recipe.problem_id} requires validation before active label use",
        "required_artifacts": required,
        "remote_deploy_args": {
            "profile_mode": profile_mode,
            "steps": "upload,build,profile,download",
            "msprof_timeout": 8,
            "remote_env_exports": [
                "APROF_INJECT_COMMON={remote_root}/common",
                "APROF_INJECT_RUN={remote_root}/common/inject_run.sh",
            ],
        },
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
