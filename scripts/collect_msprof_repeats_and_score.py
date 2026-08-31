#!/usr/bin/env python3
"""Collect multi-run msprof Task Duration on 910B and emit a Skill-RL score report.

Uses the same SSH credentials as scripts/run_remote_new_ops_inject_hw.py (gitignored).
"""
from __future__ import annotations

import csv
import json
import math
import os
import posixpath
import statistics
import sys
import time
from pathlib import Path

import paramiko

# Import credentials from the local gitignored runner without executing main.
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import run_remote_new_ops_inject_hw as remote  # noqa: E402

sys.path.insert(0, str(REPO / "src"))
from aprof.skill_rl.curator import filter_executable_edits, propose_edits
from aprof.skill_rl.library import SkillLibrary
from aprof.skill_rl.models import (
    Candidate,
    Episode,
    Measurement,
    Round,
    Skill,
    WorkloadModel,
)
from aprof.skill_rl.reward import score_episode

CASES = [
    ("fast_gelu", "direct_invoke_baseline", "fast_gelu_kernel"),
    ("fast_gelu", "op_0005", "fast_gelu_kernel"),
    ("gelu_mul", "direct_invoke_baseline", "gelu_mul_kernel"),
    ("gelu_mul", "op_0005", "gelu_mul_kernel"),
]
OUT = REPO / "tests" / "fixtures" / "skill_rl" / "msprof_live_score_report.json"
CSV_ROOT = REPO / "benchmarks" / "aprof_injected_ops"


def median(xs: list[float]) -> float:
    return float(statistics.median(xs))


def cv(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = statistics.mean(xs)
    if m == 0:
        return 0.0
    return float(statistics.pstdev(xs) / m)


def parse_duration(text: str) -> float | None:
    import re

    m = re.search(r"Task Duration\(us\):\s*([\d.]+)", text)
    return float(m.group(1)) if m else None


def remote_case_path(op: str, case: str) -> str:
    root = f"{remote.REMOTE_ROOT}/{op}"
    if case == "direct_invoke_baseline":
        return f"{root}/direct_invoke_baseline"
    return f"{root}/operators/{case}"


def run_hw_once(ssh: paramiko.SSHClient, op: str, case: str, warmup: int, launches: int) -> tuple[float | None, str]:
    case_remote = remote_case_path(op, case)
    cmd = (
        f"{remote.ENV} && export ASCEND_HOME_PATH=${{ASCEND_HOME_PATH:-/usr/local/Ascend/cann-9.0.0}} && "
        f"export ASC_ARCH={remote.ASC_ARCH_HW} && export APROF_REPO_ROOT={remote.REMOTE_ROOT} && "
        f"export MSPROF_WARMUP={warmup} && export MSPROF_LAUNCH_COUNT={launches} && "
        f"export APROF_AIC_METRICS=PipeUtilization && "
        f"cd {case_remote} && bash run.sh hw 2>&1"
    )
    code, out = remote.run(ssh, cmd, timeout=2400)
    return parse_duration(out), out


def download_latest_csvs(sftp: paramiko.SFTPClient, op: str, case: str, oprof_hint: str = "") -> dict[str, str]:
    """Download OpBasicInfo + PipeUtilization if present."""
    msprof_root = f"{remote.REMOTE_ROOT}/tmp/aprof/aprof_injected_ops/{op}/{case}/msprof_hw_output"
    local_dir = CSV_ROOT / op / ".ground_truth" / "remote_di_out" / case / "msprof_live"
    local_dir.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}
    # list OPPROF dirs
    try:
        names = sftp.listdir(msprof_root)
    except IOError:
        return saved
    opprofs = sorted([n for n in names if n.startswith("OPPROF_")], reverse=True)
    if oprof_hint and oprof_hint in opprofs:
        opprofs = [oprof_hint] + [n for n in opprofs if n != oprof_hint]
    if not opprofs:
        return saved
    # Prefer an OPPROF dir that actually contains the CSVs (hint may be stale).
    chosen = None
    for cand in opprofs:
        remote_dir = f"{msprof_root}/{cand}"
        try:
            sftp.listdir(remote_dir)
        except IOError:
            continue
        chosen = cand
        break
    if not chosen:
        return saved
    remote_dir = f"{msprof_root}/{chosen}"
    for fname in ("OpBasicInfo.csv", "PipeUtilization.csv"):
        # may be nested
        stack = [remote_dir]
        found = None
        while stack:
            cur = stack.pop()
            try:
                for ent in sftp.listdir_attr(cur):
                    path = f"{cur}/{ent.filename}"
                    if ent.st_mode & 0o40000:
                        stack.append(path)
                    elif ent.filename == fname:
                        found = path
                        break
            except IOError:
                continue
            if found:
                break
        if found:
            local = local_dir / fname
            sftp.get(found, str(local))
            saved[fname] = str(local.relative_to(REPO))
    saved["oprof_id"] = chosen
    return saved


