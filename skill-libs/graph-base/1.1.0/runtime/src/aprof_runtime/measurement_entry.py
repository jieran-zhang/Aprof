"""历史 Task-window 证据的只读回放边界。

This checks measurement evidence for the gate. Publication remains a separate
decision over the complete qualification campaign and installed release.
The draft collector is not selected by the marketplace/default installation.
"""
from .contracts import GateEvidence
from .errors import ContractError
from .jsonio import to_primitive
from .measurement_admission import _load, _number, _require
from .task_window_measurement_admission import (
    PROTOCOL, replay_task_window_measurement_admission, storage_budget,
)


_COMPLETION_FIELDS = {
    "schema_version", "kind", "protocol", "operator", "run_id", "session_id", "candidate_id",
    "source_hashes", "proof_ref", "measurement_report_ref", "started_at", "finished_at",
    "elapsed_seconds", "timeout_seconds", "status", "error",
}


def replay_historical_current_measurement_admission(artifact_reader, receipt_ref, *, expected, producer_resolver):
    """Full current proof/CSV/math replay with caller-authenticated historical producers."""
    from .measurement_admission import historical_producer_scope
    with historical_producer_scope(producer_resolver):
        return replay_current_measurement_admission(artifact_reader, receipt_ref, expected=expected)


def replay_current_measurement_admission(artifact_reader, receipt_ref, *, expected):
    """保留历史完成回执的完整回放；新验收不调用此兼容函数。"""
    completion = _load(artifact_reader, receipt_ref)
    _require(isinstance(completion, dict) and set(completion) == _COMPLETION_FIELDS
             and completion["schema_version"] == "1.0.0"
             and completion["kind"] == "local_measurement_completion"
             and completion["protocol"] == PROTOCOL,
             "formal admission requires a current Task-window completion")
    _require(completion["status"] == "passed" and completion["error"] is None,
             "formal admission requires a completed passing local job")
    started, finished = _number(completion["started_at"]), _number(completion["finished_at"])
    elapsed, timeout = _number(completion["elapsed_seconds"]), _number(completion["timeout_seconds"])
    _require(started < finished and 0 < elapsed <= timeout,
             "local measurement completion chronology or budget differs")
    for key, value in expected.items():
        _require(completion.get(key) == value,
                 "local measurement completion " + key + " differs from the gate request")
    proof_ref = completion["proof_ref"]
    _require(isinstance(proof_ref, str), "local measurement completion proof ref differs")
    proof = _load(artifact_reader, proof_ref)
    _require(isinstance(proof, dict) and proof.get("protocol") == PROTOCOL,
             "local measurement completion proof protocol differs")
    _require(all(isinstance(proof.get(key), str) for key in
                 ("registration_ref", "raw_ref", "measurement_report_ref")),
             "local measurement completion proof references differ")
    for key in ("operator", "run_id", "session_id", "candidate_id", "source_hashes",
                "measurement_report_ref"):
        _require(proof.get(key) == completion[key],
                 "local measurement completion proof " + key + " differs")
    registration = _load(artifact_reader, proof["registration_ref"])
    _require(isinstance(registration, dict) and isinstance(registration.get("profile_storage_ref"), str),
             "local measurement completion registration differs")
    storage = _load(artifact_reader, registration["profile_storage_ref"])
    raw = _load(artifact_reader, proof["raw_ref"])
    _require(isinstance(storage, dict) and isinstance(raw, dict)
             and "collection_started_at" in storage and "timeout_seconds" in storage
             and "finished_at" in raw, "local measurement completion collection references differ")
    _require(storage["collection_started_at"] == started and storage["timeout_seconds"] == timeout
             and started <= _number(raw["finished_at"]) <= finished,
             "local measurement completion does not bound collection and proof")
    config = _load(artifact_reader, proof["config_ref"])
    budget = storage_budget(artifact_reader, storage, config)
    if "budget_binding" in storage:
        _require(finished <= budget["wall_deadline"], "completion exceeded original parent budget")
    result = replay_task_window_measurement_admission(
        artifact_reader, proof_ref, expected={
            **{key: completion[key] for key in ("operator", "run_id", "session_id", "candidate_id",
                                                 "source_hashes", "measurement_report_ref")},
            **expected,
        })
    _require(result["valid"] is True, "current Task-window measurement replay failed")
    return {**result, "completion_ref": receipt_ref}


def verify_measurement_admission(evidence: GateEvidence, artifact_reader, *,
                                 source_hashes, session_id=None, run_id=None) -> None:
    """旧 gate 不再接纳新的计时样本；无计时失败记录仍可保存。"""
    evidence = GateEvidence.from_dict(to_primitive(evidence))
    if not evidence.baseline_samples_ns and not evidence.candidate_samples_ns:
        return
    raise ContractError(
        "1.1.0 的新计时验收请使用 aprofctl timing finalize；"
        "旧 Task-window/配对 gate 仅供历史回放，不接纳新性能结果"
    )
