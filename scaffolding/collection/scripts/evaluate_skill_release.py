#!/usr/bin/env python3
"""Prepare and execute the frozen three-arm, one-candidate validation matrix."""
from __future__ import annotations
from task_budget import budget_seconds, evaluation_budget, checked_pointer, collection_policy

import argparse
import asyncio
import datetime as dt
import difflib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import random
import shutil
import sqlite3
import subprocess
import sys
import time

from isolated_eval_worker import require_worker_build_budget_enforcement, run as run_worker, sha
from eval_tool_broker import BUDGET_POLICY
from run_aprof_job import dump, run as run_job

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scaffolding/tools"))

ARMS = ("baseline", "skill-only", "skill-plus-wiki")
VALIDATION_OPERATORS = ("dynamic_quant", "gelu", "gqa", "group_norm", "weight_quant_batch_matmul")
MODEL_BUDGETS = {"proposer": None, "reviewer": None}
PUBLICATION_CRITERION = {
    "primary_arm": "skill-plus-wiki", "baseline_arm": "baseline",
    "paired_unit": "operator,seed", "paired_units": 15,
    "statistic": "geomean of paired deployed speedup ratios",
    "bootstrap_resamples": 10000, "bootstrap_seed": 4101,
    "confidence_interval": "percentile two-sided 95%; lower bound > 1",
    "correctness": "no paired task loses correctness",
    "failed_candidate": "original baseline fallback speedup 1; retain failure and full cost",
    "missing_trial": "publication forbidden", "skill_only": "reported ablation, cannot rescue primary",
}


def load(path):
    return json.loads(Path(path).read_text())


def valid_model_cost(proposer_tokens, reviewer_tokens, total_tokens):
    """Usage is an audited cost; only wall time limits an admitted task."""
    return (all(type(value) is int and value >= 0 for value in (proposer_tokens, reviewer_tokens, total_tokens))
        and total_tokens == proposer_tokens + reviewer_tokens)


def _pointer(path):
    return {"path": str(Path(path).resolve()), "sha256": sha(path)}


def _trial_job(output, row, manifest):
    directory = output / "runs" / row["run_id"]
    release = Path(manifest["libraries"]["candidate"]["path"])
    device = str(manifest["evaluator"]["physical_device"])
    return {"job_id": row["run_id"], "argv": [str(Path(sys.executable).resolve()),
        str(Path(__file__).resolve()), "_execute", str(output), row["run_id"],
        "--launch", str(directory / "dispatcher-launch.json")], "cwd": str(ROOT),
        "output_dir": str(directory / "supervisor"), "timeout_seconds": evaluation_budget(manifest),
        "environment": {**manifest["evaluator"].get("environment", {}),
            "APROF_SKILL_LIB": str(release), "PYTHONPATH": str(release / "runtime/src"),
            "PYTHONDONTWRITEBYTECODE": "1", "ASCEND_RT_VISIBLE_DEVICES": device,
            "APROF_PHYSICAL_DEVICE": device, "APROF_LOGICAL_DEVICE": "0"}}


def _load_launch(output, run_id, launch_path, launch_sha256):
    directory = output / "runs" / run_id
    if Path(launch_path) != directory / "dispatcher-launch.json" or sha(launch_path) != launch_sha256:
        raise ValueError("outer launch pointer differs")
    launch = load(launch_path)
    if set(launch) != {"attempt_ref", "started_at", "started_monotonic", "deadline_monotonic",
                       "issued_monotonic", "child_timeout_seconds"}:
        raise ValueError("outer launch fields differ")
    for key in set(launch) - {"attempt_ref"}:
        if type(launch[key]) not in (int, float) or not math.isfinite(launch[key]):
            raise ValueError("outer launch contains a non-finite clock")
    attempt = load(checked(launch["attempt_ref"]))
    plan = load(checked(attempt["plan_ref"]))
    manifest, roster = load(output / "freeze.json"), load(output / "matrix.json")
    budget = evaluation_budget(manifest)
    rows = [r for r in roster["runs"] if r["run_id"] == run_id]
    if (len(rows) != 1 or set(attempt) != {"plan_ref", "budget_seconds", "created_at"}
            or set(plan) != {"schema_version", "kind", "run_id", "row", "freeze_ref", "matrix_ref", "job_ref", "budget_seconds"}
            or plan["schema_version"] != 1 or plan["kind"] != "skill_release_trial_plan"
            or plan["run_id"] != run_id or plan["row"] != rows[0]
            or budget_seconds(attempt) != budget or budget_seconds(plan) != budget
            or attempt["created_at"] != launch["started_at"]
            or launch["attempt_ref"] != _pointer(directory / "attempt.json")
            or attempt["plan_ref"] != _pointer(directory / "dispatcher-plan.json")
            or plan["freeze_ref"] != _pointer(output / "freeze.json")
            or plan["matrix_ref"] != _pointer(output / "matrix.json")
            or plan["job_ref"] != _pointer(directory / "job.json")
            or roster["freeze_sha256"] != plan["freeze_ref"]["sha256"]
            or launch["deadline_monotonic"] != launch["started_monotonic"] + budget
            or not launch["started_monotonic"] <= launch["issued_monotonic"] < launch["deadline_monotonic"]
            or launch["child_timeout_seconds"] != launch["deadline_monotonic"] - launch["issued_monotonic"]):
        raise ValueError("outer attempt reset or changed its original deadline/registration")
    job = load(checked(plan["job_ref"]))
    if job != _trial_job(output, rows[0], manifest):
        raise ValueError("outer immutable job differs")
    actual = {**job, "argv": job["argv"] + ["--launch-sha256", launch_sha256],
              "timeout_seconds": launch["child_timeout_seconds"],
              "deadline_monotonic": launch["deadline_monotonic"]}
    return launch, actual


def _dispatch_result(directory, row, launch, execution, finished_at, finished_monotonic):
    """Post-exit handoff: recover authoritative costs without rewriting child evidence."""
    child_path = directory / "child-result.json"
    result = load(child_path) if child_path.is_file() else {
        **row, "budget_policy": BUDGET_POLICY, "status": "child_failed", "deployed_speedup": 1.0}
    result = {**result, "child_result_ref": _pointer(child_path) if child_path.is_file() else None,
        "task_launch_ref": _pointer(directory / "dispatcher-launch.json"),
        "execution_ref": _pointer(directory / "supervisor/execution.json") if execution is not None else None,
        "started_at": launch["started_at"], "finished_at": finished_at,
        "started_monotonic": launch["started_monotonic"], "finished_monotonic": finished_monotonic,
        "deadline_monotonic": launch["deadline_monotonic"],
        "duration_seconds": finished_monotonic - launch["started_monotonic"]}
    for key, folder in (("worker", "worker"), ("reviewer", "reviewer")):
        path = directory / folder / "worker.json"
        result[key] = load(path) if path.is_file() else None
    result["reviewer_started"] = (directory / "reviewer").exists()
    complete = (result["worker"] is not None and result["worker"].get("usage") is not None
        and (not result["reviewer_started"] or result["reviewer"] is not None and result["reviewer"].get("usage") is not None))
    result["total_model_tokens"] = (sum(r["usage"]["totalTokens"] for r in (result["worker"], result["reviewer"])
        if r is not None and r.get("usage") is not None) if complete else None)
    if not complete:
        result["model_usage_status"] = "unavailable; missing authoritative worker/reviewer usage"
    error_path = directory / "dispatcher-error.json"
    if error_path.is_file():
        result.update(status="dispatch_failed", dispatcher_error_ref=_pointer(error_path))
    if (execution is not None and execution["status"] == "timeout") or finished_monotonic > launch["deadline_monotonic"]:
        result["status"] = "over_wall_time_budget"
    elif execution is None or execution["status"] != "passed" or execution["exit_code"] != 0 or not child_path.is_file():
        if result["status"] in ("passed", "incomplete", "completed"):
            result["status"] = "child_failed"
    if result["status"] != "passed":
        result.update(deployed_speedup=1.0, time_to_target_seconds=None, tokens_to_target=None)
    elif result.get("time_to_target_seconds") is not None:
        result.update(time_to_target_seconds=result["duration_seconds"], tokens_to_target=result["total_model_tokens"])
    return result


def dispatch(output, run_id):
    """One real process-tree budget, starting before inner validation and staging."""
    started, wall = time.monotonic(), time.time()
    output = Path(output).resolve()
    manifest, roster = load(output / "freeze.json"), load(output / "matrix.json")
    budget = evaluation_budget(manifest)
    row = next(r for r in roster["runs"] if r["run_id"] == run_id)
    directory = output / "runs" / run_id
    directory.mkdir(parents=True, exist_ok=False)  # No retry or resumed fresh deadline.
    job = _trial_job(output, row, manifest)
    dump(directory / "job.json", job)
    dump(directory / "dispatcher-plan.json", {"schema_version": 1, "kind": "skill_release_trial_plan",
        "run_id": run_id, "row": row, "freeze_ref": _pointer(output / "freeze.json"),
        "matrix_ref": _pointer(output / "matrix.json"), "job_ref": _pointer(directory / "job.json"), "budget_seconds": budget})
    dump(directory / "attempt.json", {"plan_ref": _pointer(directory / "dispatcher-plan.json"),
        "budget_seconds": budget, "created_at": wall})
    issued = time.monotonic()
    launch = {"attempt_ref": _pointer(directory / "attempt.json"), "started_at": wall,
        "started_monotonic": started, "deadline_monotonic": started + budget,
        "issued_monotonic": issued, "child_timeout_seconds": started + budget - issued}
    dump(directory / "dispatcher-launch.json", launch)
    try:
        _, actual = _load_launch(output, run_id, directory / "dispatcher-launch.json", sha(directory / "dispatcher-launch.json"))
        execution = run_job(actual)
    except BaseException as error:
        dump(directory / "dispatcher-error.json", {"type": type(error).__name__, "message": str(error)})
        receipt = directory / "supervisor/execution.json"
        execution = load(receipt) if receipt.is_file() else None
    result = _dispatch_result(directory, row, launch, execution, time.time(), time.monotonic())
    dump(directory / "dispatcher-result.json", result)
    dump(directory / "result.json", result)
    return result


