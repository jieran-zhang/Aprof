#!/usr/bin/env python3
"""Prepare and drive the manifest-based Level2 campaign using AProf evidence tools.

Preparation only snapshots sources and generates CPU inputs. Hardware stages are
explicit commands and keep isolated outputs; none run at import time.
"""
from __future__ import annotations

from aprof_layout import skill_lib, bind_run, verify_run, identity

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import msprof_exploration_campaign as campaign
from msprof_exploration_execute import event, extract_source, pointer, save, sha
from prepare_trace_pilot import create_source_snapshot, DEFAULT_EXCLUDES

ROOT = Path(__file__).resolve().parents[3]
OPERATORS = (
    "apply_adam_w", "arg_max", "cross_entropy_loss", "cummin", "gcd",
    "grid_sampler_3d", "maximum", "resize_bilinear", "unsorted_segment_sum",
    "dynamic_quant", "group_norm", "apply_rotary_pos_emb", "gather",
    "rms_norm", "scatter", "softmax",
)
ALL_CASES = list(range(1, 21))


def load(path):
    return json.loads(Path(path).read_text())


def now():
    return datetime.now(timezone.utc).isoformat()


def original_splits():
    result = {}
    for split in ("train", "validation", "test"):
        for name in (ROOT / f"scaffolding/benchmarks/cannbench/{split}/operators.txt").read_text().splitlines():
            if name.strip():
                if name in result:
                    raise ValueError("operator belongs to multiple original splits")
                result[name] = split
    return result


def task_path(run, operator):
    if operator not in OPERATORS:
        raise ValueError("not a Level2 operator")
    split = "validation" if original_splits()[operator] == "validation" else "train"
    return Path(run).resolve() / split / "tasks" / operator


def prepare_task(run, operator):
    task = task_path(run, operator)
    done = task / "preparation.json"
    if done.exists():
        record = load(done)
        if sha(task / "baseline-source.tar") != record["baseline"]["sha256"]:
            raise ValueError("prepared baseline changed")
        return record
    if task.exists():
        raise FileExistsError(f"partial preparation requires inspection: {task}")
    task.mkdir(parents=True)
    source = ROOT / "scaffolding/benchmarks/cannbench/operators" / operator
    snapshot = create_source_snapshot(source, task / "baseline-source.tar", root_label=operator,
                                      excludes=DEFAULT_EXCLUDES + ("results.json",))
    extract_source(task / "baseline-source.tar", task / "baseline")
    source_split = original_splits()[operator]
    split = "validation" if source_split == "validation" else "train"
    save(task / "baseline-binding.json", {**pointer(task / "baseline-source.tar"),
                                          "origin": {"checkout": str(ROOT), "operator_path": str(source)}})
    save(task / "split.json", {"split": split, "source_split": source_split,
                               "original_split_version": "v0001", "known_workload_optimization": True,
                               "held_out_claim": False, "graph_policy_eligible": False})
    event(task, "baseline_frozen", {"baseline": pointer(task / "baseline-source.tar"),
                                    "source_split": source_split, "split": split})
    record = {"version": campaign.FRESH_PROTOCOL, "operator": operator, "split": split,
              "source_split": source_split, "prepared_at": now(),
              "baseline": pointer(task / "baseline-source.tar"), "file_count": snapshot["file_count"]}
    save(done, record)
    return record


