"""Rule curator and compatibility helpers for structured skill edits."""

from __future__ import annotations

from aprof.skill_rl.models import Episode, Skill, SkillEdit


def _editable_from_candidate(episode: Episode, strategy_id: str, code_changes: list[str], family: str) -> dict:
    return {
        "id": strategy_id,
        "family": family,
        "scope": "production_safe",
        "preconditions": [
            "diagnosis_type == true_bottleneck",
            f"workload_class == {episode.workload.workload_class}",
        ],
        "actionable_edits": [
            {"from_trajectory": True, "code_changes": code_changes or ["unspecified_edit"]}
        ],
        "expected_metric_delta": {
            "primary": "TaskDuration_median_us",
            "direction": "decrease",
            "min_effect_pct": episode.min_effect_pct,
        },
        "measurement_policy": {
            "warm_up": 10,
            "repeat": 5,
            "statistic": "median",
            "max_cv": 0.05,
        },
        "linked_hypotheses": list(episode.actionable_strategy_ids),
        "contraindications": ["single_run_duration_as_proof"],
        "hardware_scope": [
            str(episode.metadata.get("hardware"))
        ] if episode.metadata.get("hardware") else [],
        "workload_scope": [episode.workload.workload_class],
        "operator_scope": [episode.workload.operator_family],
        "evidence_episode_ids": [episode.case_id],
        "success_count": 1,
        "confidence": min(
            1.0,
            max(0.1, ((float(episode.combined_speedup or 1.0) - 1.0) / 4.0)),
        ),
        "notes": f"curated_from:{episode.case_id}",
    }


def propose_edits(episode: Episode, library_skills: dict[str, Skill] | None = None) -> list[SkillEdit]:
    """Propose ADD/UPDATE/DEPRECATE from one episode."""
    library_skills = library_skills or {}
    edits: list[SkillEdit] = []

    for rnd in episode.rounds:
        sel = rnd.selected
        if sel and sel.accepted:
            if sel.scope == "benchmark_specialized":
                edits.append(
                    SkillEdit(
                        op="ADD",
                        skill_id=sel.strategy_id or f"specialized.{sel.id}",
                        payload={"scope": "benchmark_specialized", "notes": "appendix_only"},
                        evidence_episode_ids=[episode.case_id],
                        scope="benchmark_specialized",
                        rationale="specialized_success_not_primary",
                    )
                )
                continue
            sid = sel.strategy_id or f"trajectory.{episode.case_id}.{sel.id}"
            family = sid.split(".", 1)[0] if "." in sid else "tiling"
            # Reject empty natural-language-only updates.
            if not sel.code_changes and not sel.strategy_id:
                continue
            payload = _editable_from_candidate(episode, sid, list(sel.code_changes), family)
            op = "UPDATE" if sid in library_skills else "ADD"
            edits.append(
                SkillEdit(
                    op=op,  # type: ignore[arg-type]
                    skill_id=sid,
                    payload=payload,
                    evidence_episode_ids=[episode.case_id],
                    scope="production_safe",
                    rationale=f"accepted_round_{rnd.round_index}",
                )
            )

        for rej in rnd.rejected:
            tip = rej.reason or "rejected_candidate"
            sid = rej.strategy_id or f"failed.{rej.id}"
            edits.append(
                SkillEdit(
                    op="DELETE",
                    skill_id=sid if sid in library_skills else (sel.strategy_id if sel and sel.strategy_id else sid),
                    payload={
                        "contraindication": tip,
                        "family": (rej.strategy_id or "tiling").split(".", 1)[0],
                        "failed_candidate_id": rej.id,
                    },
                    evidence_episode_ids=[episode.case_id],
                    scope="production_safe",
                    rationale=tip,
                )
            )
    return consolidate_edits(edits)


def consolidate_edits(edits: list[SkillEdit]) -> list[SkillEdit]:
    """Deduplicate a batch and avoid UPDATE+DELETE conflicts for one skill."""
    grouped: dict[str, list[SkillEdit]] = {}
    order: list[str] = []
    for edit in edits:
        sid = edit.target_skill_id or edit.skill_id
        if sid not in grouped:
            grouped[sid] = []
            order.append(sid)
        grouped[sid].append(edit)

    result: list[SkillEdit] = []
    for sid in order:
        candidates = grouped[sid]
        writes = [e for e in candidates if e.op in ("ADD", "UPDATE")]
        deletes = [e for e in candidates if e.op in ("DELETE", "DEPRECATE")]
        noops = [e for e in candidates if e.op == "NOOP"]
        if writes:
            chosen = writes[-1]
            reasons = list(
                dict.fromkeys(
                    str(e.payload.get("contraindication") or e.rationale)
                    for e in deletes
                    if e.payload.get("contraindication") or e.rationale
                )
            )
            if reasons:
                payload = dict(chosen.payload)
                payload["contraindications"] = list(
                    dict.fromkeys(list(payload.get("contraindications") or []) + reasons)
                )
                chosen.payload = payload
                chosen.conflict_basis = "successful edit retained; rejected variants became contraindications"
            result.append(chosen)
        elif deletes:
            chosen = deletes[-1]
            chosen.op = "DELETE"
            result.append(chosen)
        elif noops:
            result.append(noops[-1])
    return result


def filter_executable_edits(edits: list[SkillEdit]) -> list[SkillEdit]:
    """Drop non-actionable ADD/UPDATE (D2)."""
    kept: list[SkillEdit] = []
    for e in edits:
        if e.scope == "benchmark_specialized":
            continue
        if e.op in ("DELETE", "DEPRECATE", "NOOP"):
            kept.append(e)
            continue
        ae = e.payload.get("actionable_edits") or []
        em = e.payload.get("expected_metric_delta") or {}
        if ae and em:
            kept.append(e)
    return kept
