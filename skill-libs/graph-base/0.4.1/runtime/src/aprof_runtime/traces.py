"""Append-only local optimization evidence, distinct from training episodes."""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker

from .errors import ContractError, StoreError
from .jsonio import canonical_json, content_hash, require_json_value
from .store import EpisodeStore
from .trace_schemas import SCHEMAS, VERSION

GENESIS = "sha256:" + "0" * 64


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def validate_trace_contract(kind: str, value: Any) -> dict:
    value = require_json_value(value)
    if kind not in SCHEMAS:
        raise ContractError(f"unknown trace contract {kind!r}")
    errors = sorted(Draft202012Validator(SCHEMAS[kind], format_checker=FormatChecker()).iter_errors(value),
                    key=lambda error: str(list(error.absolute_path)))
    if errors:
        error = errors[0]
        raise ContractError(f"{kind} $.{'.'.join(map(str, error.absolute_path))}: {error.message}")
    return value


def _hash_refs(value: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, dict):
        for key, item in value.items():
            if key not in {"event_hash", "previous_event_hash", "episode_ref"}:
                yield from _hash_refs(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _hash_refs(item, f"{path}[{index}]")
    elif isinstance(value, str) and value.startswith("sha256:"):
        yield path, value


def _verify_refs(value: dict, store: EpisodeStore | None, verified: set[str] | None = None) -> None:
    verified = set() if verified is None else verified
    if store is not None:
        for _, digest in _hash_refs(value):
            if digest not in verified:
                store.verify_artifact(digest)
                verified.add(digest)


def _read_lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise StoreError(f"{path}: incomplete final JSONL line; explicit recover_trace_tail is required")
    records = []
    for index, line in enumerate(data.splitlines(), 1):
        try:
            records.append(require_json_value(json.loads(line)))
        except (json.JSONDecodeError, UnicodeDecodeError, ContractError) as exc:
            raise StoreError(f"{path}:{index}: invalid JSONL: {exc}") from exc
    return records


@contextmanager
def _locked(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a+b") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _append(path: Path, value: dict) -> None:
    with path.open("ab") as stream:
        stream.write((canonical_json(value) + "\n").encode("utf-8"))
        stream.flush()
        os.fsync(stream.fileno())


def _atomic_jsonl(path: Path, records: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".trace-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            for record in records:
                stream.write((canonical_json(record) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def register_json_artifact(store: EpisodeStore, value: Any) -> str:
    """Canonical bytes without a newline: CAS hash equals content_hash(value)."""
    fd, name = tempfile.mkstemp(prefix="aprof-evidence-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(canonical_json(value))
        # The temporary file is removed immediately; its pathname is not a
        # durable provenance location. Canonical JSON has its CAS URI instead.
        return store.register_artifact(name, media_type="application/json",
            uri=store.object_path(content_hash(value)).resolve().as_uri())
    finally:
        Path(name).unlink(missing_ok=True)


def execution_record(*, argv, cwd, host, device=None, started_at, finished_at,
                     exit_status, log_ref=None, reason=None) -> dict:
    return {"argv": list(argv), "cwd": str(cwd), "host": host,
            "device": None if device is None else str(device), "started_at": started_at,
            "finished_at": finished_at, "exit_status": exit_status,
            "log_ref": log_ref, "reason": reason}


def _check_event(event: dict, store: EpisodeStore | None, verified: set[str] | None = None) -> None:
    validate_trace_contract("trace-event", event)
    if event["event_hash"] != content_hash({key: value for key, value in event.items() if key != "event_hash"}):
        raise StoreError(f"event hash mismatch: {event['event_id']}")
    if (event["attempt_id"] is None) != (event["candidate_id"] is None):
        raise ContractError("attempt_id and candidate_id must either both exist or both be null")
    if event["event_type"] == "candidate_proposed" and event["candidate_id"] is None:
        raise ContractError("candidate_proposed requires candidate and attempt identity")
    payload = event["payload"]
    execution = payload.get("execution")
    if execution:
        if datetime.fromisoformat(execution["finished_at"].replace("Z", "+00:00")) < datetime.fromisoformat(execution["started_at"].replace("Z", "+00:00")):
            raise ContractError("execution finished before it started")
        if execution["exit_status"] is None and not execution["reason"]:
            raise ContractError("missing exit status requires an interruption reason")
        if execution["log_ref"] is None and not execution["reason"]:
            raise ContractError("missing execution log requires an explicit reason")
    if payload.get("status") == "passed" and execution and execution["exit_status"] != 0:
        raise ContractError("passed execution requires exit_status=0")
    if "passed_count" in payload and payload["passed_count"] > payload["case_count"]:
        raise ContractError("passed_count exceeds case_count")
    _verify_refs(event, store, verified)


def _verify_records(records: list[dict], store: EpisodeStore | None = None) -> dict:
    heads: dict[tuple, tuple[int, str]] = {}
    event_ids: set[str] = set()
    # A verification pass hashes every referenced CAS object once. The set is
    # discarded afterwards, so a later verification still detects tampering.
    verified: set[str] = set()
    for event in records:
        _check_event(event, store, verified)
        if event["event_id"] in event_ids:
            raise StoreError(f"duplicate event_id: {event['event_id']}")
        event_ids.add(event["event_id"])
        key = tuple(event[name] for name in ("run_id", "task_id", "session_id"))
        sequence, previous = heads.get(key, (0, GENESIS))
        if event["sequence"] != sequence + 1 or event["previous_event_hash"] != previous:
            raise StoreError(f"broken event chain at {event['event_id']}")
        heads[key] = (event["sequence"], event["event_hash"])
    return {"valid": True, "event_count": len(records), "streams": [
        {"run_id": key[0], "task_id": key[1], "session_id": key[2], "sequence": head[0], "chain_head": head[1]}
        for key, head in sorted(heads.items())]}


def verify_trace(path: str | Path, store: EpisodeStore | None = None) -> dict:
    return _verify_records(_read_lines(Path(path)), store)


class TraceWriter:
    def __init__(self, path, *, run_id, task_id, session_id, store=None, verify_history_artifacts=True):
        self.path = Path(path)
        self.identity = dict(run_id=run_id, task_id=task_id, session_id=session_id)
        self.store = store
        self.verify_history_artifacts = verify_history_artifacts

    def append(self, event_type, payload, *, attempt_id=None, candidate_id=None,
               artifact_refs=(), event_id=None, timestamp=None) -> dict:
        with _locked(self.path):
            records = _read_lines(self.path)
            # A collecting coordinator may verify historical CAS bytes at its
            # explicit startup/seal/export boundaries. Every append still
            # verifies the complete JSONL hash chain and all new event refs.
            # Default callers retain exhaustive historical artifact checks.
            _verify_records(records, self.store if self.verify_history_artifacts else None)
            if any(any(record[key] != value for key, value in self.identity.items()) for record in records):
                raise StoreError("worker stream contains a different task/session identity")
            proposal = {"schema_version": VERSION, **self.identity, "event_type": event_type,
                        "payload": deepcopy(payload), "attempt_id": attempt_id,
                        "candidate_id": candidate_id, "artifact_refs": sorted(set(artifact_refs))}
            if event_id:
                existing = next((record for record in records if record["event_id"] == event_id), None)
                if existing:
                    if any(existing[key] != value for key, value in proposal.items()):
                        raise StoreError(f"event id reused with different content: {event_id}")
                    if not self.verify_history_artifacts:
                        _check_event(existing, self.store)
                    return existing
            event = {**proposal, "event_id": event_id or str(uuid.uuid4()), "timestamp": timestamp or utcnow(),
                     "sequence": len(records) + 1,
                     "previous_event_hash": records[-1]["event_hash"] if records else GENESIS}
            event["event_hash"] = content_hash(event)
            _check_event(event, self.store)
            _append(self.path, event)
            return event

    def seal_attempt(self, attempt_id: str) -> str:
        if self.store is None:
            raise StoreError("sealing an attempt requires an EpisodeStore CAS")
        records = _read_lines(self.path)
        _verify_records(records, self.store)
        selected = [record for record in records if record["attempt_id"] == attempt_id]
        if not selected:
            raise StoreError(f"attempt has no evidence events: {attempt_id}")
        # Outcome/episode links are appended after sealing, avoiding a hash cycle.
        if any(record["event_type"] == "attempt_finished" for record in selected):
            raise StoreError("attempt evidence must be sealed before attempt_finished")
        return register_json_artifact(self.store, {"schema_version": VERSION,
            "identity": self.identity, "attempt_id": attempt_id, "events": selected})


def recover_trace_tail(path: str | Path, store: EpisodeStore | None = None) -> dict:
    """Preserve a crash's incomplete suffix before explicitly removing only it."""
    path = Path(path)
    with _locked(path):
        data = path.read_bytes()
        if not data or data.endswith(b"\n"):
            return {"recovered": False, "discarded_bytes": 0, "artifact_ref": None}
        end = data.rfind(b"\n") + 1
        prefix, suffix = data[:end], data[end:]
        # Never silently remove a complete JSON record lacking only its newline.
        try:
            json.loads(suffix)
        except (json.JSONDecodeError, UnicodeDecodeError):
            pass
        else:
            with path.open("ab") as stream:
                stream.write(b"\n")
                stream.flush()
                os.fsync(stream.fileno())
            verify_trace(path, store)
            return {"recovered": True, "discarded_bytes": 0, "artifact_ref": None}
        recovery = path.with_name(path.name + ".interrupted-" + uuid.uuid4().hex)
        recovery.write_bytes(suffix)
        digest = store.register_artifact(recovery) if store else None
        records = [json.loads(line) for line in prefix.splitlines()]
        _verify_records(records, store)
        with path.open("r+b") as stream:
            stream.truncate(end)
            stream.flush()
            os.fsync(stream.fileno())
        return {"recovered": True, "discarded_bytes": len(suffix), "artifact_ref": digest, "recovery_file": str(recovery)}


def merge_trace_streams(paths, output, store=None) -> dict:
    unique = {}
    for path in paths:
        records = _read_lines(Path(path))
        _verify_records(records, store)
        for event in records:
            if event["event_id"] in unique and unique[event["event_id"]] != event:
                raise StoreError(f"conflicting event_id: {event['event_id']}")
            unique[event["event_id"]] = event
    # Sorting by stream/sequence preserves each original independently hashed chain.
    records = sorted(unique.values(), key=lambda event: (event["run_id"], event["task_id"], event["session_id"], event["sequence"]))
    result = _verify_records(records, store)
    with _locked(Path(output)):
        existing = {record["event_id"]: record for record in _read_lines(Path(output))}
        if any(unique.get(key) != value for key, value in existing.items()):
            raise StoreError("merge would discard or rewrite existing events")
        _atomic_jsonl(Path(output), records)
    return result


def _null_paths(value, path="$"):
    if isinstance(value, dict):
        for key, item in value.items():
            if key != "null_reasons":
                yield from _null_paths(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _null_paths(item, f"{path}[{index}]")
    elif value is None:
        yield path


def make_optimization_trace(identity: dict, **groups) -> dict:
    """Construct an explicit incomplete record; caller supplies observed facts."""
    stage = {"status": "not_run", "reason": "not collected", "artifact_refs": []}
    value = {
        "schema_version": VERSION, "identity": {"parent_attempt_id": None, **identity},
        "provenance": {"dependencies": {}, **{key: None for key in ("graph_hash", "skill_manifest_hash",
            "prompt_hash", "producer_hash", "harness_hash", "baseline_source_hash", "candidate_source_hash", "patch_hash")}},
        "knowledge": {"manifest_hash": None, "loaded": []},
        "workload": {"manifest_hash": None, "case_ids": [], "shapes": {}, "dtypes": [], "layouts": [],
            "attributes": {}, "accuracy_contract": None, "hardware_fingerprint": None},
        "diagnosis": {"symptoms": [], "mechanisms": [], "assessment_basis": "manual", "supporting_evidence": [],
            "contradicting_evidence": [], "missing_evidence": ["diagnosis not collected"], "source_anchors": []},
        "intervention": {"intent": "not recorded", "rationale": "not recorded", "expected_effects": [],
            "handler": {"id": "unrecorded", "version": "unrecorded", "producer_hash": None}, "parameters": {}, "alternatives": []},
        "routing": {"mode": "exploration", "route": None, "coverage_gap": "routing has not been established"},
        "validation": {**{key: deepcopy(stage) for key in ("static_review", "build", "correctness", "runtime", "timing", "profile")},
            "case_count": 0, "passed_count": 0, "timing_case_ids": []},
        "result": {"verdict": "inconclusive", "first_failed_stage": None, "speedup": None, "speedup_lcb": None,
            "max_regression": None, "machine_outcome_ref": None, "episode_ref": None,
            "exploration_outcome_ref": None, "graph_policy_eligible": False, "attempt_evidence_hash": None},
        "lesson": {"status": "inconclusive", "effective_conditions": [], "ineffective_conditions": [],
            "counterexamples": [], "limitations": ["evidence collection incomplete"], "next_step": "collect missing evidence", "evidence_refs": []},
        "null_reasons": {},
    }
    def update(target, source):
        for key, item in source.items():
            if key not in target:
                raise ContractError(f"unknown optimization trace field: {key}")
            if isinstance(item, dict) and isinstance(target[key], dict) and key not in {"parameters", "attributes", "shapes", "dependencies", "null_reasons", "route"}:
                update(target[key], item)
            else:
                target[key] = deepcopy(item)
    update(value, groups)
    for path in _null_paths(value):
        value["null_reasons"].setdefault(path, "not applicable or not collected; consult stage status and limitations")
    validate_optimization_trace(value)
    return value


def validate_optimization_trace(value, store=None) -> dict:
    validate_trace_contract("optimization-trace", value)
    if any(path not in value["null_reasons"] for path in _null_paths(value)):
        raise ContractError("every null requires a null_reasons JSON-path entry")
    routing, result = value["routing"], value["result"]
    if routing["mode"] == "exploration":
        if routing["route"] is not None or not routing["coverage_gap"]:
            raise ContractError("exploration must have null route and a coverage gap")
        if result["graph_policy_eligible"] or result["episode_ref"] is not None:
            raise ContractError("exploration cannot enter graph policy episodes")
    else:
        from .contracts import RouteDecision
        if routing["route"] is None or routing["coverage_gap"] is not None:
            raise ContractError("graph trace requires a route and null coverage_gap")
        RouteDecision.from_dict(routing["route"])
        if result["exploration_outcome_ref"] is not None:
            raise ContractError("graph trace cannot claim an exploration outcome")
    validation = value["validation"]
    if validation["passed_count"] > validation["case_count"]:
        raise ContractError("passed_count exceeds case_count")
    if value["lesson"]["status"] != "inconclusive" and not value["lesson"]["evidence_refs"]:
        raise ContractError("supported/refuted lessons require evidence references")
    if result["graph_policy_eligible"] and result["episode_ref"] is None:
        raise ContractError("graph policy eligibility requires a finalized episode")
    _verify_refs(value, store)
    if store and result["episode_ref"]:
        row = store.connection.execute("SELECT candidate_id, payload_json FROM episodes WHERE episode_hash=?", (result["episode_ref"],)).fetchone()
        if row is None or row[0] != value["identity"]["candidate_id"]:
            raise StoreError("episode_ref does not identify this candidate in the store")
        from .contracts import CandidateEpisode
        from .jsonio import to_primitive
        episode = CandidateEpisode.from_dict(json.loads(row[1]))
        if (routing["route"] != to_primitive(episode.draft.route) or
                value["intervention"]["parameters"] != episode.draft.parameters or
                value["provenance"]["patch_hash"] != episode.draft.patch_artifact_hash or
                value["provenance"]["baseline_source_hash"] != episode.draft.source_hashes.baseline or
                value["provenance"]["candidate_source_hash"] != episode.draft.source_hashes.candidate or
                result["verdict"] != episode.outcome.verdict.value):
            raise StoreError("summary route/parameters/source/patch/verdict differ from finalized episode")
    if store and result["exploration_outcome_ref"]:
        outcome = json.loads(store.verify_artifact(result["exploration_outcome_ref"]).read_text())
        validate_trace_contract("exploration-outcome", outcome)
        if outcome["candidate_id"] != value["identity"]["candidate_id"] or outcome["verdict"] != result["verdict"]:
            raise StoreError("summary and exploration outcome disagree")
        from .exploration import ExplorationGate
        request = json.loads(store.verify_artifact(outcome["request_hash"]).read_text())
        expected = next((item for item in ExplorationGate().evaluate(request, store=store)
                         if item["candidate_id"] == outcome["candidate_id"]), None)
        if expected != outcome:
            raise StoreError("summary references an exploration outcome that does not replay")
        candidate = next(item for item in request["candidates"] if item["candidate_id"] == outcome["candidate_id"])
        if (value["provenance"]["patch_hash"] != candidate["patch_artifact_hash"] or
                value["provenance"]["baseline_source_hash"] != candidate["source_hashes"]["baseline"] or
                value["provenance"]["candidate_source_hash"] != candidate["source_hashes"]["candidate"] or
                value["intervention"]["handler"]["id"] != candidate["handler_id"] or
                value["intervention"]["handler"]["version"] != candidate["handler_version"] or
                value["intervention"]["parameters"] != candidate["parameters"]):
            raise StoreError("summary handler/parameters/source/patch differ from frozen exploration candidate")
        for key in ("speedup", "speedup_lcb"):
            if result[key] is not None and result[key] != outcome[key]:
                raise StoreError(f"summary {key} differs from machine outcome")
    return value


def write_optimization_trace(path, record, store=None) -> dict:
    validate_optimization_trace(record, store)
    path = Path(path)
    with _locked(path):
        records = _read_lines(path)
        for existing in records:
            validate_optimization_trace(existing, store)
            if existing["identity"]["attempt_id"] == record["identity"]["attempt_id"]:
                if existing != record:
                    raise StoreError("attempt summary is immutable; use a new attempt id")
                return existing
        _append(path, record)
    return record


def write_optimization_traces(path, records, store=None) -> dict:
    """Atomically merge a batch of immutable summaries in input order.

    Every merged summary is fully validated, including CAS and gate replay, on
    every call. No verification state survives the call. Identical retries are
    deduplicated; an existing stream with duplicate attempt IDs is rejected.
    """
    path = Path(path)
    with _locked(path):
        existing = _read_lines(path)
        merged, by_attempt = [], {}

        def attempt_id(record):
            if (not isinstance(record, dict) or not isinstance(record.get("identity"), dict)
                    or not isinstance(record["identity"].get("attempt_id"), str)):
                raise ContractError("optimization trace requires identity.attempt_id")
            return record["identity"]["attempt_id"]

        for record in existing:
            identifier = attempt_id(record)
            if identifier in by_attempt:
                raise StoreError("duplicate attempt summary in existing stream")
            by_attempt[identifier] = record
            merged.append(record)
        for record in records:
            record = require_json_value(record)
            identifier = attempt_id(record)
            if identifier in by_attempt:
                # Python equality conflates JSON booleans and numbers. A retry
                # must preserve canonical content, not merely compare equal.
                if canonical_json(by_attempt[identifier]) != canonical_json(record):
                    raise StoreError("attempt summary is immutable; use a new attempt id")
            else:
                by_attempt[identifier] = record
                merged.append(record)

        # Validate the complete result once, including records absent from the
        # incoming batch. An idempotent retry must still detect CAS tampering.
        for record in merged:
            validate_optimization_trace(record, store)
        if not path.exists() or len(merged) != len(existing):
            _atomic_jsonl(path, merged)
        # Also finish durability on an identical retry after a previous call
        # installed its file but failed before syncing the directory entry.
        directory_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    return {"valid": True, "attempt_count": len(merged)}


def verify_optimization_traces(path, store=None) -> dict:
    records = _read_lines(Path(path))
    attempts = set()
    for record in records:
        validate_optimization_trace(record, store)
        identity = tuple(record["identity"][key] for key in ("run_id", "task_id", "session_id", "attempt_id"))
        if identity in attempts:
            raise StoreError("duplicate attempt summary")
        attempts.add(identity)
    return {"valid": True, "attempt_count": len(records)}


def export_episodes(store: EpisodeStore, output) -> dict:
    payloads = list(store.iter_payloads())
    with _locked(Path(output)):
        _atomic_jsonl(Path(output), (json.loads(payload) for payload in payloads))
    return {"valid": True, "episode_count": len(payloads), "output": str(output)}
