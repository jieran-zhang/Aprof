"""Sequential rollout within a scenario (SAGE-inspired skill accumulation)."""

from __future__ import annotations

from dataclasses import dataclass, field

from aprof.skill_rl.models import Episode, Skill


@dataclass
class RolloutStep:
    episode_id: str
    available_skill_ids: list[str]
    newly_unlocked: list[str] = field(default_factory=list)


@dataclass
class RolloutTrace:
    scenario_id: str
    steps: list[RolloutStep] = field(default_factory=list)
    accumulated_skill_ids: list[str] = field(default_factory=list)


def sequential_rollout(
    episodes: list[Episode],
    *,
    initial_skills: dict[str, Skill] | None = None,
    commit_strategy_ids_from_episode: bool = True,
) -> RolloutTrace:
    """
    Run episodes in order for one scenario. Later steps see skill ids committed
    from earlier accepted production-safe strategies.
    """
    if not episodes:
        return RolloutTrace(scenario_id="")
    scenario_id = episodes[0].scenario_id
    accumulated: list[str] = list((initial_skills or {}).keys())
    steps: list[RolloutStep] = []
    for ep in episodes:
        step = RolloutStep(episode_id=ep.case_id, available_skill_ids=list(accumulated))
        newly: list[str] = []
        if commit_strategy_ids_from_episode:
            for rnd in ep.rounds:
                sel = rnd.selected
                if sel and sel.accepted and sel.scope == "production_safe" and sel.strategy_id:
                    if sel.strategy_id not in accumulated:
                        accumulated.append(sel.strategy_id)
                        newly.append(sel.strategy_id)
        step.newly_unlocked = newly
        steps.append(step)
    return RolloutTrace(scenario_id=scenario_id, steps=steps, accumulated_skill_ids=accumulated)
