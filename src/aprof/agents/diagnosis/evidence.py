from __future__ import annotations

import csv
import statistics
from pathlib import Path
from typing import Any

from aprof.profiling.case_io import find_case_root, load_case_metadata
from aprof.core.models import CaseEvidence


def collect_evidence(case: Path, profile: Path) -> CaseEvidence:
    return CaseEvidence(
        metadata=load_case_metadata(case, profile),
        source=source_features(case),
        artifacts=artifact_features(profile),
    )


def source_features(case: Path) -> dict[str, Any]:
    text = ""
    for path in (case / "op_kernel").glob("*"):
        if path.is_file() and path.suffix in {".asc", ".h"}:
            text += path.read_text(encoding="utf-8", errors="ignore") + "\n"
    return {
        "inject_tail": "#define APROF_INJECT_TAIL 1" in text,
        "inject_dynshape": "#define APROF_INJECT_DYNSHAPE 1" in text,
        "data_copy_count": text.count("DataCopy("),
        "pipe_barrier_count": text.count("PipeBarrier"),
    }


def artifact_features(profile: Path) -> dict[str, Any]:
    traces = list(profile.rglob("trace.json")) if profile.exists() else []
    instr = list(profile.rglob("*_instr_exe_*.csv")) if profile.exists() else []
    code = list(profile.rglob("*_code_exe_*.csv")) if profile.exists() else []
    runtimes: list[float] = []
    pipes: dict[str, float] = {}
    for csv_path in instr:
        _accumulate_instr_csv(csv_path, runtimes, pipes)
    log_text = _read_msprof_log(profile)
    return {
        "has_trace": bool(traces),
        "trace_count": len(traces),
        "instr_csv_count": len(instr),
        "code_csv_count": len(code),
        "has_msprof_log": bool(log_text),
        "block_start_count": log_text.count("[block_start]"),
        "block_end_count": log_text.count("[block_end]"),
        "msprof_error_count": log_text.count("[ERROR]"),
        "all_task_success": "All task success" in log_text,
        "missing_object_dump": "Can not get object kernel dump path" in log_text,
        "instr_runtime_total_us": sum(runtimes),
        "instr_runtime_max_us": max(runtimes) if runtimes else 0.0,
        "instr_runtime_mean_us": statistics.mean(runtimes) if runtimes else 0.0,
        "pipe_runtime_us": pipes,
    }


def _accumulate_instr_csv(csv_path: Path, runtimes: list[float], pipes: dict[str, float]) -> None:
    try:
        with csv_path.open(newline="", encoding="utf-8", errors="ignore") as handle:
            for row in csv.DictReader(handle):
                value = row.get("running_time(us)") or row.get("running_time_us") or "0"
                pipe = row.get("pipe") or row.get("PIPE") or "unknown"
                try:
                    runtime = float(value)
                except ValueError:
                    runtime = 0.0
                runtimes.append(runtime)
                pipes[pipe] = pipes.get(pipe, 0.0) + runtime
    except OSError:
        return


def _read_msprof_log(profile: Path) -> str:
    case_root = find_case_root(profile)
    if case_root is not None and (case_root / "msprof_stdout.log").exists():
        return (case_root / "msprof_stdout.log").read_text(encoding="utf-8", errors="ignore")
    candidates = [profile / "msprof_stdout.log"]
    candidates.extend(parent / "msprof_stdout.log" for parent in profile.parents)
    for path in candidates:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="ignore")
    return ""
