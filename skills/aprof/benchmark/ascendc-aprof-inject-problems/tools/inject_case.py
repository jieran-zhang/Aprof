#!/usr/bin/env python3
"""Generate an AProf injected benchmark case from a baseline or kernel.

The tool is intentionally conservative: it only creates a new case directory
and writes metadata/manifests. It refuses to overwrite existing cases unless
--force is provided.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path


RECIPE_DEFAULTS: dict[str, dict] = {
    "blockdim": {
        "variant": "inject_blockdim",
        "label": "blockdim_too_small",
        "problem": "blockDim 设置过大或过小，导致部分 core 空转或单 core 压力过高。",
        "knobs": {"default_blockdim": 1},
        "quality_status": "weak",
        "quality_note": "sim-only blockDim case cannot prove host-side scheduling issues",
    },
    "tail": {
        "variant": "inject_tail",
        "label": "tail_inefficient",
        "problem": "tail 处理低效，例如尾块单独走低效分支或重复搬运。",
        "knobs": {"variant_flags": 1, "APROF_INJECT_TAIL": 1},
        "quality_status": "active",
        "quality_note": "tail reload is injected in kernel via APROF_INJECT_TAIL",
    },
    "tilelen_small": {
        "variant": "inject_tilelen_small",
        "label": "tileLength_too_small",
        "problem": "tileLength 过小，导致循环和同步开销占比变高。",
        "knobs": {"default_tile_length": 16},
        "quality_status": "active",
        "quality_note": "small tileLength increases tile count and sync overhead",
    },
    "tilelen_large": {
        "variant": "inject_tilelen_large",
        "label": "tileLength_too_large",
        "problem": "tileLength 过大，导致 UB 压力变高、流水粒度过粗。",
        "knobs": {"default_tile_length": 4096},
        "quality_status": "active",
        "quality_note": "keep output size unchanged when possible to preserve single-factor injection",
    },
    "tilenum": {
        "variant": "inject_tilenum",
        "label": "tileNum_unreasonable",
        "problem": "tileNum 不合理，导致 tile 调度次数异常或尾块过多。",
        "knobs": {"default_tile_num_mul": 4},
        "quality_status": "active",
        "quality_note": "tile_num_multiplier is the intended single-factor knob",
    },
    "dynshape": {
        "variant": "inject_dynshape",
        "label": "fixed_tiling_dynamic_shape",
        "problem": "动态 shape 下仍使用固定 Tiling 策略，导致不同 shape 性能波动明显。",
        "knobs": {"variant_flags": 2, "APROF_INJECT_DYNSHAPE": 1},
        "quality_status": "weak",
        "quality_note": "dynamic-shape injection needs multi-shape comparison or host tiling",
    },
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Create an AProf injected case")
    parser.add_argument("--source-mode", choices=("existing_aprof_baseline", "kernel_only", "scaffold_project"), required=True)
    parser.add_argument("--source-path", required=True, help="Baseline dir, kernel file, or scaffold project")
    parser.add_argument("--output-root", required=True, help="Directory containing baseline/inject_* cases")
    parser.add_argument("--op-name", default="", help="Operator name; inferred when omitted")
    parser.add_argument("--problem-family", choices=sorted(RECIPE_DEFAULTS), required=True)
    parser.add_argument("--variant", default="", help="Override variant directory name")
    parser.add_argument("--force", action="store_true", help="Overwrite existing output variant")
    args = parser.parse_args()

    source = Path(args.source_path).resolve()
    output_root = Path(args.output_root).resolve()
    recipe = dict(RECIPE_DEFAULTS[args.problem_family])
    variant = args.variant or str(recipe["variant"])
    case_dir = output_root / variant
    op_name = args.op_name or infer_op_name(source, output_root)

    if case_dir.exists():
        if not args.force:
            raise SystemExit(f"case already exists: {case_dir} (use --force to overwrite)")
        shutil.rmtree(case_dir)

    if args.source_mode == "existing_aprof_baseline":
        if not source.is_dir():
            raise SystemExit(f"baseline dir not found: {source}")
        shutil.copytree(source, case_dir, ignore=ignore_generated)
    elif args.source_mode == "kernel_only":
        create_kernel_only_case(source, case_dir, op_name)
    else:
        if not source.is_dir():
            raise SystemExit(f"scaffold project not found: {source}")
        shutil.copytree(source, case_dir, ignore=ignore_generated)

    apply_recipe(case_dir, op_name, args.problem_family, recipe)
    metadata = read_metadata(case_dir)
    inject_manifest = build_inject_manifest(
        source_mode=args.source_mode,
        source_path=source,
        case_dir=case_dir,
        op_name=op_name,
        problem_family=args.problem_family,
        recipe=recipe,
        metadata=metadata,
    )
    write_json(case_dir / "inject_manifest.json", inject_manifest)
    write_json(case_dir / "profiling_plan.json", build_sim_profiling_plan(op_name, variant))

    print(json.dumps(inject_manifest, indent=2, ensure_ascii=False))
    return 0


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


def create_kernel_only_case(kernel_path: Path, case_dir: Path, op_name: str) -> None:
    if not kernel_path.is_file():
        raise SystemExit(f"kernel file not found: {kernel_path}")
    (case_dir / "op_kernel").mkdir(parents=True)
    (case_dir / "scripts").mkdir()
    shutil.copy2(kernel_path, case_dir / "op_kernel" / f"{op_name}_kernel.asc")
    write_text(
        case_dir / "run.sh",
        '#!/usr/bin/env bash\nset -euo pipefail\n'
        f'OP_NAME="{op_name}"\n'
        'SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"\n'
        'INJECT_RUN="${APROF_INJECT_RUN:-$SCRIPT_DIR/../../common/inject_run.sh}"\n'
        '# shellcheck disable=SC1090\nsource "$INJECT_RUN" "$@"\n',
    )
    write_text(
        case_dir / "op_kernel" / "aprof_variant_config.h",
        "#ifndef APROF_VARIANT_CONFIG_H\n#define APROF_VARIANT_CONFIG_H\n\n"
        "#define APROF_INJECT_TAIL 0\n#define APROF_INJECT_DYNSHAPE 0\n\n"
        "#endif // APROF_VARIANT_CONFIG_H\n",
    )
    write_text(
        case_dir / "scripts" / "gen_data.py",
        "#!/usr/bin/env python3\n"
        "raise SystemExit('kernel_only scaffold needs a custom scripts/gen_data.py for this operator')\n",
    )


def apply_recipe(case_dir: Path, op_name: str, problem_family: str, recipe: dict) -> None:
    gen = case_dir / "scripts" / "gen_data.py"
    if gen.is_file():
        update_gen_data(gen, problem_family, recipe)
    cfg = case_dir / "op_kernel" / "aprof_variant_config.h"
    if cfg.is_file():
        update_variant_config(cfg, recipe)

    metadata = read_metadata(case_dir)
    metadata.update(
        {
            "op_name": metadata.get("op_name", op_name),
            "variant": recipe["variant"],
            "injected_label": recipe["label"],
            "injected_problem": recipe["problem"],
        }
    )
    for key, value in recipe["knobs"].items():
        if key == "default_tile_length":
            metadata["tile_length"] = value
        elif key == "default_blockdim":
            metadata["blockdim"] = value
        elif key == "default_tile_num_mul":
            metadata["tile_num_multiplier"] = value
        elif key == "variant_flags":
            metadata["variant_flags"] = value
    write_json(case_dir / "metadata.json", metadata)


def update_gen_data(path: Path, problem_family: str, recipe: dict) -> None:
    text = path.read_text(encoding="utf-8")
    replacements = {
        "variant_name": recipe["variant"],
        "injected_label": recipe["label"],
        "injected_problem": recipe["problem"],
    }
    for name, value in replacements.items():
        text = re.sub(rf'({name}\s*=\s*)["\'][^"\']*["\']', rf'\1"{value}"', text)
    knob_to_arg = {
        "default_tile_length": "default_tile_length",
        "default_blockdim": "default_blockdim",
        "default_tile_num_mul": "default_tile_num_mul",
        "variant_flags": "variant_flags",
    }
    for knob, arg_name in knob_to_arg.items():
        if knob in recipe["knobs"]:
            text = re.sub(rf"({arg_name}\s*=\s*)[0-9]+", rf"\g<1>{recipe['knobs'][knob]}", text)
            text = re.sub(rf"(DEFAULT_{knob.removeprefix('default_').upper()}\s*=\s*)[0-9]+", rf"\g<1>{recipe['knobs'][knob]}", text)
    write_text(path, text)


def update_variant_config(path: Path, recipe: dict) -> None:
    text = path.read_text(encoding="utf-8")
    for name in ("APROF_INJECT_TAIL", "APROF_INJECT_DYNSHAPE"):
        value = int(recipe["knobs"].get(name, 0))
        text = re.sub(rf"(#define\s+{name}\s+)[0-9]+", rf"\g<1>{value}", text)
    write_text(path, text)


def read_metadata(case_dir: Path) -> dict:
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
    problem_family: str,
    recipe: dict,
    metadata: dict,
) -> dict:
    return {
        "schema_version": 1,
        "op_name": op_name,
        "variant": case_dir.name,
        "source_mode": source_mode,
        "source_path": str(source_path),
        "case_dir": str(case_dir),
        "profile_mode": "sim" if source_mode != "scaffold_project" else "hw-msprof",
        "ground_truth": {
            "injected_label": recipe["label"],
            "problem_family": problem_family,
            "expected_diagnosis_family": diagnosis_family(problem_family),
        },
        "knobs_changed": [
            {"field": key, "injected": value, "reason": recipe["quality_note"]}
            for key, value in recipe["knobs"].items()
        ],
        "kernel_flags": {
            "APROF_INJECT_TAIL": int(recipe["knobs"].get("APROF_INJECT_TAIL", metadata.get("variant_flags") == 1)),
            "APROF_INJECT_DYNSHAPE": int(recipe["knobs"].get("APROF_INJECT_DYNSHAPE", metadata.get("variant_flags") == 2)),
        },
        "allowed_files_changed": [
            "scripts/gen_data.py",
            "op_kernel/aprof_variant_config.h",
            "metadata.json",
        ],
        "quality": {
            "single_factor": recipe["quality_status"] == "active",
            "preserve_math": True,
            "confidence": "high" if recipe["quality_status"] == "active" else "low",
            "status": recipe["quality_status"],
            "notes": [recipe["quality_note"]],
        },
        "artifacts": {
            "metadata": "metadata.json",
            "profiling_plan": "profiling_plan.json",
        },
    }


def build_sim_profiling_plan(op_name: str, variant: str) -> dict:
    return {
        "plan_id": f"inject_sim_{op_name}_{variant}",
        "profile_mode": "sim",
        "mode_reason": "AProf injected sim-only case uses run.sh build/sim and msprof op simulator",
        "required_artifacts": [
            {"path_pattern": "msprof_sim_output/**/trace.json", "reason": "sim timeline"},
            {"path_pattern": "*_instr_exe_*.csv", "reason": "instruction-level evidence"},
        ],
        "remote_deploy_args": {
            "profile_mode": "sim",
            "steps": "upload,build,profile,download",
            "msprof_timeout": 8,
            "remote_env_exports": [
                "APROF_INJECT_COMMON={remote_root}/common",
                "APROF_INJECT_RUN={remote_root}/common/inject_run.sh",
            ],
        },
    }


def diagnosis_family(problem_family: str) -> str:
    if problem_family in {"blockdim", "tilelen_small", "tilelen_large", "tilenum", "dynshape", "tail"}:
        return "tiling"
    return "unknown"


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
