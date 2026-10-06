#!/usr/bin/env python3
"""Execute one authored Level2 source attempt, retaining every real outcome.

This coordinator never authors a next intervention or chooses its parent. A
closed observation is the only input from which the author may propose another
source. Existing successful stages are reusable; failed stages are never
silently rerun or rewritten.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import re

from level2_campaign import task_path, OPERATORS
from msprof_exploration_campaign import Campaign
from msprof_exploration_execute import ALL_CASES, event, load, pointer, save, sha, task_paths
from msprof_exploration_report import digest
from run_msprof_exploration_stage import (register_proposal, run_stage, prepare_timing,
                                         verify_source_snapshot, successful_correctness_binding,
                                         measurement_options, validate_stage_options)


def timing_options(value):
    return measurement_options(value)


def check_control_settings(plan, settings):
    settings = timing_options(settings)
    scope = plan["calibration_scope"]
    if scope.get("epoch") != settings.get("epoch", "epoch-01"):
        raise ValueError("requested epoch differs from frozen control/measurement")
    if (scope.get("capture_storage") != settings.get("capture_storage") or not plan["schedule"]
            or any(row["request"].get("capture_storage") != settings.get("capture_storage")
                   for row in plan["schedule"])):
        raise ValueError("requested capture storage differs from frozen control/measurement")
    if len(plan["schedule"]) != 6:
        raise ValueError("frozen control schedule must have six processes")
    if settings.get("capture_storage") is not None:
        from msprof_raw_storage import LOCAL, policy
        for row in plan["schedule"]:
            request = row["request"]
            policy(request)
            if settings["capture_storage"] == LOCAL and scope.get("capture_storage_producer_hash") != request["capture_storage_producer"]["sha256"]:
                raise ValueError("frozen control transport producer differs")


def check_timing_settings(plan, settings):
    settings = timing_options(settings)
    expected = pointer(settings["calibration_path"]) if settings.get("calibration_path") is not None else None
    if plan.get("calibration_report") != expected:
        raise ValueError("requested calibration differs from frozen timing plan")
    overrides = settings.get("calibration_by_relation") or {}
    if set(overrides) - {row["relation"] for row in plan["cohorts"]}:
        raise ValueError("calibration override names an absent comparison relation")
    for row in plan["cohorts"]:
        frozen = checked_pointer(row["plan"], "cohort plan")
        check_control_settings(frozen, settings)
        selected = pointer(overrides[row["relation"]]) if row["relation"] in overrides else None
        if row.get("calibration_report") != selected:
            raise ValueError("requested relation calibration differs from frozen timing plan")


def reclaim_outputs(run, task, parent, group):
    # The synchronous stage returned and has reaped all writers before this call.
    from level2_storage import deduplicate, compact_journals
    result = deduplicate(run, parent / "stages" / group, kind="stage", writers_closed=True, apply=True)
    if result.get("status") == "verified_archived":
        return result  # Existing sealed bytes already replace the closed output paths.
    event(task, "closed_outputs_deduplicated", {"manifest": pointer(result["manifest_path"]),
          "reclaimed_bytes": result["reclaimed_bytes"], "evidence_bytes_deleted": 0})
    # Bind the original manifest publicly before retiring its loose journal entries.
    # Synchronous failure propagates; no next collector may start during maintenance.
    compact_journals(run, Path(result["transaction"]), writers_closed=True, apply=True)


def checked_pointer(ref, label):
    if not isinstance(ref, dict) or set(ref) != {"path", "sha256"} or sha(ref["path"]) != ref["sha256"]:
        raise ValueError(label + " changed")
    return load(ref["path"])


def feedback_pointer(task, candidate_id, observation):
    """Find immutable feedback by ledger hash, including explicit later observations."""
    task = Path(task)
    expected = observation.get("report_ref")
    if not isinstance(expected, str) or re.fullmatch(r"sha256:[0-9a-f]{64}", expected) is None:
        raise ValueError("feedback observation has no content identity")
    directory = task / "feedback"
    if directory.is_symlink():
        raise ValueError("feedback directory cannot be a symlink")
    for path in sorted(directory.glob("*.json")):
        if path.is_symlink():
            raise ValueError("feedback evidence cannot be a symlink")
        if path.is_file() and sha(path) == expected:
            value = load(path)
            if (value != observation.get("feedback") or value.get("candidate_id") != candidate_id
                    or value.get("operator") != task.name):
                raise ValueError("feedback observation identity differs")
            return pointer(path)
    raise ValueError("feedback file matching immutable observation is absent")


def stage(run, operator, candidate, kind, group, **kwargs):
    if set(kwargs) - {"cases", "plan_path", "capture_storage", "epoch"}:
        raise ValueError("unknown stage option")
    validate_stage_options(kind, kwargs.get("plan_path"),
        capture_storage=kwargs.get("capture_storage"), epoch=kwargs.get("epoch", "epoch-01"))
    run, split, task, parent, source = task_paths(run, operator, candidate)
    result = parent / "stages" / group / "result.json"
    if result.exists():
        value = load(result)
        cid = None if candidate == "baseline" else candidate
        stage_id = candidate + "-" + group
        if value["kind"] != kind or value["candidate_id"] != cid or value["stage_id"] != stage_id:
            raise ValueError("existing stage identity differs")
        ledger = Campaign(run / split / "ledger")
        state = ledger.state["tasks"][operator]
        recorded = state["stages"].get(stage_id)
        plan = load(result.parent / "stage-plan.json")
        if (recorded is None or recorded["kind"] != kind or recorded["candidate_id"] != cid
                or recorded["plan"] != plan or not recorded["attempts"]):
            raise ValueError("existing stage ledger identity or frozen plan differs")
        if recorded.get("prestart_recovery") is not None:
            from level2_stage_recovery import resolve_result
            resolved = resolve_result(result.parent, recorded)
            result = Path(resolved["current_result"]["path"])
            value = load(result)
        attempt = recorded["attempts"][-1]
        if attempt["outcome"] is None:
            raise ValueError("incomplete stage ledger finish requires explicit evidence recovery")
        if attempt.get("evidence", {}).get("result") != pointer(result):
            raise ValueError("existing stage result differs from ledger evidence")
        if value["status"] not in ("passed", "failed") or (value["status"] == "passed") != (attempt["outcome"] == "success"):
            raise ValueError("existing stage status differs from ledger outcome")
        archive = task / "baseline-source.tar" if cid is None else parent / "source.tar"
        expected_source = (ledger.config["tasks"][operator]["baseline_source_hash"] if cid is None
                           else state["candidates"][cid]["source_hash"])
        if sha(archive) != expected_source:
            raise ValueError("existing stage source archive differs from ledger")
        verify_source_snapshot(archive, source)
        if kind == "runtime":
            current_binding = successful_correctness_binding(ledger, operator, cid, parent, expected_source)
            if any(plan.get(key) != value for key, value in current_binding.items()):
                raise ValueError("runtime correctness binding differs; explicit recovery group is required")
        explicit_plan = kwargs.get("plan_path")
        if explicit_plan is not None:
            if load(explicit_plan) != plan:
                raise ValueError("requested stage plan differs from frozen plan")
        elif kind != "timing" and plan.get("case_ids") != list(ALL_CASES if kwargs.get("cases") is None else kwargs["cases"]):
            raise ValueError("requested stage cases differ from frozen plan")
        if kind == "control" and explicit_plan is None:
            check_control_settings(plan["cohort"], {key: kwargs[key] for key in ("epoch", "capture_storage") if key in kwargs})
        return value
    if result.parent.exists():
        raise ValueError("incomplete stage requires explicit evidence recovery: " + str(result.parent))
    return run_stage(run, operator, candidate, kind, group, **kwargs)


def comparison_reports(task, parent, operator, item, baseline_hash, *, required):
    """Replay source and public-case bindings before exposing timing feedback."""
    source_parent = item["source_parent"]
    controls = {"direct_parent": source_parent["candidate_id"] or "baseline"}
    if source_parent["source_hash"] != baseline_hash:
        controls["original_baseline"] = "baseline"
    plan = load(parent / "stages/search/stage-plan.json")
    expected_cases = [1, 8, 14, 20] + [row["case_id"] for row in item["probes"]]
    if plan.get("purpose") != "search" or plan.get("case_ids") != expected_cases:
        raise ValueError("search feedback cases differ from declared sentinels and probes")
    from msprof_exploration_campaign import comparisons
    if plan.get("comparisons") != comparisons(item, baseline_hash):
        raise ValueError("search plan source parent or candidate identity differs")
    cohorts = {row["relation"]: row for row in plan["cohorts"]}
    if len(cohorts) != len(plan["cohorts"]) or set(cohorts) != set(controls):
        raise ValueError("search comparison relations differ from source lineage")
    from shared_context_build import source_hash
    if sha(parent / "source.tar") != item["source_hash"]:
        raise ValueError("search candidate source archive differs from ledger")
    verify_source_snapshot(parent / "source.tar", parent / "op")
    implementation = source_hash(parent / "op")
    reports = []
    for relation, control_id in controls.items():
        cohort = cohorts[relation]
        if cohort.get("control_candidate_id") != control_id:
            raise ValueError("search control candidate differs from selected parent")
        frozen = checked_pointer(cohort["plan"], "cohort plan")
        control = task if control_id == "baseline" else task / "candidates" / control_id
        archive = control / ("baseline-source.tar" if control_id == "baseline" else "source.tar")
        expected_control = baseline_hash if control_id == "baseline" else source_parent["source_hash"]
        if sha(archive) != expected_control:
            raise ValueError("search control source archive differs from lineage")
        control_source = control / ("baseline" if control_id == "baseline" else "op")
        verify_source_snapshot(archive, control_source)
        source_hashes = {"A": source_hash(control_source), "B": implementation}
        if frozen.get("case_ids") != expected_cases:
            raise ValueError("cohort cases differ from public search scope")
        build = checked_pointer(frozen["identity_bindings"]["role_build"], "comparison role build")
        if build.get("operator") != operator or any(build["roles"][role]["source_sha256"] != source_hashes[role] for role in "AB"):
            raise ValueError("comparison role source differs from selected parent or candidate")
        report_path = parent / "stages/search" / relation / "report.json"
        if not report_path.exists():
            if required:
                raise ValueError("successful timing is missing required " + relation + " report")
            continue
        report = load(report_path)
        completion = load(report_path.parent / "group-completion.json")
        if (completion.get("status") != "passed" or report.get("evidence_status") != "verified_complete"
                or report.get("operator") != operator or report.get("comparison_kind") != "ab"
                or report.get("plan_hash") != digest(frozen) or report.get("source_hashes") != source_hashes):
            raise ValueError("timing report source, plan or completion identity differs")
        expected_cells = {(str(case), config) for case in expected_cases for config in ("normal", "swapped")}
        cells = [(str(row["case_id"]), row["buffer_config"]) for row in report["results"]]
        if ([str(c) for c in report.get("case_ids", [])] != [str(c) for c in expected_cases]
                or len(cells) != len(expected_cells) or set(cells) != expected_cells
                or set(report["suite"]) != {"normal", "swapped"}
                or any({str(c) for c in suite["case_ids"]} != {str(c) for c in expected_cases} for suite in report["suite"].values())):
            raise ValueError("timing report case coverage differs from declared public scope")
        reports.append({"relation": relation, "control_candidate_id": control_id,
            "source_hashes": source_hashes, "report": pointer(report_path),
            "case_ids": report["case_ids"], "suite": report["suite"],
            "results": [{k: row[k] for k in ("case_id", "buffer_config", "speedup", "ci95", "latency_change",
                "cv_status", "calibration_status", "coarse_observed_controls", "measurement_quality", "limitations")}
                for row in report["results"]], "limitations": report["limitations"]})
    return reports


def boundary_result(task, parent, operator, candidate_id):
    """Reuse only the exact completed guard execution, including failed guards."""
    path = parent / "boundary-validation/completion.json"
    value = load(path)
    if value.get("operator") != operator or value.get("candidate") != candidate_id or value.get("status") not in ("passed", "failed"):
        raise ValueError("existing boundary identity differs")
    request = checked_pointer(value.get("request"), "boundary request")
    if request.get("operator") != operator or request.get("candidate") != candidate_id:
        raise ValueError("existing boundary request identity differs")
    from level2_guard_contract import resolve, REQUEST_VERSION
    revision = resolve(task, parent, oracle=False)
    expected_script = revision["script"] if revision else pointer(task / "agent/boundary_guard.py")
    if request.get("script") != expected_script:
        raise ValueError("existing boundary guard source differs")
    if revision:
        from msprof_exploration_provenance import verify_pointer_tree
        from level2_guard_contract import checked_execution
        checked_execution(value.get("evidence_closure"), path.parent)
        producer = request.get("producer")
        if not isinstance(producer, dict) or producer.get("path") != str(Path(__file__).with_name("level2_guard_contract.py")):
            raise ValueError("candidate guard helper producer differs")
        verify_pointer_tree(request, evidence_path=path.parent / "request.json")
        if (value.get("version") != REQUEST_VERSION or request.get("version") != REQUEST_VERSION
                or request.get("semantic_guard_contract") != pointer(parent / "semantic-guards/contract.json")
                or [row["name"] for row in value.get("cases", [])] != [row["name"] for row in revision["cases"]]):
            raise ValueError("existing candidate guard revision/coverage differs")
    elif request.get("semantic_guard_contract") is not None or request.get("version") == REQUEST_VERSION:
        raise ValueError("undeclared candidate guard revision")
    if request.get("dispatch_plan") != pointer(parent / "dispatch_plan.json"):
        raise ValueError("existing boundary dispatch plan differs")
    binary = load(parent / "build/build_manifest.json")["standalone"]
    if request.get("binary") != binary or sha(binary["path"]) != binary["sha256"]:
        raise ValueError("existing boundary binary differs")
    return value


def baseline(run, operator, *, correctness_group="correctness", control_group="aa-initial", measurement=None, deduplicate_outputs=False):
    """Revalidate every original output and native lifecycle, then calibrate A/A.

    The full calibration stays coordinator-only. Search feedback still exposes
    only the candidate's four sentinels and its predeclared probes.
    """
    if re.fullmatch(r"correctness(?:-[A-Za-z0-9][A-Za-z0-9_-]*)?", correctness_group) is None:
        raise ValueError("correctness group must be correctness or a named correctness-* recovery group")
    if re.fullmatch(r"aa-[A-Za-z0-9][A-Za-z0-9_-]*", control_group) is None:
        raise ValueError("control group must be a named aa-* group")
    settings = timing_options(measurement)
    if set(settings) - {"epoch", "capture_storage"}:
        raise ValueError("baseline control cannot consume another calibration")
    for kind in ("correctness", "runtime", "control"):
        group = correctness_group if kind == "correctness" else control_group if kind == "control" else kind
        result = stage(run, operator, "baseline", kind, group, cases=ALL_CASES,
                       **(settings if kind == "control" else {}))
        if result["status"] != "passed":
            return {"operator": operator, "status": "blocked", "stage": result}
        if kind == "control" and deduplicate_outputs:
            _, _, task, parent, _ = task_paths(run, operator, "baseline")
            reclaim_outputs(run, task, parent, group)
    return {"operator": operator, "status": "baseline_validated_and_calibrated"}


def candidate(run, operator, candidate_id, *, boundaries=True, measurement=None, deduplicate_outputs=False):
    settings = timing_options(measurement)
    run, split, task, parent, _ = task_paths(run, operator, candidate_id)
    ledger = Campaign(run / split / "ledger")
    state = ledger.state["tasks"][operator]
    if candidate_id not in state["candidates"]:
        register_proposal(run, operator, candidate_id, parent / "proposal.json")
    ledger = Campaign(run / split / "ledger")
    item = ledger.state["tasks"][operator]["candidates"][candidate_id]
    plan_path = parent / "plans/search/stage-plan.json"
    if plan_path.exists() and (not item["feedback_closed"] or measurement is not None):
        check_timing_settings(load(plan_path), settings)
    if item["feedback_closed"] or item["observation_ids"]:
        observation = ledger.state["tasks"][operator]["observations"][item["observation_ids"][-1]]
        feedback_path = Path(feedback_pointer(task, candidate_id, observation)["path"])
        feedback = load(feedback_path)
        if (sha(feedback_path) != observation["report_ref"] or feedback != observation["feedback"]
                or feedback.get("source_hash") != item["source_hash"]
                or feedback.get("source_parent") != item["source_parent"]):
            raise ValueError("closed feedback differs from immutable ledger evidence")
        if not item["feedback_closed"] and (feedback.get("status") != "infrastructure_blocked"
                or observation.get("close_feedback") is not False):
            raise ValueError("open feedback is not a recorded infrastructure block")
        if feedback.get("failure_classification") is not None:
            from msprof_exploration_provenance import verify_pointer_tree
            verify_pointer_tree(feedback["failure_classification"], evidence_path=feedback_path)
        return {"operator": operator, "candidate_id": candidate_id, "status": feedback["status"],
                "feedback_already_closed": item["feedback_closed"], "feedback_already_recorded": True,
                "observation_ids": item["observation_ids"],
                "feedback": pointer(feedback_path)}

    results = []
    guard = None
    for kind in ("build", "correctness", "runtime"):
        result = stage(run, operator, candidate_id, kind, kind)
        results.append(result)
        if result["status"] != "passed":
            break
    if all(r["status"] == "passed" for r in results) and boundaries:
        from level2_boundaries import collect
        guard_path = parent / "boundary-validation/completion.json"
        if guard_path.exists():
            guard = boundary_result(task, parent, operator, candidate_id)
        elif guard_path.parent.exists():
            raise ValueError("incomplete boundary validation needs explicit recovery")
        else:
            guard = collect(run, operator, candidate_id)

    if all(r["status"] == "passed" for r in results) and (guard is None or guard["status"] == "passed"):
        ledger = Campaign(run / split / "ledger")
        task_state = ledger.state["tasks"][operator]
        reserved = list(task_state["reserved_final_candidate_ids"])
        if candidate_id not in reserved:
            reserved.append(candidate_id)
        if not plan_path.exists():
            plan_path = prepare_timing(run, operator, candidate_id, "search", final_candidates=reserved, **settings)
        check_timing_settings(load(plan_path), settings)
        results.append(stage(run, operator, candidate_id, "timing", "search", plan_path=plan_path))
        if results[-1]["status"] == "passed" and deduplicate_outputs:
            reclaim_outputs(run, task, parent, "search")

    ledger = Campaign(run / split / "ledger")
    state = ledger.state["tasks"][operator]
    stages = [sid for sid, row in state["stages"].items() if row["candidate_id"] == candidate_id]
    if not stages or any(state["stages"][sid]["attempts"][-1]["outcome"] is None for sid in stages):
        raise ValueError("cannot close feedback without completed real stages")
    reports, measurement_error = [], None
    timing_result = next((r for r in results if r["kind"] == "timing"), None)
    if timing_result is not None:
        try:
            reports = comparison_reports(task, parent, operator, item,
                ledger.config["tasks"][operator]["baseline_source_hash"], required=timing_result["status"] == "passed")
        except (ValueError, KeyError, OSError, TypeError) as exc:
            measurement_error = {"type": type(exc).__name__, "message": str(exc)}
    complete = (all(r["status"] == "passed" for r in results)
                and (guard is None or guard["status"] == "passed") and bool(reports) and measurement_error is None)
    failed = next((r for r in results if r["status"] != "passed"), None)
    classification = None
    if not complete:
        from level2_failure_classification import classify_failure
        classification = classify_failure(task, parent, stage=failed, guard=guard)
    infrastructure_block = bool(not complete and (measurement_error
        or classification["status"] == "infrastructure_blocked"))
    feedback = {"version": "level2_source_feedback_v1", "operator": operator, "candidate_id": candidate_id,
        "source_hash": item["source_hash"], "source_parent": item["source_parent"],
        "optimization_stage": load(parent / "proposal.json")["optimization_stage"],
        "status": "measured" if complete else "infrastructure_blocked" if infrastructure_block else "source_attempt_failed",
        "stages": [{"stage_id": r["stage_id"], "kind": r["kind"], "status": r["status"], "error": r["error"],
                    "result": pointer(parent / "stages" / r["stage_id"].removeprefix(candidate_id + "-") / "result.json")}
                   for r in results],
        "semantic_guards": pointer(parent / "boundary-validation/completion.json") if guard is not None else None,
        "comparisons": reports, "measurement_error": measurement_error,
        "failure_classification": classification,
        "formal_admission": "not_evaluated", "graph_policy_eligible": False,
        "episode_ref": None, "next_source_authored": False,
        "next_action": ("Resolve the recorded infrastructure failure through explicit evidence recovery; source feedback remains open."
                        if infrastructure_block else "Analyze this closed feedback before selecting any parent and next intervention.")}
    feedback_path = task / "feedback" / (candidate_id + ".json")
    if feedback_path.exists():
        if load(feedback_path) != feedback:
            raise ValueError("existing feedback differs")
    else:
        save(feedback_path, feedback)
    observation_id = candidate_id + "-feedback-01"
    ledger.observe(event_id=observation_id, workload=operator, candidate_id=candidate_id,
        observation_id=observation_id, stage_ids=stages, feedback=feedback,
        close_feedback=not infrastructure_block, report_ref=pointer(feedback_path)["sha256"],
        quality={"formal_admission": "not_evaluated", "infrastructure_blocked": infrastructure_block,
                 "complete_measurement": complete})
    event(task, "candidate_feedback_blocked" if infrastructure_block else "candidate_feedback_closed",
          {"observation_id": observation_id, "feedback": pointer(feedback_path)})
    return {"operator": operator, "candidate_id": candidate_id, "status": feedback["status"],
            "observation_id": observation_id, "feedback": pointer(feedback_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("baseline", "candidate"))
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--operator", action="append", required=True, choices=OPERATORS)
    parser.add_argument("--candidate")
    parser.add_argument("--correctness-group", default="correctness",
                        help="Explicit baseline correctness group; a new recovery name preserves all prior attempts")
    parser.add_argument("--capture-storage", choices=("direct", "local"))
    parser.add_argument("--epoch", default="epoch-01")
    parser.add_argument("--calibration-group", default="aa-initial")
    parser.add_argument("--deduplicate-outputs", action="store_true",
                        help="Synchronously deduplicate exact output bytes after closed control/timing stages")
    args = parser.parse_args()
    settings = {"epoch": args.epoch} if args.epoch != "epoch-01" else {}
    if args.capture_storage is not None:
        from msprof_raw_storage import DIRECT, LOCAL
        settings["capture_storage"] = LOCAL if args.capture_storage == "local" else DIRECT
    try:
        settings = timing_options(settings)
    except ValueError as exc:
        parser.error(str(exc))
    if re.fullmatch(r"aa-[A-Za-z0-9][A-Za-z0-9_-]*", args.calibration_group) is None:
        parser.error("calibration group must be a named aa-* group")
    if args.command == "candidate" and (len(args.operator) != 1 or not args.candidate):
        parser.error("one explicitly authored candidate is required")
    if args.command == "candidate" and args.correctness_group != "correctness":
        parser.error("--correctness-group currently supports baseline recovery only")
    for operator in args.operator:
        if args.command == "baseline":
            result = baseline(args.run, operator, correctness_group=args.correctness_group,
                control_group=args.calibration_group, measurement=settings, deduplicate_outputs=args.deduplicate_outputs)
        else:
            task = task_path(args.run, operator)
            selected = dict(settings)
            if settings or args.calibration_group != "aa-initial":
                selected["calibration_path"] = task / "stages" / args.calibration_group / "cohort/report.json"
            result = candidate(args.run, operator, args.candidate, measurement=selected,
                               deduplicate_outputs=args.deduplicate_outputs)
        print(json.dumps(result), flush=True)
        if result["status"] in ("blocked", "infrastructure_blocked", "source_attempt_failed"):
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
