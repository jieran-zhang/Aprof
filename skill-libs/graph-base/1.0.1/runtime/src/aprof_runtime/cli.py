from __future__ import annotations

import argparse
from contextlib import nullcontext
import sys
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4

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
from .traces import (export_episodes, merge_trace_streams, recover_trace_tail,
                     validate_trace_contract, verify_optimization_traces, verify_trace)
from .exploration import ExplorationGate, verify_exploration


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
    _evidence_arguments(gate)

    episode = commands.add_parser("episode", help="finalize candidate episodes locally or append to a store")
    episode_commands = episode.add_subparsers(dest="action", required=True)
    finalize = episode_commands.add_parser("finalize")
    finalize.add_argument("--context", required=True, type=Path)
    finalize.add_argument("--request", required=True, type=Path)
    finalize.add_argument("--graph", required=True, type=Path)
    finalize.add_argument("--policy", type=Path, help="exact behavior-policy checkpoint used for routing")
    evidence = finalize.add_mutually_exclusive_group()
    evidence.add_argument("--store", type=Path)
    evidence.add_argument("--local-index", type=Path,
                          help="verify task-local evidence and return episodes without archiving")
    finalize.add_argument("--output-index", type=Path, help="new local evidence index; never overwrite the input")
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

    dispatch = commands.add_parser("dispatch", help="validate workload metadata entry selection")
    dispatch_commands = dispatch.add_subparsers(dest="action", required=True)
    dispatch_select = dispatch_commands.add_parser("select")
    dispatch_select.add_argument("--plan", required=True, type=Path)
    dispatch_select.add_argument("--workload", required=True, type=Path)
    dispatch_validate = dispatch_commands.add_parser("validate-context")
    dispatch_validate.add_argument("--context", required=True, type=Path)

    trace = commands.add_parser("trace", help="validate and collect independent evidence streams")
    trace_commands = trace.add_subparsers(dest="action", required=True)
    trace_verify = trace_commands.add_parser("verify")
    trace_verify.add_argument("--input", required=True, type=Path)
    trace_verify.add_argument("--kind", choices=("events", "optimization"), default="events")
    trace_verify.add_argument("--store", type=Path)
    trace_merge = trace_commands.add_parser("merge")
    trace_merge.add_argument("--input", required=True, nargs="+", type=Path)
    trace_merge.add_argument("--output", required=True, type=Path)
    trace_merge.add_argument("--store", type=Path)
    trace_recover = trace_commands.add_parser("recover")
    trace_recover.add_argument("--input", required=True, type=Path)
    trace_recover.add_argument("--store", type=Path)
    trace_export = trace_commands.add_parser("export-episodes")
    trace_export.add_argument("--store", required=True, type=Path)
    trace_export.add_argument("--output", required=True, type=Path)

    exploration = commands.add_parser("exploration", help="gate graph coverage gaps without v1 episodes")
    exploration_commands = exploration.add_subparsers(dest="action", required=True)
    for action in ("gate", "verify"):
        command = exploration_commands.add_parser(action)
        command.add_argument("--request", required=True, type=Path)
        _evidence_arguments(command, required=True)
        if action == "verify":
            command.add_argument("--outcomes", required=True, type=Path)

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
    task = commands.add_parser("task", help="portable task budgets, tools and private scratch")
    actions = task.add_subparsers(dest="action", required=True)
    workspace = actions.add_parser("workspace-create")
    workspace.add_argument("--task-id", required=True)
    workspace.add_argument("--parent", type=Path)
    workspace.add_argument("--collect", action="store_true", help="require collector handoff before cleanup")
    cleanup = actions.add_parser("cleanup")
    cleanup.add_argument("--workspace", required=True, type=Path)
    cleanup.add_argument("--local-index", required=True, type=Path)
    cleanup.add_argument("--terminal-ref", required=True)
    cleanup.add_argument("--collector-receipt", type=Path)
    budget = actions.add_parser("budget-check")
    budget.add_argument("--plan", type=Path)
    budget.add_argument("--local-index", type=Path)
    budget.add_argument("--launch-ref")
    budget.add_argument("--task-id")
    runner = actions.add_parser("run", help="run one frozen job with inherited remaining time")
    runner.add_argument("--local-index", required=True, type=Path)
    runner.add_argument("--budget-ref", required=True)
    runner.add_argument("--job-ref", required=True)
    runner.add_argument("--destination", required=True, type=Path)
    runner.add_argument("--prior-terminal-ref", action="append", default=[])
    toolchain = actions.add_parser("toolchain")
    toolchain.add_argument("--check", type=Path, help="check an already frozen toolchain; never rediscover")
    for option in ("sdk-root", "python", "cmake", "cxx", "npu-smi"):
        toolchain.add_argument("--" + option)
    return parser


