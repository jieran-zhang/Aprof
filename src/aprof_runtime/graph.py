from __future__ import annotations

import math
import random
from pathlib import Path
from typing import Any

from .contracts import Context, RouteCandidate, RouteDecision
from .errors import GraphError
from .jsonio import content_hash, file_hash, load_json, require_object, require_string
from .policy import PolicyCheckpoint, load_policy_checkpoint


def _digest_equal(expected: Any, actual: str, path: str) -> None:
    expected_string = require_string(expected, path)
    normalized = expected_string if expected_string.startswith("sha256:") else "sha256:" + expected_string
    if normalized != actual:
        raise GraphError(f"{path}: checksum mismatch; expected {normalized}, got {actual}")


def _snapshot_file(snapshot_root: Path, value: Any, path: str) -> Path:
    """Resolve a manifest-controlled path without leaving the snapshot directory."""
    name = require_string(value, path)
    relative = Path(name)
    if (
        relative.is_absolute()
        or "\\" in name
        or relative.as_posix() != name
        or any(part in {"", ".", ".."} for part in relative.parts)
    ):
        raise GraphError(f"{path}: expected a normalized snapshot-relative path")
    root = snapshot_root.resolve()
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise GraphError(f"{path}: path resolves outside snapshot root") from exc
    return candidate


def _ids(items: Any, kind: str) -> set[str]:
    if not isinstance(items, list):
        raise GraphError(f"graph.{kind}: expected array")
    result: set[str] = set()
    for index, item in enumerate(items):
        obj = require_object(item, f"graph.{kind}[{index}]")
        identifier = require_string(obj.get("id"), f"graph.{kind}[{index}].id")
        if identifier in result:
            raise GraphError(f"graph.{kind}: duplicate id {identifier!r}")
        result.add(identifier)
    return result


def validate_graph(graph: Any) -> dict[str, Any]:
    obj = require_object(graph, "graph")
    required = {
        "schema_version", "graph_version", "created_from", "anchors", "predicates",
        "mechanisms", "transformations", "edges",
    }
    missing = required - obj.keys()
    if missing:
        raise GraphError("graph: missing fields: " + ", ".join(sorted(missing)))
    require_string(obj["schema_version"], "graph.schema_version")
    require_string(obj["graph_version"], "graph.graph_version")
    anchors = _ids(obj["anchors"], "anchors")
    predicates = _ids(obj["predicates"], "predicates")
    mechanisms = _ids(obj["mechanisms"], "mechanisms")
    transformations = _ids(obj["transformations"], "transformations")
    if "transformation.noop" not in transformations:
        raise GraphError("graph.transformations: required transformation.noop is missing")
    if "mechanism.unknown_unresolved" not in mechanisms:
        raise GraphError("graph.mechanisms: required mechanism.unknown_unresolved is missing")
    node_ids = anchors | predicates | mechanisms | transformations
    edge_ids: set[str] = set()
    edges = obj["edges"]
    if not isinstance(edges, list):
        raise GraphError("graph.edges: expected array")
    for index, value in enumerate(edges):
        edge = require_object(value, f"graph.edges[{index}]")
        for field in ("id", "version", "edge_type", "source", "target", "trainable", "prior_logit", "hard_preconditions", "provenance"):
            if field not in edge:
                raise GraphError(f"graph.edges[{index}]: missing field {field}")
        edge_id = require_string(edge["id"], f"graph.edges[{index}].id")
        if edge_id in edge_ids:
            raise GraphError(f"graph.edges: duplicate id {edge_id!r}")
        edge_ids.add(edge_id)
        source = require_string(edge["source"], f"graph.edges[{index}].source")
        target = require_string(edge["target"], f"graph.edges[{index}].target")
        if source not in node_ids or target not in node_ids:
            raise GraphError(f"graph.edges[{index}]: dangling source or target")
        edge_type = require_string(edge["edge_type"], f"graph.edges[{index}].edge_type")
        trainable = edge["trainable"]
        if type(trainable) is not bool:
            raise GraphError(f"graph.edges[{index}].trainable: expected boolean")
        logit = edge["prior_logit"]
        if edge_type == "problem_to_skill_prior":
            if not trainable or isinstance(logit, bool) or not isinstance(logit, (int, float)):
                raise GraphError(f"graph.edges[{index}]: problem_to_skill_prior must be trainable with numeric prior_logit")
            if not source.startswith("mechanism.") or not target.startswith("transformation."):
                raise GraphError(f"graph.edges[{index}]: problem_to_skill_prior must connect mechanism to transformation")
        elif logit is not None or trainable:
            raise GraphError(f"graph.edges[{index}]: non-policy edges must be non-trainable with null prior_logit")
    return obj


