from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ExperimentMetadata:
    operator_name: str
    kernel_version: str
    shape: str
    data_type: str
    soc_version: str
    total_duration_us: float
    total_ops: float = 0.0
    total_bytes: float = 0.0
    notes: str = ""


@dataclass(frozen=True)
class TimeWindow:
    index: int
    start_us: float
    end_us: float
    component: str
    name: str
    cycles: float = 0.0
    ops: float = 0.0
    bytes_moved: float = 0.0
    source: str = "trace"
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_us(self) -> float:
        return max(0.0, self.end_us - self.start_us)


@dataclass(frozen=True)
class CodeHotspot:
    code: str
    call_count: int
    cycles: float
    running_time_us: float
    component: str | None = None


@dataclass(frozen=True)
class Observation:
    metadata: ExperimentMetadata
    windows: list[TimeWindow]
    hotspots: list[CodeHotspot]
    input_path: str
    artifacts: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProfilingRequest:
    skill_name: str
    reason: str
    required_evidence: list[str]
    preconditions: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProfilingSkillResult:
    skill_name: str
    status: str
    outputs: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


@dataclass(frozen=True)
class ComponentLimit:
    name: str
    kind: str
    limit_per_us: float
    unit: str
    source: str
    confidence: str
    notes: str = ""
    metric_mapping: list[str] = field(default_factory=list)
    required_evidence: list[str] = field(default_factory=list)
    next_experiment: str = ""


@dataclass(frozen=True)
class ArchitectureModel:
    soc_version: str
    components: dict[str, ComponentLimit]
    shared_constraints: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WindowAttribution:
    index: int
    component: str
    name: str
    start_us: float
    end_us: float
    duration_us: float
    observed: float
    attainable: float
    utilization: float | None
    unit: str
    evidence: str
    local_bottleneck: bool = False


@dataclass(frozen=True)
class ComponentSummary:
    component: str
    kind: str
    active_time_us: float
    time_fraction: float
    observed: float
    attainable: float
    utilization: float | None
    unit: str
    source: str
    confidence: str


@dataclass(frozen=True)
class Diagnosis:
    bottleneck_class: str
    responsible_components: list[str]
    responsible_windows: list[int]
    confidence: str
    missing_evidence: list[str]
    recommendation: str
    rationale: list[str]
    agent_actions: list[str] = field(default_factory=list)
    next_profiling_requests: list[ProfilingRequest] = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisResult:
    metadata: ExperimentMetadata
    architecture: str
    input_path: str
    windows: list[WindowAttribution]
    components: list[ComponentSummary]
    idle_fraction: float
    hotspots: list[CodeHotspot]
    diagnosis: Diagnosis
    aggregate: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProfilingPlan:
    case_dir: str
    command: list[str]
    reason: str
    expected_artifacts: list[str]
    single_core: bool = True


@dataclass
class CaseEvidence:
    metadata: dict[str, Any]
    source: dict[str, Any]
    artifacts: dict[str, Any]


@dataclass
class DiagnosisResult:
    case_dir: str
    profile_dir: str
    predicted_label: str
    confidence: str
    evidence: dict[str, Any]
    recommendation: str


@dataclass
class AlignmentRow:
    case: str
    truth: str
    predicted: str
    match: bool
    confidence: str
    profile: str
