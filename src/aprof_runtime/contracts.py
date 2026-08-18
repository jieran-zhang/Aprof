from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Mapping

from .errors import ContractError
from .jsonio import (
    JSONValue,
    content_hash,
    require_bool,
    require_json_value,
    require_number,
    require_object,
    require_sha256,
    require_string,
    strict_fields,
)

SCHEMA_VERSION = "1.0.0"
EMPTY_ARTIFACT_SHA256 = "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def _version(obj: Mapping[str, Any], path: str) -> str:
    version = require_string(obj["schema_version"], f"{path}.schema_version")
    if version != SCHEMA_VERSION:
        raise ContractError(f"{path}.schema_version: unsupported version {version!r}")
    return version


def _strings(value: Any, path: str, *, nonempty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ContractError(f"{path}: expected {'non-empty ' if nonempty else ''}array of strings")
    return tuple(require_string(item, f"{path}[{index}]") for index, item in enumerate(value))


def _numbers(value: Any, path: str, *, nonempty: bool = False, minimum: float | None = None) -> tuple[float, ...]:
    if not isinstance(value, list) or (nonempty and not value):
        raise ContractError(f"{path}: expected {'non-empty ' if nonempty else ''}array of numbers")
    return tuple(require_number(item, f"{path}[{index}]", minimum=minimum) for index, item in enumerate(value))


def _hash_map(value: Any, path: str) -> dict[str, str]:
    obj = require_object(value, path)
    return {require_string(key, f"{path}.<key>"): require_sha256(item, f"{path}.{key}") for key, item in obj.items()}


def _identity_hash(value: Any, path: str) -> str:
    if value == "unknown":
        return "unknown"
    return require_sha256(value, path)


def _rfc3339_timestamp(value: Any, path: str) -> str:
    text = require_string(value, path)
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ContractError(f"{path}: expected RFC 3339 timestamp") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{path}: expected timezone-aware RFC 3339 timestamp")
    return text


def _prefixed_id(value: Any, path: str, prefix: str) -> str:
    identifier = require_string(value, path)
    if not identifier.startswith(prefix) or len(identifier) == len(prefix):
        raise ContractError(f"{path}: expected ID with prefix {prefix!r}")
    return identifier


@dataclass(frozen=True, slots=True)
class ProducerHashes:
    model: str
    prompt: str
    agent: str

    @classmethod
    def from_dict(cls, value: Any, path: str) -> "ProducerHashes":
        obj = strict_fields(value, {"model", "prompt", "agent"}, set(), path)
        return cls(*(_identity_hash(obj[key], f"{path}.{key}") for key in ("model", "prompt", "agent")))


@dataclass(frozen=True, slots=True)
class SourceHashes:
    baseline: str
    candidate: str

    @classmethod
    def from_dict(cls, value: Any, path: str) -> "SourceHashes":
        obj = strict_fields(value, {"baseline", "candidate"}, set(), path)
        return cls(require_sha256(obj["baseline"], f"{path}.baseline"), require_sha256(obj["candidate"], f"{path}.candidate"))


@dataclass(frozen=True, slots=True)
class Context:
    schema_version: str
    task_id: str
    operator: str
    hardware_fingerprint: str
    workload: dict[str, JSONValue]
    budget: dict[str, JSONValue]
    evidence: dict[str, JSONValue] = field(default_factory=dict)

    KIND: ClassVar[str] = "context"

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "Context":
        obj = strict_fields(
            value,
            {"schema_version", "task_id", "operator", "hardware_fingerprint", "workload", "budget"},
            {"evidence"}, path,
        )
        return cls(
            _version(obj, path),
            require_string(obj["task_id"], f"{path}.task_id"),
            require_string(obj["operator"], f"{path}.operator"),
            require_string(obj["hardware_fingerprint"], f"{path}.hardware_fingerprint"),
            dict(require_object(require_json_value(obj["workload"], f"{path}.workload"), f"{path}.workload")),
            dict(require_object(require_json_value(obj["budget"], f"{path}.budget"), f"{path}.budget")),
            dict(require_object(require_json_value(obj.get("evidence", {}), f"{path}.evidence"), f"{path}.evidence")),
        )


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    edge_id: str
    source_id: str
    target_id: str
    logit: float
    probability: float
    allowed: bool
    mask_reasons: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any, path: str) -> "RouteCandidate":
        obj = strict_fields(
            value,
            {"edge_id", "source_id", "target_id", "logit", "probability", "allowed", "mask_reasons"},
            set(), path,
        )
        probability = require_number(obj["probability"], f"{path}.probability", minimum=0.0)
        if probability > 1.0:
            raise ContractError(f"{path}.probability: expected value <= 1")
        candidate = cls(
            require_string(obj["edge_id"], f"{path}.edge_id"),
            require_string(obj["source_id"], f"{path}.source_id"),
            require_string(obj["target_id"], f"{path}.target_id"),
            require_number(obj["logit"], f"{path}.logit"),
            probability,
            require_bool(obj["allowed"], f"{path}.allowed"),
            _strings(obj["mask_reasons"], f"{path}.mask_reasons"),
        )
        if candidate.allowed and candidate.mask_reasons:
            raise ContractError(f"{path}: allowed candidate cannot have mask reasons")
        if not candidate.allowed and (candidate.probability != 0.0 or not candidate.mask_reasons):
            raise ContractError(f"{path}: masked candidate requires zero probability and at least one reason")
        return candidate


