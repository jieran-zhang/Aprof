"""Controller contract checks; these never certify hardware acceptance."""
from pathlib import Path
import json
import shutil
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "collection/scripts"
sys.path.insert(0, str(SCRIPTS))
import validation_host_evaluator as host
import validation_operator_adapter as adapter


def test_mechanism_must_be_declared_from_frozen_choices():
    profile = {"case_id": 1, "kernels": ["gelu_kernel"], "metrics": {"vector_wait_ratio": {}}}
    choice = {"case_id": 1, "kernel": "gelu_kernel", "metric": "vector_wait_ratio", "expected_direction": "decrease"}
    assert host.mechanism_choice({"mechanism": choice}, profile) == choice
    for altered in ({}, {**choice, "kernel": "*"}, {**choice, "metric": "posthoc_metric"}, {**choice, "case_id": 2}):
        with pytest.raises(ValueError, match="predeclare"):
            host.mechanism_choice({"mechanism": altered}, profile)


def test_aa_control_rejects_role_bias_even_with_low_cv():
    cases = [{"case_id": i, "speedup": 1.005, "baseline_cv": .01, "candidate_cv": .01} for i in range(1, 21)]
    assert host.aa_verdict({"stable": True, "per_case": cases})["passed"]
    cases[0]["speedup"] = 1.03
    assert not host.aa_verdict({"stable": True, "per_case": cases})["passed"]


def test_correctness_receipt_cannot_replace_actual_verifier_json(tmp_path):
    # Synthetic stdout fixtures exercise replay only, never hardware acceptance.
    rows = []
    for case_id in range(1, 21):
        folder = tmp_path / str(case_id)
        folder.mkdir()
        native = {"case_id": case_id, "passed": True, "mere": 0.1}
        host.dump(folder / "metadata.json", {"case_id": case_id})
        host.dump(folder / "result.json", native)
        (folder / "stdout.log").write_text(json.dumps(native) + "\n")
        (folder / "stderr.log").write_text("")
        host.dump(folder / "execution.json", {"exit_status": 0, "error": None,
            "stdout": host.ref(folder / "stdout.log"), "stderr": host.ref(folder / "stderr.log")})
        rows.append({"case_id": case_id, "correct": True, "metadata": host.ref(folder / "metadata.json"),
            "verification": host.ref(folder / "result.json"), "outputs": [],
            "kernel_execution": host.ref(folder / "execution.json"),
            "verifier_execution": host.ref(folder / "execution.json")})
    report = {"case_ids": list(range(1, 21)), "complete": True, "rows": rows}
    path = tmp_path / "report.json"
    host.dump(path, report)
    host.verify_correctness_report(host.ref(path))
    host.dump(tmp_path / "1/result.json", {"case_id": 1, "passed": True, "mere": 0.0})
    rows[0]["verification"] = host.ref(tmp_path / "1/result.json")
    host.dump(path, report)
    with pytest.raises(ValueError, match="actual verifier stdout"):
        host.verify_correctness_report(host.ref(path))


@pytest.mark.parametrize("fault", [None, "other_binary", "other_profile_source", "other_profile_binary",
    "other_profile_case", "other_profile_role", "other_profile_kernel", "empty_metrics", "metric_spec",
    "other_capture_attachment", "unregistered_correctness", "unregistered_profile", "other_host",
    "other_timing_device", "other_workload", "other_repeat", "other_controls"])