def generate_inputs(run, operator, *, retry=False):
    """One CPU Python process per operator; preserve the original generators."""
    prepare_task(run, operator)
    task = task_path(run, operator)
    finished = task / "input-bindings.json"
    if finished.exists():
        bindings = load(finished)
        for row in bindings["cases"]:
            for ref in [row["metadata"], row["verifier"], *row["inputs"].values()]:
                if sha(ref["path"]) != ref["sha256"]:
                    raise ValueError("prepared input identity changed")
        return {"operator": operator, "status": "verified_existing", "cases": len(bindings["cases"])}
    out = task / "input-generation"
    if out.exists():
        previous = load(out / "execution.json") if (out / "execution.json").exists() else None
        if not retry or previous is None or previous["status"] != "failed":
            raise ValueError("previous input generation must be closed and explicitly retried")
        number = 1
        while (task / f"input-generation-retry-{number:02d}").exists(): number += 1
        out = task / f"input-generation-retry-{number:02d}"
    out.mkdir(exist_ok=False)
    inputs = task / ("inputs" if out.name == "input-generation" else out.name.replace("input-generation", "inputs"))
    # Generators that use mmap flush can stall on the shared filesystem. Run the
    # unchanged program on local scratch, then freeze exact data bytes and record
    # the mechanical metadata path relocation separately.
    scratch = Path(tempfile.mkdtemp(prefix="aprof-level2-" + operator + "-"))
    code = ("import runpy,sys\nfrom pathlib import Path\n"
            "script=Path(sys.argv[1]); output=sys.argv[2]\n"
            "sys.path.insert(0,str(script.parent))\n"
            "for case in range(1,21):\n"
            " sys.argv=[str(script),'--case',str(case),'--output',output]\n"
            " runpy.run_path(str(script),run_name='__main__')\n")
    driver = out / "generate_all.py"
    driver.write_text(code)
    argv = [sys.executable, "-B", str(driver), str(task / "baseline/scripts/gen_data.py"), str(scratch)]
    record = {"argv": argv, "cwd": str(task / "baseline"), "started_at": now(),
              "driver": pointer(driver), "generator": pointer(task / "baseline/scripts/gen_data.py"),
              "hardware_executed": False, "scratch": str(scratch), "frozen_input_root": str(inputs)}
    save(out / "started.json", record)
    event(task, "input_generation_started", {"request": pointer(out / "started.json")})
    env = dict(os.environ, OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2",
               PYTHONDONTWRITEBYTECODE="1", ASCEND_RT_VISIBLE_DEVICES="")
    error = None
    try:
        with (out / "stdout.log").open("xb") as stdout, (out / "stderr.log").open("xb") as stderr:
            result = subprocess.run(argv, cwd=task / "baseline", env=env, stdout=stdout, stderr=stderr, timeout=3600)
        if result.returncode:
            raise RuntimeError(f"input generator failed ({result.returncode}); see {out}")
        shutil.copytree(scratch, inputs)
        relocated = []
        def relocate(value):
            if isinstance(value, str) and value.startswith(str(scratch) + "/"):
                return str(inputs) + value[len(str(scratch)):]
            if isinstance(value, dict): return {k: relocate(v) for k,v in value.items()}
            if isinstance(value, list): return [relocate(v) for v in value]
            return value
        for case in ALL_CASES:
            original = scratch / f"case_{case:02d}/metadata.json"
            frozen = inputs / f"case_{case:02d}/metadata.json"
            snapshot = out / f"original-metadata-{case:02d}.json"
            shutil.copyfile(original, snapshot)
            frozen.write_text(json.dumps(relocate(load(original)), indent=2, ensure_ascii=False, allow_nan=True) + "\n")
            relocated.append({"case_id": case, "original": pointer(snapshot), "relocated": pointer(frozen)})
        save(out / "metadata-relocation.json", {"from": str(scratch), "to": str(inputs),
             "scope": "absolute path strings only; tensor bytes, case semantics and oracle unchanged", "cases": relocated})
        rows = []
        for case in ALL_CASES:
            directory = inputs / f"case_{case:02d}"
            metadata = directory / "metadata.json"
            if not metadata.is_file():
                raise ValueError(f"input generator omitted case {case}")
            files = {p.relative_to(directory).as_posix(): pointer(p)
                     for p in sorted(directory.rglob('*')) if p.is_file() and p != metadata}
            if not files:
                raise ValueError(f"input generator omitted input files for case {case}")
            rows.append({"case_id": case, "metadata": pointer(metadata), "inputs": files,
                         "verifier": pointer(task / "baseline/scripts/verify_result.py")})
        save(finished, {"version": "level2_input_bindings_v1", "operator": operator, "cases": rows})
        save(task / "input-origin.json", {"path": str(inputs), "prepared_locally": True,
                                          "generator": record["generator"], "case_count": 20})
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        save(out / "execution.json", {**record, "finished_at": now(), "status": "failed" if error else "passed",
                                       "error": error, "exit_status": locals().get("result").returncode if "result" in locals() else None})
        event(task, "input_generation_finished", {"execution": pointer(out / "execution.json"), "status": "failed" if error else "passed"})
    return {"operator": operator, "status": "prepared", "cases": 20, "input_bindings": pointer(finished)}


