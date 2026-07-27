"""Offline SAGE-lite trainer: propose → gate → commit → compare."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from aprof.skill_rl.curator import filter_executable_edits, propose_edits
from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.models import Episode
from aprof.skill_rl.reward import score_episode
from aprof.skill_rl.sequential_rollout import sequential_rollout
from aprof.skill_rl.validation_gate import validate_edits


def run_offline_round(
    train_episodes: list[Episode],
    dev_episodes: list[Episode],
    *,
    library_root: Path | None = None,
    base_version: str = "v0",
    next_version: str = "v1",
    commit: bool = False,
) -> dict[str, Any]:
    """
    One offline Skill-RL round.

    Returns a report with frozen vs curated metrics (primary + specialized appendix).
    """
    lib = SkillLibrary(root=library_root, version_label=base_version)
    snap0 = lib.load()

    frozen_scores = {ep.case_id: score_episode(ep, skills=lib.skills).to_dict() for ep in train_episodes + dev_episodes}

    all_edits = []
    for ep in train_episodes:
        all_edits.extend(propose_edits(ep, lib.skills))
    all_edits = filter_executable_edits(all_edits)

    ok, applied, gate_report = validate_edits(all_edits, base_library=lib, dev_episodes=dev_episodes or train_episodes)

    curated_skills = dict(lib.skills)
    version_label = base_version
    if ok and applied:
        trial = SkillLibrary(root=library_root, version_label=base_version)
        trial.skills = dict(lib.skills)
        trial.apply_edits(applied)
        curated_skills = dict(trial.skills)
        if commit:
            snap = trial.commit(next_version)
            version_label = snap.version_label
        else:
            version_label = next_version + "_dry_run"

    curated_scores = {
        ep.case_id: score_episode(ep, skills=curated_skills).to_dict() for ep in train_episodes + dev_episodes
    }

    def _mean_primary(scores: dict[str, dict]) -> float:
        if not scores:
            return 0.0
        return sum(float(v.get("primary") or 0.0) for v in scores.values()) / len(scores)

    rollout = sequential_rollout(train_episodes, initial_skills=snap0.skills)

    return {
        "gate_accepted": ok,
        "gate_report": gate_report,
        "applied_edits": [f"{e.op}:{e.skill_id}" for e in applied],
        "base_version": base_version,
        "curated_version": version_label,
        "base_hash": snap0.content_hash,
        "metrics": {
            "frozen": frozen_scores,
            "curated": curated_scores,
            "primary": {
                "frozen_mean": _mean_primary(frozen_scores),
                "curated_mean": _mean_primary(curated_scores),
            },
            "specialized_appendix": {
                ep.case_id: curated_scores[ep.case_id].get("specialized_appendix_speedup", 0.0)
                for ep in train_episodes + dev_episodes
                if ep.case_id in curated_scores
            },
        },
        "rollout": {
            "scenario_id": rollout.scenario_id,
            "accumulated_skill_ids": rollout.accumulated_skill_ids,
            "steps": [
                {
                    "episode_id": s.episode_id,
                    "available_skill_ids": s.available_skill_ids,
                    "newly_unlocked": s.newly_unlocked,
                }
                for s in rollout.steps
            ],
        },
    }