@dataclass(frozen=True, slots=True)
class RouteDecision:
    graph_version: str
    policy_version: str
    selected_edge_id: str
    behavior_probability: float
    selection_mode: str
    selection_seed: int | None
    selected_mechanism_id: str
    mechanism_derivation: str
    mechanism_scores: dict[str, float]
    candidates: tuple[RouteCandidate, ...]

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "RouteDecision":
        obj = strict_fields(
            value,
            {"graph_version", "policy_version", "selected_edge_id", "behavior_probability", "selection_mode", "selection_seed", "selected_mechanism_id", "mechanism_derivation", "mechanism_scores", "candidates"},
            set(), path,
        )
        raw_candidates = obj["candidates"]
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ContractError(f"{path}.candidates: expected non-empty array")
        candidates = tuple(RouteCandidate.from_dict(item, f"{path}.candidates[{i}]") for i, item in enumerate(raw_candidates))
        edge_ids = [candidate.edge_id for candidate in candidates]
        if len(edge_ids) != len(set(edge_ids)):
            raise ContractError(f"{path}.candidates: duplicate edge_id")
        selected = require_string(obj["selected_edge_id"], f"{path}.selected_edge_id")
        if selected not in edge_ids:
            raise ContractError(f"{path}.selected_edge_id: not present in candidates")
        selected_candidate = next(candidate for candidate in candidates if candidate.edge_id == selected)
        if not selected_candidate.allowed:
            raise ContractError(f"{path}.selected_edge_id: selected candidate is hard-masked")
        selected_mechanism = require_string(obj["selected_mechanism_id"], f"{path}.selected_mechanism_id")
        if selected_mechanism != selected_candidate.source_id:
            raise ContractError(f"{path}.selected_mechanism_id: does not match selected edge source")
        raw_scores = require_object(obj["mechanism_scores"], f"{path}.mechanism_scores")
        scores = {
            require_string(key, f"{path}.mechanism_scores.<key>"): require_number(value, f"{path}.mechanism_scores.{key}")
            for key, value in raw_scores.items()
        }
        if selected_mechanism not in scores:
            raise ContractError(f"{path}.mechanism_scores: selected mechanism is missing")
        behavior = require_number(obj["behavior_probability"], f"{path}.behavior_probability", minimum=0.0)
        mode = require_string(obj["selection_mode"], f"{path}.selection_mode")
        seed = obj["selection_seed"]
        if mode == "argmax":
            if behavior != 1.0:
                raise ContractError(f"{path}.behavior_probability: argmax behavior probability must be 1")
            if seed is not None:
                raise ContractError(f"{path}.selection_seed: argmax requires null seed")
        elif mode == "sample":
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise ContractError(f"{path}.selection_seed: sample mode requires integer seed")
            if abs(behavior - selected_candidate.probability) > 1e-12:
                raise ContractError(f"{path}.behavior_probability: sampled behavior probability does not match selected candidate")
        else:
            raise ContractError(f"{path}.selection_mode: expected argmax or sample")
        derivation = require_string(obj["mechanism_derivation"], f"{path}.mechanism_derivation")
        if derivation != "fixed_supports_refutes_tri_state_v1":
            raise ContractError(f"{path}.mechanism_derivation: unsupported derivation")
        total = sum(candidate.probability for candidate in candidates)
        if abs(total - 1.0) > 1e-8:
            raise ContractError(f"{path}.candidates: probabilities sum to {total}, expected 1")
        return cls(
            require_string(obj["graph_version"], f"{path}.graph_version"),
            require_string(obj["policy_version"], f"{path}.policy_version"),
            selected,
            behavior,
            mode,
            seed,
            selected_mechanism,
            derivation,
            scores,
            candidates,
        )


