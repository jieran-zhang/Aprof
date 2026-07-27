import unittest

from aprof.skill_rl.inject_hw import load_inject_hw_train
from aprof.skill_rl.curator import filter_executable_edits, propose_edits
from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.models import Skill
from aprof.skill_rl.reward import score_episode


class TestSkillRlInjectHw(unittest.TestCase):
    def test_load_inject_train_nonempty(self):
        eps = load_inject_hw_train(limit=5)
        self.assertGreaterEqual(len(eps), 1)
        self.assertTrue(eps[0].metadata.get("source_910b"))

    def test_curated_beats_generic_actionability(self):
        eps = load_inject_hw_train(limit=8)
        if len(eps) < 2:
            self.skipTest("inject_hw_train fixtures missing")
        lib = SkillLibrary(version_label="v0")
        lib.load()
        generic = {
            sid: Skill(
                id=sk.id,
                family=sk.family,
                actionable_edits=[],
                expected_metric_delta={},
                notes="generic",
            )
            for sid, sk in lib.skills.items()
        }
        edits = []
        for ep in eps[:4]:
            edits.extend(propose_edits(ep, lib.skills))
        edits = filter_executable_edits(edits)
        trial = SkillLibrary(version_label="v0")
        trial.skills = dict(lib.skills)
        trial.apply_edits(edits)
        g_act = sum(score_episode(ep, skills=generic).actionability for ep in eps) / len(eps)
        c_act = sum(score_episode(ep, skills=trial.skills).actionability for ep in eps) / len(eps)
        self.assertGreaterEqual(c_act, g_act)


if __name__ == "__main__":
    unittest.main()