def verify_dispatch(output, row, result):
    """Require the actual whole-task job, including generation and online replay."""
    directory = output / "runs" / row["run_id"]
    if result.get("task_launch_ref") != _pointer(directory / "dispatcher-launch.json"):
        raise ValueError("trial lacks its original outer launch")
    launch, job = _load_launch(output, row["run_id"], directory / "dispatcher-launch.json",
                               result["task_launch_ref"]["sha256"])
    execution = load(directory / "supervisor/execution.json")
    if (result.get("execution_ref") != _pointer(directory / "supervisor/execution.json")
            or execution.get("schema_version") != "1.0.0" or execution.get("kind") != "aprof_execution_report"
            or execution.get("job") != job or execution.get("physical_device") is not None
            or execution.get("status") not in ("passed", "failed", "timeout")
            or type(execution.get("exit_code")) is not int
            or type(execution.get("process_started")) is not bool
            or not execution["process_started"] and (execution["exit_code"] != -1 or execution["status"] == "passed")):
        raise ValueError("outer actual execution differs from the original budget")
    start, end = (dt.datetime.fromisoformat(execution[k].replace("Z", "+00:00")).timestamp()
                  for k in ("started_at", "finished_at"))
    if (not launch["started_at"] <= start <= end <= result["finished_at"]
            or result["started_at"] != launch["started_at"]
            or result["started_monotonic"] != launch["started_monotonic"]
            or result["deadline_monotonic"] != launch["deadline_monotonic"]
            or not 0 < execution["duration_seconds"] <= result["duration_seconds"]
            or result["duration_seconds"] != result["finished_monotonic"] - launch["started_monotonic"]):
        raise ValueError("outer execution chronology or elapsed cost differs")
    for key in ("stdout", "stderr"):
        if execution[key] != _pointer(directory / "supervisor" / (key + ".log")):
            raise ValueError("outer execution log changed")
    if result.get("child_result_ref") is not None:
        child = load(checked(result["child_result_ref"]))
        if (result["child_result_ref"] != _pointer(directory / "child-result.json")
                or child.get("task_launch_ref") != result["task_launch_ref"]
                or child.get("started_monotonic") != launch["started_monotonic"]
                or child.get("deadline_monotonic") != launch["deadline_monotonic"]
                or not launch["started_monotonic"] <= child["finished_monotonic"] <= result["finished_monotonic"]
                or child["duration_seconds"] != child["finished_monotonic"] - launch["started_monotonic"]):
            raise ValueError("child reset the original task deadline")
    if (result != _dispatch_result(directory, row, launch, execution, result["finished_at"], result["finished_monotonic"])
            or load(directory / "dispatcher-result.json") != result):
        raise ValueError("dispatcher result changed the actual child/exit/cost handoff")
    if result["status"] == "passed" and (execution["status"] != "passed" or execution["exit_code"] != 0
            or not execution["process_started"] or execution.get("error") is not None or result["child_result_ref"] is None
            or result["finished_monotonic"] > launch["deadline_monotonic"]
            or result["finished_at"] > launch["started_at"] + (launch["deadline_monotonic"] - launch["started_monotonic"])):
        raise ValueError("late or failed whole-task execution cannot be accepted")
    return {"launch": result["task_launch_ref"], "execution": result["execution_ref"],
            "dispatcher_result": _pointer(directory / "dispatcher-result.json")}


def tree_sha(root, *, exclude_release_manifest=False):
    files = []
    for path in sorted(Path(root).rglob("*")):
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if exclude_release_manifest and path.relative_to(root).as_posix() == "release.json":
            continue
        if path.is_symlink():
            raise ValueError(f"frozen input contains a symlink: {path}")
        if path.is_file():
            files.append([path.relative_to(root).as_posix(), sha(path), path.stat().st_mode & 0o777])
    return "sha256:" + hashlib.sha256(json.dumps(files, separators=(",", ":")).encode()).hexdigest()


def library_sha(root):
    return tree_sha(root, exclude_release_manifest=True)


def checked(ref, *, tree=False, library=False):
    path = Path(ref["path"]).resolve(strict=True)
    if (library_sha(path) if library else tree_sha(path) if tree else sha(path)) != ref["sha256"]:
        raise ValueError(f"frozen input changed: {path}")
    return path


def _task_mode(manifest):
    return manifest.get("measurement_protocol") is not None


def _task_api(release):
    import task_validation_trial as trial
    if trial.bridge.RELEASE != Path(release).resolve():
        raise ValueError("Task evaluation requires the frozen selected runtime in a fresh process")
    return trial


def _task_local_root(manifest, api=None):
    api = api or _task_api(manifest["libraries"]["candidate"]["path"])
    root = Path(manifest["evaluator"]["task_local_root"])
    if (not root.is_absolute() or root.resolve() != root or not root.is_dir()
            or api.bridge.timing.old.select_mount(Path("/proc/self/mountinfo").read_text(), root)["filesystem_type"]
                not in api.bridge.timing.old.LOCAL_PROFILE_FILESYSTEMS):
        raise ValueError("frozen task_local_root must be a canonical supported local filesystem directory")
    return root


def _task_inputs(manifest, operator):
    """Recompute the complete baseline and all Contexts before any model call."""
    from task_baseline_context import replay_baseline_contexts
    task = manifest["tasks"][operator]
    api = _task_api(checked(manifest["libraries"]["candidate"], library=True))
    _task_local_root(manifest, api)
    if manifest["measurement_protocol"] != api.bridge.timing.PROTOCOL:
        raise ValueError("frozen Task protocol differs from the selected collector")
    local = api.bridge.LocalEvidence.from_index(checked(task["baseline_local_index"]))
    for key in ("evaluation_plan", "baseline_qualification", "route_registry"):
        checked(task[key]); local.verify_artifact(task[key]["sha256"])
    original = api.candidate.baseline._read(local, task["evaluation_plan"]["sha256"])
    comparison = load(checked(manifest["plan"]))["equal_budget_evaluation"]
    if (original["operator"] != operator or original["task_protocol"] != manifest["measurement_protocol"]
            or original["case_ids"] != list(range(1, 21))
            or budget_seconds(original) != budget_seconds(comparison)
            or collection_policy(original) != collection_policy(comparison)
            or original["physical_device"] != manifest["evaluator"]["physical_device"]
            or api.bridge.profile_capture.source_inventory(checked(task["baseline"], tree=True))
                != original["roles"]["baseline"]["files"]):
        raise ValueError("Task baseline scope, source, protocol, device or comparison budget differs")
    config = api.candidate.baseline._read(local, task["context_derivation_ref"])
    if config["plan_ref"] != task["evaluation_plan"]["sha256"]:
        raise ValueError("Context derivation names another baseline plan")
    registry = load(checked(task["route_registry"]))
    if not registry.get("contexts") or any(entry["baseline_qualification"] != task["baseline_qualification"]
                                          for entry in registry["contexts"].values()):
        raise ValueError("Task route registry differs from the frozen qualification pointer")
    trusted = replay_baseline_contexts(local, derivation_ref=task["context_derivation_ref"],
        qualification_ref=task["baseline_qualification"]["sha256"], registry_ref=task["route_registry"]["sha256"])
    if (trusted["valid"] is not True or len(trusted["contexts"]) != 20
            or {v["workload"]["case_id"] for v in trusted["contexts"].values()} != set(range(1, 21))):
        raise ValueError("Task evaluation requires every independently replayed baseline Context")
    return original, trusted


def _task_argv():
    return [str(Path(sys.executable).resolve()), str(Path(__file__).resolve()), "_evaluate_task",
        "{evaluation_output}", "{run_id}", "--workspace", "{workspace}", "--result", "{result}",
        "--launch", "{task_launch}", "--launch-sha256", "{task_launch_ref}"]