def _evidence_arguments(parser, *, required=False):
    evidence = parser.add_mutually_exclusive_group(required=required)
    evidence.add_argument("--store", type=Path, help="explicit legacy/archive CAS reader")
    evidence.add_argument("--local-index", type=Path, help="verify local evidence without archiving")
    parser.add_argument("--output-index", type=Path, help="new local evidence index; never overwrite the input")


def _evidence_reader(arguments):
    if arguments.output_index is not None and arguments.local_index is None:
        raise ContractError("--output-index requires --local-index")
    if arguments.local_index is not None:
        from .local_evidence import LocalEvidence
        reader = LocalEvidence.from_index(arguments.local_index)
        output = Path(arguments.output_index or reader.directory.parent / ("local-index-" + uuid4().hex + ".json")).absolute()
        if (output.resolve() != output or not output.is_relative_to(reader.directory.parent)
                or output.exists() or output.is_symlink() or not output.parent.is_dir()):
            raise ContractError("output index must be a new file inside the task workspace")
        arguments.output_index = output
        return nullcontext(reader)
    return EpisodeStore(arguments.store) if arguments.store else nullcontext(None)


def _local_result(arguments, reader, result):
    if arguments.local_index is None:
        return result
    output = arguments.output_index or reader.directory.parent / ("local-index-" + uuid4().hex + ".json")
    index = reader.write_index(output)
    return {**result, "storage_mode": "local_profile_only", "archive_performed": False,
            "local_index": str(index)}


