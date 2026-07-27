import unittest

from aprof.skill_rl.episode_adapter import adapt_fixture_a, adapt_fixture_b
from aprof.skill_rl.models import Candidate, Episode, Measurement, Round, WorkloadModel
from aprof.skill_rl.reward import score_episode


class TestSkillRlReward(unittest.TestCase):
    def test_fixture_a_stable_measurement_and_speedup(self):
        ep = adapt_fixture_a()
        rb = score_episode(ep)
        self.assertTrue(rb.correctness_ok)
        self.assertTrue(rb.measurement_ok)
        self.assertTrue(rb.scope_primary_ok)
        self.assertGreater(rb.speedup_score, 0.0)
        self.assertGreater(rb.primary, 0.0)

    def test_fixture_b_measurement_fails_without_warmup_repeat(self):
        ep = adapt_fixture_b()
        rb = score_episode(ep)
        self.assertTrue(rb.correctness_ok)
        self.assertFalse(rb.measurement_ok)
        self.assertEqual(rb.speedup_score, 0.0)
        # Exploratory primary may be >0 from actionability, but speedup excluded.
        self.assertIn("measurement_unstable_or_missing_warmup_repeat", " ".join(rb.notes))

    def test_bad_correctness_zeros_primary(self):
        ep = adapt_fixture_a()
        ep.metadata["correctness"] = {"checked": 100, "bad": 3}
        for rnd in ep.rounds:
            if rnd.selected:
                rnd.selected.correctness_bad = 3
                rnd.selected.correctness_checked = 100
        rb = score_episode(ep)
        self.assertFalse(rb.correctness_ok)
        self.assertEqual(rb.primary, 0.0)

    def test_specialized_not_primary_candidate(self):
        ep = adapt_fixture_b()
        # Round2 selected is specialized; production primary should still be blockdim=8.
        rb = score_episode(ep)
        self.assertTrue(rb.scope_primary_ok)
        self.assertGreater(rb.specialized_appendix_speedup, 1.0)

    def test_below_min_effect_no_speedup_score(self):
        ep = Episode(
            case_id="tiny",
            op_name="x",
            scenario_id="s",
            baseline_kind="strong",
            source="test",
            original_median_us=100.0,
            final_median_us=98.0,
            combined_speedup=100 / 98,
            workload=WorkloadModel(workload_class="normal", total_elements=10000),
            diagnosis_type="true_bottleneck",
            measurement=Measurement(warm_up=10, repeat=5, samples_us=[98, 98, 98, 98, 98], median_us=98.0),
            rounds=[
                Round(
                    round_index=1,
                    label="r1",
                    selected=Candidate(
                        id="c1",
                        strategy_id="tiling.increase_tile_length",
                        median_us=98.0,
                        accepted=True,
                        scope="production_safe",
                        semantic_status="preserved",
                        correctness_bad=0,
                        correctness_checked=10,
                        code_changes=["x"],
                    ),
                    measurement=Measurement(warm_up=10, repeat=5, samples_us=[98, 99, 97, 98, 98], median_us=98.0),
                )
            ],
            actionable_strategy_ids=["tiling.increase_tile_length"],
            min_effect_pct=3.0,
            metadata={"correctness": {"checked": 10, "bad": 0}},
        )
        rb = score_episode(ep)
        self.assertEqual(rb.speedup_score, 0.0)


if __name__ == "__main__":
    unittest.main()
