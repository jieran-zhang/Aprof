from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from aprof_runtime.contracts import (
    CandidateDraft,
    CandidateEpisode,
    Context,
    GateOutcome,
    GateRequest,
    HandlerAttempt,
)
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.errors import ContractError
from aprof_runtime.graph import load_snapshot, route_graph
from aprof_runtime.jsonio import to_primitive
from aprof_runtime.policy import load_policy_checkpoint, train_fixed_graph_policy


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
GRAPH = ROOT / "skillgraph" / "versions" / "v0001"


def _schema_registry() -> tuple[dict[str, dict], Registry]:
    documents = {
        path.name: json.loads(path.read_text(encoding="utf-8"))
        for path in SCHEMAS.glob("*.schema.json")
    }
    registry = Registry().with_resources((
        document["$id"], Resource.from_contents(document)
    ) for document in documents.values())
    return documents, registry


def _runtime_values() -> dict[str, dict]:
    graph, _ = load_snapshot(GRAPH)
    context = Context.from_dict({
        "schema_version": "1.0.0",
        "task_id": "schema-parity",
        "operator": "demo",
        "hardware_fingerprint": "ascend:test",
        "workload": {"shape": [1024]},
        "budget": {"candidate_limit": 1},
        "evidence": {"predicate_states": {"predicate.profile.scalar_hot": True}},
    })
    route = route_graph(graph, context)
    selected = next(item for item in route.candidates if item.edge_id == route.selected_edge_id)
    digest = "sha256:" + "a" * 64
    draft = {
        "schema_version": "1.0.0",
        "candidate_id": "candidate-1",
        "session_id": "session-1",
        "route": to_primitive(route),
        "transformation_id": selected.target_id,
        "transformation_version": "1.0.0",
        "producer_hashes": {"model": digest, "prompt": digest, "agent": digest},
        "source_hashes": {"baseline": digest, "candidate": digest},
        "patch_artifact_hash": digest,
        "parameters": {},
        "proposed_by": "agent:test",
        "created_at": "2026-08-11T00:00:00Z",
    }
    samples = [100.0 + (index % 3) * 0.1 for index in range(30)]
    evidence = {
        "candidate_id": "candidate-1",
        "static_review": "passed", "build": "passed", "accuracy": "passed",
        "runtime": "passed", "semantic": "passed", "scope": "passed",
        "portability": "passed",
        "baseline_samples_ns": samples,
        "candidate_samples_ns": [value * 0.8 for value in samples],
        "mechanism_alignment": True,
        "heldout_regressions": [0.0],
        "artifacts": {
            "build_log": digest, "accuracy_report": digest, "measurement_report": digest,
        },
    }
    request = GateRequest.from_dict({
        "schema_version": "1.0.0", "candidates": [draft], "evidence": [evidence],
        "config": {"bootstrap_resamples": 100},
    })
    episode = finalize_episodes(
        context, request, graph=graph,
        finalized_at="2026-08-11T01:00:00Z", runtime_build="aprof-runtime/test",
    )[0]
    checkpoint = train_fixed_graph_policy(graph, [], policy_version="schema-test")
    handler_attempt = HandlerAttempt.from_dict({
        "schema_version": "1.0.0",
        "attempt_id": "attempt-1",
        "candidate_id": "candidate-1",
        "session_id": "session-1",
        "graph_version": "v0001",
        "selected_edge_id": route.selected_edge_id,
        "mechanism_id": route.selected_mechanism_id,
        "transformation_id": selected.target_id,
        "handler_id": "handler.vectorize.masked-main-path",
        "handler_version": "1.0.0",
        "handler_producer_hash": digest,
        "parameters": {"tail_mode": "mask"},
        "context_features": {"workload_class": "normal", "dtype": "float16"},
        "parent_candidate_id": None,
        "previous_verdict": None,
        "decision_type": "initial",
        "decision_reason": "first legal handler for the selected transformation",
        "created_at": "2026-08-11T00:00:00Z"
    })
    return {
        "context.schema.json": to_primitive(context),
        "candidate-draft.schema.json": to_primitive(episode.draft),
        "gate-request.schema.json": to_primitive(request),
        "gate-outcome.schema.json": to_primitive(episode.outcome),
        "candidate-episode.schema.json": to_primitive(episode),
        "policy-checkpoint.schema.json": to_primitive(checkpoint),
        "handler-attempt.schema.json": to_primitive(handler_attempt),
    }


class SchemaModelParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.documents, cls.registry = _schema_registry()
        cls.values = _runtime_values()

    def _assert_schema_accepts(self, name: str, value: dict) -> None:
        Draft202012Validator(
            self.documents[name], registry=self.registry
        ).validate(value)

    def _assert_schema_rejects(self, name: str, value: dict) -> None:
        errors = list(Draft202012Validator(
            self.documents[name], registry=self.registry
        ).iter_errors(value))
        self.assertTrue(errors, f"{name} unexpectedly accepted invalid corpus value")

    def test_every_python_emitted_contract_is_schema_valid(self) -> None:
        for name, value in self.values.items():
            with self.subTest(schema=name):
                self._assert_schema_accepts(name, value)

    def test_shared_invalid_corpus_is_rejected_by_schema_and_python(self) -> None:
        draft = copy.deepcopy(self.values["candidate-draft.schema.json"])
        draft["route"]["behavior_probability"] = 0.5
        self._assert_schema_rejects("candidate-draft.schema.json", draft)
        with self.assertRaises(ContractError):
            CandidateDraft.from_dict(draft)

        outcome = copy.deepcopy(self.values["gate-outcome.schema.json"])
        outcome["measurement_protocol"] = "agent_claimed_fast_v1"
        self._assert_schema_rejects("gate-outcome.schema.json", outcome)
        with self.assertRaises(ContractError):
            GateOutcome.from_dict(outcome)

        policy = copy.deepcopy(self.values["policy-checkpoint.schema.json"])
        del policy["config"]["max_abs_bias"]
        self._assert_schema_rejects("policy-checkpoint.schema.json", policy)
        with self.assertRaises(ContractError):
            load_policy_checkpoint(policy)

        episode = copy.deepcopy(self.values["candidate-episode.schema.json"])
        episode["agent_verdict"] = "gain"
        self._assert_schema_rejects("candidate-episode.schema.json", episode)
        with self.assertRaises(ContractError):
            CandidateEpisode.from_dict(episode)

        handler = copy.deepcopy(self.values["handler-attempt.schema.json"])
        handler["decision_type"] = "sibling_handler"
        self._assert_schema_rejects("handler-attempt.schema.json", handler)
        with self.assertRaises(ContractError):
            HandlerAttempt.from_dict(handler)

        handler = copy.deepcopy(self.values["handler-attempt.schema.json"])
        handler["created_at"] = "not-a-time"
        with self.assertRaises(ContractError):
            HandlerAttempt.from_dict(handler)


if __name__ == "__main__":
    unittest.main()
