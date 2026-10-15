#!/usr/bin/env python3
"""Normalize real msprof-op tables without dropping core/invocation provenance.

All profile values are medians of the recorded rows, not kernel timing samples.
The raw CSVs and deterministic combined tables remain in CAS for replay.
"""
from __future__ import annotations

from aprof_layout import skill_lib

import argparse
import csv
import importlib.util
import json
import math
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(skill_lib() / "runtime/src"))
from aprof_runtime.errors import ContractError
from aprof_runtime.jsonio import canonical_json, file_hash
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact, validate_trace_contract

_SPEC = importlib.util.spec_from_file_location("aprof_profile_compressor", skill_lib() / "skills/ascendc-aprof-profiling/scripts/compress_msprof.py")
_COMPRESSOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_COMPRESSOR)

TABLE_NAMES = {name.lower(): name for name in ("OpBasicInfo", "PipeUtilization", "Memory",
    "ArithmeticUtilization", "ResourceConflictRatio", "L2Cache", "MemoryUB", "MemoryL0", "per_core_cycles")}
IDENTIFIERS = {"block_id", "sub_block_id", "core id", "core id", "core_id", "coreid", "device id", "pid"}
METADATA = ("aprof_kernel", "aprof_invocation", "aprof_source_hash", "aprof_source_path", "aprof_source_row")
MISSING = {"", "NA", "N/A", "--"}


def _write_json(path, value):
    encoded = canonical_json(value) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() != encoded:
        raise FileExistsError(f"refusing to replace different normalization output: {path}")
    path.write_text(encoded)


def _unit(field):
    units = re.findall(r"\(([^)]+)\)", field)
    for unit in units:
        if unit in {"ns", "us", "ms", "s", "%", "GB/s", "MB/s", "KB/s", "B/s", "KB", "MB", "GB", "B"}:
            return unit
    lower = field.lower()
    if lower.endswith("_ratio") or lower.endswith("_miss_rate"):
        return "ratio"
    if "cycles" in lower:
        return "cycles"
    if "instructions" in lower or "instr_number" in lower:
        return "instructions"
    if lower.endswith("_fops"):
        return "operations"
    if lower in {"block dim", "block num", "mix block dim"}:
        return "blocks"
    return "unspecified"


def _safe_name(kernel):
    # Keep kernel names readable without allowing path traversal or collisions.
    if re.fullmatch(r"[A-Za-z0-9_.-]+", kernel) and kernel not in {".", ".."}:
        return kernel
    import hashlib
    return "kernel-" + hashlib.sha256(kernel.encode()).hexdigest()[:16]


