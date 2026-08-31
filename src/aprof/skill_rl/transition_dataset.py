"""Build a unified transition dataset from Skill-RL JSON reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable


def _case_transition(case: dict[str, Any], source: str) -> dict[str, Any]:
    op = str(case.get("op") or case.get("op_name") or "unknown")
    problem = str(case.get("problem_id") or "unknown")
    case_id = str(case.get("case_id") or f"{source}:{op}:{problem}")
    before = case.get("before_median_us", case.get("inject_median_us"))
    after = case.get("after_median_us", case.get("baseline_median_us"))
    baseline = case.get("baseline_median_us")
    return {
        "case_id": case_id,
        "source": source,
        "op": op,
        "problem_family": problem,
        "shape_family": str(case.get("shape_family") or "unknown"),
        "state": {
            "before_median_us": before,
            "baseline_median_us": baseline,
            "pipe_utilization": case.get("pipe_utilization") or {},
        },
        "action": {
            "skill_id": case.get("skill_id"),
            "tile_before": case.get("tile_before"),
            "tile_after": case.get("tile_after"),
        },
        "outcome": {
            "after_median_us": after,
            "speedup": case.get("speedup_vs_inject", case.get("speedup_restore")),
            "correctness_ok": (case.get("skill_rl_score") or {}).get("correctness_ok", True),
        },
    }


def load_report_transitions(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("cases") or payload.get("performance_table") or []
    return [_case_transition(dict(row), path.name) for row in rows]


def build_transition_dataset(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in paths:
        if path.is_file():
            rows.extend(load_report_transitions(path))
    rows.sort(key=lambda row: (row["source"], row["case_id"]))
    return rows


def write_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
