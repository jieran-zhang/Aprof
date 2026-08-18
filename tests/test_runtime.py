from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from aprof_runtime.contracts import CandidateDraft, Context, EMPTY_ARTIFACT_SHA256, GateRequest, GateStageStatus, GateVerdict
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.gates import CandidateGate
from aprof_runtime.graph import load_snapshot, route_graph
from aprof_runtime.jsonio import content_hash, to_primitive
from aprof_runtime.store import EpisodeStore, _require_complete_batches


HASH = "sha256:" + "a" * 64
ARTIFACTS = {"build_log": HASH, "accuracy_report": HASH, "measurement_report": HASH}
GRAPH_PATH = Path(__file__).resolve().parents[1] / "skillgraph" / "versions" / "v0001"


def context_dict() -> dict:
    return {
        "schema_version": "1.0.0",
        "task_id": "task-1",
        "operator": "demo_op",
        "hardware_fingerprint": "ascend:test",
        "workload": {"shape": [1024]},
        "budget": {"candidate_limit": 2},
        "evidence": {"active_mechanisms": ["mechanism.unknown_unresolved"]},
    }


def route_dict(edge: str = "edge-1", probability: float = 1.0) -> dict:
    return {
        "graph_version": "v0001",
        "policy_version": "p0000",
        "selected_edge_id": edge,
        "behavior_probability": 1.0,
        "selection_mode": "argmax",
        "selection_seed": None,
        "selected_mechanism_id": "mechanism.unknown_unresolved",
        "mechanism_derivation": "fixed_supports_refutes_tri_state_v1",
        "mechanism_scores": {"mechanism.unknown_unresolved": 0.0},
        "candidates": [{
            "edge_id": edge, "source_id": "mechanism.unknown_unresolved",
            "target_id": "transformation.test", "logit": 0.0, "probability": probability,
            "allowed": True, "mask_reasons": [],
        }],
    }


def draft_dict(candidate_id: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "session_id": "session-1",
        "route": route_dict(),
        "transformation_id": "transformation.test",
        "transformation_version": "1.0.0",
        "producer_hashes": {"model": "unknown", "prompt": HASH, "agent": HASH},
        "source_hashes": {"baseline": HASH, "candidate": HASH},
        "patch_artifact_hash": HASH,
        "parameters": {},
        "proposed_by": "agent:test",
        "created_at": "2026-08-11T00:00:00Z",
    }


def evidence_dict(candidate_id: str, candidate_samples: list[float] | None = None) -> dict:
    baseline = [100.0, 101.0, 99.0, 100.0, 102.0] * 6
    candidate = (candidate_samples or [80.0, 81.0, 79.0, 80.0, 82.0]) * 6
    return {
        "candidate_id": candidate_id,
        "static_review": "passed",
        "build": "passed",
        "accuracy": "passed",
        "runtime": "passed",
        "semantic": "passed",
        "scope": "passed",
        "portability": "passed",
        "baseline_samples_ns": baseline,
        "candidate_samples_ns": candidate,
        "mechanism_alignment": True,
        "heldout_regressions": [0.0, 0.01],
        "artifacts": ARTIFACTS,
    }


def request_dict(*candidate_ids: str) -> dict:
    return {
        "schema_version": "1.0.0",
        "candidates": [draft_dict(identifier) for identifier in candidate_ids],
        "evidence": [evidence_dict(identifier) for identifier in candidate_ids],
        "config": {"min_pairs": 30, "bootstrap_resamples": 200, "min_speedup_lcb": 1.03},
    }


def noop_request_dict(candidate_id: str = "noop") -> dict:
    draft = draft_dict(candidate_id)
    draft["route"]["candidates"][0]["target_id"] = "transformation.noop"
    draft["transformation_id"] = "transformation.noop"
    draft["patch_artifact_hash"] = EMPTY_ARTIFACT_SHA256
    draft["parameters"] = {"no_mutation": True, "reason": "budget exhausted; preserve verified baseline"}
    evidence = evidence_dict(candidate_id)
    evidence.update({
        "build": "not_run", "accuracy": "not_run", "runtime": "not_run", "semantic": "not_run",
        "scope": "not_run", "portability": "not_run", "artifacts": {},
    })
    evidence.pop("baseline_samples_ns")
    evidence.pop("candidate_samples_ns")
    return {"schema_version": "1.0.0", "candidates": [draft], "evidence": [evidence], "config": {}}


