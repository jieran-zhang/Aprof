"""Self-contained JSON Schema 2020-12 contracts for local trace collection.

The checked-in schemas/ documents are exact mirrors (tested), while keeping the
definitions here makes wheel installs independent of the repository layout.
"""
from __future__ import annotations

from copy import deepcopy

VERSION = "1.0.0"
STRING = {"type": "string", "minLength": 1}
HASH = {"type": "string", "pattern": "^sha256:[0-9a-f]{64}$"}
NULL = {"type": "null"}
NUMBER = {"type": "number"}
BOOL = {"type": "boolean"}
TIME = {"type": "string", "format": "date-time"}
JSON_MAP = {"type": "object"}  # Deliberately open operator parameters/attributes.


def nullable(schema):
    return {"anyOf": [schema, NULL]}


def array(schema, **kwargs):
    return {"type": "array", "items": schema, **kwargs}


def obj(properties, required=None):
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties) if required is None else required}


STRINGS = array(STRING)
HASHES = array(HASH, uniqueItems=True)
STATUS = {"enum": ["passed", "failed", "not_run", "interrupted"]}
EXECUTION = obj({
    "argv": array(STRING, minItems=1), "cwd": STRING, "host": STRING,
    "device": nullable(STRING), "started_at": TIME, "finished_at": TIME,
    "exit_status": nullable({"type": "integer"}), "log_ref": nullable(HASH),
    "reason": nullable(STRING),
})
KNOWLEDGE_ENTRY = obj({"path": STRING, "content_hash": HASH, "purpose": STRING})
STAGE = obj({"status": STATUS, "reason": nullable(STRING), "artifact_refs": HASHES})
RUNTIME_STATUS = {"enum": ["passed", "failed", "not_run"]}
RUNTIME_EVIDENCE = obj({"candidate_id": STRING,
    **{key: RUNTIME_STATUS for key in ("static_review", "build", "accuracy", "runtime", "semantic", "scope", "portability")},
    "baseline_samples_ns": array({"type": "number", "exclusiveMinimum": 0}),
    "candidate_samples_ns": array({"type": "number", "exclusiveMinimum": 0}),
    "mechanism_alignment": nullable(BOOL), "heldout_regressions": array(NUMBER),
    "artifacts": {"type": "object", "additionalProperties": HASH}},
    ["candidate_id", "static_review", "build", "accuracy", "runtime", "semantic", "scope", "portability", "artifacts"])
RUNTIME_CONFIG = obj({
    "max_cv": {"type": "number", "minimum": 0, "maximum": .05},
    "max_heldout_regression": {"type": "number", "minimum": 0, "maximum": .03},
    "require_mechanism_alignment": {"const": True},
    "required_artifacts": {**array(STRING, uniqueItems=True), "allOf": [
        {"contains": {"const": name}} for name in ("build_log", "accuracy_report", "measurement_report")]},
    "min_pairs": {"type": "integer", "minimum": 30},
    "lcb_confidence": {"type": "number", "exclusiveMinimum": .5, "exclusiveMaximum": 1},
    "min_speedup_lcb": {"type": "number", "minimum": 1.03},
    "bootstrap_resamples": {"type": "integer", "minimum": 100}}, [])
ROUTE = obj({"graph_version": STRING, "policy_version": STRING, "selected_edge_id": STRING,
    "behavior_probability": {"type": "number", "minimum": 0, "maximum": 1},
    "selection_mode": {"enum": ["argmax", "sample"]}, "selection_seed": nullable({"type": "integer"}),
    "selected_mechanism_id": STRING, "mechanism_derivation": {"const": "fixed_supports_refutes_tri_state_v1"},
    "mechanism_scores": {"type": "object", "additionalProperties": NUMBER},
    "candidates": array(obj({"edge_id": STRING, "source_id": STRING, "target_id": STRING,
        "logit": NUMBER, "probability": {"type": "number", "minimum": 0, "maximum": 1},
        "allowed": BOOL, "mask_reasons": STRINGS}), minItems=1)})

