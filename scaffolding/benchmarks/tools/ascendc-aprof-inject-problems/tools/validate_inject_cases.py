#!/usr/bin/env python3
"""Validate AProf injected benchmark case structure and manifests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


REQUIRED_SIM_FILES = [
    "run.sh",
    "scripts/gen_data.py",
    "op_kernel/aprof_variant_config.h",
    "metadata.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate injected benchmark cases")
    parser.add_argument("--op-root", required=True, help="benchmarks/aprof_injected_ops/<op>")
    parser.add_argument("--write-report", action="store_true", help="Write inject_validation_report.json")
    args = parser.parse_args()

    op_root = Path(args.op_root).resolve()
    if not op_root.is_dir():
        raise SystemExit(f"op root not found: {op_root}")

    cases = []
    for case_dir in sorted(op_root.iterdir()):
        if not case_dir.is_dir() or (case_dir.name != "baseline" and not case_dir.name.startswith("inject_")):
            continue
        cases.append(validate_case(case_dir))

    report = {
        "schema_version": 1,
        "op_name": op_root.name,
        "cases": cases,
        "summary": {
            "total": len(cases),
            "passed": sum(1 for c in cases if c["pass"]),
            "failed": sum(1 for c in cases if not c["pass"]),
            "weak": sum(1 for c in cases if c.get("quality_status") in {"weak", "deprecated_or_weak"}),
            "unverified": sum(1 for c in cases if c.get("quality_status") == "unverified"),
            "unsupported": sum(1 for c in cases if c.get("quality_status") == "unsupported"),
        },
    }
    if args.write_report:
        (op_root / "inject_validation_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["summary"]["failed"] == 0 else 1


def validate_case(case_dir: Path) -> dict:
    missing = [rel for rel in REQUIRED_SIM_FILES if not (case_dir / rel).exists()]
    metadata = read_json(case_dir / "metadata.json")
    inject_manifest = read_json(case_dir / "inject_manifest.json")
    quality_status = inject_manifest.get("quality", {}).get("status", "missing_manifest")
    ground_truth = inject_manifest.get("ground_truth", {})
    applicability = inject_manifest.get("applicability", {})
    warnings: list[str] = []
    errors: list[str] = []

    if case_dir.name.startswith("inject_") and metadata.get("injected_label") in {None, "baseline"}:
        errors.append("inject case has no injected_label")
    if case_dir.name.startswith("inject_") and quality_status == "active":
        if not ground_truth.get("problem_family") or not ground_truth.get("problem_id"):
            errors.append("active inject case must include ground_truth.problem_family and ground_truth.problem_id")
        if applicability.get("status") not in {"applied", "validated"}:
            errors.append("active inject case must have applicability.status=applied or validated")
    if case_dir.name == "inject_blockdim" and metadata.get("blockdim") == read_baseline_blockdim(case_dir):
        warnings.append("blockdim equals baseline; sim-only blockdim signal is weak")
    if case_dir.name == "inject_dynshape":
        warnings.append("dynshape should be validated with multi-shape or scaffold_project host tiling")
    if case_dir.name == "inject_tilenum" and metadata.get("tile_num_multiplier", 1) != 1 and metadata.get("tile_length") != 256:
        warnings.append("tilenum changes tile_num_multiplier and tile_length; not a clean single-factor case")

    passed = not missing and quality_status != "missing_manifest" and not errors
    return {
        "variant": case_dir.name,
        "pass": passed,
        "missing": missing,
        "injected_label": metadata.get("injected_label", "unknown"),
        "problem_family": ground_truth.get("problem_family", metadata.get("problem_family", "unknown")),
        "problem_id": ground_truth.get("problem_id", metadata.get("problem_id", "unknown")),
        "applicability_status": applicability.get("status", "unknown"),
        "quality_status": quality_status,
        "errors": errors,
        "warnings": warnings,
    }


def read_baseline_blockdim(case_dir: Path) -> int | None:
    baseline = case_dir.parent / "baseline" / "metadata.json"
    if not baseline.is_file():
        return None
    return read_json(baseline).get("blockdim")


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
