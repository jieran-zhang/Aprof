from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping, Protocol

from .contracts import CandidateEpisode, GateVerdict
from .errors import ContractError
from .jsonio import (
    content_hash,
    load_json,
    require_number,
    require_object,
    require_sha256,
    require_string,
    strict_fields,
    to_primitive,
)


POLICY_SCHEMA_VERSION = "1.0.0"
ALGORITHM_ID = "fixed_graph_shrunk_edge_bias_v1"
OBJECTIVE_SEMANTICS = "observational_machine_gate_outcome_update_not_causal_attribution"
_MEASURED_VERDICTS = {
    GateVerdict.PRODUCTION_SAFE_GAIN,
    GateVerdict.STABLE_NO_GAIN,
    GateVerdict.HELDOUT_REGRESSION,
    GateVerdict.ATTRIBUTION_UNCERTAIN,
}
_CONFIGURABLE_NEGATIVE_VERDICTS = {
    GateVerdict.STATIC_REJECTED.value,
    GateVerdict.BUILD_FAILED.value,
    GateVerdict.ACCURACY_FAILED.value,
    GateVerdict.RUNTIME_FAILED.value,
    GateVerdict.STABLE_NO_GAIN.value,
    GateVerdict.HELDOUT_REGRESSION.value,
}


class EpisodeExport(Protocol):
    def iter_payloads(self) -> Iterator[str]: ...


@dataclass(frozen=True, slots=True)
class PolicyTrainingConfig:
    """Conservative knobs for a small-data, fixed-graph update.

    Negative verdicts are opt-in. Values must be non-positive and describe an
    update signal, not an estimate of the transformation's causal effect.
    """

    learning_rate: float = 1.0
    shrinkage: float = 4.0
    min_support: int = 2
    max_abs_signal: float = 1.0
    max_abs_bias: float = 0.5
    max_importance_weight: float = 4.0
    use_recorded_propensity: bool = True
    min_measurement_pairs: int = 30
    max_measurement_cv: float = 0.05
    allowed_runtime_prefixes: tuple[str, ...] = ("aprof-runtime/",)
    require_known_producer_hashes: bool = True
    negative_verdict_utilities: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        positive = {
            "learning_rate": self.learning_rate,
            "shrinkage": self.shrinkage,
            "max_abs_signal": self.max_abs_signal,
            "max_abs_bias": self.max_abs_bias,
            "max_importance_weight": self.max_importance_weight,
        }
        for name, value in positive.items():
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a finite positive number")
        if isinstance(self.min_support, bool) or not isinstance(self.min_support, int) or self.min_support < 1:
            raise ValueError("min_support must be a positive integer")
        if (
            isinstance(self.min_measurement_pairs, bool)
            or not isinstance(self.min_measurement_pairs, int)
            or self.min_measurement_pairs < 1
        ):
            raise ValueError("min_measurement_pairs must be a positive integer")
        if type(self.use_recorded_propensity) is not bool or type(self.require_known_producer_hashes) is not bool:
            raise ValueError("policy training boolean flags must be booleans")
        if not math.isfinite(self.max_measurement_cv) or self.max_measurement_cv < 0:
            raise ValueError("max_measurement_cv must be a finite non-negative number")
        if (
            not isinstance(self.allowed_runtime_prefixes, (tuple, list))
            or not self.allowed_runtime_prefixes
            or any(not isinstance(item, str) or not item for item in self.allowed_runtime_prefixes)
        ):
            raise ValueError("allowed_runtime_prefixes must contain non-empty prefixes")
        if not isinstance(self.negative_verdict_utilities, Mapping):
            raise ValueError("negative_verdict_utilities must be a mapping")
        for verdict, utility in self.negative_verdict_utilities.items():
            if verdict not in _CONFIGURABLE_NEGATIVE_VERDICTS:
                raise ValueError(f"{verdict} is not an eligible typed negative verdict")
            if not math.isfinite(utility) or utility > 0:
                raise ValueError(f"typed negative utility for {verdict} must be finite and <= 0")

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["allowed_runtime_prefixes"] = list(self.allowed_runtime_prefixes)
        value["negative_verdict_utilities"] = dict(sorted(self.negative_verdict_utilities.items()))
        return value

    @classmethod
    def from_dict(cls, value: Any, path: str = "config") -> "PolicyTrainingConfig":
        defaults = cls()
        allowed = set(defaults.to_dict())
        obj = strict_fields(value, set(), allowed, path)
        values = dict(obj)
        if "allowed_runtime_prefixes" in values:
            prefixes = values["allowed_runtime_prefixes"]
            if not isinstance(prefixes, list) or not all(isinstance(item, str) for item in prefixes):
                raise ContractError(f"{path}.allowed_runtime_prefixes: expected array of strings")
            values["allowed_runtime_prefixes"] = tuple(prefixes)
        if "negative_verdict_utilities" in values:
            negatives = require_object(values["negative_verdict_utilities"], f"{path}.negative_verdict_utilities")
            values["negative_verdict_utilities"] = {
                require_string(key, f"{path}.negative_verdict_utilities.<key>"): require_number(
                    item, f"{path}.negative_verdict_utilities.{key}"
                )
                for key, item in negatives.items()
            }
        try:
            return cls(**values)
        except (TypeError, ValueError) as exc:
            raise ContractError(f"{path}: {exc}") from exc


