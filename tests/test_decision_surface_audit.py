from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/audit_skillgraph_decisions.py"
SPEC = importlib.util.spec_from_file_location("audit_skillgraph_decisions", SCRIPT)
assert SPEC and SPEC.loader
audit_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit_tool)


class DecisionSurfaceAuditTest(unittest.TestCase):
    def test_v0001_is_reported_as_fixed_skeleton(self) -> None:
        graph = audit_tool._load_graph(ROOT / "skillgraph/versions/v0001")
        report = audit_tool.audit(graph)
        self.assertEqual(18, report["counts"]["predicates"])
        self.assertEqual(22, report["counts"]["trainable_prior_edges"])
        self.assertEqual([], report["formal_predicate_to_problem"]["multiple_problem_predicates"])
        self.assertEqual(
            "formal_predicate_not_raw_profiler_symptom",
            report["formal_predicate_to_problem"]["input_unit"],
        )
        self.assertEqual([], report["problem_to_action"]["multiple_positive_action_problems"])
        self.assertEqual([], report["context_conditioning"]["direct_context_conditioned_edge_ids"])
        self.assertEqual([], report["failure_recovery"]["recovery_edge_types"])
        self.assertFalse(report["substantive_decision_graph"])
        self.assertEqual(
            "fixed_graph_edge_ranking_with_handler_parameter_trace_collection",
            report["recommended_experiment_scope"],
        )

    def test_topology_alone_never_claims_empirical_decision_graph(self) -> None:
        graph = audit_tool._load_graph(ROOT / "skillgraph/versions/v0001")
        graph["handlers"] = [
            {"id": "handler.a", "transformation_id": "transformation.a"},
            {"id": "handler.b", "transformation_id": "transformation.a"},
        ]
        graph["edges"].extend([
            {
                "id": "edge.fake.context",
                "edge_type": "problem_to_skill_prior",
                "source": "mechanism.unknown_unresolved",
                "target": "transformation.vectorize_scalar_loop",
                "hard_preconditions": [{"path": "workload.shape", "op": "eq", "value": [1]}],
            },
            {"id": "edge.fake.recovery", "edge_type": "documentation_transition"},
        ])
        report = audit_tool.audit(graph)
        self.assertFalse(report["empirical_trace_support_audited"])
        self.assertFalse(report["substantive_decision_graph"])
        self.assertEqual([], report["failure_recovery"]["recovery_edge_types"])


if __name__ == "__main__":
    unittest.main()