def normalize_profile(raw_dir, out_dir, case_id, store, kernel=None):
    """Return manifest/profile paths and CAS hashes for every observed kernel.

    A supplied kernel is an exact filter. Input is one workload case; never pass
    a campaign directory mixing cases. Idempotent only for identical output.
    """
    raw_dir, out_dir = Path(raw_dir).resolve(), Path(out_dir).resolve()
    if not raw_dir.is_dir() or out_dir == raw_dir or raw_dir in out_dir.parents:
        raise ValueError("normalization output must be outside the raw profile directory")
    if isinstance(case_id, bool) or not isinstance(case_id, int) or case_id < 1:
        raise ValueError("case_id must be a positive integer")
    grouped = defaultdict(list)
    raw_artifacts, warnings = [], []
    for path in sorted(raw_dir.rglob("*.csv")):
        kind = _COMPRESSOR._csv_kind(path)
        if kind is None:
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = reader.fieldnames or []
            if len(fields) != len(set(fields)) or any(field in fields for field in METADATA):
                raise ContractError(f"duplicate/reserved CSV fields: {path}")
            rows = list(reader)
        if any(None in row for row in rows):
            raise ContractError(f"ragged CSV row: {path}")
        digest = store.register_artifact(path, media_type="text/csv")
        relative = path.relative_to(raw_dir).as_posix()
        raw_artifacts.append({"path": relative, "content_hash": digest, "kind": kind, "row_count": len(rows)})
        context_kernel = _COMPRESSOR._context_kernel(path)
        for row_index, row in enumerate(rows, 1):
            row_kernel = (row.get("Op Name") or row.get("OP Name") or context_kernel or kernel)
            if not row_kernel:
                warnings.append(f"kernel identity unavailable: {relative}:{row_index}")
                continue
            if kernel is not None and row_kernel != kernel:
                continue
            table = TABLE_NAMES.get(kind, kind)
            invocation = path.parent.relative_to(raw_dir).as_posix()
            expanded = {**row, "aprof_kernel": row_kernel, "aprof_invocation": invocation,
                "aprof_source_hash": digest, "aprof_source_path": relative, "aprof_source_row": str(row_index)}
            grouped[(row_kernel, table)].append((fields, expanded))
    if not grouped:
        raise ValueError("no supported rows with a known kernel identity")

    profiles = {}
    combined_tables = []
    metric_notes = []
    for (row_kernel, table), records in sorted(grouped.items()):
        target = out_dir / _safe_name(row_kernel) / "combined" / (table + ".csv")
        target.parent.mkdir(parents=True, exist_ok=True)
        fields = list(dict.fromkeys(field for original, _ in records for field in original))
        rows = [row for _, row in records]
        import io
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fields + list(METADATA), lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)
        data = stream.getvalue()
        if target.exists() and target.read_text() != data:
            raise FileExistsError(f"refusing to replace different combined table: {target}")
        target.write_text(data, newline="")
        combined_hash = store.register_artifact(target, media_type="text/csv")
        profile = profiles.setdefault(row_kernel, {"schema_version": "1.0.0", "case_id": case_id,
                                                   "kernel": row_kernel, "metrics": {}})
        for field in fields:
            if not field or field.lower() in IDENTIFIERS:
                continue
            samples = []
            invalid = []
            missing_count = 0
            for row in rows:
                raw = row.get(field, "")
                if raw in MISSING or raw is None:
                    missing_count += 1
                    continue
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    invalid.append(raw)
                    continue
                if not math.isfinite(value):
                    invalid.append(raw)
                    continue
                samples.append(value)
            if not samples or invalid:
                metric_notes.append({"kernel": row_kernel, "table": table, "field": field,
                    "status": "omitted", "reason": "non-numeric/non-finite values" if invalid else "no numeric samples",
                    "missing_count": missing_count, "invalid_count": len(invalid)})
                continue
            unit = _unit(field)
            profile["metrics"][f"{table}/{field}"] = {"value": float(statistics.median(samples)),
                "unit": unit, "source_artifact_hash": combined_hash, "field": field,
                "aggregation": "median", "samples": samples}
            if missing_count or unit == "unspecified":
                metric_notes.append({"kernel": row_kernel, "table": table, "field": field,
                    "status": "partial" if missing_count else "unit_unspecified", "missing_count": missing_count,
                    "reason": "missing cells excluded; no values imputed" if missing_count else "CSV does not declare a unit"})
        combined_tables.append({"kernel": row_kernel, "table": table, "path": target.relative_to(out_dir).as_posix(),
            "content_hash": combined_hash, "row_count": len(rows), "invocations": sorted({row["aprof_invocation"] for row in rows}),
            "raw_artifact_hashes": sorted({row["aprof_source_hash"] for row in rows})})

    result_profiles = []
    manifest_profiles = []
    for name, profile in sorted(profiles.items()):
        validate_trace_contract("normalized-profile", profile)
        path = out_dir / _safe_name(name) / "normalized_profile.json"
        _write_json(path, profile)
        digest = register_json_artifact(store, profile)
        invocations = sorted({invocation for table in combined_tables if table["kernel"] == name for invocation in table["invocations"]})
        entry = {"kernel": name, "path": path.relative_to(out_dir).as_posix(), "content_hash": digest,
                 "metric_count": len(profile["metrics"]), "invocation_count": len(invocations)}
        manifest_profiles.append(entry)
        result_profiles.append({**entry, "path": str(path)})
    manifest = {"schema_version": "1.0.0", "case_id": case_id, "producer_hash": file_hash(__file__),
        "compressor_hash": file_hash(_SPEC.origin), "profiles": manifest_profiles, "raw_artifacts": raw_artifacts,
        "combined_tables": combined_tables, "metric_notes": metric_notes, "warnings": sorted(set(warnings)),
        "aggregation_scope": "median over observed core rows across profiled invocations; raw rows retained",
        "production_timing_eligible": False}
    manifest_path = out_dir / "normalization_manifest.json"
    _write_json(manifest_path, manifest)
    manifest_hash = register_json_artifact(store, manifest)
    return {"schema_version": "1.0.0", "manifest_path": str(manifest_path), "manifest_hash": manifest_hash,
            "profiles": result_profiles, "warnings": manifest["warnings"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--case", required=True, type=int)
    parser.add_argument("--store", required=True)
    parser.add_argument("--kernel")
    args = parser.parse_args()
    with EpisodeStore(args.store) as store:
        result = normalize_profile(args.raw, args.output, args.case, store, args.kernel)
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == "__main__":
    main()
