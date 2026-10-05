from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from aprof_runtime.contracts import Context, validate_contract
from aprof_runtime.errors import ContractError
from aprof_runtime.graph import load_snapshot, route_graph
from aprof_runtime.jsonio import content_hash
from aprof_runtime.planning import (MEMORIES, SCHEMAS, architecture_id, schema,
    select_dispatch, validate_planning_context, validate_planning_contract, verify_profile_probe)

ROOT = Path(__file__).resolve().parents[1]
HASH = "sha256:" + "a" * 64


def context_example():
    """Synthetic fixture; numeric facts are not hardware evidence."""
    profile = dict(schema_version="1.0.0", hardware_fingerprint="synthetic-910b",
        architecture_id="910b", soc_name="Ascend910B2", npu_arch=2201,
        sdk_version="synthetic", probe_kind="sdk_soc", device_id=None,
        core_counts={"aic": 24, "aiv": 48}, memory_bytes={m: 196608 for m in MEMORIES},
        capabilities={"vector": {"status": "supported", "basis": "test fixture", "evidence_refs": [HASH]}},
        provenance={"probe_source_ref": HASH, "raw_probe_ref": HASH, "sdk_header_ref": HASH},
        limitations=["Synthetic test fixture, never measured evidence."])
    group = dict(group_id="generic", algorithm="exact elementwise algorithm", task_partition="contiguous outer tiles",
        ownership="one writer per output", reduction="none", synchronization="per-core dependency events",
        workspace_bytes=0, workspace_formula="0", required_capabilities=["vector"], memory_requirements={"UB": 1024},
        alternatives=["one tile per core"], selection_evidence=[HASH])
    plan = dict(schema_version="1.0.0", plan_id="test-plan", operator="test_op", source_hash=HASH,
        architecture_profile_ref=content_hash(profile), semantic_invariants=["all outputs computed once"],
        precision_invariants=["preserve dtype and rounding"], groups=[group])
    entry = dict(group_id="generic", tiling_key=1, kernel_entry="small_entry",
        conditions=[{"field": "numel", "op": "le", "value": 128}], required_capabilities=["vector"])
    dispatch = dict(schema_version="1.0.0", dispatch_id="test-dispatch", operator="test_op", source_hash=HASH,
        architecture_profile_ref=content_hash(profile), parallel_plan_ref=content_hash(plan), entries=[entry],
        fallback=dict(group_id="generic", tiling_key=0, kernel_entry="generic_entry", conditions=[], required_capabilities=[]))
    evidence = {"optimization_stage": "execution", "predicate_states": {"predicate.profile.vector_granularity_low": True}}
    for kind, artifact in (("architecture_profile", profile), ("parallel_plan", plan), ("dispatch_plan", dispatch)):
        evidence[kind] = artifact
        evidence[kind + "_ref"] = content_hash(artifact)
    return dict(schema_version="1.0.0", task_id="test-task", operator="test_op", hardware_fingerprint="synthetic-910b",
        workload={"source_hash": HASH, "metadata": {"shape": [128], "dtype": "float32", "layout": "ND", "attributes": {}},
                  "tiling_key": 1, "workload_group": "generic"}, budget={}, evidence=evidence)


def rebind(context):
    e = context["evidence"]
    e["architecture_profile_ref"] = content_hash(e["architecture_profile"])
    e["parallel_plan"]["architecture_profile_ref"] = e["architecture_profile_ref"]
    e["parallel_plan_ref"] = content_hash(e["parallel_plan"])
    e["dispatch_plan"].update(architecture_profile_ref=e["architecture_profile_ref"], parallel_plan_ref=e["parallel_plan_ref"])
    e["dispatch_plan_ref"] = content_hash(e["dispatch_plan"])


@pytest.mark.parametrize("name,expected", [("Ascend910B2", "910b"), ("Ascend910_9392", "910c"),
    ("Ascend910C", "910c"), ("Ascend950PR_9599", "950"), ("Ascend910B", "unknown"), ("other", "unknown")])
def test_soc_disambiguation(name, expected):
    assert architecture_id(name) == expected


def test_schema_mirrors_and_strict_fields():
    for kind in SCHEMAS:
        assert json.loads((ROOT / "schemas" / (kind.replace("_", "-") + ".schema.json")).read_text()) == schema(kind)
        value = context_example()["evidence"][kind]
        assert validate_contract(kind, value) == value
        value["unknown"] = 1
        with pytest.raises(ContractError): validate_contract(kind, value)


