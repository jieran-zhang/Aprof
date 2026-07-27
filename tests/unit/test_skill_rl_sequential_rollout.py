import unittest

from aprof.skill_rl.episode_adapter import adapt_fixture_a
from aprof.skill_rl.models import Episode
from aprof.skill_rl.sequential_rollout import sequential_rollout


class TestSkillRlSequentialRollout(unittest.TestCase):
    def test_later_round_sees_earlier_skills(self):
        ep = adapt_fixture_a()
        # Split one episode's rounds into pseudo-episodes in the same scenario.
        eps: list[Episode] = []
        for i, rnd in enumerate(ep.rounds):
            piece = Episode(
                case_id=f"{ep.case_id}::r{i+1}",
                op_name=ep.op_name,
                scenario_id=ep.scenario_id,
                baseline_kind=ep.baseline_kind,
                source=ep.source,
                original_median_us=ep.original_median_us,
                final_median_us=ep.final_median_us,
                workload=ep.workload,
                diagnosis_type=ep.diagnosis_type,
                measurement=ep.measurement,
                rounds=[rnd],
                actionable_strategy_ids=ep.actionable_strategy_ids,
                metadata=ep.metadata,
            )
            eps.append(piece)
        trace = sequential_rollout(eps)
        self.assertEqual(trace.scenario_id, ep.scenario_id)
        self.assertGreaterEqual(len(trace.steps), 2)
        # Second step should see skills unlocked by first.
        self.assertTrue(len(trace.steps[1].available_skill_ids) >= len(trace.steps[0].available_skill_ids))
        if trace.steps[0].newly_unlocked:
            for sid in trace.steps[0].newly_unlocked:
                self.assertIn(sid, trace.steps[1].available_skill_ids)
        self.assertTrue(trace.accumulated_skill_ids)


if __name__ == "__main__":
    unittest.main()