@dataclass(frozen=True, slots=True)
class EdgePolicyUpdate:
    edge_id: str
    source_id: str
    target_id: str
    prior_logit: float
    bias: float
    effective_logit: float
    reliability: float
    support_count: int
    weighted_support: float
    positive_count: int
    negative_count: int


@dataclass(frozen=True, slots=True)
class PolicyCheckpoint:
    schema_version: str
    policy_version: str
    graph_version: str
    base_graph_hash: str
    algorithm: str
    objective_semantics: str
    config: dict[str, Any]
    config_hash: str
    input_episode_hashes: tuple[str, ...]
    training_data_hashes: tuple[str, ...]
    edge_updates: tuple[EdgePolicyUpdate, ...]
    training_summary: dict[str, Any]
    checkpoint_hash: str

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)  # type: ignore[return-value]


def load_policy_checkpoint(value: str | Path | Mapping[str, Any]) -> PolicyCheckpoint:
    """Validate strict shape, hashes, and every locally derived invariant."""

    raw = load_json(value) if isinstance(value, (str, Path)) else dict(value)
    required = {
        "schema_version", "policy_version", "graph_version", "base_graph_hash",
        "algorithm", "objective_semantics", "config", "config_hash",
        "input_episode_hashes", "training_data_hashes", "edge_updates",
        "training_summary", "checkpoint_hash",
    }
    obj = strict_fields(raw, required, set(), "policy")
    if obj["schema_version"] != POLICY_SCHEMA_VERSION:
        raise ContractError("policy.schema_version: unsupported version")
    if obj["algorithm"] != ALGORITHM_ID:
        raise ContractError("policy.algorithm: unsupported algorithm")
    if obj["objective_semantics"] != OBJECTIVE_SEMANTICS:
        raise ContractError("policy.objective_semantics: unsupported semantics")
    raw_config = require_object(obj["config"], "policy.config")
    expected_config_fields = set(PolicyTrainingConfig().to_dict())
    if set(raw_config) != expected_config_fields:
        raise ContractError("policy.config: published checkpoints require the complete config")
    parsed_config = PolicyTrainingConfig.from_dict(raw_config, "policy.config")
    config = parsed_config.to_dict()
    config_hash = require_sha256(obj["config_hash"], "policy.config_hash")
    if content_hash(config) != config_hash:
        raise ContractError("policy.config_hash: payload hash mismatch")

    def hashes(name: str) -> tuple[str, ...]:
        items = obj[name]
        if not isinstance(items, list):
            raise ContractError(f"policy.{name}: expected array")
        result = tuple(require_sha256(item, f"policy.{name}[{index}]") for index, item in enumerate(items))
        if tuple(sorted(set(result))) != result:
            raise ContractError(f"policy.{name}: expected sorted unique hashes")
        return result

    raw_updates = obj["edge_updates"]
    if not isinstance(raw_updates, list):
        raise ContractError("policy.edge_updates: expected array")
    updates: list[EdgePolicyUpdate] = []
    for index, value_item in enumerate(raw_updates):
        path = f"policy.edge_updates[{index}]"
        item = strict_fields(value_item, {
            "edge_id", "source_id", "target_id", "prior_logit", "bias",
            "effective_logit", "reliability", "support_count", "weighted_support",
            "positive_count", "negative_count",
        }, set(), path)
        counts: dict[str, int] = {}
        for name in ("support_count", "positive_count", "negative_count"):
            count = item[name]
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise ContractError(f"{path}.{name}: expected non-negative integer")
            counts[name] = count
        support = require_number(item["weighted_support"], f"{path}.weighted_support", minimum=0.0)
        reliability = require_number(item["reliability"], f"{path}.reliability", minimum=0.0)
        if reliability > 1:
            raise ContractError(f"{path}.reliability: expected <= 1")
        prior = require_number(item["prior_logit"], f"{path}.prior_logit")
        bias = require_number(item["bias"], f"{path}.bias")
        effective = require_number(item["effective_logit"], f"{path}.effective_logit")
        if not math.isclose(effective, prior + bias, rel_tol=0.0, abs_tol=1e-12):
            raise ContractError(f"{path}.effective_logit: does not equal prior_logit + bias")
        if counts["positive_count"] + counts["negative_count"] > counts["support_count"]:
            raise ContractError(f"{path}: signed counts exceed support_count")
        if abs(bias) > parsed_config.max_abs_bias + 1e-12:
            raise ContractError(f"{path}.bias: exceeds configured max_abs_bias")
        if counts["support_count"] == 0 and support != 0.0:
            raise ContractError(f"{path}.weighted_support: non-zero without support")
        if counts["support_count"] > 0:
            lower = float(counts["support_count"])
            upper = parsed_config.max_importance_weight * counts["support_count"]
            if support < lower - 1e-12 or support > upper + 1e-12:
                raise ContractError(
                    f"{path}.weighted_support: outside the configured importance-weight bounds"
                )
        expected_reliability = (
            0.0
            if counts["support_count"] < parsed_config.min_support
            else support / (support + parsed_config.shrinkage)
        )
        if not math.isclose(reliability, expected_reliability, rel_tol=0.0, abs_tol=1e-12):
            raise ContractError(f"{path}.reliability: inconsistent with support and config")
        if counts["support_count"] < parsed_config.min_support and bias != 0.0:
            raise ContractError(f"{path}.bias: must be zero below min_support")
        updates.append(EdgePolicyUpdate(
            require_string(item["edge_id"], f"{path}.edge_id"),
            require_string(item["source_id"], f"{path}.source_id"),
            require_string(item["target_id"], f"{path}.target_id"),
            prior, bias, effective, reliability, counts["support_count"], support,
            counts["positive_count"], counts["negative_count"],
        ))
    edge_ids = [item.edge_id for item in updates]
    if edge_ids != sorted(set(edge_ids)):
        raise ContractError("policy.edge_updates: expected unique updates sorted by edge_id")
    summary = require_object(obj["training_summary"], "policy.training_summary")
    expected_summary_fields = {
        "input_record_count", "unique_valid_episode_count", "training_episode_count",
        "updated_edge_count", "skip_reasons",
    }
    if set(summary) != expected_summary_fields:
        raise ContractError("policy.training_summary: unexpected or missing fields")
    summary_counts: dict[str, int] = {}
    for name in expected_summary_fields - {"skip_reasons"}:
        count = summary[name]
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ContractError(f"policy.training_summary.{name}: expected non-negative integer")
        summary_counts[name] = count
    skip_reasons = require_object(summary["skip_reasons"], "policy.training_summary.skip_reasons")
    for reason, count in skip_reasons.items():
        require_string(reason, "policy.training_summary.skip_reasons.<key>")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ContractError(
                f"policy.training_summary.skip_reasons.{reason}: expected positive integer"
            )
    input_hashes = hashes("input_episode_hashes")
    training_hashes = hashes("training_data_hashes")
    if not set(training_hashes).issubset(input_hashes):
        raise ContractError("policy.training_data_hashes: must be a subset of input_episode_hashes")
    if summary_counts["unique_valid_episode_count"] != len(input_hashes):
        raise ContractError("policy.training_summary.unique_valid_episode_count: hash-count mismatch")
    if summary_counts["training_episode_count"] != len(training_hashes):
        raise ContractError("policy.training_summary.training_episode_count: hash-count mismatch")
    if summary_counts["updated_edge_count"] != sum(item.bias != 0.0 for item in updates):
        raise ContractError("policy.training_summary.updated_edge_count: edge-count mismatch")
    if summary_counts["input_record_count"] < summary_counts["unique_valid_episode_count"]:
        raise ContractError("policy.training_summary.input_record_count: smaller than unique inputs")
    checkpoint_hash = require_sha256(obj["checkpoint_hash"], "policy.checkpoint_hash")
    without_hash = dict(obj)
    del without_hash["checkpoint_hash"]
    if content_hash(without_hash) != checkpoint_hash:
        raise ContractError("policy.checkpoint_hash: payload hash mismatch")
    return PolicyCheckpoint(
        POLICY_SCHEMA_VERSION,
        require_string(obj["policy_version"], "policy.policy_version"),
        require_string(obj["graph_version"], "policy.graph_version"),
        require_sha256(obj["base_graph_hash"], "policy.base_graph_hash"),
        ALGORITHM_ID,
        OBJECTIVE_SEMANTICS,
        config,
        config_hash,
        input_hashes,
        training_hashes,
        tuple(updates),
        dict(summary),
        checkpoint_hash,
    )


