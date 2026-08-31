"""Skill-RL package: SAGE-lite offline skill library self-improvement."""

from aprof.skill_rl.episode_adapter import adapt_fixture_a, adapt_fixture_b, load_dual_fixtures
from aprof.skill_rl.config import SkillRlConfig

__all__ = [
    "adapt_fixture_a",
    "adapt_fixture_b",
    "load_dual_fixtures",
    "SkillRlConfig",
    "run_offline_round",
    "run_group_relative_round",
]


def __getattr__(name: str):
    if name == "run_offline_round":
        from aprof.skill_rl.trainer import run_offline_round

        return run_offline_round
    if name == "run_group_relative_round":
        from aprof.skill_rl.trainer import run_group_relative_round

        return run_group_relative_round
    raise AttributeError(name)