def load_snapshot(path: str | Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    location = Path(path)
    if location.is_file():
        graph = validate_graph(load_json(location))
        return graph, None
    if not location.is_dir():
        raise GraphError(f"snapshot path does not exist: {location}")
    location = location.resolve()
    manifest_path = _snapshot_file(location, "manifest.json", "snapshot manifest")
    if not manifest_path.is_file():
        raise GraphError("snapshot manifest: file is missing")
    manifest_value = load_json(manifest_path)
    manifest = require_object(manifest_value, "manifest")
    if manifest.get("immutable") is not True:
        raise GraphError("manifest.immutable must be true")
    files = require_object(manifest.get("files"), "manifest.files")
    if "graph" not in files or "checksums" not in files:
        raise GraphError("manifest.files must declare graph and checksums")
    resolved_manifest_files = {
        name: _snapshot_file(location, value, f"manifest.files.{name}")
        for name, value in files.items()
    }
    for name, candidate in resolved_manifest_files.items():
        if not candidate.is_file():
            raise GraphError(f"manifest.files.{name}: file is missing")
    graph_path = resolved_manifest_files["graph"]
    _digest_equal(manifest.get("graph_sha256"), file_hash(graph_path), "manifest.graph_sha256")

    checksums_path = resolved_manifest_files["checksums"]
    checksums = require_object(load_json(checksums_path), "checksums")
    if checksums.get("algorithm") != "sha256":
        raise GraphError("checksums.algorithm must be sha256")
    checksum_files = require_object(checksums.get("files"), "checksums.files")
    for name, expected in checksum_files.items():
        candidate = _snapshot_file(location, name, f"checksums.files.{name}")
        # A checksums file cannot contain its own stable digest.  If present,
        # it is ignored; every other declared snapshot file is verified.
        if candidate == checksums_path:
            continue
        if not candidate.is_file():
            raise GraphError(f"checksums.files.{name}: file is missing")
        _digest_equal(expected, file_hash(candidate), f"checksums.files.{name}")
    checksum_paths = {
        _snapshot_file(location, name, f"checksums.files.{name}")
        for name in checksum_files
    }
    for name, candidate in resolved_manifest_files.items():
        if name != "checksums" and candidate not in checksum_paths:
            raise GraphError(f"manifest.files.{name}: file is not covered by checksums")
    if manifest_path not in checksum_paths:
        raise GraphError("snapshot manifest is not covered by checksums")
    graph = validate_graph(load_json(graph_path))
    if manifest.get("graph_version") != graph.get("graph_version"):
        raise GraphError("manifest.graph_version does not match graph.graph_version")
    return graph, manifest


def _lookup(context: Context, dotted_path: str) -> Any:
    root: Any = {
        "task_id": context.task_id,
        "operator": context.operator,
        "hardware_fingerprint": context.hardware_fingerprint,
        "workload": context.workload,
        "budget": context.budget,
        "evidence": context.evidence,
    }
    current = root
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _condition_matches(context: Context, condition: Any) -> bool:
    if condition in (None, [], {}):
        return True
    if isinstance(condition, dict):
        if set(condition) == {"predicate", "state"}:
            predicate_states = context.evidence.get("predicate_states", {})
            if not isinstance(predicate_states, dict):
                return False
            # Missing is deliberately distinct from false.  Predicates use
            # true/false/unknown, so absent or "unknown" only matches an
            # explicitly requested unknown state.
            actual = predicate_states.get(str(condition["predicate"]), "unknown")
            return actual == condition["state"]
        if {"path", "op", "value"} <= condition.keys():
            actual, expected, operation = _lookup(context, str(condition["path"])), condition["value"], condition["op"]
            if operation == "eq":
                return actual == expected
            if operation == "ne":
                return actual != expected
            if operation == "in":
                return actual in expected if isinstance(expected, list) else False
            if operation == "contains":
                return expected in actual if isinstance(actual, (list, str, dict)) else False
            return False
        return all(_lookup(context, key) == value for key, value in condition.items())
    if isinstance(condition, list):
        return all(_condition_matches(context, item) for item in condition)
    return False


def validate_policy_for_graph(
    graph: dict[str, Any],
    policy: PolicyCheckpoint | dict[str, Any] | str | Path,
    *,
    base_graph_hash: str | None = None,
) -> tuple[PolicyCheckpoint, dict[str, float]]:
    """Validate exact graph compatibility and return effective edge logits."""

    checkpoint = load_policy_checkpoint(policy.to_dict() if isinstance(policy, PolicyCheckpoint) else policy)
    expected_hash = base_graph_hash or content_hash(graph)
    if checkpoint.graph_version != graph.get("graph_version"):
        raise GraphError(
            f"policy.graph_version {checkpoint.graph_version!r} does not match graph {graph.get('graph_version')!r}"
        )
    if checkpoint.base_graph_hash != expected_hash:
        raise GraphError(
            f"policy.base_graph_hash mismatch; expected {expected_hash}, got {checkpoint.base_graph_hash}"
        )
    graph_policy_edges = {
        str(edge["id"]): edge for edge in graph["edges"]
        if edge["edge_type"] == "problem_to_skill_prior"
    }
    updates = {item.edge_id: item for item in checkpoint.edge_updates}
    if set(updates) != set(graph_policy_edges):
        missing = sorted(set(graph_policy_edges) - set(updates))
        extra = sorted(set(updates) - set(graph_policy_edges))
        raise GraphError(f"policy edge set mismatch; missing={missing}, extra={extra}")
    for edge_id, update in updates.items():
        edge = graph_policy_edges[edge_id]
        if update.source_id != edge["source"] or update.target_id != edge["target"]:
            raise GraphError(f"policy edge {edge_id!r} endpoints do not match graph")
        if not math.isclose(update.prior_logit, float(edge["prior_logit"]), rel_tol=0.0, abs_tol=1e-12):
            raise GraphError(f"policy edge {edge_id!r} prior_logit does not match graph")
    return checkpoint, {edge_id: item.effective_logit for edge_id, item in updates.items()}


def route_graph(
    graph: dict[str, Any],
    context: Context,
    *,
    policy_version: str = "expert-prior",
    policy: PolicyCheckpoint | dict[str, Any] | str | Path | None = None,
    base_graph_hash: str | None = None,
    selection_mode: str = "argmax",
    selection_seed: int | None = None,
) -> RouteDecision:
    policy_logits: dict[str, float] | None = None
    if policy is not None:
        checkpoint, policy_logits = validate_policy_for_graph(
            graph, policy, base_graph_hash=base_graph_hash
        )
        if policy_version != "expert-prior" and policy_version != checkpoint.policy_version:
            raise GraphError("explicit policy_version does not match checkpoint policy_version")
        policy_version = checkpoint.policy_version
    if selection_mode not in {"argmax", "sample"}:
        raise GraphError("selection_mode must be argmax or sample")
    if selection_mode == "argmax" and selection_seed is not None:
        raise GraphError("argmax selection requires no seed")
    if selection_mode == "sample" and (isinstance(selection_seed, bool) or not isinstance(selection_seed, int)):
        raise GraphError("sample selection requires an integer seed")
    predicate_states = context.evidence.get("predicate_states", {})
    if not isinstance(predicate_states, dict):
        raise GraphError("context.evidence.predicate_states must be an object")
    mechanism_ids = {str(item["id"]) for item in graph["mechanisms"]}
    mechanism_scores = {identifier: 0.0 for identifier in mechanism_ids}
    for edge in graph["edges"]:
        if edge["edge_type"] not in {"supports", "refutes"}:
            continue
        state = predicate_states.get(str(edge["source"]), "unknown")
        if state not in {True, False, "unknown"}:
            raise GraphError(
                f"context.evidence.predicate_states.{edge['source']}: expected true, false, or unknown"
            )
        if state is True:
            mechanism_scores[str(edge["target"])] += 1.0 if edge["edge_type"] == "supports" else -1.0
    active_set = {identifier for identifier, score in mechanism_scores.items() if score > 0.0}
    if not active_set:
        active_set = {"mechanism.unknown_unresolved"}
    edges = [
        edge for edge in graph["edges"]
        if edge["edge_type"] == "problem_to_skill_prior"
    ]
    if not edges:
        raise GraphError("graph has no problem_to_skill_prior edges")
    mask_reasons: list[tuple[str, ...]] = []
    for edge in edges:
        reasons: list[str] = []
        if edge["source"] not in active_set:
            reasons.append("mechanism_not_supported_by_fixed_evidence_graph")
        if not _condition_matches(context, edge["hard_preconditions"]):
            reasons.append("hard_preconditions_not_satisfied")
        mask_reasons.append(tuple(reasons))
    allowed = [not reasons for reasons in mask_reasons]
    logits = [
        policy_logits[str(edge["id"])] if policy_logits is not None else float(edge["prior_logit"])
        for edge in edges
    ]
    allowed_logits = [logit for logit, ok in zip(logits, allowed, strict=True) if ok]
    if not allowed_logits:
        raise GraphError("all candidate edges were rejected by hard preconditions")
    maximum = max(allowed_logits)
    weights = [math.exp(logit - maximum) if ok else 0.0 for logit, ok in zip(logits, allowed, strict=True)]
    total = sum(weights)
    probabilities = [weight / total for weight in weights]
    if selection_mode == "argmax":
        best_index = min(range(len(edges)), key=lambda i: (-probabilities[i], str(edges[i]["id"])))
        behavior_probability = 1.0
    else:
        draw = random.Random(selection_seed).random()
        cumulative = 0.0
        best_index = len(edges) - 1
        for index, probability in enumerate(probabilities):
            cumulative += probability
            if draw < cumulative:
                best_index = index
                break
        behavior_probability = probabilities[best_index]
    candidates = tuple(
        RouteCandidate(
            str(edge["id"]), str(edge["source"]), str(edge["target"]), logit,
            probability, ok, reasons,
        )
        for edge, logit, probability, ok, reasons in zip(
            edges, logits, probabilities, allowed, mask_reasons, strict=True
        )
    )
    return RouteDecision(
        graph_version=str(graph["graph_version"]),
        policy_version=policy_version,
        selected_edge_id=candidates[best_index].edge_id,
        behavior_probability=behavior_probability,
        selection_mode=selection_mode,
        selection_seed=selection_seed,
        selected_mechanism_id=candidates[best_index].source_id,
        mechanism_derivation="fixed_supports_refutes_tri_state_v1",
        mechanism_scores=mechanism_scores,
        candidates=candidates,
    )