def prepare(run, operators=OPERATORS, jobs=2, *, retry=False):
    run = Path(run).resolve(); bind_run(run)
    def one(operator):
        result = generate_inputs(run, operator, retry=retry)
        print(json.dumps(result), flush=True)
        return result
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(one, operators))


def bootstrap(run, operators=OPERATORS):
    """Declare public task boundaries before algorithm analysis or source edits."""
    run = Path(run).resolve()
    architecture = run / "preflight/architecture_profile.json"
    if not architecture.is_file():
        raise ValueError("a real architecture profile is required")
    references = ["skills/ascendc-aprof-workflow/SKILL.md", "skills/ascendc-aprof-parallel-planning/SKILL.md",
                  "skills/ascendc-aprof-optimization/SKILL.md", "skills/ascendc-aprof-profiling/SKILL.md",
                  "skills/ascendc-aprof-diagnosis/SKILL.md"]
    for operator in operators:
        task = task_path(run, operator)
        if (task / "manifest.json").exists():
            continue
        record = prepare_task(run, operator)
        if not (task / "input-bindings.json").is_file():
            raise ValueError("prepare all inputs before task bootstrap: " + operator)
        save(task / "knowledge-catalog.json", {"operator": operator, "entries": [pointer(skill_lib() / p) for p in references],
              "skill_library": identity(),
              "collection_workflow": pointer(ROOT / "scaffolding/collection/workflows/optimization_experiment_playbook.md"),
              "read_is_not_decision_use": True})
        manifest = {"version": campaign.FRESH_PROTOCOL, "run_id": run.name, "operator": operator,
            "split": record["split"], "source_split": record["source_split"], "task_dir": str(task),
            "baseline_tree": str(task / "baseline"), "baseline": pointer(task / "baseline-source.tar"),
            "input_bindings": pointer(task / "input-bindings.json"), "architecture_profile": pointer(architecture),
            "knowledge_catalog": pointer(task / "knowledge-catalog.json"), "new_source_round_limit": 3,
            "sentinels": [1, 8, 14, 20], "max_predeclared_diagnostic_cases": 2, "correctness_cases": ALL_CASES,
            "hardware_execution": "coordinator_only", "formal_admission": "not_evaluated",
            "graph_policy_eligible": False, "episode_ref": None,
            "known_workload_optimization": True, "held_out_claim": False,
            "instructions": "Analyze algorithm_parallel before execution. Use local knowledge and recorded reads. "
                            "One source intervention per round after closed feedback; failures consume rounds. "
                            "Dispatch only from semantic workload metadata and verified hardware capability. "
                            "Do not author training JSONL or read coordinator-only nonsentinel timings."}
        save(task / "manifest.json", manifest)
        event(task, "task_bootstrapped", {"manifest": pointer(task / "manifest.json")})
    environment = run / "bootstrap/environment.json"
    if not environment.exists():
        save(environment, {"hostname": socket.gethostname(), "physical_device": 0, "cpu": 8,
             "architecture_profile": pointer(architecture), "recorded_at": now(),
             "sdk_path": os.environ.get("ASCEND_HOME_PATH"), "device_use": "serial_host_exclusive",
             "protocol": campaign.FRESH_PROTOCOL})


