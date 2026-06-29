from __future__ import annotations

import unittest

from aprof.agents.diagnosis.rules import diagnose_label
from aprof.core.models import CaseEvidence


class DiagnosisRulesTests(unittest.TestCase):
    def test_blockdim_label(self) -> None:
        evidence = CaseEvidence(
            metadata={"variant": "inject_blockdim", "blockdim": 1, "output_elements": 256},
            source={},
            artifacts={"has_trace": True},
        )
        label, confidence, _ = diagnose_label(evidence)
        self.assertEqual(label, "blockdim_too_small")
        self.assertEqual(confidence, "medium")

    def test_tail_label(self) -> None:
        evidence = CaseEvidence(
            metadata={"variant": "inject_tail", "tail_length": 1},
            source={"inject_tail": True},
            artifacts={"has_trace": True},
        )
        label, _, _ = diagnose_label(evidence)
        self.assertEqual(label, "tail_inefficient")


if __name__ == "__main__":
    unittest.main()
