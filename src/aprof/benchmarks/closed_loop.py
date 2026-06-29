from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from aprof.agents.diagnosis.agent import DiagnosisAgent
from aprof.agents.profiling.strategy import ProfilingStrategyAgent
from aprof.core.models import AlignmentRow
from aprof.core.paths import benchmarks_dir
from aprof.reports.diagnosis import write_alignment


SWIGLU_CASES = ["inject_blockdim", "inject_tilelen_small", "inject_tail"]
FAST_GELU_CASES = ["inject_blockdim", "inject_tilelen_small", "inject_tail"]


def run_swiglu_alignment(root: Path | None = None) -> list[AlignmentRow]:
    base = (root or benchmarks_dir()) / "aprof_injected_ops" / "swi_glu"
    out_dir = (root or benchmarks_dir()) / "aprof_injected_ops" / "closed_loop" / "swi_glu"
    profiler = ProfilingStrategyAgent()
    diagnoser = DiagnosisAgent()
    rows: list[AlignmentRow] = []
    for case_name in SWIGLU_CASES:
        case = base / case_name
        plan = profiler.plan(case, "SwiGlu 1x3 closed-loop targeted single-core capture")
        (case / "profiling_plan.json").write_text(
            json.dumps(asdict(plan), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        result = diagnoser.diagnose(case)
        truth = result.evidence.get("metadata", {}).get("injected_label", "unknown")
        rows.append(
            AlignmentRow(
                case=case.name,
                truth=truth,
                predicted=result.predicted_label,
                match=truth == result.predicted_label,
                confidence=result.confidence,
                profile=result.profile_dir,
            )
        )
    write_alignment(out_dir, rows)
    return rows


def run_fast_gelu_alignment(root: Path | None = None) -> list[AlignmentRow]:
    base = (root or benchmarks_dir()) / "aprof_injected_ops" / "fast_gelu"
    out_dir = (root or benchmarks_dir()) / "aprof_injected_ops" / "closed_loop" / "fast_gelu"
    profiler = ProfilingStrategyAgent()
    diagnoser = DiagnosisAgent()
    rows: list[AlignmentRow] = []
    for case_name in FAST_GELU_CASES:
        case = base / case_name
        plan = profiler.plan(case, "FastGelu inject closed-loop targeted single-core capture")
        (case / "profiling_plan.json").write_text(
            json.dumps(asdict(plan), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        result = diagnoser.diagnose(case)
        truth = result.evidence.get("metadata", {}).get("injected_label", "unknown")
        rows.append(
            AlignmentRow(
                case=case.name,
                truth=truth,
                predicted=result.predicted_label,
                match=truth == result.predicted_label,
                confidence=result.confidence,
                profile=result.profile_dir,
            )
        )
    write_alignment(out_dir, rows)
    return rows
