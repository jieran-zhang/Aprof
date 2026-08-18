from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import uuid4

from . import __version__
from .attestation import attest_route
from .contracts import CandidateEpisode, Context, GateRequest, SCHEMA_VERSION
from .errors import ContractError
from .gates import CandidateGate
from .graph import load_snapshot, validate_graph, validate_policy_for_graph
from .jsonio import content_hash
from .policy import PolicyCheckpoint, load_policy_checkpoint


def _budget_limit(context: Context, name: str) -> int | None:
    value = context.budget.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ContractError(f"context.budget.{name}: expected non-negative integer")
    return value


def _enforce_session_budget(context: Context, request: GateRequest) -> None:
    """Enforce the counters observable at the episode-finalization boundary."""

    counts = {
        "candidate_limit": len(request.candidates),
        "build_limit": sum(item.build.value != "not_run" for item in request.evidence),
        "timing_limit": sum(
            bool(item.baseline_samples_ns or item.candidate_samples_ns)
            for item in request.evidence
        ),
        "full_profile_limit": sum(
            "profile_report" in item.artifacts for item in request.evidence
        ),
    }
    for name, used in counts.items():
        limit = _budget_limit(context, name)
        if limit is not None and used > limit:
            raise ContractError(
                f"context.budget.{name}: request uses {used}, exceeding limit {limit}"
            )


def _graph_payload(graph: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(graph, Mapping):
        return validate_graph(dict(graph))
    value, _ = load_snapshot(graph)
    return value


def _policy_payload(
    policy: PolicyCheckpoint | str | Path | Mapping[str, Any] | None,
) -> tuple[dict[str, Any] | None, str | None]:
    if policy is None:
        return None, None
    if isinstance(policy, PolicyCheckpoint):
        checkpoint = load_policy_checkpoint(policy.to_dict())
    else:
        checkpoint = load_policy_checkpoint(policy)
    return checkpoint.to_dict(), checkpoint.checkpoint_hash


def finalize_episodes(
    context: Context,
    request: GateRequest,
    *,
    graph: str | Path | Mapping[str, Any],
    behavior_policy: PolicyCheckpoint | str | Path | Mapping[str, Any] | None = None,
    finalized_at: str | None = None,
    runtime_build: str | None = None,
) -> tuple[CandidateEpisode, ...]:
    """Re-run the authoritative gate and materialize immutable episodes."""
    if context.task_id.strip() == "":
        raise ContractError("context task_id is empty")
    _enforce_session_budget(context, request)
    graph_snapshot = _graph_payload(graph)
    graph_hash = content_hash(graph_snapshot)
    policy_payload, policy_hash = _policy_payload(behavior_policy)
    if behavior_policy is not None:
        assert policy_payload is not None
        validate_policy_for_graph(
            graph_snapshot, policy_payload, base_graph_hash=graph_hash
        )
    for draft in request.candidates:
        attest_route(
            context=context,
            recorded=draft.route,
            graph_snapshot=graph_snapshot,
            graph_hash=graph_hash,
            behavior_policy_checkpoint=policy_payload,
            policy_checkpoint_hash=policy_hash,
        )
    timestamp = finalized_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    build = runtime_build or f"aprof-runtime/{__version__}"
    outcomes = CandidateGate().evaluate(request)
    evidence = {item.candidate_id: item for item in request.evidence}
    episodes: list[CandidateEpisode] = []
    for draft, outcome in zip(request.candidates, outcomes, strict=True):
        episode = CandidateEpisode(
            schema_version=SCHEMA_VERSION,
            episode_id=f"episode-{uuid4()}",
            context=context,
            graph_snapshot=graph_snapshot,
            graph_hash=graph_hash,
            behavior_policy_checkpoint=policy_payload,
            policy_checkpoint_hash=policy_hash,
            gate_request=request,
            draft=draft,
            evidence=evidence[draft.candidate_id],
            outcome=outcome,
            finalized_at=timestamp,
            runtime_build=build,
            episode_hash="sha256:" + "0" * 64,
        )
        digest = content_hash({
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
        episodes.append(replace(episode, episode_hash=digest))
    return tuple(episodes)
