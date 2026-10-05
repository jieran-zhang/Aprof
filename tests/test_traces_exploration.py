from __future__ import annotations

import copy
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from aprof_runtime.contracts import GateConfig, GateEvidence
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.exploration import (ExplorationGate, freeze_exploration_manifest,
                                      mechanism_alignment_from_artifacts, verify_exploration)
from aprof_runtime.gates import evaluate_candidate_evidence
from aprof_runtime.jsonio import content_hash
from aprof_runtime.store import EpisodeStore
from aprof_runtime.trace_schemas import SCHEMAS
from aprof_runtime.traces import (TraceWriter, export_episodes, make_optimization_trace,
    merge_trace_streams, recover_trace_tail, register_json_artifact, validate_optimization_trace,
    validate_trace_contract, verify_optimization_traces, verify_trace, write_optimization_trace)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def store(tmp_path):
    with EpisodeStore(tmp_path / "episodes.sqlite") as store:
        yield store


def writer(tmp_path, store=None, session="session"):
    return TraceWriter(tmp_path / f"{session}.jsonl", run_id="run", task_id="task", session_id=session, store=store)


def decision():
    return {"action": "profile", "reason": "need device measurements", "evidence_refs": []}


def test_schema_mirrors_and_strict_event_payloads(tmp_path):
    for name, schema in SCHEMAS.items():
        assert json.loads((ROOT / "schemas" / (name + ".schema.json")).read_text()) == schema
    event = writer(tmp_path).append("next_step_decided", decision())
    event["payload"]["invented"] = True
    with pytest.raises(ContractError, match="Additional properties"):
        validate_trace_contract("trace-event", event)


def test_nonfinite_anywhere_rejected(tmp_path):
    with pytest.raises(ContractError, match="non-finite"):
        writer(tmp_path).append("next_step_decided", {**decision(), "value": math.nan})


def test_resume_dedup_and_hash_tampering(tmp_path):
    stream = writer(tmp_path)
    first = stream.append("next_step_decided", decision(), event_id="same")
    assert writer(tmp_path).append("next_step_decided", decision(), event_id="same") == first
    with pytest.raises(StoreError, match="reused"):
        stream.append("next_step_decided", {**decision(), "reason": "different"}, event_id="same")
    writer(tmp_path).append("next_step_decided", decision())
    assert verify_trace(stream.path)["event_count"] == 2
    rows = stream.path.read_text().splitlines()
    row = json.loads(rows[0]); row["payload"]["reason"] = "tampered"
    rows[0] = json.dumps(row); stream.path.write_text("\n".join(rows) + "\n")
    with pytest.raises(StoreError, match="hash mismatch"):
        verify_trace(stream.path)


def test_concurrent_writers_serialize_chain(tmp_path):
    def append(index):
        return writer(tmp_path).append("next_step_decided", decision(), event_id=str(index))
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(append, range(16)))
    assert verify_trace(writer(tmp_path).path)["event_count"] == 16


def test_cas_does_not_close_a_recycled_descriptor(tmp_path, store, monkeypatch):
    import aprof_runtime.store as store_module
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("original source")
    survivor = tmp_path / "survivor.txt"
    survivor.write_text("descriptor belongs to another operation")
    original_mkstemp = store_module.tempfile.mkstemp
    original_file_hash = store_module.file_hash
    observed = {}
    def capture_fd(*args, **kwargs):
        result = original_mkstemp(*args, **kwargs)
        observed["temporary_fd"] = result[0]
        return result
    def hash_then_reuse(path):
        result = original_file_hash(path)
        if Path(path).name.startswith(".incoming-") and "survivor_fd" not in observed:
            # The copied target has closed. This reproduces the exact descriptor
            # reuse that a concurrent TraceWriter/SQLite operation can cause.
            observed["survivor_fd"] = os.open(survivor, os.O_RDONLY)
            assert observed["survivor_fd"] == observed["temporary_fd"]
        return result
    monkeypatch.setattr(store_module.tempfile, "mkstemp", capture_fd)
    monkeypatch.setattr(store_module, "file_hash", hash_then_reuse)
    try:
        store.register_artifact(artifact)
        os.fstat(observed["survivor_fd"])
    finally:
        if "survivor_fd" in observed:
            try:
                os.close(observed["survivor_fd"])
            except OSError:
                pass


