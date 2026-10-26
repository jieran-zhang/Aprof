"""选择 contract 的 CPU 反例：收益未知不封路，安全未知不授权实施。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from aprof_runtime import action_decision, bindings, diagnosis
from aprof_runtime.diagnosis_reasoning import fact_state
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.knowledge_history import knowledge_source
from test_action_handoff_v3 import chain_fixture, rebind, write_json

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def package(tmp_path_factory):
    root = tmp_path_factory.mktemp("decision-package") / "package"
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    # v1 合同测试固定回放 D5，不能因为活跃包升级 D6 就改写历史记录。
    candidates = []
    for path in (root / bindings.ROUTING_SNAPSHOTS).glob("*.json"):
        config = json.loads(path.read_text())
        if config.get("bases", {}).get("diagnosis", {}).get("version") == "v0005":
            candidates.append((path, config))
    assert candidates, "缺少 D5 冻结 routing bundle"
    path, config = sorted(candidates, key=lambda pair: pair[1]["version"])[-1]
    artifacts, config = bindings.load_frozen_bundle(root, {"path": str(path.relative_to(root)), "sha256": file_hash(path)})
    (root / bindings.CONFIG).write_bytes(path.read_bytes())
    artifact = artifacts["diagnosis"]
    assert action_decision.required_decision_version(artifact) == "aprof.action-decision/v1"
    # 共用旧 chain_fixture 的读取入口；只在此隔离根返回已经核验的冻结数据。
    import test_action_handoff_v3 as handoff_fixture
    original_diagnosis, original_tree = diagnosis.verify, bindings.verify_tree
    def frozen_diagnosis(candidate):
        return deepcopy(artifact) if Path(candidate).resolve() == root.resolve() else original_diagnosis(candidate)
    def frozen_tree(candidate, owner):
        return deepcopy(artifacts[owner]) if Path(candidate).resolve() == root.resolve() else original_tree(candidate, owner)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(diagnosis, "verify", frozen_diagnosis)
        patch.setattr(bindings, "verify_tree", frozen_tree)
        patch.setattr(handoff_fixture, "verify_tree", frozen_tree)
        yield root, artifact


def body_locator(path):
    lines = path.read_text().splitlines()
    end = next(i for i in range(1, len(lines)) if lines[i] == "---")
    return "lines:" + str(next(i + 1 for i in range(end + 1, len(lines)) if lines[i].strip()))


def make_decision(root, artifact, task, *, workload=None, routing_features=None, routing_structure=None):
    c1, c2, c3 = chain_fixture(root, artifact, task, workload=workload, routing_features=routing_features, routing_structure=routing_structure)
    reasoning = c1["reasoning"]
    instance = reasoning["action_instances"][0]
    source_fact = "symptom.source.inner_loop_copy"
    policy_ref, policies = action_decision.condition_policy(root, artifact)
    policy = policies[instance["action_id"]]
    unknowns = [{"id": "u." + h["id"], "kind": "performance", "fact": (h["legacy_condition"] or {}).get("fact"),
                 "expected_state": None, "statement": "源码结构成立，但当前耗时占比尚未测量",
                 "affects": "改变收益估计，不改变地址和容量合法性", "resolution": "test_in_experiment"}
                for h in policy["performance_hypotheses"]]
    opportunity = {"id": "opportunity.transfer", "hypothesis_id": instance["hypothesis_id"], "action_id": instance["action_id"],
        "action_instance_id": instance["instance_id"], "case_ids": ["1"], "source_fact_ids": [source_fact],
        "cost_mechanism": "相同连续逻辑域内减少小搬运发射次数，收益大小仍未知", "predictions": [
            {"id": "fewer_calls", "kind": "source_work", "statement": "合并后每块发射次数下降", "check_method": "比较源码覆盖范围和调用次数",
             "on_support": "确认干预已减少预期源码工作", "on_refute": "修改方案，不能把不相关补丁当搬运合并"},
            {"id": "time", "kind": "performance", "statement": "当发射占比显著时同case Task时间下降", "check_method": "原oracle与统一计时",
             "on_support": "在已测范围保留候选", "on_refute": "检查带宽及其他成本解释，不据此否定全部搬运技术"}],
        "performance_hypotheses": [{"hypothesis_id": h["id"], "state": "unknown", "evidence_fact_ids": [],
            "prediction_id": "time", "unknown_id": "u." + h["id"], "reason": "知识与源码支持提出试验，不伪称已有性能观测"}
            for h in policy["performance_hypotheses"]], "unknowns": unknowns, "strongest_alternative_id": None,
        "comparison": "当前限定连续小搬运片段；未发现值得另立意图的已知机会，不凑候选数量",
        "disposition": "selected", "reason": "改变可数的调用工作并维持原覆盖域，值得验证"}
    action = next(r for r in artifact["records"] if r["id"] == instance["action_id"])
    doc = action["source_path"]
    doc_ref = {"path": doc, "sha256": action["source_hash"]}
    doc_path = knowledge_source(root, doc_ref)
    decision = {"schema_version": "aprof.action-decision/v1", "task_id": reasoning["task_id"],
        "context_hash": reasoning["context_hash"], "knowledge_hash": content_hash(artifact),
        "reasoning_ref": write_json(task / "reasoning.json", reasoning), "reasoning_hash": content_hash(reasoning),
        "condition_policy_ref": policy_ref, "routing_ref": bindings.routing_snapshot_ref(root, bindings.load_routing(root)),
        "round": 1, "current_parent_ref": reasoning["current"]["implementation_ref"], "opportunities": [opportunity],
        "evidence_requests": [], "knowledge_use": [{"opportunity_ids": [opportunity["id"]], "owner": "diagnosis",
            "document_ref": doc_ref, "locator": body_locator(doc_path), "effect_kind": "applicability",
            "before": "把连续域内多次复制当作不可改变的调用形态", "after": "核对边界、容量后允许同owner合并，并保留收益假设",
            "applicability": "本片段连续且没有跨owner修改"}],
        "selection": {"mode": "experiment", "opportunity_id": opportunity["id"], "action_instance_id": instance["instance_id"],
            "reason": "减少调用工作有源码依据，性能未知在试验中回答", "concrete_plan": "P_KEEP；同owner连续片段在容量内合并复制，保留尾块与原oracle", "stop_reason": None},
        "previous_feedback": None}
    return decision, (c1, c2, c3)


def persist_reasoning(decision, chain, task):
    reasoning = chain[0]["reasoning"]
    decision["reasoning_ref"] = write_json(task / "reasoning.json", reasoning)
    decision["reasoning_hash"] = content_hash(reasoning)
    rebind(*chain)


def attach(decision, chain, task):
    chain[0]["artifacts"] = [write_json(task / "decision.json", decision)]
    rebind(*chain)


def safety_unknown(decision, chain, task, key="constraint.capacity", expected=True):
    reasoning = chain[0]["reasoning"]
    if key in reasoning["facts"]:
        reasoning["facts"][key]["state"] = "unknown"
    else:
        reasoning["facts"][key] = {"state": "unknown", "kind": "raw", "evidence_id": None, "ref": None,
            "derived_from": [], "scope": deepcopy(reasoning["current"]["scope"]), "predicate": key}
    for candidate in reasoning["candidates"]:
        candidate["support"] = [k for k in candidate["support"] if fact_state(reasoning, k) != "unknown"]
    instance = reasoning["action_instances"][0]
    if key in instance["evidence_bindings"]:
        instance["unknowns"].append(key)
        instance["status"] = "conditional"
    unknown = {"id": "u.safety", "kind": "implementation_safety", "fact": key, "expected_state": expected,
        "statement": "该缓冲布局容量/合法域尚未完成核验", "affects": "实现可能超出声明的合法范围",
        "resolution": "check_before_implementation"}
    decision["opportunities"][0]["unknowns"].append(unknown)
    decision["evidence_requests"].append({"id": "check.capacity", "opportunity_ids": ["opportunity.transfer"],
        "unknown_ids": [unknown["id"]], "method": "按同时存活buffer、dtype字节数和目标容量计算",
        "discriminating_results": [{"outcome": "总容量与地址范围合法", "decision_effect": "才可实施当前方案"},
                                   {"outcome": "不合法", "decision_effect": "缩小块或回到C2改计划"}],
        "required_before_implementation": True, "status": "pending", "resolution": "not_run", "result_ref": None,
        "finding": "当前仅源码规划，未完成容量核算", "defer_reason": None})
    persist_reasoning(decision, chain, task)


def r2(decision, task):
    previous_ref = write_json(task / "previous-decision.json", decision)
    decision = deepcopy(decision)
    decision["round"] = 2
    decision["selection"]["mode"] = "conditional_plan"
    decision["previous_feedback"] = {"previous_decision_ref": previous_ref, "result_ref": None, "measurement": "not_measured",
        "result_limits": "仅CPU源码审阅，没有R1性能数据", "prediction_updates": [
            {"prediction_id": p["id"], "judgement": "not_tested", "reason": "尚未实施/测量前轮", "evidence_refs": []}
            for p in decision["opportunities"][0]["predictions"]],
        "current_parent_ref": decision["current_parent_ref"], "parent_reason": "继续使用原始源码，不能假设R1已晋升",
        "same_action_reason": "若R1验证调用数下降但时间不降，下一步检查块大小是否改变而非重复相同补丁",
        "new_information": "后继明确按调用工作与耗时两种结果分支，待真实反馈才能决定执行"}
    return decision


def test_source_supported_nonscalar_with_unknown_benefit_is_admissible(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, chain = make_decision(root, artifact, task)
    assert decision["opportunities"][0]["action_id"] == "action.coalesce_contiguous_transfers"
    result = action_decision.validate_decision(root, decision, task_root=task, implementation=True)
    assert result["status"] == "ready"
    assert result["performance_claim"] is False
    attach(decision, chain, task)
    assert bindings.validate_chain(root, *chain, task_root=task)["status"] == "implemented"


def test_d5_chain_requires_decision_but_historical_d4_does_not(package, tmp_path):
    root, artifact = package
    decision, chain = make_decision(root, artifact, tmp_path / "task")
    with pytest.raises(GraphError, match="唯一 action-decision"):
        bindings.validate_chain(root, *chain, task_root=tmp_path / "task")
    assert action_decision.validate_handoff_decision(root, {}, "unused", task_root=tmp_path,
        artifact={"version": "v0004"}, implementation=True) is None


@pytest.mark.parametrize("key", ["constraint.capacity", "constraint.recipe_address_legality"])
def test_unknown_safety_allows_condition_analysis_but_blocks_c3(package, tmp_path, key):
    root, artifact = package
    task = tmp_path / "task"
    decision, chain = make_decision(root, artifact, task)
    safety_unknown(decision, chain, task, key)
    result = action_decision.validate_decision(root, decision, task_root=task)
    assert result["status"] == "conditional"
    with pytest.raises(GraphError, match="实施安全"):
        action_decision.validate_decision(root, decision, task_root=task, implementation=True)


def test_resolved_request_cannot_replace_actual_safety_fact(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, chain = make_decision(root, artifact, task)
    safety_unknown(decision, chain, task)
    decision["evidence_requests"][0].update(status="completed", resolution="resolved", finding="声称算过容量",
        result_ref=write_json(task / "capacity.json", {"task_id": decision["task_id"], "bytes": 4096}))
    with pytest.raises(GraphError, match="实施安全"):
        action_decision.validate_decision(root, decision, task_root=task, implementation=True)


def test_required_false_condition_is_not_reversed(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, chain = make_decision(root, artifact, task)
    safety_unknown(decision, chain, task, "constraint.overlap_alias", expected=False)
    chain[0]["reasoning"]["facts"]["constraint.overlap_alias"].update(state=True, evidence_id="alias",
        ref={**write_json(task / "alias.json", {"task_id": decision["task_id"], "alias": True}), "locator": "alias"})
    decision["evidence_requests"][0].update(status="completed", resolution="resolved", finding="存在不允许别名",
        result_ref={"path": "alias.json", "sha256": file_hash(task / "alias.json")})
    persist_reasoning(decision, chain, task)
    with pytest.raises(GraphError, match="实施安全"):
        action_decision.validate_decision(root, decision, task_root=task, implementation=True)


def test_performance_request_cannot_be_a_safety_gate(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, chain = make_decision(root, artifact, task)
    safety_unknown(decision, chain, task)
    decision["evidence_requests"][0]["unknown_ids"] = [decision["opportunities"][0]["unknowns"][0]["id"]]
    with pytest.raises(GraphError, match="性能证据请求"):
        action_decision.validate_decision(root, decision, task_root=task)


def test_singular_and_multiple_opportunities_are_not_fixed_count_or_action_diversity(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    assert action_decision.validate_decision(root, decision, task_root=task)["opportunity_count"] == 1
    second = deepcopy(decision["opportunities"][0])
    second.update(id="opportunity.other_tile", action_instance_id=None, disposition="deferred", strongest_alternative_id="opportunity.transfer",
        comparison="同一Action不同块大小；容量代价较高，先测较低资源版本")
    for unknown in second["unknowns"]:
        unknown["id"] = "second." + unknown["id"]
    for performance in second["performance_hypotheses"]:
        performance["unknown_id"] = "second." + performance["unknown_id"]
    decision["opportunities"][0]["strongest_alternative_id"] = second["id"]
    decision["opportunities"].append(second)
    assert action_decision.validate_decision(root, decision, task_root=task)["opportunity_count"] == 2


def test_r2_needs_feedback_and_same_action_can_continue_with_new_information(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    decision["round"] = 2
    with pytest.raises(GraphError, match="前轮反馈"):
        action_decision.validate_decision(root, decision, task_root=task)
    decision["round"] = 1
    decision = r2(decision, task)
    assert action_decision.validate_decision(root, decision, task_root=task)["selection_mode"] == "conditional_plan"
    decision["previous_feedback"]["same_action_reason"] = None
    with pytest.raises(GraphError, match="继续同一 Action"):
        action_decision.validate_decision(root, decision, task_root=task)


def test_unmeasured_r2_can_update_source_prediction_but_not_performance(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    decision = r2(decision, task)
    ref = write_json(task / "static-check.json", {"task_id": decision["task_id"], "check": "源代码连续域可合并"})
    update = decision["previous_feedback"]["prediction_updates"][0]
    update.update(judgement="supported", evidence_refs=[ref], reason="新静态分析确认连续覆盖域")
    action_decision.validate_decision(root, decision, task_root=task)
    decision["previous_feedback"]["prediction_updates"][1].update(judgement="supported", evidence_refs=[ref])
    with pytest.raises(GraphError, match="性能预测"):
        action_decision.validate_decision(root, decision, task_root=task)


def test_unmeasured_r2_plan_does_not_implement_but_independent_experiment_is_allowed(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    decision = r2(decision, task)
    with pytest.raises(GraphError, match="只有明确试验选择"):
        action_decision.validate_decision(root, decision, task_root=task, implementation=True)
    decision["selection"]["mode"] = "experiment"
    # 允许依据静态新信息选择试验；没有前轮测量不成为另一道性能门禁。
    assert action_decision.validate_decision(root, decision, task_root=task, implementation=True)["status"] == "ready"


def test_arbitrary_json_cannot_claim_valid_timing_feedback(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    decision = r2(decision, task)
    decision["previous_feedback"].update(measurement="valid", result_ref=write_json(task / "fake-result.json",
        {"task_id": decision["task_id"], "speedup": 2.0}))
    with pytest.raises(GraphError):
        action_decision.validate_decision(root, decision, task_root=task)


def test_invalid_timing_does_not_discard_independent_static_feedback(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    decision = r2(decision, task)
    ref = write_json(task / "static-check.json", {"task_id": decision["task_id"], "calls": "one contiguous call"})
    feedback = decision["previous_feedback"]
    feedback.update(measurement="invalid", result_ref=write_json(task / "measurement-failure.json",
        {"task_id": decision["task_id"], "reason": "capture missing"}))
    feedback["prediction_updates"][0].update(judgement="supported", evidence_refs=[ref])
    action_decision.validate_decision(root, decision, task_root=task)
    feedback["prediction_updates"][1].update(judgement="supported", evidence_refs=[ref])
    with pytest.raises(GraphError, match="无效结果"):
        action_decision.validate_decision(root, decision, task_root=task)


def test_valid_feedback_replays_cpu_capture_and_binds_parent(package, tmp_path):
    from aprof_runtime.unified_timing import finalize_timing
    from test_unified_timing import campaign
    root, artifact = package
    task = tmp_path / "task"
    decision, chain = make_decision(root, artifact, task)
    measurement = task / "measurement"
    measurement.mkdir()
    request_path, _ = campaign(measurement)  # FakeRunner only; no hardware.
    request = json.loads(request_path.read_text())
    capture_path = measurement / request["baseline_captures"][0]["path"]
    capture = json.loads(capture_path.read_text())
    reasoning = chain[0]["reasoning"]
    parent = task / reasoning["current"]["implementation_ref"]["path"]
    shutil.copyfile(capture_path.parent / capture["artifacts"]["source"]["path"], parent)
    reasoning["current"]["implementation_ref"]["sha256"] = file_hash(parent)
    scope = reasoning["current"]["scope"]
    scope["parent_implementation_hash"] = file_hash(parent)
    for row in list(reasoning["facts"].values()) + reasoning["candidates"] + reasoning["action_instances"]:
        row["scope"] = deepcopy(scope)
    context_path = task / reasoning["source_context_ref"]["path"]
    context = json.loads(context_path.read_text())
    context["operator"] = request["operator"]
    reasoning["source_context_ref"] = write_json(context_path, context)
    reasoning["context_snapshot"]["source_context_ref"] = deepcopy(reasoning["source_context_ref"])
    reasoning["context_hash"] = content_hash(reasoning["context_snapshot"])
    decision["context_hash"] = reasoning["context_hash"]
    decision["current_parent_ref"] = deepcopy(reasoning["current"]["implementation_ref"])
    persist_reasoning(decision, chain, task)
    decision = r2(decision, task)
    result_path = measurement / "result.json"
    finalize_timing(request_path, result_path)
    decision["previous_feedback"].update(measurement="valid",
        result_ref={"path": str(result_path.relative_to(task)), "sha256": file_hash(result_path)})
    assert action_decision.validate_decision(root, decision, task_root=task)["status"] == "conditional"
    # 真计时属于另一父本时，不能用作这一次选择的经验。
    previous_path = task / decision["previous_feedback"]["previous_decision_ref"]["path"]
    previous = json.loads(previous_path.read_text())
    previous["current_parent_ref"]["sha256"] = "sha256:" + "0" * 64
    decision["previous_feedback"]["previous_decision_ref"] = write_json(previous_path, previous)
    with pytest.raises(GraphError, match="父实现"):
        action_decision.validate_decision(root, decision, task_root=task)


@pytest.mark.parametrize("bad", ["hash", "task", "instance", "unknown_detail"])
def test_bad_identity_or_unexplained_unknown_is_rejected(package, tmp_path, bad):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    if bad == "hash":
        decision["reasoning_ref"]["sha256"] = "sha256:" + "0" * 64
    elif bad == "task":
        decision["task_id"] = "other-task"
    elif bad == "instance":
        decision["selection"]["action_instance_id"] = "other-instance"
    else:
        decision["opportunities"][0]["unknowns"][0]["affects"] = ""
    with pytest.raises(GraphError):
        action_decision.validate_decision(root, decision, task_root=task)


def test_knowledge_document_must_change_a_specific_decision(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    decision["knowledge_use"][0]["after"] = decision["knowledge_use"][0]["before"]
    with pytest.raises(GraphError, match="具体判断"):
        action_decision.validate_decision(root, decision, task_root=task)


def test_history_uses_frozen_po_bundle_when_active_index_changes(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    config = json.loads((root / bindings.CONFIG).read_text())
    o_index = json.loads((root / config["bases"]["optimization"]["path"]).read_text())
    recipe = next(r for r in o_index["records"] if r["id"] == "implementation.memory-transfer.coalesce")
    decision["knowledge_use"].append({"opportunity_ids": ["opportunity.transfer"], "owner": "optimization",
        "document_ref": {"path": recipe["source_path"], "sha256": recipe["source_hash"]}, "locator": body_locator(root / recipe["source_path"]),
        "effect_kind": "parameters", "before": "每片独立复制", "after": "按连续边界与容量确定合并粒度",
        "applicability": "同一owner内的连续数据搬运"})
    active = root / "skills/ascendc-aprof-optimization/knowledge/index.json"
    previous = active.read_bytes()
    try:
        active.write_text('{"unrelated_new_active_index":true}')
        assert action_decision.validate_decision(root, decision, task_root=task)["status"] == "ready"
    finally:
        active.write_bytes(previous)


def test_frontmatter_is_not_evidence_of_reading_knowledge_body(package, tmp_path):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    decision["knowledge_use"][0]["locator"] = "lines:1"
    with pytest.raises(GraphError, match="frontmatter"):
        action_decision.validate_decision(root, decision, task_root=task)


@pytest.mark.parametrize("record", ["current", "previous"])
def test_performance_prediction_cannot_be_relabeled_static(package, tmp_path, record):
    root, artifact = package
    task = tmp_path / "task"
    decision, _ = make_decision(root, artifact, task)
    if record == "current":
        decision["opportunities"][0]["predictions"][1]["kind"] = "source_work"
    else:
        previous = deepcopy(decision)
        decision = r2(decision, task)
        previous["opportunities"][0]["predictions"][1]["kind"] = "source_work"
        decision["previous_feedback"]["previous_decision_ref"] = write_json(task / "previous-decision.json", previous)
        evidence = write_json(task / "static.json", {"task_id": decision["task_id"], "calls": 1})
        decision["previous_feedback"]["prediction_updates"][1].update(judgement="supported", evidence_refs=[evidence])
    with pytest.raises(GraphError, match="performance 预测"):
        action_decision.validate_decision(root, decision, task_root=task)


def test_future_action_requires_explicit_policy_and_conditions_not_parser_edit(package, tmp_path):
    root, original_graph = package
    future = tmp_path / "future"
    shutil.copytree(root, future)
    graph = deepcopy(original_graph)
    ref, rows = action_decision.condition_policy(future, graph)
    original = next(r for r in graph["records"] if r["kind"] == "action")
    action = deepcopy(original)
    action["id"] = "action.future_intent"
    graph["records"].append(action)
    with pytest.raises(GraphError, match="覆盖注册"):
        action_decision.condition_policy(future, graph)
    row = deepcopy(rows[original["id"]])
    row.update(action_id=action["id"], legacy_preconditions=[], legacy_dispositions=[])
    row["performance_hypotheses"] = [h for h in row["performance_hypotheses"] if h["legacy_condition"] is None]
    row["added_safety_predicates"] = [dict(fact=c["fact"], state=c["state"], definition="沿用原谓词定义、显式登记新意图所需条件",
        reason="本测试只检查扩展无需改解析器", proof_requirements=["新知识仍须来源与语义复核"], unknown_when=["缺当前对象依据"])
        for c in row["safety_conditions"]]
    policy = json.loads((future / ref["path"]).read_text())
    policy["actions"].append(row)
    new_path = "workflows/references/action-condition-policies/v0002.json"
    policy["version"] = "v0002"
    write_json(future / new_path, policy)
    del graph["source_hashes"][ref["path"]]
    graph["source_hashes"][new_path] = file_hash(future / new_path)
    _, updated = action_decision.condition_policy(future, graph)
    assert action["id"] in updated