@dataclass(slots=True)
class _Accumulator:
    support: int = 0
    weighted_support: float = 0.0
    weighted_signal: float = 0.0
    positive: int = 0
    negative: int = 0


def _load_graph(graph: str | Path | Mapping[str, Any]) -> tuple[dict[str, Any], str, str]:
    if isinstance(graph, Mapping):
        value = dict(graph)
    else:
        path = Path(graph)
        if path.is_dir():
            path = path / "graph.json"
        raw = load_json(path)
        if not isinstance(raw, dict):
            raise ContractError("graph snapshot must be a JSON object")
        value = raw
    # One hash domain for mappings, graph files, and snapshot directories.
    # Serialization whitespace and file location must not alter graph identity.
    graph_hash = content_hash(value)
    version = value.get("graph_version")
    if not isinstance(version, str) or not version:
        raise ContractError("graph snapshot has no graph_version")
    return value, version, graph_hash


def _iter_raw_records(source: Any) -> Iterator[Any]:
    if isinstance(source, CandidateEpisode) or isinstance(source, Mapping):
        yield source
        return
    if isinstance(source, (str, Path)):
        if isinstance(source, str) and source.lstrip().startswith(("{", "[")):
            try:
                value = json.loads(source)
            except json.JSONDecodeError:
                for line in source.splitlines():
                    if line.strip():
                        yield line
                return
            if isinstance(value, list):
                yield from value
            else:
                yield value
            return
        path = Path(source)
        if path.exists():
            text = path.read_text(encoding="utf-8")
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                for line in text.splitlines():
                    if line.strip():
                        yield line
                return
            if isinstance(value, list):
                yield from value
            else:
                yield value
            return
        yield source
        return
    iterator = getattr(source, "iter_payloads", None)
    if callable(iterator):
        yield from iterator()
        return
    yield from source


