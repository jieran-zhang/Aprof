from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Protocol

from aprof.core.models import AnalysisResult


@dataclass(frozen=True)
class PotentialProblem:
    title: str
    severity: str
    confidence: str
    evidence: List[str]
    recommendation: str
    related_components: List[str] = field(default_factory=list)
    related_windows: List[int] = field(default_factory=list)


@dataclass(frozen=True)
class ProblemReport:
    summary: str
    problems: List[PotentialProblem]
    model: str
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ModelClient(Protocol):
    def assess(self, result: AnalysisResult, harness_context: Dict[str, Any]) -> ProblemReport:
        ...


class LocalHeuristicModelClient:
    """Local stand-in for future model APIs.

    The interface is intentionally narrow: future LLM or service clients can
    consume the same analysis result and harness context, then return the same
    `ProblemReport` contract.
    """

    name = "local_heuristic_v0"

    def assess(self, result: AnalysisResult, harness_context: Dict[str, Any]) -> ProblemReport:
        problems: List[PotentialProblem] = []
        diagnosis = result.diagnosis

        problems.append(
            PotentialProblem(
                title=_title_for_bottleneck(diagnosis.bottleneck_class),
                severity=_severity_for_recommendation(diagnosis.recommendation),
                confidence=diagnosis.confidence,
                evidence=[
                    *diagnosis.rationale,
                    f"recommendation: {diagnosis.recommendation}",
                ],
                recommendation=diagnosis.recommendation,
                related_components=diagnosis.responsible_components,
                related_windows=diagnosis.responsible_windows,
            )
        )

        if diagnosis.missing_evidence:
            problems.append(
                PotentialProblem(
                    title="Profiling evidence is incomplete",
                    severity="medium",
                    confidence="high",
                    evidence=diagnosis.missing_evidence,
                    recommendation="rerun msprof simulator with timeline and code hotspot outputs enabled",
                )
            )

        for component in result.components[:3]:
            if component.utilization is None:
                continue
            if component.utilization < 0.5 and component.time_fraction >= 0.25:
                problems.append(
                    PotentialProblem(
                        title=f"{component.component} dominates time but is underutilized",
                        severity="medium",
                        confidence=component.confidence,
                        evidence=[
                            f"{component.component} consumes {component.time_fraction:.1%} of active time",
                            f"utilization is {component.utilization:.1%} against {component.source}",
                        ],
                        recommendation="collect component-local evidence before generating more code variants",
                        related_components=[component.component],
                    )
                )

        if result.hotspots:
            top = result.hotspots[0]
            problems.append(
                PotentialProblem(
                    title="Top source hotspot should be inspected first",
                    severity="low",
                    confidence="medium",
                    evidence=[
                        f"{top.code} accounts for {top.running_time_us:.2f} us and {top.cycles:.0f} cycles"
                    ],
                    recommendation="map the hotspot line back to the Ascend source path recorded by the harness",
                    related_components=[top.component] if top.component else [],
                )
            )

        source_root = harness_context.get("source_root")
        if source_root:
            source_note = f" Source root: {source_root}."
        else:
            source_note = " No source root was recorded."

        return ProblemReport(
            summary=(
                f"{result.metadata.operator_name}: {diagnosis.bottleneck_class} "
                f"with {diagnosis.confidence} confidence.{source_note}"
            ),
            problems=problems,
            model=self.name,
            context={
                "operator_name": result.metadata.operator_name,
                "kernel_version": result.metadata.kernel_version,
                "shape": result.metadata.shape,
                "data_type": result.metadata.data_type,
                "source_root": source_root,
                "executable": harness_context.get("executable"),
            },
        )


def write_problem_report(report: ProblemReport, out_dir: str | Path) -> None:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "problems.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (output / "problems.md").write_text(render_problem_markdown(report), encoding="utf-8")


def render_problem_markdown(report: ProblemReport) -> str:
    lines = [
        "# AProf Potential Problems",
        "",
        f"- Model: `{report.model}`",
        f"- Summary: {report.summary}",
        "",
        "## Problems",
        "",
    ]
    for index, problem in enumerate(report.problems, start=1):
        lines.extend(
            [
                f"### {index}. {problem.title}",
                "",
                f"- Severity: `{problem.severity}`",
                f"- Confidence: `{problem.confidence}`",
                f"- Components: `{', '.join(problem.related_components) or 'none'}`",
                f"- Windows: `{', '.join(str(item) for item in problem.related_windows) or 'none'}`",
                f"- Recommendation: {problem.recommendation}",
                "",
                "Evidence:",
            ]
        )
        lines.extend(f"- {item}" for item in problem.evidence)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _title_for_bottleneck(bottleneck_class: str) -> str:
    titles = {
        "scalar_control_overhead": "Scalar control overhead is limiting the kernel",
        "memory_data_movement": "Data movement is the dominant limit",
        "mixed_phase_bottleneck": "Multiple phase-local bottlenecks are present",
        "vector_compute": "Vector compute is the dominant limit",
        "idle_or_synchronization": "Idle or synchronization gaps dominate elapsed time",
        "underutilized": "Dominant component is below its attainable limit",
        "insufficient_evidence": "AProf could not build a complete diagnosis",
    }
    return titles.get(bottleneck_class, f"Potential {bottleneck_class} issue")


def _severity_for_recommendation(recommendation: str) -> str:
    if recommendation.startswith("stop"):
        return "low"
    if recommendation.startswith("request"):
        return "high"
    return "medium"