def test_qualified_baseline_joins_source_binary_profiles_and_stage_evidence(tmp_path, monkeypatch, fault):
    # Only joins after the separately tested raw/CAS machine replay are isolated
    # here. These synthetic artifacts are never usable as hardware qualification.
    class Store:
        def put(self, value):
            data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True).encode()
            import hashlib
            digest = "sha256:" + hashlib.sha256(data).hexdigest()
            path = tmp_path / digest[7:]
            path.write_bytes(data)
            return digest

        def verify_artifact(self, digest):
            path = tmp_path / digest[7:]
            assert host.sha(path) == digest
            return path

    store = Store()
    as_ref = lambda digest: host.ref(store.verify_artifact(digest))
    source_hash, binary_hash = store.put({"frozen_source": True}), store.put(b"qualified executable")
    accuracy_hash = store.put({"already_replayed_correctness": True})
    metadata = {"case_id": 1, "shape": [8], "dtype": "float32", "numel": 8, "input": "/archived/input.bin"}
    prepared = tmp_path / "inputs"
    host.dump(prepared / "case_01/metadata.json", metadata)
    metric_specs = {"wait": {"unit": "ratio", "field": "aiv_vec_wait_ratio"}}
    plan = {"operator": "gelu", "repeat": 100, "physical_device": 0,
            "prepared_inputs": str(prepared), "control_case_ids": [1, 3, 8, 14, 16, 20],
            "profile": {"case_id": 1, "kernels": ["gelu_kernel"], "metrics": metric_specs}}
    manifest = {"role": "baseline", "case_id": 1, "kernel": "gelu_kernel", "source_hash": source_hash,
                "binary_hash": binary_hash, "workload_hash": store.put(metadata),
                "hardware_hash": store.put({"host": "qualified-host", "device": "0", "physical_device": "0"})}
    if fault and fault.startswith("other_profile_"):
        key = {"other_profile_source": "source_hash", "other_profile_binary": "binary_hash",
               "other_profile_case": "case_id", "other_profile_role": "role", "other_profile_kernel": "kernel"}[fault]
        manifest[key] = 2 if key == "case_id" else "unqualified replacement"
    if fault == "other_host":
        manifest["hardware_hash"] = store.put({"host": "different-host", "device": "0", "physical_device": "0"})
    if fault == "other_workload":
        manifest["workload_hash"] = store.put({**metadata, "shape": [4]})
    manifest_hash = store.put(manifest)
    canonical = {"capture_manifest_hash": manifest_hash, "kernel": "gelu_kernel", "case_id": 1,
                 "metrics": {"wait": {"status": "available", "field": "aiv_vec_wait_ratio"}}}
    normalized = json.loads(json.dumps(canonical))
    if fault == "empty_metrics":
        normalized["metrics"] = {}
    if fault == "metric_spec":
        normalized["metrics"]["wait"]["field"] = "posthoc_metric"
    normalized_hash = store.put(normalized)
    config_hash = store.put({"expected_case_ids": [1] if fault == "other_controls" else plan["control_case_ids"]})
    protocol = {"operator": "gelu", "measurement_policy": {"repeat": 1 if fault == "other_repeat" else 100},
        "binary_hashes": dict.fromkeys(("baseline", "candidate"), binary_hash),
        "source_hashes": dict.fromkeys(("baseline", "candidate"), source_hash),
        "phases": {phase: {"config_ref": config_hash} for phase in ("aa_before", "aa_after")}}
    events = [store.put({"state": "completed", "stage": "correctness",
                         "evidence_refs": [] if fault == "unregistered_correctness" else [accuracy_hash]}),
              store.put({"state": "completed", "stage": "profile",
                         "evidence_refs": [] if fault == "unregistered_profile" else [manifest_hash, normalized_hash]})]
    control = {"attempt_roster_ref": store.put({"events": events}),
               "formal": {"raw_ref": store.put({"host": "qualified-host", "device": 0,
                                                   "physical_device": 1 if fault == "other_timing_device" else 0})}}
    qualification = {"operator": "gelu", "binary": as_ref(store.put(b"other executable") if fault == "other_binary" else binary_hash),
        "correctness": as_ref(accuracy_hash), "control_report_ref": store.put(control),
        "baseline_profiles": [{"kernel": "gelu_kernel", "normalized": as_ref(normalized_hash),
            "capture": as_ref(store.put({"other": "capture"}) if fault == "other_capture_attachment" else manifest_hash)}]}
    admission = {"protocol_ref": store.put(protocol), "stage_windows": {"profile": [100, 200]}}
    import timing_admission
    monkeypatch.setattr(timing_admission, "verify_capture_window", lambda *_args, **_kwargs: {"passed": True})

    def expand(_manifest, specs):
        assert specs == metric_specs
        return specs

    api = {"load_capture_manifest": lambda archive, digest: host.read(archive.verify_artifact(digest)),
           "expand_specs": expand, "normalize_profile": lambda *_: canonical}
    if fault is None:
        assert host.verify_qualification_bindings(store, qualification, plan, admission, api) == store.verify_artifact(binary_hash)
    else:
        with pytest.raises(ValueError):
            host.verify_qualification_bindings(store, qualification, plan, admission, api)