def test_concurrent_cas_and_trace_writers_preserve_all_descriptors(tmp_path):
    store_path = tmp_path / "shared.sqlite"
    with EpisodeStore(store_path):
        pass
    def collect(worker_id):
        with EpisodeStore(store_path) as local_store:
            stream = writer(tmp_path, local_store)
            for attempt in range(12):
                path = tmp_path / f"worker-{worker_id}-{attempt}.txt"
                path.write_text(f"worker={worker_id}, attempt={attempt}\n" * 32)
                digest = local_store.register_artifact(path)
                stream.append("next_step_decided", {**decision(), "evidence_refs": [digest]},
                              event_id=f"worker-{worker_id}-{attempt}")
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(collect, range(4)))
    with EpisodeStore(store_path) as final_store:
        assert verify_trace(writer(tmp_path).path, final_store)["event_count"] == 48
        assert final_store.connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0] == 48
        final_store.verify_integrity()


def test_cas_missing_and_changed_artifact_fail(tmp_path, store):
    path = tmp_path / "profile.csv"; path.write_text("duration_ns\n12\n")
    digest = store.register_artifact(path)
    stream = writer(tmp_path, store)
    stream.append("next_step_decided", {**decision(), "evidence_refs": [digest]})
    store.object_path(digest).write_text("modified")
    with pytest.raises(StoreError, match="does not match"):
        verify_trace(stream.path, store)


def test_coordinator_append_checks_new_refs_and_exhaustive_verify_checks_history(tmp_path, store):
    source = tmp_path / 'old.txt'; source.write_text('original')
    digest = store.register_artifact(source)
    stream = TraceWriter(tmp_path / 'collecting.jsonl', run_id='r', task_id='t',
        session_id='s', store=store, verify_history_artifacts=False)
    stream.append('next_step_decided', {**decision(), 'evidence_refs': [digest]}, event_id='original')
    store.object_path(digest).write_text('corrupt')
    stream.append('next_step_decided', decision())
    with pytest.raises(StoreError, match='does not match'):
        stream.append('next_step_decided', {**decision(), 'evidence_refs': [digest]})
    with pytest.raises(StoreError, match='does not match'):
        stream.append('next_step_decided', {**decision(), 'evidence_refs': [digest]}, event_id='original')
    with pytest.raises(StoreError, match='does not match'):
        verify_trace(stream.path, store)


def test_tail_recovery_preserves_interrupted_bytes(tmp_path, store):
    stream = writer(tmp_path, store)
    stream.append("next_step_decided", decision())
    with stream.path.open("ab") as out:
        out.write(b'{"schema_version":')
    with pytest.raises(StoreError, match="incomplete final"):
        verify_trace(stream.path)
    result = recover_trace_tail(stream.path, store)
    assert result["discarded_bytes"] > 0
    assert store.verify_artifact(result["artifact_ref"]).read_bytes() == b'{"schema_version":'
    stream.append("execution_interrupted", {"stage": "build", "reason": "SSH transport lost", "execution": None})
    assert verify_trace(stream.path, store)["event_count"] == 2


def test_merge_deduplicates_without_rehashing_or_truncation(tmp_path):
    first, second = writer(tmp_path, session="a"), writer(tmp_path, session="b")
    e = first.append("next_step_decided", decision())
    second.append("next_step_decided", decision())
    out = tmp_path / "merged.jsonl"
    assert merge_trace_streams([first.path, first.path, second.path], out)["event_count"] == 2
    assert json.loads(out.read_text().splitlines()[0])["event_hash"] == e["event_hash"]
    with pytest.raises(StoreError, match="discard"):
        merge_trace_streams([first.path], out)


def summary(digest):
    return make_optimization_trace({"run_id": "run", "task_id": "task", "session_id": "session",
        "attempt_id": "a1", "candidate_id": "c1", "operator": "exp", "split": "train", "source_parent_hash": digest})


def test_summary_identity_missing_reason_and_graph_separation(tmp_path, store):
    digest = register_json_artifact(store, {"source": "baseline"})
    record = summary(digest)
    out = tmp_path / "optimization_traces.jsonl"
    write_optimization_trace(out, record, store)
    write_optimization_trace(out, record, store)
    assert verify_optimization_traces(out, store)["attempt_count"] == 1
    record["null_reasons"].clear()
    with pytest.raises(ContractError, match="every null"):
        validate_optimization_trace(record)
    record = summary(digest); record["result"]["graph_policy_eligible"] = True
    with pytest.raises(ContractError, match="cannot enter"):
        validate_optimization_trace(record)
    record = summary(digest); record["lesson"]["status"] = "supported"
    with pytest.raises(ContractError, match="require evidence"):
        validate_optimization_trace(record)