def iter_episode_store(path: str | Path) -> Iterator[str]:
    """Read an EpisodeStore export in SQLite read-only mode."""

    location = Path(path).resolve()
    if not location.is_file():
        raise ContractError(f"episode store does not exist: {location}")
    try:
        connection = sqlite3.connect(f"file:{location}?mode=ro", uri=True)
        try:
            # Import locally to avoid coupling the policy model to store setup at
            # module import time.  Training never consumes an unverified chain.
            from .store import default_object_directory, verify_store_connection

            verify_store_connection(connection, default_object_directory(location))
            rows = connection.execute("SELECT payload_json FROM episodes ORDER BY sequence_id")
            for (payload,) in rows:
                yield str(payload)
        finally:
            connection.close()
    except sqlite3.Error as exc:
        raise ContractError(f"cannot read episode store {location}: {exc}") from exc


def _parse_episode(value: Any) -> CandidateEpisode:
    if isinstance(value, CandidateEpisode):
        # Frozen dataclasses can still be constructed directly; round-trip through
        # the contract so the content hash and all nested invariants are checked.
        return CandidateEpisode.from_dict(to_primitive(value))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ContractError(f"candidate episode is not valid JSON: {exc}") from exc
    return CandidateEpisode.from_dict(value)


def _bump(reasons: dict[str, int], reason: str) -> None:
    reasons[reason] = reasons.get(reason, 0) + 1


def _provenance_reason(episode: CandidateEpisode, config: PolicyTrainingConfig) -> str | None:
    if episode.runtime_build.lower().startswith("legacy") or episode.draft.proposed_by.lower().startswith("legacy"):
        return "legacy_episode"
    if not any(episode.runtime_build.startswith(prefix) for prefix in config.allowed_runtime_prefixes):
        return "not_machine_finalized"
    if episode.outcome.decision_hash == "sha256:" + "0" * 64:
        return "not_machine_finalized"
    if config.require_known_producer_hashes:
        hashes = episode.draft.producer_hashes
        if "unknown" in {hashes.model, hashes.prompt, hashes.agent}:
            return "provenance_incomplete"
    artifacts = episode.evidence.artifacts
    if episode.outcome.verdict in {
        GateVerdict.BUILD_FAILED,
        GateVerdict.ACCURACY_FAILED,
        GateVerdict.RUNTIME_FAILED,
    } and "build_log" not in artifacts:
        return "provenance_incomplete"
    if episode.outcome.verdict in {
        GateVerdict.ACCURACY_FAILED,
        GateVerdict.RUNTIME_FAILED,
    } and "accuracy_report" not in artifacts:
        return "provenance_incomplete"
    return None


