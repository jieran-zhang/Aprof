#!/usr/bin/env python3
"""Freeze three closed Level2 source attempts and evaluate every safe candidate.

Only final timing stages execute hardware. --prepare-only freezes their complete
twenty-case plans without executing them. This coordinator never chooses a
winner, authors source, releases spent budget, or creates a graph episode.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import level2_iteration as iteration
import msprof_exploration_campaign as campaign
import msprof_exploration_report as report
import run_msprof_exploration_stage as stage_module
from level2_campaign import OPERATORS
from msprof_exploration_execute import load, pointer, save, sha, task_paths, preflight_cohort
from shared_context_build import source_hash
from msprof_exploration_provenance import verify_pointer_tree

VERSION = "level2_final_evaluation_v1"
GROUP = "final"
INFRA_ERRORS = {"TimeoutExpired", "TimeoutError", "KeyboardInterrupt", "OSError",
                "FileNotFoundError", "PermissionError", "ConnectionError"}


class Unfinished(ValueError):
    """Evidence or work is missing; no successful completion may be emitted."""


def require(condition, message):
    if not condition:
        raise Unfinished(message)


def checked(ref, label):
    require(isinstance(ref, dict) and set(ref) == {"path", "sha256"}, label + " pointer missing")
    require(pointer(ref["path"]) == ref, label + " changed")
    return load(ref["path"])


def producers():
    # Bind this controller and the code which prepares, resumes and interprets
    # its execution. A producer update requires explicit evidence recovery.
    return [pointer(path) for path in (__file__, iteration.__file__, campaign.__file__,
                                      report.__file__, stage_module.__file__)]


def source_identity(task, state, baseline, cid):
    parent = task if cid == "baseline" else task / "candidates" / cid
    archive = parent / ("baseline-source.tar" if cid == "baseline" else "source.tar")
    source = parent / ("baseline" if cid == "baseline" else "op")
    expected = baseline if cid == "baseline" else state["candidates"][cid]["source_hash"]
    require(sha(archive) == expected, "source archive differs: " + cid)
    iteration.verify_source_snapshot(archive, source)
    return source_hash(source)


def recorded_stage(run, operator, cid, sid, row):
    """Read an already finished stage through the strict existing resume path."""
    require(sid.startswith(cid + "-"), "stage ID does not belong to source")
    group = sid[len(cid) + 1:]
    require(group and Path(group).name == group, "unsafe stage group")
    _, _, _, parent, _ = task_paths(run, operator, cid)
    path = parent / "stages" / group / "result.json"
    require(path.is_file(), "stage result missing: " + sid)
    require(row["attempts"] and row["attempts"][-1]["outcome"] is not None,
            "stage has no closed execution: " + sid)
    result = iteration.stage(run, operator, cid, row["kind"], group,
                             plan_path=path.parent / "stage-plan.json")
    verify_pointer_tree(row["attempts"][-1]["evidence"], evidence_path=path)
    return result, pointer(path)


def runtime_evidence(ledger, operator, cid, parent, row):
    """Check actual lifecycle files, not only the ledger's passed status."""
    ref = row["attempts"][-1]["evidence"].get("runtime")
    value = checked(ref, "runtime assessment")
    verify_pointer_tree(value, evidence_path=ref["path"])
    source = ledger.state["tasks"][operator]["candidates"][cid]["source_hash"]
    binding = stage_module.successful_correctness_binding(ledger, operator, cid, parent, source)
    directory = Path(binding["correctness_directory"])
    require(value.get("status") == "passed" and value.get("correctness_stage_result") == binding["correctness_result"]
            and value.get("correctness") == pointer(directory / "completion.json"), "runtime correctness binding differs")
    completion = checked(value["correctness"], "prepared correctness completion")
    require(completion.get("status") == "passed" and sorted(int(r["case_id"]) for r in completion["completed"]) == campaign.ALL_CASES,
            "runtime prepared correctness coverage differs")
    paths = [directory / f"case_{case:02d}/native.json" for case in campaign.ALL_CASES]
    standalone = directory.parent / "standalone/completion.json"
    require(value.get("native_results") == [pointer(p) for p in [*paths, standalone]],
            "runtime lifecycle coverage differs")
    for path in paths:
        native = load(path)
        require(native.get("exit_code") == 0 and all(native.get(k) is True for k in
                ("stream_destroyed", "context_destroyed", "finalized")), "native runtime lifecycle failed")
    original = load(standalone)
    require(original.get("status") == "passed" and original.get("passed_count") == 20,
            "standalone correctness coverage differs")


