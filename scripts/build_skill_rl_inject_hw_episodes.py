#!/usr/bin/env python3
"""Build Skill-RL episodes + optimization_memory from real 910B inject HW results.

Uses maintainer-only labeled HW JSON (never agent-visible case trees as GT source).
Each strong-signal inject case becomes a restore episode:
  start = inject duration, end = baseline duration, strategy from problem_id map.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
INJECT_ROOT = REPO / "benchmarks" / "aprof_injected_ops"
OUT_DIR = REPO / "tests" / "fixtures" / "skill_rl" / "inject_hw_train"
MEMORY_PATH = REPO / "benchmarks" / "aprof_injected_ops" / ".maintainer_artifacts" / "optimization_memory.jsonl"

PROBLEM_TO_STRATEGY = {
    "tile_length_too_small": ("tiling.increase_tile_length", "tiling"),
    "tileLength_too_small": ("tiling.increase_tile_length", "tiling"),
    "tileLength_too_large": ("tiling.decrease_tile_length", "tiling"),
    "blockdim_too_small": ("tiling.increase_blockdim_when_underused", "tiling"),
    "underused_blockdim": ("ai_core_utilization.balance_blockdim", "ai_core_utilization"),
    "overlaunched_empty_cores": ("ai_core_utilization.balance_blockdim", "ai_core_utilization"),
    "redundant_copyin": ("data_movement.coalesce_copy", "data_movement"),
    "extra_copyout": ("data_movement.coalesce_copy", "data_movement"),
    "excessive_pipe_barrier": ("pipeline_parallel.remove_redundant_barrier", "pipeline_parallel"),
    "serial_copy_compute_copyout": ("pipeline_parallel.enable_double_buffer", "pipeline_parallel"),
    "ub_temp_overallocated": ("onchip_memory.reclaim_dead_buffer", "onchip_memory"),
    "scalar_loop_redundant": ("api_algorithm.reduce_scalar_loop", "api_algorithm"),
    "redundant_cast_or_vector_copy": ("api_algorithm.fuse_cast_path", "api_algorithm"),
}

FAMILY_CANON = {
    "blockdim": "tiling",
    "dynshape": "tiling",
    "tail": "tiling",
    "tilelen_large": "tiling",
    "tilelen_small": "tiling",
    "tilenum": "tiling",
}


def _baseline_key(payload: dict[str, Any]) -> str | None:
    for k in ("direct_invoke_baseline", "baseline"):
        if isinstance(payload.get(k), dict) and payload[k].get("task_duration_us") is not None:
            return k
    return None


def load_labeled(op: str) -> dict[str, Any] | None:
    p = INJECT_ROOT / op / ".ground_truth" / "remote_di_out" / "results_hw_with_labels.json"
    if p.is_file():
        return json.loads(p.read_text(encoding="utf-8"))
    p2 = INJECT_ROOT / op / ".ground_truth" / "remote_di_out" / "results_hw.json"
    if p2.is_file():
        return json.loads(p2.read_text(encoding="utf-8"))
    return None


def build_episode(op: str, case: str, base: dict[str, Any], inj: dict[str, Any], min_ratio: float) -> dict[str, Any] | None:
    bu = float(base["task_duration_us"])
    iu = float(inj["task_duration_us"])
    if bu <= 0 or iu / bu < min_ratio:
        return None
    if inj.get("verify_ok") is False and base.get("verify_ok") is False:
        return None
    pid = str(inj.get("problem_id_offline") or "unknown")
    strategy_id, family = PROBLEM_TO_STRATEGY.get(pid, (f"tiling.restore_{pid}", "tiling"))
    speedup = iu / bu
    # Historical remote runner used MSPROF_WARMUP default 3, launch-count 1.
    # Mark as partially stable: warm_up ok-ish, repeat weak → Skill-RL measurement gate learns D1.
    return {
        "schema_version": 1,
        "fixture_id": f"inject_restore_{op}_{case}",
        "source": "910B_results_hw_with_labels",
        "baseline_kind": "strong",
        "benchmark": {"suite": "aprof_injected_ops", "name": op, "case": case},
        "workload_model": {
            "workload_class": "normal",
            "operator_family": "unknown",
            "total_elements": None,
        },
        "metric_contract": {
            "primary_metric": "Task Duration(us)",
            "minimum_effect_threshold_pct": 3.0,
            "correctness_gate": "prefer verify_ok on baseline and inject",
        },
        "measurement_policy": {
            "warm_up": 3,
            "repeat": 1,
            "statistic": "single_task_duration_from_OpBasicInfo",
            "notes": "from prior remote_di_out; MSPROF_WARMUP default 3, LAUNCH_COUNT 1",
        },
        "overall_result": {
            "status": "accepted",
            "original_baseline": {"median_us": iu, "role": "injected_slow"},
            "final_production_best": {
                "median_us": bu,
                "role": "direct_invoke_baseline_restore",
                "scope": "production_safe",
                "speedup_vs_original": speedup,
            },
            "final_correctness": {
                "checked": 1 if base.get("verify_ok") else 0,
                "bad": 0 if base.get("verify_ok") else 1,
            },
        },
        "rounds": [
            {
                "round": 1,
                "label": f"restore_{pid}",
                "diagnosis_type": "true_bottleneck",
                "problem_family": family,
                "baseline": {
                    "config": {"injected": True, "problem_id": pid},
                    "samples_us": [iu],
                    "median_us": iu,
                    "correctness": {
                        "checked": 1 if inj.get("verify_ok") else 0,
                        "bad": 0 if inj.get("verify_ok") else 1,
                    },
                },
                "selected_candidate": {
                    "id": f"restore_{case}",
                    "strategy": f"revert inject / apply {strategy_id}",
                    "strategy_id": strategy_id,
                    "config": {"target": "direct_invoke_baseline"},
                    "code_changes": [
                        f"restore {op}/{case} knobs toward baseline for {pid}",
                    ],
                    "samples_us": [bu],
                    "median_us": bu,
                    "speedup_vs_round_baseline": speedup,
                    "scope": "production_safe",
                    "semantic_status": "preserved",
                    "correctness": {
                        "checked": 1 if base.get("verify_ok") else 0,
                        "bad": 0 if base.get("verify_ok") else 1,
                    },
                    "accepted": True,
                    "reason": f"910B inject/baseline ratio {speedup:.3f}",
                },
                "rejected_candidates": [
                    {
                        "id": "single_run_no_warmup_claim",
                        "strategy_id": strategy_id,
                        "accepted": False,
                        "reason": "single_run_duration_as_proof",
                        "scope": "production_safe",
                        "semantic_status": "preserved",
                        "median_us": bu,
                        "samples_us": [bu],
                        "correctness": {"checked": 1, "bad": 0},
                    }
                ],
            }
        ],
        "ground_truth_offline": {"problem_id": pid, "op": op, "case": case},
    }


def memory_record(ep: dict[str, Any]) -> dict[str, Any]:
    gt = ep.get("ground_truth_offline") or {}
    sel = ep["rounds"][0]["selected_candidate"]
    return {
        "op_name": ep["benchmark"]["name"],
        "case": gt.get("case"),
        "problem_id": gt.get("problem_id"),
        "shape": "from_case_metadata_if_present",
        "dtype": "unknown",
        "soc": "Ascend910B",
        "problem_family": ep["rounds"][0].get("problem_family"),
        "strategy_id": sel["strategy_id"],
        "status": "accepted",
        "metric_before": ep["overall_result"]["original_baseline"]["median_us"],
        "metric_after": ep["overall_result"]["final_production_best"]["median_us"],
        "speedup": ep["overall_result"]["final_production_best"]["speedup_vs_original"],
        "scope": "production_safe",
        "measurement_policy": ep["measurement_policy"],
        "source": "910B_inject_restore",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-ratio", type=float, default=1.5)
    ap.add_argument("--limit", type=int, default=0, help="0 = all")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    episodes: list[dict[str, Any]] = []
    for op_dir in sorted(INJECT_ROOT.iterdir()):
        if not op_dir.is_dir() or op_dir.name.startswith(".") or op_dir.name == "common":
            continue
        payload = load_labeled(op_dir.name)
        if not payload:
            continue
        bk = _baseline_key(payload)
        if not bk:
            continue
        base = payload[bk]
        for case, inj in payload.items():
            if not isinstance(inj, dict) or case in ("baseline", "direct_invoke_baseline"):
                continue
            if not str(case).startswith("op_"):
                continue
            if inj.get("task_duration_us") is None:
                continue
            ep = build_episode(op_dir.name, case, base, inj, args.min_ratio)
            if ep:
                episodes.append(ep)

    episodes.sort(key=lambda e: e["overall_result"]["final_production_best"]["speedup_vs_original"], reverse=True)
    if args.limit > 0:
        episodes = episodes[: args.limit]

    index = []
    for ep in episodes:
        path = OUT_DIR / f"{ep['fixture_id']}.json"
        path.write_text(json.dumps(ep, indent=2, ensure_ascii=False), encoding="utf-8")
        index.append({"id": ep["fixture_id"], "path": str(path.relative_to(REPO)), "speedup": ep["overall_result"]["final_production_best"]["speedup_vs_original"]})

    (OUT_DIR / "index.json").write_text(json.dumps({"count": len(index), "episodes": index}, indent=2), encoding="utf-8")

    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MEMORY_PATH.open("w", encoding="utf-8") as f:
        for ep in episodes:
            f.write(json.dumps(memory_record(ep), ensure_ascii=False) + "\n")

    print(f"wrote {len(episodes)} episodes -> {OUT_DIR}")
    print(f"wrote memory -> {MEMORY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
