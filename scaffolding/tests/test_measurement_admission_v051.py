"""Current proofs fail closed; frozen 0.2.1 evidence remains read-only replayable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

import pytest

from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1 runtime 0.2.2", allow_module_level=True)

from aprof_runtime.contracts import CandidateEpisode, GateEvidence, GateRequest
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.exploration import ExplorationGate, verify_exploration
from aprof_runtime.gates import CandidateGate
from aprof_runtime.jsonio import content_hash
from aprof_runtime.measurement_entry import verify_measurement_admission
from aprof_runtime.task_window_measurement_admission import PROTOCOL as CURRENT_MEASUREMENT_PROTOCOL
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact, make_optimization_trace, validate_optimization_trace
from test_runtime import finalization_inputs, noop_request_dict, request_dict
from test_traces_exploration import request_fixture


ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "skill-libs/graph-base/0.5.1"


@pytest.fixture
def store(tmp_path):
    with EpisodeStore(tmp_path / "evidence.sqlite") as value:
        yield value


def bound_claim(store):
    """A self-asserted summary, intentionally never a hardware acceptance fixture."""
    request = request_dict("c1")
    source = register_json_artifact(store, {"source": "synthetic"})
    report = register_json_artifact(store, {"stable": True})
    draft = request["candidates"][0]
    draft["source_hashes"] = {"baseline": source, "candidate": source}
    evidence = request["evidence"][0]
    evidence["artifacts"] = {"measurement_report": report}
    receipt = {"protocol": CURRENT_MEASUREMENT_PROTOCOL,
               "candidate_id": "c1", "session_id": draft["session_id"], "run_id": "run",
               "source_hashes": draft["source_hashes"], "measurement_report_ref": report,
               "accepted": True, "stable": True}
    return request, receipt


def test_runtime_patch_version_is_consistent():
    assert tomllib.loads((RELEASE / "runtime/pyproject.toml").read_text())["project"]["version"] == __version__
    assert __version__ == "0.2.2"


def test_machine_thresholds_contracts_and_graph_remain_frozen():
    old = ROOT / "skill-libs/graph-base/0.5.0"
    for directory in ("schemas", "skillgraph/versions"):
        expected = {p.relative_to(old).as_posix(): p.read_bytes() for p in (old / directory).rglob("*") if p.is_file()}
        actual = {p.relative_to(RELEASE).as_posix(): p.read_bytes() for p in (RELEASE / directory).rglob("*") if p.is_file()}
        assert actual == expected
    runtime = Path("runtime/src/aprof_runtime")
    for name in ("contracts.py", "trace_schemas.py"):
        assert (RELEASE / runtime / name).read_bytes() == (old / runtime / name).read_bytes()
    marker = "def evaluate_candidate_evidence("
    assert (RELEASE / runtime / "gates.py").read_text().split(marker)[1] == (old / runtime / "gates.py").read_text().split(marker)[1]


@pytest.mark.parametrize("empty_role", [None, "baseline_samples_ns", "candidate_samples_ns"])
def test_any_timing_requires_cas_even_through_direct_python(empty_role):
    request = request_dict("c1")
    if empty_role:
        request["evidence"][0][empty_role] = []
    with pytest.raises(ContractError, match="CAS artifact reader"):
        CandidateGate().evaluate(GateRequest.from_dict(request))


def test_graph_gate_and_episode_finalization_require_method_artifact(store):
    request = request_dict("c1")
    with pytest.raises(ContractError, match="measurement_admission artifact"):
        CandidateGate().evaluate(GateRequest.from_dict(request), store=store)
    context, parsed, graph = finalization_inputs(request)
    with pytest.raises(ContractError, match="measurement_admission artifact"):
        finalize_episodes(context, parsed, graph=graph, store=store)
    assert store.connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 0


def test_claimed_summary_has_no_accepting_path(store):
    request, receipt = bound_claim(store)
    request["evidence"][0]["artifacts"]["measurement_admission"] = register_json_artifact(store, receipt)
    with pytest.raises(ContractError, match="unsupported Task window admission receipt"):
        CandidateGate().evaluate(GateRequest.from_dict(request), store=store)


@pytest.mark.parametrize("field", ["candidate_id", "source_hashes", "session_id", "run_id", "measurement_report_ref"])
def test_method_receipt_identity_is_bound_before_protocol_replay(store, field):
    request, receipt = bound_claim(store)
    receipt[field] = "substituted"
    evidence = request["evidence"][0]
    evidence["artifacts"]["measurement_admission"] = register_json_artifact(store, receipt)
    with pytest.raises(ContractError, match="measurement_admission .*differs"):
        verify_measurement_admission(GateEvidence.from_dict(evidence), store,
            source_hashes=request["candidates"][0]["source_hashes"], session_id="session-1", run_id="run")


def test_missing_method_object_is_not_a_proof(store):
    request = request_dict("c1")
    request["evidence"][0]["artifacts"]["measurement_admission"] = "sha256:" + "e" * 64
    with pytest.raises(StoreError, match="missing|indexed"):
        CandidateGate().evaluate(GateRequest.from_dict(request), store=store)


@pytest.mark.parametrize("stage,verdict", [("build", "build_failed"), ("accuracy", "accuracy_failed")])
def test_failures_without_timing_remain_recordable(stage, verdict):
    request = request_dict("c1")
    request["evidence"][0].update({stage: "failed", "baseline_samples_ns": [], "candidate_samples_ns": []})
    outcome, = CandidateGate().evaluate(GateRequest.from_dict(request))
    assert outcome.verdict.value == verdict


def test_noop_remains_recordable_without_timing():
    context, request, graph = finalization_inputs(noop_request_dict(), noop=True)
    episode, = finalize_episodes(context, request, graph=graph)
    assert episode.outcome.verdict.value == "verified_noop"
    assert episode.runtime_build == "aprof-runtime/0.2.2"


def test_exploration_gate_cannot_bypass_method_admission(tmp_path, store):
    request = request_fixture(tmp_path, store)
    with pytest.raises(ContractError, match="measurement_admission artifact"):
        ExplorationGate().evaluate(request, store=store)


def test_negative_exploration_replays_without_measured_admission(tmp_path, store):
    request = request_fixture(tmp_path, store, failed=True)
    outcomes = ExplorationGate().evaluate(request, store=store)
    assert outcomes[0]["verdict"] == "build_failed"
    assert verify_exploration(request, outcomes, store=store)["valid"]


@pytest.fixture
def historical_store(tmp_path):
    """Use the actual frozen producer to create a synthetic legacy regression proof."""
    old = ROOT / "skill-libs/graph-base/0.5.0"
    script = r'''
import json, sys
from pathlib import Path
from aprof_runtime.contracts import GateRequest
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.jsonio import to_primitive
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact
from profile_evidence_fixture import bind_profiles
from test_runtime import request_dict, finalization_inputs
where = Path(sys.argv[1])
with EpisodeStore(where / 'historical.sqlite') as store:
    digest = register_json_artifact(store, {'synthetic': 'legacy fixture'})
    request = request_dict('old')
    draft = request['candidates'][0]
    draft.update(source_hashes={'baseline': digest, 'candidate': digest}, patch_artifact_hash=digest,
                 producer_hashes={'model': 'unknown', 'prompt': 'unknown', 'agent': 'unknown'})
    request['evidence'][0]['artifacts'] = {key: digest for key in ('build_log', 'accuracy_report', 'measurement_report')}
    request, _ = bind_profiles(request, store, preserve_sources=True)
    context, request, graph = finalization_inputs(request)
    episode, = finalize_episodes(context, request, graph=graph, store=store)
    assert episode.runtime_build == 'aprof-runtime/0.2.1'
    assert episode.outcome.verdict.value == 'production_safe_gain'
    store.append(episode)
    (where / 'historical.json').write_text(json.dumps(to_primitive(episode)))
'''
    environment = {**os.environ, "APROF_SKILL_LIB": str(old), "PYTHONDONTWRITEBYTECODE": "1",
                   "PYTHONPATH": os.pathsep.join(map(str, [old / "runtime/src", ROOT / "scaffolding/tests",
                                                           ROOT / "scaffolding/collection/scripts"]))}
    subprocess.run([sys.executable, "-c", script, str(tmp_path)], env=environment, check=True, capture_output=True)
    return tmp_path / "historical.sqlite", json.loads((tmp_path / "historical.json").read_text())


def test_historical_profile_proof_is_read_only_compatible(historical_store):
    path, payload = historical_store
    with EpisodeStore(path) as store:
        assert store.verify_integrity()
        with pytest.raises(StoreError, match="current runtime identity"):
            store.append(CandidateEpisode.from_dict(payload))
        request = GateRequest.from_dict(payload["gate_request"])
        with pytest.raises(ContractError, match="measurement_admission artifact"):
            CandidateGate().evaluate(request, store=store)


def test_relabeling_legacy_episode_cannot_create_current_proof(historical_store):
    path, payload = historical_store
    payload["runtime_build"] = "aprof-runtime/0.2.2"
    payload["episode_hash"] = content_hash({key: value for key, value in payload.items() if key != "episode_hash"})
    episode = CandidateEpisode.from_dict(payload)
    with EpisodeStore(path) as store:
        with pytest.raises(StoreError, match="measurement_admission artifact"):
            store.append(episode)
        assert store.connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 1


def test_historical_replay_still_verifies_profile_cas(historical_store):
    path, payload = historical_store
    with EpisodeStore(path) as store:
        reference = payload["evidence"]["artifacts"]["mechanism_report"]
        store.verify_artifact(reference).write_text("tampered")
        with pytest.raises(StoreError, match="content does not match|corrupt"):
            store.verify_integrity()


def test_graph_summary_replays_current_method_admission(historical_store):
    path, payload = historical_store

    def summary(episode):
        draft = episode["draft"]
        return make_optimization_trace({"run_id": "run", "task_id": episode["context"]["task_id"],
            "session_id": draft["session_id"], "candidate_id": draft["candidate_id"],
            "attempt_id": "attempt", "operator": "demo_op", "split": "train",
            "source_parent_hash": draft["source_hashes"]["baseline"]},
            provenance={"baseline_source_hash": draft["source_hashes"]["baseline"],
                        "candidate_source_hash": draft["source_hashes"]["candidate"],
                        "patch_hash": draft["patch_artifact_hash"]},
            routing={"mode": "graph", "route": draft["route"], "coverage_gap": None},
            intervention={"parameters": draft["parameters"]},
            result={"episode_ref": episode["episode_hash"], "verdict": episode["outcome"]["verdict"]})

    with EpisodeStore(path) as store:
        validate_optimization_trace(summary(payload), store)
        payload["runtime_build"] = "aprof-runtime/0.2.2"
        payload["episode_hash"] = content_hash({key: value for key, value in payload.items() if key != "episode_hash"})
        # Simulate a tampered DB row: trace verification must replay CAS admission,
        # even when the payload and its arithmetic outcome are self-consistent.
        store.connection.execute("DROP TRIGGER episodes_no_update")
        store.connection.execute("UPDATE episodes SET payload_json=?, episode_hash=? WHERE candidate_id=?",
                                 (json.dumps(payload), payload["episode_hash"], payload["draft"]["candidate_id"]))
        with pytest.raises(StoreError, match="measurement_admission artifact"):
            validate_optimization_trace(summary(payload), store)


def test_copied_package_cli_enforces_same_join_without_repository_imports(tmp_path):
    package = tmp_path / "standalone"
    shutil.copytree(RELEASE / "runtime", package / "runtime", ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"))
    (package / "tools").mkdir()
    shutil.copy2(RELEASE / "tools/aprofctl", package / "tools/aprofctl")
    request = tmp_path / "request.json"
    request.write_text(json.dumps(request_dict("c1")))
    environment = {key: value for key, value in os.environ.items() if key not in ("PYTHONPATH", "APROF_SKILL_LIB")}
    environment["APROF_PYTHON"] = sys.executable
    result = subprocess.run([str(package / "tools/aprofctl"), "candidate", "gate", "--request", str(request)],
                            cwd=tmp_path, env=environment, text=True, capture_output=True)
    assert result.returncode != 0
    assert "CAS artifact reader" in result.stderr