def audit_attempts(run, operator, ledger, task):
    state = ledger.state["tasks"][operator]
    require(ledger.config["schema_version"] == campaign.FRESH_SCHEMA,
            "finalizer requires a fresh three-round Level2 campaign")
    candidates = state["candidates"]
    require(len(candidates) == state["new_source_attempts"] == state["new_rounds_started"] == 3
            and all(not item["inherited"] for item in candidates.values()),
            "unfinished: exactly three executed source attempts are required")
    baseline = ledger.config["tasks"][operator]["baseline_source_hash"]
    source_identity(task, state, baseline, "baseline")
    audited = []
    for cid, item in candidates.items():
        require(item["feedback_closed"] or state["frozen"], "source feedback is still open: " + cid)
        require(item["observation_ids"], "source has no real closed feedback: " + cid)
        observation = state["observations"][item["observation_ids"][-1]]
        feedback_path = task / "feedback" / (cid + ".json")
        feedback = load(feedback_path)
        require(observation.get("close_feedback") is True
                and observation["report_ref"] == sha(feedback_path)
                and observation["feedback"] == feedback,
                "feedback differs from closed ledger observation: " + cid)
        require(feedback.get("operator") == operator and feedback.get("candidate_id") == cid
                and feedback.get("source_hash") == item["source_hash"]
                and feedback.get("source_parent") == item["source_parent"], "feedback source lineage differs")
        require(feedback.get("status") in ("measured", "source_attempt_failed")
                and not observation.get("quality", {}).get("infrastructure_blocked")
                and not feedback.get("measurement_error"), "infrastructure-blocked or unfinished feedback: " + cid)
        source_identity(task, state, baseline, cid)
        parent = task / "candidates" / cid
        rows = {sid: row for sid, row in state["stages"].items()
                if row["candidate_id"] == cid and not
                (row["kind"] == "timing" and row["plan"].get("purpose") == "final")}
        observed = {}
        for oid in item["observation_ids"]:
            for sid, count in state["observations"][oid]["stage_attempts"].items():
                observed[sid] = max(observed.get(sid, 0), count)
        require(rows and all(observed.get(sid) == len(row["attempts"]) for sid, row in rows.items()),
                "feedback omits an executed source stage")
        results, refs = {}, {}
        for sid, row in rows.items():
            result, ref = recorded_stage(run, operator, cid, sid, row)
            results[sid], refs[sid] = result, ref
        for row in feedback.get("stages", []):
            sid = row["stage_id"]
            require(sid in results and row["result"] == refs[sid]
                    and all(row.get(k) == results[sid].get(k) for k in ("kind", "status", "error")),
                    "feedback stage outcome or evidence differs")
        latest = {}
        for sid, row in rows.items():
            kind = row["kind"]
            if kind not in latest or row["attempts"][-1]["start_order"] > rows[latest[kind]]["attempts"][-1]["start_order"]:
                latest[kind] = sid
        failures = [results[sid] for sid in latest.values() if results[sid]["status"] != "passed"]
        for failure in failures:
            require(failure["kind"] in ("build", "correctness")
                    and (failure.get("error") or {}).get("type") not in INFRA_ERRORS
                    and (failure["kind"] != "correctness" or failure.get("native_started") is True),
                    "stage failure is infrastructure, not a closed source failure")
        guard_ref = feedback.get("semantic_guards")
        guard = None
        if guard_ref is not None:
            require(guard_ref == pointer(parent / "boundary-validation/completion.json"), "boundary evidence changed")
            guard = iteration.boundary_result(task, parent, operator, cid)
            verify_pointer_tree(guard, evidence_path=guard_ref["path"])
            require(not guard.get("error")
                    and (guard.get("verification_error") or {}).get("type") not in INFRA_ERRORS
                    and all((r.get("error") or {}).get("type") not in INFRA_ERRORS for r in guard.get("cases", [])),
                    "boundary infrastructure failure is unfinished")
            require(guard.get("cases"), "boundary coverage is empty")
            if guard["status"] == "passed":
                require(not guard.get("verification_error") and all(
                    r.get("expected_process_passed") is True and r.get("dispatch_log_passed") is True
                    for r in guard["cases"]), "boundary passed status contradicts actual checks")
        qualified = campaign._safe_source(state, cid) and guard is not None and guard["status"] == "passed"
        if qualified:
            runtime_evidence(ledger, operator, cid, parent, rows[latest["runtime"]])
        if feedback["status"] == "measured":
            require(qualified and not failures and "timing" in latest, "measured feedback lacks successful safety or timing")
            comparisons = iteration.comparison_reports(task, parent, operator, item, baseline, required=True)
            require(comparisons == feedback.get("comparisons"), "closed search reports changed")
        else:
            require(not qualified and (failures or (guard is not None and guard["status"] == "failed")),
                    "source failure has no actual failed source/semantic check")
        audited.append({"candidate_id": cid, "source_hash": item["source_hash"], "status": feedback["status"],
                        "qualified": qualified, "feedback": pointer(feedback_path), "stages": refs,
                        "semantic_guards": guard_ref})
    return audited


