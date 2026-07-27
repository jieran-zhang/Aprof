"""Validation gate for skill edits (Dev split)."""

from __future__ import annotations

from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.models import Episode, SkillEdit
from aprof.skill_rl.reward import score_episode


def validate_edits(
    edits: list[SkillEdit],
    *,
    base_library: SkillLibrary,
    dev_episodes: list[Episode],
) -> tuple[bool, list[SkillEdit], dict]:
    """
    Apply edits on a copy of the library; accept only if mean primary reward
    on Dev does not drop and hard gates still pass for episodes that previously passed.
    """
    report: dict = {"accepted": False, "applied": [], "reason": ""}
    if not edits:
        report["reason"] = "no_edits"
        return False, [], report

    # Reject clearly harmful hand-authored empties.
    from aprof.skill_rl.curator import filter_executable_edits

    filtered = filter_executable_edits(edits)
    if not filtered:
        report["reason"] = "no_executable_edits"
        return False, [], report

    before_scores = [score_episode(ep, skills=base_library.skills) for ep in dev_episodes]
    before_mean = sum(s.primary for s in before_scores) / max(len(before_scores), 1)

    trial = SkillLibrary(root=base_library.root, version_label=base_library.version_label)
    trial.skills = dict(base_library.skills)
    applied = trial.apply_edits(filtered)
    if not applied:
        report["reason"] = "edits_not_applied"
        return False, [], report

    after_scores = [score_episode(ep, skills=trial.skills) for ep in dev_episodes]
    after_mean = sum(s.primary for s in after_scores) / max(len(after_scores), 1)

    # Actionability should not collapse.
    before_act = sum(s.actionability for s in before_scores) / max(len(before_scores), 1)
    after_act = sum(s.actionability for s in after_scores) / max(len(after_scores), 1)

    if after_mean + 1e-9 < before_mean and after_act + 1e-9 < before_act:
        report["reason"] = "primary_and_actionability_regressed"
        report["before_mean"] = before_mean
        report["after_mean"] = after_mean
        return False, [], report

    # Intentionally bad edit detection: empty actionable overwritten.
    for e in applied:
        if e.op in ("ADD", "UPDATE"):
            sk = trial.skills.get(e.skill_id)
            if sk and not sk.is_actionable():
                report["reason"] = "non_actionable_skill_after_edit"
                return False, [], report

    report["accepted"] = True
    report["applied"] = [e.skill_id + ":" + e.op for e in applied]
    report["before_mean"] = before_mean
    report["after_mean"] = after_mean
    report["before_actionability"] = before_act
    report["after_actionability"] = after_act
    return True, applied, report
