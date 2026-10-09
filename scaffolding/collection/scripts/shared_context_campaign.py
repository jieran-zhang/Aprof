#!/usr/bin/env python3
"""CPU-only, append-only ledger for shared_context_paired_v1 experiments.

No command discovers devices, executes workloads, imports gates, or edits prior
runs. Config and checkpoint files are immutable; events are the source of truth.
All mutation methods take an explicit event_id for safe caller retries. A stage
is charged before the caller starts its command, and failure never refunds it.
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


PROTOCOL = "shared_context_paired_v1"
SCHEMA = "shared_context_campaign_v1"
WORKLOADS = ("exp", "masked_scale", "foreach_addcdiv_scalar", "mish", "sigmoid", "gelu")
BUDGETS = {"source": 6, "build": 6, "timing_groups": 6, "profile_groups": 3}
SENTINELS = [1, 8, 14, 20]
ALL_CASES = list(range(1, 21))
ZERO_HASH = "sha256:" + "0" * 64
KINDS = {"static", "build", "correctness", "runtime", "timing", "profile", "control", "qualification"}
OUTCOMES = {"success", "failed", "build_failed", "correctness_failed", "runtime_failed",
            "quality_failed", "prestart_failure", "interrupted", "incomplete"}
OPERATIONS = {"register", "start_stage", "finish_stage", "observation", "freeze", "checkpoint", "resume"}
ARGUMENT_KEYS = {
    "register": {"workload", "candidate_id", "source_hash", "patch_hash", "source_parent", "decision_basis", "probes", "artifacts", "origin"},
    "start_stage": {"workload", "candidate_id", "stage_id", "kind", "plan"},
    "finish_stage": {"workload", "stage_id", "outcome", "formal_samples", "evidence", "reason", "actual_costs"},
    "observation": {"workload", "observation_id", "candidate_id", "stage_ids", "feedback", "close_feedback", "quality", "evidence_ref"},
    "freeze": {"workload", "candidate_ids", "final_plans", "reason"},
    "checkpoint": {"checkpoint_id", "reason", "next_action", "resources_released", "unresolved", "artifact_locations", "qualification"},
    "resume": {"checkpoint_id", "reason"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def identity(value):
    require(isinstance(value, str) and re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", value), "expected SHA-256 identity")
    return value if value.startswith("sha256:") else "sha256:" + value


def nonempty(value, label):
    require(isinstance(value, str) and bool(value.strip()), label + " is required")
    return value


def case_ids(values):
    require(isinstance(values, list) and values and all(type(n) is int and 1 <= n <= 20 for n in values), "invalid case IDs")
    require(len(values) == len(set(values)), "duplicate case IDs")
    return values


def probes_list(values):
    require(isinstance(values, list) and len(values) <= 2, "at most two predeclared probes")
    result = []
    for probe in values:
        require(isinstance(probe, dict) and set(probe) == {"case_id", "reason"}, "probe needs case_id and reason")
        require(type(probe["case_id"]) is int and 1 <= probe["case_id"] <= 20 and probe["case_id"] not in SENTINELS,
                "probe must be a nonsentinel case")
        nonempty(probe["reason"], "probe reason")
        result.append(deepcopy(probe))
    require(len({p["case_id"] for p in result}) == len(result), "duplicate probes")
    return result


def candidate_identity(value, baseline):
    allowed = {"candidate_id", "source_hash", "patch_hash", "source_parent", "decision_basis", "probes", "artifacts", "origin"}
    require(isinstance(value, dict) and not set(value) - allowed, "unknown candidate fields")
    result = deepcopy(value)
    nonempty(result.get("candidate_id"), "candidate_id")
    result["source_hash"] = identity(result.get("source_hash"))
    result["patch_hash"] = identity(result.get("patch_hash"))
    parent = result.get("source_parent")
    require(isinstance(parent, dict) and set(parent) == {"candidate_id", "source_hash"}, "source_parent identity required")
    parent["source_hash"] = identity(parent["source_hash"])
    if parent["candidate_id"] is None:
        require(parent["source_hash"] == baseline, "original parent identity mismatch")
    else:
        nonempty(parent["candidate_id"], "parent candidate ID")
    require(result["source_hash"] not in {parent["source_hash"], baseline}, "candidate must change optimization source")
    basis = result.setdefault("decision_basis", [])
    require(isinstance(basis, list) and all(isinstance(x, str) and x for x in basis) and len(set(basis)) == len(basis),
            "invalid decision basis")
    result["probes"] = probes_list(result.get("probes", []))
    for key in ("artifacts", "origin"):
        require(isinstance(result.setdefault(key, {}), dict), key + " must be an object")
    canonical(result)
    return result


def make_config(campaign_id, baselines, inherited_exp, protocol_hash, provenance=None):
    """Build the user-authorized six-workload config; exp001 consumes source 1."""
    nonempty(campaign_id, "campaign_id")
    require(isinstance(baselines, dict) and set(baselines) == set(WORKLOADS), "six baseline identities required")
    tasks = {}
    for name in WORKLOADS:
        baseline = identity(baselines[name])
        inherited = [candidate_identity(inherited_exp, baseline)] if name == "exp" else []
        if inherited:
            require(inherited[0]["candidate_id"] == "exp001" and bool(inherited[0]["origin"]), "exp001 requires inherited source provenance")
            require(inherited[0]["source_parent"]["candidate_id"] is None and not inherited[0]["decision_basis"],
                    "inherited exp001 must derive from the original baseline")
        tasks[name] = {"split": "validation" if name == "gelu" else "train", "baseline_source_hash": baseline,
                       "budgets": dict(BUDGETS), "inherited_candidates": inherited}
    result = {"schema_version": SCHEMA, "campaign_id": campaign_id, "protocol": PROTOCOL,
              "protocol_hash": identity(protocol_hash), "sentinels": list(SENTINELS), "max_probes": 2,
              "reserve_final_timing_groups": 1, "historical_queue": "prior_only_not_queued",
              "formal_admission": "unsupported_no_episode", "tasks": tasks, "provenance": deepcopy(provenance or {})}
    canonical(result)
    return result


def validate_config(config):
    require(isinstance(config, dict), "config must be an object")
    tasks = config.get("tasks", {})
    require(isinstance(tasks, dict) and set(tasks) == set(WORKLOADS), "unexpected workload roster")
    inherited = tasks["exp"].get("inherited_candidates", [])
    require(isinstance(inherited, list) and len(inherited) == 1, "exactly one inherited exp source required")
    expected = make_config(config.get("campaign_id"), {n: tasks[n].get("baseline_source_hash") for n in WORKLOADS},
                           inherited[0], config.get("protocol_hash"), config.get("provenance"))
    require(config == expected, "immutable campaign policy changed")
    return True


def _initial_state(config):
    tasks = {}
    for name, declared in config["tasks"].items():
        candidates = {}
        for value in declared["inherited_candidates"]:
            candidates[value["candidate_id"]] = {**deepcopy(value), "epoch": 0, "feedback_closed": False,
                                                   "observation_ids": [], "inherited": True}
        tasks[name] = {"split": declared["split"], "epoch": 0, "candidates": candidates, "observations": {}, "stages": {},
                       "used": {**dict.fromkeys(BUDGETS, 0), "source": len(candidates)}, "stage_starts": dict.fromkeys(KINDS, 0),
                       "actual_costs": {}, "frozen": False, "frozen_roster": None, "selection": [], "final_plans": {}}
    return {"schema_version": SCHEMA, "campaign_id": config["campaign_id"], "status": "paused",
            "formal_admission": "unsupported_no_episode", "tasks": tasks, "checkpoints": [], "latest_checkpoint_id": None}


def comparison_identities(candidate, baseline):
    controls = list(dict.fromkeys([candidate["source_parent"]["source_hash"], baseline]))
    return [{"control_source_hash": value, "candidate_source_hash": candidate["source_hash"]} for value in controls]


def timing_plan(candidate, baseline, *, purpose, manifest_ref):
    """Convenience constructor; any extra schedule fields are frozen with this plan."""
    return {"purpose": purpose, "case_ids": ALL_CASES if purpose == "final" else SENTINELS + [p["case_id"] for p in candidate["probes"]],
            "manifest_ref": identity(manifest_ref), "comparisons": comparison_identities(candidate, identity(baseline)),
            "processes": 6, "warmup": 10, "repeat": 100, "pairs_per_case": 30}


def _measurement_plan(plan, candidate, baseline):
    require(isinstance(plan, dict), "stage plan must be an object")
    plan = deepcopy(plan)
    require(plan.get("purpose") in {"search", "final"}, "timing purpose must be search or final")
    expected_cases = ALL_CASES if plan["purpose"] == "final" else SENTINELS + [p["case_id"] for p in candidate["probes"]]
    require(case_ids(plan.get("case_ids")) == expected_cases, "timing cases differ from frozen candidate declaration")
    plan["manifest_ref"] = identity(plan.get("manifest_ref"))
    comparisons = plan.get("comparisons")
    require(isinstance(comparisons, list) and comparisons, "comparison plans required")
    identities = []
    for item in comparisons:
        require(isinstance(item, dict), "invalid comparison")
        identities.append({key: identity(item.get(key)) for key in ("control_source_hash", "candidate_source_hash")})
    require(identities == comparison_identities(candidate, baseline), "must measure parent and original separately, merging equal controls")
    for key, value in (("processes", 6), ("warmup", 10), ("repeat", 100)):
        require(type(plan.setdefault(key, value)) is int and plan[key] == value, "unexpected protocol " + key)
    pairs = plan.setdefault("pairs_per_case", 30)
    require(type(pairs) is int and pairs >= 30 and pairs % 2 == 0, "pair count must be even and at least 30")
    return plan


def _active_stages(state):
    return [(name, stage_id) for name, task in state["tasks"].items() for stage_id, stage in task["stages"].items()
            if stage["attempts"][-1]["outcome"] is None]


def _quality_eligible(observation):
    return all(observation["quality"].get(key) is True for key in ("correctness", "runtime", "stable", "protocol_qualified"))


def _transition(state, config, operation, arguments):
    """Apply one validated transition to an isolated replay state."""
    a = deepcopy(arguments)
    require(operation in ARGUMENT_KEYS and not set(a) - ARGUMENT_KEYS[operation], "unknown transition arguments")
    if operation == "resume":
        require(state["status"] == "paused", "campaign is already active")
        nonempty(a.get("reason"), "resume reason")
        require(a.get("checkpoint_id") == state["latest_checkpoint_id"], "resume must reference the latest checkpoint")
        require(not _active_stages(state), "unresolved running stages must be explicitly closed")
        state["status"] = "active"
        return
    if operation == "checkpoint":
        cid = nonempty(a.get("checkpoint_id"), "checkpoint_id")
        require(all(c["checkpoint_id"] != cid for c in state["checkpoints"]), "duplicate checkpoint ID")
        nonempty(a.get("reason"), "checkpoint reason")
        nonempty(a.get("next_action"), "next action")
        require(a.get("resources_released") is True, "checkpoint requires explicit resource-release attestation")
        require(not _active_stages(state), "close every running stage before checkpoint")
        state["checkpoints"].append(a)
        state["latest_checkpoint_id"] = cid
        state["status"] = "paused"
        return
    name = a.get("workload")
    require(name in state["tasks"], "unknown workload")
    task, declared = state["tasks"][name], config["tasks"][name]
    baseline = declared["baseline_source_hash"]
    if operation == "register":
        require(not task["frozen"], "candidate roster is frozen")
        require(all(c["feedback_closed"] for c in task["candidates"].values()), "close candidate feedback before next proposal")
        candidate = candidate_identity({k: v for k, v in a.items() if k != "workload"}, baseline)
        cid = candidate["candidate_id"]
        require(cid not in task["candidates"], "duplicate candidate ID")
        require(all(c["source_hash"] != candidate["source_hash"] for c in task["candidates"].values()),
                "same source requires another observation, not another candidate")
        prior = task["observations"]
        require(all(ref in prior and prior[ref]["close_feedback"] for ref in candidate["decision_basis"]),
                "decision basis must reference already closed same-workload feedback")
        require(not task["candidates"] or candidate["decision_basis"], "subsequent proposal needs actual feedback basis")
        parent_id = candidate["source_parent"]["candidate_id"]
        if parent_id is not None:
            parent = task["candidates"].get(parent_id)
            require(parent is not None and parent["source_hash"] == candidate["source_parent"]["source_hash"], "parent source mismatch")
            latest = prior[parent["observation_ids"][-1]] if parent["observation_ids"] else None
            require(parent["feedback_closed"] and latest is not None and _quality_eligible(latest) and latest["epoch"] == task["epoch"],
                    "parent lacks current protocol-qualified feedback")
        require(task["used"]["source"] < declared["budgets"]["source"], "source budget exhausted")
        task["candidates"][cid] = {**candidate, "epoch": task["epoch"], "feedback_closed": False, "observation_ids": [], "inherited": False}
        task["used"]["source"] += 1
        return
    if operation == "start_stage":
        require(state["status"] == "active", "resume campaign before stage start")
        require(not _active_stages(state), "only one stage may be active on the host")
        sid = nonempty(a.get("stage_id"), "stage_id")
        kind = a.get("kind")
        require(kind in KINDS, "unknown stage kind")
        cid = a.get("candidate_id")
        candidate = task["candidates"].get(cid) if cid is not None else None
        require(cid is None or candidate is not None, "unknown candidate")
        plan = deepcopy(a.get("plan"))
        require(isinstance(plan, dict) and plan, "frozen stage plan required")
        if "source_hash" in plan and candidate is not None:
            require(identity(plan["source_hash"]) == candidate["source_hash"], "stage source differs from registered candidate")
        for dependency in plan.get("depends_on", []):
            require(dependency in task["stages"] and task["stages"][dependency]["attempts"][-1]["outcome"] == "success",
                    "stage dependency has not succeeded")
        if kind == "timing":
            require(candidate is not None, "candidate timing cannot be relabeled as a control")
            for prerequisite in ("build", "correctness"):
                preceding = [s for s in task["stages"].values() if s["candidate_id"] == cid and s["kind"] == prerequisite]
                require(preceding and preceding[-1]["attempts"][-1]["outcome"] == "success", "timing requires successful current " + prerequisite)
            plan = _measurement_plan(plan, candidate, baseline)
            if plan["purpose"] == "final":
                require(task["frozen"] and cid in task["selection"] and plan == task["final_plans"][cid], "final timing requires the exact frozen plan")
            else:
                require(not task["frozen"], "search cannot restart after full-result freeze")
        elif kind in {"control", "qualification"}:
            require(cid is None, "method stages must not hide candidate work")
            case_ids(plan.get("case_ids"))
            require(plan.get("control_type") in {"aa", "bb", "method"}, "explicit method control type required")
            source = identity(plan.get("source_hash"))
            require(source in {baseline, *(c["source_hash"] for c in task["candidates"].values())}, "method source must already be registered")
            require(not plan.get("comparisons"), "candidate comparisons must consume a timing group")
            if plan["control_type"] == "method":
                require(kind == "qualification" and bool(plan.get("question")), "method qualification needs its predeclared question")
        elif kind in {"profile", "correctness"}:
            case_ids(plan.get("case_ids"))
            if kind == "correctness":
                require(plan["case_ids"] == ALL_CASES, "correctness must cover all 20 cases")
            else:
                require(bool(plan.get("capture_window")), "profile capture window must be frozen")
                if candidate is not None and not task["frozen"]:
                    require(set(plan["case_ids"]) <= set(SENTINELS + [p["case_id"] for p in candidate["probes"]]),
                            "search profile cases must be declared sentinels/probes")
        if cid is None and kind not in {"control", "qualification"}:
            require(identity(plan.get("source_hash")) == baseline, "only the original baseline is exempt from candidate cost")
        previous = task["stages"].get(sid)
        if previous is not None:
            require(previous["kind"] == kind and previous["candidate_id"] == cid and previous["plan"] == plan,
                    "stage identity and plan are immutable")
            last = previous["attempts"][-1]
            require(last["outcome"] == "prestart_failure" and last["formal_samples"] == 0, "only zero-sample prestart infrastructure failures may recover")
            require(previous["recoveries"] == 0, "one prestart recovery per stage")
            previous["recoveries"] += 1
        else:
            previous = {"stage_id": sid, "candidate_id": cid, "kind": kind, "plan": plan, "recoveries": 0, "attempts": []}
            task["stages"][sid] = previous
        cost = "build" if kind == "build" else "timing_groups" if kind == "timing" else "profile_groups" if kind == "profile" else None
        charge = cost is not None and cid is not None and (kind == "build" or not previous["attempts"])
        if charge:
            limit = declared["budgets"][cost]
            if kind == "timing" and plan["purpose"] == "search":
                limit -= config["reserve_final_timing_groups"]
            require(task["used"][cost] < limit, cost + " budget exhausted (final evaluation is reserved)")
            task["used"][cost] += 1
        previous["attempts"].append({"outcome": None, "formal_samples": 0, "charged": cost if charge else None})
        task["stage_starts"][kind] += 1
        if candidate is not None:
            candidate["feedback_closed"] = False
        return
    if operation == "finish_stage":
        stage = task["stages"].get(a.get("stage_id"))
        require(stage is not None and stage["attempts"][-1]["outcome"] is None, "stage is not running")
        require(a.get("outcome") in OUTCOMES, "unknown stage outcome")
        samples = a.get("formal_samples", 0)
        require(type(samples) is int and samples >= 0, "invalid formal sample count")
        require(isinstance(a.get("evidence"), dict) and bool(a["evidence"]), "stage evidence required, including on failure")
        if a["outcome"] != "success":
            nonempty(a.get("reason"), "failure reason")
        if a["outcome"] == "prestart_failure":
            require(samples == 0, "prestart recovery cannot follow any formal sample")
        if stage["kind"] == "timing" and a["outcome"] == "success":
            plan = stage["plan"]
            expected = len(plan["case_ids"]) * len(plan["comparisons"]) * plan["processes"] * plan["pairs_per_case"] * 2
            require(samples == expected, "successful timing requires every planned formal sample")
        costs = a.get("actual_costs", {})
        require(isinstance(costs, dict) and all(isinstance(k, str) and type(v) is int and v >= 0 for k, v in costs.items()),
                "actual execution costs must be nonnegative integer counters")
        for key, value in costs.items():
            task["actual_costs"][key] = task["actual_costs"].get(key, 0) + value
        stage["attempts"][-1].update({k: deepcopy(v) for k, v in a.items() if k not in {"workload", "stage_id"}})
        stage["attempts"][-1]["formal_samples"] = samples
        return
    if operation == "observation":
        oid = nonempty(a.get("observation_id"), "observation_id")
        require(all(oid not in t["observations"] for t in state["tasks"].values()), "duplicate observation ID")
        candidate = task["candidates"].get(a.get("candidate_id"))
        require(candidate is not None, "unknown observation source")
        require(isinstance(a.get("feedback"), dict) and bool(a["feedback"]), "actual feedback required")
        require(type(a.get("close_feedback", True)) is bool, "close_feedback must be boolean")
        ids = a.get("stage_ids", [])
        require(isinstance(ids, list) and len(set(ids)) == len(ids), "invalid observation stage IDs")
        for sid in ids:
            require(sid in task["stages"] and task["stages"][sid]["candidate_id"] == candidate["candidate_id"]
                    and task["stages"][sid]["attempts"][-1]["outcome"] is not None, "observation requires completed same-source stages")
        quality = a.get("quality", {})
        require(isinstance(quality, dict) and set(quality) <= {"correctness", "runtime", "stable", "protocol_qualified"}
                and all(type(v) is bool for v in quality.values()), "quality fields must be explicit booleans")
        if any(quality.values()):
            identity(a.get("evidence_ref"))
        for flag, kinds in (("correctness", {"correctness"}), ("runtime", {"runtime", "correctness"}), ("stable", {"timing"})):
            relevant = [task["stages"][sid] for sid in ids if task["stages"][sid]["kind"] in kinds]
            if quality.get(flag):
                require(relevant and all(s["attempts"][-1]["outcome"] == "success" for s in relevant),
                        "quality claim requires successful referenced " + flag + " evidence")
        if a.get("close_feedback", True):
            require(not any(s["candidate_id"] == candidate["candidate_id"] and s["attempts"][-1]["outcome"] is None for s in task["stages"].values()),
                    "cannot close feedback while source stages are running")
            seen = {}
            for old_id in candidate["observation_ids"]:
                for sid, count in task["observations"][old_id]["stage_attempts"].items():
                    seen[sid] = max(seen.get(sid, 0), count)
            unobserved = {sid for sid, stage in task["stages"].items() if stage["candidate_id"] == candidate["candidate_id"]
                          and seen.get(sid, 0) < len(stage["attempts"])}
            require(unobserved <= set(ids), "feedback must retain every newly completed source stage")
        observation = {**a, "close_feedback": a.get("close_feedback", True), "quality": quality,
                       "epoch": task["epoch"], "protocol_hash": config["protocol_hash"],
                       "stage_attempts": {sid: len(task["stages"][sid]["attempts"]) for sid in ids}}
        task["observations"][oid] = observation
        candidate["observation_ids"].append(oid)
        candidate["feedback_closed"] = observation["close_feedback"]
        return
    if operation == "freeze":
        require(not task["frozen"], "candidate roster is already frozen")
        require(all(c["feedback_closed"] for c in task["candidates"].values()), "close feedback before freezing")
        selected = a.get("candidate_ids", [])
        require(isinstance(selected, list) and len(set(selected)) == len(selected) and all(cid in task["candidates"] for cid in selected), "invalid frozen selection")
        nonempty(a.get("reason"), "freeze reason")
        plans = a.get("final_plans", {})
        require(isinstance(plans, dict) and set(plans) == set(selected), "each selected source needs a final plan")
        require(len(selected) <= declared["budgets"]["timing_groups"] - task["used"]["timing_groups"], "insufficient reserved final groups")
        final_plans = {}
        for cid, plan in plans.items():
            normalized = _measurement_plan(plan, task["candidates"][cid], baseline)
            require(normalized["purpose"] == "final", "freeze requires complete 20-case final plans")
            final_plans[cid] = normalized
        roster = [{k: deepcopy(v) for k, v in candidate.items() if k not in {"feedback_closed", "observation_ids"}}
                  for candidate in task["candidates"].values()]
        task.update(frozen=True, frozen_roster={"candidates": roster, "sha256": digest(roster)}, selection=selected,
                    final_plans=final_plans, freeze_reason=a["reason"])
        return
    raise ValueError("unknown ledger operation")


def _read_json(path):
    def bad_constant(value):
        raise ValueError("nonfinite JSON value: " + value)
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "duplicate JSON object key: " + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), parse_constant=bad_constant, object_pairs_hook=unique_object)


def _write_exclusive(path, value):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(canonical(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prepare_ledger(directory, config):
    validate_config(config)
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    _write_exclusive(directory / "config.json", config)
    _write_exclusive(directory / "config.sha256.json", {"sha256": digest(config)})
    # The genesis event anchors the exact immutable configuration.
    genesis = {"sequence": 0, "event_id": "genesis", "operation": "prepare", "arguments": {},
               "recorded_at": datetime.now(timezone.utc).isoformat(), "previous_hash": ZERO_HASH, "config_hash": digest(config)}
    genesis["hash"] = digest(genesis)
    _write_exclusive(directory / "events.jsonl", genesis)
    (directory / ".lock").touch(exist_ok=False)
    (directory / "checkpoints").mkdir()
    _sync_directory(directory)
    return Ledger(directory)


class Ledger:
    """Persisted transactions; constructing, status and verify are read-only."""

    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self._load()

    def _load(self):
        config = _read_json(self.directory / "config.json")
        validate_config(config)
        config_hash = digest(config)
        require(_read_json(self.directory / "config.sha256.json") == {"sha256": config_hash}, "immutable config hash mismatch")
        content = (self.directory / "events.jsonl").read_bytes()
        require(content and content.endswith(b"\n"), "incomplete event log; recovery must not silently truncate evidence")
        events, ids, previous = [], {}, ZERO_HASH
        state = _initial_state(config)
        prefix_states = {}
        for sequence, line in enumerate(content.splitlines()):
            require(bool(line), "blank event record")
            event = json.loads(line)
            require(canonical(event) == line, "noncanonical or ambiguous event JSON")
            require(isinstance(event, dict) and set(event) == {"sequence", "event_id", "operation", "arguments", "recorded_at", "previous_hash", "config_hash", "hash"}, "invalid event schema")
            require(type(event["sequence"]) is int and event["sequence"] == sequence, "event sequence mismatch")
            require(event["previous_hash"] == previous and event["config_hash"] == config_hash, "event hash chain/config mismatch")
            require(event["hash"] == digest({k: v for k, v in event.items() if k != "hash"}), "event content hash mismatch")
            nonempty(event["event_id"], "event_id")
            nonempty(event["recorded_at"], "recorded_at")
            require(event["event_id"] not in ids, "duplicate event ID")
            require(isinstance(event["arguments"], dict), "invalid event arguments")
            if sequence == 0:
                require(event["operation"] == "prepare" and event["event_id"] == "genesis" and event["arguments"] == {}, "invalid genesis event")
            else:
                require(event["operation"] in OPERATIONS, "unknown event operation")
                _transition(state, config, event["operation"], event["arguments"])
            previous = event["hash"]
            ids[event["event_id"]] = event
            events.append(event)
            if event["operation"] == "checkpoint":
                prefix_states[sequence] = digest(state)
        sealed = set()
        for path in sorted((self.directory / "checkpoints").glob("*.json")):
            checkpoint = _read_json(path)
            seq = checkpoint.get("sequence")
            require(type(seq) is int and seq in prefix_states, "checkpoint pins a missing/truncated event prefix")
            require(checkpoint == {"schema_version": SCHEMA, "config_hash": config_hash, "sequence": seq,
                                   "head_hash": events[seq]["hash"], "state_hash": prefix_states[seq],
                                   "checkpoint_id": events[seq]["arguments"]["checkpoint_id"]}, "checkpoint seal mismatch")
            sealed.add(seq)
        self.config, self.config_hash, self.state, self.events, self.event_ids = config, config_hash, state, events, ids
        self.unsealed_checkpoints = [events[seq]["arguments"]["checkpoint_id"] for seq in prefix_states if seq not in sealed]
        return self

    def verify(self, *, expected_head=None, expected_config_hash=None):
        self._load()
        require(not self.unsealed_checkpoints, "unsealed checkpoint: retry its original checkpoint idempotency key")
        require(expected_head is None or identity(expected_head) == self.events[-1]["hash"], "externally pinned head mismatch")
        require(expected_config_hash is None or identity(expected_config_hash) == self.config_hash, "externally pinned config mismatch")
        return {"valid": True, "config_hash": self.config_hash, "head_hash": self.events[-1]["hash"],
                "event_count": len(self.events), "read_only": True}

    def status(self, *, split=None):
        self._load()
        require(split in {None, "train", "validation"}, "invalid split")
        result = deepcopy(self.state)
        result["tasks"] = {name: task for name, task in result["tasks"].items() if split is None or task["split"] == split}
        for name, task in result["tasks"].items():
            task["remaining"] = {key: cap - task["used"][key] for key, cap in self.config["tasks"][name]["budgets"].items()}
        result.update(config_hash=self.config_hash, head_hash=self.events[-1]["hash"], event_count=len(self.events),
                      execution_performed=False, historical_queue="prior_only_not_queued", unsealed_checkpoints=list(self.unsealed_checkpoints))
        return result

    def _seal_checkpoint(self, event):
        # A crash between journal fsync and seal creation is recoverable by the
        # same idempotency key. Never remove or rewrite a partially written seal.
        path = self.directory / "checkpoints" / (hashlib.sha256(event["arguments"]["checkpoint_id"].encode()).hexdigest() + ".json")
        state = _initial_state(self.config)
        for old in self.events[1:event["sequence"] + 1]:
            _transition(state, self.config, old["operation"], old["arguments"])
        value = {"schema_version": SCHEMA, "config_hash": self.config_hash, "sequence": event["sequence"],
                 "head_hash": event["hash"], "state_hash": digest(state), "checkpoint_id": event["arguments"]["checkpoint_id"]}
        if path.exists():
            require(_read_json(path) == value, "checkpoint seal already differs")
        else:
            _write_exclusive(path, value)
            _sync_directory(path.parent)

    def _commit(self, operation, *, event_id, **arguments):
        nonempty(event_id, "event_id")
        require(event_id != "genesis", "reserved event ID")
        canonical(arguments)
        with (self.directory / ".lock").open("rb") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            self._load()
            if event_id in self.event_ids:
                event = self.event_ids[event_id]
                require(event["operation"] == operation and event["arguments"] == arguments, "idempotency key reused with different arguments")
                if operation == "checkpoint":
                    self._seal_checkpoint(event)
                return deepcopy(event)
            require(not self.unsealed_checkpoints, "seal the committed checkpoint using its original idempotency key before continuing")
            updated = deepcopy(self.state)
            _transition(updated, self.config, operation, arguments)
            event = {"sequence": len(self.events), "event_id": event_id, "operation": operation, "arguments": deepcopy(arguments),
                     "recorded_at": datetime.now(timezone.utc).isoformat(), "previous_hash": self.events[-1]["hash"], "config_hash": self.config_hash}
            event["hash"] = digest(event)
            with (self.directory / "events.jsonl").open("ab") as stream:
                stream.write(canonical(event) + b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.events.append(event)
            self.event_ids[event_id] = event
            self.state = updated
            if operation == "checkpoint":
                self._seal_checkpoint(event)
            return deepcopy(event)

    def register(self, **arguments):
        return self._commit("register", **arguments)

    def start_stage(self, **arguments):
        return self._commit("start_stage", **arguments)

    def finish_stage(self, **arguments):
        return self._commit("finish_stage", **arguments)

    def observation(self, **arguments):
        return self._commit("observation", **arguments)

    def freeze(self, **arguments):
        return self._commit("freeze", **arguments)

    def checkpoint(self, **arguments):
        return self._commit("checkpoint", **arguments)

    def resume(self, **arguments):
        # Keep the initial resume concise; subsequent calls must name a seal.
        arguments.setdefault("checkpoint_id", None)
        return self._commit("resume", **arguments)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("prepare", "status", "verify", *sorted(OPERATIONS)):
        sub = commands.add_parser(command.replace("_", "-"))
        sub.add_argument("--ledger", type=Path, required=True)
        if command == "prepare":
            sub.add_argument("--config", type=Path, required=True)
        elif command not in {"status", "verify"}:
            sub.add_argument("--payload", type=Path, required=True)
        if command == "status":
            sub.add_argument("--split", choices=("train", "validation"))
        if command == "verify":
            sub.add_argument("--expected-head")
            sub.add_argument("--expected-config-hash")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        result = prepare_ledger(args.ledger, _read_json(args.config)).status()
    else:
        ledger = Ledger(args.ledger)
        if args.command == "status":
            result = ledger.status(split=args.split)
        elif args.command == "verify":
            result = ledger.verify(expected_head=args.expected_head, expected_config_hash=args.expected_config_hash)
        else:
            payload = _read_json(args.payload)
            require(isinstance(payload, dict), "payload must be an object")
            result = getattr(ledger, args.command.replace("-", "_"))(**payload)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