def preflight(run, operators=OPERATORS):
    """Build each original baseline and obtain real per-case repeat pilots."""
    from msprof_exploration_execute import build_operator
    import level2_pilot
    run = Path(run).resolve()
    bootstrap(run, operators)
    pilot_runner = run / "tools/pilot/build.json"
    if not pilot_runner.exists():
        level2_pilot.build_runner(pilot_runner.parent)
    for operator in operators:
        task = task_path(run, operator)
        if (task / "measurement-policy.json").exists():
            policy = load(task / "measurement-policy.json")
            if sha(policy["pilot"]["path"]) != policy["pilot"]["sha256"]:
                raise ValueError("frozen pilot changed")
            continue
        build = task / "build/build_manifest.json"
        if not build.exists():
            event(task, "baseline_preflight_build_started", {"source": pointer(task / "baseline-source.tar")})
            arch = load(run / "preflight/architecture_profile.json")
            try:
                build_operator(task / "baseline", operator, build.parent, npu_arch="dav-" + str(arch["npu_arch"]))
            except BaseException as exc:
                event(task, "baseline_preflight_build_blocked", {"error": {"type": type(exc).__name__, "message": str(exc)},
                      "build_directory_created": build.parent.exists(), "candidate_attempt": False})
                raise
            event(task, "baseline_preflight_build_completed", {"build": pointer(build)})
        output = task / "preflight/pilot"
        if (output / "pilot.json").exists():
            pilot = load(output / "pilot.json")
        else:
            pilot = level2_pilot.collect(build, pilot_runner, load(task / "input-origin.json")["path"], task / "baseline", output)
        if pilot["status"] != "passed" or [r["case_id"] for r in pilot["cases"]] != ALL_CASES:
            raise ValueError("baseline pilot incomplete: " + operator)
        repeats = {str(row["case_id"]): row["recommended_repeat"] for row in pilot["cases"]}
        # Per process: two configurations, two roles, 10 warmups + 30 pairs.
        estimated_seconds = sum(row["complete_call_us"] / 1e6 * 4 * (10 + 30 * repeats[str(row["case_id"])])
                                for row in pilot["cases"])
        policy = {"version": campaign.FRESH_PROTOCOL, "repeat_by_case": repeats,
                  "pilot": pointer(output / "pilot.json"), "threshold_us": 10000,
                  "timing_timeout_seconds": max(1800, math.ceil(estimated_seconds * 4 + 600)),
                  "timeout_basis": "all20 complete-call pilot cost x4 margin plus600s setup; minimum1800s",
                  "candidate_test_started": False}
        save(task / "measurement-policy.json", policy)
        event(task, "measurement_policy_frozen", {"policy": pointer(task / "measurement-policy.json")})
        print(json.dumps({"operator": operator, "status": "pilot_passed", "repeat_1_cases": [int(k) for k,v in repeats.items() if v==1]}), flush=True)


