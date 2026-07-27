"""Skill-RL package: SAGE-lite offline skill library self-improvement."""

from aprof.skill_rl.episode_adapter import adapt_fixture_a, adapt_fixture_b, load_dual_fixtures

__all__ = [
    "adapt_fixture_a",
    "adapt_fixture_b",
    "load_dual_fixtures",
    "run_offline_round",
]


def __getattr__(name: str):
    if name == "run_offline_round":
        from aprof.skill_rl.trainer import run_offline_round

        return run_offline_round
    raise AttributeError(name)
