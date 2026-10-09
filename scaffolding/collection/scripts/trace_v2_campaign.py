#!/usr/bin/env python3
"""CPU-only campaign bookkeeping. No executor, device discovery, or implicit start."""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import re

BUDGETS = {"source": 6, "build": 6, "timing_groups": 6, "profile_groups": 3}
SENTINELS = [1, 8, 14, 20]
_HASH = re.compile(r"(?:sha256:)?[0-9a-f]{64}\Z")
PROTOCOL = {"single_active_host": True, "warmup": 10, "repeat": 100, "pairs_per_case": 30,
            "max_cv": 0.05, "max_role_bias": 0.02, "max_drift": 0.02,
            "aa_phases": ["before", "reverse", "after"],
            "baseline_current_correctness_cases": list(range(1, 21))}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _hash(value):
    _require(isinstance(value, str) and bool(_HASH.fullmatch(value)), "expected SHA-256 identity")
    return value if value.startswith("sha256:") else "sha256:" + value


def prepare_plan(campaign_id: str, probes=()):
    probes = list(probes)
    _require(isinstance(campaign_id, str) and bool(campaign_id), "campaign_id is required")
    _require(len(probes) <= 2 and len(set(probes)) == len(probes), "at most two distinct predeclared probes")
    _require(all(type(p) is int and 1 <= p <= 20 and p not in SENTINELS for p in probes), "invalid probe case")
    return {
        "schema_version": 2, "campaign_id": campaign_id, "status": "paused",
        "execution": "requires_explicit_user_start", "workload_split": "known_workload_not_heldout",
        "sentinels": list(SENTINELS), "probes": probes, "budget_scope": "per_workload",
        "budgets": dict(BUDGETS), "protocol": deepcopy(PROTOCOL), "tasks": {
            name: {"epoch": 0, "recovery_epochs": [], "frozen": False,
                   "candidates": [], "observations": [], "comparison_groups_used": 0, "used": dict.fromkeys(BUDGETS, 0)}
            for name in ("foreach_norm", "exp")},
    }


def comparison_descriptors(candidate, original_source_hash):
    """Independent fresh measurements; equal controls share a descriptor, never samples."""
    original_source_hash = _hash(original_source_hash)
    child = candidate["source_hash"]
    parent = candidate["source_parent"]["source_hash"]
    controls = [(parent, ["child_vs_parent"])]
    if parent == original_source_hash:
        controls[0][1].append("child_vs_original")
    else:
        controls.append((original_source_hash, ["child_vs_original"]))
    return [{"comparison_id": f'{candidate["candidate_id"]}:comparison:{i}',
             "candidate_id": candidate["candidate_id"], "child_source_hash": child,
             "control_source_hash": control, "patch_hash": candidate["patch_hash"],
             "epoch": candidate["epoch"], "roles": roles,
             "sample_policy": "fresh_independent", "reuse_sample_ids": [],
             "case_ids": candidate["case_ids"], "protocol": deepcopy(PROTOCOL)}
            for i, (control, roles) in enumerate(controls)]