def test_hash_source_architecture_capacity_and_dispatch_binding():
    value = context_example()
    validate_planning_context(Context.from_dict(value), execution=True)
    broken = deepcopy(value); broken["evidence"]["parallel_plan"]["plan_id"] = "altered"
    with pytest.raises(ContractError, match="canonical"): validate_planning_context(Context.from_dict(broken), execution=True)
    broken = deepcopy(value); broken["workload"]["source_hash"] = "sha256:" + "b" * 64
    with pytest.raises(ContractError, match="source identity"): validate_planning_context(Context.from_dict(broken), execution=True)
    for capacity in (None, 1):
        broken = deepcopy(value); broken["evidence"]["architecture_profile"]["memory_bytes"]["UB"] = capacity; rebind(broken)
        with pytest.raises(ContractError, match="UB capacity"): validate_planning_context(Context.from_dict(broken), execution=True)
    broken = deepcopy(value); broken["evidence"]["dispatch_plan"]["fallback"]["group_id"] = "missing"; rebind(broken)
    with pytest.raises(ContractError, match="unknown parallel group"): validate_planning_context(Context.from_dict(broken), execution=True)


def test_plan_basis_and_candidate_implementation_are_explicitly_bound():
    value = context_example()
    implementation = "sha256:" + "b" * 64
    value["workload"].update(plan_basis_source_hash=HASH, implementation_source_hash=implementation)
    dispatch = value["evidence"]["dispatch_plan"]
    dispatch.update(source_hash=implementation, plan_basis_source_hash=HASH, implementation_source_hash=implementation)
    rebind(value)
    validate_planning_context(Context.from_dict(value), execution=True)
    broken = deepcopy(value)
    broken["evidence"]["dispatch_plan"]["plan_basis_source_hash"] = implementation
    rebind(broken)
    with pytest.raises(ContractError, match="source identity"):
        validate_planning_context(Context.from_dict(broken), execution=True)
    broken = deepcopy(dispatch); del broken["implementation_source_hash"]
    with pytest.raises(ContractError, match="both plan basis"):
        validate_planning_contract("dispatch_plan", broken)


def test_dispatch_boundaries_fallback_overlap_and_identity_rejection():
    value = context_example(); plan = value["evidence"]["dispatch_plan"]; metadata = value["workload"]["metadata"]
    for n, key in ((0, 1), (127, 1), (128, 1), (129, 0), (10000, 0)):
        assert select_dispatch(plan, {**metadata, "shape": [n]})["tiling_key"] == key
    broken = deepcopy(plan); broken["entries"].append({**deepcopy(plan["entries"][0]), "tiling_key": 2})
    with pytest.raises(ContractError, match="overlapping"): select_dispatch(broken, metadata)
    broken["entries"][1]["tiling_key"] = 1
    with pytest.raises(ContractError, match="duplicate"): select_dispatch(broken, metadata)
    broken = deepcopy(plan); broken["entries"][0]["conditions"][0]["field"] = "attributes.case_id"
    with pytest.raises(ContractError, match="case identity"): select_dispatch(broken, metadata)
    with pytest.raises(ContractError): select_dispatch(plan, {**metadata, "case_id": 1})
    broken = deepcopy(plan); broken["entries"][0]["tiling_key"] = 2**64
    with pytest.raises(ContractError): select_dispatch(broken, metadata)


def test_v2_stage_masks_and_conservative_unknown():
    graph, _ = load_snapshot(ROOT / "skillgraph/versions/v0002")
    value = context_example()
    decision = route_graph(graph, Context.from_dict(value))
    selected = next(e for e in decision.candidates if e.edge_id == decision.selected_edge_id)
    assert selected.target_id == "transformation.batch_vector_api_calls"
    for alteration in ("stage", "missing_plan", "key", "unknown_arch", "unsupported_capability"):
        broken = deepcopy(value)
        if alteration == "stage": broken["evidence"]["optimization_stage"] = "algorithm_parallel"
        elif alteration == "missing_plan": broken["evidence"].pop("parallel_plan")
        elif alteration == "key": broken["workload"]["tiling_key"] = 99
        elif alteration == "unknown_arch":
            broken["evidence"]["architecture_profile"].update(soc_name="unrecognized", architecture_id="unknown"); rebind(broken)
        else:
            broken["evidence"]["architecture_profile"]["capabilities"]["vector"]["status"] = "unknown"; rebind(broken)
        result = route_graph(graph, Context.from_dict(broken))
        assert next(e for e in result.candidates if e.edge_id == result.selected_edge_id).target_id == "transformation.noop"


def test_algorithm_route_does_not_require_an_existing_plan():
    graph, _ = load_snapshot(ROOT / "skillgraph/versions/v0002")
    value = context_example()
    value["evidence"]["optimization_stage"] = "algorithm_parallel"
    value["evidence"]["predicate_states"] = {"predicate.source.algorithm_parallel_plan_required": True}
    value["evidence"].pop("parallel_plan")
    route = route_graph(graph, Context.from_dict(value))
    assert next(e for e in route.candidates if e.edge_id == route.selected_edge_id).target_id == "transformation.select_parallel_algorithm"


def test_v1_routing_ignores_new_context_and_v2_compiles_identically():
    old, _ = load_snapshot(ROOT / "skillgraph/versions/v0001")
    value = context_example(); value["evidence"]["optimization_stage"] = "invalid"
    route = route_graph(old, Context.from_dict(value))
    assert next(e for e in route.candidates if e.edge_id == route.selected_edge_id).target_id == "transformation.batch_vector_api_calls"
    subprocess.run([sys.executable, str(ROOT / "scripts/compile_graph_v2.py"), "--check"], check=True, capture_output=True)


