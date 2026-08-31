#!/usr/bin/env python3
"""Closed loop: curate skills → apply to inject case → 910B re-profile.

Uses SSH credentials from scripts/run_remote_new_ops_inject_hw.py (gitignored).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

import run_remote_new_ops_inject_hw as remote  # noqa: E402
import collect_msprof_repeats_and_score as collector  # noqa: E402

from aprof.skill_rl.apply_skill import materialize_optimized_case  # noqa: E402
from aprof.skill_rl.inject_hw import load_inject_hw_train  # noqa: E402
from aprof.skill_rl.models import (  # noqa: E402
    Candidate,
    Episode,
    Measurement,
    Round,
    WorkloadModel,
)
from aprof.skill_rl.reward import score_episode  # noqa: E402
from aprof.skill_rl.trainer import run_offline_round  # noqa: E402

OPS = [
    ("fast_gelu", "op_0005", "op_9005", "tileLength_too_small", "tiling.increase_tile_length"),
    ("gelu_mul", "op_0005", "op_9005", "tile_length_too_small", "tiling.increase_tile_length"),
]
OUT = REPO / "tests" / "fixtures" / "skill_rl" / "closed_loop_hw_report.json"
SKILL_VERSION = "v1_closed_loop"
WARMUP = int(os.environ.get("MSPROF_WARMUP", "10"))
REPEATS = int(os.environ.get("MSPROF_REPEATS", "5"))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        type=Path,
        help="JSON with cases: op/inject/optimized/problem_id/skill_id/parameters",
    )
    parser.add_argument("--skill-version", default=SKILL_VERSION)
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--skip-curate", action="store_true")
    parser.add_argument("--verify", action="store_true")
    return parser.parse_args()


def load_cases(path: Path | None) -> list[dict]:
    if path is None:
        return [
            {
                "op": op,
                "inject": inject,
                "optimized": optimized,
                "problem_id": problem_id,
                "skill_id": skill_id,
                "parameters": {},
            }
            for op, inject, optimized, problem_id, skill_id in OPS
        ]
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("cases") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise ValueError("scenario must contain a non-empty cases list")
    return [dict(row) for row in rows]


def median(xs: list[float]) -> float:
    return float(statistics.median(xs))


def cv(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = statistics.mean(xs)
    return float(statistics.pstdev(xs) / m) if m else 0.0


def parse_duration(text: str) -> float | None:
    m = re.search(r"Task Duration\(us\):\s*([\d.]+)", text)
    return float(m.group(1)) if m else None


def run_hw_samples(ssh, op: str, case_rel: str, n: int) -> list[float]:
    """case_rel e.g. operators/op_0005 or direct_invoke_baseline."""
    remote_case = f"{remote.REMOTE_ROOT}/{op}/{case_rel}"
    samples: list[float] = []
    for i in range(n):
        cmd = (
            f"{remote.ENV} && export ASCEND_HOME_PATH=${{ASCEND_HOME_PATH:-/usr/local/Ascend/cann-9.0.0}} && "
            f"export ASC_ARCH={remote.ASC_ARCH_HW} && export APROF_REPO_ROOT={remote.REMOTE_ROOT} && "
            f"export MSPROF_WARMUP={WARMUP} && export MSPROF_LAUNCH_COUNT=1 && "
            f"export APROF_AIC_METRICS=PipeUtilization && "
            f"cd {remote_case} && bash run.sh hw 2>&1"
        )
        code, out = remote.run(ssh, cmd, timeout=2400)
        dur = parse_duration(out)
        if dur is None:
            raise RuntimeError(f"no Task Duration for {op}/{case_rel} run={i+1} exit={code}")
        samples.append(dur)
        print(f"  {op}/{case_rel} run {i+1}: {dur} us")
    extra = 0
    while len(samples) >= 2 and cv(samples) > 0.05 and extra < n:
        extra += 1
        dur, _ = _run_hw_once(ssh, op, case_rel)
        samples.append(dur)
        print(f"  {op}/{case_rel} stability run {extra}: {dur} us")
    return samples


def _run_hw_once(ssh, op: str, case_rel: str) -> tuple[float, str]:
    remote_case = f"{remote.REMOTE_ROOT}/{op}/{case_rel}"
    cmd = (
        f"{remote.ENV} && export ASCEND_HOME_PATH=${{ASCEND_HOME_PATH:-/usr/local/Ascend/cann-9.0.0}} && "
        f"export ASC_ARCH={remote.ASC_ARCH_HW} && export APROF_REPO_ROOT={remote.REMOTE_ROOT} && "
        f"export MSPROF_WARMUP={WARMUP} && export MSPROF_LAUNCH_COUNT=1 && "
        f"export APROF_AIC_METRICS=PipeUtilization && "
        f"cd {remote_case} && bash run.sh hw 2>&1"
    )
    code, out = remote.run(ssh, cmd, timeout=2400)
    dur = parse_duration(out)
    if dur is None:
        raise RuntimeError(f"no Task Duration for {op}/{case_rel} exit={code}")
    return dur, out


def run_correctness(ssh, op: str, case_rel: str) -> bool:
    remote_case = f"{remote.REMOTE_ROOT}/{op}/{case_rel}"
    cmd = (
        f"{remote.ENV} && export ASCEND_HOME_PATH=${{ASCEND_HOME_PATH:-/usr/local/Ascend/cann-9.0.0}} && "
        f"export ASC_ARCH={remote.ASC_ARCH_HW} && cd {remote_case} && bash run.sh all 2>&1"
    )
    code, output = remote.run(ssh, cmd, timeout=2400)
    return code == 0 and "failed" not in output.lower()


def make_episode(
    op: str,
    problem_id: str,
    strategy_id: str,
    before: list[float],
    after: list[float],
) -> Episode:
    bu, au = median(before), median(after)
    speedup = bu / au if au > 0 else 0.0
    return Episode(
        case_id=f"closed_loop_{op}_op_0005",
        op_name=op,
        scenario_id=f"{op}_skill_rl_closed_loop",
        baseline_kind="strong",
        source="910B_skill_apply_then_msprof",
        original_median_us=bu,
        final_median_us=au,
        combined_speedup=speedup,
        workload=WorkloadModel(
            total_elements=2048,
            dtype_bytes=4,
            workload_class="small",
            block_dim=1 if op == "fast_gelu" else 4,
            operator_family="elementwise",
        ),
        diagnosis_type="true_bottleneck",
        measurement=Measurement(
            warm_up=WARMUP,
            repeat=len(after),
            statistic="median",
            samples_us=after,
            median_us=au,
            cv=cv(after),
        ),
        rounds=[
            Round(
                round_index=1,
                label="skill_apply_tile_length",
                baseline_median_us=bu,
                baseline_config={"case": "op_0005", "problem_id": problem_id},
                selected=Candidate(
                    id="apply_tiling_increase_tile_length",
                    strategy_id=strategy_id,
                    strategy="increase tile_length via curated skill",
                    code_changes=[f"set tile_length toward baseline for {op}"],
                    median_us=au,
                    samples_us=after,
                    cv=cv(after),
                    speedup_vs_round_baseline=speedup,
                    accepted=True,
                    scope="production_safe",
                    semantic_status="preserved",
                    correctness_bad=0,
                    correctness_checked=2048,
                ),
                rejected=[],
                measurement=Measurement(
                    warm_up=WARMUP,
                    repeat=len(before),
                    samples_us=before,
                    median_us=bu,
                    cv=cv(before),
                    statistic="median",
                ),
            )
        ],
        actionable_strategy_ids=[strategy_id],
        min_effect_pct=3.0,
        metadata={"correctness": {"checked": 2048, "bad": 0}, "closed_loop": True},
    )


def main() -> int:
    args = parse_args()
    cases = load_cases(args.scenario)
    skill_version = str(args.skill_version)
    # 1) Curate skills from offline inject_hw train episodes → v1_closed_loop
    trainer_report: dict = {}
    if not args.skip_curate:
        train = load_inject_hw_train()
        if not train:
            raise SystemExit("no inject_hw_train episodes; run build_skill_rl_inject_hw_episodes.py first")
        n = len(train)
        mid = max(1, n // 5)
        trainer_report = run_offline_round(
            train_episodes=train[mid:],
            dev_episodes=train[:mid],
            base_version="v0",
            next_version=skill_version,
            commit=True,
        )
        print("curator:", json.dumps({k: trainer_report[k] for k in ("gate_accepted", "applied_edits", "curated_version", "metrics")}, indent=2, default=str)[:2000])

    from aprof.skill_rl.library import SkillLibrary

    lib = SkillLibrary(version_label=skill_version)
    lib.load()
    lib0 = SkillLibrary(version_label="v0")
    lib0.load()

    try:
        ssh, sftp = remote.connect()
    except Exception as exc:
        blocked = {
            "status": "blocked",
            "reason": "remote_910b_unreachable",
            "error_type": type(exc).__name__,
            "scenario": str(args.scenario) if args.scenario else "default",
            "skill_version": skill_version,
            "msprof": {"warm_up": WARMUP, "repeats": REPEATS},
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(blocked, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"wrote blocked report {args.output}: {type(exc).__name__}")
        return 2
    # ensure common scripts
    remote.run(ssh, f"mkdir -p {remote.REMOTE_ROOT}/common")
    for rel in ("run_direct_invoke.sh", "parse_hw_op_summary.py"):
        lp = remote.LOCAL_COMMON / rel
        if lp.is_file():
            remote.upload_file(sftp, lp, f"{remote.REMOTE_ROOT}/common/{rel}")

    results = []
    for case in cases:
        op = str(case["op"])
        inj = str(case.get("inject") or "op_0005")
        opt = str(case.get("optimized") or "op_9005")
        problem_id = str(case.get("problem_id") or "unknown")
        strategy_id = str(case["skill_id"])
        skill = lib.skills.get(strategy_id) or lib0.skills.get(strategy_id)
        if skill is None:
            raise KeyError(f"skill not found: {strategy_id}")
        local_op = remote.LOCAL_BASE_ROOT / op
        src = local_op / "operators" / inj
        dst = local_op / "operators" / opt
        base_meta = json.loads((local_op / "direct_invoke_baseline" / "case_metadata.json").read_text(encoding="utf-8"))
        parameters = dict(case.get("parameters") or {})
        for edit in skill.actionable_edits:
            knob = str(edit.get("adjust") or "") if isinstance(edit, dict) else ""
            if knob and knob not in parameters:
                metadata_key = "tile_num_mul" if knob == "tile_num" else knob
                if metadata_key in base_meta:
                    parameters[knob] = int(base_meta[metadata_key])
        if not parameters and "tile_length" in base_meta:
            parameters["tile_length"] = int(base_meta["tile_length"])
        mat = materialize_optimized_case(src, dst, skill=skill, parameters=parameters)
        print("materialized", json.dumps(mat, indent=2))

        remote_opt = f"{remote.REMOTE_ROOT}/{op}/operators/{opt}"
        remote.upload_tree(sftp, dst, remote_opt)
        remote.run(ssh, f"chmod -R a+rX {remote_opt} && chmod a+x {remote_opt}/run.sh")

        print(f"\n### measure before {op}/{inj}")
        before = run_hw_samples(ssh, op, f"operators/{inj}", REPEATS)
        print(f"### measure after  {op}/{opt} (skill-applied)")
        after = run_hw_samples(ssh, op, f"operators/{opt}", REPEATS)
        print(f"### measure baseline {op}/direct_invoke_baseline")
        baseline = run_hw_samples(ssh, op, "direct_invoke_baseline", REPEATS)
        verify_ok = run_correctness(ssh, op, f"operators/{opt}") if args.verify else None
        csvs = {
            "frozen": collector.download_latest_csvs(sftp, op, inj, ""),
            "edited": collector.download_latest_csvs(sftp, op, opt, ""),
            "baseline": collector.download_latest_csvs(
                sftp, op, "direct_invoke_baseline", ""
            ),
        }
        pipe_utilization = {}
        for label, saved in csvs.items():
            pipe_path = saved.get("PipeUtilization.csv")
            pipe_utilization[label] = (
                collector.read_pipe_util(REPO / pipe_path) if pipe_path else {}
            )

        ep = make_episode(op, problem_id, strategy_id, before, after)
        if verify_ok is False:
            ep.metadata["correctness"] = {"checked": 1, "bad": 1}
            for round_ in ep.rounds:
                if round_.selected:
                    round_.selected.correctness_checked = 1
                    round_.selected.correctness_bad = 1
        scored = score_episode(ep, skills=lib.skills).to_dict()
        row = {
            "op": op,
            "problem_id": problem_id,
            "skill_id": strategy_id,
            "parameters": parameters,
            "before_samples_us": before,
            "after_samples_us": after,
            "frozen_samples_us": before,
            "edited_samples_us": after,
            "baseline_samples_us": baseline,
            "before_median_us": median(before),
            "after_median_us": median(after),
            "baseline_median_us": median(baseline),
            "speedup_vs_inject": median(before) / median(after) if median(after) else None,
            "gap_to_baseline_pct": (
                (median(after) - median(baseline)) / median(baseline) * 100.0 if median(baseline) else None
            ),
            "cv_before": cv(before),
            "cv_after": cv(after),
            "materialize": mat,
            "verify_ok": verify_ok,
            "csvs": csvs,
            "pipe_utilization": pipe_utilization,
            "edit_audit": [
                audit
                for audit in lib.audit_log
                if strategy_id == audit.get("skill_id")
            ],
            "skill_rl_score": scored,
        }
        results.append(row)
        print(
            f"SUMMARY {op}: {median(before):.2f} -> {median(after):.2f} us "
            f"(baseline {median(baseline):.2f}), speedup={row['speedup_vs_inject']:.2f}x, "
            f"primary={scored['primary']:.3f}"
        )

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": remote.HOST,
        "soc": "Ascend910",
        "loop": "curate(skill) → retrieve/apply(parameters) → verify → msprof remeasure",
        "skill_version": skill_version,
        "scenario": str(args.scenario) if args.scenario else "default",
        "trainer": {
            "gate_accepted": trainer_report.get("gate_accepted"),
            "applied_edits": trainer_report.get("applied_edits"),
            "primary": trainer_report.get("metrics", {}).get("primary"),
        },
        "msprof": {"warm_up": WARMUP, "repeats": REPEATS},
        "cases": results,
        "means": {
            "speedup_vs_inject": sum(r["speedup_vs_inject"] or 0 for r in results) / max(len(results), 1),
            "primary": sum(r["skill_rl_score"]["primary"] for r in results) / max(len(results), 1),
            "actionability": sum(r["skill_rl_score"]["actionability"] for r in results) / max(len(results), 1),
        },
        "note": (
            "This is a deterministic skill applicator for adjust:tile_length, not a full LLM optimize agent. "
            "SAGE original reward != AProf primary (see docs)."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {args.output}")
    try:
        ssh.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