def validate_freeze(manifest):
    if manifest.get("state") != "frozen_for_validation" or manifest.get("schema_version") != 1:
        raise ValueError("root must freeze the candidate and evaluation inputs before launch")
    plan = load(checked(manifest["plan"]))["equal_budget_evaluation"]
    collection_policy(plan)
    if (plan["seeds"] != [4101, 4102, 4103] or len(plan["operators"]) != 5
            or set(plan["operators"]) != set(VALIDATION_OPERATORS)):
        raise ValueError("evaluation matrix differs from the predetermined plan")
    for key in ("candidate_limit", "build_limit", "timing_limit", "full_profile_limit"):
        if plan[key] != 1:
            raise ValueError("one-candidate budgets are frozen")
    if (budget_seconds(plan) <= 0 or plan["model_token_limit"] is not None
            or plan.get("budget_policy") != BUDGET_POLICY or manifest.get("budget_policy") != BUDGET_POLICY):
        raise ValueError("shared frozen time-only budget differs from the frozen plan")
    require_worker_build_budget_enforcement(manifest.get("worker_qualification"), model=manifest.get("model", {}).get("name"),
                                          effort=manifest.get("model", {}).get("reasoning_effort"))
    if manifest.get("model_budgets") != MODEL_BUDGETS or plan.get("model_budgets") != MODEL_BUDGETS:
        raise ValueError("model tokens must be recorded as cost without hard limits")
    if manifest.get("publication_criterion") != PUBLICATION_CRITERION:
        raise ValueError("publication criterion must be fixed before evaluation")
    if not math.isfinite(manifest["target_speedup"]) or manifest["target_speedup"] <= 1:
        raise ValueError("time-to-target threshold must be fixed above 1 before evaluation")
    candidate = checked(manifest["libraries"]["candidate"], library=True)
    baseline = checked(manifest["libraries"]["baseline"], library=True)
    verify_baseline_library(baseline)
    audit = checked(manifest["teacher_audit"])
    subprocess.run([sys.executable, "-c",
        "import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); from verify_teacher_wiki import verify; "
        "verify(Path(sys.argv[2]),Path(sys.argv[3]),Path(sys.argv[4]),Path(sys.argv[5]))",
        str(ROOT / "scaffolding/tools"), str(ROOT), str(ROOT.parent / "optimization-traces"), str(candidate), str(audit)],
        check=True, capture_output=True, text=True)
    accepted = [load_line for line in (candidate / "wiki/evolution.jsonl").read_text().splitlines()
                if line and (load_line := json.loads(line)).get("decision") == "accepted"]
    if not accepted:
        raise ValueError("no independently verified skill promotion; validation launch is gated")
    if set(manifest["tasks"]) != set(plan["operators"]):
        raise ValueError("task inventory must match all five current validation operators")
    for operator, task in manifest["tasks"].items():
        if _task_mode(manifest):
            _task_inputs(manifest, operator)
            for key in ("review_contract", "review_checklist", "review_boundaries"):
                checked(task[key])
            if task.get("profiles"):
                raise ValueError("Task evaluation does not copy persistent profile trees into model workspaces")
        else:
            baseline = checked(task["baseline"], tree=True)
            context = checked(task["context"])
            task_plan_path = checked(task["evaluation_plan"])
            task_plan = load(task_plan_path)
            qualification = load(checked(task["baseline_qualification"]))
            if (task_plan["operator"] != operator or Path(task_plan["baseline_source"]).resolve() != baseline
                    or checked(task_plan["context"]) != context or Path(task_plan["release"]).resolve() != candidate
                    or qualification["task_plan"] != task["evaluation_plan"] or qualification["status"] != "passed"
                    or load(context).get("profile") != task_plan["profile"]):
                raise ValueError("task baseline, context, profile choices or qualification differs from frozen plan")
            for key in ("source_inventory", "input_inventory"):
                checked(task_plan[key])
            checked(qualification["binary"])
            for key in ("route_registry", "review_contract", "review_checklist", "review_boundaries"):
                checked(task[key])
            registry = load(checked(task["route_registry"]))
            if not registry.get("contexts") or any(item["baseline_qualification"] != task["baseline_qualification"]
                                                    for item in registry["contexts"].values()):
                raise ValueError("all route contexts must bind this qualified baseline")
            from eval_candidate_evidence import replay_route
            for context_id in registry["contexts"]:
                replay_route(task["route_registry"], context_id, candidate)
            from validation_host_evaluator import imports as host_imports, verify_qualification
            verify_qualification(task_plan_path, task["baseline_qualification"], host_imports(candidate))
            if task.get("profiles"):
                checked(task["profiles"], tree=True)
    model = manifest["model"]
    if not all(isinstance(model.get(key), str) and model[key] for key in ("name", "reasoning_effort", "cli_version")):
        raise ValueError("model, effort and CLI version must be frozen")
    if subprocess.check_output(["codex", "--version"], text=True).strip() != model["cli_version"]:
        raise ValueError("Codex version changed")
    if not manifest["toolchain"].get("identity") or not manifest["toolchain"].get("files"):
        raise ValueError("toolchain identity and binaries must be bound")
    for ref in manifest["toolchain"]["files"] + manifest["evaluator"]["files"]:
        checked(ref)
    required_files = {Path(__file__).resolve(), *(Path(__file__).with_name(name).resolve() for name in (
        "isolated_eval_worker.py", "eval_tool_broker.py", "eval_candidate_evidence.py", "qualify_eval_tools.py", "review_packet.py", "task_budget.py",
        "validation_host_evaluator.py", "validation_operator_adapter.py", "timing_admission.py",
        "controller_admission.py", "device_paired_timing_v2.py", "run_aprof_job.py", "aprof_layout.py")),
        ROOT / "scaffolding/benchmarks/cannbench/harness/device_timer_v2.h",
        ROOT / "scaffolding/tools/verify_teacher_wiki.py"}
    if _task_mode(manifest):
        api = _task_api(candidate)
        required_files |= {Path(name).resolve() for name in api.candidate.baseline.producer_paths()}
        required_files |= {Path(name).resolve() for task in manifest["tasks"].values()
            for name in api.candidate._producers(load(checked(task["evaluation_plan"])))}
        required_files |= {Path(api.__file__).with_name(name).resolve() for name in api.PRODUCERS}
        if manifest["evaluator"]["argv"] != _task_argv():
            raise ValueError("Task evaluation must use the fixed trusted trial entry")
    if not required_files <= {checked(ref) for ref in manifest["evaluator"]["files"]}:
        raise ValueError("freeze must bind every broker/reviewer/route/controller/admission/collector producer")
    if not manifest["evaluator"]["argv"] or not manifest["evaluator"]["files"]:
        raise ValueError("a real hash-frozen host evaluator is required")
    evaluator = manifest["evaluator"]
    if (evaluator.get("lock_owner") != "evaluator" or evaluator.get("logical_device") != 0
            or type(evaluator.get("physical_device")) is not int or not 0 <= evaluator["physical_device"] < 16):
        raise ValueError("evaluator must own stage locks and freeze explicit physical-to-logical-zero mapping")
    for task in manifest["tasks"].values():
        task_plan = load(checked(task["evaluation_plan"]))
        reference_environment = (_task_api(candidate).candidate.builder.CPU_REFERENCE_ENV
            if _task_mode(manifest) else task_plan["cpu_reference_environment"])
        if (task_plan["physical_device"] != evaluator["physical_device"]
                or any(evaluator.get("environment", {}).get(key) != value for key, value in reference_environment.items())):
            raise ValueError("task mapping or oracle environment differs from frozen evaluator")
    return plan


def verify_baseline_library(baseline):
    from aprof_layout import release_module
    original = ROOT / "skill-libs/graph-base/0.5.0"
    canonical = release_module(original).verify(original)
    if (canonical.get("status") != "stable" or canonical.get("release_id") != "graph-base/0.5.0"
            or load(baseline / "release.json") != canonical or library_sha(baseline) != library_sha(original)):
        raise ValueError("comparison baseline must be the unchanged canonical graph-base/0.5.0 release")
    return canonical


def matrix(plan):
    rows = []
    for seed in plan["seeds"]:
        block = [{"run_id": f"{operator}-{arm}-{seed}", "operator": operator, "arm": arm, "seed": seed}
                 for operator in plan["operators"] for arm in ARMS]
        random.Random(seed).shuffle(block)
        rows.extend(block)
    if len(rows) != len({row["run_id"] for row in rows}):
        raise ValueError("evaluation run identities must be unique")
    return rows


def prepare(manifest_path, output):
    manifest = load(manifest_path)
    plan = validate_freeze(manifest)
    output.mkdir(parents=True, exist_ok=False)
    dump(output / "freeze.json", manifest)
    dump(output / "matrix.json", {"freeze_sha256": sha(output / "freeze.json"), "runs": matrix(plan),
        "seed_semantics": "run-order/repetition labels; workload RNG is unchanged and model sampling is not deterministically seeded"})
    return {"runs": 45, "path": str(output)}


