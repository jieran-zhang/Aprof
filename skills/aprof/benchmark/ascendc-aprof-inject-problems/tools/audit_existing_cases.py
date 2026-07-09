#!/usr/bin/env python3
"""Audit existing AProf injected cases and write non-invasive manifests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


LABEL_TO_FAMILY = {
    "blockdim_too_small": "tiling",
    "tail_inefficient": "tiling",
    "tileLength_too_small": "tiling",
    "tileLength_too_large": "tiling",
    "tileNum_unreasonable": "tiling",
    "fixed_tiling_dynamic_shape": "tiling",
    "redundant_copyin": "data_movement",
    "extra_copyout": "data_movement",
    "small_datacopy_granularity": "data_movement",
    "serial_copy_compute_copyout": "pipeline_parallel",
    "double_buffer_disabled": "pipeline_parallel",
    "excessive_pipe_barrier": "pipeline_parallel",
    "ub_temp_overallocated": "onchip_memory",
    "gm_spill_intermediate": "onchip_memory",
    "low_ub_reuse": "onchip_memory",
    "underused_blockdim": "ai_core_utilization",
    "overlaunched_empty_cores": "ai_core_utilization",
    "tail_core_imbalance": "ai_core_utilization",
    "scalar_loop_redundant": "api_algorithm",
    "small_vector_api_chunks": "api_algorithm",
    "redundant_cast_or_vector_copy": "api_algorithm",
}

LABEL_TO_EXPECTED = {
    "baseline": "baseline",
}

LABEL_TO_PROBLEM_ID = {
    "blockdim_too_small": "blockdim_too_small",
    "tail_inefficient": "tail_inefficient",
    "tileLength_too_small": "tile_length_too_small",
    "tileLength_too_large": "tile_length_too_large",
    "tileNum_unreasonable": "tile_num_unreasonable",
    "fixed_tiling_dynamic_shape": "fixed_tiling_dynamic_shape",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit existing inject cases without changing source files")
    parser.add_argument("--op-root", required=True, help="benchmarks/aprof_injected_ops/<op>")
    parser.add_argument("--write", action="store_true", help="Write inject_manifest/profiling_plan/report files")
    args = parser.parse_args()

    op_root = Path(args.op_root).resolve()
    baseline = read_json(op_root / "baseline" / "metadata.json")
    cases = []
    for case_dir in sorted(op_root.iterdir()):
        if not case_dir.is_dir() or (case_dir.name != "baseline" and not case_dir.name.startswith("inject_")):
            continue
        metadata = read_json(case_dir / "metadata.json")
        if not metadata:
            continue
        audit = audit_case(case_dir, metadata, baseline)
        cases.append(audit)
        if args.write:
            write_json(case_dir / "inject_manifest.json", build_manifest(case_dir, metadata, audit))
            write_json(case_dir / "profiling_plan.json", build_sim_plan(metadata, case_dir.name))

    report = {
        "schema_version": 2,
        "op_name": op_root.name,
        "cases": cases,
        "summary": {
            "total": len(cases),
            "active": sum(1 for c in cases if c["quality_status"] == "active"),
            "weak": sum(1 for c in cases if c["quality_status"] == "weak"),
            "deprecated_or_weak": sum(1 for c in cases if c["quality_status"] == "deprecated_or_weak"),
        },
    }
    if args.write:
        write_json(op_root / "inject_audit_report.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


def audit_case(case_dir: Path, metadata: dict, baseline: dict) -> dict:
    label = metadata.get("injected_label", "unknown")
    warnings: list[str] = []
    status = "active"

    if label == "baseline":
        status = "active"
    elif label == "blockdim_too_small":
        if metadata.get("blockdim") == baseline.get("blockdim"):
            status = "deprecated_or_weak"
            warnings.append("blockdim equals baseline; current case changes workload size, not blockDim policy")
    elif label == "tileNum_unreasonable":
        if metadata.get("tile_length") != baseline.get("tile_length"):
            status = "weak"
            warnings.append("tileNum case also changes tile_length; not a clean single-factor case")
    elif label == "fixed_tiling_dynamic_shape":
        status = "weak"
        warnings.append("dynshape needs multi-shape comparison or host tiling scaffold")
        if metadata.get("tile_length") == metadata.get("output_elements"):
            warnings.append("tile_length equals output_elements after clamping; fixed-large-tiling signal is weak")
    elif label == "tileLength_too_large":
        if metadata.get("output_elements") != baseline.get("output_elements"):
            status = "weak"
            warnings.append("tileLength_large also changes output_elements; not a clean single-factor case")

    return {
        "variant": case_dir.name,
        "label": label,
        "problem_family": LABEL_TO_FAMILY.get(label, "baseline" if label == "baseline" else "unknown"),
        "quality_status": status,
        "single_factor": status == "active",
        "warnings": warnings,
        "metadata": {
            "output_elements": metadata.get("output_elements"),
            "blockdim": metadata.get("blockdim"),
            "tile_length": metadata.get("tile_length"),
            "tile_num": metadata.get("tile_num"),
            "tail_length": metadata.get("tail_length"),
            "tile_num_multiplier": metadata.get("tile_num_multiplier"),
            "variant_flags": metadata.get("variant_flags"),
        },
    }


def build_manifest(case_dir: Path, metadata: dict, audit: dict) -> dict:
    label = metadata.get("injected_label", "unknown")
    return {
        "schema_version": 1,
        "op_name": metadata.get("op_name", case_dir.parent.name),
        "variant": case_dir.name,
        "source_mode": "existing_aprof_baseline",
        "source_path": str(case_dir.parent / "baseline"),
        "case_dir": str(case_dir),
        "profile_mode": "sim",
        "ground_truth": {
            "injected_label": label,
            "problem_family": audit["problem_family"],
            "problem_id": metadata.get("problem_id", LABEL_TO_PROBLEM_ID.get(label, label)),
            "expected_diagnosis_family": LABEL_TO_EXPECTED.get(label, audit["problem_family"]),
        },
        "applicability": {
            "status": "applied" if audit["quality_status"] != "deprecated_or_weak" else "unverified",
            "source_modes": ["existing_aprof_baseline"],
            "patch_results": [],
        },
        "knobs_changed": infer_knobs(metadata, audit),
        "kernel_flags": {
            "APROF_INJECT_TAIL": 1 if metadata.get("variant_flags") == 1 else 0,
            "APROF_INJECT_DYNSHAPE": 1 if metadata.get("variant_flags") == 2 else 0,
        },
        "allowed_files_changed": [
            "scripts/gen_data.py",
            "op_kernel/aprof_variant_config.h",
            "metadata.json",
        ],
        "quality": {
            "single_factor": audit["single_factor"],
            "preserve_math": True,
            "confidence": "high" if audit["quality_status"] == "active" else "low",
            "status": audit["quality_status"],
            "notes": audit["warnings"],
        },
        "artifacts": {
            "metadata": "metadata.json",
            "profiling_plan": "profiling_plan.json",
        },
    }


def infer_knobs(metadata: dict, audit: dict) -> list[dict]:
    knobs = []
    for key in ("output_elements", "blockdim", "tile_length", "tile_num", "tail_length", "tile_num_multiplier", "variant_flags"):
        value = metadata.get(key)
        if value is not None:
            knobs.append({"field": key, "injected": value, "reason": "; ".join(audit["warnings"]) or audit["label"]})
    return knobs


def build_sim_plan(metadata: dict, variant: str) -> dict:
    op_name = metadata.get("op_name", "unknown")
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


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
