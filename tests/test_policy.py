from __future__ import annotations

import json
import copy
import tempfile
import unittest
from pathlib import Path

from aprof_runtime.cli import _parser, run
from aprof_runtime.contracts import Context, EMPTY_ARTIFACT_SHA256, GateRequest, GateVerdict
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.errors import ContractError
from aprof_runtime.graph import route_graph
from aprof_runtime.jsonio import content_hash, to_primitive
from aprof_runtime.policy import PolicyTrainingConfig, load_policy_checkpoint, train_fixed_graph_policy
from aprof_runtime.store import EpisodeStore


HASH_A = "sha256:" + "a" * 64
HASH_B = "sha256:" + "b" * 64
EDGE_ID = "edge.prior.demo.optimize"
SECOND_EDGE_ID = "edge.prior.demo.noop"


def graph_dict() -> dict:
    return {
        "schema_version": "1.0.0",
        "graph_version": "vtest",
        "created_from": {},
        "anchors": [],
        "predicates": [{"id": "predicate.demo"}],
        "mechanisms": [{"id": "mechanism.demo"}, {"id": "mechanism.unknown_unresolved"}],
        "transformations": [{"id": "transformation.demo"}, {"id": "transformation.noop"}],
        "edges": [
            {
                "id": "edge.support.demo", "version": "1.0.0", "edge_type": "supports",
                "source": "predicate.demo", "target": "mechanism.demo", "trainable": False,
                "prior_logit": None, "hard_preconditions": [], "provenance": [],
            },
            {
                "id": EDGE_ID, "version": "1.0.0", "edge_type": "problem_to_skill_prior",
                "source": "mechanism.demo", "target": "transformation.demo", "trainable": True,
                "prior_logit": 2.5, "hard_preconditions": [], "provenance": [],
            },
        ],
    }


def episode(
    candidate_id: str,
    *,
    graph_version: str = "vtest",
    verdict: str = "gain",
    known_provenance: bool = True,
    mechanism_alignment: bool | None = True,
    graph: dict | None = None,
    selection_mode: str = "argmax",
    selection_seed: int | None = None,
):
    graph_value = copy.deepcopy(graph or graph_dict())
    graph_value["graph_version"] = graph_version
    context = Context.from_dict({
        "schema_version": "1.0.0",
        "task_id": f"task-{candidate_id}",
        "operator": "demo",
        "hardware_fingerprint": "ascend:test",
        "workload": {"shape": [1024]},
        "budget": {"candidate_limit": 1},
        "evidence": {"predicate_states": {"predicate.demo": True}},
    })
    route = to_primitive(route_graph(
        graph_value,
        context,
        selection_mode=selection_mode,
        selection_seed=selection_seed,
    ))
    selected = next(item for item in route["candidates"] if item["edge_id"] == route["selected_edge_id"])
    draft = {
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "session_id": f"session-{candidate_id}",
        "route": route,
        "transformation_id": selected["target_id"],
        "transformation_version": "1.0.0",
        "producer_hashes": {
            "model": HASH_A if known_provenance else "unknown",
            "prompt": HASH_A,
            "agent": HASH_A,
        },
        "source_hashes": {"baseline": HASH_A, "candidate": HASH_B},
        "patch_artifact_hash": HASH_B,
        "parameters": {},
        "proposed_by": "agent:test",
        "created_at": "2026-08-11T00:00:00Z",
    }
    evidence = {
        "candidate_id": candidate_id,
        "static_review": "passed",
        "build": "passed",
        "accuracy": "passed",
        "runtime": "passed",
        "semantic": "passed",
        "scope": "passed",
        "portability": "passed",
        "baseline_samples_ns": [100.0 + (index % 3 - 1) * 0.2 for index in range(30)],
        "candidate_samples_ns": [80.0 + (index % 3 - 1) * 0.2 for index in range(30)],
        "mechanism_alignment": mechanism_alignment,
        "heldout_regressions": [0.0],
        "artifacts": {
            "build_log": HASH_A,
            "accuracy_report": HASH_A,
            "measurement_report": HASH_A,
        },
    }
    config = {"min_pairs": 30, "bootstrap_resamples": 200, "min_speedup_lcb": 1.03}
    if verdict == "build_failed":
        evidence.update({"build": "failed", "accuracy": "not_run", "runtime": "not_run"})
        evidence.pop("baseline_samples_ns")
        evidence.pop("candidate_samples_ns")
    elif verdict == "attribution_uncertain":
        config["require_mechanism_alignment"] = True
    request = GateRequest.from_dict({
        "schema_version": "1.0.0",
        "candidates": [draft],
        "evidence": [evidence],
        "config": config,
    })
    return finalize_episodes(
        context,
        request,
        graph=graph_value,
        finalized_at="2026-08-11T01:00:00Z",
        runtime_build="aprof-runtime/test",
    )[0]


