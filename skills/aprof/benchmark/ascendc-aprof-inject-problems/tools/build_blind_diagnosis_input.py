#!/usr/bin/env python3
"""Build a sanitized single-case input for aprof-diagnosis-agent.

The output is intentionally independent from any baseline. It keeps neutral
source/shape/tiling/profile facts and removes injection ground truth labels.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SAFE_METADATA_KEYS = {
    "op_name",
    "output_elements",
    "input_elements",
    "input_stride",
    "output_stride",
    "blockdim",
    "tile_length",
    "tile_num",
    "tail_length",
    "tile_num_multiplier",
    "dtype",
    "format",
}

FORBIDDEN_KEYS = {
    "variant",
    "variant_name",
    "label",
    "injected_label",
    "injected_problem",
    "problem",
    "problem_family",
    "problem_id",
    "quality_status",
    "quality_note",
    "knobs",
}

FORBIDDEN_FILES = {
    "inject_manifest.json",
    "inject_audit_report.json",
    "label_alignment_report.json",
}

SOURCE_PATTERNS = ("*.asc", "*.cpp", "*.cc", "*.c", "*.h", "*.hpp")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build blind single-case diagnosis input")
    parser.add_argument("--case-dir", required=True, help="Single kernel/case directory")
    parser.add_argument("--out", required=True, help="Output JSON path")
    parser.add_argument("--case-id", default="anonymous_case", help="Opaque case id")
    parser.add_argument("--hardware-context-json", default="", help="Optional hardware context JSON")
    parser.add_argument("--trace", action="append", default=[], help="Optional trace.json path; can repeat")
    parser.add_argument("--max-source-bytes", type=int, default=80000)
    parser.add_argument("--max-top-events", type=int, default=20)
    args = parser.parse_args()

    case_dir = Path(args.case_dir).resolve()
    if not case_dir.is_dir():
        raise SystemExit(f"case dir not found: {case_dir}")

    payload = {
        "case_id": args.case_id,
        "input_policy": {
            "single_case_only": True,
            "baseline_allowed": False,
            "ground_truth_allowed": False,
            "ground_truth_fields_redacted": True,
            "ground_truth_files_redacted": True,
        },
        "kernel": {
            "source_files": collect_sources(case_dir, args.max_source_bytes),
            "metadata": collect_safe_metadata(case_dir),
        },
        "profiling_artifacts": {
            "trace_summaries": [
                summarize_trace(Path(trace).resolve(), args.max_top_events) for trace in args.trace
            ],
        },
        "hardware_context": load_hardware_context(args.hardware_context_json),
        "required_output_contract": "skills/aprof/references/contracts.md#single_case_diagnosisjson",
        "diagnosis_requirements": [
            "Diagnose this kernel independently; do not compare with baseline.",
            "For each diagnosis item, provide at least two supporting metrics.",
            "Use roofline-single-case.md and mark evidence as direct, estimated, or trace-proxy.",
            "Do not infer or mention injected labels, variants, or ground truth.",
        ],
    }

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(out)
    return 0


def collect_sources(case_dir: Path, max_source_bytes: int) -> list[dict[str, Any]]:
    roots = [case_dir / "op_kernel", case_dir]
    files: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for pattern in SOURCE_PATTERNS:
            files.extend(root.rglob(pattern))

    seen: set[Path] = set()
    results: list[dict[str, Any]] = []
    remaining = max_source_bytes
    for path in sorted(files):
        if path in seen:
            continue
        seen.add(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        text = sanitize_text(text)
        if remaining <= 0:
            truncated = True
            text = ""
        else:
            truncated = len(text.encode("utf-8")) > remaining
            text = text[:remaining]
            remaining -= len(text.encode("utf-8"))
        results.append(
            {
                "path": sanitize_path(path.relative_to(case_dir)),
                "content": text,
                "truncated": truncated,
            }
        )
    return results


def collect_safe_metadata(case_dir: Path) -> dict[str, Any]:
    metadata_path = case_dir / "metadata.json"
    if not metadata_path.is_file():
        return {}
    raw = json.loads(metadata_path.read_text(encoding="utf-8"))
    return {key: raw[key] for key in SAFE_METADATA_KEYS if key in raw}


def load_hardware_context(path_text: str) -> dict[str, Any]:
    if not path_text:
        return {
            "status": "missing",
            "required_params": [
                "soc_version",
                "aiv_core_num",
                "aic_core_num",
                "ub_bytes_per_core",
                "frequency_hz",
                "vector_peak_flops",
                "cube_peak_flops",
                "gm_bandwidth_bytes_per_s",
            ],
            "note": "Provide this via --hardware-context-json for direct roofline; otherwise diagnosis must use estimated/proxy evidence.",
        }
    path = Path(path_text).resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    return sanitize_obj(data)


def summarize_trace(path: Path, max_top_events: int) -> dict[str, Any]:
    if not path.is_file():
        return {"path": "anonymous_trace.json", "error": "not found"}
    data = json.loads(path.read_text(encoding="utf-8"))
    events = data.get("traceEvents", data) if isinstance(data, dict) else data
    if not isinstance(events, list):
        return {"path": "anonymous_trace.json", "error": "unsupported trace format"}

    counts: Counter[str] = Counter()
    duration_by_name: defaultdict[str, float] = defaultdict(float)
    timestamps: list[float] = []
    total_duration = 0.0

    for event in events:
        if not isinstance(event, dict):
            continue
        name = sanitize_text(str(event.get("name", event.get("op", "unknown"))))
        dur = to_float(event.get("dur", event.get("duration", 0.0)))
        ts = to_float(event.get("ts", event.get("timestamp", None)))
        counts[name] += 1
        duration_by_name[name] += dur
        total_duration += dur
        if ts is not None:
            timestamps.append(ts)

    top_by_duration = sorted(duration_by_name.items(), key=lambda item: item[1], reverse=True)[:max_top_events]
    top_by_count = counts.most_common(max_top_events)
    span = max(timestamps) - min(timestamps) if timestamps else None

    return {
        "path": "anonymous_trace.json",
        "event_count": sum(counts.values()),
        "timeline_span": span,
        "total_duration": total_duration,
        "top_by_duration": [{"name": name, "duration": dur} for name, dur in top_by_duration],
        "top_by_count": [{"name": name, "count": count} for name, count in top_by_count],
        "evidence_level": "trace-proxy",
    }


def sanitize_obj(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            sanitize_text(str(key)): sanitize_obj(item)
            for key, item in value.items()
            if str(key) not in FORBIDDEN_KEYS
        }
    if isinstance(value, list):
        return [sanitize_obj(item) for item in value]
    if isinstance(value, str):
        return sanitize_text(value)
    return value


def sanitize_text(text: str) -> str:
    text = re.sub(r"APROF_INJECT_[A-Z0-9_]+", "APROF_FEATURE_FLAG", text)
    text = re.sub(r"APROF_PATCH_[A-Z0-9_]+", "APROF_PATCH_MARKER", text)
    text = re.sub(r"\bMaybeInject[A-Za-z0-9_]*\b", "MaybeFeaturePath", text)
    text = re.sub(r"\binject_[A-Za-z0-9_]+\b", "anonymous_variant", text)
    text = re.sub(r"\binjected_(label|problem)\b", "redacted_ground_truth", text)
    return text


def sanitize_path(path: Path) -> str:
    parts = [sanitize_text(part) for part in path.parts]
    return str(Path(*parts))


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    raise SystemExit(main())
