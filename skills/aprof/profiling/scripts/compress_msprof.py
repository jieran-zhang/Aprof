#!/usr/bin/env python3
"""Compress raw msprof/msprof-op CSV artifacts into an AProf symptom draft.

The output is deliberately a draft: measured fields and artifact hashes are
machine-derived, while thresholded predicates are labelled as expert
heuristics. Missing fields remain ``unknown`` and are never synthesized.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Any, Iterable


SCHEMA_VERSION = "1.0.0"
RELEVANT_NAMES = {
    "opbasicinfo.csv",
    "pipeutilization.csv",
    "memory.csv",
    "arithmeticutilization.csv",
    "resourceconflictratio.csv",
    "l2cache.csv",
    "memoryub.csv",
    "memoryl0.csv",
    "per_core_cycles.csv",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _number(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().rstrip("%")
    if not text or text.lower() in {"n/a", "na", "none", "-"}:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _read_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except (OSError, csv.Error):
        return []


def _csv_kind(path: Path) -> str | None:
    lower = path.name.lower()
    if lower in RELEVANT_NAMES:
        return lower.removesuffix(".csv")
    if lower.startswith("op_summary_"):
        suffix = lower.removeprefix("op_summary_").removesuffix(".csv")
        # CANNBot archives metric-specific files such as
        # op_summary_PipeUtilization.csv, while standard ``msprof --export``
        # writes a timestamped op_summary_<time>.csv containing the common
        # duration/block/pipe fields in one row.  Do not mistake the timestamp
        # for a metric kind or those fields will silently disappear.
        return suffix if suffix in {name.removesuffix(".csv") for name in RELEVANT_NAMES} else "op_summary"
    return None


def _matches_op(row: dict[str, str], op_name: str | None) -> bool:
    if not op_name:
        return True
    observed = (row.get("Op Name") or row.get("OP Name") or "").strip()
    return not observed or observed == op_name


def _candidate_rows(
    artifacts: Iterable[tuple[Path, str]], op_name: str | None
) -> tuple[list[tuple[Path, str, dict[str, str]]], list[str]]:
    candidates: list[tuple[Path, str, dict[str, str]]] = []
    warnings: list[str] = []
    for path, kind in artifacts:
        if kind == "per_core_cycles":
            continue
        rows = [row for row in _read_rows(path) if _matches_op(row, op_name)]
        if not rows:
            warnings.append(f"no matching rows: {path}")
            continue
        for row in rows:
            candidates.append((path, kind, row))
    return candidates, warnings


def _values(rows: Iterable[dict[str, str]], *keys: str) -> list[float]:
    result: list[float] = []
    for row in rows:
        for key in keys:
            value = _number(row.get(key))
            if value is not None:
                result.append(value)
                break
    return result


def _maximum(rows: Iterable[dict[str, str]], *keys: str) -> float | None:
    values = _values(rows, *keys)
    return max(values) if values else None


def _median(rows: Iterable[dict[str, str]], *keys: str) -> float | None:
    values = _values(rows, *keys)
    return statistics.median(values) if values else None


def _first_text(rows: Iterable[dict[str, str]], *keys: str) -> str | None:
    for row in rows:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
    return None


def _ratio(value: float | None) -> float | None:
    if value is None:
        return None
    return value / 100.0 if value > 1.0 else value


def _per_core_times(
    rows_by_kind: dict[str, list[dict[str, str]]], artifacts: list[tuple[Path, str]]
) -> list[float]:
    times: list[float] = []
    for row in rows_by_kind.get("pipeutilization", []):
        core_id = _first_text(
            [row], "Core ID", "Core Id", "core_id", "coreid", "AI Core ID"
        )
        if core_id is None:
            continue
        values = _values([row], "aiv_time(us)", "aic_time(us)")
        if values:
            times.append(max(values))
    if len(times) >= 2:
        return times
    for path, kind in artifacts:
        if kind != "per_core_cycles":
            continue
        cycles = _values(_read_rows(path), "task_cycles", "cycles")
        if len(cycles) >= 2:
            return cycles
    return []


def _state(
    identifier: str,
    value: float | None,
    threshold: float | None,
    *,
    direction: str,
    candidate_problems: list[str],
    evidence_fields: list[str],
    threshold_source: str,
) -> dict[str, Any]:
    if value is None or threshold is None:
        status: bool | str = "unknown"
    elif direction == "above":
        status = value > threshold
    elif direction == "below":
        status = value < threshold
    else:
        raise ValueError(f"unsupported direction: {direction}")
    return {
        "id": identifier,
        "state": status,
        "value": value,
        "threshold": threshold,
        "direction": direction,
        "threshold_source": threshold_source,
        "candidate_problem_ids": candidate_problems,
        "evidence_fields": evidence_fields,
    }


def _predicate(symptoms: list[dict[str, Any]], symptom_id: str) -> bool | str:
    for item in symptoms:
        if item["id"] == symptom_id:
            return item["state"]
    return "unknown"


def compress(args: argparse.Namespace) -> dict[str, Any]:
    root = args.input.resolve()
    if not root.is_dir():
        raise ValueError(f"input report directory does not exist: {root}")
    if args.available_cores is not None and args.available_cores < 1:
        raise ValueError("available cores must be positive")
    if args.theoretical_gm_bytes is not None and args.theoretical_gm_bytes <= 0:
        raise ValueError("theoretical GM bytes must be positive")
    if args.minimum_profile_repeats < 1:
        raise ValueError("minimum profile repeats must be positive")
    if args.cv_threshold < 0:
        raise ValueError("CV threshold must be non-negative")
    artifacts = [
        (path, kind)
        for path in sorted(root.rglob("*.csv"))
        if path.is_file() and (kind := _csv_kind(path)) is not None
    ]
    candidate_rows, warnings = _candidate_rows(artifacts, args.op_name)
    if not candidate_rows:
        raise ValueError(f"no supported msprof CSV rows found under {root}")
    observed_ops = {
        name
        for _, _, row in candidate_rows
        if (name := _first_text([row], "Op Name", "OP Name"))
    }
    if not args.op_name and len(observed_ops) > 1:
        raise ValueError(
            "multiple op names are present; pass --op-name explicitly: "
            + ", ".join(sorted(observed_ops))
        )

    rows_by_kind: dict[str, list[dict[str, str]]] = {}
    all_rows: list[dict[str, str]] = []
    for _, kind, row in candidate_rows:
        rows_by_kind.setdefault(kind, []).append(row)
        all_rows.append(row)

    # Standard msprof archives use op_summary_PipeUtilization.csv, which is
    # normalized to the same kind as msprof-op PipeUtilization.csv.
    pipe_rows = (
        rows_by_kind.get("pipeutilization", [])
        + rows_by_kind.get("op_summary", [])
    )
    memory_rows = rows_by_kind.get("memory", [])
    conflict_rows = rows_by_kind.get("resourceconflictratio", [])

    ratios = {
        "aiv_vec": _ratio(_median(pipe_rows, "aiv_vec_ratio")),
        "aiv_scalar": _ratio(_median(pipe_rows, "aiv_scalar_ratio")),
        "aiv_mte2": _ratio(_median(pipe_rows, "aiv_mte2_ratio")),
        "aiv_mte3": _ratio(_median(pipe_rows, "aiv_mte3_ratio")),
        "aic_cube": _ratio(
            _median(pipe_rows, "aic_cube_ratio", "aic_mac_ratio")
        ),
        "aic_scalar": _ratio(_median(pipe_rows, "aic_scalar_ratio")),
        "aic_mte2": _ratio(_median(pipe_rows, "aic_mte2_ratio")),
        "aic_mte3": _ratio(_median(pipe_rows, "aic_mte3_ratio")),
        "aic_fixpipe": _ratio(_median(pipe_rows, "aic_fixpipe_ratio")),
    }
    scalar_ratio = max(
        value for value in (ratios["aiv_scalar"], ratios["aic_scalar"]) if value is not None
    ) if any(value is not None for value in (ratios["aiv_scalar"], ratios["aic_scalar"])) else None
    mte2_ratio = max(
        value for value in (ratios["aiv_mte2"], ratios["aic_mte2"]) if value is not None
    ) if any(value is not None for value in (ratios["aiv_mte2"], ratios["aic_mte2"])) else None

    per_core = _per_core_times(rows_by_kind, artifacts)
    imbalance = (
        (max(per_core) - min(per_core)) / max(per_core)
        if len(per_core) >= 2 and max(per_core) > 0
        else None
    )
    block_dim_value = _median(all_rows, "Block Dim", "Block Num", "block_dim")
    block_dim = int(block_dim_value) if block_dim_value is not None else None
    core_coverage = (
        block_dim / args.available_cores
        if block_dim is not None and args.available_cores
        else None
    )
    gm_to_ub_kb = _median(memory_rows, "GM_to_UB_datas(KB)")
    mte2_instructions = _median(
        memory_rows, "aiv_mte2_instructions", "aic_mte2_instructions"
    )
    useful_bytes_per_mte = (
        gm_to_ub_kb * 1024.0 / mte2_instructions
        if gm_to_ub_kb is not None and mte2_instructions and mte2_instructions > 0
        else None
    )
    bandwidth_usage = _ratio(
        _median(
            memory_rows,
            "GM_to_UB_bw_usage_rate(%)",
            "aiv_gm_to_ub_bw_usage_rate(%)",
        )
    )
    conflict_ratio = _ratio(
        _median(
            conflict_rows,
            "aiv_vec_total_cflt_ratio",
            "aiv_vec_bank_cflt_ratio",
            "aiv_vec_resc_cflt_ratio",
        )
    )
    read_kb = _median(memory_rows, "read_main_memory_datas(KB)")
    write_kb = _median(memory_rows, "write_main_memory_datas(KB)")
    observed_gm_bytes = (
        (read_kb + write_kb) * 1024.0
        if read_kb is not None and write_kb is not None
        else None
    )
    traffic_amplification = (
        observed_gm_bytes / args.theoretical_gm_bytes
        if observed_gm_bytes is not None and args.theoretical_gm_bytes
        else None
    )

    cannbot_thresholds = (
        "ops-profiling/references/optimization_quickref.md and "
        "csv_fields_reference.md; expert heuristic, not hardware calibration"
    )
    symptoms = [
        _state(
            "symptom.profile.core_coverage_low",
            core_coverage,
            1.0 if args.available_cores else None,
            direction="below",
            candidate_problems=[
                "mechanism.underused_task_parallelism",
                "mechanism.workload_limited",
            ],
            evidence_fields=["block_dim", "available_cores"],
            threshold_source="direct comparison; tiny workload remains a refuting context",
        ),
        _state(
            "symptom.profile.per_core_time_imbalanced",
            imbalance,
            args.imbalance_threshold,
            direction="above",
            candidate_problems=[
                "mechanism.core_tail_imbalance",
                "mechanism.underused_task_parallelism",
            ],
            evidence_fields=["per_core_time"],
            threshold_source=cannbot_thresholds,
        ),
        _state(
            "symptom.profile.scalar_share_high",
            scalar_ratio,
            args.scalar_ratio_threshold,
            direction="above",
            candidate_problems=[
                "mechanism.scalar_control_hot_loop",
                "mechanism.vector_api_fragmentation",
                "mechanism.workload_limited",
            ],
            evidence_fields=["aiv_scalar_ratio", "aic_scalar_ratio"],
            threshold_source=cannbot_thresholds,
        ),
        _state(
            "symptom.profile.ub_conflict_high",
            conflict_ratio,
            args.conflict_ratio_threshold,
            direction="above",
            candidate_problems=[
                "mechanism.ub_bank_conflict",
                "mechanism.pipeline_serialization",
            ],
            evidence_fields=["aiv_vec_total_cflt_ratio"],
            threshold_source=cannbot_thresholds,
        ),
        _state(
            "symptom.profile.gm_traffic_amplified",
            traffic_amplification,
            args.traffic_amplification_threshold if args.theoretical_gm_bytes else None,
            direction="above",
            candidate_problems=[
                "mechanism.redundant_gm_round_trip",
                "mechanism.onchip_capacity_pressure",
                "mechanism.tiny_transfer_setup_amplification",
            ],
            evidence_fields=["observed_gm_bytes", "theoretical_gm_bytes"],
            threshold_source="task-specific algorithmic traffic model",
        ),
    ]
    mte_inputs_complete = all(
        value is not None for value in (mte2_ratio, bandwidth_usage, useful_bytes_per_mte)
    )
    mte_state: bool | str = "unknown"
    if mte_inputs_complete:
        mte_state = bool(
            mte2_ratio > args.mte2_ratio_threshold
            and bandwidth_usage < args.bandwidth_usage_threshold
            and useful_bytes_per_mte < args.min_useful_transfer_bytes
        )
    symptoms.append(
        {
            "id": "symptom.profile.mte_setup_dominated",
            "state": mte_state,
            "value": {
                "mte2_ratio": mte2_ratio,
                "bandwidth_usage": bandwidth_usage,
                "useful_bytes_per_mte_instruction": useful_bytes_per_mte,
            },
            "threshold": {
                "mte2_ratio": args.mte2_ratio_threshold,
                "maximum_bandwidth_usage": args.bandwidth_usage_threshold,
                "minimum_useful_transfer_bytes": args.min_useful_transfer_bytes,
            },
            "direction": "compound",
            "threshold_source": cannbot_thresholds,
            "candidate_problem_ids": [
                "mechanism.tiny_transfer_setup_amplification",
                "mechanism.pipeline_serialization",
                "mechanism.redundant_gm_round_trip",
            ],
            "evidence_fields": [
                "mte2_ratio",
                "GM_to_UB_bw_usage_rate(%)",
                "GM_to_UB_datas(KB)",
                "mte2_instructions",
            ],
        }
    )

    pipe_candidates = {
        "aiv_vec": ["mechanism.vector_api_fragmentation", "mechanism.workload_limited"],
        "aiv_scalar": ["mechanism.scalar_control_hot_loop", "mechanism.workload_limited"],
        "aic_scalar": ["mechanism.scalar_control_hot_loop", "mechanism.workload_limited"],
        "aiv_mte2": ["mechanism.tiny_transfer_setup_amplification", "mechanism.pipeline_serialization"],
        "aic_mte2": ["mechanism.tiny_transfer_setup_amplification", "mechanism.pipeline_serialization"],
        "aiv_mte3": ["mechanism.redundant_gm_round_trip", "mechanism.pipeline_serialization"],
        "aic_mte3": ["mechanism.redundant_gm_round_trip", "mechanism.pipeline_serialization"],
        "aic_cube": ["mechanism.unknown_unresolved"],
        "aic_fixpipe": ["mechanism.unknown_unresolved"],
    }
    present_ratios = {key: value for key, value in ratios.items() if value is not None}
    dominant_pipe = max(present_ratios, key=present_ratios.get) if present_ratios else None

    predicate_states = {
        "predicate.profile.gm_traffic_amplified": _predicate(
            symptoms, "symptom.profile.gm_traffic_amplified"
        ),
        "predicate.profile.mte_setup_dominated": _predicate(
            symptoms, "symptom.profile.mte_setup_dominated"
        ),
        "predicate.profile.overlap_low": "unknown",
        "predicate.profile.per_core_time_imbalanced": _predicate(
            symptoms, "symptom.profile.per_core_time_imbalanced"
        ),
        "predicate.profile.scalar_hot": _predicate(
            symptoms, "symptom.profile.scalar_share_high"
        ),
        "predicate.profile.tasks_below_available_cores": _predicate(
            symptoms, "symptom.profile.core_coverage_low"
        ),
        "predicate.profile.ub_conflict_high": _predicate(
            symptoms, "symptom.profile.ub_conflict_high"
        ),
        "predicate.profile.vector_granularity_low": "unknown",
    }
    artifact_records = [
        {
            "path": path.relative_to(root).as_posix(),
            "kind": kind,
            "sha256": _sha256(path),
        }
        for path, kind in artifacts
    ]
    duration_samples = _values(all_rows, "Task Duration(us)", "Task Duration")
    duration = statistics.median(duration_samples) if duration_samples else None
    duration_mean = statistics.mean(duration_samples) if duration_samples else None
    duration_std = (
        statistics.stdev(duration_samples) if len(duration_samples) > 1 else 0.0
    ) if duration_samples else None
    duration_cv = (
        duration_std / abs(duration_mean)
        if duration_mean not in (None, 0.0) and duration_std is not None
        else None
    )
    duration_statistics = (
        {
            "count": len(duration_samples),
            "mean_us": duration_mean,
            "median_us": duration,
            "min_us": min(duration_samples),
            "max_us": max(duration_samples),
            "std_us": duration_std,
            "cv": duration_cv,
            "selected": "median_us",
        }
        if duration_samples else None
    )
    if len(duration_samples) < args.minimum_profile_repeats:
        profile_metric_status = "repeat_limited"
    elif duration_cv is None or duration_cv > args.cv_threshold:
        profile_metric_status = "unstable"
    else:
        profile_metric_status = "stable_full_profile_metric"
    unresolved_reasons = {
        "predicate.profile.gm_traffic_amplified": [
            name for name, value in (
                ("observed_gm_bytes", observed_gm_bytes),
                ("theoretical_gm_bytes", args.theoretical_gm_bytes),
            ) if value is None
        ],
        "predicate.profile.mte_setup_dominated": [
            name for name, value in (
                ("mte2_ratio", mte2_ratio),
                ("gm_to_ub_bandwidth_usage", bandwidth_usage),
                ("useful_bytes_per_mte_instruction", useful_bytes_per_mte),
            ) if value is None
        ],
        "predicate.profile.overlap_low": ["timeline_or_trace_overlap_not_parsed"],
        "predicate.profile.per_core_time_imbalanced": (
            [] if imbalance is not None else ["per_core_time_with_core_id_not_found"]
        ),
        "predicate.profile.ub_conflict_high": (
            [] if conflict_ratio is not None else ["resource_conflict_ratio_not_found"]
        ),
        "predicate.profile.vector_granularity_low": [
            "vector_instruction_granularity_not_parsed"
        ],
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "kind": "aprof_profile_symptom_draft",
        "source_root": str(root),
        "operator": args.op_name or _first_text(all_rows, "Op Name", "OP Name") or "unknown",
        "extractor": {
            "id": "aprof.compress_msprof",
            "version": "1.0.0",
            "threshold_profile": "cannbot-ops-profiling-expert-heuristics-v1",
        },
        "artifacts": artifact_records,
        "features": {
            "task_duration_us": duration,
            "task_duration_samples_us": duration_samples,
            "task_duration_statistics": duration_statistics,
            "task_duration_measurement_status": profile_metric_status,
            "production_gain_eligible": False,
            "block_dim": block_dim,
            "available_cores": args.available_cores,
            "core_coverage": core_coverage,
            "per_core_time": per_core,
            "per_core_imbalance": imbalance,
            "pipe_ratios": ratios,
            "dominant_pipe": dominant_pipe,
            "observed_gm_bytes": observed_gm_bytes,
            "theoretical_gm_bytes": args.theoretical_gm_bytes,
            "traffic_amplification": traffic_amplification,
            "useful_bytes_per_mte_instruction": useful_bytes_per_mte,
            "gm_to_ub_bandwidth_usage": bandwidth_usage,
            "ub_conflict_ratio": conflict_ratio,
        },
        "symptoms": symptoms,
        "dominant_pipe_candidate_problem_ids": pipe_candidates.get(dominant_pipe, []),
        "predicate_states": predicate_states,
        "unresolved_extractors": [
            identifier
            for identifier, state in predicate_states.items()
            if state == "unknown"
        ],
        "unresolved_reasons": {
            identifier: unresolved_reasons.get(identifier, ["required_evidence_missing"])
            for identifier, state in predicate_states.items()
            if state == "unknown"
        },
        "warnings": sorted(set(warnings)),
        "authority": {
            "measured_features": "machine-derived",
            "symptom_thresholds": "expert-heuristic-draft",
            "candidate_problem_ids": "non-authoritative ambiguity set",
            "routing": "must be replayed by aprofctl against an immutable graph",
        },
    }
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="msprof report or archived CSV root")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--op-name")
    parser.add_argument("--available-cores", type=int)
    parser.add_argument("--theoretical-gm-bytes", type=float)
    parser.add_argument("--scalar-ratio-threshold", type=float, default=0.30)
    parser.add_argument("--mte2-ratio-threshold", type=float, default=0.50)
    parser.add_argument("--bandwidth-usage-threshold", type=float, default=0.60)
    parser.add_argument("--min-useful-transfer-bytes", type=float, default=16384.0)
    parser.add_argument("--conflict-ratio-threshold", type=float, default=0.05)
    parser.add_argument("--imbalance-threshold", type=float, default=0.10)
    parser.add_argument("--traffic-amplification-threshold", type=float, default=1.20)
    parser.add_argument("--minimum-profile-repeats", type=int, default=5)
    parser.add_argument("--cv-threshold", type=float, default=0.05)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = compress(args)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"wrote {args.output}: {len(result['artifacts'])} artifacts, "
        f"{len(result['symptoms'])} symptoms, "
        f"{len(result['unresolved_extractors'])} unresolved predicates"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
