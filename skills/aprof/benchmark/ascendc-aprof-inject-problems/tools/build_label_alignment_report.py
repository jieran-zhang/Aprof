#!/usr/bin/env python3
"""Build a label alignment report for injected benchmark cases.

The tool can consume optional diagnosis predictions. Without predictions it
marks active cases as pending and weak/deprecated cases as skipped.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build inject label alignment report")
    parser.add_argument("--op-root", required=True, help="benchmarks/aprof_injected_ops/<op>")
    parser.add_argument("--predictions", default="", help="Optional JSON mapping variant -> predicted_label")
    parser.add_argument("--write", action="store_true", help="Write label_alignment_report.json and .md")
    args = parser.parse_args()

    op_root = Path(args.op_root).resolve()
    predictions = read_json(Path(args.predictions)) if args.predictions else {}
    cases = []
    for case_dir in sorted(op_root.iterdir()):
        if not case_dir.is_dir() or (case_dir.name != "baseline" and not case_dir.name.startswith("inject_")):
            continue
        manifest = read_json(case_dir / "inject_manifest.json")
        metadata = read_json(case_dir / "metadata.json")
        if not metadata:
            continue
        cases.append(build_case(case_dir.name, manifest, metadata, predictions))

    summary = {
        "total": len(cases),
        "passed": sum(1 for c in cases if c["status"] == "pass"),
        "failed": sum(1 for c in cases if c["status"] == "fail"),
        "pending": sum(1 for c in cases if c["status"] == "pending"),
        "skipped": sum(1 for c in cases if c["status"] == "skipped"),
    }
    report = {
        "schema_version": 1,
        "op_name": op_root.name,
        "cases": cases,
        "summary": summary,
    }
    if args.write:
        write_json(op_root / "label_alignment_report.json", report)
        (op_root / "label_alignment_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if summary["failed"] == 0 else 1


def build_case(variant: str, manifest: dict, metadata: dict, predictions: dict) -> dict:
    label = metadata.get("injected_label", "unknown")
    quality = manifest.get("quality", {})
    quality_status = quality.get("status", "missing_manifest")
    predicted = prediction_for(predictions, variant)
    if quality_status in {"weak", "deprecated_or_weak", "missing_manifest"}:
        status = "skipped"
        reason = f"quality_status={quality_status}"
    elif predicted is None:
        status = "pending"
        reason = "no diagnosis prediction provided"
    elif predicted == label:
        status = "pass"
        reason = ""
    else:
        status = "fail"
        reason = f"predicted_label={predicted}"
    return {
        "variant": variant,
        "ground_truth_label": label,
        "predicted_label": predicted,
        "status": status,
        "quality_status": quality_status,
        "reason": reason,
        "evidence": [
            f"metadata.tile_length={metadata.get('tile_length')}",
            f"metadata.tile_num={metadata.get('tile_num')}",
            f"metadata.tail_length={metadata.get('tail_length')}",
            f"metadata.variant_flags={metadata.get('variant_flags')}",
        ],
    }


def prediction_for(predictions: dict, variant: str) -> str | None:
    value = predictions.get(variant)
    if isinstance(value, dict):
        return value.get("predicted_label")
    if isinstance(value, str):
        return value
    return None


def render_markdown(report: dict) -> str:
    lines = [
        f"# {report['op_name']} Label Alignment",
        "",
        "## Summary",
        "",
        f"- Total: {report['summary']['total']}",
        f"- Passed: {report['summary']['passed']}",
        f"- Failed: {report['summary']['failed']}",
        f"- Pending: {report['summary']['pending']}",
        f"- Skipped: {report['summary']['skipped']}",
        "",
        "## Cases",
        "",
        "| Variant | Ground Truth | Predicted | Status | Reason |",
        "| ------- | ------------ | --------- | ------ | ------ |",
    ]
    for case in report["cases"]:
        lines.append(
            "| {variant} | {ground_truth_label} | {predicted_label} | {status} | {reason} |".format(
                **{k: str(v) for k, v in case.items()}
            )
        )
    lines.append("")
    return "\n".join(lines)


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
