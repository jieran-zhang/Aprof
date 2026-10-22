"""Current gate binding to prospective Task-window evidence, with no hardware."""
from copy import deepcopy
import json

import pytest

from aprof_runtime.contracts import GateEvidence, GateRequest
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.errors import ContractError
from aprof_runtime.gates import CandidateGate
from aprof_runtime.measurement_entry import verify_measurement_admission
import aprof_runtime.measurement_entry as entry
from aprof_runtime.task_window_measurement_admission import summarize_task_window_raw
from aprof_runtime.traces import register_json_artifact
from test_runtime import finalization_inputs, noop_request_dict, request_dict
from test_shared_measurement_admission import archive, draft
from test_task_window_measurement_admission import window_archive


def _evidence(window_archive):
    store, raw, config, registration, calibration, seal, expected, *_ = window_archive
    proof_ref = seal()
    proof = json.loads(store.verify_artifact(proof_ref).read_text())
    storage = json.loads(store.verify_artifact(registration['profile_storage_ref']).read_text())
    receipt = {'schema_version': '1.0.0', 'kind': 'local_measurement_completion',
        'protocol': entry.PROTOCOL,
        **{key: proof[key] for key in ('operator', 'run_id', 'session_id', 'candidate_id',
                                        'source_hashes', 'measurement_report_ref')},
        'proof_ref': proof_ref, 'started_at': storage['collection_started_at'],
        'finished_at': raw['finished_at'] + 1, 'elapsed_seconds': 24,
        'timeout_seconds': storage['timeout_seconds'], 'status': 'passed', 'error': None}
    reference = register_json_artifact(store, receipt)
    projection = summarize_task_window_raw(raw, config, store)["gate_projection"]
    value = {"candidate_id": config["candidate_id"],
             **{key: "passed" for key in ("static_review", "build", "accuracy", "runtime",
                                         "semantic", "scope", "portability")},
             **deepcopy(projection),
             "artifacts": {"measurement_admission": reference,
                           "measurement_report": receipt["measurement_report_ref"]}}
    return store, config, expected, value, receipt


def test_current_window_proof_reaches_candidate_gate_without_publication_claim(window_archive):
    store, config, expected, evidence, receipt = _evidence(window_archive)
    verify_measurement_admission(GateEvidence.from_dict(evidence), store,
        source_hashes=expected["source_hashes"], session_id=config["session_id"],
        run_id=config["run_id"])
    request = request_dict(config["candidate_id"])
    request["candidates"][0]["session_id"] = config["session_id"]
    request["candidates"][0]["source_hashes"] = expected["source_hashes"]
    evidence["static_review"] = "failed"  # Keep this synthetic proof out of production-safe outcomes.
    request["evidence"][0] = evidence
    outcome, = CandidateGate().evaluate(GateRequest.from_dict(request), store=store)
    assert outcome.verdict.value == "static_rejected"
    assert receipt["protocol"] == entry.PROTOCOL
    assert receipt['kind'] == 'local_measurement_completion'


def test_direct_proof_cannot_bypass_local_job_completion(window_archive):
    store, config, expected, evidence, receipt = _evidence(window_archive)
    with pytest.raises(ContractError):
        entry.replay_current_measurement_admission(store, receipt['proof_ref'], expected=expected)
    evidence['artifacts']['measurement_admission'] = receipt['proof_ref']
    with pytest.raises(ContractError):
        verify_measurement_admission(GateEvidence.from_dict(evidence), store,
            source_hashes=expected['source_hashes'], session_id=config['session_id'])


@pytest.mark.parametrize("change", ("old_protocol", "wrong_projection", "wrong_report",
                                    "failed_completion", "over_budget", "wrong_start",
                                    "raw_after_completion", "wrong_proof_report"))
def test_current_entry_rejects_substituted_measurement(window_archive, change):
    store, config, expected, evidence, receipt = _evidence(window_archive)
    if change in {"old_protocol", "failed_completion", "over_budget", "wrong_start",
                  "raw_after_completion", "wrong_proof_report"}:
        if change == 'old_protocol':
            receipt['protocol'] = 'shared_buffer_msprof_task_window_v3'
        elif change == 'failed_completion':
            receipt['status'] = 'failed'
            receipt['error'] = {'type': 'TimeoutError', 'message': 'online replay exceeded budget'}
        elif change == 'over_budget':
            receipt['elapsed_seconds'] = receipt['timeout_seconds'] + 1
        elif change == 'wrong_start':
            receipt['started_at'] += 1
        elif change == 'raw_after_completion':
            receipt['finished_at'] = receipt['started_at'] + 1
        else:
            receipt['measurement_report_ref'] = register_json_artifact(store, {'stable': True})
        evidence["artifacts"]["measurement_admission"] = register_json_artifact(store, receipt)
    elif change == "wrong_projection":
        evidence["candidate_samples_ns"][0] *= 2
    else:
        evidence["artifacts"]["measurement_report"] = register_json_artifact(store, {"stable": True})
    with pytest.raises(ContractError):
        verify_measurement_admission(GateEvidence.from_dict(evidence), store,
            source_hashes=expected["source_hashes"], session_id=config["session_id"])


def test_episode_finalize_reads_measurement_once_after_prepare(monkeypatch):
    context, request, graph = finalization_inputs(noop_request_dict(), noop=True)

    class Reader:
        def __init__(self):
            self.reads = 0

        def verify_artifact(self, _reference):
            self.reads += 1

    reader = Reader()
    monkeypatch.setattr(entry, "verify_measurement_admission",
        lambda _evidence, artifact_reader, **_kwargs:
            artifact_reader.verify_artifact("synthetic measurement boundary"))
    episode, = finalize_episodes(context, request, graph=graph, store=reader)
    assert episode.outcome.verdict.value == "verified_noop"
    assert reader.reads == 1
