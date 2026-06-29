from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aprof.core.errors import MetricContractError
from aprof.core.models import ArchitectureModel, ComponentLimit


def load_architecture(path: str | Path) -> ArchitectureModel:
    """Load a JSON-compatible YAML architecture config."""

    config_path = Path(path)
    data = json.loads(config_path.read_text(encoding="utf-8"))
    components: dict[str, ComponentLimit] = {}

    for name, raw in data.get("components", {}).items():
        components[name] = ComponentLimit(
            name=name,
            kind=str(raw["kind"]),
            limit_per_us=float(raw["limit_per_us"]),
            unit=str(raw["unit"]),
            source=str(raw.get("source", "unknown")),
            confidence=str(raw.get("confidence", "low")),
            notes=str(raw.get("notes", "")),
            metric_mapping=[str(item) for item in raw.get("metric_mapping", [])],
            required_evidence=[str(item) for item in raw.get("required_evidence", [])],
            next_experiment=str(raw.get("next_experiment", "")),
        )

    if "soc_version" not in data:
        raise MetricContractError(f"missing soc_version in architecture config: {config_path}")

    return ArchitectureModel(
        soc_version=str(data["soc_version"]),
        components=components,
        shared_constraints=[str(item) for item in data.get("shared_constraints", [])],
    )


def architecture_to_dict(model: ArchitectureModel) -> dict[str, Any]:
    return {
        "soc_version": model.soc_version,
        "components": {
            name: {
                "kind": component.kind,
                "limit_per_us": component.limit_per_us,
                "unit": component.unit,
                "source": component.source,
                "confidence": component.confidence,
                "notes": component.notes,
                "metric_mapping": component.metric_mapping,
                "required_evidence": component.required_evidence,
                "next_experiment": component.next_experiment,
            }
            for name, component in model.components.items()
        },
        "shared_constraints": model.shared_constraints,
    }


@dataclass(frozen=True)
class MetricDescriptor:
    """Hardware metric description for a single component."""

    component: str
    kind: str
    unit: str
    metric_mapping: list[str]
    required_evidence: list[str]
    source: str
    confidence: str
    notes: str = ""


@dataclass(frozen=True)
class EvidenceRequirement:
    """Evidence needed before a diagnosis can be trusted."""

    component: str
    required_evidence: list[str]
    next_experiment: str = ""


@dataclass(frozen=True)
class MetricInterface:
    """Communication contract between profiling and diagnosis agents."""

    soc_version: str
    metrics: dict[str, MetricDescriptor]
    shared_constraints: list[str]

    def missing_evidence(self, available: set[str]) -> list[str]:
        missing: list[str] = []
        for descriptor in self.metrics.values():
            for item in descriptor.required_evidence:
                if item not in available:
                    missing.append(item)
        return sorted(set(missing))


def architecture_to_metric_interface(model: ArchitectureModel) -> MetricInterface:
    metrics = {
        name: MetricDescriptor(
            component=name,
            kind=component.kind,
            unit=component.unit,
            metric_mapping=list(component.metric_mapping),
            required_evidence=list(component.required_evidence),
            source=component.source,
            confidence=component.confidence,
            notes=component.notes,
        )
        for name, component in model.components.items()
    }
    return MetricInterface(
        soc_version=model.soc_version,
        metrics=metrics,
        shared_constraints=list(model.shared_constraints),
    )
