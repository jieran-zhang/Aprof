"""Lightweight group-relative edit selection and VERL-compatible export."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

from aprof.skill_rl.models import SkillEdit
from aprof.skill_rl.replay_env import ReplayResult


@dataclass
class GroupRelativeCandidate:
    edit: SkillEdit
    reward: float
    advantage: float = 0.0
    accepted: bool = False


def group_relative_advantages(rewards: list[float]) -> list[float]:
    if not rewards:
        return []
    mean = sum(rewards) / len(rewards)
    variance = sum((reward - mean) ** 2 for reward in rewards) / len(rewards)
    std = math.sqrt(variance)
    if std <= 1e-12:
        return [0.0 for _ in rewards]
    return [(reward - mean) / std for reward in rewards]


class LightweightEditSelector:
    """A dependency-free contextual bandit over operation/family features."""

    def __init__(self, learning_rate: float = 0.1):
        self.learning_rate = learning_rate
        self.weights: dict[str, float] = {}

    @staticmethod
    def features(edit: SkillEdit) -> list[str]:
        family = str(edit.payload.get("family") or edit.skill_id.split(".", 1)[0] or "unknown")
        return [f"op={edit.op}", f"family={family}", f"op_family={edit.op}:{family}"]

    def score(self, edit: SkillEdit) -> float:
        return sum(self.weights.get(feature, 0.0) for feature in self.features(edit))

    def update(self, candidates: Iterable[GroupRelativeCandidate]) -> None:
        for candidate in candidates:
            for feature in self.features(candidate.edit):
                self.weights[feature] = self.weights.get(feature, 0.0) + (
                    self.learning_rate * candidate.advantage
                )

    def choose(self, candidates: list[GroupRelativeCandidate]) -> GroupRelativeCandidate:
        return max(
            candidates,
            key=lambda candidate: (
                self.score(candidate.edit),
                candidate.reward,
                candidate.edit.candidate_id,
            ),
        )


def candidates_from_replay(results: list[ReplayResult]) -> list[GroupRelativeCandidate]:
    rewards = [result.transition.reward.get("training_reward", 0.0) for result in results]
    advantages = group_relative_advantages([float(reward) for reward in rewards])
    return [
        GroupRelativeCandidate(
            edit=SkillEdit(**result.transition.action),
            reward=float(reward),
            advantage=advantage,
            accepted=result.accepted,
        )
        for result, reward, advantage in zip(results, rewards, advantages)
    ]


def export_verl_jsonl(
    path: Path,
    *,
    prompt: dict,
    candidates: list[GroupRelativeCandidate],
    bank_version: str,
) -> None:
    """Write one JSON object per sampled completion for future VERL-GRPO."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for candidate in candidates:
            row = {
                "data_source": "aprof_skill_memory",
                "prompt": prompt,
                "completion": asdict(candidate.edit),
                "reward": candidate.reward,
                "advantage": candidate.advantage,
                "candidate_group_id": candidate.edit.candidate_group_id,
                "bank_version": bank_version,
            }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
