import unittest

from aprof.skill_rl.episode_adapter import adapt_fixture_a, adapt_fixture_b
from aprof.skill_rl.splits import demo_dual_fixture_split
from aprof.skill_rl.trainer import run_offline_round


class TestSkillRlTrainer(unittest.TestCase):
    def test_offline_round_report_structure(self):
        a = adapt_fixture_a()
        b = adapt_fixture_b()
        report = run_offline_round([a], [b], commit=False)
        self.assertIn("metrics", report)
        self.assertIn("primary", report["metrics"])
        self.assertIn("specialized_appendix", report["metrics"])
        self.assertIn("frozen_mean", report["metrics"]["primary"])
        self.assertIn("curated_mean", report["metrics"]["primary"])
        # Curated should not collapse primary vs frozen on these fixtures.
        self.assertGreaterEqual(
            report["metrics"]["primary"]["curated_mean"] + 1e-9,
            report["metrics"]["primary"]["frozen_mean"] - 0.05,
        )
        # Actionability present in curated scores
        curated = report["metrics"]["curated"]
        self.assertIn(a.case_id, curated)
        self.assertGreaterEqual(curated[a.case_id]["actionability"], 0.5)

    def test_demo_split(self):
        sp = demo_dual_fixture_split()
        self.assertIn("fast_gelu_large_weak_start", sp.train)
        self.assertIn("fast_gelu_2048_strong_baseline", sp.dev)


if __name__ == "__main__":
    unittest.main()
