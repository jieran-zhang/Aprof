"""Skill-RL core models (SAGE-lite, defect-driven)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Scope = Literal["production_safe", "benchmark_specialized", "rejected", "unknown"]
BaselineKind = Literal["naive", "strong"]
EditOp = Literal["ADD", "UPDATE", "DELETE", "NOOP", "DEPRECATE"]
DiagnosisType = Literal[
    "true_bottleneck",
    "workload_limited",
    "measurement_limited",
    "code_quality_risk",
    "optimization_not_recommended",
    "unknown",
]


@dataclass
class Measurement:
    warm_up: int = 0
    repeat: int = 0
    statistic: str = "median"
    samples_us: list[float] = field(default_factory=list)
    median_us: float | None = None
    cv: float | None = None

    def is_stable(
        self,
        min_warmup: int = 1,
        min_repeat: int = 3,
        max_cv: float | None = None,
    ) -> bool:
        if self.warm_up < min_warmup or self.repeat < min_repeat:
            return False
        if self.median_us is None and not self.samples_us:
            return False
        if max_cv is not None and self.cv is not None and self.cv > max_cv:
            return False
        return True


@dataclass
class WorkloadModel:
    total_elements: int | None = None
    dtype_bytes: int | None = None
    workload_class: str = "unknown"
    block_dim: int | None = None
    operator_family: str = "unknown"


@dataclass
class Candidate:
    id: str
    strategy_id: str = ""
    strategy: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    code_changes: list[str] = field(default_factory=list)
    median_us: float | None = None
    samples_us: list[float] = field(default_factory=list)
    cv: float | None = None
    speedup_vs_round_baseline: float | None = None
    accepted: bool = False
    reason: str = ""
    scope: Scope = "production_safe"
    semantic_status: str = "preserved"
    correctness_bad: int = 0
    correctness_checked: int = 0


@dataclass
class Round:
    round_index: int
    label: str
    baseline_median_us: float | None = None
    baseline_config: dict[str, Any] = field(default_factory=dict)
    selected: Candidate | None = None
    rejected: list[Candidate] = field(default_factory=list)
    measurement: Measurement = field(default_factory=Measurement)


@dataclass
class Episode:
    case_id: str
    op_name: str
    scenario_id: str
    baseline_kind: BaselineKind
    source: str
    original_median_us: float | None = None
    final_median_us: float | None = None
    combined_speedup: float | None = None
    workload: WorkloadModel = field(default_factory=WorkloadModel)
    diagnosis_type: DiagnosisType = "unknown"
    measurement: Measurement = field(default_factory=Measurement)
    rounds: list[Round] = field(default_factory=list)
    actionable_strategy_ids: list[str] = field(default_factory=list)
    retrieved_skill_ids: list[str] = field(default_factory=list)
    used_skill_ids: list[str] = field(default_factory=list)
    generated_skill_ids: list[str] = field(default_factory=list)
    apply_result: dict[str, Any] = field(default_factory=dict)
    compile_result: dict[str, Any] = field(default_factory=dict)
    verification_result: dict[str, Any] = field(default_factory=dict)
    profile_result: dict[str, Any] = field(default_factory=dict)
    cost: dict[str, float] = field(default_factory=dict)
    min_effect_pct: float = 3.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Skill:
    id: str
    family: str
    version: int = 1
    scope: Scope = "production_safe"
    preconditions: list[str] = field(default_factory=list)
    actionable_edits: list[dict[str, Any]] = field(default_factory=list)
    expected_metric_delta: dict[str, Any] = field(default_factory=dict)
    measurement_policy: dict[str, Any] = field(default_factory=dict)
    linked_hypotheses: list[str] = field(default_factory=list)
    contraindications: list[str] = field(default_factory=list)
    hardware_scope: list[str] = field(default_factory=list)
    workload_scope: list[str] = field(default_factory=list)
    operator_scope: list[str] = field(default_factory=list)
    evidence_episode_ids: list[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    last_used_at: str = ""
    confidence: float = 0.0
    tombstone: bool = False
    notes: str = ""

    def is_actionable(self) -> bool:
        return not self.tombstone and bool(self.actionable_edits) and bool(self.expected_metric_delta)


@dataclass
class SkillEdit:
    op: EditOp
    skill_id: str
    target_skill_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_episode_ids: list[str] = field(default_factory=list)
    scope: Scope = "production_safe"
    rationale: str = ""
    conflict_basis: str = ""
    merge_basis: str = ""
    policy_name: str = "rule"
    policy_logprob: float | None = None
    candidate_group_id: str = ""
    candidate_id: str = ""


@dataclass
class RewardBreakdown:
    correctness_ok: bool = False
    semantics_ok: bool = False
    scope_primary_ok: bool = False
    measurement_ok: bool = False
    speedup_score: float = 0.0
    actionability: float = 0.0
    workload_awareness: float = 0.0
    efficiency: float = 0.0
    specialized_appendix_speedup: float = 0.0
    primary: float = 0.0
    outcome_reward: float = 0.0
    reuse_reward: float = 0.0
    edit_reward: float = 0.0
    cost_penalty: float = 0.0
    health_penalty: float = 0.0
    training_reward: float = 0.0
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SkillLibrarySnapshot:
    version_label: str
    skills: dict[str, Skill] = field(default_factory=dict)
    content_hash: str = ""
    parent_hash: str = ""
    training_run_id: str = ""
    audit_log: list[dict[str, Any]] = field(default_factory=list)
