"""Memory-R1 style policies for managing a structured skill bank."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable, Protocol

from aprof.skill_rl.curator import consolidate_edits, propose_edits
from aprof.skill_rl.models import Episode, Skill, SkillEdit
from aprof.skill_rl.retriever import RetrievedSkill


@dataclass
class ManagerState:
    episode: Episode
    retrieved: list[RetrievedSkill]
    skills: dict[str, Skill]
    bank_version: str = ""

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "episode": self.episode.to_dict(),
            "retrieved": [asdict(item) for item in self.retrieved],
            "skills": {
                sid: {
                    "id": skill.id,
                    "family": skill.family,
                    "preconditions": skill.preconditions,
                    "actionable_edits": skill.actionable_edits,
                    "expected_metric_delta": skill.expected_metric_delta,
                    "contraindications": skill.contraindications,
                    "confidence": skill.confidence,
                }
                for sid, skill in self.skills.items()
                if sid in {item.skill_id for item in self.retrieved}
            },
            "bank_version": self.bank_version,
            "allowed_ops": ["ADD", "UPDATE", "DELETE", "NOOP"],
        }


class ManagerPolicy(Protocol):
    name: str

    def propose(self, state: ManagerState, *, group_size: int = 1) -> list[SkillEdit]:
        ...


class FrozenPolicy:
    name = "frozen"

    def propose(self, state: ManagerState, *, group_size: int = 1) -> list[SkillEdit]:
        return [
            SkillEdit(
                op="NOOP",
                skill_id="",
                evidence_episode_ids=[state.episode.case_id],
                rationale="frozen_policy",
                policy_name=self.name,
                candidate_group_id=state.episode.case_id,
                candidate_id="noop",
            )
        ]


class RulePolicy:
    name = "rule"

    def propose(self, state: ManagerState, *, group_size: int = 1) -> list[SkillEdit]:
        edits = propose_edits(state.episode, state.skills)
        for index, edit in enumerate(edits):
            edit.policy_name = self.name
            edit.candidate_group_id = state.episode.case_id
            edit.candidate_id = f"rule-{index}"
        return edits or FrozenPolicy().propose(state)


Sampler = Callable[[dict[str, Any], int], list[dict[str, Any] | str]]


class SampledPolicy:
    """Adapter for GLM/local-model JSON candidates; it does not own model serving."""

    name = "sampled"

    def __init__(self, sampler: Sampler):
        self.sampler = sampler

    @staticmethod
    def _parse(raw: dict[str, Any] | str) -> dict[str, Any]:
        if isinstance(raw, str):
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.strip("`")
                if raw.startswith("json"):
                    raw = raw[4:].lstrip()
            return json.loads(raw)
        return dict(raw)

    def propose(self, state: ManagerState, *, group_size: int = 1) -> list[SkillEdit]:
        group_seed = json.dumps(
            {
                "case_id": state.episode.case_id,
                "bank_version": state.bank_version,
                "policy": self.name,
                "group_size": group_size,
            },
            sort_keys=True,
        )
        group_id = (
            f"{state.episode.case_id}:"
            f"{hashlib.sha256(group_seed.encode()).hexdigest()[:8]}"
        )
        edits: list[SkillEdit] = []
        for index, candidate in enumerate(self.sampler(state.to_prompt_dict(), group_size)):
            try:
                data = self._parse(candidate)
                op = str(data.get("op") or "NOOP").upper()
                if op not in {"ADD", "UPDATE", "DELETE", "NOOP"}:
                    continue
                skill_id = str(data.get("target_skill_id") or data.get("skill_id") or "")
                if op != "NOOP" and not skill_id:
                    continue
                edits.append(
                    SkillEdit(
                        op=op,  # type: ignore[arg-type]
                        skill_id=skill_id,
                        target_skill_id=skill_id,
                        payload=dict(data.get("payload") or {}),
                        evidence_episode_ids=[state.episode.case_id],
                        rationale=str(data.get("rationale") or ""),
                        conflict_basis=str(data.get("conflict_basis") or ""),
                        merge_basis=str(data.get("merge_basis") or ""),
                        policy_name=self.name,
                        policy_logprob=(
                            float(data["policy_logprob"])
                            if data.get("policy_logprob") is not None
                            else None
                        ),
                        candidate_group_id=group_id,
                        candidate_id=str(data.get("candidate_id") or index),
                    )
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
        return edits or FrozenPolicy().propose(state)
