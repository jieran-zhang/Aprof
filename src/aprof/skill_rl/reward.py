"""Multi-objective reward for Skill-RL (defect-driven hard/soft gates)."""

from __future__ import annotations

from aprof.skill_rl.models import Candidate, Episode, RewardBreakdown, Skill


def _primary_production_candidate(episode: Episode) -> Candidate | None:
    """Last production_safe accepted candidate, skipping specialized-only accepts."""
    chosen: Candidate | None = None
    for rnd in episode.rounds:
        sel = rnd.selected
        if not sel or not sel.accepted:
            continue
        if sel.scope == "benchmark_specialized":
            continue
        if sel.semantic_status not in ("preserved", "unknown", ""):
            continue
        chosen = sel
    # Fixture B: round1 production best even if round2 selected specialized.
    if chosen is None:
        for rnd in episode.rounds:
            for c in [rnd.selected] + list(rnd.rejected):
                if c and c.accepted and c.scope == "production_safe":
                    return c
            for raw_id in ():
                pass
    return chosen


def _specialized_speedup(episode: Episode) -> float:
    if episode.original_median_us and episode.original_median_us > 0:
        appendix = (episode.metadata or {}).get("specialized_appendix") or {}
        med = appendix.get("median_us")
        if med:
            return float(episode.original_median_us) / float(med)
    for rnd in episode.rounds:
        sel = rnd.selected
        if sel and sel.scope == "benchmark_specialized" and sel.median_us and episode.original_median_us:
            return float(episode.original_median_us) / float(sel.median_us)
    return 0.0


def _speedup_vs_original(episode: Episode, cand: Candidate | None) -> float:
    if not cand or not cand.median_us or not episode.original_median_us:
        if episode.combined_speedup:
            return float(episode.combined_speedup)
        return 0.0
    if cand.median_us <= 0:
        return 0.0
    return float(episode.original_median_us) / float(cand.median_us)


