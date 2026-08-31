"""Deterministic structured retrieval for the skill library."""

from __future__ import annotations

from dataclasses import dataclass

from aprof.skill_rl.config import SkillRlConfig
from aprof.skill_rl.models import Episode, Skill


@dataclass(frozen=True)
class RetrievedSkill:
    skill_id: str
    score: float
    reasons: tuple[str, ...] = ()


def _problem_terms(episode: Episode) -> set[str]:
    terms = {str(episode.diagnosis_type).lower()}
    terms.update(str(x).lower() for x in episode.actionable_strategy_ids)
    for key in ("problem_id", "problem_family", "diagnosis_id"):
        value = episode.metadata.get(key)
        if value:
            terms.add(str(value).lower())
    return terms


def score_skill(episode: Episode, skill: Skill, *, hardware: str = "") -> RetrievedSkill:
    if skill.tombstone or not skill.is_actionable():
        return RetrievedSkill(skill.id, -1.0, ("inactive",))
    score = 0.0
    reasons: list[str] = []
    problem_terms = _problem_terms(episode)
    skill_terms = {
        skill.id.lower(),
        skill.family.lower(),
        *(str(x).lower() for x in skill.linked_hypotheses),
    }
    if any(any(term in candidate or candidate in term for candidate in skill_terms) for term in problem_terms):
        score += 0.45
        reasons.append("problem_match")
    if skill.family in episode.actionable_strategy_ids or any(
        sid.startswith(skill.family + ".") for sid in episode.actionable_strategy_ids
    ):
        score += 0.20
        reasons.append("family_match")
    op_family = episode.workload.operator_family
    if not skill.operator_scope or episode.op_name in skill.operator_scope or op_family in skill.operator_scope:
        score += 0.15
        reasons.append("operator_scope")
    workload = episode.workload.workload_class
    if not skill.workload_scope or workload in skill.workload_scope:
        score += 0.10
        reasons.append("workload_scope")
    if not skill.hardware_scope or not hardware or hardware in skill.hardware_scope:
        score += 0.05
        reasons.append("hardware_scope")
    score += 0.05 * max(0.0, min(1.0, skill.confidence))
    return RetrievedSkill(skill.id, min(score, 1.0), tuple(reasons))


def retrieve_skills(
    episode: Episode,
    skills: dict[str, Skill],
    *,
    config: SkillRlConfig | None = None,
    hardware: str = "",
) -> list[RetrievedSkill]:
    cfg = config or SkillRlConfig()
    eligible = []
    for skill in skills.values():
        if (
            not cfg.allow_cross_operator
            and skill.operator_scope
            and episode.op_name not in skill.operator_scope
            and episode.workload.operator_family not in skill.operator_scope
        ):
            continue
        if (
            not cfg.allow_cross_hardware
            and hardware
            and skill.hardware_scope
            and hardware not in skill.hardware_scope
        ):
            continue
        eligible.append(skill)
    ranked = [score_skill(episode, skill, hardware=hardware) for skill in eligible]
    ranked = [item for item in ranked if item.score >= cfg.retrieval_min_score]
    ranked.sort(key=lambda item: (-item.score, item.skill_id))
    return ranked[: cfg.retrieval_top_k]
