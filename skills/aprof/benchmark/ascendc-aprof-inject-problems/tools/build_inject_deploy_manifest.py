#!/usr/bin/env python3
"""Build batch deploy manifests for AProf injected benchmark cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build inject_deploy_manifest.json for an op")
    parser.add_argument("--op-root", required=True, help="benchmarks/aprof_injected_ops/<op>")
    parser.add_argument("--common-dir", default="", help="benchmarks/aprof_injected_ops/common")
    parser.add_argument("--profile-mode", choices=("sim", "hw-msprof", "hw-op"), default="sim")
    parser.add_argument("--include-baseline", action="store_true", help="Include baseline as a deploy case")
    parser.add_argument("--write-case-plans", action="store_true", help="Create missing per-case profiling_plan.json")
    args = parser.parse_args()

    op_root = Path(args.op_root).resolve()
    if not op_root.is_dir():
        raise SystemExit(f"op root not found: {op_root}")
    common_dir = Path(args.common_dir).resolve() if args.common_dir else op_root.parent / "common"
    batch_local_out = op_root / "remote_inject_out"

    cases = []
    for case_dir in sorted(op_root.iterdir()):
        if not case_dir.is_dir():
            continue
        if case_dir.name == "baseline" and not args.include_baseline:
            continue
        if case_dir.name != "baseline" and not case_dir.name.startswith("inject_"):
            continue
        metadata_path = case_dir / "metadata.json"
        if not metadata_path.is_file():
            continue
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        profiling_plan = case_dir / "profiling_plan.json"
        if args.write_case_plans and not profiling_plan.exists():
            write_json(profiling_plan, build_sim_plan(metadata, case_dir.name))
        inject_manifest = case_dir / "inject_manifest.json"
        quality_status = "unknown"
        if inject_manifest.is_file():
            manifest_data = json.loads(inject_manifest.read_text(encoding="utf-8"))
            quality_status = manifest_data.get("quality", {}).get("status", "unknown")
            ground_truth = manifest_data.get("ground_truth", {})
            applicability = manifest_data.get("applicability", {})
        else:
            ground_truth = {}
            applicability = {}
        cases.append(
            {
                "variant": case_dir.name,
                "local_dir": str(case_dir),
                "local_out": str(batch_local_out / case_dir.name),
                "profiling_plan": str(profiling_plan),
                "inject_manifest": str(inject_manifest) if inject_manifest.exists() else "",
                "ground_truth_label": metadata.get("injected_label", "unknown"),
                "problem_family": ground_truth.get("problem_family", metadata.get("problem_family", "unknown")),
                "problem_id": ground_truth.get("problem_id", metadata.get("problem_id", "unknown")),
                "applicability_status": applicability.get("status", "unknown"),
                "quality_status": quality_status,
            }
        )

    manifest = {
        "schema_version": 1,
        "op_name": op_root.name,
        "source_root": str(op_root),
        "inject_common_dir": str(common_dir),
        "profile_mode": args.profile_mode,
        "batch_local_out": str(batch_local_out),
        "cases": cases,
    }
    out = op_root / "inject_deploy_manifest.json"
    write_json(out, manifest)
    print(json.dumps(manifest, indent=2, ensure_ascii=False))
    return 0


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


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
