"""Current-release profiling provenance and formal admission regressions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest
import aprof_runtime

if aprof_runtime.__version__ == "0.2.0":
    pytest.skip("0.4.1 freezes runtime 0.2.0; select APROF_SKILL_LIB=.../0.4.2 for new contracts", allow_module_level=True)

from aprof_runtime.contracts import GateRequest, GateVerdict
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.exploration import mechanism_alignment_from_artifacts
from aprof_runtime.gates import CandidateGate
from aprof_runtime.jsonio import to_primitive
from aprof_runtime.profile_evidence import normalize_profile, replay_profile_metric
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact, validate_trace_contract
from test_runtime import request_dict, finalization_inputs


@pytest.fixture
def store(tmp_path):
    with EpisodeStore(tmp_path / "evidence.sqlite") as result:
        yield result


def blob(store, value):
    import tempfile
    with tempfile.NamedTemporaryFile() as stream:
        stream.write(value.encode())
        stream.flush()
        return store.register_artifact(Path(stream.name))


def seal_capture(store, manifest, capture):
    scope = {key: manifest[key] for key in ("backend", "role", "case_id", "kernel", "workload_hash", "source_hash", "binary_hash", "hardware_hash", "tool", "policy", "collector_hash", "protocol_version")}
    scope.update({key: capture[key] for key in ("capture_id", "collection", "files")})
    identity = {"binary_hash": manifest["binary_hash"], "tool_hash": manifest["tool"]["executable_hash"], "source_hash": manifest["source_hash"]}
    checks = {"before": identity, "after": identity}
    capture["log_hash"] = register_json_artifact(store, {"capture_scope": scope,
        "capture": {"argv": capture["argv"], "exit_code": capture["exit_code"], "identity_checks": checks}, "import": {"exit_code": 0, "identity_checks": checks}})


def fixture(store, role="baseline", values=None, fmt="csv", *, repeats=5):
    values = values or [100] * repeats
    source = blob(store, role + " source")
    workload = register_json_artifact(store, {"case": 1, "shape": [1024]})
    hardware = {"device": 0, "soc": "Ascend950" if fmt == "jsonl" else "Ascend910C"}
    info = [{"category": "Device Info", "arch info": "3510"},
            {"category": "AI Core Information", "ai core count": 36},
            {"category": "CPU Information", "ai cpu count": 6}]
    if fmt == "jsonl":
        hardware["report_identity"] = {row["category"]: row for row in info}
        hardware["report_identity"]["frequencies"] = {"Current Freq": 1650, "Rated Freq": 1650}
    manifest = {
        "schema_version": "1.0.0", "backend": "npu-compute" if fmt == "jsonl" else "msprof", "role": role,
        "collector_hash": blob(store, "collector"), "protocol_version": "independent_capture_v1",
        "case_id": 1, "kernel": "exp_kernel", "workload_hash": workload,
        "source_hash": source, "binary_hash": blob(store, role + " binary"),
        "hardware_hash": register_json_artifact(store, hardware), "tool": {"executable_hash": blob(store, "profiler"), "version": "fixture-v1"},
        "policy": {"warmups": 10, "repeats": repeats, "sections": ["PipeUtilization"]},
        "warmup_runs": [{"argv": ["exp", "1"], "exit_code": 0,
                         "log_hash": register_json_artifact(store, {"argv": ["exp", "1"], "exit_code": 0, "warmup": i})} for i in range(10)], "captures": [],
    }
    for i, warmup in enumerate(manifest["warmup_runs"]):
        identity = {"binary_hash": manifest["binary_hash"], "tool_hash": manifest["tool"]["executable_hash"], "source_hash": manifest["source_hash"]}
        warmup["log_hash"] = register_json_artifact(store, {"argv": warmup["argv"], "exit_code": 0, "warmup": i,
            "identity_checks": {"before": identity, "after": identity}})
    sources = []
    for i, value in enumerate(values):
        field = "aiv_time(us)"
        if fmt == "csv":
            raw = f"Op Name,block_id,{field}\nexp_kernel,0,{value}\nexp_kernel,1,{value}\nother,0,9999\n"
            where = {}
            filename = "PipeUtilization.csv"
        else:
            raw = json.dumps({"category": "PipeUtilization", field: value}) + "\n" + json.dumps({
                "category": "OpInfoSummary", "Op Name": "exp_kernel", "Device Id": 0,
                "Current Freq": 1650, "Rated Freq": 1650, "Op Type": "vector"}) + "\n"
            where = {"category": "PipeUtilization"}
            filename = "summary.jsonl"
        path = f"capture-{i}/exp_kernel/{filename}"
        files = [{"path": path, "artifact_hash": blob(store, raw), "format": fmt, "kernel": "exp_kernel"}]
        if fmt == "csv":
            files.append({"path": f"capture-{i}/exp_kernel/OpBasicInfo.csv", "artifact_hash": blob(store, "Op Name,Task Duration(us)\nexp_kernel,10\n"), "format": "csv", "kernel": "exp_kernel"})
        else:
            files.append({"path": f"capture-{i}/HardwareInfo.jsonl", "artifact_hash": blob(store, "\n".join(json.dumps(row) for row in info)+"\n"), "format": "jsonl", "kernel": "exp_kernel"})
        capture = {"capture_id": str(i), "collection": f"capture-{i}/exp_kernel", "argv": (["profiler", "--", "exp", "1"] if fmt == "jsonl" else ["profiler", "op", "--application=exp 1"]), "exit_code": 0, "files": files}
        seal_capture(store, manifest, capture)
        manifest["captures"].append(capture)
        sources.append({"capture_id": str(i), "path": path, "format": fmt, "field": field,
                        "where": where, "row_aggregation": "median"})
    digest = register_json_artifact(store, manifest)
    spec = {"duration": {"unit": "us", "aggregation": "mean", "sources": sources}}
    profile = normalize_profile(store, digest, spec)
    return manifest, profile, spec


def admission(store):
    before, bp, _ = fixture(store)
    after, cp, _ = fixture(store, "candidate", [80] * 5)
    report = {"schema_version": "1.0.0", "candidate_id": "c1", "hypothesis_basis": "measured",
        "metrics": [{"name": "duration", "baseline": 100, "candidate": 80, "expected_direction": "decrease",
                     "unit": "us", "baseline_profile_hash": register_json_artifact(store, bp),
                     "candidate_profile_hash": register_json_artifact(store, cp)}]}
    value = request_dict("c1")
    dummy = blob(store, "checked build and accuracy fixture")
    value["candidates"][0]["source_hashes"] = {"baseline": before["source_hash"], "candidate": after["source_hash"]}
    value["candidates"][0]["patch_artifact_hash"] = dummy
    value["candidates"][0]["producer_hashes"] = {name: "unknown" for name in ("model", "agent", "prompt")}
    value["evidence"][0]["artifacts"] = {name: dummy for name in ("build_log", "accuracy_report", "measurement_report")}
    value["evidence"][0]["artifacts"]["mechanism_report"] = register_json_artifact(store, report)
    return value, before, after, bp, cp, report


@pytest.mark.parametrize("fmt", ["csv", "jsonl"])
def test_source_replay_counts_processes_not_cores(store, fmt):
    manifest, profile, _ = fixture(store, fmt=fmt)
    assert profile["metrics"]["duration"]["samples"] == [100] * 5
    assert profile["metrics"]["duration"]["status"] == "available"
    assert replay_profile_metric(store, profile, "duration") == manifest


@pytest.mark.parametrize("field,value", [("value", 999), ("samples", [100] * 6), ("cv", 0.01),
    ("status", "missing"), ("unit", "ns"), ("aggregation", "sum")])
def test_forged_normalized_statistic_is_rejected(store, field, value):
    _, profile, _ = fixture(store)
    profile["metrics"]["duration"][field] = value
    with pytest.raises(ContractError):
        replay_profile_metric(store, profile, "duration")


@pytest.mark.parametrize("field,value", [("kernel", "other"), ("case_id", 2)])
def test_profile_identity_cannot_be_relabelled(store, field, value):
    _, profile, _ = fixture(store)
    profile[field] = value
    with pytest.raises(ContractError, match="workload/kernel"):
        replay_profile_metric(store, profile, "duration")


@pytest.mark.parametrize("values,status", [([100, 100, None, 100, 100], "missing"),
    ([1, 10, 100, 1000, 10000], "unstable"), ([100], "unstable")])
def test_unavailable_or_nonindependent_evidence_cannot_admit(store, values, status):
    _, profile, _ = fixture(store, values=values, fmt="jsonl", repeats=len(values))
    assert profile["metrics"]["duration"]["status"] == status


@pytest.mark.parametrize("mutation", ["collection", "duplicate_capture", "duplicate_receipt", "role", "source", "backend", "hardware", "unit"])
def test_mismatched_or_rebound_mechanism_sources_are_rejected(store, mutation):
    value, before, after, bp, cp, report = admission(store)
    if mutation == "collection":
        after["captures"][0]["collection"] = "wrong"
    elif mutation == "duplicate_capture":
        after["captures"][1]["capture_id"] = "0"
    elif mutation == "duplicate_receipt":
        after["captures"][1]["log_hash"] = after["captures"][0]["log_hash"]
    elif mutation == "role":
        after["role"] = "baseline"
    elif mutation == "source":
        after["source_hash"] = before["source_hash"]
    elif mutation == "backend":
        after["backend"] = "npu-compute"
    elif mutation == "hardware":
        after["hardware_hash"] = register_json_artifact(store, {"device": 1})
    elif mutation == "unit":
        cp["metrics"]["duration"]["unit"] = "ns"
    cp["capture_manifest_hash"] = register_json_artifact(store, after)
    report["metrics"][0]["candidate_profile_hash"] = register_json_artifact(store, cp)
    value["evidence"][0]["artifacts"]["mechanism_report"] = register_json_artifact(store, report)
    with pytest.raises(ContractError):
        CandidateGate().evaluate(GateRequest.from_dict(value), store=store)


def test_new_gate_ignores_bare_agent_boolean():
    outcome, = CandidateGate().evaluate(GateRequest.from_dict(request_dict("c1")))
    assert outcome.verdict is GateVerdict.ATTRIBUTION_UNCERTAIN
    assert not outcome.eligible


def test_profiling_is_not_required_to_record_failed_build(store):
    value = request_dict("c1")
    value["evidence"][0]["build"] = "failed"
    outcome, = CandidateGate().evaluate(GateRequest.from_dict(value), store=store)
    assert outcome.verdict is GateVerdict.BUILD_FAILED


def test_gate_recomputes_support_instead_of_trusting_false(store):
    value, *_ = admission(store)
    value["evidence"][0]["mechanism_alignment"] = False
    result, = CandidateGate().evaluate(GateRequest.from_dict(value), store=store)
    assert result.eligible


def test_finalize_append_reopen_replay_nested_raw_sources(store):
    value, before, *_ = admission(store)
    context, request, graph = finalization_inputs(value)
    episodes = finalize_episodes(context, request, graph=graph, store=store)
    assert episodes[0].outcome.eligible
    assert episodes[0].runtime_build == "aprof-runtime/0.2.1"
    store.append_many(episodes)
    store.verify_integrity()
    with EpisodeStore(store.path) as reopened:
        reopened.verify_integrity()
    raw = before["captures"][0]["files"][0]["artifact_hash"]
    store.object_path(raw).write_text("tampered\n")
    with pytest.raises(StoreError, match="corrupt|content does not match"):
        store.verify_integrity()


def test_finalize_cannot_impersonate_old_runtime(store):
    value, *_ = admission(store)
    context, request, graph = finalization_inputs(value)
    with pytest.raises(ContractError, match="current runtime"):
        finalize_episodes(context, request, graph=graph, store=store, runtime_build="aprof-runtime/0.2.0")


def test_strict_manifest_rejects_unknown_fields(store):
    manifest, _, _ = fixture(store)
    manifest["trust_me"] = True
    with pytest.raises(ContractError):
        validate_trace_contract("capture-manifest", manifest)


def test_old_profile_contract_is_still_valid_and_readable(store):
    raw = blob(store, "Op Name,aiv_time(us)\nexp_kernel,10\n")
    profile = {"schema_version": "1.0.0", "case_id": 1, "kernel": "exp_kernel", "metrics": {
        "duration": {"value": 10, "unit": "us", "source_artifact_hash": raw,
                     "field": "aiv_time(us)", "aggregation": "mean", "samples": [10]}}}
    assert validate_trace_contract("normalized-profile", profile) == profile
    from aprof_runtime.exploration import _profile_metric
    assert _profile_metric(store, register_json_artifact(store, profile), "duration")[1]["value"] == 10


def test_reused_warmup_receipt_is_not_ten_executions(store):
    manifest, _, spec = fixture(store)
    manifest["warmup_runs"] = [manifest["warmup_runs"][0]] * 10
    with pytest.raises(ContractError, match="distinct process"):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


def test_unrelated_warmup_command_is_rejected(store):
    manifest, _, spec = fixture(store)
    manifest["warmup_runs"][0]["argv"] = ["/bin/true"]
    with pytest.raises(ContractError, match="same exact workload"):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


def test_insufficient_real_warmup_stays_diagnostic(store):
    manifest, _, spec = fixture(store)
    manifest["policy"]["warmups"] = 1
    manifest["warmup_runs"] = manifest["warmup_runs"][:1]
    for capture in manifest["captures"]:
        seal_capture(store, manifest, capture)
    profile = normalize_profile(store, register_json_artifact(store, manifest), spec)
    assert profile["metrics"]["duration"]["status"] == "unstable"


@pytest.mark.parametrize("raw", [
    'Op Name,block_id,aiv_time(us)\nexp_kernel,0,100,extra\n',
    'Op Name,block_id,aiv_time(us)\nexp_kernel,0\n',
    'Op Name,block_id,aiv_time(us),aiv_time(us)\nexp_kernel,0,100,200\n',
])
def test_malformed_csv_cannot_be_normalized(store, raw):
    manifest, _, spec = fixture(store)
    manifest["captures"][0]["files"][0]["artifact_hash"] = blob(store, raw)
    seal_capture(store, manifest, manifest["captures"][0])
    with pytest.raises(ContractError):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


def test_duplicate_jsonl_keys_are_rejected(store):
    manifest, _, spec = fixture(store, fmt="jsonl")
    file = manifest["captures"][0]["files"][0]
    raw = store.verify_artifact(file["artifact_hash"]).read_text().replace('"category": "PipeUtilization"', '"category": "wrong", "category": "PipeUtilization"')
    file["artifact_hash"] = blob(store, raw)
    seal_capture(store, manifest, manifest["captures"][0])
    with pytest.raises(ContractError, match="duplicate JSON key"):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


def test_core_cherry_pick_is_rejected(store):
    manifest, _, spec = fixture(store)
    for source in spec["duration"]["sources"]:
        source["where"] = {"block_id": "0"}
    with pytest.raises(ContractError, match="cherry-pick"):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


def test_negative_raw_time_is_rejected(store):
    with pytest.raises(ContractError, match="nonnegative"):
        fixture(store, values=[-100] * 5)


def test_npu_csv_uses_all_applicable_unique_vector_cores(store):
    manifest, _, spec = fixture(store, fmt="jsonl")
    for capture, source in zip(manifest["captures"], spec["duration"]["sources"]):
        path = capture["collection"] + "/PipeUtilization.csv"
        raw = "block_id,sub_block_id,aiv_time(us)\n0,vector0,10\n1,vector0,20\n0,cube,NA\n"
        capture["files"].append({"path": path, "artifact_hash": blob(store, raw), "format": "csv", "kernel": manifest["kernel"]})
        source.update(path=path, format="csv", where={})
        seal_capture(store, manifest, capture)
    profile = normalize_profile(store, register_json_artifact(store, manifest), spec)
    assert profile["metrics"]["duration"]["samples"] == [15] * 5
    file = manifest["captures"][0]["files"][-1]
    file["artifact_hash"] = blob(store, "block_id,sub_block_id,aiv_time(us)\n0,vector0,10\n0,vector0,90\n")
    seal_capture(store, manifest, manifest["captures"][0])
    with pytest.raises(ContractError, match="duplicate raw profiling core"):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


@pytest.mark.parametrize("field,value", [("Op Name", "other"), ("Device Id", 7), ("Current Freq", 1600)])
def test_rehashed_raw_npu_identity_cannot_escape_manifest_binding(store, field, value):
    manifest, _, spec = fixture(store, fmt="jsonl")
    capture = manifest["captures"][0]
    file = capture["files"][0]
    rows = [json.loads(line) for line in store.verify_artifact(file["artifact_hash"]).read_text().splitlines()]
    rows[-1][field] = value
    file["artifact_hash"] = blob(store, "\n".join(json.dumps(row) for row in rows)+"\n")
    seal_capture(store, manifest, capture)
    with pytest.raises(ContractError, match="kernel|device|frequencies"):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


def test_append_cannot_promote_a_self_hashed_bare_boolean_episode(store):
    from aprof_runtime.jsonio import content_hash
    from aprof_runtime.contracts import CandidateEpisode
    value, *_ = admission(store)
    del value["evidence"][0]["artifacts"]["mechanism_report"]
    context, request, graph = finalization_inputs(value)
    episode = finalize_episodes(context, request, graph=graph)[0]
    forged = to_primitive(episode)
    forged["gate_request"] = to_primitive(request)
    forged["evidence"] = to_primitive(request.evidence[0])
    forged["outcome"] = to_primitive(CandidateGate()._evaluate_prepared(request)[0])
    forged["episode_hash"] = content_hash({k: v for k, v in forged.items() if k != "episode_hash"})
    structural = CandidateEpisode.from_dict(forged)
    assert structural.outcome.eligible  # Parsing alone is not admission.
    with pytest.raises(StoreError, match="CAS-backed"):
        store.append(structural)


def test_current_runtime_reads_frozen_old_episode_store_without_rewriting(tmp_path):
    import os
    import subprocess
    import sys
    root = Path(__file__).resolve().parents[2]
    old = root / "skill-libs/graph-base/0.4.1"
    path = tmp_path / "historical.sqlite"
    env = dict(os.environ, APROF_SKILL_LIB=str(old), PYTHONPATH=os.pathsep.join([
        str(old / "runtime/src"), str(root / "scaffolding/collection/scripts"), str(root / "scaffolding/tests")]))
    script = """from pathlib import Path
