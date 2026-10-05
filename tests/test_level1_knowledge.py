from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("level1_knowledge", ROOT / "scripts/prepare_level1_knowledge.py")
assert SPEC and SPEC.loader
knowledge = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(knowledge)


class Level1KnowledgeTest(unittest.TestCase):
    def test_local_cases_are_exactly_twenty_and_json_finite(self):
        for operator in knowledge.OPERATORS:
            cases = knowledge.local_cases(ROOT / "benchmarks/cannbench/operators" / operator / "scripts/cases.py")
            self.assertEqual(20, len(cases))
            json.dumps(knowledge.json_safe(cases), allow_nan=False)

    def test_literal_parser_rejects_executable_python(self):
        with self.assertRaises(ValueError):
            knowledge.literal(ast.parse("__import__('os').system('echo forbidden')", mode="eval").body)

    def test_split_membership_refuses_sealed_and_cross_split(self):
        for operator, split in (("swi_glu", "test"), ("gelu", "train"), ("foreach_norm", "validation")):
            with self.assertRaises(ValueError):
                knowledge.verify_split(ROOT, operator, split)

    def test_seven_upstream_case_matrices_and_thresholds_match(self):
        if not (ROOT / "third_party/cann-bench/tasks").is_dir():
            self.skipTest("cann-bench has not been restored")
        for operator in knowledge.OPERATORS:
            report = knowledge.verify_task_parity(ROOT, operator)
            self.assertEqual([], report["mismatches"], operator)
            self.assertFalse(report["precision_contract"]["upstream_checker_equivalent"])

    def test_resolver_supports_registry_alias_and_rejects_escape(self):
        expected = ROOT / "skills/aprof/diagnosis/SKILL.md"
        self.assertEqual(expected, knowledge.resolve_reference(ROOT, "aprof-ascendc-diagnosis"))
        with self.assertRaises(ValueError):
            knowledge.resolve_reference(ROOT, "../../etc/passwd")

    def test_actual_reads_are_separate_from_manifest_and_attested(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(knowledge, "dependency_state", return_value={}), \
                mock.patch.object(knowledge, "verify_task_parity", return_value={"mismatches": [], "fixture": "read-attestation-unit-test"}):
            out = Path(tmp) / "knowledge"
            manifest = knowledge.prepare_manifest(ROOT, "foreach_norm", "train", run_id="test-run", session_id="test-session", output_dir=out)
            reads = out / "knowledge_reads.jsonl"
            self.assertEqual("", reads.read_text())
            content = knowledge.read_reference(out / "manifest.json", "ascendc-aprof-workflow", "start workflow", role="optimizer")
            self.assertIn("# AProf Trainable Workflow", content)
            knowledge.read_reference(out / "manifest.json", "ascendc-aprof-diagnosis", "form source hypothesis")
            records = reads.read_text().splitlines(keepends=True)
            self.assertEqual(2, len(records))
            knowledge.verify_read_records(records, manifest["manifest_sha256"])
            records[0] = records[0].replace("start workflow", "altered purpose")
            with self.assertRaises(ValueError):
                knowledge.verify_read_records(records, manifest["manifest_sha256"])
            with self.assertRaises(ValueError):
                knowledge.prepare_manifest(ROOT, "foreach_norm", "train", run_id="test-run", session_id="test-session", output_dir=out)

    def test_tampered_manifest_is_refused_before_returning_content(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(knowledge, "dependency_state", return_value={}), \
                mock.patch.object(knowledge, "verify_task_parity", return_value={"mismatches": [], "fixture": "manifest-integrity-unit-test"}):
            out = Path(tmp) / "knowledge"
            knowledge.prepare_manifest(ROOT, "gelu", "validation", run_id="test-run", session_id="validation", output_dir=out)
            path = out / "manifest.json"
            manifest = json.loads(path.read_text())
            manifest["split"] = "train"
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "manifest hash mismatch"):
                knowledge.read_reference(path, "ascendc-aprof-workflow", "invalid read")


if __name__ == "__main__":
    unittest.main()