def stage(manifest, row, workspace):
    task = manifest["tasks"][row["operator"]]
    if _task_mode(manifest) and task.get("profiles"):
        raise ValueError("Task staging must not copy baseline profile trees")
    workspace.mkdir()
    shutil.copytree(checked(task["baseline"], tree=True), workspace / "baseline")
    shutil.copytree(workspace / "baseline", workspace / "candidate")
    if _task_mode(manifest):
        original = load(checked(task["evaluation_plan"]))
        registry = load(checked(task["route_registry"]))
        dump(workspace / "context.json", {"kind": "qualified_task_description", "operator": row["operator"],
            "measurement_protocol": manifest["measurement_protocol"], "profile": original["profile"],
            "baseline_qualification": task["baseline_qualification"],
            "context_derivation_ref": task["context_derivation_ref"], "case_ids": original["case_ids"],
            "contexts": {key: load(checked(value["context"])) for key, value in registry["contexts"].items()},
            "original_workloads": [{key: case[key] for key in ("case_id", "workload", "role_kernel_names",
                "launches_per_call")} for case in original["cases"]]})
    else:
        shutil.copy2(checked(task["context"]), workspace / "context.json")
    if task.get("profiles"):
        shutil.copytree(checked(task["profiles"], tree=True), workspace / "profiles")
    library = checked(manifest["libraries"]["baseline" if row["arm"] == "baseline" else "candidate"], library=True)
    shutil.copytree(library, workspace / "library", ignore=shutil.ignore_patterns("wiki", "__pycache__", "*.pyc"))
    if row["arm"] == "skill-plus-wiki":
        (workspace / "library/wiki").mkdir()
        shutil.copy2(library / "wiki/index.json", workspace / "library/wiki/index.json")
    wiki_instruction = ("For ambiguity or counterexamples, inspect library/wiki/index.json and call read_wiki for one relevant page."
                        if row["arm"] == "skill-plus-wiki" else "This arm has no Wiki access.")
    profile = load(workspace / "context.json")["profile"]
    context = load(workspace / "context.json")
    context["graph_context_ids"] = list(load(checked(task["route_registry"]))["contexts"])
    dump(workspace / "context.json", context)
    proposal_example = json.dumps({"intent": "Describe the concrete intervention", "actual_parent": "original baseline",
        "route_receipt_ref": {"path": "Copy the exact path returned by graph_route", "sha256": "Copy the exact returned sha256"},
        "transformation_id": "Copy the selected route target_id", "parameters": {},
        "rationale": "Explain evidence, applicable shapes/dtypes, alternatives and risks",
        "source_anchors": [{"path": f"op_kernel/{row['operator']}_kernel.asc", "line": 1,
                            "why": "Replace this example with the actual relevant source line and mechanism"}],
        "mechanism": {"case_id": profile["case_id"], "kernel": profile["kernels"][0],
                      "metric": next(iter(profile["metrics"])), "expected_direction": "decrease"}}, indent=2)
    planning_instruction = ("Include parallel_plan and dispatch_plan in this SAME submitted JSON. "
        "Use the qualified Contexts in context.json: retain the original operator semantics, ownership, "
        "workspace and synchronization contracts. Describe all candidate changes explicitly; do not "
        "invent resource limits, kernel entries or tiling keys. For an existing unkeyed complete-call "
        "implementation, dispatch_plan may contain mode=unkeyed_complete_call and a nonempty dispatch_id; "
        "the trusted adapter binds all original workloads and complete ordered kernel sequences. "
        "Machine source/architecture hashes may be omitted and are bound by the trusted controller. "
        "This description envelope is not a runtime Context and does not authorize new predicates."
        if _task_mode(manifest) else "")
    prompt = f"""Optimize {row['operator']} for the frozen hardware and semantic contract in context.json.
Start with library/skills/ascendc-aprof-workflow/SKILL.md and follow its legal SkillGraph routes.
The read-only baseline/ is the original source. profiles/ (when present) contains baseline evidence.
Implement exactly one atomic candidate in candidate/. Do not build, run kernels, profile, create another candidate, or spawn agents.
The trusted controller will run one build, full correctness, one formal timing group and one profile group after you finish.
Preserve the complete oracle, CLI, harness and timer. Kernel and tiling implementation may change.
Host text outside APROF_EVAL_OPERATOR_BEGIN/END and CMake must remain byte-identical. Do not introduce host launch/runtime
helpers in includes or change the number of host launch sites/host loop headers. These conservative scope checks apply
to every arm; an unattestable timing scope is rejected.
After submission an independent, blind source reviewer checks semantics, tails, ownership, UB capacity, synchronization,
workspace bounds and complete timing scope. A critical failure or unknown rejects the candidate; there is no edit retry.
Only the broker tools can read or edit files; no command execution tools are available.
Call graph_route with one context.json graph_context_ids value. Do not invent predicate values.
The plan must include its returned route_receipt_ref, the selected transformation_id and parameters matching that graph node.
Write candidate_plan.json with intent, actual parent=original baseline, rationale, shape/dtype conditions, source anchors,
supporting/opposing evidence, risks and validation expectations. Do not claim a measured gain.
Use the exact key actual_parent with value "original baseline". Include mechanism with exactly case_id, kernel, metric,
and expected_direction (increase or decrease), selecting the frozen profile choices in context.json before any measurements.
Use source_anchors as a nonempty list of {{"path": "relative/source.asc", "line": 1, "why": "specific mechanism evidence"}}.
The following is the exact required JSON structure (replace descriptive placeholders and choose a supported metric direction;
source anchor lines must describe your actual candidate). Additional rationale fields are permitted:
{proposal_example}
Replace the empty parameters example with values satisfying graph_route's returned parameter_schema.
{planning_instruction}
{wiki_instruction}
Budget: one candidate and one trusted build. The original frozen task deadline is shared by generation, independent review,
build, correctness, timing, profiling and online admission. Model tokens, including cached input, are recorded
as cost without a hard limit. Archiving follows task exit and is accounted separately.
Use replace_text to edit; finish with submit_candidate(plan).
Run-order/repetition label {row['seed']} identifies this run; workload RNG is unchanged and model sampling is not seeded.
Finish once the candidate and concise plan are saved.
"""
    (workspace / "prompt.txt").write_text(prompt)
    return library / "wiki" if row["arm"] == "skill-plus-wiki" else None


def validate_candidate(baseline, candidate):
    if any(path.is_symlink() for path in candidate.rglob("*")):
        raise ValueError("candidate may not introduce symlinks")
    before = {p.relative_to(baseline): p for p in baseline.rglob("*") if p.is_file()}
    after = {p.relative_to(candidate): p for p in candidate.rglob("*") if p.is_file()}
    changed = []
    for relative in before.keys() | after.keys():
        old, new = before.get(relative), after.get(relative)
        if new and (new.is_symlink() or not new.resolve().is_relative_to(candidate.resolve())):
            raise ValueError("candidate symlink escapes frozen source")
        if old and new and old.read_bytes() == new.read_bytes():
            continue
        editable = relative.suffix in (".asc", ".h", ".cpp") or relative.name == "CMakeLists.txt"
        if not editable or relative.parts[0] == "scripts" or relative.name == "aprof_device_timer.h":
            raise ValueError(f"candidate modified a protected contract/harness: {relative}")
        changed.append(relative.as_posix())
    return sorted(changed)


def score(receipt):
    if receipt.get("kind") == "task_validation_evaluation":
        from aprof_layout import skill_lib
        plan = load(checked(receipt["candidate_plan_ref"]))
        outcome, _ = _replay_task_evaluation(receipt, skill_lib(), receipt["row"], Path(plan["workspace"]))
        return outcome["score"]
    if any(type(receipt["counts"][key]) is not int or not 0 <= receipt["counts"][key] <= 1
           for key in ("candidates", "builds", "timing_groups", "profile_groups")):
        raise ValueError("host evaluator exceeded the single-candidate budget")
    cases = receipt["cases"]
    if not cases or len({case["case_id"] for case in cases}) != len(cases):
        raise ValueError("missing or duplicate evaluation cases")
    for reference in receipt["evidence"]:
        checked(reference)
    if not receipt["evidence"] or not receipt.get("full_declared_correctness"):
        raise ValueError("full correctness and raw measurement receipts are required")
    correct = all(case["correct"] is True for case in cases)
    if any(not math.isfinite(case[field]) or case[field] <= 0 for case in cases
           for field in ("baseline_us", "candidate_us")):
        raise ValueError("invalid timing samples")
    ratios = [case["baseline_us"] / case["candidate_us"] for case in cases]
    if not all(math.isfinite(value) and value > 0 for value in ratios):
        raise ValueError("invalid timing samples")
    geomean = math.exp(sum(math.log(value) for value in ratios) / len(ratios))
    return {"correct": correct, "geomean_speedup": geomean,
            "correct_speedup": geomean if correct else 0,
            "regression_cases": [case["case_id"] for case, ratio in zip(cases, ratios) if ratio < 1]}