def freeze_campaign(run):
    """Publish the complete roster and import proven baseline compilation costs."""
    from run_msprof_exploration_stage import verify_source_snapshot
    run = Path(run).resolve()
    by_split = {"train": {}, "validation": {}}
    policies = {}
    for operator in OPERATORS:
        task = task_path(run, operator)
        manifest = load(task / "manifest.json")
        policy = load(task / "measurement-policy.json")
        if sha(policy["pilot"]["path"]) != policy["pilot"]["sha256"]:
            raise ValueError("pilot changed")
        verify_source_snapshot(task / "baseline-source.tar", task / "baseline")
        by_split[manifest["split"]][operator] = {"baseline_source_hash": sha(task / "baseline-source.tar"),
            "source_split": manifest["source_split"], "repeat_by_case": policy["repeat_by_case"], "pilot_ref": policy["pilot"]["sha256"]}
        policies[operator] = pointer(task / "measurement-policy.json")
    manifest_path = run / "campaign-manifest.json"
    if not manifest_path.exists():
        save(manifest_path, {"version": campaign.FRESH_SCHEMA, "operators": by_split, "measurement_policies": policies,
             "case_count": 320, "source_attempts_planned": 48, "formal_admission": "not_evaluated",
             "graph_policy_eligible": False, "held_out_claim": False})
    for split, workloads in by_split.items():
        directory = run / split / "ledger"
        ledger = campaign.Campaign(directory) if directory.exists() else campaign.create_fresh(directory,
            campaign_id=run.name + "/" + split, workloads=workloads, provenance={"manifest": pointer(manifest_path)})
        for operator in workloads:
            task = task_path(run, operator)
            if "baseline-preflight-build" in ledger.state["tasks"][operator]["stages"]:
                continue
            build = task / "build/build_manifest.json"
            result = load(task / "build/build-execution/execution.json")
            if result["status"] != "passed": raise ValueError("baseline build failed")
            ledger.start(event_id=operator + "-import-baseline-build-start", workload=operator,
                stage_id="baseline-preflight-build", kind="build", plan={"source_hash": workloads[operator]["baseline_source_hash"],
                    "preflight_evidence_import": True, "execution": pointer(task / "build/build-execution/execution.json")})
            ledger.finish(event_id=operator + "-import-baseline-build-finish", workload=operator,
                stage_id="baseline-preflight-build", outcome="success", evidence={"build": pointer(build)},
                native_started=False, actual_costs={"baseline_build_commands": 1, "cmake_configure_commands": 1},
                reason="Import the previously recorded preflight compilation; no new invocation or candidate budget charge.")
    return pointer(manifest_path)


def freeze_engineering(run, *, historical_continuation=False):
    """Snapshot actual producer/knowledge bytes before use, with task root seals."""
    run = Path(run).resolve()
    root = run / "bootstrap"
    number = len(list(root.glob("frozen-engineering-*.json"))) + 1
    files = []
    if historical_continuation:
        if (run / "skill-lib.json").exists():
            raise ValueError("historical continuation requires an unbound legacy run")
        binding = identity()
    else:
        binding = verify_run(run)
    collector_roots = [ROOT / "scaffolding/collection", ROOT / "scaffolding/benchmarks/cannbench/harness",
                       ROOT / "scaffolding/benchmarks/cannbench/task_specs"]
    package = skill_lib()
    release_files = __import__("json").loads((package / "release.json").read_text())["files"]
    paths = sorted({path for directory in collector_roots for path in directory.rglob("*")}
                   | {package / name for name in release_files} | {package / "release.json"})
    for path in paths:
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc": continue
        digest = sha(path)
        snapshot = root / "source-cas" / digest[7:]
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.exists():
            if sha(snapshot) != digest: raise ValueError("engineering CAS corruption")
        else:
            with snapshot.open("xb") as output: output.write(path.read_bytes())
        files.append({"path": str(path), "sha256": digest, "snapshot": str(snapshot)})
    value = {"version": "level2_frozen_engineering_v1", "recorded_at": now(), "files": files,
             "skill_library": binding,
             "skill_files": [row["path"] for row in files if Path(row["path"]).is_relative_to(package)],
             "collector_files": [row["path"] for row in files if not Path(row["path"]).is_relative_to(package)],
             "task_manifests": [pointer(task_path(run, op) / "manifest.json") for op in OPERATORS
                                if (task_path(run, op) / "manifest.json").is_file()]}
    if (run / "campaign-manifest.json").exists(): value["campaign_manifest"] = pointer(run / "campaign-manifest.json")
    path = root / f"frozen-engineering-{number:03d}.json"
    save(path, value)
    return pointer(path)