@dataclass(frozen=True, slots=True)
class CandidateDraft:
    schema_version: str
    candidate_id: str
    session_id: str
    route: RouteDecision
    transformation_id: str
    transformation_version: str
    producer_hashes: ProducerHashes
    source_hashes: SourceHashes
    patch_artifact_hash: str
    parameters: dict[str, JSONValue]
    proposed_by: str
    created_at: str
    parent_candidate_id: str | None = None

    KIND: ClassVar[str] = "candidate_draft"

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "CandidateDraft":
        # Strict fields are a security boundary: an agent cannot smuggle in a verdict
        # or selected_as_best flag.
        obj = strict_fields(
            value,
            {"schema_version", "candidate_id", "session_id", "route", "transformation_id", "transformation_version", "producer_hashes", "source_hashes", "patch_artifact_hash", "parameters", "proposed_by", "created_at"},
            {"parent_candidate_id"}, path,
        )
        parent = obj.get("parent_candidate_id")
        route = RouteDecision.from_dict(obj["route"], f"{path}.route")
        transformation_id = require_string(obj["transformation_id"], f"{path}.transformation_id")
        selected_target = next(item.target_id for item in route.candidates if item.edge_id == route.selected_edge_id)
        if transformation_id != selected_target:
            raise ContractError(f"{path}.transformation_id: does not match selected route target {selected_target!r}")
        return cls(
            _version(obj, path),
            require_string(obj["candidate_id"], f"{path}.candidate_id"),
            require_string(obj["session_id"], f"{path}.session_id"),
            route,
            transformation_id,
            require_string(obj["transformation_version"], f"{path}.transformation_version"),
            ProducerHashes.from_dict(obj["producer_hashes"], f"{path}.producer_hashes"),
            SourceHashes.from_dict(obj["source_hashes"], f"{path}.source_hashes"),
            require_sha256(obj["patch_artifact_hash"], f"{path}.patch_artifact_hash"),
            dict(require_object(require_json_value(obj["parameters"], f"{path}.parameters"), f"{path}.parameters")),
            require_string(obj["proposed_by"], f"{path}.proposed_by"),
            require_string(obj["created_at"], f"{path}.created_at"),
            None if parent is None else require_string(parent, f"{path}.parent_candidate_id"),
        )