def test_source_scope_does_not_promote_case_specialization_or_removed_tails(tmp_path):
    before, after = tmp_path / "before", tmp_path / "after"
    before.mkdir()
    after.mkdir()
    original = "constexpr unsigned TILE = 1024;\nvoid run(int n) { for (int i=0; i<n; ++i) arithmetic(i); }\n"
    (before / "kernel.asc").write_text(original)
    (after / "kernel.asc").write_text(original.replace("1024", "2048"))
    admitted = [{"path": "kernel.asc", "symbol": "TILE", "kind": "tile_elements", "minimum": 256, "maximum": 8192, "multiple_of": 256}]
    assert host.attest_parameter_scope(before, after, admitted)["passed"]
    assert not host.attest_parameter_scope(before, after, [])["passed"]
    (after / "kernel.asc").write_text(original.replace("i<n", "i<1024"))
    assert not host.attest_parameter_scope(before, after, admitted)["passed"]
    (after / "kernel.asc").write_text(original + "if (case_id == 20) hardcoded_output();\n")
    assert not host.attest_parameter_scope(before, after, admitted)["passed"]


def test_build_failure_uses_official_gate_without_synthetic_measurements(tmp_path, monkeypatch):
    # Only a negative gate path is exercised. Build is deliberately made to
    # fail before any correctness, timing or profiler function can be reached.
    prepared = tmp_path / "prepared-source"
    adapter.prepare("gelu", prepared, tmp_path / "unused-upstream")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for role in ("baseline", "candidate"):
        shutil.copytree(prepared / "baseline", workspace / role)
    changed = workspace / "candidate/op_kernel/gelu_kernel.asc"
    changed.write_text(changed.read_text() + "\n// synthetic negative-path unit fixture\n")
    choice = dict(case_id=1, kernel="gelu_kernel", metric="vector_wait_ratio", expected_direction="decrease")
    host.dump(workspace / "candidate_plan.json", {"intent": "unit test build failure", "actual_parent": "original baseline",
        "mechanism": choice, "source_anchors": [{"path": "op_kernel/gelu_kernel.asc", "line": 1, "why": "unit source binding"}]})
    plan = {"operator": "gelu", "release": str(adapter.ROOT / "skill-libs/graph-base/1.0.0"),
            "profile": {"case_id": 1, "kernels": ["gelu_kernel"], "metrics": {"vector_wait_ratio": {}}}}
    host.dump(tmp_path / "plan.json", plan)
    host.dump(tmp_path / "qualification.json", {"unit_fixture": "negative build only; no hardware acceptance"})
    monkeypatch.setattr(host, "validate_plan", lambda _plan, _api: (workspace / "baseline", tmp_path / "inputs"))
    monkeypatch.setattr(host, "verify_qualification", lambda *_: tmp_path / "unexecuted-binary")
    import eval_candidate_evidence
    def unit_review(store, *_args, **_kwargs):
        digest = host.imports(Path(plan["release"]))["register_json_artifact"](
            store, {"unit_fixture": "review stub used only before a deliberately failed build"})
        return {"source_review": digest, "route_receipt": digest}
    monkeypatch.setattr(eval_candidate_evidence, "register_candidate_evidence", unit_review)

    def build_failure(*_):
        raise RuntimeError("deliberate unit build failure")

    def hardware_forbidden(*_, **__):
        raise AssertionError("hardware function reached by negative-path unit test")

    monkeypatch.setattr(host, "build", build_failure)
    monkeypatch.setattr(host, "correctness", hardware_forbidden)
    monkeypatch.setattr(host, "capture_mechanism", hardware_forbidden)
    result = host.evaluate(tmp_path / "plan.json", host.ref(tmp_path / "qualification.json"), workspace,
        tmp_path / "evaluation.json", "gelu-unit-negative-4101", 3600)
    assert result["formal_outcome"] == "build_failed"
    assert result["counts"] == {"candidates": 1, "builds": 1, "timing_groups": 0, "profile_groups": 0}
    assert not result["measured_cases_complete"]
    assert not result["full_declared_correctness"]
    assert all(case["baseline_us"] is None and case["candidate_us"] is None for case in result["cases"])
    request = host.read(tmp_path / "host-evidence/exploration-request.json")
    assert request["config"] == {}
    assert request["evidence"][0]["baseline_samples_ns"] == []
    assert request["evidence"][0]["build"] == "failed"
