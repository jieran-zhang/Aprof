import unittest

from aprof.skill_rl.episode_adapter import adapt_fixture_a, adapt_fixture_b


class TestSkillRlEpisodeAdapter(unittest.TestCase):
    def test_fixture_a_large_shape_numbers(self):
        ep = adapt_fixture_a()
        self.assertEqual(ep.baseline_kind, "naive")
        self.assertAlmostEqual(ep.original_median_us or 0.0, 23548.65, places=2)
        self.assertAlmostEqual(ep.final_median_us or 0.0, 91.178, places=3)
        self.assertEqual(len(ep.rounds), 3)
        self.assertGreater(ep.combined_speedup or 0.0, 200.0)
        r1 = ep.rounds[0]
        self.assertIsNotNone(r1.selected)
        self.assertAlmostEqual(r1.selected.speedup_vs_round_baseline or 0.0, 31.0, delta=0.2)
        self.assertIn("tiling.increase_blockdim_when_underused", ep.actionable_strategy_ids)

    def test_fixture_b_small_shape_numbers(self):
        ep = adapt_fixture_b()
        self.assertEqual(ep.baseline_kind, "strong")
        self.assertEqual(ep.workload.total_elements, 2048)
        self.assertAlmostEqual(ep.original_median_us or 0.0, 7.8, places=1)
        self.assertAlmostEqual(ep.final_median_us or 0.0, 5.9, places=1)
        self.assertAlmostEqual(ep.combined_speedup or 0.0, 1.322, places=2)
        self.assertEqual(ep.rounds[0].selected.config.get("blockdim"), 8)
        # Rejected / non-accepted candidates parseable
        self.assertTrue(any(ep.rounds[1].rejected))
        specs = [
            c
            for rnd in ep.rounds
            for c in ([rnd.selected] if rnd.selected else [])
            if c and c.scope == "benchmark_specialized"
        ]
        self.assertTrue(specs)


if __name__ == "__main__":
    unittest.main()