@dataclass(frozen=True, slots=True)
class HandlerAttempt:
    """Strict exploration sidecar for handler and parameter learning.

    This is deliberately separate from the immutable v1 episode contract. It
    records the decision surface that v0001 currently collapses into free-form
    transformation parameters.
    """

    schema_version: str
    attempt_id: str
    candidate_id: str
    session_id: str
    graph_version: str
    selected_edge_id: str
    mechanism_id: str
    transformation_id: str
    handler_id: str
    handler_version: str
    handler_producer_hash: str
    parameters: dict[str, JSONValue]
    context_features: dict[str, JSONValue]
    parent_candidate_id: str | None
    previous_verdict: str | None
    decision_type: str
    decision_reason: str
    created_at: str

    KIND: ClassVar[str] = "handler_attempt"
    DECISION_TYPES: ClassVar[set[str]] = {
        "initial",
        "retry_same_handler",
        "sibling_handler",
        "sibling_transformation",
        "reroute_after_evidence",
        "debug_repair",
    }
    PREVIOUS_VERDICTS: ClassVar[set[str]] = {
        "static_rejected",
        "build_failed",
        "accuracy_failed",
        "runtime_failed",
        "artifacts_incomplete",
        "measurement_unstable",
        "attribution_uncertain",
        "stable_no_gain",
        "benchmark_specialized_gain",
        "heldout_regression",
        "production_safe_gain",
        "verified_noop",
    }

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "HandlerAttempt":
        required = {
            "schema_version", "attempt_id", "candidate_id", "session_id",
            "graph_version", "selected_edge_id", "mechanism_id",
            "transformation_id", "handler_id", "handler_version",
            "handler_producer_hash", "parameters", "context_features",
            "parent_candidate_id", "previous_verdict", "decision_type",
            "decision_reason", "created_at",
        }
        obj = strict_fields(value, required, set(), path)
        decision_type = require_string(obj["decision_type"], f"{path}.decision_type")
        if decision_type not in cls.DECISION_TYPES:
            raise ContractError(
                f"{path}.decision_type: expected one of {', '.join(sorted(cls.DECISION_TYPES))}"
            )
        parent_value = obj["parent_candidate_id"]
        previous_value = obj["previous_verdict"]
        parent = None if parent_value is None else require_string(
            parent_value, f"{path}.parent_candidate_id"
        )
        previous = None if previous_value is None else require_string(
            previous_value, f"{path}.previous_verdict"
        )
        if previous is not None and previous not in cls.PREVIOUS_VERDICTS:
            raise ContractError(f"{path}.previous_verdict: unknown typed gate verdict")
        if decision_type == "initial":
            if parent is not None or previous is not None:
                raise ContractError(
                    f"{path}: initial handler attempt requires null parent and previous verdict"
                )
        elif parent is None or previous is None:
            raise ContractError(
                f"{path}: non-initial handler attempt requires parent and previous verdict"
            )
        return cls(
            _version(obj, path),
            require_string(obj["attempt_id"], f"{path}.attempt_id"),
            require_string(obj["candidate_id"], f"{path}.candidate_id"),
            require_string(obj["session_id"], f"{path}.session_id"),
            require_string(obj["graph_version"], f"{path}.graph_version"),
            _prefixed_id(obj["selected_edge_id"], f"{path}.selected_edge_id", "edge."),
            _prefixed_id(obj["mechanism_id"], f"{path}.mechanism_id", "mechanism."),
            _prefixed_id(obj["transformation_id"], f"{path}.transformation_id", "transformation."),
            _prefixed_id(obj["handler_id"], f"{path}.handler_id", "handler."),
            require_string(obj["handler_version"], f"{path}.handler_version"),
            require_sha256(obj["handler_producer_hash"], f"{path}.handler_producer_hash"),
            dict(require_object(require_json_value(obj["parameters"], f"{path}.parameters"), f"{path}.parameters")),
            dict(require_object(require_json_value(obj["context_features"], f"{path}.context_features"), f"{path}.context_features")),
            parent,
            previous,
            decision_type,
            require_string(obj["decision_reason"], f"{path}.decision_reason"),
            _rfc3339_timestamp(obj["created_at"], f"{path}.created_at"),
        )


@dataclass(frozen=True, slots=True)
class GateEvidence:
    candidate_id: str
    static_review: "GateStageStatus"
    build: "GateStageStatus"
    accuracy: "GateStageStatus"
    runtime: "GateStageStatus"
    semantic: "GateStageStatus"
    scope: "GateStageStatus"
    portability: "GateStageStatus"
    baseline_samples_ns: tuple[float, ...]
    candidate_samples_ns: tuple[float, ...]
    mechanism_alignment: bool | None
    heldout_regressions: tuple[float, ...]
    artifacts: dict[str, str]

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "GateEvidence":
        obj = strict_fields(
            value,
            {"candidate_id", "static_review", "build", "accuracy", "runtime", "semantic", "scope", "portability", "artifacts"},
            {"baseline_samples_ns", "candidate_samples_ns", "mechanism_alignment", "heldout_regressions"}, path,
        )
        alignment = obj.get("mechanism_alignment")
        if alignment is not None:
            alignment = require_bool(alignment, f"{path}.mechanism_alignment")
        return cls(
            require_string(obj["candidate_id"], f"{path}.candidate_id"),
            GateStageStatus.parse(obj["static_review"], f"{path}.static_review"),
            GateStageStatus.parse(obj["build"], f"{path}.build"),
            GateStageStatus.parse(obj["accuracy"], f"{path}.accuracy"),
            GateStageStatus.parse(obj["runtime"], f"{path}.runtime"),
            GateStageStatus.parse(obj["semantic"], f"{path}.semantic"),
            GateStageStatus.parse(obj["scope"], f"{path}.scope"),
            GateStageStatus.parse(obj["portability"], f"{path}.portability"),
            _numbers(obj.get("baseline_samples_ns", []), f"{path}.baseline_samples_ns", minimum=0.000001),
            _numbers(obj.get("candidate_samples_ns", []), f"{path}.candidate_samples_ns", minimum=0.000001),
            alignment,
            _numbers(obj.get("heldout_regressions", []), f"{path}.heldout_regressions"),
            _hash_map(obj["artifacts"], f"{path}.artifacts"),
        )