def publish_preflight_feedback(run, operator):
    """Expose only declared search cases from the coordinator's baseline pilot."""
    task = task_path(run, operator)
    target = task / "feedback/baseline-preflight.json"
    if target.exists(): return pointer(target)
    pilot_path = task / "preflight/pilot/pilot.json"
    pilot = load(pilot_path)
    if pilot["status"] != "passed" or {r["case_id"] for r in pilot["cases"]} != set(ALL_CASES):
        raise ValueError("public initial feedback requires complete baseline pilot")
    declaration = task / "agent/diagnostic_requests.json"
    declared = load(declaration) if declaration.exists() else {}
    probes = declared.get("requests", declared.get("cases", []))
    probes = [{"case_id": p["case_id"], "purpose": p.get("purpose", p.get("reason"))} for p in probes]
    if len(probes) > 2 or any(p["case_id"] in campaign.SENTINELS or not p.get("purpose") for p in probes):
        raise ValueError("at most two distinct nonsentinel probes with public purpose")
    ids = [*campaign.SENTINELS, *[p["case_id"] for p in probes]]
    if len(set(ids)) != len(ids) or any(c not in ALL_CASES for c in ids): raise ValueError("invalid probe case IDs")
    save(target, {"version": "level2_baseline_public_preflight_v1", "operator": operator,
        "scope": "Original prepared complete-call pilot: one measured call after one warmup, for initial hypotheses only; not paired gain or formal gate.",
        "cases": [row for row in pilot["cases"] if row["case_id"] in ids], "revealed_case_ids": ids,
        "source": pointer(task / "baseline-source.tar"), "evidence": pointer(pilot_path),
        "probe_declaration": pointer(declaration) if declaration.exists() else None,
        "all20_prepared_outputs_passed": True, "standalone_runtime_gate": "pending", "formal_admission": "not_evaluated"})
    event(task, "baseline_public_preflight_published", {"feedback": pointer(target), "case_ids": ids})
    return pointer(target)