def _replay_task_evaluation(receipt, release, row, materialized):
    """Project verified Task leaves and the actual runtime episode; no SQL trace."""
    api = _task_api(release)
    if (receipt.get("status") != "completed" or receipt.get("error") is not None
            or receipt.get("row") != row or receipt.get("measurement_protocol") != api.bridge.timing.PROTOCOL
            or receipt.get("archive_performed") is not False or receipt.get("admission_authority") is not False
            or receipt.get("eligible_for_publication") is not False):
        raise ValueError("Task evaluation is incomplete or changed scope")
    local = api.bridge.LocalEvidence.from_index(checked(receipt["local_index"]))
    if local.directory.parent != Path(receipt["task_root"]):
        raise ValueError("Task local handoff escaped its actual task root")
    for key in ("candidate_plan_ref", "draft_ref", "trial_ref", "result_ref", "online_replay_ref", "task_launch_ref"):
        checked(receipt[key]); local.verify_artifact(receipt[key]["sha256"])
    read = lambda ref: load(local.verify_artifact(ref))
    plan = read(receipt["candidate_plan_ref"]["sha256"])
    trial = read(receipt["trial_ref"]["sha256"])
    if (plan["run_id"] != row["run_id"] or plan["operator"] != row["operator"]
            or plan["launch_ref"] != receipt["task_launch_ref"]["sha256"]
            or plan["deadline_monotonic"] != receipt["deadline_monotonic"]
            or trial["candidate_plan_ref"] != receipt["candidate_plan_ref"]["sha256"]
            or trial["draft_ref"] != receipt["draft_ref"]["sha256"]
            or receipt["candidate_tree_sha256"] != tree_sha(materialized / "candidate")):
        raise ValueError("Task evaluation changed its actual candidate, trial or original deadline")
    for role in ("baseline", "candidate"):
        validate_source_bundle(local, plan["source_hashes"][role], materialized / role,
                               api.bridge.profile_capture.source_inventory)
    replayed = api.replay_trial(local, trial_ref=receipt["trial_ref"]["sha256"],
                               result_ref=receipt["result_ref"]["sha256"])
    if replayed["valid"] is not True or read(receipt["online_replay_ref"]["sha256"]) != replayed:
        raise ValueError("Task online replay differs from actual component replay")
    result = read(receipt["result_ref"]["sha256"])
    stages = [read(ref)["artifacts"] for ref in result["stages"]]
    accuracy = read(stages[0]["accuracy_report"])
    measured = read(stages[1]["measurement_report"])
    finalization = read(stages[3]["finalization"])
    from aprof_runtime.contracts import CandidateEpisode
    episode = CandidateEpisode.from_dict(finalization["episodes"][0])
    expected = list(range(1, 21))
    if (accuracy["case_ids"] != expected or [case["case_id"] for case in measured["per_case"]] != expected
            or [(item["case_id"], item["role"]) for item in accuracy["rows"]]
                != [(cid, role) for cid in expected for role in ("baseline", "candidate")]):
        raise ValueError("Task score omitted original cases or a correctness role")
    cases = [{"case_id": item["case_id"], "correct": all(r["correct"] is True for r in accuracy["rows"]
                    if r["case_id"] == item["case_id"]),
              **{role + "_us": item[role + "_median_ns"] / 1000 for role in ("baseline", "candidate")}}
             for item in measured["per_case"]]
    projection = {"counts": dict(candidates=1, builds=1, timing_groups=1, profile_groups=1),
        "cases": cases, "full_declared_correctness": True,
        "evidence": [{"path": str(local.verify_artifact(ref)), "sha256": ref}
                     for ref in (stages[0]["accuracy_report"], stages[1]["measurement_report"], stages[3]["finalization"])]}
    return {"kind": "task_evaluation_projection", "result": {"verdict": episode.outcome.verdict.value},
            "score": score(projection), "cases": cases, "episode_hash": episode.episode_hash}, episode.outcome.speedup


def _verify_task_controller(manifest, row, directory, receipt, execution, launch_ref):
    """Join the local terminal to its real child exit and original supervisor."""
    output = directory.parents[1]
    launch, _ = _load_launch(output, row["run_id"], checked(launch_ref), launch_ref["sha256"])
    deadline = launch["deadline_monotonic"]
    if Path(receipt["task_root"]).parent != _task_local_root(manifest):
        raise ValueError("Task controller escaped the frozen local workspace root")
    substitutions = {"evaluation_output": str(output), "run_id": row["run_id"],
        "workspace": str(directory / "controller-workspace"), "result": str(directory / "evaluation.json"),
        "task_launch": launch_ref["path"], "task_launch_ref": launch_ref["sha256"]}
    expected_env = {**manifest["evaluator"].get("environment", {}),
        "APROF_TASK_LAUNCH_PATH": launch_ref["path"], "APROF_TASK_LAUNCH_SHA256": launch_ref["sha256"],
        "APROF_TASK_DEADLINE_MONOTONIC": str(deadline),
        "APROF_SKILL_LIB": manifest["libraries"]["candidate"]["path"],
        "PYTHONPATH": str(Path(manifest["libraries"]["candidate"]["path"]) / "runtime/src"),
        "PYTHONDONTWRITEBYTECODE": "1", "APROF_EVALUATION_SEED": str(row["seed"]),
        "ASCEND_RT_VISIBLE_DEVICES": str(manifest["evaluator"]["physical_device"]),
        "APROF_PHYSICAL_DEVICE": str(manifest["evaluator"]["physical_device"]), "APROF_LOGICAL_DEVICE": "0"}
    start, end = (dt.datetime.fromisoformat(execution[key].replace("Z", "+00:00"))
                  for key in ("started_at", "finished_at"))
    timeout = execution["job"]["timeout_seconds"]
    if (manifest["evaluator"]["argv"] != _task_argv()
            or execution.get("schema_version") != "1.0.0" or execution.get("kind") != "aprof_execution_report"
            or execution["status"] != "passed" or type(execution["exit_code"]) is not int or execution["exit_code"] != 0
            or execution.get("error") or not start.tzinfo or not end.tzinfo
            or execution["job"] != {"job_id": row["run_id"], "argv": [v.format_map(substitutions) for v in _task_argv()],
                "cwd": str(ROOT), "output_dir": str(directory / "controller"), "timeout_seconds": timeout,
                "deadline_monotonic": deadline, "environment": expected_env}
            or not 0 < execution["duration_seconds"] <= timeout <= evaluation_budget(manifest)
            or receipt.get("measurement_protocol") != manifest["measurement_protocol"]
            or receipt.get("task_launch_ref") != launch_ref or receipt.get("row") != row
            or receipt.get("status") != "completed" or receipt.get("deadline_monotonic") != deadline
            or not launch["started_at"] <= start.timestamp() <= receipt["started_at"]
                <= receipt["finished_at"] <= end.timestamp() <= launch["started_at"] + evaluation_budget(manifest)
            or not launch["issued_monotonic"] <= receipt["started_monotonic"] <= receipt["finished_monotonic"] <= deadline):
        raise ValueError("Task controller actual exit, identity, environment or original deadline differs")
    for key in ("stdout", "stderr"):
        checked(execution[key])


def paired_comparison(pairs):
    if len(pairs) != PUBLICATION_CRITERION["paired_units"]:
        raise ValueError("all 15 predetermined pairs are required")
    logs = [math.log(new["deployed_speedup"] / old["deployed_speedup"]) for old, new in pairs]
    rng = random.Random(PUBLICATION_CRITERION["bootstrap_seed"])
    samples = sorted(math.exp(sum(rng.choices(logs, k=len(logs))) / len(logs))
                     for _ in range(PUBLICATION_CRITERION["bootstrap_resamples"]))
    return {"paired_geomean_ratio": math.exp(sum(logs) / len(logs)),
            "bootstrap_95_lower": samples[int(0.025 * len(samples))],
            "bootstrap_95_upper": samples[int(0.975 * len(samples))],
            "no_correctness_decline": all(not old["correct"] or new["correct"] for old, new in pairs),
            "correct_tasks": sum(new["correct"] for old, new in pairs),
            "regression_case_count": sum(len(new["regression_cases"]) for old, new in pairs)}