@dataclass(frozen=True, slots=True)
class GateConfig:
    """Per-request gate settings constrained by the runtime safety profile.

    A caller may make these settings stricter, but cannot relax the runtime-owned
    production floors below.  Keeping that validation in the contract parser
    makes every gate entry point share the same trust boundary.
    """

    MAX_CV: ClassVar[float] = 0.05
    MAX_HELDOUT_REGRESSION: ClassVar[float] = 0.03
    MIN_PAIRS: ClassVar[int] = 30
    MIN_SPEEDUP_LCB: ClassVar[float] = 1.03
    REQUIRED_ARTIFACTS: ClassVar[tuple[str, ...]] = (
        "build_log",
        "accuracy_report",
        "measurement_report",
    )

    max_cv: float = MAX_CV
    max_heldout_regression: float = MAX_HELDOUT_REGRESSION
    require_mechanism_alignment: bool = True
    required_artifacts: tuple[str, ...] = ("build_log", "accuracy_report", "measurement_report")
    min_pairs: int = MIN_PAIRS
    lcb_confidence: float = 0.95
    min_speedup_lcb: float = MIN_SPEEDUP_LCB
    bootstrap_resamples: int = 2000

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "GateConfig":
        obj = strict_fields(
            value, set(),
            {"max_cv", "max_heldout_regression", "require_mechanism_alignment", "required_artifacts", "min_pairs", "lcb_confidence", "min_speedup_lcb", "bootstrap_resamples"}, path,
        )
        min_pairs = obj.get("min_pairs", cls.MIN_PAIRS)
        resamples = obj.get("bootstrap_resamples", 2000)
        if isinstance(min_pairs, bool) or not isinstance(min_pairs, int) or min_pairs < cls.MIN_PAIRS:
            raise ContractError(f"{path}.min_pairs: runtime safety profile requires value >= {cls.MIN_PAIRS}")
        if isinstance(resamples, bool) or not isinstance(resamples, int) or resamples < 100:
            raise ContractError(f"{path}.bootstrap_resamples: expected integer >= 100")
        confidence = require_number(obj.get("lcb_confidence", 0.95), f"{path}.lcb_confidence", minimum=0.0)
        if not 0.5 < confidence < 1.0:
            raise ContractError(f"{path}.lcb_confidence: expected value between 0.5 and 1")
        max_cv = require_number(obj.get("max_cv", cls.MAX_CV), f"{path}.max_cv", minimum=0.0)
        if max_cv > cls.MAX_CV:
            raise ContractError(f"{path}.max_cv: runtime safety profile requires value <= {cls.MAX_CV}")
        max_regression = require_number(
            obj.get("max_heldout_regression", cls.MAX_HELDOUT_REGRESSION),
            f"{path}.max_heldout_regression",
            minimum=0.0,
        )
        if max_regression > cls.MAX_HELDOUT_REGRESSION:
            raise ContractError(
                f"{path}.max_heldout_regression: runtime safety profile requires value <= {cls.MAX_HELDOUT_REGRESSION}"
            )
        require_alignment = require_bool(
            obj.get("require_mechanism_alignment", True), f"{path}.require_mechanism_alignment"
        )
        if not require_alignment:
            raise ContractError(f"{path}.require_mechanism_alignment: runtime safety profile requires true")
        required_artifacts = _strings(
            obj.get("required_artifacts", list(cls.REQUIRED_ARTIFACTS)), f"{path}.required_artifacts"
        )
        if len(required_artifacts) != len(set(required_artifacts)):
            raise ContractError(f"{path}.required_artifacts: duplicate artifact name")
        missing_artifacts = sorted(set(cls.REQUIRED_ARTIFACTS) - set(required_artifacts))
        if missing_artifacts:
            raise ContractError(
                f"{path}.required_artifacts: runtime safety profile requires {', '.join(missing_artifacts)}"
            )
        min_speedup_lcb = require_number(
            obj.get("min_speedup_lcb", cls.MIN_SPEEDUP_LCB), f"{path}.min_speedup_lcb", minimum=0.0
        )
        if min_speedup_lcb < cls.MIN_SPEEDUP_LCB:
            raise ContractError(
                f"{path}.min_speedup_lcb: runtime safety profile requires value >= {cls.MIN_SPEEDUP_LCB}"
            )
        return cls(
            max_cv,
            max_regression,
            require_alignment,
            required_artifacts,
            min_pairs,
            confidence,
            min_speedup_lcb,
            resamples,
        )


