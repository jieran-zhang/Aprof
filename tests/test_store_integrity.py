from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from aprof_runtime.cli import _parser, run
from aprof_runtime.contracts import Context, EMPTY_ARTIFACT_SHA256, GateRequest
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.errors import StoreError
from aprof_runtime.graph import route_graph
from aprof_runtime.jsonio import to_primitive
from aprof_runtime.policy import iter_episode_store
from aprof_runtime.store import EpisodeStore


_GRAPH_PATH = Path(__file__).resolve().parents[1] / "skillgraph" / "versions" / "v0001" / "graph.json"


def _graph() -> dict:
    return json.loads(_GRAPH_PATH.read_text(encoding="utf-8"))


def _context(candidate_id: str, *, noop: bool = False) -> Context:
    return Context.from_dict({
        "schema_version": "1.0.0",
        "task_id": f"task-{candidate_id}",
        "operator": "demo",
        "hardware_fingerprint": "ascend:test",
        "workload": {"shape": [1024]},
        "budget": {"candidate_limit": 1},
        "evidence": {"predicate_states": {} if noop else {"predicate.profile.scalar_hot": True}},
    })


def _episode(
    digest: str,
    candidate_id: str = "candidate-1",
    *,
    session_id: str | None = None,
):
    context = _context(candidate_id)
    graph = _graph()
    route = route_graph(graph, context)
    selected = next(item for item in route.candidates if item.edge_id == route.selected_edge_id)
    samples = [100.0 + (index % 3) for index in range(30)]
    candidate_samples = [80.0 + (index % 3) for index in range(30)]
    draft = {
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "session_id": session_id or f"session-{candidate_id}",
        "route": to_primitive(route),
        "transformation_id": selected.target_id,
        "transformation_version": "1.0.0",
        "producer_hashes": {"model": "unknown", "prompt": "unknown", "agent": "unknown"},
        "source_hashes": {"baseline": digest, "candidate": digest},
        "patch_artifact_hash": digest,
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
        "baseline_samples_ns": samples,
        "candidate_samples_ns": candidate_samples,
        "mechanism_alignment": True,
        "heldout_regressions": [0.0],
        "artifacts": {
            "build_log": digest,
            "accuracy_report": digest,
            "measurement_report": digest,
        },
    }
    request = GateRequest.from_dict({
        "schema_version": "1.0.0",
        "candidates": [draft],
        "evidence": [evidence],
        "config": {"bootstrap_resamples": 100},
    })
    return finalize_episodes(
        context, request, graph=graph,
        finalized_at="2026-08-11T01:00:00Z",
        runtime_build="aprof-runtime/test",
    )[0]


def _noop_episode(source_digest: str, candidate_id: str = "noop"):
    context = _context(candidate_id, noop=True)
    graph = _graph()
    route = route_graph(graph, context)
    selected = next(item for item in route.candidates if item.edge_id == route.selected_edge_id)
    if selected.target_id != "transformation.noop":
        raise AssertionError("seed graph's unresolved route must select NOOP")
    draft = {
        "schema_version": "1.0.0",
        "candidate_id": candidate_id,
        "session_id": f"session-{candidate_id}",
        "route": to_primitive(route),
        "transformation_id": "transformation.noop",
        "transformation_version": "1.0.0",
        "producer_hashes": {"model": "unknown", "prompt": "unknown", "agent": "unknown"},
        "source_hashes": {"baseline": source_digest, "candidate": source_digest},
        "patch_artifact_hash": EMPTY_ARTIFACT_SHA256,
        "parameters": {"no_mutation": True, "reason": "budget exhausted"},
        "proposed_by": "agent:test",
        "created_at": "2026-08-11T00:00:00Z",
    }
    evidence = {
        "candidate_id": candidate_id,
        "static_review": "passed",
        "build": "not_run",
        "accuracy": "not_run",
        "runtime": "not_run",
        "semantic": "not_run",
        "scope": "not_run",
        "portability": "not_run",
        "mechanism_alignment": None,
        "heldout_regressions": [],
        "artifacts": {},
    }
    request = GateRequest.from_dict({
        "schema_version": "1.0.0",
        "candidates": [draft],
        "evidence": [evidence],
        "config": {},
    })
    return finalize_episodes(
        context, request, graph=graph,
        finalized_at="2026-08-11T01:00:00Z",
        runtime_build="aprof-runtime/test",
    )[0]