from aprof_runtime.store import EpisodeStore
from test_store_integrity import _episode
p=Path(__import__('sys').argv[1]); source=p.with_suffix('.txt'); source.write_text('historical immutable source')
with EpisodeStore(p) as store:
    store.append(_episode(store.register_artifact(source)))
"""
    subprocess.run([sys.executable, "-c", script, str(path)], env=env, check=True, capture_output=True, text=True)
    with EpisodeStore(path) as reopened:
        before = reopened.connection.execute("SELECT payload_json FROM episodes").fetchone()[0]
        reopened.verify_integrity()
        after = reopened.connection.execute("SELECT payload_json FROM episodes").fetchone()[0]
        assert before == after
        assert json.loads(after)["runtime_build"] == "aprof-runtime/0.2.0"
        from aprof_runtime.contracts import CandidateEpisode
        with pytest.raises(StoreError, match="current runtime identity"):
            reopened.append(CandidateEpisode.from_dict(json.loads(after)))


@pytest.mark.parametrize("alignment", [False, None, True])
def test_candidate_and_finalize_share_canonical_provenance_decision(store, alignment):
    value, *_ = admission(store)
    value["evidence"][0]["mechanism_alignment"] = alignment
    context, request, graph = finalization_inputs(value)
    gate, = CandidateGate().evaluate(request, store=store)
    episode, = finalize_episodes(context, request, graph=graph, store=store)
    assert gate == episode.outcome


@pytest.mark.parametrize("field", ["binary_hash", "tool_hash", "source_hash"])
def test_replayed_process_receipt_rejects_identity_change(store, field):
    manifest, _, spec = fixture(store)
    capture = manifest["captures"][0]
    receipt = json.loads(store.verify_artifact(capture["log_hash"]).read_text())
    receipt["capture"]["identity_checks"]["after"][field] = blob(store, "changed identity")
    capture["log_hash"] = register_json_artifact(store, receipt)
    with pytest.raises(ContractError, match="identity changed"):
        normalize_profile(store, register_json_artifact(store, manifest), spec)


def test_bound_candidate_kernel_can_be_renamed_without_cross_kernel_aggregation(store):
    value, _, candidate_manifest, _, candidate_profile, report = admission(store)
    candidate_manifest["kernel"] = "optimized_exp"
    for capture in candidate_manifest["captures"]:
        for file in capture["files"]:
            raw = store.verify_artifact(file["artifact_hash"]).read_text()
            file["artifact_hash"] = blob(store, raw.replace("exp_kernel", "optimized_exp"))
            file["kernel"] = "optimized_exp"
        seal_capture(store, candidate_manifest, capture)
    specs = {"duration": {key: candidate_profile["metrics"]["duration"][key] for key in ("unit", "aggregation", "sources")}}
    updated = normalize_profile(store, register_json_artifact(store, candidate_manifest), specs)
    report["metrics"][0]["candidate_profile_hash"] = register_json_artifact(store, updated)
    value["evidence"][0]["artifacts"]["mechanism_report"] = register_json_artifact(store, report)
    assert CandidateGate().evaluate(GateRequest.from_dict(value), store=store)[0].eligible