def validate_final_plan(path, ledger, task, operator, cid, options=None):
    plan = load(path)
    state = ledger.state["tasks"][operator]
    baseline = ledger.config["tasks"][operator]["baseline_source_hash"]
    item = state["candidates"][cid]
    campaign._timing_plan(plan, item, baseline, policy=ledger.config["policy"],
                          repeat_by_case=ledger.config["tasks"][operator].get("repeat_by_case"))
    require(plan["purpose"] == "final" and plan["case_ids"] == campaign.ALL_CASES,
            "final comparisons must cover all twenty cases")
    manifest_path = Path(path).parent / "comparisons.json"
    require(sha(manifest_path) == plan["manifest_ref"], "comparison manifest changed")
    require(load(manifest_path) == {"candidate_id": cid, "cohorts": plan["cohorts"], "case_ids": campaign.ALL_CASES},
            "comparison manifest identity differs")
    controls = {"direct_parent": item["source_parent"]["candidate_id"] or "baseline"}
    if item["source_parent"]["source_hash"] != baseline:
        controls["original_baseline"] = "baseline"
    require(len(plan["cohorts"]) == len(controls)
            and {c["relation"] for c in plan["cohorts"]} == set(controls), "final comparison relations differ")
    candidate_hash = source_identity(task, state, baseline, cid)
    checked(plan["calibration_report"], "final calibration")
    for cohort in plan["cohorts"]:
        control = controls[cohort["relation"]]
        require(cohort["control_candidate_id"] == control, "final control differs from source parent")
        frozen = checked(cohort["plan"], "final cohort")
        require(frozen["case_ids"] == campaign.ALL_CASES and frozen["comparison_kind"] == "ab", "final cohort coverage differs")
        if options is not None:
            require(frozen["calibration_scope"].get("epoch") == options["epoch"], "final timing epoch differs")
            for entry in frozen["schedule"]:
                require(entry["request"].get("capture_storage") == options.get("capture_storage"),
                        "final capture storage differs")
        preflight_cohort(frozen)
        build = checked(frozen["identity_bindings"]["role_build"], "final role build")
        hashes = {"A": source_identity(task, state, baseline, control), "B": candidate_hash}
        require(build["operator"] == operator and all(build["roles"][r]["source_sha256"] == hashes[r] for r in "AB"),
                "final role source differs from parent or candidate")
        if "calibration_report" in cohort:
            checked(cohort["calibration_report"], "relation calibration")
    return plan


def final_reports(parent, plan):
    """Replay all six actual observations, including their byte-bound outputs."""
    results = []
    for cohort in plan["cohorts"]:
        directory = parent / "stages" / GROUP / cohort["relation"]
        frozen = checked(cohort["plan"], "final cohort")
        require(load(directory / "plan.json") == frozen, "executed final cohort plan differs")
        completion = load(directory / "group-completion.json")
        directories = [str(directory / row["name"]) for row in frozen["schedule"]]
        require(completion.get("status") == "passed" and completion.get("error") is None
                and completion.get("completed_sessions") == directories, "final cohort is incomplete")
        calibration = checked(cohort.get("calibration_report", plan["calibration_report"]), "final calibration")
        actual = report.analyze_task_cohort(directories, frozen, calibration)
        require(load(directory / "report.json") == actual, "final report differs from actual observations")
        require(actual["case_ids"] == [str(c) for c in campaign.ALL_CASES]
                and actual["evidence_status"] == "verified_complete", "final report lacks full coverage")
        results.append({"relation": cohort["relation"], "control_candidate_id": cohort["control_candidate_id"],
                        "report": pointer(directory / "report.json"),
                        "completion": pointer(directory / "group-completion.json")})
    return results


