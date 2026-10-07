#!/usr/bin/env python3
"""CPU-only bridge from shared-context ledger/method evidence to isolated v2 views.

Archive reads completed artifacts and writes only a new export directory. It never
imports a hardware supervisor or a runtime store. Method failures remain task
checkpoints; only ledger-registered changed sources become optimization memories.
Inherited sources retain their original run/attempt identity.

Optional method-index JSON: {"methods": [{"operator": "foreach_norm", "split":
"train", "directory": "method/foreach_norm/qualification", "evidence":
[{"path": "...", "sha256": "sha256:..."}]}]}. Paths resolve against RUN.
Normal task qualification directories and closure.json are discovered directly.
Use kind="positive_comparison" for a regular method contrast. foreach_norm's
qualification and positive-comparison directories are independently discovered.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import math
import os
import re
from pathlib import Path

import feedback_trace_export as export
import shared_context_campaign as campaign
import shared_context_report as statistics
import trace_v2_dataset as v2


VERSION = "shared_context_archive_v1"
TEXT_SUFFIXES = {".json", ".jsonl", ".csv", ".log", ".txt", ".md", ".py", ".patch"}


class FrozenRecorder(export.Recorder):
    """Freeze/read each evidence file once, then reuse validated selectors."""
    def __init__(self, manifest, output):
        super().__init__(manifest, output)
        self.frozen_paths = {}
        self.selected_refs = {}

    def pointer(self, pointer, split="train", purpose="shared-context evidence"):
        path = (self.manifest.parent / pointer["path"]).resolve()
        key = (str(path), split)
        if key not in self.frozen_paths:
            self.frozen_paths[key] = super().pointer({**pointer, "selector": ""}, split, purpose)
        base = self.evidence.entries[self.frozen_paths[key]]
        require(pointer.get("sha256", base["sha256"]) == base["sha256"], "evidence hash mismatch: " + str(path))
        selector = pointer.get("selector", "")
        selected = (*key, selector)
        if selected not in self.selected_refs:
            # Empty selectors bind the entire file by hash. Large tar/binary
            # payloads must not enter the metadata bytes cache merely to reuse
            # their already verified identity.
            if selector:
                data = self.evidence.read(base["path"])
                v2.validate_selector(selector, Path(base["path"]), data)
            ref = self.evidence._entry(base["sha256"], base["path"], base["size_bytes"], split, selector, purpose)
            self.origins.setdefault(ref, set()).add(str(path))
            self.selected_refs[selected] = ref
        return self.selected_refs[selected]


def load(path):
    return v2.strict_loads(Path(path).read_bytes())


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = v2.canonical(value)
    if path.exists():
        require(path.read_bytes() == data, "immutable archive document differs: " + str(path))
    else:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    return path


def repair_bootstrap_probes(run, draft):
    """Supersede a bootstrap/CPU-only ledger, preserving every old byte and ID.

    This is an explicit bounded metadata correction, not a general config reset.
    Any hardware stage or changed source roster forbids this narrow correction.
    """
    run, draft = Path(run).resolve(), Path(draft).resolve()
    audit = run / "bootstrap" / "exp001-probe-correction.json"
    old_path = run / "bootstrap" / "ledger-before-exp001-probe-correction"
    if audit.exists():
        value = load(audit)
        require(value["draft_sha256"] == file_hash(draft), "probe correction source changed")
        campaign.Ledger(old_path).verify(expected_head=value["old_head_hash"])
        current = campaign.Ledger(run / "ledger")
        current.verify(expected_config_hash=value["new_config_hash"])
        require(current.config["tasks"]["exp"]["inherited_candidates"][0]["probes"] == value["after"], "corrected probes changed")
        return value
    proposal = load(draft)
    require(proposal.get("id") == "exp-c01-coalesce-tile-8192" and proposal.get("cases") == [1, 8, 14, 20, 3, 9],
            "unexpected inherited exp proposal")
    parameters = proposal.get("intervention", {}).get("parameters", {})
    require(parameters == {"baseline_tile_elements": 4096, "candidate_tile_elements": 8192}, "proposal mechanism differs")
    require(all(token in proposal.get("rationale", "") for token in ("cases3/9", "0.5170/0.5298", "8036/8152", "BF16")),
            "original BF16 transfer/setup rationale is not available")
    ledger_path = run / "ledger"
    with (ledger_path / ".lock").open("rb") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        old = campaign.Ledger(ledger_path)
        old.verify()
        require(all(e["operation"] in {"prepare", "resume", "start_stage", "finish_stage", "observation"} for e in old.events),
                "probe correction cannot follow source roster or checkpoint changes")
        require(all(stage["kind"] in {"static", "build"} for task in old.state["tasks"].values() for stage in task["stages"].values()),
                "hardware stage history already exists")
        config = deepcopy(old.config)
        candidate = config["tasks"]["exp"]["inherited_candidates"][0]
        before = deepcopy(candidate["probes"])
        require([p["case_id"] for p in before] == [3, 9], "inherited probe cases differ")
        after = [
            {"case_id": 3, "reason": "Inherited BF16 transfer/setup probe for 4096-to-8192 tile coalescing: original case3 profile reported MTE2 ratio 0.5170 and 8036 useful bytes per instruction; startup-window limitations remain."},
            {"case_id": 9, "reason": "Inherited BF16 transfer/setup probe for 4096-to-8192 tile coalescing: original case9 profile reported MTE2 ratio 0.5298 and 8152 useful bytes per instruction; startup-window limitations remain."},
        ]
        candidate["probes"] = after
        proof = {"old_config_hash": old.config_hash, "old_head_hash": old.events[-1]["hash"],
                 "old_ledger": str(old_path), "draft": str(draft), "draft_sha256": file_hash(draft),
                 "replayed_events": [{"event_id": e["event_id"], "original_hash": e["hash"], "original_recorded_at": e["recorded_at"]} for e in old.events[1:]],
                 "replay_semantics": "Metadata migration re-records existing transitions; actual execution times remain in the preserved predecessor and command evidence.",
                 "changed_fields": ["tasks.exp.inherited_candidates[0].probes[0].reason", "tasks.exp.inherited_candidates[0].probes[1].reason"]}
        config["provenance"]["bootstrap_probe_correction"] = proof
        staging = run / ".ledger-probe-correction-staging"
        require(not staging.exists() and not old_path.exists(), "incomplete correction artifacts require explicit review")
        new = campaign.prepare_ledger(staging, config)
        for event in old.events[1:]:
            new._commit(event["operation"], event_id=event["event_id"], **event["arguments"])
        old_counts = {n: t["used"] for n, t in old.state["tasks"].items()}
        require(old_counts == {n: t["used"] for n, t in new.state["tasks"].items()}, "correction must preserve every budget counter")
        for n in campaign.WORKLOADS:
            prior, current = deepcopy(old.state["tasks"][n]), deepcopy(new.state["tasks"][n])
            if n == "exp":
                prior["candidates"]["exp001"]["probes"] = after
            require(prior == current, "correction changed source identity or task history")
        # Preserve the lock inode across the directory swap, including waiters.
        (staging / ".lock").unlink()
        os.link(ledger_path / ".lock", staging / ".lock")
        old_path.parent.mkdir(parents=True, exist_ok=True)
        ledger_path.rename(old_path)
        try:
            staging.rename(ledger_path)
        except BaseException:
            old_path.rename(ledger_path)
            raise
        campaign._sync_directory(run)
        campaign._sync_directory(old_path.parent)
        value = {"schema_version": VERSION, "kind": "bootstrap_metadata_correction", "recorded_at": datetime.now(timezone.utc).isoformat(),
                 **proof, "new_config_hash": new.config_hash, "new_head_hash": new.events[-1]["hash"],
                 "before": before, "after": after, "candidate_id": "exp001", "source_hash": candidate["source_hash"],
                 "patch_hash": candidate["patch_hash"], "source_parent": candidate["source_parent"],
                 "costs_unchanged": old_counts, "stage_history_at_correction": {n: list(t["stages"]) for n, t in old.state["tasks"].items()}, "new_source_charge": False,
                 "reason": "Correct copied probe prose to the original BF16 transfer/setup hypothesis; exp has no p attribute. Original bootstrap events remain in the audited predecessor."}
        _exclusive_json(audit, value)
        campaign._sync_directory(audit.parent)
        return value


def _split_for(operator):
    return "validation" if operator == "gelu" else "train"


def _safe_path(path, split, *, owner=None):
    original = Path(path).absolute()
    resolved = original.resolve()
    location = str(resolved) + (" (from " + str(original) + ")" if original != resolved else "")

    def check(condition, message):
        require(condition, message + ": " + location)

    check(split in {"train", "validation"}, "unknown evidence split")
    opposite = "validation" if split == "train" else "train"

    def inspect(parts):
        anchors = [(i, parts[i + 1]) for i, part in enumerate(parts[:-1])
                   if (part == "tasks" and parts[i + 1] in (*campaign.WORKLOADS, "foreach_norm"))
                   or (part == "method" and parts[i + 1] == "foreach_norm")]
        for _, operator in anchors:
            check(_split_for(operator) == split, "cross-split task/method evidence")
            check(owner is None or operator == owner, "cross-task evidence owner mismatch")
        check(not anchors or all(operator == anchors[0][1] for _, operator in anchors), "cross-task nested evidence owners")
        # A declared task owns its oracle validation/ subdirectories. Tokens
        # before that owner still describe an enclosing split and cannot be
        # neutralized by appending tasks/exp to a validation-root path.
        prefix = parts[:anchors[0][0]] if anchors else parts
        check(opposite not in prefix, "cross-split evidence directory before owner")
        if anchors:
            for i in range(anchors[0][0] + 2, len(parts)):
                if parts[i] == opposite:
                    explicit_root = parts[i - 1] in {"archive", "dataset", "datasets", "export", "exports", "v2"}
                    explicit_root = explicit_root or i >= 2 and parts[i - 2] == "revisions"
                    check(not explicit_root, "cross-split nested dataset root")
        return anchors[0][1] if anchors else None

    lexical_owner = inspect(original.parts)
    resolved_owner = inspect(resolved.parts)
    check(lexical_owner is None or resolved_owner is None or lexical_owner == resolved_owner,
          "cross-task symlink evidence owner mismatch")
    check("ledger" not in resolved.parts, "global ledger bytes must not enter a split evidence closure")
    check(resolved.name not in {"run-manifest.json", "config.sha256.json"}, "global coordinator manifest must be projected before export")
    return resolved


ANALYSIS_VERSION = "shared_context_candidate_analysis_v1"
FACT_FIELDS = {"statement", "basis", "case_ids", "metrics", "parameters", "conditions", "limitations", "evidence"}


def validate_candidate_analysis(path, run, operator, candidate_id, *, max_evidence_bytes=None):
    """Read-only bounded analysis validation; never opens source tar or binaries."""
    run, path = Path(run).resolve(), Path(path).resolve()
    ledger = campaign.Ledger(run / "ledger")
    require(operator in ledger.state["tasks"] and candidate_id in ledger.state["tasks"][operator]["candidates"], "analysis requires a registered source")
    candidate = ledger.state["tasks"][operator]["candidates"][candidate_id]
    value = load(path)
    required = {"schema_version", "candidate_id", "source_hash", "retrospective", "evidence", "diagnosis", "intervention"}
    require(isinstance(value, dict) and required <= set(value) <= required | {"lessons", "read_audits"}, "unknown/missing candidate analysis fields")
    require(value["schema_version"] == ANALYSIS_VERSION and value["retrospective"] is True, "candidate analysis must be explicitly retrospective")
    require(value["candidate_id"] == candidate_id and value["source_hash"] == candidate["source_hash"], "analysis source identity differs from ledger")
    refs = value["evidence"]
    require(isinstance(refs, dict) and refs, "analysis evidence aliases required")
    selected = {}
    for alias, pointer in refs.items():
        require(isinstance(alias, str) and re.fullmatch(r"[A-Za-z0-9_-]+", alias), "invalid analysis evidence alias")
        require(isinstance(pointer, dict) and {"path", "sha256"} <= set(pointer) <= {"path", "sha256", "selector"}, "analysis evidence requires path/hash and optional selector")
        target = Path(pointer["path"])
        target = _safe_path(target if target.is_absolute() else run / target, _split_for(operator), owner=operator)
        require(target.is_file(), "missing analysis evidence: " + str(target))
        if max_evidence_bytes is not None:
            require(target.stat().st_size <= max_evidence_bytes, "analysis evidence exceeds bounded validator limit: " + str(target))
        data = target.read_bytes()
        require(v2.digest_bytes(data) == campaign.identity(pointer["sha256"]), "analysis evidence hash mismatch: " + alias)
        selector = pointer.get("selector", "")
        v2.validate_selector(selector, target, data)
        selected[alias] = (target, data, selector)

    def aliases(items):
        require(isinstance(items, list) and items and len(set(items)) == len(items) and all(isinstance(k, str) and k in refs for k in items), "fact evidence must name nonempty known aliases")

    def strings(items, label):
        require(isinstance(items, list) and all(isinstance(x, str) and x for x in items), "invalid " + label)

    def fact(item, claim=False):
        require(isinstance(item, dict) and {"statement", "basis", "evidence"} <= set(item) <= FACT_FIELDS | ({"status"} if claim else set()), "unknown/missing analysis fact fields")
        require(isinstance(item["statement"], str) and item["statement"] and item["basis"] == "retrospective_current_evidence", "analysis facts must use retrospective_current_evidence")
        aliases(item["evidence"])
        cases = item.get("case_ids", [])
        require(isinstance(cases, list) and len(set(cases)) == len(cases) and all(type(c) is int and 1 <= c <= 20 for c in cases), "invalid analysis fact cases")
        for key in ("metrics", "parameters", "conditions"):
            require(key not in item or isinstance(item[key], dict), "analysis " + key + " must be an object")
        strings(item.get("limitations", []), "fact limitations")
        if claim:
            require(item.get("status") in {"supported", "refuted", "inconclusive"}, "analysis claim requires explicit supported/refuted/inconclusive status")

    def diagnosis(item):
        require(isinstance(item, dict) and set(item) == {"symptoms", "hypotheses", "missing_evidence"}, "diagnosis requires symptoms/hypotheses/missing_evidence")
        for key in ("symptoms", "hypotheses"):
            require(isinstance(item[key], list), "diagnosis facts must be arrays")
            for item_fact in item[key]:
                fact(item_fact)
        strings(item["missing_evidence"], "missing evidence")

    def intervention(item):
        fact(item)
        require(any(campaign.identity(refs[alias]["sha256"]) == candidate["patch_hash"] and not refs[alias].get("selector") for alias in item["evidence"]), "intervention must bind the exact optimization patch")

    diagnosis(value["diagnosis"])
    intervention(value["intervention"])
    lessons = value.get("lessons", [])
    require(isinstance(lessons, list), "lessons must be an array")
    seen = set()
    for lesson in lessons:
        required_lesson = {"id", "kind", "title", "claims", "evidence"}
        optional = {"diagnosis", "intervention", "effective_conditions", "ineffective_conditions", "counterexamples", "limitations", "next_questions"}
        require(isinstance(lesson, dict) and required_lesson <= set(lesson) <= required_lesson | optional, "unknown/missing analysis lesson fields")
        require(isinstance(lesson["id"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", lesson["id"]) and lesson["id"] not in seen, "invalid/duplicate local lesson id")
        seen.add(lesson["id"])
        require(lesson["kind"] == "operator_optimization" and isinstance(lesson["title"], str) and lesson["title"], "analysis lesson must describe operator optimization")
        aliases(lesson["evidence"])
        require(any(campaign.identity(refs[a]["sha256"]) != candidate["patch_hash"] for a in lesson["evidence"]), "operator lesson requires measured/recorded evidence beyond its patch")
        diagnosis(lesson.get("diagnosis", value["diagnosis"]))
        intervention(lesson.get("intervention", value["intervention"]))
        require(isinstance(lesson["claims"], list) and lesson["claims"], "empty operator lessons are not accepted")
        for claim in lesson["claims"]:
            fact(claim, claim=True)
        for key in ("effective_conditions", "ineffective_conditions", "counterexamples"):
            require(isinstance(lesson.get(key, []), list), "lesson conditions must be arrays")
            for item in lesson.get(key, []):
                fact(item)
        for key in ("limitations", "next_questions"):
            strings(lesson.get(key, []), key)

    def selected_json(alias):
        target, data, selector = selected[alias]
        row = v2.strict_loads(data)
        # Read audits deliberately require an object JSON pointer, not a JSONL
        # line selector: the original complete audit remains external evidence.
        require(not selector or selector.startswith("/"), "read audit selector must be an object JSON pointer")
        for part in selector.split("/")[1:]:
            part = part.replace("~1", "/").replace("~0", "~")
            row = row[int(part)] if isinstance(row, list) else row[part]
        return row

    audits = value.get("read_audits", [])
    require(isinstance(audits, list), "read_audits must be an array")
    for audit in audits:
        require(isinstance(audit, dict) and set(audit) == {"record", "temporal_scope", "used_for_current_judgment"}, "read audit needs record/scope/selected knowledge")
        aliases([audit["record"]])
        scope = audit["temporal_scope"]
        require(scope in {"current_pre_execution_review", "post_execution_analysis"}, "unknown knowledge audit temporal scope")
        row = selected_json(audit["record"])
        require(isinstance(row, dict) and row.get("operator") == operator and row.get("candidate_id") == candidate_id and isinstance(row.get("actual_reads"), list), "knowledge audit must explicitly record current same-source actual_reads")
        timestamp = row.get("created_at", row.get("recorded_at"))
        require(isinstance(timestamp, str), "knowledge audit requires its actual timestamp")
        at = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        require(at.tzinfo is not None, "knowledge audit timestamp must include timezone")
        started = datetime.fromisoformat(ledger.events[0]["recorded_at"].replace("Z", "+00:00"))
        correction = ledger.config.get("provenance", {}).get("bootstrap_probe_correction")
        if correction:
            predecessor = campaign.Ledger(correction["old_ledger"])
            predecessor.verify(expected_head=correction["old_head_hash"])
            started = min(started, datetime.fromisoformat(predecessor.events[0]["recorded_at"].replace("Z", "+00:00")))
        require(at >= started, "historical reads cannot be relabeled as current campaign reads")
        if scope == "current_pre_execution_review":
            require(row.get("kind") == "agent_initial_static_review", "pre-execution read audit must be the recorded initial static review")
            hardware = [e for e in ledger.events if e["operation"] == "start_stage" and e["arguments"].get("workload") == operator
                        and e["arguments"].get("candidate_id") == candidate_id and e["arguments"].get("kind") in {"correctness", "runtime", "timing", "profile"}]
            require(not hardware or at <= min(datetime.fromisoformat(e["recorded_at"].replace("Z", "+00:00")) for e in hardware), "initial read audit postdates candidate hardware execution")
        chosen = audit["used_for_current_judgment"]
        require(isinstance(chosen, list) and len(set(chosen)) == len(chosen) and len(chosen) <= 5, "select at most five knowledge items; keep complete reads in the external audit")
        for alias in chosen:
            aliases([alias])
            target = selected[alias][0]
            require(any(isinstance(item, dict) and Path(item.get("path", "")).resolve() == target and
                        campaign.identity(item.get("sha256")) == campaign.identity(refs[alias]["sha256"]) for item in row["actual_reads"]), "selected knowledge item was not recorded in this read audit")
    return value


class Bridge:
    def __init__(self, run, output=None, method_index=None):
        self.run = Path(run).resolve()
        self.output = Path(output or self.run / "archive").resolve()
        require(self.output != self.run and self.run not in self.output.parents or self.output.is_relative_to(self.run / "archive"),
                "in-run export must stay inside RUN/archive")
        self.ledger = campaign.Ledger(self.run / "ledger")
        self.ledger.verify()
        require(not campaign._active_stages(self.ledger.state), "archive only after active stages have finished or explicitly failed")
        self.index = load(method_index) if method_index else {"methods": []}
        require(isinstance(self.index, dict) and set(self.index) <= {"methods"}, "invalid method index")
        self.pointer_cache = {}

    def pointer(self, path, split, *, expected=None, selector=None):
        path = _safe_path(path, split)
        if expected is not None and path.suffix == ".py" and not path.is_file():
            frozen = v2.object_path(self.output / split / "v2" / "external_evidence", campaign.identity(expected))
            if frozen.is_file():
                return self.pointer(frozen, split, expected=expected, selector=selector)
        key = (path, split)
        if key not in self.pointer_cache:
            self.pointer_cache[key] = {"path": str(path), "sha256": file_hash(path)}
        pointer = deepcopy(self.pointer_cache[key])
        if expected is not None and campaign.identity(expected) != pointer["sha256"] and path.suffix == ".py":
            # A producer may have advanced since an earlier export. Reuse the
            # already frozen bytes, never substitute today's source for them.
            frozen = v2.object_path(self.output / split / "v2" / "external_evidence", campaign.identity(expected))
            if frozen.is_file():
                return self.pointer(frozen, split, expected=expected, selector=selector)
        require(expected is None or campaign.identity(expected) == pointer["sha256"], "source/artifact identity mismatch: " + str(path))
        if selector:
            pointer["selector"] = selector
        return pointer

    def document(self, split, label, value):
        path = self.output / "inputs" / split / label / (v2.digest(value)[7:] + ".json")
        _exclusive_json(path, value)
        return self.pointer(path, split)

    def _files(self, directory, split):
        directory = _safe_path(directory, split)
        if not directory.is_dir():
            return []
        # Explicit text/raw journals only; do not hash potentially enormous live
        # binaries, device outputs, build trees or regenerated input tensors.
        return [self.pointer(p, split) for p in sorted(directory.rglob("*"))
                if p.is_file() and p.suffix in TEXT_SUFFIXES and not {"build", "CMakeFiles", "__pycache__"}.intersection(p.relative_to(directory).parts)]

    def _build_artifacts(self, path, split):
        path = Path(path)
        if not path.is_file():
            return []
        build = load(path)
        refs = [self.pointer(path, split)]
        for role in build.get("roles", {}).values():
            if "binary" in role:
                refs.append(self.pointer(role["binary"], split, expected=role["binary_sha256"]))
        runner = build.get("runner")
        if isinstance(runner, dict) and runner.get("path"):
            refs.append(self.pointer(runner["path"], split, expected=runner["sha256"]))
        elif isinstance(runner, str):
            refs.append(self.pointer(runner, split, expected=build["runner_hash"]))
        return refs

    def _analysis(self, path, operator, candidate_id, split):
        raw = validate_candidate_analysis(path, self.run, operator, candidate_id)
        aliases = {key: self._evidence_paths([value], split, owner=operator)[0] for key, value in raw["evidence"].items()}

        def expand(value):
            if isinstance(value, list):
                return [expand(item) for item in value]
            if isinstance(value, dict):
                return {key: [aliases[a] for a in item] if key == "evidence" else expand(item) for key, item in value.items()}
            return value

        diagnosis = expand(raw["diagnosis"])
        diagnosis["retrospective"] = True
        intervention = expand(raw["intervention"])
        lessons = []
        for item in raw.get("lessons", []):
            lesson = expand(item)
            lesson.update(id=f"{self.ledger.config['campaign_id']}/{split}/operator/{operator}/{candidate_id}/{item['id']}",
                          operator=operator, split=split, source_attempt_ids=[candidate_id], graph_links=[])
            lesson.setdefault("diagnosis", deepcopy(diagnosis))
            lesson.setdefault("intervention", deepcopy(intervention))
            lessons.append(lesson)
        reads, read_summaries = [], []
        for audit in raw.get("read_audits", []):
            pointer = aliases[audit["record"]]
            row = load(pointer["path"])
            for part in pointer.get("selector", "").split("/")[1:]:
                part = part.replace("~1", "/").replace("~0", "~")
                row = row[int(part)] if isinstance(row, list) else row[part]
            names = [Path(aliases[a]["path"]).parent.name + "/" + Path(aliases[a]["path"]).name for a in audit["used_for_current_judgment"]]
            summary = {"temporal_scope": audit["temporal_scope"], "recorded_at": row.get("created_at", row.get("recorded_at")),
                       "audit_kind": row.get("kind"), "selected_knowledge": names,
                       "actual_read_count_in_external_audit": len(row["actual_reads"]),
                       "purpose": audit["temporal_scope"] + ": recorded current agent read audit; selected knowledge: " + (", ".join(names) or "none attributed here"),
                       "audit": pointer, "attribution": "Retrospective projection of the original read audit; not historical optimizer proposal knowledge."}
            summary_ref = self.document(split, operator + "-read-audit-summary", summary)
            reads.append({"record": summary_ref})
            read_summaries.append(summary)
        return {"diagnosis": diagnosis, "intervention": intervention, "lessons": lessons,
                "actual_reads": reads, "read_audits": read_summaries,
                "evidence": [self.pointer(path, split), *aliases.values()]}

    def _evidence_paths(self, value, split, *, owner=None):
        result = []
        if isinstance(value, list):
            for item in value:
                result.extend(self._evidence_paths(item, split, owner=owner))
        elif isinstance(value, dict):
            if isinstance(value.get("path"), str):
                path = Path(value["path"])
                path = path if path.is_absolute() else self.run / path
                _safe_path(path, split, owner=owner)
                result.append(self.pointer(path, split, expected=value.get("sha256"), selector=value.get("selector")))
            else:
                for key, item in value.items():
                    if isinstance(key, str) and isinstance(item, str) and item.startswith("sha256:") and (Path(key).is_absolute() or "/" in key):
                        path = Path(key)
                        path = path if path.is_absolute() else self.run / path
                        _safe_path(path, split, owner=owner)
                        result.append(self.pointer(path, split, expected=item))
                    else:
                        result.extend(self._evidence_paths(item, split, owner=owner))
        return result

    def _producer_evidence(self, record, directory, split):
        """Resolve historical code by its recorded hash, including prior exports."""
        resolved, unavailable = [], []
        for original, value in record.get("producers", {}).items():
            expected = value.get("sha256") if isinstance(value, dict) else value
            expected = campaign.identity(expected)
            original = Path(original)
            paths = []
            if isinstance(value, dict) and value.get("snapshot"):
                paths.append(Path(value["snapshot"]))
            paths.extend([directory / "producers" / original.name,
                          v2.object_path(self.output / split / "v2" / "external_evidence", expected)])
            paths.extend(sorted((self.run / "bootstrap").glob("**/" + original.name)))
            # Coordinators sometimes preserve an old helper under a versioned
            # filename. Match the bytes, not just the live basename.
            paths.extend(sorted((self.run / "bootstrap").glob("**/*.py")))
            paths.append(original)
            for path in paths:
                if not path.is_absolute():
                    path = self.run / path
                if not path.is_file():
                    continue
                pointer = self.pointer(path, split)
                if pointer["sha256"] == expected:
                    binding = {"original_path": str(original), "recorded_hash": expected, "snapshot": pointer,
                               "preexecution_freeze_established_by_archive": False}
                    if path.is_relative_to(self.run / "bootstrap"):
                        for metadata in sorted(path.parent.glob("*.json")):
                            try:
                                preservation = load(metadata)
                            except (OSError, ValueError):
                                continue
                            files = preservation.get("files", {}) if isinstance(preservation, dict) else {}
                            if isinstance(files, dict) and files.get(str(path)) == expected and preservation.get("old_helper_preservation"):
                                binding["preservation"] = {"note": preservation["old_helper_preservation"],
                                    "recorded_at": preservation.get("recorded_at"), "record_path": str(metadata),
                                    "record_hash": file_hash(metadata)}
                                break
                    resolved.append(binding)
                    break
            else:
                unavailable.append({"original_path": str(original), "recorded_hash": expected,
                                    "reason": "Recorded producer bytes are unavailable; current source is not substituted."})
        return {"resolved": resolved, "producer_snapshot_unavailable": unavailable}, [r["snapshot"] for r in resolved]

    def _prestart(self, record):
        costs = record.get("actual_costs", {})
        return (record.get("ledger_stage_started") is False and
                type(costs.get("native_sessions_attempted")) is int and costs["native_sessions_attempted"] == 0 and
                record.get("formal_samples", 0) == 0 and
                all(costs.get(key, 0) == 0 for key in ("native_sessions_started", "native_sessions_completed", "native_complete_calls", "event_samples",
                    "warmup_complete_calls", "native_kernel_launches_submitted", "profile_launches_captured", "diagnostic_cases_completed")))

    def _method(self, operator, directory, split):
        evidence = self._files(directory, split)
        evidence.extend(self._build_artifacts(directory.parent / "aa-build/build_manifest.json", split))
        for subdir in ("qualification-execution", "aa-build-execution"):
            evidence.extend(self._files(directory.parent / subdir, split))
        for name in ("build_manifest.json", "A.harness.patch", "B.harness.patch"):
            path = directory.parent / "aa-build" / name
            if path.is_file():
                evidence.append(self.pointer(path, split))
        state = {"operator": operator, "split": split, "directory": str(directory), "status": "not_started",
                 "formal_admission": "not_evaluated", "graph_policy_eligible": False, "episode_ref": None,
                 "evidence": evidence, "native_bundle_replay": "external_supervisor_only_not_performed_by_archive"}
        report_path = directory / "report.json"
        if report_path.exists():
            require((directory / "manifest.json").is_file() and (directory / "sessions.json").is_file(),
                    "method report is missing its frozen manifest/raw sessions")
            manifest, sessions, report = (load(directory / name) for name in ("manifest.json", "sessions.json", "report.json"))
            require(manifest["task_id"] == operator and manifest["stages"] == ["qualification"], "foreign/nonqualification method report")
            require(manifest["run_id"] == self.ledger.config["campaign_id"], "method report belongs to a different collection run")
            statistics.verify_report(manifest, sessions, report)
            quality = report["measurement_quality"]
            state.update(status="qualified" if quality["observed_checks_pass"] else "blocked", report_recomputed=True,
                         measurement_quality=quality, case_attributes=report["case_attributes"],
                         qualification=report["qualification"], limitations=report["limitations"],
                         cv_by_cell=[{**{k: cell[k] for k in ("case_id", "session_id", "block_id", "load_order", "buffer_config")},
                                      "A_cv": cell["A"]["cv"], "B_cv": cell["B"]["cv"]} for cell in report["cells"]])
        elif (directory / "collection-completion.json").is_file():
            completion = load(directory / "collection-completion.json")
            state.update(status="incomplete", completion=completion,
                         reason="No complete verified qualification report; retain actual collection completion/failure.")
        elif evidence:
            state.update(status="prepared_not_qualified", reason="Only preparation/partial evidence exists; qualification has not been established.")
        result_path = directory.parent / "qualification-result.json"
        if result_path.is_file():
            result = load(result_path)
            evidence.append(self.pointer(result_path, split))
            evidence.extend(self._evidence_paths(result.get("evidence", []), split, owner=operator))
            state["recorded_qualification_result"] = result
            producers, refs = self._producer_evidence(result, directory, split)
            state["producer_binding"] = producers
            evidence.extend(refs)
            if not report_path.exists():
                state.update(status="blocked" if result.get("status") in {"blocked", "failed", "incomplete"} else "unverified_result_without_report",
                             reason=result.get("error") or result.get("reason") or "No complete replayable qualification report.")
        preparation_failures = []
        for path in sorted({result_path, *directory.parent.glob("qualification-preflight-result-*.json"),
                            *directory.parent.glob("qualification-prestart-result-*.json")}):
            if not path.is_file():
                continue
            result = load(path)
            if not self._prestart(result):
                continue
            require(result.get("operator", operator) == operator, "foreign qualification preparation failure")
            producer_binding, producer_refs = self._producer_evidence(result, directory, split)
            evidence.extend([self.pointer(path, split), *producer_refs])
            preparation_failures.append({"status": "prestart_failure", "ledger_stage_started": False,
                "native_sessions_attempted": 0, "actual_record": result, "record": self.pointer(path, split),
                "producer_binding": producer_binding, "qualification_evaluated": False})
        if preparation_failures:
            state["prestart_observations"] = preparation_failures
            if not report_path.exists():
                state.update(status="prestart_blocked", reason="Qualification preparation failed before a ledger stage or native session; qualification is not evaluated.")
        return state

    def _method_lesson(self, method):
        """One concrete method lesson only when a full report was recomputed."""
        if not method.get("report_recomputed"):
            return None
        operator, split = method["operator"], method["split"]
        primary = [p for p in method["evidence"] if Path(p["path"]).name in {"report.json", "manifest.json"}]
        symptoms = []
        for case, data in method["qualification"].items():
            conditions = {name: {"aa_ratio": effect["speedup"], "ratio_ci95": effect["ci95"],
                                  "equivalence": statistics.equivalence(effect)} for name, effect in data["conditions"].items()}
            contrasts = {name: {"full_log_contrast": effect["mean_log"], "log_ci95": effect["log_ci95"],
                                 "exp_contrast": effect["speedup"], "exp_contrast_ci95": effect["ci95"],
                                 "block_multiplier_range": [math.exp(min(effect["log_effects"])), math.exp(max(effect["log_effects"]))],
                                 "mixed_block_directions": min(effect["log_effects"]) < 0 < max(effect["log_effects"]),
                                 "equivalence": statistics.equivalence(effect)}
                         for name, effect in data["contrasts"].items()}
            cvs = [cell for cell in method["cv_by_cell"] if cell["case_id"] == case]
            maximum_cv = max(max(cell["A_cv"], cell["B_cv"]) for cell in cvs)
            ratios = [item["aa_ratio"] for item in conditions.values()]
            # Keep one representative of each observed failure category and
            # factor. All eleven complete checks and process series remain in
            # the frozen report instead of being duplicated in lesson prose.
            selected_conditions = {}
            for classification in ("observed_bias", "precision_insufficient"):
                choices = [(name, value) for name, value in conditions.items() if value["equivalence"] == classification]
                if choices:
                    name, value = max(choices, key=lambda row: max(abs(row[1]["ratio_ci95"][0] - 1), abs(row[1]["ratio_ci95"][1] - 1)))
                    selected_conditions[name] = value
            selected_contrasts = {name: value for name, value in contrasts.items() if value["equivalence"] != "equivalent"}
            classifications = {key: sum(value["equivalence"] == key for value in [*conditions.values(), *contrasts.values()])
                               for key in ("equivalent", "observed_bias", "precision_insufficient")}
            representative = max(conditions, key=lambda name: conditions[name]["ratio_ci95"][1] - conditions[name]["ratio_ci95"][0])
            symptoms.append({"statement": f"Case {case}: A/A condition ratios span {min(ratios):.9g}–{max(ratios):.9g}; maximum role CV is {maximum_cv:.9g}. Separate load, buffer and order contrasts are retained with their 95% intervals.",
                             "basis": "recomputed_current_method_report", "case_ids": [int(case)] if case.isdigit() else [],
                             "case_label": case, "case_attributes": method["case_attributes"][case],
                             "aa_ratio_range": [min(ratios), max(ratios)], "maximum_role_cv": maximum_cv,
                             "representative_aa_condition": {"name": representative, **conditions[representative]},
                             "check_classification_counts": classifications,
                             "low_cv_is_not_sufficient_counterexample": maximum_cv <= .05 and any(value["equivalence"] != "equivalent" for value in [*conditions.values(), *contrasts.values()]),
                             "key_abnormal_aa_conditions": selected_conditions, "abnormal_factor_contrasts": selected_contrasts,
                             "complete_eleven_checks_and_process_series": "External frozen qualification report; selection does not discard equivalent, small or inconclusive effects.",
                             "evidence": primary})
        passed = method["measurement_quality"]["observed_checks_pass"]
        claim = ("All declared A/A conditions, factor contrasts and within-process CV checks met the frozen qualification rules."
                 if passed else "This frozen A/A qualification did not meet all declared acceptance checks; observed bias and insufficient precision remain separately classified.")
        return {"id": f"{self.ledger.config['campaign_id']}/{split}/method/{operator}", "kind": "measurement_method", "operator": operator,
                "split": split, "title": f"{operator}: shared-context A/A qualification {'passed' if passed else 'blocked'} on the declared cases",
                "diagnosis": {"symptoms": symptoms, "hypotheses": [], "missing_evidence": ["Candidate-specific interactions and optimization benefit are not established by A/A qualification."]},
                "intervention": {"statement": "Executed the frozen same-process/context/stream A/A design with separate module-load, buffer-map and AB/BA conditions across six blocks.",
                                 "basis": "recorded_method_protocol_and_recomputed_sessions", "evidence": primary},
                "claims": [{"statement": claim, "status": "supported", "basis": "recomputed_current_method_report",
                            "failure_summary": self._quality_summary(method["measurement_quality"]), "evidence": primary}],
                "limitations": [*method["limitations"], "Factor contrasts are complete log differences, not raw A/B operator speedups.",
                                 "Qualification is tied to the declared source, harness, cases and environment; no formal gate or episode is generated."],
                "next_questions": [] if passed else ["Which observed factor or unresolved precision limitation requires a separately planned method repair?"],
                "source_attempt_ids": [], "graph_links": [], "evidence": primary}

    def _quality_summary(self, quality):
        result = {key: value for key, value in quality.items() if key != "failures"}
        counts = {}
        for failure in quality.get("failures", []):
            key = failure["check"] + ":" + failure["status"]
            counts[key] = counts.get(key, 0) + 1
        result.update(failure_count=len(quality.get("failures", [])), failures_by_check_and_status=counts)
        return result

    def _method_checkpoint(self, method):
        """Keep raw statistical series in their original evidence, not twice."""
        result = {key: value for key, value in method.items() if key not in {"qualification", "cv_by_cell", "recorded_qualification_result"}}
        if "recorded_qualification_result" in method:
            recorded = method["recorded_qualification_result"]
            result["qualification_result_summary"] = {key: recorded[key] for key in ("status", "error", "formal_samples", "actual_costs", "next_action") if key in recorded}
        if "measurement_quality" in result:
            result["measurement_quality"] = self._quality_summary(result["measurement_quality"])
        if method.get("report_recomputed") and "qualification" in method:
            lesson = self._method_lesson(method)
            result["case_summaries"] = [{key: value for key, value in item.items() if key != "evidence"}
                                        for item in lesson["diagnosis"]["symptoms"]]
            result["complete_checks"] = "All eleven checks and per-process CV/log effects are retained in the external qualification report."
        return result

    def _method_comparison(self, operator, directory, split):
        """A regular positive control is method evidence, never a new source attempt."""
        evidence = self._files(directory, split)
        state = {"operator": operator, "split": split, "directory": str(directory),
                 "status": "prepared_not_measured", "evidence": evidence,
                 "formal_admission": "not_evaluated", "graph_policy_eligible": False,
                 "episode_ref": None, "source_attempts_created": 0,
                 "native_bundle_replay": "external_supervisor_only_not_performed_by_archive"}
        if (directory / "report.json").is_file():
            manifest, sessions, report = (load(directory / name) for name in ("manifest.json", "sessions.json", "report.json"))
            require(manifest["task_id"] == operator and manifest["run_id"] == self.ledger.config["campaign_id"],
                    "foreign positive method comparison")
            require(manifest["stages"] == ["before", "reverse", "ab", "after"], "positive method comparison needs regular control phases")
            require(manifest["qualification_scope"].get("status") == "externally_qualified", "positive method comparison lacks external qualification")
            statistics.verify_report(manifest, sessions, report)
            quality = report["measurement_quality"]
            cases = {case: {"speedup": effect["speedup"], "ci95": effect["ci95"],
                            "attributes": report["case_attributes"][case]}
                     for case, effect in report["phases"]["ab"]["cases"].items()}
            state.update(status="passed" if quality["observed_checks_pass"] else "quality_failed", report_recomputed=True,
                         measurement_quality=quality, qualification_scope=manifest["qualification_scope"],
                         ab_suite=report["phases"]["ab"]["suite"], ab_cases=cases,
                         observed_facts=[f"Case {case}: regular A/B speedup {value['speedup']:.9g} with 95% CI [{value['ci95'][0]:.9g}, {value['ci95'][1]:.9g}]."
                                         for case, value in cases.items()],
                         interpretation="Recorded method positive-control contrast, including near-unity cases; historical optimized source is not registered as a current attempt.")
        elif (directory / "collection-completion.json").is_file():
            state.update(status="incomplete", completion=load(directory / "collection-completion.json"))
        return state

    def _candidate(self, name, candidate, task, split, projected):
        cid = candidate["candidate_id"]
        directory = self.run / "tasks" / name / "candidates" / cid
        baseline = self.run / "tasks" / name / "baseline-source.tar"
        parent = baseline if candidate["source_parent"]["candidate_id"] is None else directory.parent / candidate["source_parent"]["candidate_id"] / "source.tar"
        pointers = {"original_baseline": self.pointer(baseline, split, expected=self.ledger.config["tasks"][name]["baseline_source_hash"]),
                    "direct_parent": self.pointer(parent, split, expected=candidate["source_parent"]["source_hash"]),
                    "candidate": self.pointer(directory / "source.tar", split, expected=candidate["source_hash"]),
                    "patch": self.pointer(directory / "optimization.patch", split, expected=candidate["patch_hash"]),
                    "parent_attempt_id": candidate["source_parent"]["candidate_id"]}
        origin_run = candidate["origin"].get("run_id") if candidate["inherited"] else self.ledger.config["campaign_id"]
        require(isinstance(origin_run, str) and origin_run, "inherited source needs its original run identity")
        evidence = [projected]
        for filename in ("registration.json", "source-change.json", "inheritance.json", "static-review.json"):
            if (directory / filename).is_file():
                evidence.append(self.pointer(directory / filename, split))
        for filename in ("build_manifest.json", "A.harness.patch", "B.harness.patch"):
            path = directory / "ab-build" / filename
            if path.is_file():
                evidence.append(self.pointer(path, split))
        evidence.extend(self._build_artifacts(directory / "ab-build/build_manifest.json", split))
        if (directory / "inheritance.json").is_file():
            inheritance = load(directory / "inheritance.json")
            require(inheritance.get("original_attempt_id") == f"{origin_run}/{split}/{cid}" and inheritance.get("same_source_attempt") is True,
                    "inherited attempt identity differs from original source record")
        registration = load(directory / "registration.json") if (directory / "registration.json").is_file() else {}
        source_change = load(directory / "source-change.json") if (directory / "source-change.json").is_file() else {}
        diagnosis = {"symptoms": [], "hypotheses": [], "missing_evidence": [], "retrospective": True}
        intervention = {"statement": "Registered optimization source differs from its frozen direct parent; exact patch is bound.",
                        "basis": "retrospective_source_registration", "evidence": [pointers["patch"], *evidence]}
        old_task = None
        if candidate["inherited"]:
            origin = load(directory / "inheritance.json").get("origin") if (directory / "inheritance.json").is_file() else None
            if origin:
                old_task = Path(origin).resolve().parents[1]
        if old_task is not None and (old_task / "agent" / "next-experiment.json").is_file():
            proposal_path = old_task / "agent" / "next-experiment.json"
            proposal = load(proposal_path)
            proposal_ref = self.pointer(proposal_path, split)
            evidence.append(proposal_ref)
            rationale = proposal.get("rationale")
            if rationale:
                diagnosis["hypotheses"].append({"statement": rationale, "basis": "recorded_historical_agent_proposal",
                                                 "case_ids": proposal.get("cases", []), "evidence": [proposal_ref],
                                                 "limitations": proposal.get("measurement_limitations", [])})
            intervention = {"statement": proposal["intervention"]["intent"], "basis": "recorded_historical_agent_proposal",
                            "parameters": proposal["intervention"].get("parameters", {}),
                            "expected_counters": proposal.get("expected_counters", {}), "evidence": [proposal_ref, pointers["patch"]],
                            "limitations": proposal.get("measurement_limitations", [])}
        evaluations, timeline = [], []
        # Preparation can fail before start_stage. Such actual records are
        # observations of this existing source, not correctness verdicts or new
        # ledger executions. Discover them independently of ledger stages.
        for path in sorted(directory.glob("*/group-result.json")):
            result = load(path)
            if not self._prestart(result):
                continue
            require(result.get("candidate_id") == cid and result.get("operator", name) == name, "foreign candidate prestart record")
            require(result.get("run_id", self.ledger.config["campaign_id"]) == self.ledger.config["campaign_id"] and
                    result.get("source_hash", candidate["source_hash"]) == candidate["source_hash"], "foreign prestart run/source identity")
            stage_name = result.get("stage", "preparation")
            require(isinstance(stage_name, str) and stage_name, "prestart stage name required")
            intended_stage = f"{cid}-{path.parent.name}"
            require(intended_stage not in task["stages"], "prestart record conflicts with an existing ledger stage")
            result_ref = self.pointer(path, split)
            producers, producer_refs = self._producer_evidence(result, path.parent, split)
            local_evidence = [*self._files(path.parent, split), *producer_refs]
            recoveries = []
            for recovery_path in sorted(directory.glob("*prestart-recovery*.json")):
                recovery = load(recovery_path)
                failed = recovery.get("failed_record", {})
                if not isinstance(failed.get("path"), str) or Path(failed["path"]).resolve() != path.resolve():
                    continue
                require(failed.get("sha256") == result_ref["sha256"], "prestart recovery failed-record hash mismatch")
                require(recovery.get("attempt_id") == cid and recovery.get("source_hash") == candidate["source_hash"]
                        and recovery.get("source_change") is False and recovery.get("hardware_sessions_started") == 0
                        and recovery.get("recovery_number") == 1, "invalid one-time same-source prestart recovery")
                require(f"{stage_name}-{recovery.get('failed_group')}" == path.parent.name, "recovery failed-group label mismatch")
                next_group = recovery.get("next_group")
                require(isinstance(next_group, str) and next_group and Path(next_group).name == next_group, "unsafe recovery group")
                target = directory / f"{stage_name}-{next_group}"
                recovery_ref = self.pointer(recovery_path, split)
                local_evidence.append(recovery_ref)
                recoveries.append({"record": recovery_ref, "recovery_number": 1, "target_directory": str(target),
                                   "target_stage_id": f"{cid}-{stage_name}-{next_group}",
                                   "outcome_inferred": False, "actual_record": recovery})
            require(len(recoveries) <= 1, "more than one prestart recovery was recorded")
            observation = {"status": "prestart_failure", "reason": json.dumps(result.get("error"), ensure_ascii=False),
                "summary": {"classification": "prestart_failure", "ledger_stage_started": False,
                            "native_sessions_attempted": 0, "source_hash": candidate["source_hash"],
                            "actual_costs": result.get("actual_costs", {}), "original_status": result.get("status"),
                            "correctness_evaluated": False, "recoveries": recoveries, "producer_binding": producers},
                "cases": [], "actual_record": result, "evidence": [result_ref, *local_evidence]}
            observation_ref = self.document(split, name + "-prestart-observation", observation)
            evaluations.append({"id": f"{self.ledger.config['campaign_id']}:{cid}:prestart:{path.parent.name}",
                "run_id": self.ledger.config["campaign_id"], "session_id": f"prestart:{path.parent.name}",
                "baseline": "direct_parent", "relation": "measurement_continuation", "measurement_quality": "not_measured_prestart",
                "stages": [{"name": stage_name + "_prestart", "record": observation_ref}], "observations": observation_ref})
            timestamp = result.get("ended_at", result.get("started_at"))
            if isinstance(timestamp, (int, float)):
                row = {"timestamp": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(), "event_type": "prestart_failure_observed",
                       "summary": f"{path.parent.name} failed during preparation; no ledger stage or native session started.",
                       "observation": observation_ref, "recoveries": recoveries, "evidence": local_evidence}
                timeline.append({"record": self.document(split, name + "-prestart-events", row)})
            evidence.extend(local_evidence)
        if (directory / "static-review.json").is_file():
            review = load(directory / "static-review.json")
            require(isinstance(review.get("status"), str), "static review needs an actual recorded status")
            evaluations.append({"id": f"{origin_run}:{cid}:static-review", "run_id": origin_run,
                                "session_id": registration.get("session_id", "historical-static-review"), "baseline": "direct_parent",
                                "relation": "original_attempt", "measurement_quality": "not_measured_static_review_only",
                                "stages": [{"name": "static_review", "record": self.pointer(directory / "static-review.json", split)}]})
        recorded_time = source_change.get("timestamp_utc") or registration.get("registered_at")
        if recorded_time:
            row = {"timestamp": recorded_time, "event_type": "source_registered",
                   "summary": f"Recorded source {cid}; source identity and original registration are preserved.", "evidence": evidence,
                   "attribution": "retrospective_projection_of_recorded_source_registration"}
            timeline.append({"record": self.document(split, name + "-source-events", row)})
        for sid, stage in task["stages"].items():
            if stage["candidate_id"] != cid:
                continue
            for number, attempt in enumerate(stage["attempts"]):
                require(attempt["outcome"] is not None, "candidate execution is still running")
                stage_record = {"status": attempt["outcome"], "reason": attempt.get("reason"), "ledger_stage": stage,
                                "attempt_index": number, "actual_completion": attempt, "evidence": [projected]}
                for key in ("role_build", "runner_build"):
                    if stage["plan"].get(key):
                        evidence.extend(self._build_artifacts(stage["plan"][key], split))
                linked = self._evidence_paths(attempt.get("evidence", {}), split, owner=name)
                for pointer in linked:
                    path = Path(pointer["path"])
                    if path.name == "group-result.json":
                        recorded = load(path)
                        producer_binding, producer_refs = self._producer_evidence(recorded, path.parent, split)
                        evidence.extend([*self._files(path.parent, split), *producer_refs])
                        stage_record["producer_binding"] = producer_binding
                    if stage["kind"] != "timing" or path.name != "group-result.json":
                        continue
                    group = load(path)
                    if group.get("schema_version") != "shared_context_comparison_group_v1":
                        continue
                    require(group["operator"] == name and group["candidate_id"] == cid and group["stage_id"] == sid
                            and group["run_id"] == self.ledger.config["campaign_id"], "foreign candidate comparison group")
                    require(group["formal_samples"] == attempt["formal_samples"], "comparison group cost differs from ledger")
                    # Keep the complete text closure, including partial native
                    # journals, without copying output tensors/build binaries.
                    evidence.extend(self._files(path.parent, split))
                    for evaluation in group["evaluations"]:
                        if evaluation["status"] not in {"passed", "quality_failed"}:
                            continue
                        comparison = path.parent / evaluation["control"]
                        manifest, sessions, report = (load(comparison / filename) for filename in ("manifest.json", "sessions.json", "report.json"))
                        statistics.verify_report(manifest, sessions, report)
                        require(evaluation["cases"] == report["phases"]["ab"]["cases"] and evaluation["suite"] == report["phases"]["ab"]["suite"],
                                "comparison summary differs from recomputed report")
                    stage_record["comparison_group"] = group
                record = self.document(split, name + "-execution", stage_record)
                evaluations.append({"id": f"{self.ledger.config['campaign_id']}:{cid}:{sid}:{number}",
                                    "run_id": self.ledger.config["campaign_id"], "session_id": sid + ":" + str(number),
                                    "baseline": "direct_parent", "relation": "measurement_continuation" if candidate["inherited"] or evaluations else "original_attempt",
                                    "measurement_quality": "not_evaluated_by_archive_see_bound_report", "stages": [{"name": stage["kind"], "record": record}]})
                if "comparison_group" in stage_record:
                    group = stage_record["comparison_group"]
                    observations = {"summary": {"status": group.get("status", attempt["outcome"]),
                        "formal_samples": group["formal_samples"], "actual_costs": group.get("actual_costs", {}),
                        "comparisons": [{k: value for k, value in evaluation.items() if k != "cases"}
                                        for evaluation in group["evaluations"]],
                        "comparison_scope": "Independent comparisons retain their own control source; no ratios are composed."},
                        "cases": [{"case_id": case, "control": evaluation["control"],
                                   "control_source_hash": evaluation["control_source_hash"], **effect}
                                  for evaluation in group["evaluations"] for case, effect in evaluation.get("cases", {}).items()]}
                    evaluations[-1]["observations"] = self.document(split, name + "-comparison-observations", observations)
                    evaluations[-1]["measurement_quality"] = group.get("status", attempt["outcome"])
                evidence.extend(linked)
                for pointer in linked:
                    path = Path(pointer["path"])
                    if path.parent.name.endswith("-execution"):
                        evidence.extend(self._files(path.parent, split))
        for kind in ("build", "correctness", "runtime", "timing", "profile"):
            if not any(s["candidate_id"] == cid and s["kind"] == kind for s in task["stages"].values()):
                diagnosis["missing_evidence"].append(f"No separately recorded candidate {kind} stage in this collection; no outcome is inferred from static review or another phase.")
        decision = None
        if candidate["observation_ids"]:
            observation = task["observations"][candidate["observation_ids"][-1]]
            decision = {"action": "recorded_feedback", "reason": json.dumps(observation["feedback"], ensure_ascii=False, sort_keys=True), "evidence": [projected]}
        analysis = None
        if (directory / "analysis.json").is_file():
            analysis = self._analysis(directory / "analysis.json", name, cid, split)
            for key in ("symptoms", "hypotheses", "missing_evidence"):
                diagnosis[key].extend(analysis["diagnosis"][key])
            historical_intervention = intervention
            intervention = deepcopy(analysis["intervention"])
            if historical_intervention.get("basis") == "recorded_historical_agent_proposal":
                intervention["recorded_historical_proposal"] = {
                    key: deepcopy(historical_intervention[key])
                    for key in ("statement", "basis", "parameters", "expected_counters", "limitations")
                    if key in historical_intervention}
                references = [*intervention["evidence"], *historical_intervention.get("evidence", [])]
                intervention["evidence"] = list({v2.digest(pointer): pointer for pointer in references}.values())
            evidence.extend(analysis["evidence"])
        return {"id": cid, "origin_run_id": origin_run, "task_id": name, "operator": name, "split": split,
                "sources": pointers, "context": {"collection_run_id": self.ledger.config["campaign_id"], "source_attempt_origin_run_id": origin_run,
                    "inherited_source": candidate["inherited"], "new_source_charge": not candidate["inherited"],
                    "protocol": campaign.PROTOCOL, "formal_admission": "not_evaluated", "graph_policy_eligible": False, "episode_ref": None,
                    "scope": "known_workload_not_heldout", "probes": candidate["probes"],
                    "current_analysis_attribution": "retrospective_current_evidence" if analysis else "not_recorded",
                    "current_read_audit_summaries": analysis["read_audits"] if analysis else [],
                    "source_identity_kind": "Frozen optimization source tar and optimization patch; generated wrapper patches/native module identities are separately bound build evidence."},
                "diagnosis": diagnosis, "intervention": intervention, "evaluations": evaluations, "timeline": timeline,
                "actual_reads": analysis["actual_reads"] if analysis else [], "next_decision": decision, "archive_evidence": evidence,
                "archive_lessons": analysis["lessons"] if analysis else []}

    def prepare_split(self, split):
        attempts, checkpoints, artifacts, lessons = [], [], [], []
        run_id = self.ledger.config["campaign_id"]
        for name, task in self.ledger.state["tasks"].items():
            if task["split"] != split:
                continue
            projection = {"schema_version": VERSION, "kind": "task_ledger_projection", "collection_run_id": run_id,
                          "operator": name, "split": split, "protocol": campaign.PROTOCOL, "source_ledger_head": self.ledger.events[-1]["hash"],
                          "declaration": self.ledger.config["tasks"][name], "task": task,
                          "attribution": "read_only_replayed_ledger_projection_not_new_execution"}
            projected = self.document(split, name + "-ledger", projection)
            taskdir = self.run / "tasks" / name
            method = self._method(name, taskdir / "qualification", split)
            lesson = self._method_lesson(method)
            if lesson:
                lessons.append(lesson)
            evidence = [projected, *method["evidence"]]
            method_diagnostics = []
            for sid, stage in task["stages"].items():
                if stage["candidate_id"] is not None:
                    continue
                for key in ("role_build", "runner_build"):
                    if stage["plan"].get(key):
                        evidence.extend(self._build_artifacts(stage["plan"][key], split))
                for attempt in stage["attempts"]:
                    refs = self._evidence_paths(attempt.get("evidence", {}), split, owner=name)
                    evidence.extend(refs)
                    for pointer in refs:
                        path = Path(pointer["path"])
                        if path.name == "group-result.json":
                            result = load(path)
                            producer_binding, producer_refs = self._producer_evidence(result, path.parent, split)
                            evidence.extend([*self._files(path.parent, split), *producer_refs])
                            method_diagnostics.append({"stage_id": sid, "kind": stage["kind"], "status": attempt["outcome"],
                                "actual_costs": attempt.get("actual_costs", {}), "producer_binding": producer_binding,
                                "paired_performance_evaluated": False, "record": pointer})
            for subdirectory in ("qualification-execution", "aa-build-execution"):
                evidence.extend(self._files(taskdir / subdirectory, split))
            task_notes = {taskdir / filename for filename in ("baseline-binding.json", "input-bindings.json", "task-parity.json", "closure.json", "qualification-result.json",
                "aa-failure-analysis.json", "agent-initial-review.json", "agent-feedback-decision.json", "execution-manifest.json")}
            task_notes.update(taskdir.glob("*runtime*manifest*.json"))
            task_notes.update(taskdir.glob("*manifest*runtime*.json"))
            for path in sorted(task_notes):
                if path.is_file():
                    evidence.append(self.pointer(path, split))
            closure = load(taskdir / "closure.json") if (taskdir / "closure.json").is_file() else None
            if closure is not None:
                require(isinstance(closure, dict) and isinstance(closure.get("status"), str) and closure["status"], "closure requires a nonempty status string")
            if closure:
                evidence.extend(self._evidence_paths(closure.get("evidence", []), split, owner=name))
            checkpoint = {"operator": name, "split": split, "collection_run_id": run_id,
                          "status": closure.get("status", method["status"]) if closure else method["status"],
                          "recorded_closure": closure, "method_qualification": self._method_checkpoint(method), "used": task["used"],
                          "method_diagnostics": method_diagnostics,
                          "remaining": {k: campaign.BUDGETS[k] - task["used"][k] for k in campaign.BUDGETS},
                          "source_attempt_count": len(task["candidates"]), "formal_admission": "not_evaluated",
                          "graph_policy_eligible": False, "episode_ref": None, "evidence": evidence}
            checkpoints.append(checkpoint)
            artifacts.extend(evidence)
            for candidate in task["candidates"].values():
                attempt = self._candidate(name, candidate, task, split, projected)
                artifacts.extend(attempt.pop("archive_evidence"))
                lessons.extend(attempt.pop("archive_lessons"))
                attempts.append(attempt)
        methods = list(self.index.get("methods", []))
        norm = self.run / "method" / "foreach_norm" / "qualification"
        if norm.is_dir() and not any(m.get("operator") == "foreach_norm" and m.get("kind", "qualification") == "qualification" for m in methods):
            methods.append({"operator": "foreach_norm", "split": "train", "directory": str(norm)})
        positive = norm.parent / "positive-comparison"
        if positive.is_dir() and not any(m.get("operator") == "foreach_norm" and m.get("kind") == "positive_comparison" for m in methods):
            methods.append({"operator": "foreach_norm", "split": "train", "directory": str(positive), "kind": "positive_comparison"})
        seen = set()
        for entry in methods:
            require(isinstance(entry, dict) and entry.get("split") in {"train", "validation"}, "method entry needs explicit split")
            if entry["split"] != split:
                continue
            operator = entry["operator"]
            kind = entry.get("kind", "qualification")
            require(kind in {"qualification", "positive_comparison"}, "unknown method evidence kind")
            require((operator, kind) not in seen and _split_for(operator) == split, "duplicate or cross-split method entry")
            seen.add((operator, kind))
            directory = Path(entry["directory"])
            directory = directory if directory.is_absolute() else self.run / directory
            _safe_path(directory, split, owner=operator)
            method = self._method_comparison(operator, directory, split) if kind == "positive_comparison" else self._method(operator, directory, split)
            method["evidence"].extend(self._evidence_paths(entry.get("evidence", []), split, owner=operator))
            checkpoints.append({"kind": "standalone_method_" + kind, "collection_run_id": run_id, **self._method_checkpoint(method)})
            artifacts.extend(method["evidence"])
            lesson = self._method_lesson(method) if kind == "qualification" else None
            if lesson:
                lessons.append(lesson)
        manifest = {"run_id": run_id, "task_id": "shared-context-" + split, "split": split, "attempts": attempts,
                    "lessons": lessons, "task_checkpoints": checkpoints, "artifact_index": list({v2.digest(p): p for p in artifacts}.values()),
                    "archive_contract": {"version": VERSION, "no_new_method_source_attempts": True,
                        "binary_outputs": "Native DSOs/runners and source tar archives are frozen. Output tensors are not copied; oracle acknowledgements and output hashes remain in evidence.",
                        "inherited_source_attempts": sum(a["origin_run_id"] != run_id for a in attempts),
                        "new_source_attempts": sum(a["origin_run_id"] == run_id for a in attempts),
                        "measurement_method_lessons": sum(item["kind"] == "measurement_method" for item in lessons),
                        "operator_optimization_lessons": sum(item["kind"] == "operator_optimization" for item in lessons)}}
        return Path(self.document(split, "recording", manifest)["path"])

    def publish_split(self, manifest_path, split):
        config = load(manifest_path)
        output = self.output / split / "v2"
        recorder = FrozenRecorder(manifest_path, output)
        memories = {}
        for number, attempt in enumerate(config["attempts"]):
            origin = attempt["origin_run_id"]
            body = recorder.memory(attempt, number, {**config, "run_id": origin})
            for raw, evaluation in zip(attempt["evaluations"], body["evaluations"]):
                evaluation["run_id"] = raw["run_id"]
            identifier = f"{origin}/{split}/{attempt['id']}"
            require(identifier not in memories, "duplicate source attempt identity")
            memories[identifier] = body
        checkpoint_refs = []
        for index, checkpoint in enumerate(config["task_checkpoints"]):
            checkpoint_refs.append(recorder.pointer({"path": str(manifest_path), "selector": "/task_checkpoints/" + str(index)}, split,
                                                    "method/task checkpoint, not a source attempt"))
        for pointer in config["artifact_index"]:
            recorder.pointer(pointer, split, "frozen method/source execution evidence")
        def freeze_lesson(value):
            if isinstance(value, list):
                return [freeze_lesson(item) for item in value]
            if isinstance(value, dict):
                result = {}
                for key, item in value.items():
                    if key == "evidence":
                        refs = [recorder.pointer(pointer, split, "method lesson evidence") for pointer in item]
                        result[key] = [{"path": recorder.evidence.entries[ref]["path"], "selector": recorder.evidence.entries[ref]["selector"]} for ref in refs]
                    else:
                        result[key] = freeze_lesson(item)
                return result
            return value
        lessons = [freeze_lesson(value) for value in config["lessons"]]
        producer_hash = file_hash(__file__)
        producer_source_ref = recorder.pointer({"path": str(Path(__file__).resolve()), "sha256": producer_hash}, split,
                                               "archive producer source for this published revision")
        metadata = {"schema_version": v2.VERSION, "run_id": config["run_id"], "collection_run_id": config["run_id"],
                    "task_id": config["task_id"], "split": split, "exporter_hardware_executed": False,
                    "legacy_gate_and_episode_semantics": "unchanged", "formal_admission": "not_evaluated",
                    "graph_policy_eligible": False, "episode_ref": None, "task_checkpoint_refs": checkpoint_refs,
                    **config["archive_contract"], "original_evidence_locations": {k: sorted(v) for k, v in recorder.origins.items()},
                    "producer_hash": producer_hash, "producer_source_ref": producer_source_ref}
        metadata["evaluation_granularity"] = "One recorded source stage attempt per evaluation; continuation counts are not timing groups or independent native processes."
        result = v2.publish(output, memories, lambda rows: v2.normalize_lessons(lessons, rows, recorder.evidence), recorder.evidence, metadata)
        result["verification"] = v2.verify(output, deep=True)
        result.update(inherited_source_attempts=config["archive_contract"]["inherited_source_attempts"],
                      new_source_attempts=config["archive_contract"]["new_source_attempts"], task_checkpoints=len(checkpoint_refs),
                      measurement_method_lessons=config["archive_contract"]["measurement_method_lessons"],
                      operator_optimization_lessons=config["archive_contract"]["operator_optimization_lessons"])
        return result

    def archive(self, *, publish=True):
        # Prepare both split closures before either current pointer is changed.
        manifests = {split: self.prepare_split(split) for split in ("train", "validation")}
        result = {"schema_version": VERSION, "run_id": self.ledger.config["campaign_id"], "hardware_executed": False,
                  "recording_manifests": {k: str(v) for k, v in manifests.items()}}
        if publish:
            result["datasets"] = {split: self.publish_split(path, split) for split, path in manifests.items()}
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    repair = commands.add_parser("repair-probes")
    repair.add_argument("--run", required=True, type=Path)
    repair.add_argument("--draft", required=True, type=Path)
    archive = commands.add_parser("archive")
    archive.add_argument("--run", required=True, type=Path)
    archive.add_argument("--output", type=Path)
    archive.add_argument("--method-index", type=Path)
    archive.add_argument("--prepare-only", action="store_true")
    verify = commands.add_parser("verify")
    verify.add_argument("--output", required=True, type=Path)
    analysis = commands.add_parser("validate-analysis", help="read-only bounded analysis/evidence validation; no source tar or binary hashing")
    analysis.add_argument("--run", required=True, type=Path)
    analysis.add_argument("--operator", required=True, choices=campaign.WORKLOADS)
    analysis.add_argument("--candidate", required=True)
    analysis.add_argument("--max-evidence-bytes", type=int, default=1024 * 1024)
    args = parser.parse_args(argv)
    if args.command == "repair-probes":
        result = repair_bootstrap_probes(args.run, args.draft)
    elif args.command == "validate-analysis":
        require(args.max_evidence_bytes > 0, "positive evidence size bound required")
        path = args.run / "tasks" / args.operator / "candidates" / args.candidate / "analysis.json"
        value = validate_candidate_analysis(path, args.run, args.operator, args.candidate, max_evidence_bytes=args.max_evidence_bytes)
        result = {"valid": True, "hardware_executed": False, "retrospective": True, "candidate_id": args.candidate,
                  "named_evidence_files": len(value["evidence"]), "symptoms": len(value["diagnosis"]["symptoms"]),
                  "lessons": len(value.get("lessons", [])), "read_audit_scopes": [a["temporal_scope"] for a in value.get("read_audits", [])]}
    elif args.command == "verify":
        result = {split: v2.verify(args.output / split / "v2", deep=True) for split in ("train", "validation")}
    else:
        result = Bridge(args.run, args.output, args.method_index).archive(publish=not args.prepare_only)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
