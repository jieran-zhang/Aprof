from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from aprof.profiling.case_io import latest_profile
from aprof.agents.diagnosis.evidence import collect_evidence
from aprof.core.models import DiagnosisResult
from aprof.reports.diagnosis import write_diagnosis
from aprof.agents.diagnosis.rules import diagnose_label


class DiagnosisAgent:
    """Thin orchestrator: case/profile -> evidence -> rule diagnosis -> reports."""

    def diagnose(self, case_dir: str | Path, profile_dir: str | Path | None = None) -> DiagnosisResult:
        case = Path(case_dir).resolve()
        profile = Path(profile_dir).resolve() if profile_dir else latest_profile(case)
        evidence = collect_evidence(case, profile)
        label, confidence, recommendation = diagnose_label(evidence)
        result = DiagnosisResult(
            case_dir=str(case),
            profile_dir=str(profile),
            predicted_label=label,
            confidence=confidence,
            evidence=asdict(evidence),
            recommendation=recommendation,
        )
        write_diagnosis(case, result)
        return result


# Backward-compatible names for any ad-hoc imports made during experiments.
DiagnosisEvidence = dict[str, Any]