def finalization_inputs(value: dict, *, noop: bool = False, budget: dict | None = None):
    graph, _ = load_snapshot(GRAPH_PATH)
    raw_context = context_dict()
    if budget is not None:
        raw_context["budget"] = budget
    raw_context["evidence"] = {
        "predicate_states": {} if noop else {"predicate.profile.scalar_hot": True}
    }
    context = Context.from_dict(raw_context)
    route = to_primitive(route_graph(graph, context))
    selected = next(item for item in route["candidates"] if item["edge_id"] == route["selected_edge_id"])
    cloned = json.loads(json.dumps(value))
    for draft in cloned["candidates"]:
        draft["route"] = route
        draft["transformation_id"] = selected["target_id"]
    return context, GateRequest.from_dict(cloned), graph


class ContractTests(unittest.TestCase):
    def test_gate_config_cannot_weaken_runtime_safety_profile(self) -> None:
        unsafe_values = (
            ("min_pairs", 29, "requires value >= 30"),
            ("max_cv", 0.051, "requires value <= 0.05"),
            ("min_speedup_lcb", 1.029, "requires value >= 1.03"),
            ("max_heldout_regression", 0.031, "requires value <= 0.03"),
            ("require_mechanism_alignment", False, "requires true"),
            ("required_artifacts", ["build_log"], "requires accuracy_report, measurement_report"),
        )
        for field, unsafe, message in unsafe_values:
            with self.subTest(field=field), self.assertRaisesRegex(ContractError, message):
                value = request_dict("c1")
                value["config"][field] = unsafe
                GateRequest.from_dict(value)

    def test_gate_config_may_tighten_runtime_safety_profile(self) -> None:
        value = request_dict("c1")
        value["config"].update({
            "min_pairs": 31,
            "max_cv": 0.04,
            "min_speedup_lcb": 1.05,
            "max_heldout_regression": 0.02,
            "required_artifacts": [*ARTIFACTS, "static_review_report"],
        })
        config = GateRequest.from_dict(value).config
        self.assertEqual(config.min_pairs, 31)
        self.assertEqual(config.required_artifacts[-1], "static_review_report")

    def test_agent_cannot_set_selected_as_best_on_draft(self) -> None:
        value = draft_dict("c1")
        value["selected_as_best"] = True
        with self.assertRaisesRegex(ContractError, "unknown fields: selected_as_best"):
            CandidateDraft.from_dict(value)

    def test_probability_invariants_are_strict(self) -> None:
        value = draft_dict("c1")
        value["route"]["behavior_probability"] = 0.5
        with self.assertRaisesRegex(ContractError, "argmax behavior probability must be 1"):
            CandidateDraft.from_dict(value)

    def test_transformation_identity_must_match_selected_edge(self) -> None:
        value = draft_dict("c1")
        value["transformation_id"] = "transformation.some_other_skill"
        with self.assertRaisesRegex(ContractError, "does not match selected route target"):
            CandidateDraft.from_dict(value)

    def test_early_build_failure_needs_no_timing(self) -> None:
        value = evidence_dict("c1")
        value.update({"build": "failed", "accuracy": "not_run", "runtime": "not_run"})
        value.pop("baseline_samples_ns")
        value.pop("candidate_samples_ns")
        request = request_dict("c1")
        request["evidence"] = [value]
        outcome = CandidateGate().evaluate(GateRequest.from_dict(request))[0]
        self.assertEqual(outcome.verdict, GateVerdict.BUILD_FAILED)
        self.assertEqual(outcome.pair_count, 0)


