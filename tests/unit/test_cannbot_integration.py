from __future__ import annotations

import unittest

from aprof.integrations.cannbot import (
    cannbot_skills_root,
    get_skill_markdown,
    list_skills,
    resolve_skill,
)


class CannbotIntegrationTests(unittest.TestCase):
    def test_submodule_present(self) -> None:
        root = cannbot_skills_root()
        self.assertTrue((root / "ops").is_dir())

    def test_list_skills(self) -> None:
        skills = list_skills()
        self.assertGreater(len(skills), 10)
        names = {skill.name for skill in skills}
        self.assertIn("ops-profiling", names)
        self.assertIn("npu-arch", names)

    def test_resolve_ops_profiling(self) -> None:
        skill = resolve_skill("ops-profiling")
        text = get_skill_markdown("ops-profiling")
        self.assertEqual(skill.name, "ops-profiling")
        self.assertIn("name:", text)


if __name__ == "__main__":
    unittest.main()