def update(checkpoint):
    return next(item for item in checkpoint.edge_updates if item.edge_id == EDGE_ID)


class FixedGraphPolicyTests(unittest.TestCase):
    def test_verified_gain_moves_bias_positive_from_expert_prior(self) -> None:
        checkpoint = train_fixed_graph_policy(
            graph_dict(), [episode("gain")], policy_version="p0001",
            config=PolicyTrainingConfig(min_support=1),
        )
        item = update(checkpoint)
        self.assertGreater(item.bias, 0)
        self.assertEqual(item.effective_logit, item.prior_logit + item.bias)
        self.assertEqual(item.positive_count, 1)
        self.assertLessEqual(item.bias, 0.5)
        self.assertEqual(checkpoint.training_summary["training_episode_count"], 1)

    def test_typed_negative_is_opt_in_and_moves_bias_negative(self) -> None:
        failed = episode("failed", verdict="build_failed")
        default = train_fixed_graph_policy(
            graph_dict(), [failed], policy_version="p-default",
            config=PolicyTrainingConfig(min_support=1),
        )
        self.assertEqual(update(default).bias, 0)
        configured = train_fixed_graph_policy(
            graph_dict(), [failed], policy_version="p-negative",
            config=PolicyTrainingConfig(
                min_support=1,
                negative_verdict_utilities={"build_failed": -0.75},
            ),
        )
        self.assertLess(update(configured).bias, 0)
        self.assertEqual(update(configured).negative_count, 1)

    def test_ineligible_records_are_filtered_with_typed_reasons(self) -> None:
        uncertain = episode(
            "uncertain", verdict="attribution_uncertain", mechanism_alignment=None,
        )
        incomplete = episode("unknown-producer", known_provenance=False)
        checkpoint = train_fixed_graph_policy(
            graph_dict(), [uncertain, incomplete], policy_version="p0001",
            config=PolicyTrainingConfig(min_support=1),
        )
        reasons = checkpoint.training_summary["skip_reasons"]
        self.assertEqual(reasons["attribution_uncertain"], 1)
        self.assertEqual(reasons["provenance_incomplete"], 1)
        self.assertEqual(update(checkpoint).bias, 0)
        self.assertEqual(checkpoint.training_data_hashes, ())

    def test_verified_noop_is_reserved_for_future_stop_model(self) -> None:
        seed = episode("noop")
        context = seed.context
        noop_graph = graph_dict()
        noop_edge = next(item for item in noop_graph["edges"] if item["id"] == EDGE_ID)
        noop_edge["target"] = "transformation.noop"
        draft = to_primitive(seed.draft)
        draft["transformation_id"] = "transformation.noop"
        draft["route"] = to_primitive(route_graph(noop_graph, context))
        draft["source_hashes"]["candidate"] = draft["source_hashes"]["baseline"]
        draft["patch_artifact_hash"] = EMPTY_ARTIFACT_SHA256
        draft["parameters"] = {"no_mutation": True, "reason": "expert prior recommends stopping"}
        evidence = to_primitive(seed.evidence)
        evidence["runtime"] = "not_run"
        evidence["baseline_samples_ns"] = []
        evidence["candidate_samples_ns"] = []
        request = GateRequest.from_dict({
            "schema_version": "1.0.0",
            "candidates": [draft],
            "evidence": [evidence],
            "config": {},
        })
        noop = finalize_episodes(
            context, request, graph=noop_graph, finalized_at="2026-08-11T01:00:00Z",
            runtime_build="aprof-runtime/test",
        )[0]
        self.assertEqual(noop.outcome.verdict, GateVerdict.VERIFIED_NOOP)
        self.assertFalse(noop.outcome.policy_update_eligible)
        checkpoint = train_fixed_graph_policy(
            noop_graph, [noop], policy_version="p0001",
            config=PolicyTrainingConfig(min_support=1),
        )
        self.assertEqual(checkpoint.training_summary["skip_reasons"]["verified_noop"], 1)
        self.assertEqual(update(checkpoint).support_count, 0)

    def test_checkpoint_is_deterministic_and_export_order_independent(self) -> None:
        first_episode = episode("first")
        second_episode = episode("second")
        config = PolicyTrainingConfig(min_support=1)
        first = train_fixed_graph_policy(
            graph_dict(), [first_episode, to_primitive(second_episode)],
            policy_version="p0001", config=config,
        )
        second = train_fixed_graph_policy(
            graph_dict(), [to_primitive(second_episode), first_episode],
            policy_version="p0001", config=config,
        )
        self.assertEqual(first, second)
        self.assertEqual(first.checkpoint_hash, second.checkpoint_hash)

    def test_checkpoint_loader_rejects_rehashed_out_of_bounds_bias(self) -> None:
        checkpoint = train_fixed_graph_policy(
            graph_dict(), [], policy_version="p0001",
            config=PolicyTrainingConfig(max_abs_bias=0.5),
        )
        forged = to_primitive(checkpoint)
        forged["edge_updates"][0]["bias"] = 999.0
        forged["edge_updates"][0]["effective_logit"] = (
            forged["edge_updates"][0]["prior_logit"] + 999.0
        )
        forged["checkpoint_hash"] = content_hash({
            key: value for key, value in forged.items() if key != "checkpoint_hash"
        })
        with self.assertRaisesRegex(ContractError, "exceeds configured max_abs_bias"):
            load_policy_checkpoint(forged)

    def test_graph_hash_domain_is_canonical_for_mapping_and_file(self) -> None:
        graph = graph_dict()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "graph.json"
            path.write_text(json.dumps(graph, indent=4), encoding="utf-8")
            from_mapping = train_fixed_graph_policy(graph, [], policy_version="p0001")
            from_file = train_fixed_graph_policy(path, [], policy_version="p0001")
        self.assertEqual(from_mapping.base_graph_hash, from_file.base_graph_hash)
        self.assertEqual(from_mapping, from_file)

    def test_graph_version_mismatch_never_updates_target_graph(self) -> None:
        checkpoint = train_fixed_graph_policy(
            graph_dict(), [episode("wrong", graph_version="vother")],
            policy_version="p0001", config=PolicyTrainingConfig(min_support=1),
        )
        self.assertEqual(update(checkpoint).support_count, 0)
        self.assertEqual(
            checkpoint.training_summary["skip_reasons"]["graph_version_mismatch"], 1,
        )

    def test_same_version_different_graph_hash_never_updates_target_graph(self) -> None:
        behavior_graph = graph_dict()
        behavior_graph["edges"][-1]["prior_logit"] = 2.0
        checkpoint = train_fixed_graph_policy(
            graph_dict(), [episode("wrong-hash", graph=behavior_graph)],
            policy_version="p0001", config=PolicyTrainingConfig(min_support=1),
        )
        self.assertEqual(update(checkpoint).support_count, 0)
        self.assertEqual(
            checkpoint.training_summary["skip_reasons"]["graph_hash_mismatch"], 1,
        )

    def test_two_episodes_checkpoint_changes_real_candidate_ranking(self) -> None:
        graph = {
            "schema_version": "1.0.0",
            "graph_version": "vtest",
            "created_from": {},
            "anchors": [],
            "predicates": [{"id": "predicate.demo"}],
            "mechanisms": [
                {"id": "mechanism.demo"},
                {"id": "mechanism.unknown_unresolved"},
            ],
            "transformations": [
                {"id": "transformation.demo"},
                {"id": "transformation.noop"},
            ],
            "edges": [
                {
                    "id": "edge.support.demo", "version": "1.0.0", "edge_type": "supports",
                    "source": "predicate.demo", "target": "mechanism.demo",
                    "trainable": False, "prior_logit": None,
                    "hard_preconditions": [], "provenance": [],
                },
                {
                    "id": EDGE_ID, "version": "1.0.0", "edge_type": "problem_to_skill_prior",
                    "source": "mechanism.demo", "target": "transformation.demo",
                    "trainable": True, "prior_logit": 0.0,
                    "hard_preconditions": [], "provenance": [],
                },
                {
                    "id": SECOND_EDGE_ID, "version": "1.0.0", "edge_type": "problem_to_skill_prior",
                    "source": "mechanism.demo", "target": "transformation.noop",
                    "trainable": True, "prior_logit": 0.05,
                    "hard_preconditions": [], "provenance": [],
                },
            ],
        }
        episodes = [
            episode("e2e-1", graph=graph, selection_mode="sample", selection_seed=1),
            episode("e2e-2", graph=graph, selection_mode="sample", selection_seed=3),
        ]
        checkpoint = train_fixed_graph_policy(
            graph, episodes, policy_version="p0001",
            config=PolicyTrainingConfig(min_support=2),
        )
        context = Context.from_dict({
            "schema_version": "1.0.0",
            "task_id": "route-after-training",
            "operator": "demo",
            "hardware_fingerprint": "ascend:test",
            "workload": {},
            "budget": {},
            "evidence": {"predicate_states": {"predicate.demo": True}},
        })
        before = route_graph(graph, context)
        after = route_graph(graph, context, policy=checkpoint)
        self.assertEqual(before.selected_edge_id, SECOND_EDGE_ID)
        self.assertEqual(after.selected_edge_id, EDGE_ID)
        self.assertEqual(after.policy_version, "p0001")
        before_logit = next(item.logit for item in before.candidates if item.edge_id == EDGE_ID)
        after_logit = next(item.logit for item in after.candidates if item.edge_id == EDGE_ID)
        self.assertGreater(after_logit, before_logit)

    def test_cli_trains_verified_store_validates_and_routes_with_checkpoint(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = root / "skillgraph" / "versions" / "v0001"
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            episodes_path = temporary / "episodes.sqlite"
            with EpisodeStore(episodes_path):
                pass
            unsafe_jsonl = temporary / "episodes.jsonl"
            unsafe_jsonl.write_text("{}\n", encoding="utf-8")
            with self.assertRaisesRegex(ContractError, "verified SQLite EpisodeStore"):
                run(_parser().parse_args([
                    "policy", "train", "--graph", str(snapshot),
                    "--episodes", str(unsafe_jsonl), "--policy-version", "unsafe",
                    "--output", str(temporary / "unsafe.json"),
                ]))
            output = temporary / "pcli.json"
            train_args = _parser().parse_args([
                "policy", "train", "--graph", str(snapshot),
                "--episodes", str(episodes_path), "--policy-version", "pcli",
                "--output", str(output),
            ])
            trained = run(train_args)
            self.assertTrue(output.is_file())
            self.assertEqual(trained["checkpoint"]["policy_version"], "pcli")
            validated = run(_parser().parse_args([
                "policy", "validate", "--checkpoint", str(output),
                "--graph", str(snapshot),
            ]))
            self.assertTrue(validated["valid"])
            context_path = temporary / "context.json"
            context_path.write_text(json.dumps({
                "schema_version": "1.0.0",
                "task_id": "cli-route",
                "operator": "demo",
                "hardware_fingerprint": "ascend:test",
                "workload": {},
                "budget": {},
                "evidence": {"predicate_states": {}},
            }), encoding="utf-8")
            routed = run(_parser().parse_args([
                "graph", "route", "--graph", str(snapshot),
                "--context", str(context_path), "--policy", str(output),
            ]))
            self.assertEqual(routed["route"]["policy_version"], "pcli")


if __name__ == "__main__":
    unittest.main()
