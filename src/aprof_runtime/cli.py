from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Sequence

from .contracts import Context, GateRequest, validate_contract
from .episodes import finalize_episodes
from .errors import AProfRuntimeError, ContractError
from .gates import CandidateGate
from .graph import load_snapshot, route_graph, validate_policy_for_graph
from .jsonio import content_hash, dump_json, load_json, to_primitive
from .policy import (
    PolicyTrainingConfig,
    iter_episode_store,
    load_policy_checkpoint,
    train_fixed_graph_policy,
    write_policy_checkpoint,
)
from .store import EpisodeStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aprofctl")
    commands = parser.add_subparsers(dest="command", required=True)

    contract = commands.add_parser("contract", help="validate strict runtime contracts")
    contract_commands = contract.add_subparsers(dest="action", required=True)
    validate = contract_commands.add_parser("validate")
    validate.add_argument("--kind", required=True)
    validate.add_argument("--input", required=True, type=Path)

    candidate = commands.add_parser("candidate", help="run machine-authoritative candidate gates")
    candidate_commands = candidate.add_subparsers(dest="action", required=True)
    gate = candidate_commands.add_parser("gate")
    gate.add_argument("--request", required=True, type=Path)

    episode = commands.add_parser("episode", help="finalize and append candidate episodes")
    episode_commands = episode.add_subparsers(dest="action", required=True)
    finalize = episode_commands.add_parser("finalize")
    finalize.add_argument("--context", required=True, type=Path)
    finalize.add_argument("--request", required=True, type=Path)
    finalize.add_argument("--graph", required=True, type=Path)
    finalize.add_argument("--policy", type=Path, help="exact behavior-policy checkpoint used for routing")
    finalize.add_argument("--store", type=Path)
    verify_episodes = episode_commands.add_parser("verify", help="verify CAS objects and the episode hash chain")
    verify_episodes.add_argument("--store", required=True, type=Path)

    artifact = commands.add_parser("artifact", help="manage content-addressed artifacts")
    artifact_commands = artifact.add_subparsers(dest="action", required=True)
    add_artifact = artifact_commands.add_parser("add")
    add_artifact.add_argument("--store", required=True, type=Path)
    add_artifact.add_argument("--file", required=True, type=Path)
    add_artifact.add_argument("--media-type")
    verify_artifact = artifact_commands.add_parser("verify")
    verify_artifact.add_argument("--store", required=True, type=Path)
    verify_artifact.add_argument("--content-hash", required=True)

    graph = commands.add_parser("graph", help="validate and route immutable graph snapshots")
    graph_commands = graph.add_subparsers(dest="action", required=True)
    graph_validate = graph_commands.add_parser("validate")
    graph_validate.add_argument("--graph", required=True, type=Path)
    graph_route = graph_commands.add_parser("route")
    graph_route.add_argument("--graph", required=True, type=Path)
    graph_route.add_argument("--context", required=True, type=Path)
    graph_route.add_argument("--policy-version", default="expert-prior")
    graph_route.add_argument("--policy", type=Path, help="validated fixed-graph policy checkpoint")
    graph_route.add_argument("--selection-mode", choices=("argmax", "sample"), default="argmax")
    graph_route.add_argument("--selection-seed", type=int)

    policy = commands.add_parser("policy", help="train and validate fixed-graph policy checkpoints")
    policy_commands = policy.add_subparsers(dest="action", required=True)
    policy_train = policy_commands.add_parser("train")
    policy_train.add_argument("--graph", required=True, type=Path)
    policy_train.add_argument(
        "--episodes", required=True, type=Path,
        help="verified EpisodeStore SQLite database (JSON/JSONL is intentionally rejected)",
    )
    policy_train.add_argument("--policy-version", required=True)
    policy_train.add_argument("--output", required=True, type=Path)
    policy_train.add_argument("--config", type=Path, help="optional PolicyTrainingConfig JSON")
    policy_validate = policy_commands.add_parser("validate")
    policy_validate.add_argument("--checkpoint", required=True, type=Path)
    policy_validate.add_argument("--graph", type=Path, help="also require exact graph compatibility")
    return parser


def _snapshot_hash(graph: dict[str, Any]) -> str:
    return content_hash(graph)