EVENT_PAYLOADS = {
    "task_started": obj({"operator": STRING, "split": {"enum": ["train", "validation"]},
        "knowledge_manifest_hash": nullable(HASH), "baseline_source_hash": HASH,
        "budget": obj({key: {"type": "integer", "minimum": 0} for key in
            ("candidate_limit", "build_limit", "timing_limit", "full_profile_limit")})}),
    "knowledge_loaded": obj({"entries": array(KNOWLEDGE_ENTRY, minItems=1)}),
    "baseline_validated": obj({"status": STATUS, "case_count": {"type": "integer", "minimum": 0},
        "passed_count": {"type": "integer", "minimum": 0}, "execution": nullable(EXECUTION), "reason": nullable(STRING)}),
    "profile_collected": obj({"stage": STRING, "status": STATUS, "profile_hash": nullable(HASH),
        "execution": EXECUTION, "reason": nullable(STRING)}),
    "diagnosis_recorded": obj({"symptoms": STRINGS, "mechanisms": STRINGS,
        "assessment_basis": {"enum": ["measured", "inferred", "heuristic", "manual"]},
        "supporting_evidence": HASHES, "contradicting_evidence": HASHES,
        "missing_evidence": STRINGS, "source_anchors": STRINGS}),
    "candidate_proposed": obj({"mode": {"enum": ["graph", "exploration"]}, "hypothesis": STRING,
        "source_parent_hash": HASH, "patch_hash": HASH, "handler_id": STRING,
        "handler_version": STRING, "parameters": JSON_MAP, "expected_effects": STRINGS,
        "alternatives": STRINGS, "coverage_gap": nullable(STRING)}),
    "stage_completed": obj({"stage": STRING, "status": STATUS, "execution": nullable(EXECUTION),
        "reason": nullable(STRING), "artifact_refs": HASHES}),
    "next_step_decided": obj({"action": STRING, "reason": STRING, "evidence_refs": HASHES}),
    "attempt_finished": obj({"verdict": STRING, "summary_ref": nullable(HASH), "reason": STRING}),
    "task_finished": obj({"status": {"enum": ["completed", "blocked", "interrupted"]},
        "reason": STRING, "attempt_count": {"type": "integer", "minimum": 0}, "summary_ref": nullable(HASH)}),
    "execution_interrupted": obj({"stage": STRING, "reason": STRING, "execution": nullable(EXECUTION)}),
}


def document(name, body):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": f"https://aprof.local/schemas/{name}.schema.json", **body}


TRACE_EVENT = document("trace-event", obj({
    "schema_version": {"const": VERSION}, "event_id": STRING, "run_id": STRING,
    "task_id": STRING, "session_id": STRING, "attempt_id": nullable(STRING),
    "candidate_id": nullable(STRING), "sequence": {"type": "integer", "minimum": 1},
    "timestamp": TIME, "event_type": {"enum": list(EVENT_PAYLOADS)}, "payload": {},
    "artifact_refs": HASHES, "previous_event_hash": HASH, "event_hash": HASH,
}))
TRACE_EVENT["allOf"] = [{"if": {"properties": {"event_type": {"const": name}}},
                         "then": {"properties": {"payload": payload}}}
                        for name, payload in EVENT_PAYLOADS.items()]