def _task_command(arguments):
    if arguments.action == "run":
        from .local_evidence import LocalEvidence
        from .task_budget import run_task
        return run_task(LocalEvidence.from_index(arguments.local_index), budget_ref=arguments.budget_ref,
                        job_ref=arguments.job_ref, destination=arguments.destination,
                        prior_terminal_refs=arguments.prior_terminal_ref)
    if arguments.action == "workspace-create":
        from .task_workspace import create_workspace
        return create_workspace(arguments.task_id, parent=arguments.parent, collect=arguments.collect)
    if arguments.action == "cleanup":
        from .task_workspace import cleanup_workspace
        return cleanup_workspace(arguments.workspace, local_index=arguments.local_index,
                                 terminal_ref=arguments.terminal_ref, collector_receipt=arguments.collector_receipt)
    if arguments.action == "budget-check":
        from .task_budget import validate_budget_plan, replay_task_budget
        if arguments.plan:
            if any((arguments.local_index, arguments.launch_ref, arguments.task_id)):
                raise ContractError("use --plan alone, or --local-index/--launch-ref/--task-id together")
            return {"valid": True, "plan": validate_budget_plan(load_json(arguments.plan)),
                    "verification": "plan_structure_only"}
        if not all((arguments.local_index, arguments.launch_ref, arguments.task_id)):
            raise ContractError("budget replay requires --local-index, --launch-ref and --task-id")
        from .local_evidence import LocalEvidence
        return {"valid": True, "budget": replay_task_budget(LocalEvidence.from_index(arguments.local_index),
                    {"kind": "task", "launch_ref": arguments.launch_ref}, task_id=arguments.task_id)}
    if arguments.action == "toolchain":
        from .task_toolchain import discover_task_toolchain, validate_task_toolchain
        options = {key: getattr(arguments, key) for key in ("sdk_root", "python", "cmake", "cxx", "npu_smi")}
        if arguments.check:
            if any(options.values()):
                raise ContractError("a frozen toolchain check cannot select replacement tools")
            binding = load_json(arguments.check)
            validate_task_toolchain(binding, live=True)
            return {"valid": True, "toolchain": binding}
        return {"toolchain": discover_task_toolchain(**options)}
    raise AssertionError("unreachable task command")


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
    if arguments.command == "task":
        return _task_command(arguments)
    if arguments.command == "dispatch":
        from .planning import select_dispatch, validate_planning_context
        if arguments.action == "select":
            return select_dispatch(load_json(arguments.plan), load_json(arguments.workload))
        validate_planning_context(Context.from_dict(load_json(arguments.context)), execution=True)
        return {"valid": True, "contract": "architecture_parallel_dispatch_v1"}
    if arguments.command == "contract":
        trace_kinds = {"trace_event", "optimization_trace", "exploration_manifest", "exploration_request", "exploration_outcome", "normalized_profile", "mechanism_report", "capture_manifest"}
        validator = (lambda kind, value: validate_trace_contract(kind.replace("_", "-"), value)) if arguments.kind in trace_kinds else validate_contract
        validated = validator(arguments.kind, load_json(arguments.input))
        return {"valid": True, "kind": arguments.kind, "value": to_primitive(validated)}
    if arguments.command == "trace":
        with EpisodeStore(arguments.store) if arguments.store else nullcontext(None) as store:
            if arguments.action == "verify":
                verifier = verify_trace if arguments.kind == "events" else verify_optimization_traces
                return verifier(arguments.input, store)
            if arguments.action == "merge":
                return merge_trace_streams(arguments.input, arguments.output, store)
            if arguments.action == "recover":
                return recover_trace_tail(arguments.input, store)
            return export_episodes(store, arguments.output)
    if arguments.command == "exploration":
        with _evidence_reader(arguments) as store:
            request = load_json(arguments.request)
            if arguments.action == "gate":
                return _local_result(arguments, store, {"outcomes": ExplorationGate().evaluate(request, store=store)})
            outcomes = load_json(arguments.outcomes)
            if isinstance(outcomes, dict):
                outcomes = outcomes.get("outcomes", outcomes.get("result", {}).get("outcomes"))
            if not isinstance(outcomes, list):
                raise ContractError("expected exploration outcomes array")
            return _local_result(arguments, store, verify_exploration(request, outcomes, store=store))
    if arguments.command == "candidate":
        request = GateRequest.from_dict(load_json(arguments.request))
        with _evidence_reader(arguments) as store:
            return _local_result(arguments, store, {"outcomes": to_primitive(CandidateGate().evaluate(request, store=store))})
    if arguments.command == "episode" and arguments.action == "finalize":
        context = Context.from_dict(load_json(arguments.context))
        request = GateRequest.from_dict(load_json(arguments.request))
        if arguments.local_index is not None:
            with _evidence_reader(arguments) as store:
                episodes = finalize_episodes(context, request, graph=arguments.graph,
                    behavior_policy=arguments.policy, store=store)
                return _local_result(arguments, store, {"episodes": to_primitive(episodes), "store_sequences": []})
        if arguments.output_index is not None:
            raise ContractError("--output-index requires --local-index")
        with EpisodeStore(arguments.store) if arguments.store else nullcontext(None) as store:
            episodes = finalize_episodes(
                context, request, graph=arguments.graph,
                behavior_policy=arguments.policy, store=store,
            )
            sequences = list(store.append_many(episodes)) if store is not None else []
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
        arguments = parser.parse_args(argv)
        result = run(arguments)
    except (AProfRuntimeError, OSError) as exc:
        print(dump_json({"ok": False, "error": str(exc)}), file=sys.stderr, end="")
        return 2
    print(dump_json({"ok": True, "result": result}), end="")
    if arguments.command == "task" and arguments.action == "run" and result["status"] != "passed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