def execute(output, run_id, *, launch_path=None, launch_sha256=None):
    launch = None
    if launch_path is not None:
        launch, _ = _load_launch(output, run_id, launch_path, launch_sha256)
    manifest = load(output / "freeze.json")
    if _task_mode(manifest) and launch is None:
        raise ValueError("Task evaluation requires its original supervisor launch")
    plan = validate_freeze(manifest)
    roster = load(output / "matrix.json")
    if roster["freeze_sha256"] != sha(output / "freeze.json") or roster["runs"] != matrix(plan):
        raise ValueError("evaluation roster or freeze changed")
    row = next(row for row in roster["runs"] if row["run_id"] == run_id)
    directory = output / "runs" / run_id
    if launch is None:
        directory.mkdir(parents=True, exist_ok=False)
    elif (directory / "child-result.json").exists() or (directory / "workspace").exists():
        raise ValueError("supervised child already started")
    workspace = directory / "workspace"
    started = time.monotonic() if launch is None else launch["started_monotonic"]
    model = manifest["model"]
    result = {**row, "budget_policy": BUDGET_POLICY, "worker": None, "reviewer": None,
              "reviewer_started": False, "status": "incomplete", "deployed_speedup": 1.0}
    if launch is not None:
        result["task_launch_ref"] = _pointer(launch_path)
    phase = "stage"
    try:
        if time.monotonic() - started >= budget_seconds(plan):
            raise TimeoutError("original task deadline expired before staging")
        wiki = stage(manifest, row, workspace)
        remaining = budget_seconds(plan) - (time.monotonic() - started)
        if remaining <= 0:
            result["status"] = "over_wall_time_budget"
        else:
            phase = "worker"
            worker = asyncio.run(run_worker(workspace, directory / "worker", model["name"], model["reasoning_effort"],
                                MODEL_BUDGETS["proposer"], remaining, wiki,
                                qualification=manifest["worker_qualification"], route_registry=manifest["tasks"][row["operator"]]["route_registry"],
                                release=Path(manifest["libraries"]["candidate"]["path"]), deadline_monotonic=started+budget_seconds(plan)))
            result.update(worker=worker, status=worker["status"])
            if worker["status"] == "completed":
                submitted_plan = load(directory / "worker/root/work/candidate_plan.json")
                if submitted_plan.get("transformation_id") == "transformation.noop":
                    if tree_sha(directory / "worker/root/work/baseline") != tree_sha(directory / "worker/root/work/candidate"):
                        raise ValueError("NOOP candidate mutated source")
                    result["status"] = "noop"
                else:
                    phase = "reviewer"
                    review_candidate(manifest, row, directory, started, result)
            phase = "candidate_or_controller"
            if result["status"] == "completed":
                evaluate_candidate(manifest, plan, row, directory, workspace, started, result)
    except Exception as error:
        # Setup/transport failures also consume a trial. Missing usage stays
        # unknown and prevents publication; it is never replaced with zero.
        result["status"] = phase + "_error"
        result["failure"] = {"stage": phase, "type": type(error).__name__, "message": str(error)}
        result["deployed_speedup"] = 1.0
    if result["worker"] is None:
        result["model_usage_status"] = "unavailable; no authoritative worker receipt"
        result["partial_worker_evidence"] = [{"path": str(path), "sha256": sha(path)}
            for name in ("worker.json", "events.jsonl", "stderr.log")
            if (path := directory / "worker" / name).is_file()]
    result["duration_seconds"] = time.monotonic() - started
    if result["duration_seconds"] > budget_seconds(plan):
        result["status"] = "over_wall_time_budget"
        result["deployed_speedup"] = 1.0
    result["time_to_target_seconds"] = result["duration_seconds"] if result["deployed_speedup"] >= manifest["target_speedup"] else None
    usage_complete = (result["worker"] is not None and result["worker"].get("usage") is not None
        and (not result["reviewer_started"] or result["reviewer"] is not None and result["reviewer"].get("usage") is not None))
    result["total_model_tokens"] = (sum(value["usage"]["totalTokens"] for value in (result["worker"], result["reviewer"])
        if value is not None and value.get("usage") is not None) if usage_complete else None)
    result["tokens_to_target"] = result["total_model_tokens"] if result["time_to_target_seconds"] is not None else None
    if launch is not None:
        result.update(task_launch_ref=_pointer(launch_path), started_monotonic=started,
            finished_monotonic=started + result["duration_seconds"], deadline_monotonic=launch["deadline_monotonic"])
    dump(directory / ("result.json" if launch is None else "child-result.json"), result)
    return result


def review_candidate(manifest, row, directory, started, result):
    from eval_tool_broker import REVIEW_SOURCE_POLICY, inventory, pointer, review_inventory
    from review_packet import build_review_packet
    task, model = manifest["tasks"][row["operator"]], manifest["model"]
    original = directory / "worker/root/work"
    review_input = directory / "review-input"
    review_input.mkdir()
    before, after = inventory(original / "baseline"), inventory(original / "candidate")
    views = {role: review_inventory(files) for role, files in (("baseline", before), ("candidate", after))}
    if not all(views.values()):
        raise ValueError("review requires implementation sources in both roles")
    for role in ("baseline", "candidate"):
        (review_input / role).mkdir()
        for name, reference in views[role].items():
            destination = review_input / role / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original / role / name, destination)
            if sha(destination) != reference:
                raise ValueError("review source changed while materializing its frozen view")
    for key, name in (("review_contract", "contract.json"), ("review_checklist", "checklist.json"), ("review_boundaries", "boundaries.json")):
        shutil.copy2(checked(task[key]), review_input / name)
    patches = []
    for name in sorted(views["baseline"].keys() | views["candidate"].keys()):
        if views["baseline"].get(name) == views["candidate"].get(name):
            continue
        old, new = review_input / "baseline" / name, review_input / "candidate" / name
        patches.extend(difflib.unified_diff(old.read_text().splitlines(True) if old.exists() else [],
            new.read_text().splitlines(True) if new.exists() else [], fromfile="baseline/" + name, tofile="candidate/" + name))
    (review_input / "diff.txt").write_text("".join(patches))
    packet = build_review_packet(review_input, expected_inventory=inventory(review_input))
    (review_input / "prompt.txt").write_text(packet["prompt"])
    deadline = started + (evaluation_budget(manifest) if "plan" in manifest else budget_seconds(checked_pointer(manifest["budget_plan"])))
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        result["status"] = "over_wall_time_budget"
        return
    result["reviewer_started"] = True
    reviewer = asyncio.run(run_worker(review_input, directory / "reviewer", model["name"], model["reasoning_effort"],
        MODEL_BUDGETS["reviewer"], remaining, qualification=manifest["worker_qualification"], review=True, deadline_monotonic=deadline))
    result["reviewer"] = reviewer
    if reviewer["status"] != "completed":
        result["status"] = "reviewer_" + reviewer["status"]
        return
    receipt = {"schema_version": 1, "review_source_policy": REVIEW_SOURCE_POLICY,
        "review_packet_binding": packet["binding"],
        "baseline_inventory": before, "candidate_inventory": after,
        "plan_sha256": sha(original / "candidate_plan.json"), "worker_receipt_ref": pointer(directory / "reviewer/worker.json"),
        "input_inventory": inventory(review_input),
        "decision": reviewer["submission"], "contract_ref": task["review_contract"], "checklist_ref": task["review_checklist"],
        "boundaries_ref": task["review_boundaries"], "prompt_ref": pointer(review_input / "prompt.txt")}
    dump(original / "candidate_review.json", receipt)
    if not reviewer["submission"]["accepted"]:
        result["status"] = "source_review_rejected"


def evaluate_candidate(manifest, plan, row, directory, workspace, started, result):
    worker = result["worker"]
    if worker["status"] == "completed":
        materialized = directory / "worker/root/work"
        result["changed_files"] = validate_candidate(workspace / "baseline", materialized / "candidate")
        if not (materialized / "candidate_plan.json").is_file():
            raise ValueError("worker omitted its intervention plan")
        dump(directory / "candidate-freeze.json", {"source_sha256": tree_sha(materialized / "candidate"),
                                                   "plan_sha256": sha(materialized / "candidate_plan.json")})
        remaining = budget_seconds(plan) - (time.monotonic() - started)
        if remaining <= 0:
            result["status"] = "over_wall_time_budget"
        else:
            controller_workspace = directory / "controller-workspace"
            shutil.copytree(materialized, controller_workspace)
            # Local staging consumes the original task deadline too.
            remaining = budget_seconds(plan) - (time.monotonic() - started)
            if remaining <= 0:
                result["status"] = "over_wall_time_budget"
                return
            substitutions = {"workspace": str(controller_workspace), "result": str(directory / "evaluation.json"),
                             "evaluation_output": str(directory.parents[1]),
                             "operator": row["operator"], "seed": str(row["seed"]), "run_id": row["run_id"],
                             "seconds": str(remaining),
                             "task_launch": result.get("task_launch_ref", {}).get("path", ""),
                             "task_launch_ref": result.get("task_launch_ref", {}).get("sha256", ""),
                             "deadline_monotonic": str(started + budget_seconds(plan))}
            task_environment = ({"APROF_TASK_LAUNCH_PATH": result["task_launch_ref"]["path"],
                "APROF_TASK_LAUNCH_SHA256": result["task_launch_ref"]["sha256"],
                "APROF_TASK_DEADLINE_MONOTONIC": substitutions["deadline_monotonic"]}
                if result.get("task_launch_ref") else {})
            argv = [value.format_map(substitutions) for value in manifest["evaluator"]["argv"]]
            if _task_mode(manifest) and (manifest["evaluator"]["argv"] != _task_argv()
                    or not result.get("task_launch_ref")):
                raise ValueError("Task controller entry or original supervisor launch is missing")
            execution = run_job({"job_id": row["run_id"], "argv": argv, "cwd": str(ROOT),
                "output_dir": str(directory / "controller"), "timeout_seconds": remaining,
                "deadline_monotonic": started + budget_seconds(plan),
                # The formal device timer owns the lock. An outer lock deadlocks it.
                "environment": {**manifest["evaluator"].get("environment", {}), **task_environment,
                    **({"APROF_SKILL_LIB": manifest["libraries"]["candidate"]["path"],
                        "PYTHONPATH": str(Path(manifest["libraries"]["candidate"]["path"]) / "runtime/src"),
                        "PYTHONDONTWRITEBYTECODE": "1"} if _task_mode(manifest) else {}),
                    "APROF_EVALUATION_SEED": str(row["seed"]),
                    "ASCEND_RT_VISIBLE_DEVICES": str(manifest["evaluator"]["physical_device"]),
                    "APROF_PHYSICAL_DEVICE": str(manifest["evaluator"]["physical_device"]),
                    "APROF_LOGICAL_DEVICE": "0"}})
            result["controller"] = execution
            result["status"] = execution["status"]
            if execution["status"] == "passed":
                receipt = load(directory / "evaluation.json")
                if _task_mode(manifest) != (receipt.get("kind") == "task_validation_evaluation"):
                    raise ValueError("controller receipt differs from the frozen measurement mode")
                if _task_mode(manifest):
                    _verify_task_controller(manifest, row, directory, receipt, execution, result["task_launch_ref"])
                result["controller_observation"] = {key: receipt.get(key) for key in (
                    "counts", "full_declared_correctness", "cases", "failure", "formal_outcome")}
                result["controller_observation"]["receipt"] = {"path": str(directory / "evaluation.json"), "sha256": sha(directory / "evaluation.json")}
                trace, speedup = replay_evaluation(receipt, Path(manifest["libraries"]["candidate"]["path"]), row, materialized)
                result.update(trace["score"] if _task_mode(manifest) else score(receipt))
                if result["correct"] and trace["result"]["verdict"] == "production_safe_gain":
                    result["deployed_speedup"] = speedup


