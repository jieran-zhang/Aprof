"""Adapt optimization trajectory JSON fixtures into Episode objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aprof.skill_rl.models import (
    BaselineKind,
    Candidate,
    Episode,
    Measurement,
    Round,
    WorkloadModel,
)

FIXTURE_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "skill_rl"
FIXTURE_A = FIXTURE_DIR / "aprof_fast_gelu_three_round_optimization_summary.json"
FIXTURE_B = FIXTURE_DIR / "fast_gelu_2048_strong_baseline_episode.json"


def _load_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    return json.loads(text)


def _median(samples: list[float], fallback: float | None = None) -> float | None:
    if samples:
        s = sorted(samples)
        mid = len(s) // 2
        if len(s) % 2:
            return float(s[mid])
        return float((s[mid - 1] + s[mid]) / 2.0)
    return fallback


def _candidate_from_dict(raw: dict[str, Any] | None) -> Candidate | None:
    if not raw:
        return None
    corr = raw.get("correctness") or {}
    samples = [float(x) for x in raw.get("samples_us") or []]
    return Candidate(
        id=str(raw.get("id") or "unknown"),
        strategy_id=str(raw.get("strategy_id") or ""),
        strategy=str(raw.get("strategy") or ""),
        config=dict(raw.get("config") or {}),
        code_changes=list(raw.get("code_changes") or []),
        median_us=_median(samples, raw.get("median_us")),
        samples_us=samples,
        cv=raw.get("cv"),
        speedup_vs_round_baseline=raw.get("speedup_vs_round_baseline"),
        accepted=bool(raw.get("accepted", False)),
        reason=str(raw.get("reason") or ""),
        scope=raw.get("scope") or "production_safe",  # type: ignore[arg-type]
        semantic_status=str(raw.get("semantic_status") or "preserved"),
        correctness_bad=int(corr.get("bad") or 0),
        correctness_checked=int(corr.get("checked") or 0),
    )


def _measurement_from_block(
    block: dict[str, Any] | None,
    policy: dict[str, Any] | None = None,
) -> Measurement:
    block = block or {}
    policy = policy or {}
    samples = [float(x) for x in block.get("samples_us") or []]
    warm_up = int(policy.get("warm_up") or block.get("warm_up") or 0)
    # Infer repeat from samples when policy omitted (Fixture A style).
    repeat = int(policy.get("repeat") or block.get("repeat") or (len(samples) if samples else 0))
    return Measurement(
        warm_up=warm_up,
        repeat=repeat,
        statistic=str(policy.get("statistic") or block.get("statistic") or "median"),
        samples_us=samples,
        median_us=_median(samples, block.get("median_us")),
        cv=block.get("cv"),
    )


def adapt_fixture_a(data: dict[str, Any] | None = None) -> Episode:
    """Large-shape weak-start trajectory from origin/main summary."""
    data = data or _load_json(FIXTURE_A)
    overall = data.get("overall_result") or {}
    contract = data.get("metric_contract") or {}
    original = overall.get("original_baseline") or {}
    final = overall.get("final_best") or {}
    # Fixture A documents median over five samples → treat as stable measurement.
    policy = {"warm_up": 10, "repeat": 5, "statistic": "median"}
    rounds: list[Round] = []
    strategy_ids: list[str] = []
    for raw_round in data.get("rounds") or []:
        selected = _candidate_from_dict(raw_round.get("selected_candidate"))
        if selected and not selected.strategy_id:
            # Infer actionable ids from labels / strategy text.
            label = str(raw_round.get("label") or "")
            if "launch" in label or "multicore" in (selected.strategy or ""):
                selected.strategy_id = "tiling.increase_blockdim_when_underused"
            elif "tile_length" in label:
                selected.strategy_id = "tiling.increase_tile_length"
            elif "dead_buffer" in label or "onchip" in label:
                selected.strategy_id = "onchip_memory.reclaim_dead_buffer"
        if selected and selected.strategy_id:
            strategy_ids.append(selected.strategy_id)
        rejected = []
        for r in raw_round.get("rejected_candidates") or []:
            c = _candidate_from_dict(r)
            if c:
                rejected.append(c)
        # Also harvest non-selected from candidates[] if present.
        for r in raw_round.get("candidates") or []:
            c = _candidate_from_dict(r)
            if c and (not selected or c.id != selected.id) and not c.accepted:
                rejected.append(c)
        base = raw_round.get("baseline") or {}
        meas = _measurement_from_block(base, policy)
        if selected and selected.samples_us:
            meas = _measurement_from_block(
                {
                    "samples_us": selected.samples_us,
                    "median_us": selected.median_us,
                    "cv": selected.cv,
                },
                policy,
            )
        rounds.append(
            Round(
                round_index=int(raw_round.get("round") or len(rounds) + 1),
                label=str(raw_round.get("label") or f"round_{len(rounds)+1}"),
                baseline_median_us=base.get("median_us"),
                baseline_config=dict(base.get("config") or {}),
                selected=selected,
                rejected=rejected,
                measurement=meas,
            )
        )
    corr = overall.get("final_correctness") or {}
    ep = Episode(
        case_id="fast_gelu_large_weak_start",
        op_name=str((data.get("benchmark") or {}).get("name") or "fast_gelu"),
        scenario_id="fast_gelu_large_shape",
        baseline_kind="naive",
        source="origin/main:tests/aprof_fast_gelu_three_round_optimization_summary.json",
        original_median_us=original.get("median_us"),
        final_median_us=final.get("median_us"),
        combined_speedup=overall.get("combined_speedup_vs_original"),
        workload=WorkloadModel(
            total_elements=16777216,
            dtype_bytes=4,
            workload_class="large",
            block_dim=int(original.get("blockdim") or 1),
            operator_family="elementwise",
        ),
        diagnosis_type="true_bottleneck",
        measurement=Measurement(
            warm_up=10,
            repeat=5,
            statistic="median",
            median_us=final.get("median_us"),
            samples_us=[],
            cv=None,
        ),
        rounds=rounds,
        actionable_strategy_ids=list(dict.fromkeys(strategy_ids)),
        min_effect_pct=float(contract.get("minimum_effect_threshold_pct") or 3.0),
        metadata={"correctness": corr, "fixture": "A"},
    )
    return ep


def adapt_fixture_b(data: dict[str, Any] | None = None) -> Episode:
    """Small-shape strong-baseline narrative (collaborator synthetic, schema-aligned)."""
    data = data or _load_json(FIXTURE_B)
    overall = data.get("overall_result") or {}
    policy = data.get("measurement_policy") or {}
    wl = data.get("workload_model") or {}
    original = overall.get("original_baseline") or {}
    prod = overall.get("final_production_best") or {}
    rounds: list[Round] = []
    strategy_ids: list[str] = []
    for raw_round in data.get("rounds") or []:
        selected = _candidate_from_dict(raw_round.get("selected_candidate"))
        if selected and selected.strategy_id:
            strategy_ids.append(selected.strategy_id)
        rejected: list[Candidate] = []
        for r in raw_round.get("rejected_candidates") or []:
            c = _candidate_from_dict(r)
            if c:
                rejected.append(c)
        for r in raw_round.get("candidates") or []:
            c = _candidate_from_dict(r)
            if not c:
                continue
            if selected and c.id == selected.id:
                continue
            if not c.accepted:
                rejected.append(c)
            elif c.scope == "benchmark_specialized":
                # Keep specialized visible even if "accepted" as appendix.
                pass
        base = raw_round.get("baseline") or {}
        rounds.append(
            Round(
                round_index=int(raw_round.get("round") or len(rounds) + 1),
                label=str(raw_round.get("label") or ""),
                baseline_median_us=base.get("median_us"),
                baseline_config=dict(base.get("config") or {}),
                selected=selected,
                rejected=rejected,
                measurement=_measurement_from_block(base, policy),
            )
        )
    corr = overall.get("final_correctness") or {}
    return Episode(
        case_id=str(data.get("fixture_id") or "fast_gelu_2048_strong_baseline"),
        op_name=str((data.get("benchmark") or {}).get("name") or "fast_gelu"),
        scenario_id="fast_gelu_small_shape_2048",
        baseline_kind=str(data.get("baseline_kind") or "strong"),  # type: ignore[arg-type]
        source=str(data.get("source") or "collaborator_report_synthetic"),
        original_median_us=original.get("median_us"),
        final_median_us=prod.get("median_us"),
        combined_speedup=prod.get("speedup_vs_original"),
        workload=WorkloadModel(
            total_elements=wl.get("total_elements"),
            dtype_bytes=wl.get("dtype_bytes"),
            workload_class=str(wl.get("workload_class") or "small"),
            block_dim=wl.get("block_dim"),
            operator_family=str(wl.get("operator_family") or "elementwise"),
        ),
        diagnosis_type="true_bottleneck",
        measurement=_measurement_from_block(
            {"samples_us": [prod.get("median_us")] if prod.get("median_us") else [], "median_us": prod.get("median_us")},
            policy,
        ),
        rounds=rounds,
        actionable_strategy_ids=list(dict.fromkeys(strategy_ids)),
        min_effect_pct=float((data.get("metric_contract") or {}).get("minimum_effect_threshold_pct") or 3.0),
        metadata={
            "correctness": corr,
            "specialized_appendix": overall.get("specialized_appendix"),
            "fixture": "B",
        },
    )


def load_dual_fixtures() -> list[Episode]:
    return [adapt_fixture_a(), adapt_fixture_b()]