class Campaign:
    """Pure in-memory, transactional checkpoint transitions; observation IDs are chronological."""

    def __init__(self, plan):
        self.plan = deepcopy(plan)
        self.validate()

    def validate(self):
        p = self.plan
        _require(p.get("schema_version") == 2 and p.get("status") == "paused", "only paused v2 plans are supported")
        _require(p.get("execution") == "requires_explicit_user_start", "execution must stay explicitly gated")
        _require(p.get("workload_split") == "known_workload_not_heldout", "incorrect workload classification")
        expected = prepare_plan(p["campaign_id"], p["probes"])
        _require(p["sentinels"] == SENTINELS and p["budgets"] == BUDGETS and p.get("budget_scope") == "per_workload", "immutable campaign policy changed")
        _require(p.get("protocol") == PROTOCOL, "immutable measurement protocol changed")
        _require(set(p["tasks"]) == set(expected["tasks"]), "unexpected workload")
        # Replay all accepted transitions to validate identities, chronology and budget counters.
        for name, task in p["tasks"].items():
            replay = Campaign.__new__(Campaign)
            replay.plan = deepcopy(expected)
            for event in task.get("events", []):
                method = event["method"]
                _require(method in {"register_candidate", "close_observation", "freeze", "recover_prestart"}, "unknown checkpoint event")
                getattr(replay, method)(name, **event["arguments"])
            _require(replay.plan["tasks"][name] == task, "checkpoint state does not match validated event history")
        sample_ids = [sample for task in p["tasks"].values() for observation in task["observations"]
                      for comparison in observation["comparisons"] for sample in comparison["sample_ids"]]
        _require(len(sample_ids) == len(set(sample_ids)), "measurement samples cannot be reused across workloads")
        return True

    def _record(self, task, method, arguments):
        task.setdefault("events", []).append({"method": method, "arguments": deepcopy(arguments)})

    def register_candidate(self, workload, *, candidate_id, source_hash, patch_hash,
                           source_parent, decision_basis, original_source_hash):
        task = self.plan["tasks"][workload]
        _require(not task["frozen"], "candidate roster is frozen")
        _require(len(task["candidates"]) == len(task["observations"]), "close candidate feedback before next proposal")
        source_hash, patch_hash, original_source_hash = map(_hash, (source_hash, patch_hash, original_source_hash))
        source_parent = deepcopy(source_parent)
        source_parent["source_hash"] = _hash(source_parent.get("source_hash"))
        _require(isinstance(candidate_id, str) and bool(candidate_id) and all(c["candidate_id"] != candidate_id for c in task["candidates"]), "candidate ID must be unique")
        _require(all(c["source_hash"] != source_hash for c in task["candidates"]), "duplicate source identity")
        if task["candidates"]:
            _require(task["candidates"][0]["original_source_hash"] == original_source_hash, "original source changed")
        _require(source_hash != source_parent["source_hash"], "child must change parent source")
        _require(len(set(decision_basis)) == len(decision_basis), "duplicate decision reference")
        prior = {o["observation_id"]: o for o in task["observations"]}
        _require(all(ref in prior for ref in decision_basis), "decision references must already be closed")
        parent_id = source_parent.get("candidate_id")
        if parent_id is None:
            _require(source_parent["source_hash"] == original_source_hash, "original parent identity mismatch")
        else:
            matches = [o for o in prior.values() if o["candidate_id"] == parent_id]
            _require(len(matches) == 1, "parent must have a closed observation")
            observation = matches[0]
            parent = next(c for c in task["candidates"] if c["candidate_id"] == parent_id)
            _require(parent["source_hash"] == source_parent["source_hash"], "parent source mismatch")
            _require(observation["correct"] and observation["runtime_ok"] and observation["stable"] and observation["epoch"] == task["epoch"], "parent is ineligible")
        _require(task["used"]["source"] < BUDGETS["source"], "source budget exhausted")
        candidate = dict(candidate_id=candidate_id, source_hash=source_hash, patch_hash=patch_hash,
                         source_parent=deepcopy(source_parent), decision_basis=list(decision_basis),
                         original_source_hash=original_source_hash, epoch=task["epoch"],
                         case_ids=self.plan["sentinels"] + self.plan["probes"])
        candidate["comparisons"] = comparison_descriptors(candidate, original_source_hash)
        task["candidates"].append(candidate)
        task["used"]["source"] += 1
        self._record(task, "register_candidate", {k: deepcopy(candidate[k]) for k in (
            "candidate_id", "source_hash", "patch_hash", "source_parent", "decision_basis", "original_source_hash")})
        return deepcopy(candidate)

    def close_observation(self, workload, *, observation_id, candidate_id, correct, runtime_ok,
                          stable, diagnostics, comparisons=(), build_count=0, profile_groups=0):
        task = self.plan["tasks"][workload]
        _require(len(task["candidates"]) == len(task["observations"]) + 1, "no pending candidate")
        candidate = task["candidates"][-1]
        _require(candidate["candidate_id"] == candidate_id, "observation candidate mismatch")
        _require(isinstance(observation_id, str) and bool(observation_id) and all(o["observation_id"] != observation_id for o in task["observations"]), "observation ID must be unique")
        _require(all(type(v) is bool for v in (correct, runtime_ok, stable)), "outcomes must be booleans")
        _require(isinstance(diagnostics, dict) and bool(diagnostics), "actual normal skill diagnostics must be recorded")
        descriptors = {d["comparison_id"]: d for d in candidate["comparisons"]}
        all_samples = {s for t in self.plan["tasks"].values() for o in t["observations"]
                       for c in o["comparisons"] for s in c["sample_ids"]}
        seen = set()
        for result in comparisons:
            cid = result["comparison_id"]
            _require(cid in descriptors and cid not in seen, "unknown or repeated comparison")
            seen.add(cid)
            for key in ("candidate_id", "child_source_hash", "control_source_hash", "patch_hash", "epoch"):
                _require(result.get(key) == descriptors[cid][key], "comparison identity mismatch")
            _require(result.get("case_ids") == candidate["case_ids"] and result.get("protocol") == PROTOCOL,
                     "comparison case/protocol mismatch")
            _hash(result.get("evidence_report_ref"))
            _hash(result.get("child_binary_hash"))
            _hash(result.get("control_binary_hash"))
            inputs = result.get("input_hashes", {})
            _require(set(inputs) == {str(case) for case in candidate["case_ids"]}, "input identity coverage mismatch")
            for identity in inputs.values():
                _hash(identity)
            quality = result.get("quality", {})
            _require(quality.get("scope") == "externally_attested_current_epoch",
                     "explicit externally attested quality scope required")
            _require(quality.get("baseline_current_correctness_cases") == PROTOCOL["baseline_current_correctness_cases"]
                     and quality.get("baseline_current_correctness_passed") is True,
                     "current baseline correctness coverage required")
            aa = quality.get("aa", {})
            _require(set(aa) == set(PROTOCOL["aa_phases"]), "current control AA proof required")
            for phase in aa.values():
                _require(phase.get("control_source_hash") == descriptors[cid]["control_source_hash"]
                         and phase.get("epoch") == task["epoch"]
                         and phase.get("control_binary_hash") == result["control_binary_hash"], "AA identity mismatch")
                _hash(phase.get("evidence_report_ref"))
                for metric, limit in (("cv", 0.05), ("role_bias", 0.02), ("drift", 0.02)):
                    value = phase.get(metric)
                    _require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                             "invalid AA metric")
                    _require(not stable or value <= limit, "stable claim contradicts AA quality")
            _require(result.get("pairs_per_case") == 30, "thirty pairs per case required")
            samples = result["sample_ids"]
            _require(len(samples) == len(candidate["case_ids"]) * 30 * 2, "sample count does not match cases and pairs")
            _require(bool(samples) and all(isinstance(s, str) and s for s in samples), "sample identities required")
            _require(len(set(samples)) == len(samples) and not all_samples.intersection(samples), "measurement samples cannot be reused")
            all_samples.update(samples)
        _require(not (correct and runtime_ok and stable) or seen == set(descriptors), "eligible observation requires both comparator roles")
        costs = {"build": build_count, "profile_groups": profile_groups, "timing_groups": int(bool(comparisons))}
        _require(all(type(n) is int and n >= 0 and task["used"][key] + n <= BUDGETS[key] for key, n in costs.items()), "invalid cost or budget exhausted")
        arguments = dict(observation_id=observation_id, candidate_id=candidate_id, correct=correct,
                         runtime_ok=runtime_ok, stable=stable, diagnostics=deepcopy(diagnostics),
                         comparisons=deepcopy(list(comparisons)), build_count=build_count, profile_groups=profile_groups)
        task["observations"].append({**arguments, "epoch": task["epoch"]})
        task["comparison_groups_used"] += len(comparisons)
        for key, n in costs.items():
            task["used"][key] += n
        self._record(task, "close_observation", arguments)

    def freeze(self, workload, *, reason=""):
        task = self.plan["tasks"][workload]
        _require(not task["frozen"] and len(task["candidates"]) == len(task["observations"]), "close feedback before freezing once")
        _require(task["candidates"] or bool(reason), "empty frozen roster requires a blocked reason")
        task["frozen"] = True
        task["freeze_reason"] = reason
        self._record(task, "freeze", {"reason": reason})

    def recover_prestart(self, workload, *, epoch, reason):
        task = self.plan["tasks"][workload]
        _require(epoch == task["epoch"] and epoch not in task["recovery_epochs"], "one infrastructure recovery per epoch")
        _require(not task["candidates"] and not task["frozen"], "only infrastructure prestart recovery; stability retries forbidden")
        _require(bool(reason), "infrastructure failure reason required")
        task["recovery_epochs"].append(epoch)
        self._record(task, "recover_prestart", {"epoch": epoch, "reason": reason})

    def dry_run(self):
        self.validate()
        return {"status": "paused", "execution_permitted": False, "tasks": {
            name: {"cases": self.plan["sentinels"] + self.plan["probes"],
                   "remaining_budget": {k: BUDGETS[k] - task["used"][k] for k in BUDGETS},
                   "comparisons": [deepcopy(d) for c in task["candidates"] for d in c["comparisons"]]}
            for name, task in self.plan["tasks"].items()}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--skill-lib", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    prepare.add_argument("--campaign-id", required=True)
    prepare.add_argument("--probe", type=int, action="append", default=[])
    dry = commands.add_parser("dry-run")
    dry.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "prepare":
        from aprof_layout import identity
        plan = prepare_plan(args.campaign_id, args.probe)
        plan["skill_library"] = identity(args.skill_lib)
        with args.output.open("x") as stream:
            json.dump(plan, stream, indent=2)
            stream.write("\n")
    else:
        print(json.dumps(Campaign(json.loads(args.manifest.read_text())).dry_run(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
