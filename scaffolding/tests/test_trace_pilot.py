from __future__ import annotations

from aprof_layout import skill_lib

import importlib.util
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from aprof_runtime.contracts import Context, RouteDecision
from aprof_runtime.jsonio import file_hash
from aprof_runtime.store import EpisodeStore


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scaffolding/collection/scripts" / "prepare_trace_pilot.py"
SPEC = importlib.util.spec_from_file_location("prepare_trace_pilot", SCRIPT)
assert SPEC and SPEC.loader
TRACE_PILOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TRACE_PILOT)


def pilot_config(*, producer_artifacts: dict[str, str] | None = None) -> dict:
    value = {
        "schema_version": "1.0.0",
        "run_id": "test-pilot-001",
        "split_version": "v0001",
        "graph": "skillgraph/versions/v0001",
        "tasks": [{
            "task_id": "exp-natural-001",
            "split": "train",
            "operator": "exp",
            "op_dir": "scaffolding/benchmarks/cannbench/operators/exp",
            "hardware_fingerprint": "ascend:test:cann-test",
            "origin": "natural",
            "lineage_id": "exp-natural-v1",
            "sentinel_case_ids": [1, 8, 14, 20],
            "budget": {
                "candidate_limit": 3,
                "build_limit": 3,
                "timing_limit": 2,
                "full_profile_limit": 1,
            },
            "selection": {"mode": "argmax", "seed": None},
            "evidence": {"predicate_states": {}},
            "device": 0,
            "build_jobs": 2,
        }],
    }
    if producer_artifacts is not None:
        value["producer_artifacts"] = producer_artifacts
    return value


class TracePilotTest(unittest.TestCase):
    def test_source_snapshot_is_deterministic_and_excludes_generated_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "kernel.asc").write_text("kernel v1\n", encoding="utf-8")
            (source / "nested").mkdir()
            (source / "nested" / "host.asc").write_text("host\n", encoding="utf-8")
            (source / "build").mkdir()
            (source / "build" / "generated.bin").write_bytes(b"first")

            first = TRACE_PILOT.create_source_snapshot(
                source, root / "first.tar", root_label="demo"
            )
            (source / "build" / "generated.bin").write_bytes(b"changed")
            second = TRACE_PILOT.create_source_snapshot(
                source, root / "second.tar", root_label="demo"
            )
            self.assertEqual(first["sha256"], second["sha256"])
            self.assertEqual((root / "first.tar").read_bytes(), (root / "second.tar").read_bytes())

            with tarfile.open(root / "first.tar") as archive:
                names = archive.getnames()
                manifest = json.load(archive.extractfile("APROF_SOURCE_SNAPSHOT.json"))
            self.assertEqual(
                ["APROF_SOURCE_SNAPSHOT.json", "source/kernel.asc", "source/nested/host.asc"],
                names,
            )
            self.assertEqual(2, len(manifest["files"]))

            (source / "kernel.asc").write_text("kernel v2\n", encoding="utf-8")
            third = TRACE_PILOT.create_source_snapshot(
                source, root / "third.tar", root_label="demo"
            )
            self.assertNotEqual(first["sha256"], third["sha256"])

    def test_prepare_creates_split_store_context_route_and_cas_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            producers: dict[str, str] = {}
            for role in TRACE_PILOT.PRODUCER_ROLES:
                path = root / f"{role}.identity"
                path.write_text(f"{role}-identity-v1\n", encoding="utf-8")
                producers[role] = str(path)

            result = TRACE_PILOT.prepare(
                pilot_config(producer_artifacts=producers), root / "runs"
            )
            run_dir = Path(result["run_directory"])
            manifest = json.loads(Path(result["manifest"]).read_text(encoding="utf-8"))
            task = manifest["tasks"][0]
            context = Context.from_dict(json.loads(Path(task["context"]["path"]).read_text()))
            route = RouteDecision.from_dict(json.loads(Path(task["route"]["path"]).read_text()))

            self.assertEqual("exp", context.operator)
            self.assertEqual(list(range(1, 21)), context.workload["acceptance_case_ids"])
            self.assertEqual("mechanism.unknown_unresolved", route.selected_mechanism_id)
            self.assertEqual("transformation.noop", next(
                item.target_id for item in route.candidates
                if item.edge_id == route.selected_edge_id
            ))
            self.assertFalse(any("producer artifacts are missing" in item for item in manifest["warnings"]))
            self.assertNotIn("unknown", set(manifest["producer_hashes"].values()))
            self.assertFalse(manifest["dataset"]["sealed_test_allowed"])

            store_path = Path(manifest["stores"]["train"])
            with EpisodeStore(store_path) as store:
                self.assertEqual("sha256:" + "0" * 64, store.verify_integrity())
                self.assertEqual(5, store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
                baseline_hash = task["baseline_snapshot"]["sha256"]
                self.assertEqual(baseline_hash, file_hash(store.verify_artifact(baseline_hash)))

            next_commands = json.loads(
                (run_dir / "tasks" / "exp-natural-001" / "next-commands.json").read_text()
            )
            self.assertEqual(str(skill_lib() / "runtime/src"), next_commands["environment"]["PYTHONPATH"])
            self.assertIn("dry_run_baseline_stages", next_commands["commands"])

    def test_missing_producers_are_explicitly_exploratory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = TRACE_PILOT.prepare(pilot_config(), Path(directory) / "runs")
            manifest = result["value"]
            self.assertEqual(
                {"model": "unknown", "prompt": "unknown", "agent": "unknown"},
                manifest["producer_hashes"],
            )
            self.assertTrue(any("default policy training will skip" in item for item in manifest["warnings"]))

    def test_sealed_test_tasks_are_rejected(self) -> None:
        value = pilot_config()
        value["tasks"][0]["split"] = "test"
        with self.assertRaisesRegex(ValueError, "sealed test is forbidden"):
            TRACE_PILOT._validate_config(value)

    def test_existing_run_directory_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "runs"
            (root / "test-pilot-001").mkdir(parents=True)
            with self.assertRaisesRegex(ValueError, "refusing to overwrite"):
                TRACE_PILOT.prepare(pilot_config(), root)


if __name__ == "__main__":
    unittest.main()