@dataclass(frozen=True, slots=True)
class GateRequest:
    schema_version: str
    candidates: tuple[CandidateDraft, ...]
    evidence: tuple[GateEvidence, ...]
    config: GateConfig

    KIND: ClassVar[str] = "gate_request"

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "GateRequest":
        obj = strict_fields(value, {"schema_version", "candidates", "evidence"}, {"config"}, path)
        raw_candidates, raw_evidence = obj["candidates"], obj["evidence"]
        if not isinstance(raw_candidates, list) or not raw_candidates:
            raise ContractError(f"{path}.candidates: expected non-empty array")
        if not isinstance(raw_evidence, list) or not raw_evidence:
            raise ContractError(f"{path}.evidence: expected non-empty array")
        candidates = tuple(CandidateDraft.from_dict(item, f"{path}.candidates[{i}]") for i, item in enumerate(raw_candidates))
        evidence = tuple(GateEvidence.from_dict(item, f"{path}.evidence[{i}]") for i, item in enumerate(raw_evidence))
        candidate_ids = [item.candidate_id for item in candidates]
        evidence_ids = [item.candidate_id for item in evidence]
        if len(set(candidate_ids)) != len(candidate_ids) or len(set(evidence_ids)) != len(evidence_ids):
            raise ContractError(f"{path}: candidate ids must be unique")
        if set(candidate_ids) != set(evidence_ids):
            raise ContractError(f"{path}: candidates and evidence must have identical candidate ids")
        session_ids = {item.session_id for item in candidates}
        if len(session_ids) != 1:
            raise ContractError(f"{path}.candidates: all candidates must belong to one session")
        return cls(_version(obj, path), candidates, evidence, GateConfig.from_dict(obj.get("config", {}), f"{path}.config"))


class GateVerdict(str, Enum):
    VERIFIED_NOOP = "verified_noop"
    STATIC_REJECTED = "static_rejected"
    BUILD_FAILED = "build_failed"
    ACCURACY_FAILED = "accuracy_failed"
    RUNTIME_FAILED = "runtime_failed"
    ARTIFACTS_INCOMPLETE = "artifacts_incomplete"
    MEASUREMENT_UNSTABLE = "measurement_unstable"
    ATTRIBUTION_UNCERTAIN = "attribution_uncertain"
    STABLE_NO_GAIN = "stable_no_gain"
    BENCHMARK_SPECIALIZED_GAIN = "benchmark_specialized_gain"
    HELDOUT_REGRESSION = "heldout_regression"
    PRODUCTION_SAFE_GAIN = "production_safe_gain"


class GateStageStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_RUN = "not_run"

    @classmethod
    def parse(cls, value: Any, path: str) -> "GateStageStatus":
        try:
            return cls(require_string(value, path))
        except ValueError as exc:
            raise ContractError(f"{path}: expected passed, failed, or not_run") from exc


