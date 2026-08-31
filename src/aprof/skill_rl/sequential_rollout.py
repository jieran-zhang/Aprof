"""Sequential rollout within a scenario (SAGE-inspired skill accumulation)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from aprof.skill_rl.config import SkillRlConfig
from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.memory_manager import ManagerPolicy, ManagerState, RulePolicy
from aprof.skill_rl.models import Episode, Skill
from aprof.skill_rl.retriever import retrieve_skills
from aprof.skill_rl.reward import score_training_transition


@dataclass
class RolloutStep:
    episode_id: str
    available_skill_ids: list[str]
    newly_unlocked: list[str] = field(default_factory=list)
    retrieved_skill_ids: list[str] = field(default_factory=list)
    used_skill_ids: list[str] = field(default_factory=list)
    generated_skill_ids: list[str] = field(default_factory=list)
    edit_actions: list[str] = field(default_factory=list)
    outcome_reward: float = 0.0
    reuse_reward: float = 0.0
    edit_reward: float = 0.0
    training_reward: float = 0.0
    bank_hash_before: str = ""
    bank_hash_after: str = ""


@dataclass
class RolloutTrace:
    scenario_id: str
    steps: list[RolloutStep] = field(default_factory=list)
    accumulated_skill_ids: list[str] = field(default_factory=list)
    final_skills: dict[str, Skill] = field(default_factory=dict)


EpisodeExecutor = Callable[[Episode, dict[str, Skill], list[str]], Episode]


def build_task_chains(
    episodes: list[Episode],
    *,
    chain_length: int = 2,
) -> list[list[Episode]]:
    """Group by problem × operator family × hardware, keeping ops distinct."""
    grouped: dict[tuple[str, str, str], list[Episode]] = {}
    for episode in episodes:
        problem = str(
            episode.metadata.get("problem_family")
            or episode.metadata.get("problem_id")
            or (episode.actionable_strategy_ids[0] if episode.actionable_strategy_ids else "unknown")
        )
        key = (
            problem,
            episode.workload.operator_family,
            str(episode.metadata.get("hardware") or "unknown"),
        )
        grouped.setdefault(key, []).append(episode)
    chains: list[list[Episode]] = []
    for rows in grouped.values():
        chain: list[Episode] = []
        seen_ops: set[str] = set()
        for episode in sorted(rows, key=lambda item: (item.op_name, item.case_id)):
            if episode.op_name in seen_ops:
                continue
            chain.append(episode)
            seen_ops.add(episode.op_name)
            if len(chain) == chain_length:
                chains.append(chain)
                chain = []
                seen_ops = set()
        if len(chain) >= 2:
            chains.append(chain)
    return chains


def sequential_rollout(
    episodes: list[Episode],
    *,
    initial_skills: dict[str, Skill] | None = None,
    commit_strategy_ids_from_episode: bool = True,
    manager_policy: ManagerPolicy | None = None,
    executor: EpisodeExecutor | None = None,
    config: SkillRlConfig | None = None,
    library_root=None,
) -> RolloutTrace:
    """
    Run episodes in order for one scenario. Later steps see skill ids committed
    from earlier accepted production-safe strategies.
    """
    if not episodes:
        return RolloutTrace(scenario_id="")
    scenario_id = episodes[0].scenario_id
    accumulated: list[str] = list((initial_skills or {}).keys())
    if manager_policy is not None:
        return run_managed_rollout(
            episodes,
            initial_skills=initial_skills,
            manager_policy=manager_policy,
            executor=executor,
            config=config,
            library_root=library_root,
        )
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
    return RolloutTrace(
        scenario_id=scenario_id,
        steps=steps,
        accumulated_skill_ids=accumulated,
        final_skills=dict(initial_skills or {}),
    )


def run_managed_rollout(
    episodes: list[Episode],
    *,
    initial_skills: dict[str, Skill] | None = None,
    manager_policy: ManagerPolicy | None = None,
    executor: EpisodeExecutor | None = None,
    config: SkillRlConfig | None = None,
    library_root=None,
) -> RolloutTrace:
    """Execute retrieve→use→edit over a temporary skill bank."""
    if not episodes:
        return RolloutTrace(scenario_id="")
    cfg = config or SkillRlConfig()
    policy = manager_policy or RulePolicy()
    bank = SkillLibrary(root=library_root, version_label="rollout")
    bank.skills = dict(initial_skills or {})
    steps: list[RolloutStep] = []
    generated_so_far: set[str] = set()

    for episode in episodes[: cfg.chain_length]:
        before_hash = _bank_hash(bank.skills)
        retrieved = retrieve_skills(
            episode,
            bank.skills,
            config=cfg,
            hardware=str(episode.metadata.get("hardware") or ""),
        )
        retrieved_ids = [item.skill_id for item in retrieved]
        episode.retrieved_skill_ids = retrieved_ids
        if executor is not None:
            episode = executor(episode, dict(bank.skills), retrieved_ids)
        elif not episode.used_skill_ids:
            episode.used_skill_ids = [
                sid for sid in retrieved_ids if sid in episode.actionable_strategy_ids
            ]

        reused_prior = bool(generated_so_far & set(episode.used_skill_ids))
        state = ManagerState(
            episode=episode,
            retrieved=retrieved,
            skills=dict(bank.skills),
            bank_version=before_hash,
        )
        edits = policy.propose(state, group_size=cfg.candidate_group_size)
        applied = bank.apply_edits(
            edits,
            library_budget=cfg.library_budget,
            transaction_id=episode.case_id,
        )
        generated = [
            edit.target_skill_id or edit.skill_id
            for edit in applied
            if edit.op in ("ADD", "UPDATE") and (edit.target_skill_id or edit.skill_id)
        ]
        episode.generated_skill_ids = generated
        generated_so_far.update(generated)
        after_hash = _bank_hash(bank.skills)
        mutating_edits = [edit for edit in edits if edit.op != "NOOP"]
        unique_targets = {
            edit.target_skill_id or edit.skill_id
            for edit in mutating_edits
            if edit.target_skill_id or edit.skill_id
        }
        duplicate_count = max(0, len(mutating_edits) - len(unique_targets))
        conflict_count = sum(bool(edit.conflict_basis) for edit in mutating_edits)
        specialized_count = sum(
            edit.scope == "benchmark_specialized" for edit in mutating_edits
        )
        episode.cost["candidate_count"] = float(len(mutating_edits))
        episode.cost["health_penalty"] = (
            cfg.duplicate_penalty * duplicate_count
            + cfg.conflict_penalty * conflict_count
            + cfg.specialized_penalty * specialized_count
        )
        frozen_outcome = episode.metadata.get("frozen_outcome")
        edited_outcome = episode.metadata.get("edited_outcome")
        reward = score_training_transition(
            episode,
            skills=bank.skills,
            frozen_outcome=float(frozen_outcome) if frozen_outcome is not None else None,
            edited_outcome=(
                float(edited_outcome)
                if generated and edited_outcome is not None
                else float(frozen_outcome)
                if frozen_outcome is not None
                else None
            ),
            generated_skill_reused=reused_prior,
            outcome_override=(
                float(edited_outcome)
                if generated and edited_outcome is not None
                else float(frozen_outcome)
                if not generated and frozen_outcome is not None
                else None
            ),
            config=cfg,
        )
        steps.append(
            RolloutStep(
                episode_id=episode.case_id,
                available_skill_ids=sorted(bank.skills),
                newly_unlocked=generated,
                retrieved_skill_ids=retrieved_ids,
                used_skill_ids=list(episode.used_skill_ids),
                generated_skill_ids=generated,
                edit_actions=[
                    f"{edit.op}:{edit.target_skill_id or edit.skill_id}" for edit in applied
                ],
                outcome_reward=reward.outcome_reward,
                reuse_reward=reward.reuse_reward,
                edit_reward=reward.edit_reward,
                training_reward=reward.training_reward,
                bank_hash_before=before_hash,
                bank_hash_after=after_hash,
            )
        )
    return RolloutTrace(
        scenario_id=episodes[0].scenario_id,
        steps=steps,
        accumulated_skill_ids=sorted(bank.skills),
        final_skills=dict(bank.skills),
    )


def _bank_hash(skills: dict[str, Skill]) -> str:
    from aprof.skill_rl.library import content_hash

    return content_hash(skills)