def finalize(run, operator, *, prepare_only=False, timing_options=None):
    """Return an honest unfinished status without retrying or replacing evidence."""
    try:
        return _finalize(run, operator, prepare_only=prepare_only, timing_options=timing_options)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        return {"operator": operator, "status": "unfinished", "error": {"type": type(exc).__name__, "message": str(exc)},
                "formal_admission": "not_evaluated", "graph_policy_eligible": False, "episode_ref": None,
                "selected_candidate_id": None}


def timing_settings(task, supplied, request_path, *, needs_calibration):
    """A resumed invocation inherits frozen settings unless explicitly supplied."""
    if supplied is None and request_path.exists():
        settings = load(request_path)["timing_options"]
        verify_pointer_tree(settings, evidence_path=request_path)
        return settings
    supplied = supplied or {}
    require(isinstance(supplied, dict) and not set(supplied) - {
        "capture_storage", "epoch", "calibration_path", "calibration_by_relation"}, "unknown final timing option")
    epoch = supplied.get("epoch", "epoch-01")
    require(isinstance(epoch, str) and bool(epoch.strip()), "timing epoch is required")
    overrides = supplied.get("calibration_by_relation", {})
    require(isinstance(overrides, dict) and set(overrides) <= {"direct_parent", "original_baseline"},
            "unknown calibration relation")
    calibration = supplied.get("calibration_path", task / "stages/aa-initial/cohort/report.json")
    settings = {"epoch": epoch,
                "calibration_report": pointer(calibration) if needs_calibration or "calibration_path" in supplied else None,
                "calibration_by_relation": {relation: pointer(path) for relation, path in overrides.items()}}
    if "capture_storage" in supplied:
        settings["capture_storage"] = supplied["capture_storage"]
    return settings


