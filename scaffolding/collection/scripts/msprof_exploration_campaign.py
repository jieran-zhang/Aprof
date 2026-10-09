#!/usr/bin/env python3
"""CPU-only, protocol-specific campaign ledger for msprof task-time exploration.

This module never executes commands or imports runtime gates. A committed start
reserves/charges work before an external controller launches it. The old shared
context ledger is only read when importing a sealed predecessor checkpoint.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re

from shared_context_campaign import (
    ALL_CASES, BUDGETS, SENTINELS, ZERO_HASH, _read_json, _sync_directory,
    _write_exclusive, canonical, digest, identity, nonempty, probes_list, require,
)

SCHEMA = "msprof_exploration_campaign_v1"
CHECKPOINT_SCHEMA = "msprof_exploration_checkpoint_v1"
PROTOCOL = "msprof_task_time_exploration_v1"
PRODUCER_PROTOCOL = "msprof_kernel_time_study_v1"
METRIC = "operator_task_sum_us"
PROFILER_MODE = "task_time_l1_ai_core_off"
TRAIN_WORKLOADS = ("exp", "masked_scale", "foreach_addcdiv_scalar", "mish", "sigmoid")
WORKLOADS = (*TRAIN_WORKLOADS, "gelu")
KINDS = {"static", "build", "correctness", "runtime", "timing", "profile", "control"}
OUTCOMES = {"success", "failed", "build_failed", "correctness_failed", "runtime_failed",
            "prestart_failure", "interrupted", "incomplete"}
POLICY = {"protocol": PROTOCOL, "producer_protocol": PRODUCER_PROTOCOL, "metric": METRIC,
          "profiler_mode": PROFILER_MODE, "processes": 6, "configurations": ["normal", "swapped"],
          "warmup": 10, "repeat": 10, "pairs_per_case": 30, "max_new_rounds": 3,
          "aa_ratio_bounds": [1 / 1.02, 1.02], "max_cv": 0.05}
FRESH_SCHEMA = "msprof_exploration_campaign_v2"
FRESH_PROTOCOL = "msprof_task_time_exploration_v2"
FRESH_POLICY = {**POLICY, "protocol": FRESH_PROTOCOL,
                "producer_protocol": "msprof_kernel_time_study_v2", "repeat": "frozen_per_case"}
ARGUMENTS = {
    "register": {"workload", "candidate_id", "source_hash", "patch_hash", "source_parent",
                 "decision_basis", "probes", "artifacts"},
    "start": {"workload", "stage_id", "kind", "candidate_id", "plan"},
    "finish": {"workload", "stage_id", "outcome", "evidence", "native_started",
               "formal_samples", "actual_costs", "reason"},
    "observe": {"workload", "observation_id", "candidate_id", "stage_ids", "feedback",
                "close_feedback", "report_ref", "quality"},
    "freeze": {"workload", "candidate_ids", "final_plans", "reason"},
    "qualify_continuation": {"workload", "stage_id", "source_hash", "plan_hash", "qualification", "reason"},
    "qualify_prestart": {"workload", "stage_id", "source_hash", "plan_hash", "failed_result", "qualification", "reason"},
    "checkpoint": {"checkpoint_id", "reason", "next_action", "resources_released", "artifacts"},
    "resume": {"checkpoint_id", "reason"},
}


def _file_hash(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _split(name):
    return "validation" if name == "gelu" else "train"


def _cases(value):
    require(isinstance(value, list) and value and all(type(c) is int and c in ALL_CASES for c in value), "invalid case IDs")
    require(len(value) == len(set(value)), "duplicate case IDs")
    return value


def _counters(value, *, budgets=False):
    require(isinstance(value, dict) and all(isinstance(k, str) and type(v) is int and v >= 0 for k, v in value.items()),
            "cost counters must be nonnegative integers")
    if budgets:
        require(set(value) == set(BUDGETS) and all(value[k] <= BUDGETS[k] for k in BUDGETS), "invalid inherited budget")
    return value


def _evidence(value):
    require(isinstance(value, dict) and value, "bound evidence is required, including on failure")
    def hashes(v):
        if isinstance(v, dict):
            return any(hashes(item) for item in v.values())
        if isinstance(v, list):
            return any(hashes(item) for item in v)
        if not isinstance(v, str) or not v.startswith("sha256:"):
            return False
        try:
            identity(v)
        except ValueError:
            return False
        return True
    require(hashes(value), "evidence requires at least one content hash")
    canonical(value)


def comparisons(candidate, baseline, *, search_lite=False):
    """One or two independent comparisons; equal parent/original share one."""
    baseline = identity(baseline)
    parent = candidate["source_parent"]["source_hash"]
    return [{"control_source_hash": control, "candidate_source_hash": candidate["source_hash"],
             "roles": ["child_vs_parent", "child_vs_original"] if parent == baseline else
                      ["child_vs_parent"] if control == parent else ["child_vs_original"]}
            for control in dict.fromkeys((parent,) if search_lite else (parent, baseline))]


def timing_plan(candidate, baseline, *, purpose, manifest_ref, final_candidate_ids=None,
                policy=None, repeat_by_case=None, search_lite=False, **schedule):
    policy = POLICY if policy is None else policy
    require(type(search_lite) is bool, "search_lite must be a boolean")
    fresh = policy == FRESH_POLICY
    if search_lite:
        from msprof_search_protocol import LITE_PROTOCOL, LITE_PRODUCER
        require(fresh and purpose == "search", "lite measurement is only for fresh Level2 search")
        policy = {**policy, "protocol": LITE_PROTOCOL, "producer_protocol": LITE_PRODUCER,
                  "processes": 2, "pairs_per_case": 6}
    plan = {"purpose": purpose, "manifest_ref": identity(manifest_ref),
            "case_ids": list(ALL_CASES) if purpose == "final" else list(SENTINELS) + [p["case_id"] for p in candidate["probes"]],
            "comparisons": comparisons(candidate, baseline, search_lite=search_lite),
            **{k: deepcopy(policy[k]) for k in ("protocol", "producer_protocol", "metric", "profiler_mode",
                                               "processes", "configurations", "warmup", "repeat", "pairs_per_case")}}
    if fresh:
        _repeats(repeat_by_case)
        plan["repeat_by_case"] = {str(case): repeat_by_case[str(case)] for case in plan["case_ids"]}
    if purpose == "search":
        plan["final_candidate_ids"] = list(final_candidate_ids if final_candidate_ids is not None else [candidate["candidate_id"]])
    require(not set(schedule).intersection(plan), "schedule cannot override protocol or comparison fields")
    plan.update(deepcopy(schedule))
    return plan


def expected_samples(plan):
    """Role samples; repeat complete calls are not independent samples."""
    return len(plan["case_ids"]) * len(plan["comparisons"]) * plan["processes"] * len(plan["configurations"]) * plan["pairs_per_case"] * 2


def expected_complete_calls(plan):
    from msprof_search_protocol import LITE_PROTOCOL
    if plan.get("protocol") in (FRESH_PROTOCOL, LITE_PROTOCOL):
        return (sum(plan["repeat_by_case"][str(case)] for case in plan["case_ids"])
                * len(plan["comparisons"]) * plan["processes"]
                * len(plan["configurations"]) * plan["pairs_per_case"] * 2)
    return expected_samples(plan) * plan["repeat"]


def _timing_plan(plan, candidate, baseline, *, policy=None, repeat_by_case=None):
    require(isinstance(plan, dict), "frozen timing plan required")
    require(plan.get("purpose") in {"search", "final"}, "timing purpose must be search or final")
    from msprof_search_protocol import LITE_PROTOCOL
    expected = timing_plan(candidate, baseline, purpose=plan["purpose"], manifest_ref=plan.get("manifest_ref"),
                           final_candidate_ids=plan.get("final_candidate_ids"),
                           policy=policy, repeat_by_case=repeat_by_case,
                           search_lite=plan.get("protocol") == LITE_PROTOCOL)
    require(all(plan.get(key) == value for key, value in expected.items()), "timing plan differs from frozen cases, identities or protocol")
    if plan["purpose"] == "final":
        require("final_candidate_ids" not in plan, "final reservation belongs to search plan")
    canonical(plan)
    return deepcopy(plan)


def _initial_state(config):
    tasks = {}
    for name, declared in config["tasks"].items():
        candidates = {c["candidate_id"]: {**deepcopy(c), "inherited": True, "feedback_closed": True,
                                          "observation_ids": [], "current_round_started": False}
                      for c in declared["inherited_candidates"]}
        tasks[name] = {"split": declared["split"], "used": deepcopy(declared["inherited_used"]),
                       "candidates": candidates, "observations": {}, "stages": {}, "new_source_attempts": 0,
                       "new_rounds_started": 0, "search_candidate_ids": [], "stage_starts": dict.fromkeys(sorted(KINDS), 0),
                       "actual_costs": {}, "fixed_costs": {}, "frozen": False,
                       "reserved_final_candidate_ids": [], "selection": [], "final_plans": {}, "frozen_roster": None}
    return {"schema_version": config["schema_version"], "campaign_id": config["campaign_id"], "status": "active",
            "formal_admission": "not_evaluated", "graph_policy_eligible": False, "episode_ref": None,
            "tasks": tasks, "latest_checkpoint_id": None}


def _repeats(value):
    require(isinstance(value, dict) and set(value) == {str(c) for c in ALL_CASES},
            "repeat_by_case must cover exactly twenty cases")
    require(all(type(v) is int and v in (1, 10) for v in value.values()),
            "case repeat must be the predeclared 1 or 10")


def _validate_config(config):
    require(isinstance(config, dict) and set(config) == {"schema_version", "campaign_id", "policy", "budgets", "tasks", "predecessor", "provenance"},
            "unknown/missing config fields")
    fresh = config["schema_version"] == FRESH_SCHEMA
    policy = FRESH_POLICY if fresh else POLICY
    require(config["schema_version"] in (SCHEMA, FRESH_SCHEMA) and config["policy"] == policy and config["budgets"] == BUDGETS,
            "immutable campaign protocol or budgets changed")
    nonempty(config["campaign_id"], "campaign_id")
    require(isinstance(config["tasks"], dict) and config["tasks"], "empty workload roster")
    require(fresh or set(config["tasks"]) <= set(WORKLOADS), "unexpected workload roster")
    for name, task in config["tasks"].items():
        require(re.fullmatch(r"[a-z][a-z0-9_]*", name) is not None, "invalid workload name")
        fields = {"split", "baseline_source_hash", "inherited_used", "inherited_candidates", "max_new_rounds"}
        if fresh:
            fields |= {"source_split", "repeat_by_case", "pilot_ref"}
        require(set(task) == fields, "unknown task config fields")
        require(task["split"] in ("train", "validation"), "invalid data-view split")
        if fresh:
            require(task["source_split"] in ("train", "validation", "test"), "missing original split lineage")
            require(task["split"] == ("validation" if task["source_split"] == "validation" else "train"), "incorrect research split")
            _repeats(task["repeat_by_case"])
            identity(task["pilot_ref"])
            require(task["inherited_candidates"] == [] and all(v == 0 for v in task["inherited_used"].values()), "fresh campaign cannot invent inherited budgets")
            require(task["max_new_rounds"] == 3, "fresh campaign requires three source rounds")
        else:
            require(task["split"] == _split(name), "incorrect task split")
        identity(task["baseline_source_hash"])
        _counters(task["inherited_used"], budgets=True)
        require(type(task["max_new_rounds"]) is int and 0 <= task["max_new_rounds"] <= POLICY["max_new_rounds"], "invalid new source round limit")
        require(isinstance(task["inherited_candidates"], list), "inherited source list required")
        seen = set()
        for candidate in task["inherited_candidates"]:
            cid = nonempty(candidate.get("candidate_id"), "inherited candidate ID")
            require(cid not in seen, "duplicate inherited candidate")
            seen.add(cid)
            identity(candidate.get("source_hash")); identity(candidate.get("patch_hash"))
            require(candidate.get("stable_id") == f"{candidate.get('origin_run_id')}/{task['split']}/{cid}", "inherited stable attempt identity differs")
            nonempty(candidate.get("origin_run_id"), "origin run ID")
            require(isinstance(candidate.get("source_parent"), dict), "inherited source parent required")
            identity(candidate["source_parent"].get("source_hash"))
            probes_list(candidate.get("probes", []))
        require(len(seen) <= task["inherited_used"]["source"], "inherited source count exceeds charged budget")
    predecessor = config["predecessor"]
    if fresh:
        require(predecessor is None, "fresh campaign does not inherit a historical experiment")
    else:
        require(isinstance(predecessor, dict) and {"checkpoint", "checkpoint_hash", "config_hash", "head_hash", "campaign_id"} <= set(predecessor), "predecessor binding required")
        for key in ("checkpoint_hash", "config_hash", "head_hash"):
            identity(predecessor[key])
    require(isinstance(config["provenance"], dict), "provenance must be an object")
    canonical(config)


def _active(state):
    return [(name, sid) for name, task in state["tasks"].items() for sid, stage in task["stages"].items()
            if stage["attempts"][-1]["outcome"] is None]


def _safe_source(task, cid):
    """Current build/correctness/prepared/runtime, independent of timing quality."""
    stages = [stage for stage in task["stages"].values() if stage["candidate_id"] == cid]
    builds = [stage for stage in stages if stage["kind"] == "build"]
    if not builds:
        return False
    latest_build = max(builds, key=lambda stage: stage["attempts"][-1]["start_order"])
    if latest_build["attempts"][-1]["outcome"] != "success":
        return False
    build_position = latest_build["attempts"][-1]["start_order"]
    for kind in ("correctness", "runtime"):
        matches = [stage for stage in stages if stage["kind"] == kind and stage["attempts"][-1]["start_order"] > build_position]
        if not matches or max(matches, key=lambda stage: stage["attempts"][-1]["start_order"])["attempts"][-1]["outcome"] != "success":
            return False
    return True


def _transition(state, config, operation, arguments):
    a = deepcopy(arguments)
    require(operation in ARGUMENTS and not set(a) - ARGUMENTS[operation], "unknown transition arguments")
    if operation == "checkpoint":
        nonempty(a.get("checkpoint_id"), "checkpoint ID"); nonempty(a.get("reason"), "checkpoint reason")
        nonempty(a.get("next_action"), "next action")
        require(a.get("resources_released") is True and not _active(state), "checkpoint requires finished stages and released resources")
        require(isinstance(a.get("artifacts", {}), dict), "checkpoint artifacts must be an object")
        require(a["checkpoint_id"] != state["latest_checkpoint_id"], "duplicate checkpoint ID")
        state.update(status="paused", latest_checkpoint_id=a["checkpoint_id"])
        return
    if operation == "resume":
        require(state["status"] == "paused" and a.get("checkpoint_id") == state["latest_checkpoint_id"], "resume requires latest paused checkpoint")
        nonempty(a.get("reason"), "resume reason")
        state["status"] = "active"
        return
    name = a.get("workload")
    require(name in state["tasks"], "unknown workload")
    task = state["tasks"][name]
    baseline = config["tasks"][name]["baseline_source_hash"]
    timing_options = {"policy": config["policy"], "repeat_by_case": config["tasks"][name].get("repeat_by_case")}
    if operation == "register":
        require(state["status"] == "active" and not task["frozen"], "source search is paused or frozen")
        require(all(c["feedback_closed"] for c in task["candidates"].values()), "close source feedback before another proposal")
        require(task["new_source_attempts"] < config["tasks"][name]["max_new_rounds"], "new source round limit exhausted")
        require(task["used"]["source"] < BUDGETS["source"], "source budget exhausted")
        cid = nonempty(a.get("candidate_id"), "candidate ID")
        require(cid not in task["candidates"], "duplicate candidate ID")
        source, patch = identity(a.get("source_hash")), identity(a.get("patch_hash"))
        parent = a.get("source_parent")
        require(isinstance(parent, dict) and set(parent) == {"candidate_id", "source_hash"}, "explicit source parent required")
        parent["source_hash"] = identity(parent["source_hash"])
        require(source != baseline and source != parent["source_hash"], "candidate must change optimization source")
        require(all(c["source_hash"] != source for c in task["candidates"].values()), "same source requires another observation")
        basis = a.get("decision_basis", [])
        require(isinstance(basis, list) and all(isinstance(ref, str) for ref in basis) and len(set(basis)) == len(basis), "invalid decision basis")
        require(all(ref in task["observations"] and task["observations"][ref]["close_feedback"] for ref in basis), "decision basis must reference closed same-task observations")
        require(task["new_source_attempts"] == 0 or basis, "next candidate requires recorded feedback basis")
        if parent["candidate_id"] is None:
            require(parent["source_hash"] == baseline, "original parent identity mismatch")
            require(_safe_source(task, None), "baseline parent requires current build, correctness, prepared output and runtime")
        else:
            prior = task["candidates"].get(parent["candidate_id"])
            require(prior is not None and prior["source_hash"] == parent["source_hash"], "parent source identity mismatch")
            require(prior["feedback_closed"] and _safe_source(task, parent["candidate_id"]), "parent requires current build, correctness, prepared output and runtime")
        artifacts = a.get("artifacts", {})
        require(isinstance(artifacts, dict), "source artifacts must be an object")
        task["candidates"][cid] = {"candidate_id": cid, "source_hash": source, "patch_hash": patch,
            "source_parent": parent, "decision_basis": basis, "probes": probes_list(a.get("probes", [])),
            "artifacts": artifacts, "origin_run_id": config["campaign_id"], "stable_id": f"{config['campaign_id']}/{task['split']}/{cid}",
            "inherited": False, "feedback_closed": False, "observation_ids": [], "current_round_started": False}
        task["used"]["source"] += 1
        task["new_source_attempts"] += 1
        return
    if operation == "qualify_continuation":
        require(config.get("schema_version") == FRESH_SCHEMA and not task["frozen"]
                and state["status"] == "active" and _active(state) == [("dynamic_quant", "dynamic_quant001-search")],
                "continuation requires only its exact original active stage")
        stage = task["stages"].get(a.get("stage_id"))
        candidate = task["candidates"].get("dynamic_quant001")
        from level2_cohort_continuation import validate_qualification
        validate_qualification(stage, candidate, a)
        stage["continuation"] = deepcopy(a)
        return
    if operation == "qualify_prestart":
        require(set(a) == ARGUMENTS[operation], "prestart qualification fields differ")
        require(config.get("schema_version") == FRESH_SCHEMA and task["frozen"]
                and state["status"] == "active" and not _active(state),
                "prestart qualification requires a quiescent frozen fresh task")
        stage = task["stages"].get(a.get("stage_id"))
        require(stage is not None and "prestart_recovery" not in stage,
                "stage is missing or already qualified")
        candidate = task["candidates"].get(stage["candidate_id"])
        from level2_stage_recovery import validate_qualification
        validate_qualification(stage, candidate, a)
        stage["prestart_recovery"] = deepcopy(a)
        return
    if operation == "start":
        require(state["status"] == "active" and not _active(state), "campaign paused or another host stage is active")
        sid, kind, cid = nonempty(a.get("stage_id"), "stage ID"), a.get("kind"), a.get("candidate_id")
        require(kind in KINDS, "unknown stage kind")
        candidate = task["candidates"].get(cid) if cid is not None else None
        require(cid is None or candidate is not None, "unknown candidate")
        require(not (task["frozen"] and candidate and kind in {"build", "static"}), "frozen candidate build/source identity cannot change")
        plan = a.get("plan")
        require(isinstance(plan, dict) and plan, "frozen stage plan required")
        for dependency in plan.get("depends_on", []):
            require(dependency in task["stages"] and task["stages"][dependency]["attempts"][-1]["outcome"] == "success", "stage dependency did not succeed")
        if "source_hash" in plan:
            source = identity(plan["source_hash"])
            require(source == (candidate["source_hash"] if candidate else baseline) or kind == "control", "stage source identity mismatch")
        if kind == "timing":
            require(candidate is not None, "candidate timing must consume a timing group")
            require(_safe_source(task, cid), "timing requires current build, correctness, prepared output and runtime")
            plan = _timing_plan(plan, candidate, baseline, **timing_options)
            if plan["purpose"] == "final":
                require(task["frozen"] and cid in task["selection"] and plan == task["final_plans"][cid], "final requires exact frozen plan")
                require(not any(s["kind"] == "timing" and s["candidate_id"] == cid and s["plan"]["purpose"] == "final" and key != sid
                                for key, s in task["stages"].items()), "final plan already has a stage; new retries need another frozen campaign plan")
            else:
                require(not task["frozen"], "search cannot follow final freeze")
                require(cid in task["search_candidate_ids"] or len(task["search_candidate_ids"]) < 3, "at most three distinct search candidates")
                selected = plan["final_candidate_ids"]
                require(isinstance(selected, list) and selected and len(set(selected)) == len(selected) and all(c in task["candidates"] for c in selected), "invalid final candidate reservation")
                require(set(task["reserved_final_candidate_ids"]) <= set(selected), "search cannot silently release reserved final candidates")
        elif kind == "control":
            require(cid is None and not plan.get("comparisons"), "candidate comparisons cannot hide in fixed controls")
            require(plan.get("control_type") in {"aa", "method"}, "fixed control type is required")
            require(identity(plan.get("source_hash")) in {baseline, *(c["source_hash"] for c in task["candidates"].values())}, "unknown fixed control source")
            _cases(plan.get("case_ids")); identity(plan.get("manifest_ref"))
        elif kind == "correctness":
            require(plan.get("case_ids") == ALL_CASES, "correctness must cover all 20 cases")
        elif kind == "profile":
            _cases(plan.get("case_ids"))
            require(plan.get("capture_window"), "mechanism profile needs frozen capture window")
            require(plan.get("profiler_mode") != PROFILER_MODE, "task-only candidate measurement is timing, not mechanism profile")
            if candidate and not task["frozen"]:
                require(set(plan["case_ids"]) <= set(SENTINELS + [p["case_id"] for p in candidate["probes"]]), "search profile case was not declared")
        if cid is None and kind != "control":
            require(identity(plan.get("source_hash")) == baseline, "only original baseline is exempt from candidate charges")
        previous = task["stages"].get(sid)
        if previous:
            require(previous["kind"] == kind and previous["candidate_id"] == cid and previous["plan"] == plan, "stage identity and plan are immutable")
            last = previous["attempts"][-1]
            qualified = previous.get("prestart_recovery")
            if qualified is not None:
                from level2_stage_recovery import validate_qualification
                validate_qualification(previous, candidate, qualified)
            require((last["outcome"] == "prestart_failure" or qualified is not None)
                    and last["native_started"] is False and last["formal_samples"] == 0,
                    "only an evidenced native-not-started failure may recover")
            require(previous["recoveries"] == 0, "only one prestart recovery per stage")
            previous["recoveries"] += 1
        else:
            previous = {"stage_id": sid, "candidate_id": cid, "kind": kind, "plan": deepcopy(plan), "recoveries": 0, "attempts": []}
            task["stages"][sid] = previous
        cost = "build" if kind == "build" else "timing_groups" if kind == "timing" else "profile_groups" if kind == "profile" else None
        charge = cost if candidate and cost and (kind == "build" or not previous["attempts"]) else None
        if charge:
            require(task["used"][charge] < BUDGETS[charge], charge + " budget exhausted")
            if kind == "timing" and plan["purpose"] == "search":
                require(BUDGETS["timing_groups"] - task["used"]["timing_groups"] - 1 >= len(plan["final_candidate_ids"]), "insufficient reserved full evaluation groups")
            task["used"][charge] += 1
        if kind == "timing" and plan["purpose"] == "search":
            task["reserved_final_candidate_ids"] = list(plan["final_candidate_ids"])
            if cid not in task["search_candidate_ids"]:
                task["search_candidate_ids"].append(cid)
        previous["attempts"].append({"outcome": None, "native_started": None, "formal_samples": 0, "charged": charge,
                                     "start_order": sum(task["stage_starts"].values()) + 1})
        if previous.get("prestart_recovery") is not None:
            previous["attempts"][-1]["prestart_qualification"] = deepcopy(previous["prestart_recovery"]["qualification"])
        task["stage_starts"][kind] += 1
        if candidate:
            candidate["feedback_closed"] = False
            if not candidate["inherited"] and not candidate["current_round_started"]:
                candidate["current_round_started"] = True
                task["new_rounds_started"] += 1
        else:
            task["fixed_costs"][kind + "_starts"] = task["fixed_costs"].get(kind + "_starts", 0) + 1
        return
    if operation == "finish":
        stage = task["stages"].get(a.get("stage_id"))
        require(stage is not None and stage["attempts"][-1]["outcome"] is None, "stage is not active")
        require(a.get("outcome") in OUTCOMES, "execution outcome must be independent of measurement quality")
        require(type(a.get("native_started")) is bool, "native_started must be explicitly recorded")
        samples = a.get("formal_samples", 0)
        require(type(samples) is int and samples >= 0, "invalid formal sample count")
        _evidence(a.get("evidence"))
        qualified = stage["attempts"][-1].get("prestart_qualification")
        if qualified is not None:
            original = Path(stage["prestart_recovery"]["failed_result"]["path"])
            require(a["evidence"].get("qualification") == qualified
                    and a["evidence"].get("result", {}).get("path") == str(original.with_name("result.recovery-01.json")),
                    "recovered finish must retain qualification and distinct result")
        if a["outcome"] != "success":
            nonempty(a.get("reason"), "failure reason")
        if not a["native_started"]:
            require(samples == 0, "unstarted native cannot have samples")
        if a["outcome"] == "prestart_failure":
            require(a["native_started"] is False and samples == 0, "prestart recovery requires native_started=False")
        if a["outcome"] == "success" and stage["kind"] in {"correctness", "timing", "profile", "control"}:
            require(a["native_started"] is True, "successful hardware stage requires native execution")
        if a["outcome"] == "success" and stage["kind"] == "runtime" and not a["native_started"]:
            require(isinstance(a["evidence"].get("runtime"), dict), "derived runtime assessment needs bound native lifecycle evidence")
            checks = [s for s in task["stages"].values() if s["kind"] == "correctness" and s["candidate_id"] == stage["candidate_id"]]
            require(checks and max(checks, key=lambda s: s["attempts"][-1]["start_order"])["attempts"][-1]["outcome"] == "success",
                    "derived runtime assessment requires successful prepared correctness")
        if a["outcome"] == "success" and stage["kind"] == "correctness":
            require(a["evidence"].get("prepared_output_checked") is True, "correctness must bind prepared output validation")
        if a["outcome"] == "success" and stage["kind"] == "timing":
            require(samples == expected_samples(stage["plan"]), "timing success requires the frozen process, pair and configuration coverage")
        if stage.get("continuation") is not None:
            require(a["evidence"].get("continuation") == stage["continuation"]["qualification"],
                    "continuation finish must bind its exact certificate")
            if a["outcome"] == "success":
                c = a.get("actual_costs", {})
                require(c.get("native_processes_started") == 7 and c.get("native_processes_completed") == 6
                        and c.get("role_samples") == samples + 360 and c.get("timed_complete_calls") == 46800
                        and c.get("warmup_complete_calls") == 1560,
                        "continuation actual costs must include original failed p03")
        costs = _counters(a.get("actual_costs", {}))
        for key, amount in costs.items():
            task["actual_costs"][key] = task["actual_costs"].get(key, 0) + amount
            if stage["candidate_id"] is None:
                task["fixed_costs"][key] = task["fixed_costs"].get(key, 0) + amount
        stage["attempts"][-1].update({k: deepcopy(v) for k, v in a.items() if k not in {"workload", "stage_id"}})
        return
    if operation == "observe":
        oid, cid = nonempty(a.get("observation_id"), "observation ID"), a.get("candidate_id")
        require(all(oid not in t["observations"] for t in state["tasks"].values()), "duplicate observation ID")
        require(cid in task["candidates"], "observation requires registered source identity")
        candidate = task["candidates"][cid]
        ids = a.get("stage_ids", [])
        require(isinstance(ids, list) and len(set(ids)) == len(ids), "invalid observation stages")
        if config["schema_version"] == FRESH_SCHEMA:
            require(ids, "fresh feedback must reference an executed stage")
        for sid in ids:
            require(sid in task["stages"] and task["stages"][sid]["candidate_id"] == cid and task["stages"][sid]["attempts"][-1]["outcome"] is not None,
                    "observation stages must be completed and from the same source")
        require(isinstance(a.get("feedback"), dict) and a["feedback"], "actual feedback required")
        require(type(a.get("close_feedback", True)) is bool and isinstance(a.get("quality", {}), dict), "invalid feedback/quality fields")
        if a.get("report_ref") is not None:
            identity(a["report_ref"])
        if a.get("close_feedback", True):
            require(not any(s["candidate_id"] == cid and s["attempts"][-1]["outcome"] is None for s in task["stages"].values()), "cannot close running source stages")
            seen = {}
            for old in candidate["observation_ids"]:
                for sid, count in task["observations"][old]["stage_attempts"].items():
                    seen[sid] = max(seen.get(sid, 0), count)
            require(all(sid in ids for sid, s in task["stages"].items() if s["candidate_id"] == cid and seen.get(sid, 0) < len(s["attempts"])),
                    "feedback must retain every newly completed source stage")
        task["observations"][oid] = {**a, "protocol": config["policy"]["protocol"], "stable_attempt_id": candidate["stable_id"],
                                       "stage_attempts": {sid: len(task["stages"][sid]["attempts"]) for sid in ids}}
        candidate["observation_ids"].append(oid)
        candidate["feedback_closed"] = a.get("close_feedback", True)
        return
    if operation == "freeze":
        require(not task["frozen"] and all(c["feedback_closed"] for c in task["candidates"].values()), "close feedback before freezing once")
        if config["schema_version"] == FRESH_SCHEMA:
            require(task["new_source_attempts"] == 3 and task["new_rounds_started"] == 3,
                    "complete three actual source rounds before final freeze; checkpoint unfinished work instead")
        nonempty(a.get("reason"), "freeze reason")
        selected, plans = a.get("candidate_ids"), a.get("final_plans")
        require(isinstance(selected, list) and len(set(selected)) == len(selected) and all(cid in task["candidates"] for cid in selected), "invalid final selection")
        require(isinstance(plans, dict) and set(plans) == set(selected), "every selected candidate needs final plan")
        require(len(selected) <= BUDGETS["timing_groups"] - task["used"]["timing_groups"], "insufficient full evaluation budget")
        normalized = {}
        for cid, plan in plans.items():
            require(_safe_source(task, cid), "selected candidate needs current correctness/runtime")
            normalized[cid] = _timing_plan(plan, task["candidates"][cid], baseline, **timing_options)
            require(plan["purpose"] == "final", "freeze needs complete 20-case final plans")
        roster = [{k: deepcopy(v) for k, v in c.items() if k not in {"feedback_closed", "observation_ids", "current_round_started"}}
                  for c in task["candidates"].values()]
        task.update(frozen=True, selection=selected, final_plans=normalized, freeze_reason=a["reason"],
                    frozen_roster={"candidates": roster, "sha256": digest(roster)})
        return
    raise ValueError("unsupported ledger transition")


def _predecessor(path):
    """Read only checkpoint, identity and cost metadata; never performance/source files."""
    path = Path(path).resolve()
    checkpoint = _read_json(path)
    if checkpoint.get("schema_version") == CHECKPOINT_SCHEMA:
        ledger = Campaign(checkpoint["ledger"])
        ledger.verify(expected_head=checkpoint["head_hash"], expected_config_hash=checkpoint["config_hash"])
        require(checkpoint == ledger._checkpoint_value(ledger.events[checkpoint["sequence"]]), "predecessor checkpoint seal mismatch")
    else:
        from shared_context_campaign import Ledger
        require(checkpoint.get("schema_version") == "shared_context_checkpoint_pointer_v1", "unsupported predecessor checkpoint")
        ledger = Ledger(checkpoint["ledger"])
        ledger.verify(expected_head=checkpoint["ledger_head"], expected_config_hash=checkpoint["ledger_config_hash"])
        require(checkpoint.get("resources_released") is True and checkpoint.get("status") == "paused", "predecessor must be paused and released")
        remaining = {name: {k: BUDGETS[k] - task["used"][k] for k in BUDGETS} for name, task in ledger.state["tasks"].items()}
        require(checkpoint.get("remaining_budgets") == remaining, "checkpoint budgets differ from ledger")
        delivery_ref = checkpoint.get("delivery")
        if delivery_ref:
            require(_file_hash(delivery_ref["path"]) == delivery_ref["sha256"], "delivery hash differs from checkpoint")
            delivery = _read_json(delivery_ref["path"])
            require(delivery.get("remaining_budgets") == remaining, "delivery budgets differ from ledger")
        for name, entry in checkpoint.get("qualification", {}).items():
            closure = _read_json(entry["closure"])
            require(closure.get("operator") == name and closure.get("split") == ledger.state["tasks"][name]["split"], "task closure identity mismatch")
            require(closure.get("used") == ledger.state["tasks"][name]["used"] and closure.get("remaining") == remaining[name], "task closure budgets differ from ledger")
    require(ledger.state["status"] == "paused", "predecessor ledger must be paused")
    return ledger, {"checkpoint": str(path), "checkpoint_hash": _file_hash(path), "config_hash": ledger.config_hash,
                    "head_hash": ledger.events[-1]["hash"], "campaign_id": ledger.config["campaign_id"]}


def create(directory, *, campaign_id, prior_checkpoint, baselines=None, workloads=None, provenance=None, max_new_rounds=None):
    """Create a fresh run ledger with fully inherited lifetime budget counters."""
    old, predecessor = _predecessor(prior_checkpoint)
    require(campaign_id != old.config["campaign_id"], "new campaign requires an independent run ID")
    names = list(TRAIN_WORKLOADS if workloads is None else workloads)
    require(names and len(set(names)) == len(names) and set(names) <= set(WORKLOADS), "invalid campaign workload roster")
    require(set(names) <= set(old.state["tasks"]), "predecessor lacks workload budget")
    baselines = baselines or {name: old.config["tasks"][name]["baseline_source_hash"] for name in names}
    require(set(baselines) == set(names), "baseline identities must match workload roster")
    limits = {name: POLICY["max_new_rounds"] for name in names}
    if max_new_rounds is not None:
        if type(max_new_rounds) is int:
            limits = {name: max_new_rounds for name in names}
        else:
            require(isinstance(max_new_rounds, dict) and set(max_new_rounds) <= set(names), "invalid per-task round limits")
            limits.update(max_new_rounds)
    tasks = {}
    for name in names:
        source = identity(baselines[name])
        require(source == old.config["tasks"][name]["baseline_source_hash"], "baseline changed across budget inheritance")
        inherited = []
        for cid, candidate in old.state["tasks"][name]["candidates"].items():
            origin = candidate.get("origin_run_id") or candidate.get("origin", {}).get("run_id") or old.config["campaign_id"]
            inherited.append({"candidate_id": cid, "source_hash": candidate["source_hash"], "patch_hash": candidate["patch_hash"],
                "source_parent": deepcopy(candidate["source_parent"]), "decision_basis": [], "probes": deepcopy(candidate.get("probes", [])),
                "artifacts": deepcopy(candidate.get("artifacts", {})), "origin_run_id": origin, "stable_id": f"{origin}/{_split(name)}/{cid}"})
        tasks[name] = {"split": _split(name), "baseline_source_hash": source, "max_new_rounds": limits[name],
                       "inherited_used": deepcopy(old.state["tasks"][name]["used"]), "inherited_candidates": inherited}
    config = {"schema_version": SCHEMA, "campaign_id": campaign_id, "policy": deepcopy(POLICY), "budgets": dict(BUDGETS),
              "tasks": tasks, "predecessor": predecessor, "provenance": deepcopy(provenance or {})}
    return _create_ledger(directory, config)


def create_fresh(directory, *, campaign_id, workloads, provenance=None):
    """Create a new manifest-driven experiment, with no fabricated predecessor.

    Each workload declares baseline_source_hash, source_split, repeat_by_case,
    and pilot_ref. A previously sealed campaign is never relabelled as v2.
    Original test tasks enter the research train view with explicit test lineage;
    this ledger still never authorizes graph-policy training.
    """
    require(isinstance(workloads, dict) and workloads, "workload manifest required")
    tasks = {}
    for name, declaration in workloads.items():
        require(isinstance(declaration, dict) and set(declaration) == {
            "baseline_source_hash", "source_split", "repeat_by_case", "pilot_ref"},
            "fresh workload needs frozen source, split and timing pilot")
        tasks[name] = {**deepcopy(declaration),
                       "split": "validation" if declaration["source_split"] == "validation" else "train",
                       "max_new_rounds": 3, "inherited_used": dict.fromkeys(BUDGETS, 0),
                       "inherited_candidates": []}
    config = {"schema_version": FRESH_SCHEMA, "campaign_id": campaign_id,
              "policy": deepcopy(FRESH_POLICY), "budgets": dict(BUDGETS), "tasks": tasks,
              "predecessor": None, "provenance": deepcopy(provenance or {})}
    return _create_ledger(directory, config)


def _create_ledger(directory, config):
    _validate_config(config)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    _write_exclusive(directory / "config.json", config)
    _write_exclusive(directory / "config.sha256.json", {"sha256": digest(config)})
    genesis = {"sequence": 0, "event_id": "genesis", "operation": "prepare", "arguments": {},
               "recorded_at": datetime.now(timezone.utc).isoformat(), "previous_hash": ZERO_HASH, "config_hash": digest(config)}
    genesis["hash"] = digest(genesis)
    _write_exclusive(directory / "events.jsonl", genesis)
    (directory / ".lock").touch(exist_ok=False)
    (directory / "checkpoints").mkdir()
    _sync_directory(directory)
    return Campaign(directory)


class Campaign:
    """Append-only transactions. Construction/status/verification are pure reads."""
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self._load()

    def _load(self):
        config = _read_json(self.directory / "config.json")
        _validate_config(config)
        config_hash = digest(config)
        require(_read_json(self.directory / "config.sha256.json") == {"sha256": config_hash}, "immutable config hash mismatch")
        data = (self.directory / "events.jsonl").read_bytes()
        require(data and data.endswith(b"\n"), "incomplete event tail; verification never repairs it")
        state, events, ids, prior, checkpoints = _initial_state(config), [], {}, ZERO_HASH, {}
        for sequence, line in enumerate(data.splitlines()):
            event = json.loads(line)
            require(canonical(event) == line, "noncanonical or ambiguous event JSON")
            require(set(event) == {"sequence", "event_id", "operation", "arguments", "recorded_at", "previous_hash", "config_hash", "hash"}, "invalid event schema")
            require(type(event["sequence"]) is int and event["sequence"] == sequence, "event sequence mismatch")
            require(event["previous_hash"] == prior and event["config_hash"] == config_hash, "event hash chain/config mismatch")
            require(event["hash"] == digest({k: v for k, v in event.items() if k != "hash"}), "event content hash mismatch")
            nonempty(event["event_id"], "event ID"); nonempty(event["recorded_at"], "event timestamp")
            require(event["event_id"] not in ids and isinstance(event["arguments"], dict), "duplicate event ID or invalid arguments")
            if sequence == 0:
                require(event["operation"] == "prepare" and event["event_id"] == "genesis" and event["arguments"] == {}, "invalid genesis")
            else:
                _transition(state, config, event["operation"], event["arguments"])
            if event["operation"] == "checkpoint":
                cid = event["arguments"]["checkpoint_id"]
                require(cid not in checkpoints, "duplicate checkpoint ID")
                checkpoints[cid] = (sequence, digest(state))
            events.append(event); ids[event["event_id"]] = event; prior = event["hash"]
        self.config, self.config_hash, self.state, self.events, self.event_ids = config, config_hash, state, events, ids
        self._checkpoint_states = checkpoints
        sealed = set()
        for path in (self.directory / "checkpoints").glob("*.json"):
            seal = _read_json(path)
            cid = seal.get("checkpoint_id")
            require(cid in checkpoints, "seal pins a missing checkpoint event")
            event = events[checkpoints[cid][0]]
            require(seal == self._checkpoint_value(event), "checkpoint seal mismatch")
            require(path.name == hashlib.sha256(cid.encode()).hexdigest() + ".json", "checkpoint filename mismatch")
            sealed.add(cid)
        self.unsealed_checkpoints = [cid for cid in checkpoints if cid not in sealed]
        return self

    def _checkpoint_value(self, event):
        cid = event["arguments"]["checkpoint_id"]
        return {"schema_version": CHECKPOINT_SCHEMA, "ledger": str(self.directory), "checkpoint_id": cid,
                "sequence": event["sequence"], "config_hash": self.config_hash, "head_hash": event["hash"],
                "state_hash": self._checkpoint_states[cid][1]}

    def _seal(self, event):
        value = self._checkpoint_value(event)
        path = self.directory / "checkpoints" / (hashlib.sha256(value["checkpoint_id"].encode()).hexdigest() + ".json")
        if path.exists():
            require(_read_json(path) == value, "existing checkpoint seal differs")
        else:
            _write_exclusive(path, value)
            _sync_directory(path.parent)
        return path

    def verify(self, *, expected_head=None, expected_config_hash=None):
        self._load()
        require(not self.unsealed_checkpoints, "unsealed checkpoint; retry its original idempotency key")
        require(expected_head is None or identity(expected_head) == self.events[-1]["hash"], "externally pinned head mismatch")
        require(expected_config_hash is None or identity(expected_config_hash) == self.config_hash, "externally pinned config mismatch")
        return {"valid": True, "read_only": True, "event_count": len(self.events), "head_hash": self.events[-1]["hash"], "config_hash": self.config_hash}

    def status(self, *, split=None):
        self._load()
        require(split in {None, "train", "validation"}, "invalid split")
        result = deepcopy(self.state)
        result["tasks"] = {n: t for n, t in result["tasks"].items() if split is None or t["split"] == split}
        for name, task in result["tasks"].items():
            task["remaining"] = {k: BUDGETS[k] - task["used"][k] for k in BUDGETS}
            task["remaining_new_source_rounds"] = self.config["tasks"][name]["max_new_rounds"] - task["new_source_attempts"]
        result.update(config_hash=self.config_hash, head_hash=self.events[-1]["hash"], event_count=len(self.events),
                      unsealed_checkpoints=list(self.unsealed_checkpoints), read_only=True, hardware_executed=False)
        return result

    def timing_plan(self, workload, candidate_id, *, purpose, manifest_ref,
                    final_candidate_ids=None, **schedule):
        self._load()
        task = self.config["tasks"][workload]
        return timing_plan(self.state["tasks"][workload]["candidates"][candidate_id],
                           task["baseline_source_hash"], purpose=purpose, manifest_ref=manifest_ref,
                           final_candidate_ids=final_candidate_ids, policy=self.config["policy"],
                           repeat_by_case=task.get("repeat_by_case"), **schedule)

    def validate_start(self, *, workload, stage_id, kind, plan, candidate_id=None, event_id=None):
        """Pure preflight. start() independently revalidates under the write lock."""
        self._load()
        require(not self.unsealed_checkpoints, "seal committed checkpoint before continuing")
        arguments = dict(workload=workload, stage_id=stage_id, kind=kind, plan=plan, candidate_id=candidate_id)
        canonical(arguments)
        if event_id is not None:
            nonempty(event_id, "event ID")
            require(event_id != "genesis", "reserved event ID")
        existing = self.event_ids.get(event_id)
        if existing is not None:
            require(existing["operation"] == "start" and existing["arguments"] == arguments, "idempotency key reused with different arguments")
        else:
            _transition(deepcopy(self.state), self.config, "start", arguments)
        return {"valid": True, "read_only": True, "already_committed": existing is not None,
                "head_hash": self.events[-1]["hash"], "config_hash": self.config_hash}

    def _commit(self, operation, *, event_id, **arguments):
        nonempty(event_id, "event ID")
        require(event_id != "genesis", "reserved event ID")
        canonical(arguments)
        with (self.directory / ".lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._load()
            if event_id in self.event_ids:
                event = self.event_ids[event_id]
                require(event["operation"] == operation and event["arguments"] == arguments, "idempotency key reused with different arguments")
                if operation == "checkpoint":
                    self._seal(event)
                return deepcopy(event)
            require(not self.unsealed_checkpoints, "seal committed checkpoint before continuing")
            updated = deepcopy(self.state)
            _transition(updated, self.config, operation, arguments)
            if operation == "checkpoint":
                require(arguments["checkpoint_id"] not in self._checkpoint_states, "duplicate checkpoint ID")
            event = {"sequence": len(self.events), "event_id": event_id, "operation": operation, "arguments": deepcopy(arguments),
                     "recorded_at": datetime.now(timezone.utc).isoformat(), "previous_hash": self.events[-1]["hash"], "config_hash": self.config_hash}
            event["hash"] = digest(event)
            with (self.directory / "events.jsonl").open("ab") as stream:
                stream.write(canonical(event) + b"\n"); stream.flush(); os.fsync(stream.fileno())
            self.events.append(event); self.event_ids[event_id] = event; self.state = updated
            if operation == "checkpoint":
                self._checkpoint_states[arguments["checkpoint_id"]] = (event["sequence"], digest(updated))
                self._seal(event)
            return deepcopy(event)

    def register(self, *, event_id, workload, candidate_id, source_hash, patch_hash, source_parent, decision_basis, probes=None, artifacts=None):
        return self._commit("register", event_id=event_id, workload=workload, candidate_id=candidate_id,
                            source_hash=source_hash, patch_hash=patch_hash, source_parent=source_parent,
                            decision_basis=decision_basis, probes=probes or [], artifacts=artifacts or {})

    def qualify_continuation(self, *, event_id, workload, stage_id, source_hash, plan_hash, qualification, reason):
        return self._commit("qualify_continuation", event_id=event_id, workload=workload, stage_id=stage_id,
                            source_hash=source_hash, plan_hash=plan_hash, qualification=qualification, reason=reason)

    def qualify_prestart(self, *, event_id, workload, stage_id, source_hash, plan_hash, failed_result, qualification, reason):
        return self._commit("qualify_prestart", event_id=event_id, workload=workload, stage_id=stage_id,
                            source_hash=source_hash, plan_hash=plan_hash, failed_result=failed_result,
                            qualification=qualification, reason=reason)

    def start(self, *, event_id, workload, stage_id, kind, plan, candidate_id=None):
        return self._commit("start", event_id=event_id, workload=workload, stage_id=stage_id, kind=kind, plan=plan, candidate_id=candidate_id)

    def finish(self, *, event_id, workload, stage_id, outcome, evidence, native_started, formal_samples=0, actual_costs=None, reason=None):
        return self._commit("finish", event_id=event_id, workload=workload, stage_id=stage_id, outcome=outcome, evidence=evidence,
                            native_started=native_started, formal_samples=formal_samples, actual_costs=actual_costs or {}, reason=reason)

    def observe(self, *, event_id, workload, observation_id, candidate_id, stage_ids, feedback, close_feedback=True, report_ref=None, quality=None):
        return self._commit("observe", event_id=event_id, workload=workload, observation_id=observation_id, candidate_id=candidate_id,
                            stage_ids=stage_ids, feedback=feedback, close_feedback=close_feedback, report_ref=report_ref, quality=quality or {})

    def freeze(self, *, event_id, workload, candidate_ids, final_plans, reason):
        return self._commit("freeze", event_id=event_id, workload=workload, candidate_ids=candidate_ids, final_plans=final_plans, reason=reason)

    def checkpoint(self, *, event_id, checkpoint_id, reason, next_action, resources_released, artifacts=None):
        return self._commit("checkpoint", event_id=event_id, checkpoint_id=checkpoint_id, reason=reason, next_action=next_action,
                            resources_released=resources_released, artifacts=artifacts or {})

    def resume(self, *, event_id, checkpoint_id, reason):
        return self._commit("resume", event_id=event_id, checkpoint_id=checkpoint_id, reason=reason)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("create", "create-fresh", "status", "verify", *ARGUMENTS):
        item = commands.add_parser(command)
        item.add_argument("--ledger", type=Path, required=True)
        if command == "create":
            item.add_argument("--campaign-id", required=True)
            item.add_argument("--prior-checkpoint", type=Path, required=True)
            item.add_argument("--workload", action="append")
        elif command == "create-fresh":
            item.add_argument("--manifest", type=Path, required=True)
        elif command == "status":
            item.add_argument("--split", choices=("train", "validation"))
        elif command == "verify":
            item.add_argument("--expected-head"); item.add_argument("--expected-config-hash")
        else:
            item.add_argument("--payload", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "create":
        result = create(args.ledger, campaign_id=args.campaign_id, prior_checkpoint=args.prior_checkpoint, workloads=args.workload).status()
    elif args.command == "create-fresh":
        result = create_fresh(args.ledger, **_read_json(args.manifest)).status()
    else:
        ledger = Campaign(args.ledger)
        if args.command == "status":
            result = ledger.status(split=args.split)
        elif args.command == "verify":
            result = ledger.verify(expected_head=args.expected_head, expected_config_hash=args.expected_config_hash)
        else:
            result = getattr(ledger, args.command)(**_read_json(args.payload))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