def request_fixture(tmp_path, store, *, failed=False):
    source = register_json_artifact(store, {"source": "baseline"})
    candidate_source = register_json_artifact(store, {"source": "candidate"})
    patch = register_json_artifact(store, {"patch": "change tiling"})
    stream = writer(tmp_path, store)
    stream.append("candidate_proposed", {"mode": "exploration", "hypothesis": "one tile reduces launch overhead",
        "source_parent_hash": source, "patch_hash": patch, "handler_id": "handler.test", "handler_version": "1",
        "parameters": {"tile": 512}, "expected_effects": ["reduce launch count"], "alternatives": [],
        "coverage_gap": "handler not in graph"}, attempt_id="a1", candidate_id="c1")
    fragment = stream.seal_attempt("a1")
    candidate = {"candidate_id": "c1", "session_id": "session", "source_hashes": {"baseline": source, "candidate": candidate_source},
        "patch_artifact_hash": patch, "handler_id": "handler.test", "handler_version": "1", "parameters": {"tile": 512},
        "coverage_gap": "handler not in graph", "attempt_evidence_hash": fragment}
    manifest = freeze_exploration_manifest(store, run_id="run", task_id="task", split="train", candidates=[candidate])
    evidence = {"candidate_id": "c1", **{key: "passed" for key in
        ("static_review", "build", "accuracy", "runtime", "semantic", "scope", "portability")},
        "artifacts": {}, "baseline_samples_ns": [], "candidate_samples_ns": [], "heldout_regressions": [], "mechanism_alignment": True}
    if failed:
        evidence.update(build="failed", accuracy="not_run", runtime="not_run")
    else:
        a, b = [100.0] * 30, [80.0] * 30
        # Floating point projection must match actual equal-case log aggregation.
        suite_a = [math.exp(math.log(100.0))] * 30
        suite_b = [math.exp(math.log(80.0))] * 30
        report = {"unit": "ns", "aggregation": "equal_case_geometric_mean_per_round", "case_ids": list(range(1, 21)), "stable": True,
            "per_case": [{"case_id": i, "baseline_samples_ns": a, "candidate_samples_ns": b} for i in range(1, 21)],
            "gate_projection": {"baseline_samples_ns": suite_a, "candidate_samples_ns": suite_b, "heldout_regressions": [math.exp(math.log(.8)) - 1] * 20}}
        report_hash = register_json_artifact(store, report)
        evidence.update(report["gate_projection"])
        evidence["artifacts"] = {"build_log": source, "accuracy_report": source, "measurement_report": report_hash}
        profiles = []
        for label, duration in (("baseline", 20.0), ("candidate", 10.0)):
            csv_path = tmp_path / f"{label}.csv"
            csv_path.write_text(f"Name,duration(us)\ncompute,{duration}\ncompute,{duration}\n")
            csv_hash = store.register_artifact(csv_path)
            profiles.append(register_json_artifact(store, {"schema_version": "1.0.0", "case_id": 1,
                "kernel": "compute", "metrics": {"duration": {"value": duration, "unit": "us",
                    "source_artifact_hash": csv_hash, "field": "duration(us)", "aggregation": "mean", "samples": [duration, duration]}}}))
        evidence["artifacts"]["mechanism_report"] = register_json_artifact(store, {"schema_version": "1.0.0", "candidate_id": "c1",
            "hypothesis_basis": "heuristic", "metrics": [{"name": "duration", "baseline": 20.0, "candidate": 10.0,
                "expected_direction": "decrease", "unit": "us", "baseline_profile_hash": profiles[0], "candidate_profile_hash": profiles[1]}]})
    return {"schema_version": "1.0.0", "frozen_manifest_hash": manifest, "candidates": [candidate], "evidence": [evidence], "config": {"bootstrap_resamples": 100}}


def test_exploration_gate_replay_and_no_episode_pollution(tmp_path, store):
    request = request_fixture(tmp_path, store)
    outcomes = ExplorationGate().evaluate(request, store=store)
    assert outcomes[0]["verdict"] == "production_safe_gain"
    assert outcomes[0]["eligible"] is True
    assert outcomes[0]["graph_policy_eligible"] is False
    assert outcomes[0]["episode_ref"] is None
    assert "selected_as_best" not in outcomes[0]
    assert verify_exploration(request, outcomes, store=store)["valid"]
    assert store.connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 0
    out = tmp_path / "episodes.jsonl"
    assert export_episodes(store, out)["episode_count"] == 0
    assert out.read_bytes() == b""