def _measurement_reason(episode: CandidateEpisode, config: PolicyTrainingConfig) -> str | None:
    outcome = episode.outcome
    if outcome.verdict is GateVerdict.MEASUREMENT_UNSTABLE:
        return "measurement_unstable"
    if outcome.verdict is GateVerdict.ARTIFACTS_INCOMPLETE:
        return "provenance_incomplete"
    if outcome.verdict not in _MEASURED_VERDICTS:
        return None
    if outcome.pair_count < config.min_measurement_pairs:
        return "measurement_pairs_insufficient"
    if outcome.measurement_protocol != "paired_log_speedup_deterministic_bootstrap_lcb_v1":
        return "measurement_protocol_unqualified"
    if not math.isfinite(outcome.measurement_cv) or outcome.measurement_cv > config.max_measurement_cv:
        return "measurement_unstable"
    if "measurement_report" not in episode.evidence.artifacts:
        return "measurement_provenance_incomplete"
    return None


def _training_signal(episode: CandidateEpisode, config: PolicyTrainingConfig) -> tuple[float | None, str | None]:
    verdict = episode.outcome.verdict
    if verdict.value == "verified_noop":
        return None, "verified_noop"
    if verdict is GateVerdict.ATTRIBUTION_UNCERTAIN:
        return None, "attribution_uncertain"
    if verdict is GateVerdict.PRODUCTION_SAFE_GAIN:
        if not episode.outcome.eligible or episode.outcome.utility <= 0:
            return None, "positive_utility_inconsistent"
        return min(episode.outcome.utility, config.max_abs_signal), None
    configured = config.negative_verdict_utilities.get(verdict.value)
    if configured is None:
        return None, "verdict_not_configured"
    return max(configured, -config.max_abs_signal), None