OPTIMIZATION_TRACE = document("optimization-trace", obj({
    "schema_version": {"const": VERSION},
    "identity": obj({"run_id": STRING, "task_id": STRING, "session_id": STRING,
        "attempt_id": STRING, "candidate_id": STRING, "operator": STRING,
        "split": {"enum": ["train", "validation"]}, "parent_attempt_id": nullable(STRING),
        "source_parent_hash": HASH}),
    "provenance": obj({"dependencies": {"type": "object", "additionalProperties": STRING}, **{
        key: nullable(HASH) for key in ("graph_hash", "skill_manifest_hash", "prompt_hash",
        "producer_hash", "harness_hash", "baseline_source_hash", "candidate_source_hash", "patch_hash")}}),
    "knowledge": obj({"manifest_hash": nullable(HASH), "loaded": array(KNOWLEDGE_ENTRY)}),
    "workload": obj({"manifest_hash": nullable(HASH), "case_ids": array({"type": "integer", "minimum": 1}, uniqueItems=True),
        "shapes": JSON_MAP, "dtypes": STRINGS, "layouts": STRINGS, "attributes": JSON_MAP,
        "accuracy_contract": nullable(STRING), "hardware_fingerprint": nullable(STRING)}),
    "diagnosis": deepcopy(EVENT_PAYLOADS["diagnosis_recorded"]),
    "intervention": obj({"intent": STRING, "rationale": STRING, "expected_effects": STRINGS,
        "handler": obj({"id": STRING, "version": STRING, "producer_hash": nullable(HASH)}),
        "parameters": JSON_MAP, "alternatives": STRINGS}),
    "routing": obj({"mode": {"enum": ["graph", "exploration"]}, "route": nullable(ROUTE), "coverage_gap": nullable(STRING)}),
    "validation": obj({**{name: STAGE for name in ("static_review", "build", "correctness", "runtime", "timing", "profile")},
        "case_count": {"type": "integer", "minimum": 0}, "passed_count": {"type": "integer", "minimum": 0},
        "timing_case_ids": array({"type": "integer", "minimum": 1}, uniqueItems=True)}),
    "result": obj({"verdict": STRING, "first_failed_stage": nullable(STRING),
        "speedup": nullable(NUMBER), "speedup_lcb": nullable(NUMBER), "max_regression": nullable(NUMBER),
        "machine_outcome_ref": nullable(HASH), "episode_ref": nullable(HASH),
        "exploration_outcome_ref": nullable(HASH), "graph_policy_eligible": BOOL,
        "attempt_evidence_hash": nullable(HASH)}),
    "lesson": obj({"status": {"enum": ["supported", "refuted", "inconclusive"]},
        "effective_conditions": STRINGS, "ineffective_conditions": STRINGS, "counterexamples": STRINGS,
        "limitations": STRINGS, "next_step": STRING, "evidence_refs": HASHES}),
    "null_reasons": {"type": "object", "additionalProperties": STRING},
}))

EXPLORATION_CANDIDATE = obj({"candidate_id": STRING, "session_id": STRING,
    "source_hashes": obj({"baseline": HASH, "candidate": HASH}), "patch_artifact_hash": HASH,
    "handler_id": STRING, "handler_version": STRING, "parameters": JSON_MAP,
    "coverage_gap": STRING, "attempt_evidence_hash": HASH})
FROZEN_MANIFEST = document("exploration-manifest", obj({
    "schema_version": {"const": VERSION}, "run_id": STRING, "task_id": STRING,
    "split": {"enum": ["train", "validation"]}, "frozen_at": TIME,
    "candidates": array(EXPLORATION_CANDIDATE, minItems=1),
}))
EXPLORATION_REQUEST = document("exploration-request", obj({
    "schema_version": {"const": VERSION}, "frozen_manifest_hash": HASH,
    "candidates": array(EXPLORATION_CANDIDATE, minItems=1),
    "evidence": array(RUNTIME_EVIDENCE, minItems=1), "config": RUNTIME_CONFIG,
}))
EXPLORATION_OUTCOME = document("exploration-outcome", obj({
    "schema_version": {"const": VERSION}, "candidate_id": STRING, "frozen_manifest_hash": HASH,
    "request_hash": HASH, "verdict": STRING, "state_path": STRINGS,
    **{key: NUMBER for key in ("baseline_median_ns", "candidate_median_ns", "speedup", "speedup_lcb", "measurement_cv", "utility")},
    "pair_count": {"type": "integer", "minimum": 0}, "measurement_protocol": STRING,
    "eligible": BOOL, "graph_policy_eligible": {"const": False}, "episode_ref": NULL,
    "reasons": STRINGS, "outcome_hash": HASH,
}))