class GateTests(unittest.TestCase):
    def test_direct_dataclass_construction_cannot_bypass_gate_profile(self) -> None:
        request = GateRequest.from_dict(request_dict("c1"))
        unsafe = replace(request, config=replace(request.config, min_pairs=1))
        with self.assertRaisesRegex(ContractError, "requires value >= 30"):
            CandidateGate().evaluate(unsafe)

    def test_verified_noop_is_audited_but_never_selected_or_trained_as_gain(self) -> None:
        request = GateRequest.from_dict(noop_request_dict())
        outcome = CandidateGate().evaluate(request)[0]
        self.assertEqual(outcome.verdict, GateVerdict.VERIFIED_NOOP)
        self.assertEqual(outcome.utility, 0.0)
        self.assertFalse(outcome.eligible)
        self.assertFalse(outcome.policy_update_eligible)
        self.assertFalse(outcome.selected_as_best)
        self.assertIn("no_mutation", outcome.state_path)
        context, final_request, graph = finalization_inputs(noop_request_dict(), noop=True)
        episode = finalize_episodes(context, final_request, graph=graph)[0]
        self.assertEqual(episode.outcome.verdict, GateVerdict.VERIFIED_NOOP)

    def test_noop_with_mutated_source_or_nonempty_patch_is_rejected(self) -> None:
        value = noop_request_dict()
        value["candidates"][0]["source_hashes"]["candidate"] = "sha256:" + "b" * 64
        value["candidates"][0]["patch_artifact_hash"] = HASH
        outcome = CandidateGate().evaluate(GateRequest.from_dict(value))[0]
        self.assertEqual(outcome.verdict, GateVerdict.STATIC_REJECTED)
        self.assertFalse(outcome.eligible)
        self.assertTrue(any("source hashes differ" in reason for reason in outcome.reasons))
        self.assertTrue(any("zero-byte" in reason for reason in outcome.reasons))

    def test_noop_requires_static_review_to_pass(self) -> None:
        value = noop_request_dict()
        value["evidence"][0]["static_review"] = "not_run"
        outcome = CandidateGate().evaluate(GateRequest.from_dict(value))[0]
        self.assertEqual(outcome.verdict, GateVerdict.STATIC_REJECTED)
        self.assertTrue(any("requires passed" in reason for reason in outcome.reasons))

    def test_semantic_not_run_cannot_reach_production_safe_gain(self) -> None:
        value = request_dict("c1")
        value["evidence"][0]["semantic"] = "not_run"
        outcome = CandidateGate().evaluate(GateRequest.from_dict(value))[0]
        self.assertEqual(outcome.verdict, GateVerdict.ACCURACY_FAILED)
        self.assertFalse(outcome.eligible)

    def test_paired_lcb_and_batch_selection_are_authoritative(self) -> None:
        request = request_dict("fast", "faster")
        request["evidence"][1] = evidence_dict("faster", [70.0, 71.0, 69.0, 70.0, 72.0])
        outcomes = CandidateGate().evaluate(GateRequest.from_dict(request))
        self.assertEqual([item.verdict for item in outcomes], [GateVerdict.PRODUCTION_SAFE_GAIN] * 2)
        self.assertEqual([item.selected_as_best for item in outcomes], [False, True])
        self.assertGreater(outcomes[1].speedup_lcb, outcomes[0].speedup_lcb)
        self.assertEqual(outcomes[0].measurement_protocol, "paired_log_speedup_deterministic_bootstrap_lcb_v1")

    def test_benchmark_specialized_gain_is_preserved_but_not_selected(self) -> None:
        request = request_dict("c1")
        request["evidence"][0]["portability"] = "not_run"
        outcome = CandidateGate().evaluate(GateRequest.from_dict(request))[0]
        self.assertEqual(outcome.verdict, GateVerdict.BENCHMARK_SPECIALIZED_GAIN)
        self.assertFalse(outcome.eligible)
        self.assertFalse(outcome.selected_as_best)

    def test_unpaired_measurements_are_rejected(self) -> None:
        request = request_dict("c1")
        request["evidence"][0]["candidate_samples_ns"].pop()
        outcome = CandidateGate().evaluate(GateRequest.from_dict(request))[0]
        self.assertEqual(outcome.verdict, GateVerdict.MEASUREMENT_UNSTABLE)