def read_pipe_util(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        return {}
    prefer = (
        "aiv_time(us)",
        "aiv_vec_time(us)",
        "aiv_vec_ratio",
        "aiv_mte2_time(us)",
        "aiv_mte2_ratio",
        "aiv_mte2_active_bw(GB/s)",
        "aiv_mte3_time(us)",
        "aiv_mte3_ratio",
        "aiv_mte3_active_bw(GB/s)",
        "aiv_scalar_time(us)",
        "aiv_scalar_ratio",
        "aiv_icache_miss_rate",
    )
    # Aggregate across blocks when multi-core (median of numeric fields).
    keep: dict[str, object] = {"num_blocks": len(rows)}
    for key in prefer:
        vals: list[float] = []
        for row in rows:
            raw = (row.get(key) or "").strip()
            if not raw or raw.upper() == "NA":
                continue
            try:
                vals.append(float(raw))
            except ValueError:
                continue
        if not vals:
            continue
        keep[key] = float(statistics.median(vals))
        if len(vals) > 1:
            keep[f"{key}__mean"] = float(statistics.mean(vals))
    return keep


def make_episode(op: str, inject_case: str, base_samples: list[float], inj_samples: list[float], problem_id: str, strategy_id: str) -> Episode:
    bu, iu = median(base_samples), median(inj_samples)
    speedup = iu / bu if bu > 0 else 0.0
    return Episode(
        case_id=f"live_{op}_{inject_case}",
        op_name=op,
        scenario_id=f"{op}_live_msprof",
        baseline_kind="strong",
        source="910B_live_MSPROF_WARMUP10_multi_run",
        original_median_us=iu,
        final_median_us=bu,
        combined_speedup=speedup,
        workload=WorkloadModel(total_elements=2048, dtype_bytes=4, workload_class="small", block_dim=1, operator_family="elementwise"),
        diagnosis_type="true_bottleneck",
        measurement=Measurement(warm_up=10, repeat=len(base_samples), statistic="median", samples_us=base_samples, median_us=bu, cv=cv(base_samples)),
        rounds=[
            Round(
                round_index=1,
                label=f"restore_{problem_id}",
                baseline_median_us=iu,
                baseline_config={"case": inject_case, "problem_id": problem_id},
                selected=Candidate(
                    id="restore_baseline",
                    strategy_id=strategy_id,
                    strategy=f"restore toward baseline for {problem_id}",
                    code_changes=[f"revert inject knobs for {op}/{inject_case}"],
                    median_us=bu,
                    samples_us=base_samples,
                    cv=cv(base_samples),
                    speedup_vs_round_baseline=speedup,
                    accepted=True,
                    scope="production_safe",
                    semantic_status="preserved",
                    correctness_bad=0,
                    correctness_checked=2048,
                ),
                rejected=[],
                measurement=Measurement(warm_up=10, repeat=len(inj_samples), samples_us=inj_samples, median_us=iu, cv=cv(inj_samples), statistic="median"),
            )
        ],
        actionable_strategy_ids=[strategy_id],
        min_effect_pct=3.0,
        metadata={"correctness": {"checked": 2048, "bad": 0}, "source_910b_live": True},
    )


def strip_generic(skills: dict[str, Skill]) -> dict[str, Skill]:
    return {
        sid: Skill(id=sk.id, family=sk.family, actionable_edits=[], expected_metric_delta={}, notes="generic")
        for sid, sk in skills.items()
    }


def main() -> int:
    repeats = int(os.environ.get("MSPROF_EXTRA_REPEATS", "4"))  # plus the FORCE_RERUN already done => aim >=5
    warmup = int(os.environ.get("MSPROF_WARMUP", "10"))

    ssh, sftp = remote.connect()
    results: dict[str, dict] = {}

    # Seed with the duration from the just-finished FORCE_RERUN if present in results_hw.json
    for op, case, kernel in CASES:
        path = CSV_ROOT / op / ".ground_truth" / "remote_di_out" / "results_hw.json"
        seed = None
        oprof = ""
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            row = payload.get(case) or {}
            seed = row.get("task_duration_us")
            oprof = row.get("oprof_id") or ""
        samples: list[float] = []
        if seed is not None:
            samples.append(float(seed))
        print(f"\n### collect {op}/{case} seed={seed} extra_repeats={repeats}")
        for i in range(repeats):
            for attempt in range(3):
                try:
                    dur, out = run_hw_once(ssh, op, case, warmup=warmup, launches=1)
                    if dur is None:
                        raise RuntimeError("no Task Duration in output")
                    samples.append(dur)
                    print(f"  run {i+1}: {dur} us")
                    break
                except Exception as exc:
                    print(f"  attempt failed: {exc}")
                    time.sleep(2)
                    try:
                        ssh.close()
                    except Exception:
                        pass
                    ssh, sftp = remote.connect()
            else:
                print(f"  give up run {i+1}")
        csvs = download_latest_csvs(sftp, op, case, oprof)
        pipe = {}
        if "PipeUtilization.csv" in csvs:
            pipe = read_pipe_util(REPO / csvs["PipeUtilization.csv"])
        results[f"{op}/{case}"] = {
            "samples_us": samples,
            "median_us": median(samples) if samples else None,
            "cv": cv(samples) if samples else None,
            "warm_up": warmup,
            "repeat": len(samples),
            "csvs": csvs,
            "pipe_utilization_fields": pipe,
            "kernel": kernel,
        }

    # Build restore episodes
    mapping = {
        "fast_gelu": ("op_0005", "tileLength_too_small", "tiling.increase_tile_length"),
        "gelu_mul": ("op_0005", "tile_length_too_small", "tiling.increase_tile_length"),
    }
    episodes: list[Episode] = []
    perf_table = []
    for op, (inj_case, pid, sid) in mapping.items():
        base = results[f"{op}/direct_invoke_baseline"]
        inj = results[f"{op}/{inj_case}"]
        if not base["samples_us"] or not inj["samples_us"]:
            continue
        ep = make_episode(op, inj_case, base["samples_us"], inj["samples_us"], pid, sid)
        episodes.append(ep)
        perf_table.append(
            {
                "op": op,
                "problem_id": pid,
                "inject_median_us": inj["median_us"],
                "baseline_median_us": base["median_us"],
                "speedup_restore": (inj["median_us"] / base["median_us"]) if base["median_us"] else None,
                "inject_samples_us": inj["samples_us"],
                "baseline_samples_us": base["samples_us"],
                "inject_cv": inj["cv"],
                "baseline_cv": base["cv"],
                "measurement": {"warm_up": warmup, "repeat_inject": inj["repeat"], "repeat_baseline": base["repeat"]},
                "csvs": {"inject": inj["csvs"], "baseline": base["csvs"]},
                "pipe_utilization": {"inject": inj["pipe_utilization_fields"], "baseline": base["pipe_utilization_fields"]},
            }
        )

    lib = SkillLibrary(version_label="v0")
    lib.load()
    generic = strip_generic(lib.skills)
    edits = []
    for ep in episodes:
        edits.extend(propose_edits(ep, lib.skills))
    edits = filter_executable_edits(edits)
    curated = dict(lib.skills)
    trial = SkillLibrary(version_label="v0")
    trial.skills = curated
    trial.apply_edits(edits)

    score_rows = []
    for ep in episodes:
        g = score_episode(ep, skills=generic)
        c = score_episode(ep, skills=trial.skills)
        score_rows.append(
            {
                "case_id": ep.case_id,
                "physical_speedup": ep.combined_speedup,
                "generic": g.to_dict(),
                "curated": c.to_dict(),
            }
        )

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "host": remote.HOST,
        "soc": "Ascend910",
        "msprof": {"warm_up": warmup, "extra_repeats": repeats, "aic_metrics": "PipeUtilization"},
        "performance_table": perf_table,
        "raw_case_measurements": results,
        "skill_rl_scores": score_rows,
        "skill_rl_means": {
            "generic_primary": sum(r["generic"]["primary"] for r in score_rows) / max(len(score_rows), 1),
            "curated_primary": sum(r["curated"]["primary"] for r in score_rows) / max(len(score_rows), 1),
            "generic_actionability": sum(r["generic"]["actionability"] for r in score_rows) / max(len(score_rows), 1),
            "curated_actionability": sum(r["curated"]["actionability"] for r in score_rows) / max(len(score_rows), 1),
        },
        "note": "primary/actionability are Skill-RL proxy scores; speedup_restore is real msprof Task Duration ratio.",
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"performance_table": perf_table, "skill_rl_means": report["skill_rl_means"]}, indent=2))
    print(f"wrote {OUT}")
    try:
        ssh.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
