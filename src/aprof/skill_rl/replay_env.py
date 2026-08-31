"""Low-cost counterfactual replay before expensive 910B validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from aprof.skill_rl.config import SkillRlConfig
from aprof.skill_rl.library import SkillLibrary, content_hash
from aprof.skill_rl.models import Episode, SkillEdit
from aprof.skill_rl.reward import score_training_transition


@dataclass
class ReplayTransition:
    case_id: str
    scenario_id: str
    state: dict[str, Any]
    action: dict[str, Any]
    frozen_outcome: float
    edited_outcome: float
    bank_hash_before: str
    bank_hash_after: str
    reward: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReplayResult:
    accepted: bool
    marginal_gain: float
    transition: ReplayTransition
    reason: str = ""


class ReplayEnvironment:
    def __init__(self, *, config: SkillRlConfig | None = None):
        self.config = config or SkillRlConfig()

    def evaluate(
        self,
        episode: Episode,
        edit: SkillEdit,
        base_library: SkillLibrary,
        *,
        frozen_outcome: float | None = None,
        edited_outcome: float | None = None,
    ) -> ReplayResult:
        before_hash = content_hash(base_library.skills)
        trial = base_library.clone()
        applied = trial.apply_edits(
            [edit],
            library_budget=self.config.library_budget,
            transaction_id=f"replay:{episode.case_id}",
        )
        after_hash = content_hash(trial.skills)
        frozen = float(
            frozen_outcome
            if frozen_outcome is not None
            else episode.metadata.get("frozen_outcome", 0.0)
        )
        edited = float(
            edited_outcome
            if edited_outcome is not None
            else episode.metadata.get("edited_outcome", frozen)
        )
        if edit.op == "NOOP":
            edited = frozen
        elif edit.op in ("DELETE", "DEPRECATE"):
            edited = float(episode.metadata.get("delete_outcome", frozen))
        rb = score_training_transition(
            episode,
            skills=trial.skills,
            frozen_outcome=frozen,
            edited_outcome=edited,
            generated_skill_reused=bool(episode.used_skill_ids),
            outcome_override=edited,
            config=self.config,
        )
        transition = ReplayTransition(
            case_id=episode.case_id,
            scenario_id=episode.scenario_id,
            state={
                "episode": episode.to_dict(),
                "bank_version": base_library.version_label,
            },
            action=asdict(edit),
            frozen_outcome=frozen,
            edited_outcome=edited,
            bank_hash_before=before_hash,
            bank_hash_after=after_hash,
            reward=rb.to_dict(),
        )
        marginal = edited - frozen
        accepted = bool(applied) and rb.correctness_ok and marginal >= 0.0
        return ReplayResult(
            accepted=accepted,
            marginal_gain=marginal,
            transition=transition,
            reason="" if accepted else "edit_not_beneficial_or_not_applied",
        )