NORMALIZED_PROFILE_V1 = document("normalized-profile", obj({"schema_version": {"const": VERSION},
    "case_id": {"type": "integer", "minimum": 1}, "kernel": STRING,
    "metrics": {"type": "object", "minProperties": 1, "additionalProperties": obj({
        "value": NUMBER, "unit": STRING, "source_artifact_hash": HASH, "field": STRING,
        "aggregation": {"enum": ["mean", "median", "sum", "min", "max"]},
        "samples": array(NUMBER, minItems=1)})}}))
# Version 1.1 separates core/record reduction from independent process captures.
REDUCER = {"enum": ["mean", "median", "sum", "min", "max"]}
BACKEND = {"enum": ["msprof", "npu-compute"]}
CAPTURE_RUN = obj({"argv": array(STRING, minItems=1), "exit_code": {"type": "integer"}, "log_hash": HASH})
CAPTURE_FILE = obj({"path": STRING, "artifact_hash": HASH,
    "format": {"enum": ["csv", "jsonl", "json", "binary"]}, "kernel": STRING})
CAPTURE_MANIFEST = document("capture-manifest", obj({
    "schema_version": {"const": "1.0.0"}, "backend": BACKEND,
    "collector_hash": HASH, "protocol_version": {"const": "independent_capture_v1"},
    "role": {"enum": ["baseline", "candidate"]}, "case_id": {"type": "integer", "minimum": 1},
    "kernel": STRING, "workload_hash": HASH, "source_hash": HASH, "binary_hash": HASH,
    "hardware_hash": HASH, "tool": obj({"executable_hash": HASH, "version": STRING}),
    "policy": obj({"warmups": {"type": "integer", "minimum": 0},
        "repeats": {"type": "integer", "minimum": 1}, "sections": array(STRING, uniqueItems=True)}),
    "warmup_runs": array(CAPTURE_RUN),
    "captures": array(obj({**CAPTURE_RUN["properties"], "capture_id": STRING,
        "collection": STRING, "files": array(CAPTURE_FILE, minItems=1)}), minItems=1)}))
PROFILE_SOURCE = obj({"capture_id": STRING, "path": STRING, "format": {"enum": ["csv", "jsonl"]},
    "field": STRING, "where": {"type": "object", "additionalProperties": STRING}, "row_aggregation": REDUCER})
NORMALIZED_PROFILE_V11 = document("normalized-profile-v1.1", obj({
    "schema_version": {"const": "1.1.0"}, "metric_definition_version": {"const": "raw_metric_v1"}, "case_id": {"type": "integer", "minimum": 1},
    "kernel": STRING, "capture_manifest_hash": HASH,
    "metrics": {"type": "object", "minProperties": 1, "additionalProperties": obj({
        "value": nullable(NUMBER), "unit": STRING, "aggregation": REDUCER,
        "samples": array(NUMBER), "status": {"enum": ["available", "missing", "unstable"]},
        "cv": nullable(NUMBER), "sources": array(PROFILE_SOURCE, minItems=1)})}}))
NORMALIZED_PROFILE = document("normalized-profile", {"oneOf": [
    NORMALIZED_PROFILE_V1, NORMALIZED_PROFILE_V11]})
MECHANISM_REPORT = document("mechanism-report", obj({"schema_version": {"const": VERSION},
    "candidate_id": STRING, "hypothesis_basis": {"enum": ["user", "heuristic", "manual", "measured"]},
    "metrics": array(obj({"name": STRING, "baseline": NUMBER, "candidate": NUMBER,
        "expected_direction": {"enum": ["increase", "decrease"]}, "unit": STRING,
        "baseline_profile_hash": HASH, "candidate_profile_hash": HASH}), minItems=1)}))

SCHEMAS = {"trace-event": TRACE_EVENT, "optimization-trace": OPTIMIZATION_TRACE,
           "exploration-manifest": FROZEN_MANIFEST, "exploration-request": EXPLORATION_REQUEST,
           "exploration-outcome": EXPLORATION_OUTCOME, "normalized-profile": NORMALIZED_PROFILE,
           "mechanism-report": MECHANISM_REPORT, "capture-manifest": CAPTURE_MANIFEST}