@dataclass(frozen=True, slots=True)
class GateOutcome:
    schema_version: str
    candidate_id: str
    verdict: GateVerdict
    state_path: tuple[str, ...]
    baseline_median_ns: float
    candidate_median_ns: float
    speedup: float
    speedup_lcb: float
    pair_count: int
    measurement_protocol: str
    measurement_cv: float
    utility: float
    eligible: bool
    policy_update_eligible: bool
    selected_as_best: bool
    reasons: tuple[str, ...]
    decision_hash: str

    KIND: ClassVar[str] = "gate_outcome"

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "GateOutcome":
        obj = strict_fields(
            value,
            {"schema_version", "candidate_id", "verdict", "state_path", "baseline_median_ns", "candidate_median_ns", "speedup", "speedup_lcb", "pair_count", "measurement_protocol", "measurement_cv", "utility", "eligible", "policy_update_eligible", "selected_as_best", "reasons", "decision_hash"},
            set(), path,
        )
        try:
            verdict = GateVerdict(require_string(obj["verdict"], f"{path}.verdict"))
        except ValueError as exc:
            raise ContractError(f"{path}.verdict: unknown verdict") from exc
        pair_count = obj["pair_count"]
        if isinstance(pair_count, bool) or not isinstance(pair_count, int) or pair_count < 0:
            raise ContractError(f"{path}.pair_count: expected non-negative integer")
        protocol = require_string(obj["measurement_protocol"], f"{path}.measurement_protocol")
        if protocol not in {
            "paired_log_speedup_deterministic_bootstrap_lcb_v1",
            "no_mutation_source_identity_v1",
        }:
            raise ContractError(f"{path}.measurement_protocol: unsupported protocol")
        return cls(
            _version(obj, path),
            require_string(obj["candidate_id"], f"{path}.candidate_id"), verdict,
            _strings(obj["state_path"], f"{path}.state_path", nonempty=True),
            require_number(obj["baseline_median_ns"], f"{path}.baseline_median_ns", minimum=0.0),
            require_number(obj["candidate_median_ns"], f"{path}.candidate_median_ns", minimum=0.0),
            require_number(obj["speedup"], f"{path}.speedup", minimum=0.0),
            require_number(obj["speedup_lcb"], f"{path}.speedup_lcb", minimum=0.0),
            pair_count,
            protocol,
            require_number(obj["measurement_cv"], f"{path}.measurement_cv", minimum=0.0),
            require_number(obj["utility"], f"{path}.utility"),
            require_bool(obj["eligible"], f"{path}.eligible"),
            require_bool(obj["policy_update_eligible"], f"{path}.policy_update_eligible"),
            require_bool(obj["selected_as_best"], f"{path}.selected_as_best"),
            _strings(obj["reasons"], f"{path}.reasons"),
            require_sha256(obj["decision_hash"], f"{path}.decision_hash"),
        )