def score_episode(
    episode: Episode,
    *,
    skills: dict[str, Skill] | None = None,
    min_warmup: int = 1,
    min_repeat: int = 3,
) -> RewardBreakdown:
    """Compute RewardBreakdown for one optimization episode."""
    rb = RewardBreakdown()
    corr = (episode.metadata or {}).get("correctness") or {}
    bad = int(corr.get("bad") or 0)
    checked = int(corr.get("checked") or 0)
    # Prefer candidate-level correctness when present.
    prod = _primary_production_candidate(episode)
    if prod and prod.correctness_checked:
        bad = prod.correctness_bad
        checked = prod.correctness_checked

    rb.correctness_ok = bad == 0 and checked > 0
    if not rb.correctness_ok:
        rb.notes.append("correctness_gate_failed")
        rb.primary = 0.0
        return rb

    rb.semantics_ok = True
    if prod and prod.semantic_status not in ("preserved", "unknown", ""):
        rb.semantics_ok = False
        rb.notes.append("semantics_not_preserved")

    rb.scope_primary_ok = prod is not None and prod.scope == "production_safe"
    if not rb.scope_primary_ok:
        rb.notes.append("no_production_safe_primary_candidate")

    # Measurement: episode-level or last round.
    meas = episode.measurement
    if not meas.is_stable(min_warmup=min_warmup, min_repeat=min_repeat):
        # Fallback: any round with enough samples counts as repeat evidence.
        ok = False
        for rnd in episode.rounds:
            if rnd.measurement.is_stable(min_warmup=min_warmup, min_repeat=min_repeat):
                ok = True
                meas = rnd.measurement
                break
            if len(rnd.measurement.samples_us) >= min_repeat and (meas.warm_up >= min_warmup or episode.baseline_kind == "naive"):
                # Fixture A: warm_up annotated on policy even if per-block omitted.
                if episode.measurement.warm_up >= min_warmup or len(rnd.measurement.samples_us) >= min_repeat:
                    ok = episode.measurement.warm_up >= min_warmup or episode.baseline_kind == "naive"
                    if episode.measurement.warm_up >= min_warmup and len(rnd.measurement.samples_us) >= min_repeat:
                        ok = True
        rb.measurement_ok = ok
        if not ok:
            rb.notes.append("measurement_unstable_or_missing_warmup_repeat")
    else:
        rb.measurement_ok = True

    # Soft: speedup (only if measurement ok for primary)
    speedup = _speedup_vs_original(episode, prod)
    min_effect = episode.min_effect_pct / 100.0
    # speedup score in [0,1] capped log-ish: require >= 1+min_effect
    if speedup >= 1.0 + min_effect:
        # Normalize: 1.03 → ~0.1 floor, large speedups saturate at 1.0
        rb.speedup_score = min(1.0, (speedup - 1.0) / max(speedup, 1.0))
        if speedup >= 1.2:
            rb.speedup_score = min(1.0, 0.5 + min(0.5, (speedup - 1.2) / 10.0))
        if speedup >= 2.0:
            rb.speedup_score = min(1.0, 0.7 + min(0.3, (speedup - 2.0) / 50.0))
    else:
        rb.speedup_score = 0.0
        rb.notes.append("below_min_effect_threshold")

    if not rb.measurement_ok:
        rb.speedup_score = 0.0
        rb.notes.append("speedup_excluded_from_primary_due_to_measurement")

    # Actionability
    if episode.actionable_strategy_ids:
        rb.actionability = 1.0
    elif prod and prod.strategy_id:
        rb.actionability = 1.0
    elif prod and prod.code_changes:
        rb.actionability = 0.5
    else:
        rb.actionability = 0.0
        rb.notes.append("low_actionability")

    if skills:
        matched = [sid for sid in episode.actionable_strategy_ids if sid in skills and skills[sid].is_actionable()]
        if matched:
            rb.actionability = 1.0
        elif rb.actionability >= 1.0:
            # Trajectory actionable but library skill still generic.
            rb.actionability = 0.7
            rb.notes.append("trajectory_actionable_library_generic")

    # Workload awareness (D3)
    rb.workload_awareness = 1.0
    wc = (episode.workload.workload_class or "").lower()
    if wc in ("tiny", "small") and episode.diagnosis_type == "true_bottleneck":
        # Small shape with real underused cores can still be true_bottleneck if blockdim=1.
        # Only penalize if no actionable multicore strategy was used.
        if not any("blockdim" in s for s in episode.actionable_strategy_ids):
            rb.workload_awareness = 0.3
            rb.notes.append("small_workload_true_bottleneck_without_clear_anchor")
        else:
            rb.workload_awareness = 0.8
            rb.notes.append("small_workload_but_actionable_parallelism")

    # Efficiency: fewer rejected relative to accepts is better; explainable rejects help.
    n_rej = sum(len(r.rejected) for r in episode.rounds)
    n_acc = sum(1 for r in episode.rounds if r.selected and r.selected.accepted)
    explainable = sum(1 for r in episode.rounds for c in r.rejected if c.reason)
    if n_acc:
        rb.efficiency = min(1.0, 0.4 + 0.4 * (explainable / max(n_rej, 1)) + 0.2 * (1.0 / (1 + n_rej)))
    else:
        rb.efficiency = 0.2

    rb.specialized_appendix_speedup = _specialized_speedup(episode)

    hard_ok = rb.correctness_ok and rb.semantics_ok and rb.scope_primary_ok
    if not hard_ok:
        rb.primary = 0.0
        return rb

    # Primary combines soft scores; measurement gate zeros speedup already.
    rb.primary = (
        0.45 * rb.speedup_score
        + 0.25 * rb.actionability
        + 0.20 * rb.workload_awareness
        + 0.10 * rb.efficiency
    )
    if not rb.measurement_ok:
        # Still allow partial credit for actionability/workload on exploratory runs.
        rb.primary = 0.35 * rb.actionability + 0.15 * rb.workload_awareness + 0.10 * rb.efficiency
        rb.notes.append("primary_exploratory_without_stable_measurement")
    return rb


def compare_primary(a: RewardBreakdown, b: RewardBreakdown) -> float:
    return b.primary - a.primary