def summarize(output):
    roster = load(output / "matrix.json")["runs"]
    rows = []
    for row in roster:
        path = output / "runs" / row["run_id"] / "result.json"
        rows.append(load(path) if path.exists() else {**row, "status": "not_run"})
    report = {"schema_version": 1, "runs": rows,
              "complete": all(row["status"] not in ("not_run", "incomplete") for row in rows),
              "publication_verdict": "requires paired comparison and correctness review; this runner never publishes"}
    dump(output / "summary.json", report)
    return report


def validate_source_bundle(store, reference, tree, inventory):
    bundle = load(store.verify_artifact(reference))
    if bundle.get("schema_version") != "1.0.0" or not isinstance(bundle.get("files"), dict):
        raise ValueError("formal source must use the frozen profiler source-bundle JSON schema")
    for file_reference in bundle["files"].values():
        store.verify_artifact(file_reference)
    if bundle["files"] != inventory(tree):
        raise ValueError("formal source bundle differs from the clean worker source tree")


def replay_evaluation(receipt, release, row, materialized):
    """A host evaluator must attach the real frozen machine outcome, including failures."""
    if receipt.get("kind") == "task_validation_evaluation":
        return _replay_task_evaluation(receipt, release, row, materialized)
    runtime = release / "runtime/src"
    sys.path.insert(0, str(runtime))
    import aprof_runtime
    from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory, verify_store_connection
    from aprof_runtime.traces import validate_optimization_trace
    from aprof_runtime.contracts import CandidateEpisode
    if Path(aprof_runtime.__file__).resolve().parent != (runtime / "aprof_runtime").resolve():
        raise ValueError("publication verification requires the candidate runtime in a fresh process")
    profiler_path = release / "skills/ascendc-aprof-profiling/scripts/profile_capture.py"
    specification = importlib.util.spec_from_file_location("aprof_eval_profile_capture", profiler_path)
    profiler = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(profiler)

    class Replay(_ReadOnlyArtifacts):
        def object_path(self, reference):
            return self.verify_artifact(reference)

        def register_artifact(self, path, **_kwargs):
            reference = sha(path)
            self.verify_artifact(reference)
            return reference

    trace = load(checked(receipt["trace"]))
    database = checked(receipt["store"])
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as connection:
        objects = default_object_directory(database)
        verify_store_connection(connection, objects)
        store = Replay(connection, objects)
        validate_optimization_trace(trace, store)
        outcome = trace["result"]
        if outcome["episode_ref"]:
            saved = connection.execute("SELECT payload_json FROM episodes WHERE episode_hash=?", (outcome["episode_ref"],)).fetchone()
            episode = CandidateEpisode.from_dict(json.loads(saved[0]))
            artifacts = episode.evidence.artifacts
            measured_speedup = episode.outcome.speedup
        elif outcome["exploration_outcome_ref"]:
            formal = load(store.verify_artifact(outcome["exploration_outcome_ref"]))
            request = load(store.verify_artifact(formal["request_hash"]))
            evidence = next(item for item in request["evidence"] if item["candidate_id"] == trace["identity"]["candidate_id"])
            artifacts, measured_speedup = evidence["artifacts"], formal["speedup"]
        else:
            raise ValueError("evaluation has no replayable machine outcome")
        accuracy = load(store.verify_artifact(artifacts["accuracy_report"]))
        cases = load(store.verify_artifact(artifacts["evaluation_case_report"]))
        if cases != receipt["cases"] or accuracy["case_ids"] != [case["case_id"] for case in cases]:
            raise ValueError("per-case summary differs from gate-bound measurements")
        if accuracy["passed_case_ids"] != [case["case_id"] for case in cases if case["correct"]]:
            raise ValueError("per-case correctness differs from gate-bound correctness report")
        from validation_host_evaluator import ref as controller_ref, verify_correctness_report
        correctness = verify_correctness_report(controller_ref(store.verify_artifact(accuracy["reports_ref"])))
        if [row["correct"] for row in correctness["rows"]] != [case["correct"] for case in cases]:
            raise ValueError("gate accuracy differs from original per-case verifier receipts")
        report = load(store.verify_artifact(artifacts["measurement_report"]))
        from timing_admission import verify_timing_admission, verify_boundary_report, verify_profile_window
        expected = {"run_id": trace["identity"]["run_id"], "candidate_id": trace["identity"]["candidate_id"],
            "operator": row["operator"], "source_hashes": {role: trace["provenance"][role + "_source_hash"] for role in ("baseline", "candidate")},
            "purpose": "evaluation",
            "registration_ref": artifacts["qualification_registration"],
            "hardware_report_ref": artifacts["hardware_report"],
            "formal_refs": {"raw_ref": artifacts["timing_raw"], "config_ref": artifacts["timing_config"], "report_ref": artifacts["measurement_report"]}}
        admission = verify_timing_admission(store, artifacts["control_report"], expected=expected)
        verify_profile_window(store, artifacts["mechanism_report"], window=admission["stage_windows"]["profile"],
                              control_report_ref=artifacts["control_report"])
        control = load(store.verify_artifact(artifacts["control_report"]))
        if "boundary_report" in artifacts:
            if "boundary" in admission.get("stage_windows", {}):
                expected["boundary_window"] = admission["stage_windows"]["boundary"]
            verify_boundary_report(store, artifacts["boundary_report"], protocol_ref=control["protocol_ref"], expected=expected)
        from eval_candidate_evidence import verify_candidate_evidence
        reviewed = verify_candidate_evidence(materialized, release)
        if (not reviewed["accepted"] or load(store.verify_artifact(artifacts["source_review"])) != reviewed["source_review"]
                or load(store.verify_artifact(artifacts["route_receipt"])) != reviewed["route_receipt"]):
            raise ValueError("machine evidence differs from independent source review or route")
        for case, measured in zip(cases, report["per_case"], strict=True):
            if any(case[role + "_us"] != measured[role + "_median_ns"] / 1000 for role in ("baseline", "candidate")):
                raise ValueError("reported per-case latency differs from raw device samples")
        for role in ("baseline", "candidate"):
            validate_source_bundle(store, trace["provenance"][role + "_source_hash"],
                                   materialized / role, profiler.source_inventory)
    if (trace["identity"]["operator"] != row["operator"] or trace["identity"]["run_id"] != row["run_id"]
            or trace["identity"]["split"] != "validation"):
        raise ValueError("evaluation machine trace identity differs")
    if (trace["validation"]["case_count"] != len(receipt["cases"])
            or trace["validation"]["passed_count"] != sum(case["correct"] is True for case in receipt["cases"])):
        raise ValueError("evaluation correctness differs from machine trace")
    return trace, measured_speedup