class StoreTests(unittest.TestCase):
    def test_artifact_index_is_content_addressed_and_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "report.json"
            artifact.write_text('{"ok":true}\n', encoding="utf-8")
            with EpisodeStore(Path(directory) / "episodes.sqlite") as store:
                first = store.register_artifact(artifact, media_type="application/json")
                second = store.register_artifact(artifact, media_type="application/json")
                self.assertEqual(first, second)
                count = store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
                self.assertEqual(count, 1)
                with self.assertRaises(sqlite3.DatabaseError):
                    store.connection.execute("UPDATE artifacts SET content_hash=?", (HASH,))

    def test_episode_roundtrip_replays_gate_and_route(self) -> None:
        context, request, graph = finalization_inputs(request_dict("c1"))
        episode = finalize_episodes(
            context, request, graph=graph, finalized_at="2026-08-11T01:00:00Z"
        )[0]
        # Serialized episodes validate their own content hash.
        episode.__class__.from_dict(to_primitive(episode))

    def test_tampered_episode_hash_is_rejected(self) -> None:
        context, request, graph = finalization_inputs(request_dict("c1"))
        episode = finalize_episodes(context, request, graph=graph)[0]
        value = to_primitive(episode)
        value["context"]["operator"] = "tampered"
        with self.assertRaisesRegex(ContractError, "payload hash mismatch"):
            episode.__class__.from_dict(value)

    def test_forged_gate_outcome_is_rejected_even_with_recomputed_episode_hash(self) -> None:
        request = request_dict("c1")
        request["evidence"][0].update({"build": "failed", "accuracy": "not_run", "runtime": "not_run"})
        request["evidence"][0].pop("baseline_samples_ns")
        request["evidence"][0].pop("candidate_samples_ns")
        context, final_request, graph = finalization_inputs(request)
        episode = finalize_episodes(context, final_request, graph=graph)[0]
        value = to_primitive(episode)
        value["outcome"].update({
            "verdict": "production_safe_gain",
            "eligible": True,
            "selected_as_best": True,
            "utility": 999.0,
            "decision_hash": "sha256:" + "f" * 64,
        })
        value["episode_hash"] = content_hash({key: item for key, item in value.items() if key != "episode_hash"})
        with self.assertRaisesRegex(ContractError, "does not match authoritative gate evaluation"):
            episode.__class__.from_dict(value)

    def test_forged_route_is_rejected_even_after_regating_and_rehashing(self) -> None:
        context, request, graph = finalization_inputs(request_dict("c1"))
        episode = finalize_episodes(context, request, graph=graph)[0]
        value = to_primitive(episode)
        selected = value["draft"]["route"]["selected_edge_id"]
        for draft in (value["draft"], value["gate_request"]["candidates"][0]):
            candidate = next(
                item for item in draft["route"]["candidates"] if item["edge_id"] == selected
            )
            candidate["logit"] += 100.0
        forged_request = GateRequest.from_dict(value["gate_request"])
        value["outcome"] = to_primitive(CandidateGate().evaluate(forged_request)[0])
        value["episode_hash"] = content_hash({
            key: item for key, item in value.items() if key != "episode_hash"
        })
        with self.assertRaisesRegex(ContractError, "deterministic replay"):
            episode.__class__.from_dict(value)

    def test_finalization_enforces_observable_session_budgets(self) -> None:
        cases = (
            ({"candidate_limit": 0}, "candidate_limit"),
            ({"candidate_limit": 1, "build_limit": 0}, "build_limit"),
            ({"candidate_limit": 1, "timing_limit": 0}, "timing_limit"),
        )
        for budget, field in cases:
            with self.subTest(field=field):
                context, request, graph = finalization_inputs(
                    request_dict("c1"), budget=budget
                )
                with self.assertRaisesRegex(ContractError, field):
                    finalize_episodes(context, request, graph=graph)

    def test_episode_persists_complete_batch_gate_request(self) -> None:
        context, request, graph = finalization_inputs(request_dict("c1", "c2"))
        episodes = finalize_episodes(context, request, graph=graph)
        self.assertEqual([item.candidate_id for item in episodes[0].gate_request.candidates], ["c1", "c2"])
        self.assertEqual(episodes[0].gate_request.config.min_pairs, 30)
        episodes[0].__class__.from_dict(to_primitive(episodes[0]))
        with self.assertRaisesRegex(StoreError, "appended completely"):
            _require_complete_batches(episodes[:1])
        _require_complete_batches(episodes)