class ContentAddressedStoreTests(unittest.TestCase):
    def test_artifact_is_copied_and_source_mutation_does_not_change_cas(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "report.json"
            source.write_bytes(b'{"ok":true}\n')
            with EpisodeStore(root / "episodes.sqlite") as store:
                digest = store.register_artifact(source, media_type="application/json")
                object_path = store.object_path(digest)
                self.assertNotEqual(object_path, source)
                self.assertEqual(object_path.read_bytes(), b'{"ok":true}\n')
                source.write_bytes(b"mutated")
                self.assertEqual(store.verify_artifact(digest), object_path)
                self.assertEqual(object_path.read_bytes(), b'{"ok":true}\n')

    def test_missing_or_corrupt_cas_object_rejects_episode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "artifact"
            source.write_bytes(b"evidence")
            with EpisodeStore(root / "episodes.sqlite") as store:
                digest = store.register_artifact(source)
                episode = _episode(digest)
                store.object_path(digest).unlink()
                with self.assertRaisesRegex(StoreError, "missing"):
                    store.append(episode)
                store.register_artifact(source)
                store.object_path(digest).write_bytes(b"corrupt")
                with self.assertRaisesRegex(StoreError, "content does not match"):
                    store.append(episode)
                self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0], 0)

    def test_append_many_is_atomic_and_chain_is_verified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "artifact"
            source.write_bytes(b"shared artifact")
            with EpisodeStore(root / "episodes.sqlite") as store:
                digest = store.register_artifact(source)
                first = _episode(digest, "first")
                # The duplicate second value violates unique episode/candidate ids
                # after the first insert.  The complete transaction must roll back.
                with self.assertRaises(StoreError):
                    store.append_many((first, first))
                self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0], 0)
                self.assertEqual(store.connection.execute("SELECT COUNT(*) FROM episode_chain").fetchone()[0], 0)

                second = _episode(digest, "second")
                self.assertEqual(store.append_many((first, second)), (1, 2))
                head = store.verify_integrity()
                self.assertTrue(head.startswith("sha256:"))
                self.assertEqual(len(list(store.iter_payloads())), 2)

    def test_chain_tables_are_append_only_and_corruption_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "artifact"
            source.write_bytes(b"artifact")
            with EpisodeStore(root / "episodes.sqlite") as store:
                digest = store.register_artifact(source)
                store.append(_episode(digest))
                with self.assertRaises(sqlite3.DatabaseError):
                    store.connection.execute(
                        "UPDATE episode_chain SET chain_hash=?", ("sha256:" + "f" * 64,)
                    )
                store.connection.rollback()
                store.connection.execute("DROP TRIGGER episode_chain_no_update")
                store.connection.execute(
                    "UPDATE episode_chain SET chain_hash=?", ("sha256:" + "f" * 64,)
                )
                store.connection.commit()
                with self.assertRaisesRegex(StoreError, "invalid chain hash"):
                    store.verify_integrity()
                with self.assertRaisesRegex(StoreError, "invalid chain hash"):
                    list(iter_episode_store(root / "episodes.sqlite"))

    def test_session_budget_is_cumulative_across_append_calls(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "artifact"
            source.write_bytes(b"artifact")
            with EpisodeStore(root / "episodes.sqlite") as store:
                digest = store.register_artifact(source)
                store.append(_episode(digest, "budget-1", session_id="shared-session"))
                with self.assertRaisesRegex(StoreError, "exceeds candidate_limit"):
                    store.append(_episode(digest, "budget-2", session_id="shared-session"))
                self.assertEqual(
                    store.connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0], 1
                )

    def test_verified_noop_requires_real_identical_source_and_empty_patch_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.snapshot"
            source.write_bytes(b"source tree manifest")
            empty = root / "empty.patch"
            empty.write_bytes(b"")
            with EpisodeStore(root / "episodes.sqlite") as store:
                source_digest = store.register_artifact(source)
                empty_digest = store.register_artifact(empty)
                self.assertEqual(empty_digest, EMPTY_ARTIFACT_SHA256)
                sequence = store.append(_noop_episode(source_digest))
                self.assertEqual(sequence, 1)
                self.assertEqual(store.verify_integrity(), store.connection.execute(
                    "SELECT chain_hash FROM episode_chain WHERE sequence_id=1"
                ).fetchone()[0])

    def test_cli_can_verify_artifacts_and_episode_chain(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store_path = root / "episodes.sqlite"
            source = root / "artifact"
            source.write_bytes(b"artifact")
            with EpisodeStore(store_path) as store:
                digest = store.register_artifact(source)
                store.append(_episode(digest))
            artifact_result = run(_parser().parse_args([
                "artifact", "verify", "--store", str(store_path),
                "--content-hash", digest,
            ]))
            self.assertTrue(artifact_result["valid"])
            episode_result = run(_parser().parse_args([
                "episode", "verify", "--store", str(store_path),
            ]))
            self.assertTrue(episode_result["valid"])
            self.assertEqual(episode_result["episode_count"], 1)


if __name__ == "__main__":
    unittest.main()