def _episode_training_source(path: Path) -> Any:
    with path.open("rb") as stream:
        is_sqlite = stream.read(16) == b"SQLite format 3\x00"
    if not is_sqlite:
        raise ContractError(
            "policy training requires a verified SQLite EpisodeStore so CAS artifacts and the hash chain can be checked"
        )
    return iter_episode_store(path)


def run(arguments: argparse.Namespace) -> Any:
    if arguments.command == "contract":
        validated = validate_contract(arguments.kind, load_json(arguments.input))
        return {"valid": True, "kind": arguments.kind, "value": to_primitive(validated)}
    if arguments.command == "candidate":
        request = GateRequest.from_dict(load_json(arguments.request))
        return {"outcomes": to_primitive(CandidateGate().evaluate(request))}
    if arguments.command == "episode" and arguments.action == "finalize":
        context = Context.from_dict(load_json(arguments.context))
        request = GateRequest.from_dict(load_json(arguments.request))
        episodes = finalize_episodes(
            context,
            request,
            graph=arguments.graph,
            behavior_policy=arguments.policy,
        )
        sequences: list[int] = []
        if arguments.store:
            with EpisodeStore(arguments.store) as store:
                sequences = list(store.append_many(episodes))
        return {"episodes": to_primitive(episodes), "store_sequences": sequences}
    if arguments.command == "episode" and arguments.action == "verify":
        with EpisodeStore(arguments.store) as store:
            head = store.verify_integrity()
            count = store.connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        return {"valid": True, "episode_count": int(count), "chain_head": head}
    if arguments.command == "artifact" and arguments.action == "add":
        with EpisodeStore(arguments.store) as store:
            digest = store.register_artifact(arguments.file, media_type=arguments.media_type)
        return {"content_hash": digest}
    if arguments.command == "artifact" and arguments.action == "verify":
        with EpisodeStore(arguments.store) as store:
            object_path = store.verify_artifact(arguments.content_hash)
        return {"valid": True, "content_hash": arguments.content_hash, "object": str(object_path)}
    if arguments.command == "graph" and arguments.action == "validate":
        graph, manifest = load_snapshot(arguments.graph)
        return {
            "valid": True,
            "graph_version": graph["graph_version"],
            "counts": {
                key: len(graph[key]) for key in ("anchors", "predicates", "mechanisms", "transformations", "edges")
            },
            "manifest_validated": manifest is not None,
        }
    if arguments.command == "graph" and arguments.action == "route":
        graph, _ = load_snapshot(arguments.graph)
        context = Context.from_dict(load_json(arguments.context))
        return {"route": to_primitive(route_graph(
            graph, context,
            policy_version=arguments.policy_version,
            policy=arguments.policy,
            base_graph_hash=_snapshot_hash(graph) if arguments.policy else None,
            selection_mode=arguments.selection_mode,
            selection_seed=arguments.selection_seed,
        ))}
    if arguments.command == "policy" and arguments.action == "train":
        # Validate the immutable graph snapshot before using its priors.
        load_snapshot(arguments.graph)
        config = (
            PolicyTrainingConfig.from_dict(load_json(arguments.config))
            if arguments.config else PolicyTrainingConfig()
        )
        checkpoint = train_fixed_graph_policy(
            arguments.graph,
            _episode_training_source(arguments.episodes),
            policy_version=arguments.policy_version,
            config=config,
        )
        write_policy_checkpoint(checkpoint, arguments.output)
        return {
            "checkpoint": to_primitive(checkpoint),
            "output": str(arguments.output),
        }
    if arguments.command == "policy" and arguments.action == "validate":
        checkpoint = load_policy_checkpoint(arguments.checkpoint)
        compatible = None
        if arguments.graph:
            graph, _ = load_snapshot(arguments.graph)
            validate_policy_for_graph(
                graph,
                checkpoint,
                base_graph_hash=_snapshot_hash(graph),
            )
            compatible = str(arguments.graph)
        return {
            "valid": True,
            "policy_version": checkpoint.policy_version,
            "graph_version": checkpoint.graph_version,
            "compatible_graph": compatible,
        }
    raise AssertionError("unreachable command")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    try:
        result = run(parser.parse_args(argv))
    except (AProfRuntimeError, OSError) as exc:
        print(dump_json({"ok": False, "error": str(exc)}), file=sys.stderr, end="")
        return 2
    print(dump_json({"ok": True, "result": result}), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
