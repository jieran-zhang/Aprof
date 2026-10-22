from __future__ import annotations

from typing import Any, Mapping

from .contracts import Context, RouteDecision
from .errors import ContractError
from .graph import route_graph, validate_graph, validate_policy_for_graph
from .jsonio import content_hash, require_sha256
from .policy import load_policy_checkpoint


def attest_route(
    *,
    context: Context,
    recorded: RouteDecision,
    graph_snapshot: Mapping[str, Any],
    graph_hash: str,
    behavior_policy_checkpoint: Mapping[str, Any] | None,
    policy_checkpoint_hash: str | None,
) -> RouteDecision:
    """Recompute a route from the exact graph, context, policy, and RNG seed.

    Hashes bind identities; this function establishes authority by replaying the
    deterministic computation and comparing the complete typed RouteDecision.
    """

    graph = validate_graph(dict(graph_snapshot))
    expected_graph_hash = content_hash(graph)
    if require_sha256(graph_hash, "episode.graph_hash") != expected_graph_hash:
        raise ContractError("episode.graph_hash: canonical graph payload hash mismatch")

    policy = None
    if behavior_policy_checkpoint is None:
        if policy_checkpoint_hash is not None:
            raise ContractError(
                "episode.policy_checkpoint_hash: must be null for expert-prior routing"
            )
        if recorded.policy_version != "expert-prior":
            raise ContractError(
                "episode.behavior_policy_checkpoint: required for a learned policy route"
            )
    else:
        policy = load_policy_checkpoint(behavior_policy_checkpoint)
        expected_policy_hash = require_sha256(
            policy_checkpoint_hash, "episode.policy_checkpoint_hash"
        )
        if policy.checkpoint_hash != expected_policy_hash:
            raise ContractError(
                "episode.policy_checkpoint_hash: does not match embedded checkpoint"
            )
        validate_policy_for_graph(graph, policy, base_graph_hash=expected_graph_hash)
        if recorded.policy_version != policy.policy_version:
            raise ContractError(
                "episode.route.policy_version: does not match embedded checkpoint"
            )

    recomputed = route_graph(
        graph,
        context,
        policy_version=recorded.policy_version,
        policy=policy,
        base_graph_hash=expected_graph_hash if policy is not None else None,
        selection_mode=recorded.selection_mode,
        selection_seed=recorded.selection_seed,
    )
    if recomputed != recorded:
        raise ContractError(
            "episode.route: does not match graph/context/policy deterministic replay"
        )
    return recomputed

