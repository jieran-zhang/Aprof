from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "compile_seed_graph.py"
SPEC = importlib.util.spec_from_file_location("compile_seed_graph", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
COMPILER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPILER)


class SeedGraphCompilerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.source_dir = REPO_ROOT / "skillgraph" / "source"
        self.snapshot_dir = REPO_ROOT / "skillgraph" / "versions" / "v0001"

    def test_checked_in_snapshot_is_current_and_internally_consistent(self) -> None:
        artifacts = COMPILER.materialize_snapshot(
            self.source_dir, self.snapshot_dir, REPO_ROOT, check=True
        )
        graph = json.loads(artifacts["graph.json"])
        manifest = json.loads(artifacts["manifest.json"])
        checksums = json.loads(artifacts["checksums.json"])

        self.assertEqual(graph["graph_version"], "v0001")
        self.assertEqual(len(graph["anchors"]), 6)
        self.assertTrue(all(node["kind"] == "facet" for node in graph["anchors"]))
        self.assertTrue(all(node["selectable"] is False for node in graph["anchors"]))
        self.assertIn(
            "mechanism.unknown_unresolved", {node["id"] for node in graph["mechanisms"]}
        )
        self.assertIn(
            "transformation.noop", {node["id"] for node in graph["transformations"]}
        )
        self.assertTrue(all("evaluation" in node for node in graph["predicates"]))
        self.assertEqual(
            graph["prior_semantics"]["score_type"], "uncalibrated_expert_score"
        )
        self.assertEqual(
            graph["prior_semantics"]["interpretation"],
            "ordinal_initial_ranking_only",
        )
        self.assertIs(graph["prior_semantics"]["calibrated_probability"], False)
        self.assertEqual(graph["prior_semantics"]["temperature"], 1.0)
        trainable_priors = [
            edge
            for edge in graph["edges"]
            if edge["edge_type"] == "problem_to_skill_prior"
        ]
        self.assertTrue(trainable_priors)
        self.assertTrue(
            all(
                edge["prior_status"] == "expert_seed_unverified"
                for edge in trainable_priors
            )
        )
        self.assertEqual(manifest["graph_sha256"], hashlib.sha256(artifacts["graph.json"]).hexdigest())
        for filename, expected_hash in checksums["files"].items():
            self.assertEqual(hashlib.sha256(artifacts[filename]).hexdigest(), expected_hash)

    def test_compilation_is_byte_deterministic(self) -> None:
        first = COMPILER.build_snapshot(self.source_dir, REPO_ROOT)
        second = COMPILER.build_snapshot(self.source_dir, REPO_ROOT)
        self.assertEqual(first, second)

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output_a = root / "a"
            output_b = root / "b"
            COMPILER.materialize_snapshot(self.source_dir, output_a, REPO_ROOT)
            COMPILER.materialize_snapshot(self.source_dir, output_b, REPO_ROOT)
            self.assertEqual(
                {path.name: path.read_bytes() for path in output_a.iterdir()},
                {path.name: path.read_bytes() for path in output_b.iterdir()},
            )

    def test_existing_snapshot_cannot_be_mutated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copied_source = root / "source"
            output = root / "v0001"
            shutil.copytree(self.source_dir, copied_source)
            COMPILER.materialize_snapshot(copied_source, output, REPO_ROOT)

            mechanisms_path = copied_source / "mechanisms.json"
            mechanisms = json.loads(mechanisms_path.read_text(encoding="utf-8"))
            mechanisms["mechanisms"][0]["description"] += " changed"
            mechanisms_path.write_text(
                json.dumps(mechanisms, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                COMPILER.GraphCompileError, "publish a new graph version"
            ):
                COMPILER.materialize_snapshot(copied_source, output, REPO_ROOT)

    def test_seed_prior_excludes_benchmark_generation_and_fast_gelu_history(self) -> None:
        graph = json.loads(
            (self.snapshot_dir / "graph.json").read_text(encoding="utf-8")
        )
        provenance_paths = {
            record["path"].lower()
            for collection in (
                "anchors",
                "predicates",
                "mechanisms",
                "transformations",
                "edges",
            )
            for item in graph[collection]
            for record in item["provenance"]
        }
        self.assertFalse(any("inject" in path for path in provenance_paths))
        self.assertFalse(any("fast_gelu" in path for path in provenance_paths))

    def test_unverified_status_is_mandatory_for_every_trainable_prior(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copied_source = Path(temp) / "source"
            shutil.copytree(self.source_dir, copied_source)
            edge_path = copied_source / "edges.json"
            edge_source = json.loads(edge_path.read_text(encoding="utf-8"))
            prior = next(
                edge
                for edge in edge_source["edges"]
                if edge["edge_type"] == "problem_to_skill_prior"
            )
            del prior["prior_status"]
            edge_path.write_text(
                json.dumps(edge_source, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                COMPILER.GraphCompileError, "must remain explicitly unverified"
            ):
                COMPILER.build_snapshot(copied_source, REPO_ROOT)

    def test_provenance_files_and_slices_are_bound_into_source_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copied_source = root / "skillgraph" / "source"
            shutil.copytree(self.source_dir, copied_source)
            shutil.copytree(REPO_ROOT / "skills" / "aprof", root / "skills" / "aprof")

            first = COMPILER.build_snapshot(copied_source, root)
            first_manifest = json.loads(first["manifest.json"])
            first_checksums = json.loads(first["checksums.json"])
            provenance = first_checksums["provenance_sources"]
            cited_path = "skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md"
            self.assertIn(cited_path, provenance)
            self.assertRegex(provenance[cited_path]["file_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(provenance[cited_path]["slices"])
            self.assertTrue(
                all(len(digest) == 64 for digest in provenance[cited_path]["slices"].values())
            )

            output = root / "skillgraph" / "versions" / "v0001"
            COMPILER.materialize_snapshot(copied_source, output, root)
            cited_file = root / cited_path
            cited_file.write_text(
                cited_file.read_text(encoding="utf-8") + "\nprovenance tamper\n",
                encoding="utf-8",
            )
            second = COMPILER.build_snapshot(copied_source, root)
            second_manifest = json.loads(second["manifest.json"])
            self.assertNotEqual(
                first_manifest["source_sha256"], second_manifest["source_sha256"]
            )
            with self.assertRaisesRegex(COMPILER.GraphCompileError, "snapshot check failed"):
                COMPILER.materialize_snapshot(copied_source, output, root, check=True)

    def test_provenance_path_cannot_escape_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            copied_source = Path(temp) / "source"
            shutil.copytree(self.source_dir, copied_source)
            anchors_path = copied_source / "anchors.json"
            anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
            anchors["anchors"][0]["provenance"][0]["path"] = "../outside.md"
            anchors_path.write_text(
                json.dumps(anchors, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                COMPILER.GraphCompileError, "normalized and repository-relative"
            ):
                COMPILER.build_snapshot(copied_source, REPO_ROOT)


if __name__ == "__main__":
    unittest.main()
