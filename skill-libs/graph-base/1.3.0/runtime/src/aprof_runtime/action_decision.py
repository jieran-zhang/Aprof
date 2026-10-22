"""校验试验选择的身份、比较与反馈；不自动打分，也不证明自然语言判断。"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .errors import GraphError
from .jsonio import canonical_json, content_hash, file_hash
from .knowledge import local, validate_schema

POLICY_PREFIX = "workflows/references/action-condition-policies/"


def _same(left, right):
    return canonical_json(left) == canonical_json(right)


def _file(root, ref):
    path = local(Path(root), ref["path"])
    if not path.is_file() or file_hash(path) != ref["sha256"]:
        raise GraphError(f"decision 引用文件缺失或 hash 不匹配: {ref['path']}")
    return path


def _json(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise GraphError(f"decision JSON 不可读取: {path}") from exc


def _task_ref(task_root, ref, task_id):
    path = _file(task_root, ref)
    if path.suffix == ".json":
        value = _json(path)
        if isinstance(value, dict) and "task_id" in value and value["task_id"] != task_id:
            raise GraphError("decision 证据跨 task 引用")
    return path


def requires_decision(artifact):
    version = artifact.get("version", "")
    return bool(re.fullmatch(r"v[0-9]{4}", version) and int(version[1:]) >= 5)


def required_decision_version(artifact):
    if not requires_decision(artifact):
        return None
    return "aprof.action-decision/v2" if int(artifact["version"][1:]) >= 6 else "aprof.action-decision/v1"


def decision_schema(value):
    versions = {"aprof.action-decision/v1": "action-decision", "aprof.action-decision/v2": "action-decision-v2",
                "aprof.action-decision/v3": "action-decision-v3"}
    try:
        return versions[value["schema_version"]]
    except (KeyError, TypeError) as exc:
        raise GraphError("不支持的 action-decision schema_version") from exc


def condition_policy(root, artifact):
    """规则绑定冻结图的源清单，绝不把活跃 policy 回填到历史图。"""
    refs = [{"path": name, "sha256": sha} for name, sha in artifact["source_hashes"].items()
            if name.startswith(POLICY_PREFIX) and name.endswith(".json")]
    if len(refs) != 1:
        raise GraphError("新诊断快照需要唯一冻结 action condition policy")
    ref = refs[0]
    policy = _json(_file(root, ref))
    validate_schema(Path(root), "action-condition-policy", policy)
    legacy_ref = policy["legacy_graph_ref"]
    legacy = _json(_file(root, {"path": legacy_ref["path"], "sha256": legacy_ref["file_sha256"]}))
    if legacy.get("version") != legacy_ref["version"] or content_hash(legacy) != legacy_ref["graph_sha256"]:
        raise GraphError("condition policy 历史图身份不匹配")
    legacy_actions = {r["id"]: r for r in legacy["records"] if r["kind"] == "action"}
    if artifact["version"] < policy["applies_from_graph_version"]:
        raise GraphError("condition policy 不适用于此诊断版本")
    actions = {r["id"]: r for r in artifact["records"] if r["kind"] == "action"}
    rows = {r["action_id"]: r for r in policy["actions"]}
    if len(rows) != len(policy["actions"]) or set(rows) != set(actions):
        raise GraphError("condition policy 必须唯一覆盖注册 Action")
    for identifier, row in rows.items():
        original = legacy_actions.get(identifier)
        expected_legacy = original["preconditions"] if original is not None else []
        if not _same(row["legacy_preconditions"], expected_legacy):
            raise GraphError("condition policy 原前提必须精确保留冻结历史图")
        legacy_conditions = {p["fact"]: p["state"] for p in row["legacy_preconditions"]}
        dispositions = {p["fact"]: p for p in row["legacy_dispositions"]}
        if len(dispositions) != len(row["legacy_dispositions"]) or set(dispositions) != set(legacy_conditions):
            raise GraphError("旧前提必须逐条且唯一登记迁移去向")
        for fact, disposition in dispositions.items():
            if disposition["state"] is not legacy_conditions[fact]:
                raise GraphError("迁移不能改变旧前提要求的 true/false")
            targets = (row["safety_conditions"] if disposition["destination"] == "safety_conditions" else
                       [h["legacy_condition"] for h in row["performance_hypotheses"] if h["legacy_condition"] is not None])
            if sum(p["fact"] == fact and p["state"] is disposition["state"] for p in targets) != 1:
                raise GraphError("旧前提迁移去向与安全/性能投影不一致")
        added = {p["fact"]: p for p in row["added_safety_predicates"]}
        new_conditions = {p["fact"]: p for p in row["safety_conditions"] if p["fact"] not in legacy_conditions}
        if (len(added) != len(row["added_safety_predicates"]) or set(added) != set(new_conditions) or
                any(added[f]["state"] is not new_conditions[f]["state"] for f in added)):
            raise GraphError("新增安全条件必须有精确 added_safety_predicates 定义")
        conditions = [{"fact": p["fact"], "state": p["state"]} for p in row["safety_conditions"]]
        if not _same(conditions, actions[identifier]["preconditions"]):
            raise GraphError("Action preconditions 与冻结实施安全/结构条件不一致")
        hypotheses = row["performance_hypotheses"]
        if len({p["id"] for p in hypotheses}) != len(hypotheses):
            raise GraphError("性能假设 ID 重复")
        performance_facts = {p["legacy_condition"]["fact"] for p in hypotheses if p["legacy_condition"] is not None}
        if performance_facts & {p["fact"] for p in conditions}:
            raise GraphError("性能假设不能同时作为实施安全门禁")
    return ref, rows


def _unique(rows, key, label):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise GraphError(f"{label} ID 重复")
    return result


def _performance_predictions(opportunity):
    predictions = {p["id"]: p for p in opportunity["predictions"]}
    if any(predictions.get(h["prediction_id"], {}).get("kind") != "performance"
           for h in opportunity["performance_hypotheses"]):
        raise GraphError("性能假设必须引用 performance 预测，不能改标 source_work 绕过反馈边界")


def _knowledge_use(root, decision, artifacts, opportunities):
    used = set()
    for use in decision["knowledge_use"]:
        if not set(use["opportunity_ids"]) <= set(opportunities):
            raise GraphError("knowledge_use 引用未知机会")
        owner = use["owner"]
        ref = use["document_ref"]
        if artifacts[owner]["source_hashes"].get(ref["path"]) != ref["sha256"]:
            raise GraphError("知识正文必须属于声明 owner 的精确知识源清单")
        if not any(r.get("source_path") == ref["path"] and r.get("source_hash") == ref["sha256"] for r in artifacts[owner]["records"]):
            raise GraphError("knowledge_use 必须引用注册知识正文，不能用来源清单或 REGION 代替")
        from .knowledge_history import knowledge_source
        path = knowledge_source(root, ref)
        match = re.fullmatch(r"lines:([1-9][0-9]*)(?:-([1-9][0-9]*))?", use["locator"])
        lines = path.read_text().splitlines()
        start, end = int(match[1]), int(match[2] or match[1])
        if not 1 <= start <= end <= len(lines):
            raise GraphError("knowledge_use 正文定位超界")
        header_end = next((i + 1 for i in range(1, len(lines)) if lines[0] == "---" and lines[i] == "---"), 0)
        if end <= header_end or not any(line.strip() for line in lines[max(start - 1, header_end):end]):
            raise GraphError("knowledge_use 必须实际定位正文，不能只读 frontmatter")
        if use["before"].strip() == use["after"].strip():
            raise GraphError("knowledge_use 必须说明知识改变或确认了哪项具体判断")
        used.update(use["opportunity_ids"])
    return used


def _feedback(root, decision, task_root, selected, policies):
    feedback = decision["previous_feedback"]
    if decision["round"] == 1:
        if feedback is not None:
            raise GraphError("首轮不能伪造前轮反馈")
        return
    if feedback is None:
        raise GraphError("R2/后继选择必须读取并评价前轮反馈")
    previous = _json(_task_ref(task_root, feedback["previous_decision_ref"], decision["task_id"]))
    validate_schema(Path(root), decision_schema(previous), previous)
    if previous["schema_version"] != decision["schema_version"]:
        raise GraphError("反馈前后必须使用相同 decision 契约；历史记录不自动升级")
    if (previous["task_id"] != decision["task_id"] or previous["round"] + 1 != decision["round"] or
            previous["knowledge_hash"] != decision["knowledge_hash"] or
            not _same(previous["condition_policy_ref"], decision["condition_policy_ref"])):
        raise GraphError("前轮 decision 的任务、轮次或知识身份不匹配")
    if not _same(feedback["current_parent_ref"], decision["current_parent_ref"]):
        raise GraphError("R2 当前父本与反馈父本不一致")
    old_opportunities = {o["id"]: o for o in previous["opportunities"]}
    for opportunity in old_opportunities.values():
        if previous["schema_version"] == "aprof.action-decision/v2" and opportunity["action_id"] is None:
            if opportunity["performance_hypotheses"] or opportunity["action_instance_id"] is not None:
                raise GraphError("前轮未注册意图不能伪造 Action 实例或性能策略")
            continue
        policy = policies.get(opportunity["action_id"])
        if policy is None or {h["hypothesis_id"] for h in opportunity["performance_hypotheses"]} != {h["id"] for h in policy["performance_hypotheses"]}:
            raise GraphError("前轮记录必须完整保留该 Action 的性能假设")
        _performance_predictions(opportunity)
    previous_selected = old_opportunities.get(previous["selection"]["opportunity_id"])
    expected_predictions = {p["id"] for p in previous_selected["predictions"]} if previous_selected else set()
    updates = _unique(feedback["prediction_updates"], "prediction_id", "反馈预测")
    if set(updates) != expected_predictions:
        raise GraphError("R2 必须逐项评价前轮所选机会的预测")
    measurement = feedback["measurement"]
    prediction_kinds = {p["id"]: p["kind"] for p in previous_selected["predictions"]} if previous_selected else {}
    if measurement == "not_measured":
        if feedback["result_ref"] is not None:
            raise GraphError("无硬件实测不能伪造前轮计时结果")
        for prediction_id, update in updates.items():
            if prediction_kinds[prediction_id] == "performance":
                if update["judgement"] != "not_tested" or update["evidence_refs"]:
                    raise GraphError("无硬件实测不能确认或削弱性能预测")
            else:
                if update["judgement"] in {"supported", "weakened"} and not update["evidence_refs"]:
                    raise GraphError("静态预测更新必须引用真实新增源码/分析依据")
                for ref in update["evidence_refs"]:
                    _task_ref(task_root, ref, decision["task_id"])
    else:
        if feedback["result_ref"] is None:
            raise GraphError("已测反馈必须引用真实结果")
        result_path = _task_ref(task_root, feedback["result_ref"], decision["task_id"])
        result = _json(result_path)
        if measurement == "valid" or result.get("kind") == "unified_timing_result":
            validate_schema(Path(root), "unified-timing-result", result)
            if measurement == "valid" and result.get("verdict") == "inconclusive":
                raise GraphError("inconclusive 计时不能标为有效反馈")
        if measurement == "valid":
            from .unified_timing import verify_timing
            from .errors import ContractError
            try:
                verify_timing(result_path)
                request = _json(Path(result["request"]["path"]))
            except (ContractError, OSError, ValueError) as exc:
                raise GraphError(f"反馈统一计时原始链回放失败: {exc}") from exc
            prior_reasoning = _json(_task_ref(task_root, previous["reasoning_ref"], decision["task_id"]))
            prior_context = _json(_task_ref(task_root, prior_reasoning["source_context_ref"], decision["task_id"]))
            if (result["operator"] != prior_context.get("operator") or
                    request["baseline_source_sha256"] != previous["current_parent_ref"]["sha256"] or
                    decision["current_parent_ref"]["sha256"] not in {request["baseline_source_sha256"], request["candidate_source_sha256"]}):
                raise GraphError("反馈算子/父实现与前轮决策或当前父本不匹配")
        for prediction_id, update in updates.items():
            if update["judgement"] in {"supported", "weakened"} and not update["evidence_refs"]:
                raise GraphError("预测得到支持/削弱必须有对应结果依据")
            if measurement == "invalid" and prediction_kinds[prediction_id] == "performance" and update["judgement"] in {"supported", "weakened"}:
                raise GraphError("无效结果不能确认或削弱性能预测")
            for ref in update["evidence_refs"]:
                _task_ref(task_root, ref, decision["task_id"])
    if selected and previous_selected and selected["action_id"] == previous_selected["action_id"]:
        if not feedback["same_action_reason"] or not feedback["same_action_reason"].strip():
            raise GraphError("继续同一 Action 必须说明前轮之后仍值得检验的新信息")


def validate_decision(root: Path, decision: dict, *, task_root=None, artifact=None,
                      reasoning=None, selected_instance_id=None, implementation=False, artifacts=None, routing_config=None,
                      selected_instance_ids=None, selected_scheme_id=None) -> dict:
    """未知性能允许有依据的试验；未知安全、假引用或缺反馈不能授权实施。"""
    if decision.get("schema_version") == "aprof.action-decision/v3":
        from .action_decision_v3 import validate_decision as validate_scheme_decision
        return validate_scheme_decision(root, decision, task_root=task_root, artifact=artifact,
                                        reasoning=reasoning, selected_instance_id=selected_instance_id,
                                        selected_instance_ids=selected_instance_ids, selected_scheme_id=selected_scheme_id,
                                        implementation=implementation, artifacts=artifacts, routing_config=routing_config)
    if selected_instance_ids is not None or selected_scheme_id is not None:
        raise GraphError("多成员/方案绑定仅属于 action-decision/v3，不能混入旧契约")
    from . import diagnosis
    from .bindings import _reasoning, load_frozen_bundle
    from .diagnosis_reasoning import action_status, fact_state
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    validate_schema(root, decision_schema(decision), decision)
    is_v2 = decision["schema_version"] == "aprof.action-decision/v2"
    frozen_artifacts, frozen_config = load_frozen_bundle(root, decision["routing_ref"])
    if artifacts is not None and not _same(artifacts, frozen_artifacts):
        raise GraphError("decision routing bundle 与交接知识快照不同")
    if routing_config is not None and not _same(routing_config, frozen_config):
        raise GraphError("decision routing config 与交接配置不同")
    if artifact is not None and not _same(artifact, frozen_artifacts["diagnosis"]):
        raise GraphError("decision routing bundle 与诊断快照不同")
    artifacts, artifact = frozen_artifacts, frozen_artifacts["diagnosis"]
    diagnosis.validate_artifact(artifact, root)
    expected_version = required_decision_version(artifact)
    if expected_version is not None and decision["schema_version"] != expected_version:
        raise GraphError(f"{artifact['version']} 要求 {expected_version}，不能用旧比较格式绕过")
    policy_ref, policies = condition_policy(root, artifact)
    if not _same(policy_ref, decision["condition_policy_ref"]):
        raise GraphError("decision condition policy 与精确图快照不一致")
    stored = _json(_task_ref(task_root, decision["reasoning_ref"], decision["task_id"]))
    if reasoning is not None and not _same(reasoning, stored):
        raise GraphError("decision 引用了其他 C1 reasoning")
    reasoning = stored
    _reasoning(root, reasoning, task_root, artifact)
    if (decision["task_id"] != reasoning["task_id"] or decision["context_hash"] != reasoning["context_hash"] or
            decision["knowledge_hash"] != content_hash(artifact) or decision["reasoning_hash"] != content_hash(reasoning) or
            not _same(decision["current_parent_ref"], reasoning["current"]["implementation_ref"])):
        raise GraphError("decision task/context/knowledge/reasoning/parent 身份不匹配")
    nodes = {r["id"]: r for r in artifact["records"]}
    hypotheses = {h["hypothesis_id"]: h for h in reasoning["candidates"]}
    instances = {i["instance_id"]: i for i in reasoning["action_instances"]}
    opportunities = _unique(decision["opportunities"], "id", "机会")
    unknowns, owners = {}, {}
    for opportunity in opportunities.values():
        identifier = opportunity["id"]
        hypothesis = hypotheses.get(opportunity["hypothesis_id"])
        unregistered = is_v2 and opportunity["action_id"] is None
        if hypothesis is None or (not unregistered and opportunity["action_id"] not in policies):
            raise GraphError("机会必须引用当前候选机制与已注册 Action")
        instance_id = opportunity["action_instance_id"]
        if instance_id is not None:
            instance = instances.get(instance_id)
            if instance is None or instance["action_id"] != opportunity["action_id"] or instance["hypothesis_id"] != opportunity["hypothesis_id"]:
                raise GraphError("机会不能串用其他 Action 或机制的实例")
        for fact_id in opportunity["source_fact_ids"]:
            fact = reasoning["facts"].get(fact_id)
            predicate = fact.get("predicate", fact_id) if fact else fact_id
            view = fact.get("view", nodes.get(predicate, {}).get("view")) if fact else None
            if fact is None or fact_state(reasoning, fact_id) == "unknown" or view == "profile" or predicate.startswith("symptom.profile."):
                raise GraphError("机会的源码/适用依据必须是当前已知非 profiling 事实")
        alternative = opportunity["strongest_alternative_id"]
        if alternative is not None and (alternative == identifier or alternative not in opportunities):
            raise GraphError("最强替代必须引用另一个已比较机会")
        if len(opportunities) > 1 and alternative is None:
            raise GraphError("多机会比较必须指出当前最强替代，不强制更换 Action")
        policy = policies[opportunity["action_id"]] if not unregistered else {"safety_conditions": [], "performance_hypotheses": []}
        safety = {c["fact"]: c["state"] for c in policy["safety_conditions"]}
        perf_policy = {h["id"]: h for h in policy["performance_hypotheses"]}
        performance_facts = {h["legacy_condition"]["fact"] for h in perf_policy.values() if h["legacy_condition"] is not None}
        predictions = _unique(opportunity["predictions"], "id", "预测")
        _performance_predictions(opportunity)
        for unknown in opportunity["unknowns"]:
            if unknown["id"] in unknowns:
                raise GraphError("unknown ID 必须在 decision 内唯一")
            unknowns[unknown["id"]], owners[unknown["id"]] = unknown, identifier
            if unknown["kind"] == "implementation_safety":
                if (unknown["fact"] is None or (unknown["fact"] not in safety and not unknown["fact"].startswith("constraint.")) or
                        unknown["fact"] in performance_facts or type(unknown["expected_state"]) is not bool or
                        unknown["resolution"] != "check_before_implementation"):
                    raise GraphError("实施安全 unknown 必须是 Action 条件或 P/O 正文明确的 constraint 合法性条件")
                if unknown["fact"] in safety and unknown["expected_state"] is not safety[unknown["fact"]]:
                    raise GraphError("实施安全 unknown 不能反转 Action 的 true/false 前提")
            elif unknown["resolution"] == "check_before_implementation" or unknown["expected_state"] is not None:
                raise GraphError("纯性能或选择信息 unknown 不能变成实施安全门禁")
        performances = _unique(opportunity["performance_hypotheses"], "hypothesis_id", "性能假设")
        if set(performances) != set(perf_policy):
            raise GraphError("机会必须完整讨论该 Action 的性能假设，不能只列已就绪安全条件")
        for hypothesis_id, performance in performances.items():
            if performance["prediction_id"] not in predictions:
                raise GraphError("性能假设必须关联当前机会的可检验预测")
            for fact_id in performance["evidence_fact_ids"]:
                if fact_id not in reasoning["facts"]:
                    raise GraphError("性能假设引用不存在的事实")
            if performance["state"] == "unknown":
                unknown = unknowns.get(performance["unknown_id"])
                if unknown is None or owners[unknown["id"]] != identifier or unknown["kind"] != "performance":
                    raise GraphError("性能 unknown 必须具体声明缺什么及影响哪项判断")
            else:
                if performance["unknown_id"] is not None or not performance["evidence_fact_ids"]:
                    raise GraphError("已判断性能假设必须有依据，不能继续混用 unknown")
                condition = perf_policy[hypothesis_id]["legacy_condition"]
                if condition is not None:
                    expected = condition["state"] if performance["state"] == "supported" else not condition["state"]
                    if not any(reasoning["facts"][key].get("predicate", key) == condition["fact"] and fact_state(reasoning, key) is expected
                               for key in performance["evidence_fact_ids"]):
                        raise GraphError("性能假设的支持/反驳与原谓词及期望 true/false 不一致")
                elif not any(fact_state(reasoning, key) != "unknown" for key in performance["evidence_fact_ids"]):
                    raise GraphError("unknown 事实不能冒充已支持或已反驳的性能证据")
    requests = _unique(decision["evidence_requests"], "id", "补证据请求")
    requested_safety, unresolved = set(), []
    for request in requests.values():
        if not set(request["opportunity_ids"]) <= set(opportunities) or not set(request["unknown_ids"]) <= set(unknowns):
            raise GraphError("补证据请求引用未知机会或 unknown")
        if any(owners[u] not in request["opportunity_ids"] for u in request["unknown_ids"]):
            raise GraphError("补证据请求串用其他机会的 unknown")
        if request["required_before_implementation"]:
            if any(unknowns[u]["kind"] != "implementation_safety" for u in request["unknown_ids"]):
                raise GraphError("性能证据请求不得成为实施安全硬门禁")
            requested_safety.update(request["unknown_ids"])
        if request["status"] == "completed":
            if request["result_ref"] is None or request["resolution"] == "not_run":
                raise GraphError("已完成补证据必须有真实结果与判别状态")
            _task_ref(task_root, request["result_ref"], decision["task_id"])
        elif request["result_ref"] is not None or request["resolution"] != "not_run":
            raise GraphError("尚未完成的补证据不能声明结果")
        if request["status"] in {"deferred", "unavailable"} and not request["defer_reason"]:
            raise GraphError("延期或不可获取证据必须解释原因及对决策的限制")
        if request["required_before_implementation"] and request["resolution"] != "resolved":
            unresolved.append(request["id"])
    if {u for u, value in unknowns.items() if value["kind"] == "implementation_safety"} - requested_safety:
        raise GraphError("实施安全 unknown 必须有明确补证据请求")
    selection = decision["selection"]
    selected = opportunities.get(selection["opportunity_id"])
    declared_selected = {o["id"] for o in opportunities.values() if o["disposition"] == "selected"}
    if selection["mode"] == "stop":
        if selected is not None or selection["action_instance_id"] is not None or declared_selected or not selection["stop_reason"]:
            raise GraphError("停止必须说明原因，不能伪装已选择动作")
    elif selected is None or declared_selected != {selected["id"]}:
        raise GraphError("决策必须准确对应一个已比较机会")
    if selected is not None and selection["action_instance_id"] != selected["action_instance_id"]:
        raise GraphError("所选机会与 Action 实例不一致")
    if selection["mode"] in {"experiment", "conditional_plan"} and not selection["concrete_plan"]:
        raise GraphError("试验或条件规划必须给出具体方案，不能只列 unknown")
    if selected_instance_id is not None and selection["action_instance_id"] != selected_instance_id:
        raise GraphError("P/O 交接实例与 decision 所选实例不一致")
    used = _knowledge_use(root, decision, artifacts, opportunities)
    if selected is not None and selected["id"] not in used:
        raise GraphError("所选机会必须记录知识正文怎样影响选择、参数或拒绝理由")
    _feedback(root, decision, task_root, selected, policies)
    if is_v2:
        from .action_decision_v2 import validate_analysis
        validate_analysis(root, decision, reasoning, task_root)
    missing, failed = [], []
    if selection["action_instance_id"] is not None:
        status = action_status(root, reasoning, instances[selection["action_instance_id"]], artifact=artifact)
        missing, failed = status["missing"], status["failed"]
    selected_requests = [identifier for identifier in unresolved if selected and selected["id"] in requests[identifier]["opportunity_ids"]]
    if selected is not None:
        selected_safety = {u["fact"]: u for u in selected["unknowns"] if u["kind"] == "implementation_safety"}
        if set(missing) - set(selected_safety):
            raise GraphError("所选 Action 尚缺安全条件必须具体声明 unknown 并补证据")
        for fact_id, unknown in selected_safety.items():
            instance = instances.get(selection["action_instance_id"], {})
            bound = instance.get("evidence_bindings", {}).get(fact_id, fact_id)
            fact = reasoning["facts"].get(bound)
            if fact is None or fact_state(reasoning, bound) == "unknown":
                missing.append(fact_id)
            elif fact.get("predicate", bound) != fact_id or not _same(fact["scope"], hypotheses[selected["hypothesis_id"]]["scope"]):
                raise GraphError("补证据安全事实的 predicate 或完整目标范围不匹配")
            elif fact_state(reasoning, bound) is not unknown["expected_state"]:
                failed.append(fact_id)
    from .action_decision_v2 import missing_workload_mapping
    missing_mapping = missing_workload_mapping(decision, reasoning, task_root, artifact) if is_v2 else []
    if implementation:
        if missing_mapping:
            raise GraphError("C3 缺少测前冻结的完整 workload case payload 映射；须在首次选择前绑定完整 workload_ref，不能事后补填冒称准入")
        if selection["mode"] != "experiment" or selected is None or selection["action_instance_id"] is None:
            raise GraphError("只有明确试验选择可进入 C3 implemented；条件规划/补证据/停止不能实施")
        if missing or failed or selected_requests:
            raise GraphError("C3 实施安全/结构条件或必需补证据未满足: " + ", ".join(missing + failed + selected_requests))
    return {"schema_version": "aprof.action-decision-validation/v2" if is_v2 else "aprof.action-decision-validation/v1", "task_id": decision["task_id"],
            "decision_hash": content_hash(decision), "selection_mode": selection["mode"],
            "opportunity_count": len(opportunities), "status": "conditional" if missing_mapping or missing or failed or selected_requests or selection["mode"] in {"conditional_plan", "collect_evidence"} else "ready",
            "missing_safety": sorted(missing), "failed_safety": sorted(failed), "pending_required_evidence": sorted(selected_requests),
            **({"missing_workload_mapping": missing_mapping} if artifact["version"] >= "v0007" else {}),
            "performance_claim": False, "semantic_review_required": True}


def validate_handoff_decision(root, c1, instance_id, *, task_root, artifact, implementation, artifacts=None, routing_config=None):
    """新图使用 sidecar；旧 handoff schema、历史 D4 链及 frozen 来源保持原义。"""
    if c1.get("schema_version") == "aprof.handoff/v4":
        from .action_decision_v3 import selected_scheme, validate_decision as validate_scheme_decision
        decision = _json(_file(task_root, c1["decision_ref"]))
        if decision.get("schema_version") != "aprof.action-decision/v3":
            raise GraphError("handoff/v4 仅接受显式 action-decision/v3，不能混装旧比较格式")
        for ref in c1["artifacts"]:
            path = _file(task_root, ref)
            if path.suffix == ".json":
                value = _json(path)
                if isinstance(value, dict) and str(value.get("schema_version", "")).startswith("aprof.action-decision/") and not _same(value, decision):
                    raise GraphError("handoff/v4 不能混装其他版本或不同方案的 decision")
        scheme = selected_scheme(decision)
        if (scheme is None or not c1.get("scheme_id") or c1["scheme_id"] != scheme["id"]
                or c1.get("scheme_hash") != content_hash(scheme)):
            raise GraphError("handoff/v4 必须提供非空 scheme_id 及匹配精确 decision 的 scheme hash")
        identifiers = [instance_id] if isinstance(instance_id, str) else list(instance_id)
        return validate_scheme_decision(root, decision, task_root=task_root, artifact=artifact,
                                        reasoning=c1["reasoning"], selected_instance_ids=identifiers,
                                        selected_scheme_id=c1["scheme_id"], implementation=implementation,
                                        artifacts=artifacts, routing_config=routing_config)
    if not requires_decision(artifact):
        return None
    decisions = []
    for ref in c1["artifacts"]:
        path = _file(task_root, ref)
        if path.suffix == ".json":
            value = _json(path)
            if isinstance(value, dict) and value.get("schema_version") in {"aprof.action-decision/v1", "aprof.action-decision/v2", "aprof.action-decision/v3"}:
                decisions.append(value)
    if len(decisions) != 1:
        raise GraphError(f"{artifact['version']} C1.artifacts 必须引用唯一 action-decision（{required_decision_version(artifact)}）")
    if decisions[0]["schema_version"] != required_decision_version(artifact):
        raise GraphError(f"旧 handoff/v3 链要求 {required_decision_version(artifact)}，不能静默采用新方案契约")
    return validate_decision(root, decisions[0], task_root=task_root, artifact=artifact,
                             reasoning=c1["reasoning"], selected_instance_id=instance_id,
                             implementation=implementation, artifacts=artifacts, routing_config=routing_config)