def verify_publication(output: Path, *, release: Path) -> dict:
    """Read-only stable-release gate; all 45 trials, including failures, are retained."""
    output, release = output.resolve(), release.resolve()
    manifest = load(output / "freeze.json")
    plan = validate_freeze(manifest)
    if checked(manifest["libraries"]["candidate"], library=True) != release:
        raise ValueError("validation candidate differs from release being sealed")
    roster = load(output / "matrix.json")
    if (roster["freeze_sha256"] != sha(output / "freeze.json") or roster["runs"] != matrix(plan)
            or len(roster["runs"]) != 45 or len({row["run_id"] for row in roster["runs"]}) != 45):
        raise ValueError("validation roster differs from frozen 45-run matrix")
    scores, evidence = {}, []
    for row in roster["runs"]:
        directory = output / "runs" / row["run_id"]
        result = load(directory / "result.json")
        if result.get("worker") is None:
            raise ValueError(f"terminal trial {row['run_id']} lacks an authoritative model usage receipt")
        worker = load(directory / "worker/worker.json")
        evidence.append({"path": str(directory / "result.json"), "sha256": sha(directory / "result.json"),
                         "worker": {"path": str(directory / "worker/worker.json"), "sha256": sha(directory / "worker/worker.json")},
                         "events": {"path": str(directory / "worker/events.jsonl"), "sha256": sha(directory / "worker/events.jsonl")}})
        events = [json.loads(line) for line in (directory / "worker/events.jsonl").read_text().splitlines() if line]
        usage = [event["params"]["tokenUsage"]["total"] for event in events
                 if event.get("method") == "thread/tokenUsage/updated"]
        if not usage or worker["usage"] is None:
            raise ValueError("trial lacks authoritative model usage; actual cost must be recorded")
        totals = [item.get("totalTokens") for item in usage]
        if any(type(value) is not int or value < 0 for value in totals) or totals != sorted(totals):
            raise ValueError("authoritative cumulative model usage must be nonnegative and monotonic")
        if (usage and worker["usage"] != usage[-1]) or (not usage and worker["usage"] is not None):
            raise ValueError("altered model usage")
        if (worker["model"] != manifest["model"]["name"] or worker["reasoning_effort"] != manifest["model"]["reasoning_effort"]
                or worker != result["worker"] or any(result.get(key) != value for key, value in row.items())):
            raise ValueError("trial identity or worker receipt differs")
        from eval_tool_broker import CONFIG, tool_specs
        if (worker.get("role") != "proposer" or worker.get("qualification_ref") != manifest["worker_qualification"]
                or worker.get("config") != CONFIG or worker.get("worker_builds") != 0
                or worker.get("budget_policy") != BUDGET_POLICY or result.get("budget_policy") != BUDGET_POLICY):
            raise ValueError("trial did not use the qualified tool-only worker")
        calls = [json.loads(line) for line in checked(worker["broker_ref"]).read_text().splitlines() if line]
        allowed = {item["name"] for item in tool_specs(wiki=row["arm"] == "skill-plus-wiki")}
        if any(item["tool"] not in allowed for item in calls):
            raise ValueError("trial used a tool outside its frozen arm")
        reviewer = result.get("reviewer")
        review_tokens = 0
        if bool(result.get("reviewer_started")) != (directory / "reviewer").exists():
            raise ValueError("trial reviewer lifecycle differs from its recorded artifacts")
        if result.get("reviewer_started"):
            if reviewer is None or reviewer.get("usage") is None:
                raise ValueError("started reviewer lacks authoritative model usage")
            recorded_reviewer = load(directory / "reviewer/worker.json")
            reviewer_events = [json.loads(line) for line in checked(recorded_reviewer["events_ref"]).read_text().splitlines() if line]
            reviewer_usage = [event["params"]["tokenUsage"]["total"] for event in reviewer_events if event.get("method") == "thread/tokenUsage/updated"]
            reviewer_totals = [item.get("totalTokens") for item in reviewer_usage]
            if (recorded_reviewer != reviewer or not reviewer_usage or reviewer_usage[-1] != reviewer["usage"]
                    or any(type(value) is not int or value < 0 for value in reviewer_totals) or reviewer_totals != sorted(reviewer_totals)
                    or reviewer["model"] != manifest["model"]["name"] or reviewer["reasoning_effort"] != manifest["model"]["reasoning_effort"]
                    or reviewer["qualification_ref"] != manifest["worker_qualification"] or reviewer["role"] != "reviewer"
                    or reviewer.get("budget_policy") != BUDGET_POLICY):
                raise ValueError("independent reviewer identity or usage differs")
            review_tokens = max(item["totalTokens"] for item in reviewer_usage)
            evidence.append({"reviewer": {"path": str(directory / "reviewer/worker.json"), "sha256": sha(directory / "reviewer/worker.json")}})
        total_tokens = usage[-1]["totalTokens"] + review_tokens
        if (result.get("total_model_tokens") != total_tokens
                or not valid_model_cost(usage[-1]["totalTokens"], review_tokens, total_tokens)):
            raise ValueError("trial total does not include all proposer and reviewer model tokens")
        evidence.append(verify_dispatch(output, row, result))
        fallback = {"correct": False, "deployed_speedup": 1.0, "regression_cases": [],
                    "failure": result["status"], "duration_seconds": result["duration_seconds"], "usage": worker["usage"], "total_model_tokens": total_tokens}
        if (worker["status"] != "completed"
                or result["duration_seconds"] > budget_seconds(plan) or result["status"] != "passed"):
            if result["status"] in ("not_run", "incomplete"):
                raise ValueError("all 45 trials must have a recorded terminal outcome")
            scores[(row["operator"], row["seed"], row["arm"])] = fallback
            continue
        materialized = directory / "worker/root/work"
        if not result.get("reviewer_started") or reviewer is None:
            raise ValueError("successful trial omitted independent source review")
        from eval_candidate_evidence import verify_candidate_evidence
        reviewed = verify_candidate_evidence(materialized, release, model=manifest["model"],
            baseline_qualification=manifest["tasks"][row["operator"]]["baseline_qualification"])
        if not reviewed["accepted"]:
            raise ValueError("successful trial has an unaccepted source review")
        if reviewed["route_receipt"]["registry_ref"] != manifest["tasks"][row["operator"]]["route_registry"]:
            raise ValueError("candidate route differs from this task's frozen qualified-baseline contexts")
        for task_key, receipt_key in (("review_contract", "contract_ref"), ("review_checklist", "checklist_ref"), ("review_boundaries", "boundaries_ref")):
            if reviewed["source_review"][receipt_key] != manifest["tasks"][row["operator"]][task_key]:
                raise ValueError("independent review used different frozen contracts or boundaries")
        frozen = load(directory / "candidate-freeze.json")
        if frozen != {"source_sha256": tree_sha(materialized / "candidate"), "plan_sha256": sha(materialized / "candidate_plan.json")}:
            raise ValueError("candidate changed after model completion")
        task = manifest["tasks"][row["operator"]]
        if tree_sha(materialized / "baseline") != task["baseline"]["sha256"]:
            raise ValueError("trial original baseline differs from frozen task")
        validate_candidate(materialized / "baseline", materialized / "candidate")
        execution = load(directory / "controller/execution.json")
        if execution != result["controller"] or execution["status"] != "passed" or execution["exit_code"] != 0:
            raise ValueError("controller execution receipt differs")
        for key in ("stdout", "stderr"):
            checked(execution[key])
        receipt = load(directory / "evaluation.json")
        if _task_mode(manifest) != (receipt.get("kind") == "task_validation_evaluation"):
            raise ValueError("published receipt differs from the frozen measurement mode")
        if receipt.get("candidate_tree_sha256") != frozen["source_sha256"]:
            raise ValueError("measurements are not bound to the actual worker candidate")
        if _task_mode(manifest):
            if receipt.get("kind") != "task_validation_evaluation":
                raise ValueError("Task evaluation cannot substitute an Event/SQLite receipt")
            _verify_task_controller(manifest, row, directory, receipt, execution, result["task_launch_ref"])
        trace, measured_speedup = replay_evaluation(receipt, release, row, materialized)
        derived = trace["score"] if _task_mode(manifest) else score(receipt)
        derived["deployed_speedup"] = (measured_speedup
            if derived["correct"] and trace["result"]["verdict"] == "production_safe_gain" else 1.0)
        scores[(row["operator"], row["seed"], row["arm"])] = derived
        evidence.append({"path": str(directory / "evaluation.json"), "sha256": sha(directory / "evaluation.json")})
    comparisons = {}
    for arm in ARMS[1:]:
        pairs = [(scores[(op, seed, "baseline")], scores[(op, seed, arm)])
                 for op in plan["operators"] for seed in plan["seeds"]]
        comparisons[arm] = paired_comparison(pairs)
    primary = comparisons[PUBLICATION_CRITERION["primary_arm"]]
    if not primary["no_correctness_decline"] or primary["bootstrap_95_lower"] <= 1:
        raise ValueError("primary skill+Wiki comparison does not support improvement without correctness decline")
    return {"accepted": True, "trial_count": 45, "comparisons": comparisons, "receipts": evidence,
            "freeze": {"path": str(output / "freeze.json"), "sha256": sha(output / "freeze.json")}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("manifest", type=Path)
    p.add_argument("output", type=Path)
    p = sub.add_parser("run")
    p.add_argument("output", type=Path)
    p.add_argument("run_id")
    p = sub.add_parser("_execute", help=argparse.SUPPRESS)
    p.add_argument("output", type=Path)
    p.add_argument("run_id")
    p.add_argument("--launch", type=Path, required=True)
    p.add_argument("--launch-sha256", required=True)
    p = sub.add_parser("_evaluate_task", help=argparse.SUPPRESS)
    p.add_argument("output", type=Path)
    p.add_argument("run_id")
    p.add_argument("--workspace", type=Path, required=True)
    p.add_argument("--result", type=Path, required=True)
    p.add_argument("--launch", type=Path, required=True)
    p.add_argument("--launch-sha256", required=True)
    p = sub.add_parser("summarize")
    p.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "prepare":
        answer = prepare(args.manifest.resolve(), args.output.resolve())
    elif args.command == "run":
        answer = dispatch(args.output.resolve(), args.run_id)
    elif args.command == "_execute":
        answer = execute(args.output.resolve(), args.run_id,
            launch_path=args.launch.resolve(), launch_sha256=args.launch_sha256)
    elif args.command == "_evaluate_task":
        manifest = load(args.output / "freeze.json")
        row = next(row for row in load(args.output / "matrix.json")["runs"] if row["run_id"] == args.run_id)
        if not _task_mode(manifest) or manifest["evaluator"]["argv"] != _task_argv():
            raise ValueError("trusted Task entry requires a frozen Task evaluation")
        answer = _task_api(manifest["libraries"]["candidate"]["path"]).execute_evaluation(
            manifest, row, args.workspace.resolve(), args.result.resolve(),
            launch_path=args.launch.resolve(), launch_sha256=args.launch_sha256)
    else:
        answer = summarize(args.output.resolve())
    print(json.dumps(answer, ensure_ascii=False, allow_nan=False))
    if args.command == "_execute" and answer["status"] not in ("passed", "noop"):
        raise SystemExit(2)
    if args.command == "_evaluate_task" and answer["status"] != "completed":
        raise SystemExit(2)