class GraphTests(unittest.TestCase):
    def test_seed_snapshot_and_static_prior_route(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = root / "skillgraph" / "versions" / "v0001"
        if not snapshot.exists():
            self.skipTest("seed graph is built by a parallel refactor component")
        graph, manifest = load_snapshot(snapshot)
        self.assertIsNotNone(manifest)
        context = Context.from_dict(context_dict())
        decision = route_graph(graph, context)
        self.assertEqual(decision.graph_version, "v0001")
        self.assertEqual(decision.selection_mode, "argmax")
        self.assertEqual(decision.behavior_probability, 1.0)
        self.assertAlmostEqual(sum(item.probability for item in decision.candidates), 1.0)
        self.assertIn(decision.selected_edge_id, {item.edge_id for item in decision.candidates})
        self.assertTrue(any(not item.allowed and item.mask_reasons for item in decision.candidates))

    def test_sampling_is_seeded_and_records_true_propensity(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = root / "skillgraph" / "versions" / "v0001"
        if not snapshot.exists():
            self.skipTest("seed graph is built by a parallel refactor component")
        graph, _ = load_snapshot(snapshot)
        value = context_dict()
        value["evidence"] = {"predicate_states": {"predicate.source.ub_live_bytes_near_capacity": True}}
        context = Context.from_dict(value)
        first = route_graph(graph, context, selection_mode="sample", selection_seed=42)
        second = route_graph(graph, context, selection_mode="sample", selection_seed=42)
        self.assertEqual(first, second)
        selected = next(item for item in first.candidates if item.edge_id == first.selected_edge_id)
        self.assertEqual(first.behavior_probability, selected.probability)
        self.assertLess(first.behavior_probability, 1.0)

    def test_unsubstantiated_external_mechanism_proposal_is_ignored(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = root / "skillgraph" / "versions" / "v0001"
        if not snapshot.exists():
            self.skipTest("seed graph is built by a parallel refactor component")
        graph, _ = load_snapshot(snapshot)
        value = context_dict()
        value["evidence"] = {"active_mechanisms": ["mechanism.scalar_control_hot_loop"]}
        decision = route_graph(graph, Context.from_dict(value))
        self.assertEqual(decision.selected_mechanism_id, "mechanism.unknown_unresolved")
        scalar_candidates = [item for item in decision.candidates if item.source_id == "mechanism.scalar_control_hot_loop"]
        self.assertTrue(scalar_candidates)
        self.assertTrue(all(not item.allowed for item in scalar_candidates))

    def test_argmax_contract_rejects_softmax_as_fake_propensity(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = root / "skillgraph" / "versions" / "v0001"
        if not snapshot.exists():
            self.skipTest("seed graph is built by a parallel refactor component")
        graph, _ = load_snapshot(snapshot)
        value = context_dict()
        value["evidence"] = {"predicate_states": {"predicate.source.ub_live_bytes_near_capacity": True}}
        decision = route_graph(graph, Context.from_dict(value))
        serialized = to_primitive(decision)
        selected = next(item for item in serialized["candidates"] if item["edge_id"] == serialized["selected_edge_id"])
        serialized["behavior_probability"] = selected["probability"]
        with self.assertRaisesRegex(ContractError, "argmax behavior probability must be 1"):
            CandidateDraft.from_dict({**draft_dict("c1"), "route": serialized})

    def test_predicate_preconditions_keep_unknown_distinct_from_false(self) -> None:
        root = Path(__file__).resolve().parents[1]
        snapshot = root / "skillgraph" / "versions" / "v0001"
        if not snapshot.exists():
            self.skipTest("seed graph is built by a parallel refactor component")
        graph, _ = load_snapshot(snapshot)
        gated = next(
            edge for edge in graph["edges"]
            if edge["edge_type"] == "problem_to_skill_prior" and edge["hard_preconditions"]
        )
        predicate = gated["hard_preconditions"][0]["predicate"]
        value = context_dict()
        value["evidence"] = {
            "active_mechanisms": [gated["source"]],
            "predicate_states": {predicate: True},
        }
        decision = route_graph(graph, Context.from_dict(value))
        candidate = next(item for item in decision.candidates if item.edge_id == gated["id"])
        self.assertGreater(candidate.probability, 0.0)


if __name__ == "__main__":
    unittest.main()