def test_exploration_failure_is_preserved(tmp_path, store):
    request = request_fixture(tmp_path, store, failed=True)
    outcome = ExplorationGate().evaluate(request, store=store)[0]
    assert outcome["verdict"] == "build_failed"
    assert outcome["pair_count"] == 0


def test_exploration_rejects_frozen_source_handler_mutation(tmp_path, store):
    request = request_fixture(tmp_path, store, failed=True)
    request["candidates"][0]["parameters"]["tile"] = 1024
    with pytest.raises(ContractError, match="frozen manifest"):
        ExplorationGate().evaluate(request, store=store)
    # Re-freezing a manifest cannot conceal disagreement with the sealed proposal.
    request["frozen_manifest_hash"] = freeze_exploration_manifest(store, run_id="run", task_id="task", split="train", candidates=request["candidates"])
    with pytest.raises(ContractError, match="differ from attempt proposal"):
        ExplorationGate().evaluate(request, store=store)


def test_exploration_refuses_invented_route_or_weakened_gate(tmp_path, store):
    request = request_fixture(tmp_path, store, failed=True)
    request["candidates"][0]["route"] = {}
    with pytest.raises(ContractError, match="Additional properties"):
        ExplorationGate().evaluate(request, store=store)
    del request["candidates"][0]["route"]
    request["config"]["max_cv"] = .10
    with pytest.raises(ContractError):
        ExplorationGate().evaluate(request, store=store)


def test_projection_tampering_and_hidden_case_jitter_rejected(tmp_path, store):
    request = request_fixture(tmp_path, store)
    evidence = request["evidence"][0]
    evidence["candidate_samples_ns"][0] = 1.0
    with pytest.raises(ContractError, match="differ from the bound"):
        ExplorationGate().evaluate(request, store=store)
    report = json.loads(store.verify_artifact(evidence["artifacts"]["measurement_report"]).read_text())
    evidence.update(report["gate_projection"])
    report["per_case"][0]["candidate_samples_ns"][0] = 8000.0
    evidence["artifacts"]["measurement_report"] = register_json_artifact(store, report)
    with pytest.raises(ContractError, match="instability was hidden"):
        ExplorationGate().evaluate(request, store=store)


def test_outcome_tampering_cannot_be_rehashed_into_acceptance(tmp_path, store):
    request = request_fixture(tmp_path, store, failed=True)
    outcomes = list(ExplorationGate().evaluate(request, store=store))
    outcomes[0]["verdict"] = "production_safe_gain"
    outcomes[0]["outcome_hash"] = content_hash({key: value for key, value in outcomes[0].items() if key != "outcome_hash"})
    with pytest.raises(StoreError, match="do not reproduce"):
        verify_exploration(request, outcomes, store=store)


def test_shared_gate_retains_v1_arithmetic(tmp_path, store):
    request = request_fixture(tmp_path, store)
    outcome = ExplorationGate().evaluate(request, store=store)[0]
    shared = evaluate_candidate_evidence("c1", GateEvidence.from_dict(request["evidence"][0]), GateConfig.from_dict(request["config"]))
    assert outcome["speedup"] == shared.speedup
    assert outcome["speedup_lcb"] == shared.speedup_lcb
    assert outcome["utility"] == shared.utility
    assert outcome["state_path"] == list(shared.state_path)


def test_missing_profile_cannot_be_agent_asserted_into_alignment(tmp_path, store):
    request = request_fixture(tmp_path, store)
    del request["evidence"][0]["artifacts"]["mechanism_report"]
    assert request["evidence"][0]["mechanism_alignment"] is True
    assert ExplorationGate().evaluate(request, store=store)[0]["verdict"] == "attribution_uncertain"


def test_profile_claims_must_reproduce_bound_raw_csv(tmp_path, store):
    request = request_fixture(tmp_path, store)
    evidence = request["evidence"][0]
    report = json.loads(store.verify_artifact(evidence["artifacts"]["mechanism_report"]).read_text())
    profile = json.loads(store.verify_artifact(report["metrics"][0]["candidate_profile_hash"]).read_text())
    profile["metrics"]["duration"]["samples"] = [1.0, 1.0]
    profile["metrics"]["duration"]["value"] = 1.0
    report["metrics"][0]["candidate_profile_hash"] = register_json_artifact(store, profile)
    report["metrics"][0]["candidate"] = 1.0
    evidence["artifacts"]["mechanism_report"] = register_json_artifact(store, report)
    with pytest.raises(ContractError, match="samples differ from bound raw"):
        mechanism_alignment_from_artifacts(evidence, store)
