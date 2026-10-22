"""CPU paper fixtures: action identity, independent P/O routing and implementation gates."""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest
import yaml

from aprof_runtime import bindings, diagnosis
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.knowledge import digest, build as build_tree, verify as verify_tree

ROOT = Path(__file__).resolve().parents[2]
PARENT = Path(diagnosis.REGION) / "versions/v0003"
HASH = digest(b"fixture")


@pytest.fixture(scope="module")
def package(tmp_path_factory, request):
    """Use the frozen parent as an independent migration fixture, never rewrite the package."""
    root = tmp_path_factory.mktemp("diagnosis-package")
    # Freeze the actual imported compiler bytes inside this independent package.
    # Other maintenance agents may edit the checkout while this CPU fixture runs.
    original_file = diagnosis.__file__
    frozen_compiler = root / "runtime/src/aprof_runtime/diagnosis.py"
    frozen_compiler.parent.mkdir(parents=True)
    shutil.copy(original_file, frozen_compiler)
    diagnosis.__file__ = str(frozen_compiler)
    request.addfinalizer(lambda: setattr(diagnosis, "__file__", original_file))
    (root / "schemas").mkdir()
    for name in diagnosis.SCHEMA_NAMES + ("diagnosis-retrieval", "diagnosis-reasoning", "diagnosis-case", "diagnosis-proposal"):
        shutil.copy(ROOT / f"schemas/{name}.schema.json", root / "schemas")
    shutil.copytree(ROOT / PARENT, root / PARENT)
    manifest = Path("workflows/references/knowledge-sources-1.3.0.json")
    (root / manifest).parent.mkdir(parents=True)
    shutil.copy(ROOT / manifest, root / manifest)
    parent = json.loads((root / PARENT / "graph.json").read_text())
    region = root / diagnosis.REGION
    (region / "REGION.json").write_text(json.dumps({"schema_version": "aprof.diagnosis-region/v1", "owner": "diagnosis", "version": "v0004"}))
    for old in parent["records"]:
        record = {k: deepcopy(v) for k, v in old.items() if k not in {"body", "source_path", "source_hash"}}
        record["schema_version"] = "aprof.diagnosis-record/v1"
        record["slots"] = [{"name": "target", "kind": "object", "description": "当前目标", "required": True}]
        record["claims"] = [{"id": "historical", "text": "历史来源只用于可核验线索", "basis": "legacy_seed", "source_indexes": [0], "review_status": "gap", "limitations": ["本测试无硬件运行"]}]
        record["review"] = {"state": "gap", "source_credibility": "历史来源", "discriminating_power": "unknown", "observed_frequency": "unknown", "gaps": ["待当前任务验证"]}
        if record["kind"] == "symptom":
            record["observation"] = {"object_slots": ["target"], "rule": record["title"], "comparison_basis": "同目标比较", "unknown_when": ["缺数据"], "interpretation_boundary": "不能自动推断机制", "required_components": []}
        elif record["kind"] == "problem":
            record["analysis"] = {k: ["待验证"] for k in ["mechanism_chain", "objects_and_stages", "predictions", "supporting_checks", "counter_checks", "limits"]}
            record["analysis"].update(alternatives=[], actions=[])
        elif record["kind"] == "action":
            record["instantiation"] = {"target_slots": ["target"], "required_bindings": ["target"], "effect": "待验证变换", "costs": ["新增资源"], "unknown_policy": "C2条件分析", "replan_triggers": ["所有权改变"]}
        else:
            record["binding"] = {"object_bindings": [{"from_slot": "target", "to_slot": "target", "rule": "同对象"}], "joint_requirements": [], "exceptions": [], "rationale": "待证据判别", "discriminating_checks": ["对照机制"]}
        for source in record["sources"]:
            target = root / source["path"]
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(ROOT / source["path"], target)
        target = root / old["source_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("---\n" + yaml.safe_dump(record, allow_unicode=True, sort_keys=False) + "---\n\n" + old["body"] + "\n")
    loose = region / "sources/unused.txt"
    loose.parent.mkdir(parents=True, exist_ok=True)
    loose.write_text("未被摘录的来源仍须进入hash清单\n")
    artifact = diagnosis.build(root, PARENT)
    for name in ("action-routing", "knowledge-handoff-v3", "knowledge-route", "architecture-profile", "parallel-plan", "dispatch-plan", "knowledge-index", "knowledge-record", "context"):
        shutil.copy(ROOT / f"schemas/{name}.schema.json", root / "schemas")
    for owner in ("parallel-planning", "optimization"):
        region_path = Path(f"skills/ascendc-aprof-{owner}/knowledge")
        shutil.copytree(ROOT / region_path, root / region_path)
        index = json.loads((ROOT / region_path / "index.json").read_text())
        for record in index["records"]:
            for source in record["sources"]:
                target = root / source["path"]
                if not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(ROOT / source["path"], target)
    shutil.copy(ROOT / bindings.CONFIG, root / bindings.CONFIG)
    bindings.freeze_bases(root)
    return root, artifact


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n")
    return {"path": path.name, "sha256": file_hash(path)}


def plan(scope, *, algorithm="paper-current"):
    architecture = {"schema_version": "1.0.0", "architecture_id": "910c", "soc_name": "Ascend910C",
        "npu_arch": 2201, "sdk_version": "paper-only", "hardware_fingerprint": "paper-only",
        "probe_kind": "sdk_soc", "device_id": None, "core_counts": {"aiv": 1, "aic": 1},
        "memory_bytes": {key: 65536 for key in ("UB", "L1", "L0_A", "L0_B", "L0_C", "L2", "BT")},
        "capabilities": {}, "provenance": {"probe_source_ref": HASH, "raw_probe_ref": HASH, "sdk_header_ref": None},
        "limitations": ["CPU声明验证，不声称硬件支持或收益"]}
    parallel = {"schema_version": "1.0.0", "plan_id": "paper-plan", "operator": "paper", "source_hash": scope["parent_implementation_hash"],
        "architecture_profile_ref": content_hash(architecture), "semantic_invariants": ["output identity"], "precision_invariants": ["same visible rounding"],
        "groups": [{"group_id": "all", "algorithm": algorithm, "task_partition": "one paper task", "ownership": "disjoint output",
                    "reduction": "none", "synchronization": "same dependencies", "workspace_bytes": 0, "workspace_formula": "0",
                    "required_capabilities": [], "memory_requirements": {"UB": 4096}, "alternatives": [], "selection_evidence": [HASH]}]}
    dispatch = {"schema_version": "1.0.0", "dispatch_id": "paper-dispatch", "operator": "paper", "source_hash": scope["parent_implementation_hash"],
                "architecture_profile_ref": content_hash(architecture), "parallel_plan_ref": content_hash(parallel), "entries": [],
                "fallback": {"group_id": "all", "tiling_key": 0, "kernel_entry": "paper_kernel", "conditions": [], "required_capabilities": []}}
    contracts = {key: "unchanged" for key in bindings.CONTRACTS}
    contracts["algorithm"] = algorithm
    return {"scope": deepcopy(scope), "architecture_profile": architecture, "parallel_plan": parallel, "dispatch_plan": dispatch,
            "contracts": contracts, "implementation_freedom": {"dimensions": ["local_transfer"],
            "parameter_domains": [{"name": "tile", "minimum": 32, "maximum": 1024}], "reason": "仅允许本地搬运参数"}}


_FIXTURE_CACHE = {}


def chain_fixture(root, artifact, task, *, action_id="action.coalesce_contiguous_transfers", p_mode="KEEP", o_mode="CHANGE", workload=None, routing_features=None, routing_structure=None):
    cache_key = (str(root), content_hash(artifact), file_hash(root / bindings.CONFIG), action_id, p_mode, o_mode, content_hash(workload), content_hash(routing_features), content_hash(routing_structure))
    task.mkdir()
    if cache_key in _FIXTURE_CACHE:
        cached, files = _FIXTURE_CACHE[cache_key]
        for name, raw in files.items():
            (task / name).write_bytes(raw)
        return deepcopy(cached)
    parent_ref = {"path": "parent.cpp", "sha256": digest(b"paper parent\n")}
    (task / parent_ref["path"]).write_bytes(b"paper parent\n")
    workload_ref = write_json(task / "workload.json", workload if workload is not None else {"shape": [64], "dtype": "float32", "layout": "ND", "attributes": {}})
    structure_ref = None
    if routing_structure is not None:
        structure_ref = write_json(task / 'routing-structure.json', dict(routing_structure, parent_ref=parent_ref, workload_ref=workload_ref))
    attrs = {"platform": "dav-2201", "family": ["elementwise"], "dtype": "float32", "features": ["memory-transfer", "tiling-tail"] + (routing_features or [])}
    origin_ref = write_json(task / "context.json", {"schema_version": "1.0.0", "task_id": "paper-task", "operator": "paper",
        "hardware_fingerprint": "paper-only", "workload": {}, "budget": {}, "evidence": {"routing_attributes": attrs, **({"routing_feature_source_ref": structure_ref} if structure_ref else {})}})
    context = {"schema_version": "aprof.evidence/v1", "task_id": "paper-task", "source_context_ref": origin_ref, "attributes": attrs, "facts": {}}
    scope = {"task_id": "paper-task", "parent_implementation_hash": parent_ref["sha256"], "workload_hash": workload_ref["sha256"],
             "target_ids": ["tensor.x"], "stage": "kernel.main"}
    parent_plan = plan(scope)
    action = next(r for r in artifact["records"] if r["id"] == action_id)
    expected = {p["fact"]: p["state"] for p in action["preconditions"]}
    for owner in bindings.OWNERS:
        for r in verify_tree(root, owner)["records"]:
            for route in r.get("routes", []):
                for key in route["required_evidence"]:
                    expected.setdefault(key, True)
    expected["constraint.paper_combination_review"] = True
    nodes = {r["id"]: r for r in artifact["records"]}
    composites = {}
    views = {}
    for key in list(expected):
        symptom = nodes.get(key, {})
        if symptom.get("kind") == "symptom":
            views[key] = symptom["view"]
        components = [c["id"] for c in symptom.get("observation", {}).get("required_components", [])]
        if components:
            composites[key] = components
            for index, component in enumerate(components):
                expected[component] = expected[key] if index == 0 else True
                views[component] = symptom["view"]
    raw_ref = write_json(task / "raw.json", {"paper_only": True, "declared_states": expected})
    facts = {key: {"state": state, "kind": "raw", "predicate": key, "evidence_id": key, "ref": {**raw_ref, "locator": key},
            "derived_from": [], "scope": deepcopy(scope)} for key, state in expected.items()}
    for key, view in views.items():
        facts[key]["view"] = view
        if view == "profile":
            facts[key]["time_range"] = {"kind": "full_artifact", "aggregation": "all_recorded_samples"}
    for key, components in composites.items():
        facts[key].update(kind="derived", evidence_id=None, ref=None, derived_from=components,
                          components=components, view=nodes[key]["view"])
    targets = {}
    objects = {"tensor.x": {"object_id": "tensor.x", "kind": "tensor", "description": "纸面目标"}}
    for slot in action["slots"]:
        if not slot["required"]:
            continue
        kind, name = slot["kind"], slot["name"]
        if kind in {"stage", "workload", "implementation"}:
            identifier = "kernel.main" if name == "stage" else f"{kind}.{name}"
            objects[identifier] = {"object_id": identifier, "kind": kind, "description": slot["description"]}
        else:
            identifier = "tensor.x"
            if kind != "object":
                objects[identifier]["kind"] = kind
        targets[name] = identifier
    instance = {"instance_id": "action-instance.one", "action_id": action_id, "template_hash": content_hash(action),
        "hypothesis_id": "temporary.problem", "targets": targets, "scope": deepcopy(scope), "parameters": {"tile": 64},
        "evidence_bindings": {key: key for key in expected}, "unknowns": [], "status": "ready", "reason": "纸面来源声明",
        "parent_plan_hash": content_hash(parent_plan)}
    candidate = {"hypothesis_id": "temporary.problem", "problem_id": None, "mechanism": "临时机制复用注册A", "targets": ["tensor.x"],
        "scope": deepcopy(scope), "support": list(expected), "counter": [], "unknown": [], "alternatives": [], "checks": ["后续真实验证"],
        "status": "plausible", "reason": "纸面说明", "excluded_by": [], "independent_evidence_groups": []}
    reasoning = {"schema_version": "aprof.diagnosis-reasoning/v1", "task_id": "paper-task", "context_hash": content_hash(context),
        "knowledge_hash": content_hash(artifact), "source_context_ref": origin_ref, "context_snapshot": context,
        "current": {"implementation_ref": parent_ref, "workload_ref": workload_ref, "scope": scope,
                    "objects": list(objects.values())},
        "facts": facts, "candidates": [candidate], "action_instances": [instance], "predecessor_ref": None}
    c1 = {"schema_version": "aprof.handoff/v3", "stage": "C1", "task_id": "paper-task", "candidate_id": None,
          "parent_hash": None, "artifacts": [], "reasoning": reasoning}
    hint = bindings.default_hint(root, action_id)
    selected = {"instance": deepcopy(instance), "instance_hash": content_hash(instance), "routing_config_hash": content_hash(bindings.load_routing(root)),
        "routing_hint": hint, "parallel_route": bindings.route_parallel(root, reasoning, instance["instance_id"], hint, task_root=task),
        "parallel": {"mode": p_mode, "entry_id": None if p_mode == "KEEP" else "planning.elementwise.continuous"},
        "parent_plan": parent_plan, "confirmed_plan": deepcopy(parent_plan),
        "compatibility": {"fact_bindings": ["constraint.paper_combination_review"], "rationale": "同一owner、逻辑依赖、数值和有效访问域"}}
    if p_mode == "CHANGE":
        selected["confirmed_plan"] = plan(scope, algorithm="paper-new-plan")
    selected["confirmed_plan_ref"] = write_json(task / "confirmed-plan.json", selected["confirmed_plan"])
    c2 = {"schema_version": "aprof.handoff/v3", "stage": "C2", "task_id": "paper-task", "candidate_id": None,
          "parent_hash": content_hash(c1), "artifacts": [], "selection": selected}
    if p_mode == o_mode == "KEEP":
        source_ref = parent_ref
    else:
        (task / "candidate.cpp").write_text("paper implementation of confirmed plan\n")
        source_ref = {"path": "candidate.cpp", "sha256": file_hash(task / "candidate.cpp")}
    dispatch = deepcopy(selected["confirmed_plan"]["dispatch_plan"])
    dispatch.update(source_hash=source_ref["sha256"], implementation_source_hash=source_ref["sha256"], plan_basis_source_hash=parent_ref["sha256"])
    execution = {"instance_hash": content_hash(instance), "selection_hash": content_hash(selected),
        "optimization_route": bindings.route_optimization(root, reasoning, selected, task_root=task),
        "optimization": {"mode": o_mode, "entry_ids": [] if o_mode == "KEEP" else ["implementation.memory-transfer.coalesce"]},
        "implementation_source_ref": source_ref, "dispatch_plan": dispatch, "actual_contracts": deepcopy(selected["confirmed_plan"]["contracts"]),
        "actual_parameters": {"tile": 64}, "changes": [],
        "actual_changes": [] if p_mode == o_mode == "KEEP" else [{"target_id": "tensor.x", "source_locator": "lines:1", "description": "纸面实施同owner连续搬运或已确认计划", "intended_effect": "按声明落实动作", "limitations": ["未声称任意C++语义证明或性能收益"]}], "compatibility": deepcopy(selected["compatibility"]),
        "result": "NOOP" if p_mode == o_mode == "KEEP" else "implemented",
        "executed_instances": [] if p_mode == o_mode == "KEEP" else [instance["instance_id"]]}
    c3 = {"schema_version": "aprof.handoff/v3", "stage": "C3", "task_id": "paper-task",
          "candidate_id": None if p_mode == o_mode == "KEEP" else "paper-candidate", "parent_hash": content_hash(c2), "artifacts": [], "execution": execution}
    result = (c1, c2, c3)
    _FIXTURE_CACHE[cache_key] = (deepcopy(result), {p.name: p.read_bytes() for p in task.iterdir() if p.is_file()})
    return result


def rebind(c1, c2, c3):
    instance = c1["reasoning"]["action_instances"][0]
    c2["selection"]["instance"] = deepcopy(instance)
    c2["selection"]["instance_hash"] = content_hash(instance)
    c2["parent_hash"] = content_hash(c1)
    c3["execution"]["instance_hash"] = content_hash(instance)
    c3["execution"]["selection_hash"] = content_hash(c2["selection"])
    c3["parent_hash"] = content_hash(c2)


def test_p_and_o_are_selected_at_different_stages_without_timing(package, tmp_path):
    root, artifact = package
    chain = chain_fixture(root, artifact, tmp_path / "task")
    c1, c2, c3 = chain
    assert "optimization" not in c2["selection"]
    assert bindings.validate_chain(root, c1, c2, task_root=tmp_path / "task")["status"] == "ready"
    result = bindings.validate_chain(root, *chain, task_root=tmp_path / "task")
    assert result["status"] == "implemented"
    assert result["actual_combination"]["optimization"]["entry_ids"] == ["implementation.memory-transfer.coalesce"]
    assert not result["causal_claim"]


@pytest.mark.parametrize("p_mode,o_mode,expected", [("KEEP", "KEEP", "NOOP"), ("CHANGE", "KEEP", "implemented")])
def test_keep_retains_complete_plan_and_o_keep_implements_changed_p(package, tmp_path, p_mode, o_mode, expected):
    root, artifact = package
    task = tmp_path / "task"
    chain = chain_fixture(root, artifact, task, p_mode=p_mode, o_mode=o_mode)
    assert bindings.validate_chain(root, *chain, task_root=task)["status"] == expected
    if p_mode == "CHANGE":
        assert chain[2]["execution"]["implementation_source_ref"]["sha256"] != chain[0]["reasoning"]["current"]["implementation_ref"]["sha256"]


@pytest.mark.parametrize("damage", ["foreign_recipe", "fake_attributes", "hint_facts", "instance_parameters", "instance_target", "parent_plan", "scope", "algorithm", "dispatch", "empty_change", "fallback", "noop_execution", "empty_actual_changes", "wrong_change_target", "bad_change_locator", "fake_plan_file", "different_plan_file"])
def test_illegal_combinations_forgery_and_cross_instance_are_rejected(package, tmp_path, damage):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    if damage == "foreign_recipe":
        c3["execution"]["optimization"]["entry_ids"] = ["implementation.vector-api.cast"]
    elif damage == "fake_attributes":
        c1["reasoning"]["context_snapshot"]["attributes"]["family"] = ["matmul"]
        c1["reasoning"]["context_hash"] = content_hash(c1["reasoning"]["context_snapshot"])
        rebind(c1, c2, c3)
    elif damage == "hint_facts":
        c2["selection"]["routing_hint"]["facts"] = {"constraint.capacity": True}
        rebind(c1, c2, c3)
    elif damage == "instance_parameters":
        c2["selection"]["instance"]["parameters"]["tile"] = 128
    elif damage == "instance_target":
        c2["selection"]["instance"]["targets"]["target"] = "tensor.y"
    elif damage == "parent_plan":
        c2["selection"]["parent_plan"]["contracts"]["ownership"] = "other owner"
    elif damage == "scope":
        next(iter(c1["reasoning"]["facts"].values()))["scope"]["target_ids"] = ["tensor.y"]
        rebind(c1, c2, c3)
    elif damage == "algorithm":
        c3["execution"]["actual_contracts"]["algorithm"] = "unauthorized algorithm"
        c3["execution"]["changes"] = [{"dimension": "algorithm", "before": "paper-current", "after": "unauthorized algorithm"}]
    elif damage == "dispatch":
        c3["execution"]["dispatch_plan"]["fallback"]["kernel_entry"] = "other_entry"
    elif damage == "empty_change":
        c3["execution"]["optimization"]["entry_ids"] = []
    elif damage == "fallback":
        c3["execution"]["optimization"]["entry_ids"] = ["implementation.memory-transfer.fallback"]
    elif damage == "fake_plan_file":
        c2["selection"]["confirmed_plan_ref"]["sha256"] = content_hash(c2["selection"]["confirmed_plan"])
        rebind(c1, c2, c3)
    elif damage == "different_plan_file":
        c2["selection"]["confirmed_plan_ref"] = write_json(task / "confirmed-plan.json", {"wrong": "plan"})
        rebind(c1, c2, c3)
    elif damage == "empty_actual_changes":
        c3["execution"]["actual_changes"] = []
    elif damage == "wrong_change_target":
        c3["execution"]["actual_changes"][0]["target_id"] = "tensor.y"
    elif damage == "bad_change_locator":
        c3["execution"]["actual_changes"][0]["source_locator"] = "lines:9999"
    else:
        c3["execution"]["optimization"] = {"mode": "KEEP", "entry_ids": []}
    with pytest.raises(GraphError):
        bindings.validate_chain(root, c1, c2, c3, task_root=task)


def test_unknown_is_conditional_in_c2_but_cannot_be_implemented(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    reasoning = c1["reasoning"]
    key = "symptom.profile.mte_setup_dominated"
    reasoning["facts"][key]["state"] = "unknown"
    reasoning["candidates"][0]["support"].remove(key)
    reasoning["candidates"][0]["unknown"].append(key)
    instance = reasoning["action_instances"][0]
    instance["status"], instance["unknowns"] = "conditional", [key]
    rebind(c1, c2, c3)
    c2["selection"]["parallel_route"] = bindings.route_parallel(root, reasoning, instance["instance_id"], c2["selection"]["routing_hint"], task_root=task)
    rebind(c1, c2, c3)
    assert bindings.validate_chain(root, c1, c2, task_root=task)["status"] == "conditional"
    with pytest.raises(GraphError, match="硬前提"):
        bindings.validate_chain(root, c1, c2, c3, task_root=task)


def test_false_precondition_and_temporary_new_action_cannot_bypass_instance_gates(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task, action_id="action.decompose_tasks_dynamically", o_mode="KEEP", p_mode="CHANGE")
    key = "symptom.workload.tiny_or_overhead_limited"
    assert c1["reasoning"]["facts"][key]["state"] is False
    assert bindings.validate_chain(root, c1, c2, task_root=task)["status"] == "ready"
    c1["reasoning"]["facts"][key]["state"] = True
    rebind(c1, c2, c3)
    with pytest.raises(GraphError, match="硬前提"):
        bindings.validate_chain(root, c1, c2, task_root=task)
    c1["reasoning"]["facts"][key]["state"] = False
    c1["reasoning"]["action_instances"][0]["action_id"] = "action.temporary_unregistered"
    rebind(c1, c2, c3)
    with pytest.raises(GraphError):
        bindings.validate_chain(root, c1, c2, task_root=task)


def test_future_router_uses_actual_route_tree_and_unmatched_scope_stays_empty(package, tmp_path):
    root, artifact = package
    # A separate copy permits a real new future category without editing package knowledge.
    future = tmp_path / "future-package"
    shutil.copytree(root, future)
    owner = "parallel-planning"
    region = future / f"skills/ascendc-aprof-{owner}/knowledge"
    original = verify_tree(future, owner)
    nodes = {r["id"]: r for r in original["records"]}
    replacements = {"planning.elementwise": "planning.future", "planning.elementwise.continuous": "planning.future.method", "planning.elementwise.fallback": "planning.future.fallback"}
    for old_id, new_id in replacements.items():
        record = {k: deepcopy(v) for k, v in nodes[old_id].items() if k not in {"body", "source_path", "source_hash"}}
        record["id"] = new_id
        if old_id == "planning.elementwise":
            record["routes"] = [r for r in record["routes"] if r["target"] in replacements]
            for route in record["routes"]:
                route["target"] = replacements[route["target"]]
        else:
            record["parent"] = "planning.future"
        (region / f"future-{new_id.split('.')[-1]}.md").write_text("---\n" + yaml.safe_dump(record, allow_unicode=True, sort_keys=False) + "---\n\n" + nodes[old_id]["body"] + "\n\n纸面未来分类使用已有机制，不声称新硬件支持。\n")
    root_path = future / nodes["planning.root"]["source_path"]
    text = root_path.read_text()
    header, body = text[4:].split("\n---\n", 1)
    record = yaml.safe_load(header)
    route = deepcopy(record["routes"][0])
    route.update(target="planning.future", match=[{"field": "family", "op": "contains", "value": "future-novel"}])
    record["routes"].append(route)
    root_path.write_text("---\n" + yaml.safe_dump(record, allow_unicode=True, sort_keys=False) + "---\n" + body)
    identity = json.loads((region / "REGION.json").read_text())
    identity["version"] = f"v{int(identity['version'][1:]) + 1:04d}"
    write_json(region / "REGION.json", identity)
    build_tree(future, owner)
    # Independently add an O branch with a new feature token; no parser enum changes.
    o_region = future / "skills/ascendc-aprof-optimization/knowledge"
    o_nodes = {r["id"]: r for r in verify_tree(future, "optimization")["records"]}
    o_replacements = {"implementation.memory-transfer": "implementation.future", "implementation.memory-transfer.coalesce": "implementation.future.method", "implementation.memory-transfer.fallback": "implementation.future.fallback"}
    for old_id, new_id in o_replacements.items():
        record = {k: deepcopy(v) for k, v in o_nodes[old_id].items() if k not in {"body", "source_path", "source_hash"}}
        record["id"] = new_id
        if old_id == "implementation.memory-transfer":
            record["routes"] = [r for r in record["routes"] if r["target"] in o_replacements]
            for route in record["routes"]:
                route["target"] = o_replacements[route["target"]]
        else:
            record["parent"] = "implementation.future"
        (o_region / f"future-{new_id.split('.')[-1]}.md").write_text("---\n" + yaml.safe_dump(record, allow_unicode=True, sort_keys=False) + "---\n\n" + o_nodes[old_id]["body"] + "\n")
    o_root_path = future / o_nodes["implementation.root"]["source_path"]
    header, body = o_root_path.read_text()[4:].split("\n---\n", 1)
    record = yaml.safe_load(header)
    route = deepcopy(record["routes"][0])
    route.update(target="implementation.future", match=[{"field": "features", "op": "contains", "value": "future-feature"}])
    record["routes"].append(route)
    o_root_path.write_text("---\n" + yaml.safe_dump(record, allow_unicode=True, sort_keys=False) + "---\n" + body)
    identity = json.loads((o_region / "REGION.json").read_text())
    identity["version"] = f"v{int(identity['version'][1:]) + 1:04d}"
    write_json(o_region / "REGION.json", identity)
    build_tree(future, "optimization")
    config = json.loads((future / bindings.CONFIG).read_text())
    row = next(r for r in config["actions"] if r["action_id"] == "action.coalesce_contiguous_transfers")
    row["planning_subtrees"] = ["planning.future"]
    row["optimization_subtrees"] = ["implementation.future"]
    write_json(future / bindings.CONFIG, config)
    with pytest.raises(GraphError, match="精确快照"):
        bindings.load_routing(future)
    bindings.freeze_bases(future)
    task = tmp_path / "future-task"
    c1, c2, c3 = chain_fixture(future, artifact, task, p_mode="CHANGE")
    # Update the authoritative Context itself, then freeze a new C1; the hint never changes facts.
    origin = json.loads((task / "context.json").read_text())
    origin["evidence"]["routing_attributes"]["family"] = ["future-novel"]
    origin["evidence"]["routing_attributes"]["features"] = ["future-feature"]
    ref = write_json(task / "context.json", origin)
    reasoning = c1["reasoning"]
    reasoning["source_context_ref"] = ref
    reasoning["context_snapshot"]["source_context_ref"] = ref
    reasoning["context_snapshot"]["attributes"] = deepcopy(origin["evidence"]["routing_attributes"])
    reasoning["context_hash"] = content_hash(reasoning["context_snapshot"])
    c2["selection"]["parallel"]["entry_id"] = "planning.future.method"
    c2["selection"]["parallel_route"] = bindings.route_parallel(future, reasoning, reasoning["action_instances"][0]["instance_id"], c2["selection"]["routing_hint"], task_root=task)
    assert c2["selection"]["parallel_route"]["matches"][0]["id"] == "planning.future.method"
    rebind(c1, c2, c3)
    c3["execution"]["optimization_route"] = bindings.route_optimization(future, reasoning, c2["selection"], task_root=task)
    c3["execution"]["optimization"]["entry_ids"] = ["implementation.future.method"]
    assert c3["execution"]["optimization_route"]["matches"][0]["id"] == "implementation.future.method"
    assert bindings.validate_chain(future, c1, c2, c3, task_root=task)["status"] == "implemented"
    wrong = deepcopy(reasoning["context_snapshot"])
    wrong["attributes"]["family"] = ["unseen-family"]
    assert bindings.route_candidates(verify_tree(future, owner), wrong, ["planning.future"])["matches"] == []


def test_coverage_is_reviewed_scope_and_keeps_new_actions_pending(package):
    root, artifact = package
    report = bindings.coverage(root)
    assert report["reviewed_actions"] == 28
    assert len(report["variant_reviews"]) == 12
    assert len(report["proposals"]) == 2
    assert not report["execution_coverage_claim"]
    assert all(p["status"] == "pending_source_review" for p in report["proposals"])


def test_first_plan_and_unknown_capacity_allow_c2_analysis_but_c3_stays_blocked(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task, p_mode="CHANGE", o_mode="KEEP")
    selection = c2["selection"]
    c1["reasoning"]["action_instances"][0]["parent_plan_hash"] = None
    selection["parent_plan"] = None
    confirmed = selection["confirmed_plan"]
    confirmed["architecture_profile"]["memory_bytes"]["UB"] = None
    arch_hash = content_hash(confirmed["architecture_profile"])
    confirmed["parallel_plan"]["architecture_profile_ref"] = arch_hash
    confirmed["dispatch_plan"].update(architecture_profile_ref=arch_hash, parallel_plan_ref=content_hash(confirmed["parallel_plan"]))
    selection["confirmed_plan_ref"] = write_json(task / "confirmed-plan.json", confirmed)
    rebind(c1, c2, c3)
    result = bindings.validate_chain(root, c1, c2, task_root=task)
    assert result["status"] == "conditional" and "capacity.UB" in result["missing"]
    with pytest.raises(GraphError, match="硬门禁"):
        bindings.validate_chain(root, c1, c2, c3, task_root=task)
    selection["parallel"] = {"mode": "KEEP", "entry_id": None}
    rebind(c1, c2, c3)
    with pytest.raises(GraphError, match="P_KEEP"):
        bindings.validate_chain(root, c1, c2, task_root=task)


def test_arbitrary_true_fact_cannot_be_relabelled_as_capacity(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    reasoning = c1["reasoning"]
    reasoning["action_instances"][0]["evidence_bindings"]["constraint.capacity"] = "constraint.paper_combination_review"
    rebind(c1, c2, c3)
    with pytest.raises(GraphError, match="predicate"):
        bindings.validate_chain(root, c1, c2, task_root=task)


def test_two_instances_of_same_action_keep_scoped_facts_and_cannot_be_swapped(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    reasoning = c1["reasoning"]
    reasoning["current"]["scope"]["target_ids"].append("tensor.y")
    reasoning["current"]["objects"].append({"object_id": "tensor.y", "kind": "tensor", "description": "第二个独立目标"})
    scope_y = deepcopy(c2["selection"]["instance"]["scope"])
    scope_y["target_ids"] = ["tensor.y"]
    raw_y = write_json(task / "raw-y.json", {"target_id": "tensor.y", "paper_only": True})
    keys = list(reasoning["facts"])
    for key in keys:
        fact = deepcopy(reasoning["facts"][key])
        fact.update(scope=deepcopy(scope_y), predicate=key, evidence_id="y." + key, ref={**raw_y, "locator": key})
        reasoning["facts"]["y." + key] = fact
    second = deepcopy(reasoning["action_instances"][0])
    second.update(instance_id="action-instance.two", hypothesis_id="temporary.second", scope=scope_y,
                  targets={"target": "tensor.y"}, evidence_bindings={key: "y." + key for key in keys}, parent_plan_hash=content_hash(plan(scope_y)))
    candidate = deepcopy(reasoning["candidates"][0])
    candidate.update(hypothesis_id="temporary.second", scope=deepcopy(scope_y), targets=["tensor.y"], support=["y." + key for key in keys])
    reasoning["candidates"].append(candidate)
    reasoning["action_instances"].append(second)
    rebind(c1, c2, c3)
    assert bindings.validate_chain(root, c1, c2, c3, task_root=task)["status"] == "implemented"
    c3["execution"]["instance_hash"] = content_hash(second)
    with pytest.raises(GraphError, match="串实例"):
        bindings.validate_chain(root, c1, c2, c3, task_root=task)


def test_derived_route_facts_keep_real_raw_file_references(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    reasoning = c1["reasoning"]
    key = "symptom.profile.mte_setup_dominated"
    raw = deepcopy(reasoning["facts"][key])
    raw.update(predicate="paper.raw_mte", view="profile")
    reasoning["facts"]["paper.raw_mte"] = raw
    reasoning["facts"][key] = {"state": True, "kind": "derived", "view": "profile", "predicate": key,
        "evidence_id": None, "ref": None, "derived_from": ["paper.raw_mte"], "scope": deepcopy(raw["scope"])}
    context = bindings.routing_context(root, reasoning, reasoning["action_instances"][0], task_root=task)
    projected = context["facts"][key]
    assert projected["kind"] == "derived"
    assert projected["ref"] == raw["ref"]
    assert projected["ref"]["sha256"] == file_hash(task / projected["ref"]["path"])


def test_json_identity_and_enum_values_preserve_boolean_integer_float_types():
    assert not bindings._domain(True, {"values": [1]})
    assert not bindings._domain(1.0, {"values": [1]})
    assert bindings._domain(1, {"values": [1]})
    assert not bindings._same({"parameters": {"tile": 1}}, {"parameters": {"tile": True}})
    assert not bindings._same({"parameters": {"tile": 1}}, {"parameters": {"tile": 1.0}})


@pytest.mark.parametrize("value", [True, 1.0])
def test_c2_instance_cannot_replace_integer_with_boolean_or_float(package, tmp_path, value):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    c1["reasoning"]["action_instances"][0]["parameters"]["tile"] = 1
    c3["execution"]["actual_parameters"]["tile"] = 1
    rebind(c1, c2, c3)
    c2["selection"]["instance"]["parameters"]["tile"] = value
    c3["execution"]["selection_hash"] = content_hash(c2["selection"])
    c3["parent_hash"] = content_hash(c2)
    with pytest.raises(GraphError, match="串实例"):
        bindings.validate_chain(root, c1, c2, c3, task_root=task)


@pytest.mark.parametrize("value", [True, 1.0])
def test_parameter_enum_cannot_approve_boolean_or_float_as_integer(package, tmp_path, value):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    selection = c2["selection"]
    for name in ("parent_plan", "confirmed_plan"):
        selection[name]["implementation_freedom"]["parameter_domains"] = [{"name": "tile", "values": [1]}]
    c1["reasoning"]["action_instances"][0]["parent_plan_hash"] = content_hash(selection["parent_plan"])
    selection["confirmed_plan_ref"] = write_json(task / "confirmed-plan.json", selection["confirmed_plan"])
    rebind(c1, c2, c3)
    c3["execution"]["optimization_route"] = bindings.route_optimization(root, c1["reasoning"], selection, task_root=task)
    c3["execution"]["actual_parameters"]["tile"] = value
    with pytest.raises(GraphError, match="参数变化"):
        bindings.validate_chain(root, c1, c2, c3, task_root=task)


def test_confirmed_plan_file_identity_does_not_equate_true_with_one(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    selection = c2["selection"]
    for name in ("parent_plan", "confirmed_plan"):
        selection[name]["contracts"]["paper_numeric"] = 1
    c1["reasoning"]["action_instances"][0]["parent_plan_hash"] = content_hash(selection["parent_plan"])
    forged = deepcopy(selection["confirmed_plan"])
    forged["contracts"]["paper_numeric"] = True
    selection["confirmed_plan_ref"] = write_json(task / "confirmed-plan.json", forged)
    rebind(c1, c2, c3)
    with pytest.raises(GraphError, match="确认计划不同"):
        bindings.validate_chain(root, c1, c2, task_root=task)


def test_dispatch_numeric_representation_cannot_change_without_permission(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    c3["execution"]["dispatch_plan"]["fallback"]["tiling_key"] = 0.0
    with pytest.raises(GraphError, match="dispatch 域变化"):
        bindings.validate_chain(root, c1, c2, c3, task_root=task)


@pytest.mark.parametrize("damage", ["unknown_schema", "bad_context", "bool_attribute", "bad_evidence"])
def test_context_authority_rejects_unrecognized_schema_and_type_forgery(package, tmp_path, damage):
    root, artifact = package
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    reasoning = c1["reasoning"]
    origin = json.loads((task / "context.json").read_text())
    if damage == "unknown_schema":
        origin["schema_version"] = "paper.context/v1"
    elif damage == "bad_context":
        del origin["hardware_fingerprint"]
    elif damage == "bool_attribute":
        origin["evidence"]["routing_attributes"]["paper_attribute"] = 1
        reasoning["context_snapshot"]["attributes"]["paper_attribute"] = True
    else:
        origin = {"schema_version": "aprof.evidence/v1", "task_id": reasoning["task_id"], "attributes": reasoning["context_snapshot"]["attributes"], "facts": {}}
    origin_ref = write_json(task / "context.json", origin)
    reasoning["source_context_ref"] = origin_ref
    reasoning["context_snapshot"]["source_context_ref"] = origin_ref
    reasoning["context_hash"] = content_hash(reasoning["context_snapshot"])
    with pytest.raises(GraphError):
        bindings.routing_context(root, reasoning, reasoning["action_instances"][0], task_root=task, artifact=artifact)


def test_frozen_bundle_replays_complete_chain_without_latest_region_or_config(package, tmp_path, monkeypatch):
    original, artifact = package
    root = tmp_path / "historical-package"
    shutil.copytree(original, root)
    task = tmp_path / "task"
    c1, c2, c3 = chain_fixture(root, artifact, task)
    config = bindings.load_routing(root)
    ref = bindings.routing_snapshot_ref(root, config)
    for owner in bindings.OWNERS:
        base = config["bases"][owner]
        assert (root / base["path"]).read_bytes() == (root / f"skills/ascendc-aprof-{owner}/knowledge/index.json").read_bytes()
        assert base["file_sha256"] == file_hash(root / base["path"])
    # Future maintenance may replace both mutable entrypoints; historical replay uses neither.
    write_json(root / bindings.CONFIG, {"future": "routing config"})
    write_json(root / diagnosis.REGION / "REGION.json", {"schema_version": "aprof.diagnosis-region/v1", "owner": "diagnosis", "version": "v9999"})
    monkeypatch.setattr(bindings, "_artifacts", lambda *args: pytest.fail("historical replay read latest knowledge"))
    artifacts, frozen_config = bindings.load_frozen_bundle(root, ref)
    assert content_hash(artifacts["diagnosis"]) == content_hash(artifact)
    assert bindings.load_routing(root, artifacts=artifacts, routing_config=frozen_config) == frozen_config
    assert bindings.route_optimization(root, c1["reasoning"], c2["selection"], task_root=task,
        artifacts=artifacts, routing_config=frozen_config) == c3["execution"]["optimization_route"]
    outcome = bindings.validate_chain(root, c1, c2, c3, task_root=task, artifacts=artifacts, routing_config=frozen_config)
    assert outcome["status"] == "implemented"


@pytest.mark.parametrize("target", ["tree", "routing"])
def test_freeze_refuses_different_bytes_at_existing_immutable_address(package, tmp_path, target):
    original, artifact = package
    root = tmp_path / "package"
    shutil.copytree(original, root)
    config = bindings.load_routing(root)
    ref = bindings.routing_snapshot_ref(root, config)
    path = root / (config["bases"]["optimization"]["path"] if target == "tree" else ref["path"])
    changed = path.read_bytes() + b"\n"
    path.write_bytes(changed)
    with pytest.raises(GraphError, match="不可变快照"):
        bindings.freeze_bases(root)
    assert path.read_bytes() == changed


def test_frozen_replay_checks_archived_sources_for_loader_and_explicit_bundle(package, tmp_path):
    original, artifact = package
    root = tmp_path / "package"
    shutil.copytree(original, root)
    task = tmp_path / "task"
    chain = chain_fixture(root, artifact, task)
    config = bindings.load_routing(root)
    ref = bindings.routing_snapshot_ref(root, config)
    artifacts, config = bindings.load_frozen_bundle(root, ref)
    source = next(source for r in artifacts["optimization"]["records"] for source in r["sources"] if source["path"] not in artifact["source_hashes"])
    path = root / source["path"]
    path.write_bytes(path.read_bytes() + b"\n// altered archived source\n")
    with pytest.raises(GraphError, match="hash"):
        bindings.load_frozen_bundle(root, ref)
    with pytest.raises(GraphError, match="hash"):
        bindings.validate_chain(root, *chain, task_root=task, artifacts=artifacts, routing_config=config)


def test_frozen_source_excerpt_and_line_ranges_are_verified(package):
    root, artifact = package
    tree = verify_tree(root, "optimization")
    corrupted = deepcopy(tree)
    corrupted["records"][0]["sources"][0]["excerpt_sha256"] = digest(b"wrong excerpt")
    with pytest.raises(GraphError, match="摘录hash"):
        bindings._validate_frozen_sources(root, corrupted)
    corrupted = deepcopy(tree)
    corrupted["records"][0]["sources"][0]["lines"] = [10**8, 10**8 + 1]
    with pytest.raises(GraphError, match="lines越界"):
        bindings._validate_frozen_sources(root, corrupted)


def test_real_v5_metadata_additions_keep_v4_handoffs_replayable_and_fixture_generic(package, tmp_path):
    original, v4 = package
    root = tmp_path / "future-package"
    shutil.copytree(original, root)
    old_task = tmp_path / "old-task"
    old_chain = chain_fixture(root, v4, old_task)
    old_ref = bindings.routing_snapshot_ref(root, bindings.load_routing(root))
    action = next(r for r in v4["records"] if r["id"] == "action.keep_intermediate_onchip")
    symptom_id = next(p["fact"] for p in action["preconditions"] if p["fact"].startswith("symptom."))
    symptom = next(r for r in v4["records"] if r["id"] == symptom_id)
    for record in (action, symptom):
        path = root / record["source_path"]
        header, body = path.read_text()[4:].split("\n---\n", 1)
        header = yaml.safe_load(header)
        if record["kind"] == "action":
            header["slots"] += [{"name": name, "kind": kind, "description": "纸面角色对象", "required": True}
                for name, kind in (("stage", "stage"), ("workload", "workload"), ("implementation", "implementation"), ("producer", "stage"), ("consumer", "stage"))]
        else:
            header["observation"]["required_components"] = [{"id": "paper.component.one", "description": "第一项联合观察"}, {"id": "paper.component.two", "description": "第二项联合观察"}]
        path.write_text("---\n" + yaml.safe_dump(header, allow_unicode=True, sort_keys=False) + "---\n" + body)
    write_json(root / diagnosis.REGION / "REGION.json", {"schema_version": "aprof.diagnosis-region/v1", "owner": "diagnosis", "version": "v0005"})
    from test_diagnosis_v4 import copy_condition_policy
    copy_condition_policy(root, v4)
    v5 = diagnosis.build(root, Path(diagnosis.REGION) / "versions/v0004")
    bindings.freeze_bases(root)
    new_task = tmp_path / "new-task"
    new_chain = chain_fixture(root, v5, new_task, action_id=action["id"], p_mode="CHANGE", o_mode="KEEP")
    instance = new_chain[0]["reasoning"]["action_instances"][0]
    assert {"producer", "consumer", "stage", "implementation", "workload"} <= set(instance["targets"])
    composite = new_chain[0]["reasoning"]["facts"][symptom_id]
    assert composite["kind"] == "derived" and set(composite["components"]) == {"paper.component.one", "paper.component.two"}
    # 新版本新增选择记录，旧链仍按冻结 v4 原义回放。
    with pytest.raises(GraphError, match="唯一 action-decision"):
        bindings.validate_chain(root, *new_chain, task_root=new_task)
    artifacts, config = bindings.load_frozen_bundle(root, old_ref)
    assert artifacts["diagnosis"]["version"] == "v0004"
    assert bindings.validate_chain(root, *old_chain, task_root=old_task, artifacts=artifacts, routing_config=config)["status"] == "implemented"