def materialize_candidate(run, operator, candidate_id):
    """Bind author-supplied plan drafts to the actual immutable implementation.

    This fills only content identities and metadata selections. It never invents
    a hypothesis, phase, decision or source intervention on the author's behalf.
    """
    from aprof_runtime.jsonio import content_hash
    from aprof_runtime.planning import validate_planning_contract, select_dispatch
    from level2_adapters import workload_metadata
    from shared_context_build import source_hash
    run = Path(run).resolve()
    task = task_path(run, operator); parent = task / "candidates" / candidate_id
    source = parent / "op"
    final = parent / "proposal.json"
    if final.exists(): raise FileExistsError(final)
    draft_path = parent / "proposal.draft.json"
    draft = load(draft_path)
    if draft.get("candidate_id") != candidate_id or draft.get("operator") != operator:
        raise ValueError("candidate author identity differs")
    preview = parent / "pre-registration-source.tar"
    if not preview.exists(): create_source_snapshot(source, preview, root_label=candidate_id)
    else:
        from run_msprof_exploration_stage import verify_source_snapshot
        verify_source_snapshot(preview, source)
    implementation = sha(preview)
    profile_path = task / "agent/architecture_profile.json"
    profile = validate_planning_contract("architecture_profile", load(profile_path))
    plan_path = parent / "parallel_plan.json"
    plan = validate_planning_contract("parallel_plan", load(plan_path))
    dispatch = load(parent / "dispatch_plan.proposed.json")
    dispatch.update(source_hash=implementation, implementation_source_hash=implementation,
                    plan_basis_source_hash=plan["source_hash"], parallel_plan_ref=content_hash(plan),
                    architecture_profile_ref=content_hash(profile))
    validate_planning_contract("dispatch_plan", dispatch)
    dispatch_path = parent / "dispatch_plan.json"; save(dispatch_path, dispatch)
    sequences = load(parent / "dispatch-sequences.proposed.json")
    for row in sequences.values(): row.setdefault("auxiliary_tasks", [])
    save(parent / "dispatch-launch.json", {"version": "level2_dispatch_launch_v1", "source_sha256": source_hash(source),
        "dispatch_plan": dispatch, "sequences": sequences})
    graph_root = run / "graph/v0002"
    if not graph_root.exists(): shutil.copytree(skill_lib() / "skillgraph/versions/v0002", graph_root)
    graph = load(graph_root / "graph.json")
    selections = []
    for row in load(task / "input-bindings.json")["cases"]:
        metadata = workload_metadata(operator, load(row["metadata"]["path"]))
        selections.append({"case_id": row["case_id"], "metadata": metadata, **select_dispatch(dispatch, metadata)})
    # Selection evidence is closed over actual public read snapshots, without
    # assuming that reading an artifact proves it influenced a decision.
    refs = {ref for group in plan["groups"] for ref in group["selection_evidence"]}
    evidence = []
    for directory in (task / "read-evidence", task / "agent", task / "baseline", run / "preflight"):
        for path in sorted(directory.rglob("*")):
            if path.is_file() and sha(path) in refs:
                evidence.append(pointer(path)); refs.discard(evidence[-1]["sha256"])
    if refs: raise ValueError("parallel plan has unclosed selection evidence: " + str(sorted(refs)))
    proposal = {**draft, "source_dir": str(source), "plan_basis_source_hash": plan["source_hash"],
        "implementation_source_hash": implementation, "architecture_profile_ref": content_hash(profile),
        "parallel_plan_ref": content_hash(plan), "dispatch_plan_ref": content_hash(dispatch),
        "graph_hash": content_hash(graph), "dispatch_selections": selections,
        "artifacts": {"author_draft": pointer(draft_path), "architecture_profile": pointer(profile_path),
            "parallel_plan": pointer(plan_path), "dispatch_plan": pointer(dispatch_path),
            "graph_snapshot": pointer(graph_root / "graph.json"), "dispatch_launch": pointer(parent / "dispatch-launch.json"),
            "planning_evidence": evidence}}
    if draft.get('semantic_guard_draft') is not None:
        from level2_guard_contract import materialize
        proposal['artifacts']['semantic_guard_contract'] = materialize(
            task, parent, draft['semantic_guard_draft'], implementation, pointer(dispatch_path))
    save(final, proposal)
    event(task, "candidate_identities_materialized", {"candidate_id": candidate_id, "proposal": pointer(final),
        "author_draft": pointer(draft_path), "implementation": pointer(preview), "source_changed_here": False})
    return pointer(final)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("prepare")
    p.add_argument("--skill-lib", type=Path, help="complete stable release; required for new runs unless APROF_SKILL_LIB is set")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--operator", action="append", choices=OPERATORS)
    p.add_argument("--jobs", type=int, choices=(1, 2), default=2)
    p.add_argument("--retry-failed-inputs", action="store_true")
    for command in ("bootstrap", "preflight", "freeze", "freeze-engineering", "publish-preflight", "materialize"):
        p = sub.add_parser(command)
        p.add_argument("--run", type=Path, required=True)
        if command in ("bootstrap", "preflight"): p.add_argument("--operator", action="append", choices=OPERATORS)
        if command in ("publish-preflight", "materialize"): p.add_argument("--operator", required=True, choices=OPERATORS)
        if command == "materialize": p.add_argument("--candidate", required=True)
    args = parser.parse_args(argv)
    if args.command != "prepare":
        verify_run(args.run)
    if args.command == "prepare":
        prepare(args.run, args.operator or OPERATORS, args.jobs, retry=args.retry_failed_inputs)
    elif args.command == "bootstrap": bootstrap(args.run, args.operator or OPERATORS)
    elif args.command == "preflight": preflight(args.run, args.operator or OPERATORS)
    elif args.command == "freeze": print(json.dumps(freeze_campaign(args.run)))
    elif args.command == "freeze-engineering": print(json.dumps(freeze_engineering(args.run)))
    elif args.command == "publish-preflight": print(json.dumps(publish_preflight_feedback(args.run, args.operator)))
    else: print(json.dumps(materialize_candidate(args.run, args.operator, args.candidate)))


if __name__ == "__main__":
    main()