def _finalize(run, operator, *, prepare_only, timing_options):
    require(operator in OPERATORS, "not a Level2 operator")
    run, split, task, _, _ = task_paths(run, operator, "baseline")
    ledger = campaign.Campaign(run / split / "ledger")
    require(ledger.state["status"] == "active" and not campaign._active(ledger.state),
            "campaign is paused or has an active stage")
    require(not ledger.unsealed_checkpoints, "checkpoint seal is incomplete")
    audit = audit_attempts(run, operator, ledger, task)
    qualified = [row["candidate_id"] for row in audit if row["qualified"]]
    state = ledger.state["tasks"][operator]
    directory = task / "finalization"
    request_path = directory / "request.json"
    options = timing_settings(task, timing_options, request_path, needs_calibration=bool(qualified))
    plans, refs = {}, {}
    if not state["frozen"]:
        require(len(qualified) <= campaign.BUDGETS["timing_groups"] - state["used"]["timing_groups"],
                "insufficient existing final evaluation budget")
    for cid in qualified:
        parent = task / "candidates" / cid
        path = parent / "plans" / GROUP / "stage-plan.json"
        if not path.exists():
            require(not request_path.exists() and not state["frozen"], "frozen final plan is missing")
            require(not path.parent.exists(), "partial final planning requires explicit evidence recovery")
            checked(options["calibration_report"], "final calibration")
            calibration = options["calibration_report"]["path"]
            # Existing relation-specific calibration is retained; no new control
            # executions or undocumented changes of measurement policy occur.
            search = load(parent / "plans/search/stage-plan.json")
            overrides = {c["relation"]: c["calibration_report"]["path"] for c in search["cohorts"] if "calibration_report" in c}
            for c in search["cohorts"]:
                if "calibration_report" in c:
                    checked(c["calibration_report"], "search relation calibration")
            for relation, ref in options["calibration_by_relation"].items():
                checked(ref, "explicit relation calibration")
                overrides[relation] = ref["path"]
            path = stage_module.prepare_timing(run, operator, cid, GROUP, purpose="final",
                        calibration_path=calibration, calibration_by_relation=overrides, epoch=options["epoch"],
                        **({"capture_storage": options["capture_storage"]} if "capture_storage" in options else {}))
        plans[cid] = validate_final_plan(path, ledger, task, operator, cid, options)
        require(plans[cid].get("calibration_report") == options["calibration_report"], "final calibration differs from requested setting")
        for cohort in plans[cid]["cohorts"]:
            if cohort["relation"] in options["calibration_by_relation"]:
                require(cohort.get("calibration_report") == options["calibration_by_relation"][cohort["relation"]],
                        "final relation calibration differs from requested setting")
        refs[cid] = pointer(path)
    request = {"version": VERSION, "operator": operator, "campaign_config_hash": ledger.config_hash,
               "producers": producers(), "source_attempts": audit, "evaluation_candidate_ids": qualified,
               "timing_options": options,
               "final_plans": refs, "case_ids": campaign.ALL_CASES,
               "selection_policy": "all_correctness_runtime_boundary_qualified_candidates_without_timing_filter",
               "selected_candidate_id": None, "formal_admission": "not_evaluated",
               "graph_policy_eligible": False, "episode_ref": None}
    if request_path.exists():
        require(load(request_path) == request, "frozen finalization request or evidence changed")
    else:
        require(not state["frozen"], "frozen ledger has no finalization request")
        save(request_path, request)
    reason = "All safe candidates; no winner selected; finalization request " + sha(request_path)
    if state["frozen"]:
        require(state["selection"] == qualified and state["final_plans"] == plans
                and state["freeze_reason"] == reason, "ledger final freeze differs from request")
    else:
        ledger.freeze(event_id=operator + "-finalize-freeze", workload=operator,
                      candidate_ids=qualified, final_plans=plans, reason=reason)
    base = {"version": VERSION, "operator": operator, "request": pointer(request_path),
            "evaluation_candidate_ids": qualified, "source_attempt_count": 3, "selected_candidate_id": None,
            "formal_admission": "not_evaluated", "graph_policy_eligible": False, "episode_ref": None}
    if prepare_only:
        return {**base, "status": "prepared", "final_measurements_complete": False}
    results = []
    for cid in qualified:
        parent = task / "candidates" / cid
        result = iteration.stage(run, operator, cid, "timing", GROUP, plan_path=refs[cid]["path"])
        require(result["status"] == "passed", "final stage failed; retained without retry: " + cid)
        results.append({"candidate_id": cid, "result": pointer(parent / "stages" / GROUP / "result.json"),
                        "comparisons": final_reports(parent, plans[cid])})
    completion = {**base, "status": "final_evaluations_completed" if qualified else "closed_no_qualified_candidates",
                  "final_measurements_complete": True, "comparisons": results,
                  "claim": "Evaluation closure only; no optimized winner or formal admission is asserted."}
    completion_path = directory / "completion.json"
    if completion_path.exists():
        require(load(completion_path) == completion, "final completion differs from actual results")
    else:
        save(completion_path, completion)
    return completion


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--operator", choices=OPERATORS, action="append", required=True)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--capture-storage", choices=("direct", "local"))
    parser.add_argument("--epoch")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--calibration-by-relation", action="append", default=[], metavar="RELATION=PATH")
    args = parser.parse_args(argv)
    timing_options = {}
    if args.capture_storage:
        try:
            import msprof_raw_storage
        except ImportError:
            parser.error("capture storage producer is not installed in this engineering snapshot")
        timing_options["capture_storage"] = dict(msprof_raw_storage.LOCAL if args.capture_storage == "local" else msprof_raw_storage.DIRECT)
    if args.epoch is not None:
        timing_options["epoch"] = args.epoch
    if args.calibration is not None:
        timing_options["calibration_path"] = args.calibration
    for entry in args.calibration_by_relation:
        relation, separator, path = entry.partition("=")
        if not separator or relation not in ("direct_parent", "original_baseline") or not path:
            parser.error("calibration relation must be direct_parent=PATH or original_baseline=PATH")
        refs = timing_options.setdefault("calibration_by_relation", {})
        if relation in refs:
            parser.error("duplicate calibration relation")
        refs[relation] = Path(path)
    for operator in args.operator:
        result = finalize(args.run, operator, prepare_only=args.prepare_only, timing_options=timing_options or None)
        print(json.dumps(result), flush=True)
        if result["status"] == "unfinished":
            return 1
        if result["status"] == "closed_no_qualified_candidates":
            return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