def train_fixed_graph_policy(
    graph: str | Path | Mapping[str, Any],
    episodes: Iterable[Any] | EpisodeExport | str | Path,
    *,
    policy_version: str,
    config: PolicyTrainingConfig | None = None,
) -> PolicyCheckpoint:
    """Fit deterministic edge biases without changing the graph structure.

    This is an observational update from machine gate outcomes. It deliberately
    does not estimate or claim causal credit for a mechanism or transformation.
    """

    if not policy_version.strip():
        raise ValueError("policy_version must be non-empty")
    training_config = config or PolicyTrainingConfig()
    graph_value, graph_version, graph_hash = _load_graph(graph)
    edges = {
        edge["id"]: edge
        for edge in graph_value.get("edges", [])
        if edge.get("edge_type") == "problem_to_skill_prior" and edge.get("trainable") is True
    }
    accumulators = {edge_id: _Accumulator() for edge_id in edges}
    skip_reasons: dict[str, int] = {}
    input_hashes: set[str] = set()
    training_hashes: set[str] = set()
    seen: set[str] = set()
    accepted: list[tuple[str, str, float, float]] = []
    input_count = 0

    for raw in _iter_raw_records(episodes):
        input_count += 1
        try:
            episode = _parse_episode(raw)
        except (ContractError, TypeError, ValueError):
            _bump(skip_reasons, "contract_invalid")
            continue
        input_hashes.add(episode.episode_hash)
        if episode.episode_hash in seen:
            _bump(skip_reasons, "duplicate_episode")
            continue
        seen.add(episode.episode_hash)
        if episode.draft.route.graph_version != graph_version:
            _bump(skip_reasons, "graph_version_mismatch")
            continue
        if episode.graph_hash != graph_hash:
            _bump(skip_reasons, "graph_hash_mismatch")
            continue
        reason = _provenance_reason(episode, training_config)
        if reason:
            _bump(skip_reasons, reason)
            continue
        if not episode.outcome.policy_update_eligible:
            _bump(
                skip_reasons,
                "verified_noop" if episode.outcome.verdict.value == "verified_noop" else "policy_update_ineligible",
            )
            continue
        reason = _measurement_reason(episode, training_config)
        if reason:
            _bump(skip_reasons, reason)
            continue
        edge_id = episode.draft.route.selected_edge_id
        if edge_id not in edges:
            _bump(skip_reasons, "selected_edge_not_trainable")
            continue
        route_candidates = {item.edge_id: item for item in episode.draft.route.candidates}
        if set(route_candidates) != set(edges):
            _bump(skip_reasons, "route_candidate_set_mismatch")
            continue
        selected_route = route_candidates[edge_id]
        graph_edge = edges[edge_id]
        if (
            selected_route.source_id != graph_edge["source"]
            or selected_route.target_id != graph_edge["target"]
        ):
            _bump(skip_reasons, "route_edge_identity_mismatch")
            continue
        signal, reason = _training_signal(episode, training_config)
        if reason:
            _bump(skip_reasons, reason)
            continue
        assert signal is not None
        propensity = episode.draft.route.behavior_probability
        if training_config.use_recorded_propensity:
            if propensity <= 0 or not math.isfinite(propensity):
                _bump(skip_reasons, "propensity_invalid")
                continue
            weight = min(1.0 / propensity, training_config.max_importance_weight)
        else:
            weight = 1.0
        accepted.append((episode.episode_hash, edge_id, signal, weight))
        training_hashes.add(episode.episode_hash)

    # Hash ordering makes the floating-point reduction independent of export or
    # database row order.
    for _, edge_id, signal, weight in sorted(accepted):
        accumulator = accumulators[edge_id]
        accumulator.support += 1
        accumulator.weighted_support += weight
        accumulator.weighted_signal += weight * signal
        accumulator.positive += int(signal > 0)
        accumulator.negative += int(signal < 0)

    updates: list[EdgePolicyUpdate] = []
    for edge_id, edge in sorted(edges.items()):
        accumulator = accumulators[edge_id]
        prior = float(edge["prior_logit"])
        if accumulator.support < training_config.min_support:
            bias = 0.0
            reliability = 0.0
        else:
            raw_bias = (
                training_config.learning_rate
                * accumulator.weighted_signal
                / (accumulator.weighted_support + training_config.shrinkage)
            )
            bias = max(-training_config.max_abs_bias, min(training_config.max_abs_bias, raw_bias))
            reliability = accumulator.weighted_support / (
                accumulator.weighted_support + training_config.shrinkage
            )
        updates.append(EdgePolicyUpdate(
            edge_id=edge_id,
            source_id=str(edge["source"]),
            target_id=str(edge["target"]),
            prior_logit=prior,
            bias=bias,
            effective_logit=prior + bias,
            reliability=reliability,
            support_count=accumulator.support,
            weighted_support=accumulator.weighted_support,
            positive_count=accumulator.positive,
            negative_count=accumulator.negative,
        ))

    config_value = training_config.to_dict()
    summary = {
        "input_record_count": input_count,
        "unique_valid_episode_count": len(input_hashes),
        "training_episode_count": len(training_hashes),
        "updated_edge_count": sum(item.bias != 0 for item in updates),
        "skip_reasons": dict(sorted(skip_reasons.items())),
    }
    without_hash = {
        "schema_version": POLICY_SCHEMA_VERSION,
        "policy_version": policy_version,
        "graph_version": graph_version,
        "base_graph_hash": graph_hash,
        "algorithm": ALGORITHM_ID,
        "objective_semantics": OBJECTIVE_SEMANTICS,
        "config": config_value,
        "config_hash": content_hash(config_value),
        "input_episode_hashes": sorted(input_hashes),
        "training_data_hashes": sorted(training_hashes),
        "edge_updates": [to_primitive(item) for item in updates],
        "training_summary": summary,
    }
    return PolicyCheckpoint(
        schema_version=POLICY_SCHEMA_VERSION,
        policy_version=policy_version,
        graph_version=graph_version,
        base_graph_hash=graph_hash,
        algorithm=ALGORITHM_ID,
        objective_semantics=OBJECTIVE_SEMANTICS,
        config=config_value,
        config_hash=without_hash["config_hash"],
        input_episode_hashes=tuple(sorted(input_hashes)),
        training_data_hashes=tuple(sorted(training_hashes)),
        edge_updates=tuple(updates),
        training_summary=summary,
        checkpoint_hash=content_hash(without_hash),
    )


def write_policy_checkpoint(checkpoint: PolicyCheckpoint, path: str | Path) -> None:
    """Publish once: an existing checkpoint path is never overwritten."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(checkpoint.to_dict(), ensure_ascii=False, sort_keys=True, indent=2))
        stream.write("\n")