@dataclass(frozen=True, slots=True)
class CandidateEpisode:
    schema_version: str
    episode_id: str
    context: Context
    graph_snapshot: dict[str, JSONValue]
    graph_hash: str
    behavior_policy_checkpoint: dict[str, JSONValue] | None
    policy_checkpoint_hash: str | None
    gate_request: GateRequest
    draft: CandidateDraft
    evidence: GateEvidence
    outcome: GateOutcome
    finalized_at: str
    runtime_build: str
    episode_hash: str

    KIND: ClassVar[str] = "candidate_episode"

    @classmethod
    def from_dict(cls, value: Any, path: str = "$") -> "CandidateEpisode":
        obj = strict_fields(
            value,
            {"schema_version", "episode_id", "context", "graph_snapshot", "graph_hash", "behavior_policy_checkpoint", "policy_checkpoint_hash", "gate_request", "draft", "evidence", "outcome", "finalized_at", "runtime_build", "episode_hash"},
            set(), path,
        )
        raw_policy = obj["behavior_policy_checkpoint"]
        policy = None
        if raw_policy is not None:
            policy = dict(require_object(
                require_json_value(raw_policy, f"{path}.behavior_policy_checkpoint"),
                f"{path}.behavior_policy_checkpoint",
            ))
        raw_policy_hash = obj["policy_checkpoint_hash"]
        episode = cls(
            _version(obj, path),
            require_string(obj["episode_id"], f"{path}.episode_id"),
            Context.from_dict(obj["context"], f"{path}.context"),
            dict(require_object(
                require_json_value(obj["graph_snapshot"], f"{path}.graph_snapshot"),
                f"{path}.graph_snapshot",
            )),
            require_sha256(obj["graph_hash"], f"{path}.graph_hash"),
            policy,
            None if raw_policy_hash is None else require_sha256(
                raw_policy_hash, f"{path}.policy_checkpoint_hash"
            ),
            GateRequest.from_dict(obj["gate_request"], f"{path}.gate_request"),
            CandidateDraft.from_dict(obj["draft"], f"{path}.draft"),
            GateEvidence.from_dict(obj["evidence"], f"{path}.evidence"),
            GateOutcome.from_dict(obj["outcome"], f"{path}.outcome"),
            require_string(obj["finalized_at"], f"{path}.finalized_at"),
            require_string(obj["runtime_build"], f"{path}.runtime_build"),
            require_sha256(obj["episode_hash"], f"{path}.episode_hash"),
        )
        if len({episode.draft.candidate_id, episode.evidence.candidate_id, episode.outcome.candidate_id}) != 1:
            raise ContractError(f"{path}: draft/evidence/outcome candidate id mismatch")
        request_drafts = {item.candidate_id: item for item in episode.gate_request.candidates}
        request_evidence = {item.candidate_id: item for item in episode.gate_request.evidence}
        if episode.draft.candidate_id not in request_drafts:
            raise ContractError(f"{path}.gate_request: episode candidate is absent from gate batch")
        if request_drafts[episode.draft.candidate_id] != episode.draft:
            raise ContractError(f"{path}.draft: does not match authoritative gate request")
        if request_evidence[episode.draft.candidate_id] != episode.evidence:
            raise ContractError(f"{path}.evidence: does not match authoritative gate request")
        expected_hash = content_hash({
            "schema_version": episode.schema_version,
            "episode_id": episode.episode_id,
            "context": episode.context,
            "graph_snapshot": episode.graph_snapshot,
            "graph_hash": episode.graph_hash,
            "behavior_policy_checkpoint": episode.behavior_policy_checkpoint,
            "policy_checkpoint_hash": episode.policy_checkpoint_hash,
            "gate_request": episode.gate_request,
            "draft": episode.draft,
            "evidence": episode.evidence,
            "outcome": episode.outcome,
            "finalized_at": episode.finalized_at,
            "runtime_build": episode.runtime_build,
        })
        if episode.episode_hash != expected_hash:
            raise ContractError(f"{path}.episode_hash: payload hash mismatch")
        # Local import avoids a module cycle while ensuring serialized episodes
        # are attestations of a runtime computation, not merely self-hashed data.
        from .gates import CandidateGate

        authoritative = {
            item.candidate_id: item for item in CandidateGate().evaluate(episode.gate_request)
        }
        if episode.outcome != authoritative[episode.draft.candidate_id]:
            raise ContractError(f"{path}.outcome: does not match authoritative gate evaluation")
        from .attestation import attest_route

        attest_route(
            context=episode.context,
            recorded=episode.draft.route,
            graph_snapshot=episode.graph_snapshot,
            graph_hash=episode.graph_hash,
            behavior_policy_checkpoint=episode.behavior_policy_checkpoint,
            policy_checkpoint_hash=episode.policy_checkpoint_hash,
        )
        return episode


CONTRACTS = {
    Context.KIND: Context,
    CandidateDraft.KIND: CandidateDraft,
    HandlerAttempt.KIND: HandlerAttempt,
    GateRequest.KIND: GateRequest,
    GateOutcome.KIND: GateOutcome,
    CandidateEpisode.KIND: CandidateEpisode,
}


def validate_contract(kind: str, value: Any) -> Any:
    try:
        contract = CONTRACTS[kind]
    except KeyError as exc:
        raise ContractError(f"unknown contract kind {kind!r}; choose from {', '.join(sorted(CONTRACTS))}") from exc
    return contract.from_dict(value)
