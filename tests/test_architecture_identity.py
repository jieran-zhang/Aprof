"""Identity routing regressions; no SDK compilation or hardware queries."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from aprof_runtime.contracts import Context
from aprof_runtime.errors import ContractError
from aprof_runtime.graph import load_snapshot, route_graph
from aprof_runtime.planning import architecture_id, validate_planning_contract
from test_planning import context_example, rebind

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name,family", [
    ("Ascend910B4-1", "910b"), ("Ascend910B2C", "910b"),
    ("Ascend910_9362", "910c"), ("Ascend910_9392", "910c"),
    ("Ascend950DT_95A1", "950"), ("Ascend950PR_957b", "950"),
])
def test_reviewed_sdk_names_match_exactly_and_preserve_raw_identity(name, family):
    assert architecture_id(name) == family
    assert architecture_id(name.lower()) == family
    profile = context_example()["evidence"]["architecture_profile"]
    profile.update(soc_name=name, architecture_id=family, npu_arch=3510 if family == "950" else 2201)
    assert validate_planning_contract("architecture_profile", profile)["soc_name"] == name


@pytest.mark.parametrize("name", [
    "Ascend910B", "Ascend910B10", "Ascend910B2_fake", "Ascend910B4-2",
    "Ascend910C_fake", "Ascend910C2", "Ascend910_93garbage", "Ascend910_9392_extra",
    "Ascend950", "Ascend950_not_a_device", "Ascend950PR_9599_fake", "Ascend910_9599",
    "Ascend950DT_95A1/other", "Ascend910_9392 ",
])
def test_unknown_or_extended_names_cannot_authorize_stage_routes(name):
    assert architecture_id(name) == "unknown"
    graph, _ = load_snapshot(ROOT / "skillgraph/versions/v0002")
    for stage in ("algorithm_parallel", "execution"):
        value = context_example()
        value["evidence"]["optimization_stage"] = stage
        value["evidence"]["predicate_states"].update({"predicate.source.algorithm_parallel_plan_required": True})
        value["evidence"]["architecture_profile"].update(soc_name=name, architecture_id="unknown")
        rebind(value)
        result = route_graph(graph, Context.from_dict(value))
        selected = next(e for e in result.candidates if e.edge_id == result.selected_edge_id)
        assert selected.target_id == "transformation.noop"


def test_same_isa_does_not_collapse_910b_and_910c_or_enable_950_features():
    for name, family in (("Ascend910B4-1", "910b"), ("Ascend910_9392", "910c")):
        profile = context_example()["evidence"]["architecture_profile"]
        profile.update(soc_name=name, architecture_id=family, npu_arch=2201)
        validate_planning_contract("architecture_profile", profile)
        contradictory = deepcopy(profile)
        contradictory["architecture_id"] = "910b" if family == "910c" else "910c"
        with pytest.raises(ContractError, match="exact SoC"):
            validate_planning_contract("architecture_profile", contradictory)
        profile["capabilities"]["simt"] = deepcopy(profile["capabilities"]["vector"])
        with pytest.raises(ContractError, match="950 architecture"):
            validate_planning_contract("architecture_profile", profile)


@pytest.mark.parametrize("name,should_query", [("Ascend910B4-1", True),
    ("Ascend910_9392", True), ("Ascend950DT_95A1", True), ("Ascend910B4;echo", False)])
def test_probe_preserves_valid_hyphenated_name_in_argv_without_device_access(tmp_path, monkeypatch, name, should_query):
    spec = importlib.util.spec_from_file_location("identity_probe", ROOT / "scripts/probe_architecture.py")
    probe = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe)
    output = tmp_path / "profile.json"
    monkeypatch.setattr(sys, "argv", [str(probe.__file__), "--soc-name", name,
                                     "--sdk", str(tmp_path / "sdk"), "--output", str(output)])
    monkeypatch.setattr(probe, "compiler_identity", lambda *_: {
        "status": "unknown", "path": None, "version": None, "evidence_refs": []})
    def forbidden_device(*_):
        pytest.fail("SDK identity test must never initialize a device")
    monkeypatch.setattr(probe, "device_soc", forbidden_device)
    calls = []
    def run(argv, **kwargs):
        assert not kwargs.get("shell")
        calls.append(argv)
        facts = {"npu_arch": 3510 if architecture_id(name) == "950" else 2201,
                 "core_counts": {"aic": 1, "aiv": 1}, "memory_bytes": {}}
        return subprocess.CompletedProcess(argv, 0, "" if argv[0] == "g++" else json.dumps(facts), "")
    monkeypatch.setattr(probe.subprocess, "run", run)
    probe.main()
    profile = json.loads(output.read_text())
    assert profile["soc_name"] == name
    assert profile["architecture_id"] == architecture_id(name)
    assert profile["probe_kind"] == "sdk_soc"
    assert profile["visible_core_counts"] == {"aic": None, "aiv": None}
    assert all(profile["capabilities"][k]["status"] == "unknown" for k in ("simt", "ssbuffer"))
    if should_query:
        assert len(calls) == 2 and calls[1][-1] == name
    else:
        assert not calls
        assert all(count is None for count in profile["core_counts"].values())