def test_cli_dispatch_and_new_contract(tmp_path):
    from aprof_runtime.cli import main
    value = context_example()
    for kind in SCHEMAS:
        path = tmp_path / (kind + ".json"); path.write_text(json.dumps(value["evidence"][kind]))
        assert main(["contract", "validate", "--kind", kind, "--input", str(path)]) == 0
    path = tmp_path / "metadata.json"; path.write_text(json.dumps(value["workload"]["metadata"]))
    assert main(["dispatch", "select", "--plan", str(tmp_path / "dispatch_plan.json"), "--workload", str(path)]) == 0


def test_probe_failure_keeps_unknown_capabilities():
    spec = importlib.util.spec_from_file_location("probe_architecture", ROOT / "scripts/probe_architecture.py")
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    profile = module.build_profile({"probe_kind": "unavailable", "soc_name": None, "errors": ["SDK unavailable"]},
        "unknown", {"probe_source_ref": HASH, "raw_probe_ref": HASH, "sdk_header_ref": None})
    assert profile["architecture_id"] == "unknown"
    assert profile["core_counts"] == {"aic": None, "aiv": None}
    assert all(c["status"] == "unknown" for c in profile["capabilities"].values())


def test_profile_values_are_recomputed_from_raw_probe():
    profile = context_example()["evidence"]["architecture_profile"]
    raw = dict(probe_kind=profile["probe_kind"], device_id=profile["device_id"], soc_name=profile["soc_name"],
               platform={k: profile[k] for k in ("npu_arch", "core_counts", "memory_bytes")})
    profile["provenance"]["raw_probe_ref"] = content_hash(raw)
    verify_profile_probe(profile, raw)
    profile["memory_bytes"] = {**profile["memory_bytes"], "UB": 999999}
    with pytest.raises(ContractError, match="reproduce"): verify_profile_probe(profile, raw)


def test_visibility_and_compiler_are_distinct_from_sdk_capacity():
    profile = context_example()['evidence']['architecture_profile']
    profile['visible_core_counts'] = {'aic': None, 'aiv': 12}
    profile['compiler'] = {'status':'unknown','path':None,'version':None,'evidence_refs':[]}
    raw = dict(probe_kind=profile['probe_kind'],device_id=profile['device_id'],soc_name=profile['soc_name'],
        platform={k:profile[k] for k in ('npu_arch','core_counts','memory_bytes')},
        visible_core_counts=deepcopy(profile['visible_core_counts']),compiler=deepcopy(profile['compiler']))
    profile['provenance']['raw_probe_ref'] = content_hash(raw)
    verify_profile_probe(profile,raw)
    profile['visible_core_counts']['aiv'] = 48
    with pytest.raises(ContractError,match='reproduce'): verify_profile_probe(profile,raw)


def test_950_specific_capabilities_require_compiler_identity_and_feature_evidence():
    profile = context_example()['evidence']['architecture_profile']
    profile.update(architecture_id='950',soc_name='Ascend950PR_9599',npu_arch=3510)
    profile['capabilities']['simt'] = {'status':'supported','basis':'synthetic target compile evidence','evidence_refs':[HASH]}
    with pytest.raises(ContractError,match='verified compiler'): validate_planning_contract('architecture_profile',profile)
    profile['compiler'] = {'status':'verified','path':'/synthetic/compiler','version':'synthetic compiler','evidence_refs':[HASH]}
    validate_planning_contract('architecture_profile',profile)
    profile['compiler']['evidence_refs'] = []
    with pytest.raises(ContractError,match='verified compiler'): validate_planning_contract('architecture_profile',profile)


def test_device_probe_reports_query_failure_as_unknown_and_cleans_up(tmp_path,monkeypatch):
    from unittest.mock import Mock
    from types import SimpleNamespace
    spec=importlib.util.spec_from_file_location('probe_architecture',ROOT/'scripts/probe_architecture.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def info(device,attribute,target):
        target._obj.value=12 if attribute==201 else 0
        return 0 if attribute==201 else 123
    library=SimpleNamespace(aclInit=Mock(return_value=0),aclrtSetDevice=Mock(return_value=0),
        aclrtGetSocName=Mock(return_value=b'Ascend910_9392'),aclrtGetDeviceInfo=Mock(side_effect=info),
        aclrtResetDevice=Mock(return_value=0),aclFinalize=Mock(return_value=0))
    monkeypatch.setattr(module.ctypes,'CDLL',lambda _:library)
    facts=module.device_soc(tmp_path,0)
    assert facts['visible_core_counts']=={'aic':None,'aiv':12}
    library.aclrtResetDevice.assert_called_once_with(0);library.aclFinalize.assert_called_once_with()
