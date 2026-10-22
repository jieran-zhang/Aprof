"""完整方案的比较与后继反馈；不把计划保证当作已发生事实。"""
from __future__ import annotations

import math
from pathlib import Path

from .errors import GraphError
from .jsonio import content_hash
from .knowledge import validate_schema
from .action_decision import (
    _same, _task_ref, _json, _unique, _knowledge_use,
    _performance_predictions, condition_policy,
)
from .action_decision_v2 import workload_case_ids, workload_case_payloads, missing_workload_mapping

VERSION = "aprof.action-decision/v3"


def selected_scheme(decision):
    """返回选中的原始方案；不投影或伪造旧版单机会决策。"""
    identifier = decision["selection"]["scheme_id"]
    return next((s for s in decision["schemes"] if s["id"] == identifier), None)


def _members(scheme):
    return {m["action_instance_id"]: m for m in scheme["members"]}


def validate_decision(root, decision, *, task_root=None, artifact=None, reasoning=None,
                      selected_instance_id=None, selected_instance_ids=None,
                      selected_scheme_id=None, implementation=False,
                      artifacts=None, routing_config=None):
    """C1 允许条件分析；C3 的变换后保证由 handoff/v4 绑定实际源码核实。"""
    from . import diagnosis
    from .bindings import _reasoning, load_frozen_bundle
    root = Path(root)
    task_root = Path(task_root) if task_root is not None else root
    validate_schema(root, "action-decision-v3", decision)
    frozen_artifacts, frozen_config = load_frozen_bundle(root, decision["routing_ref"])
    if artifacts is not None and not _same(artifacts, frozen_artifacts):
        raise GraphError("decision routing bundle 与交接知识快照不同")
    if routing_config is not None and not _same(routing_config, frozen_config):
        raise GraphError("decision routing config 与交接配置不同")
    if artifact is not None and not _same(artifact, frozen_artifacts["diagnosis"]):
        raise GraphError("decision routing bundle 与诊断快照不同")
    artifacts, artifact = frozen_artifacts, frozen_artifacts["diagnosis"]
    diagnosis.validate_artifact(artifact, root)
    if artifact["version"] < "v0006":
        raise GraphError("方案决策 v3 需要 D v0006 或其显式后继；历史快照不自动升级")
    policy_ref, policies = condition_policy(root, artifact)
    if not _same(policy_ref, decision["condition_policy_ref"]):
        raise GraphError("decision condition policy 与精确图快照不一致")
    stored = _json(_task_ref(task_root, decision["reasoning_ref"], decision["task_id"]))
    if reasoning is not None and not _same(reasoning, stored):
        raise GraphError("decision 引用了其他 C1 reasoning")
    reasoning = stored
    _reasoning(root, reasoning, task_root, artifact)
    if (decision["task_id"] != reasoning["task_id"] or
            decision["context_hash"] != reasoning["context_hash"] or
            decision["knowledge_hash"] != content_hash(artifact) or
            decision["reasoning_hash"] != content_hash(reasoning) or
            not _same(decision["current_parent_ref"], reasoning["current"]["implementation_ref"])):
        raise GraphError("decision task/context/knowledge/reasoning/parent 身份不匹配")
    opportunities, requests = _validate_opportunities(decision, reasoning, artifact, policies, task_root)
    analysis = _validate_analysis(decision, reasoning, task_root)
    missing_mapping = missing_workload_mapping(decision, reasoning, task_root, artifact)
    scheme, readiness = _validate_schemes(root, decision, reasoning, artifact, opportunities, requests, analysis)
    used = _knowledge_use(root, decision, artifacts, opportunities)
    if scheme and {m["opportunity_id"] for m in scheme["members"]} - used:
        raise GraphError("每个方案成员必须记录知识正文如何影响选择、参数或拒绝理由")
    member_ids = [m["action_instance_id"] for m in scheme["members"]] if scheme else []
    if selected_instance_id is not None:
        if selected_instance_ids is not None:
            raise GraphError("不能混装单实例与多实例交接参数")
        selected_instance_ids = [selected_instance_id]
    if selected_instance_ids is not None and (len(set(selected_instance_ids)) != len(selected_instance_ids) or
                                              set(selected_instance_ids) != set(member_ids)):
        raise GraphError("P/O 交接成员必须精确对应所选方案，不能遗漏或借用其他实例")
    if selected_scheme_id is not None and (scheme is None or selected_scheme_id != scheme["id"]):
        raise GraphError("P/O 交接 scheme_id 与 decision 不同")
    _validate_feedback(root, decision, reasoning, policies, task_root)
    missing = sorted({f for r in readiness for f in r["missing_safety"]})
    failed = sorted({f for r in readiness for f in r["failed_safety"]})
    pending = sorted({f for r in readiness for f in r["pending_required_evidence"]})
    if implementation:
        if missing_mapping:
            raise GraphError("C3 缺少测前冻结的完整 workload case payload 映射；须在首次选择前绑定完整 workload_ref，不能事后补填冒称准入")
        if decision["selection"]["mode"] != "experiment" or scheme is None:
            raise GraphError("只有明确试验方案可进入 C3；条件规划/补证据/停止不能实施")
        if missing or failed or pending:
            raise GraphError("C3 每个成员的实施安全/结构条件均须满足；计划保证不是实际事实: " +
                             ", ".join(missing + failed + pending))
    conditional = missing_mapping or missing or failed or pending or decision["selection"]["mode"] in {"conditional_plan", "collect_evidence"}
    return {"schema_version": "aprof.action-decision-validation/v3", "task_id": decision["task_id"],
            "decision_hash": content_hash(decision), "selection_mode": decision["selection"]["mode"],
            "scheme_id": scheme["id"] if scheme else None,
            "scheme_hash": content_hash(scheme) if scheme else None,
            "member_instance_ids": member_ids, "member_readiness": readiness,
            "opportunity_count": len(opportunities), "scheme_count": len(decision["schemes"]),
            "status": "conditional" if conditional else "ready",
            "missing_safety": missing, "failed_safety": failed, "pending_required_evidence": pending,
            **({"missing_workload_mapping": missing_mapping} if artifact["version"] >= "v0007" else {}),
            "performance_claim": False, "semantic_review_required": True}


def _validate_opportunities(decision, reasoning, artifact, policies, task_root):
    from .diagnosis_reasoning import fact_state
    nodes = {r["id"]: r for r in artifact["records"]}
    hypotheses = {h["hypothesis_id"]: h for h in reasoning["candidates"]}
    instances = {i["instance_id"]: i for i in reasoning["action_instances"]}
    opportunities = _unique(decision["opportunities"], "id", "机会")
    unknowns, owners = {}, {}
    for opportunity in opportunities.values():
        identifier = opportunity["id"]
        hypothesis = hypotheses.get(opportunity["hypothesis_id"])
        unregistered = opportunity["action_id"] is None
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
            if not _same(fact['scope'], hypothesis['scope']):
                raise GraphError('机会源码依据不能跨目标实例借用')
        alternative = opportunity["strongest_alternative_id"]
        if alternative is not None and (alternative == identifier or alternative not in opportunities):
            raise GraphError("最强替代必须引用另一个已比较机会")
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
                if not _same(reasoning['facts'][fact_id]['scope'], hypothesis['scope']):
                    raise GraphError('成员性能依据不能跨目标借用；跨目标联合效应应在方案层保留假设')
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
    return opportunities, requests


def _validate_analysis(decision, reasoning, task_root):
    from .action_decision import _same, _task_ref, _json, _unique
    from .diagnosis_reasoning import fact_state, validate_scope
    overview = decision['path_overview']
    if not _same(overview['workload_ref'], reasoning['current']['workload_ref']):
        raise GraphError('path_overview 必须绑定当前完整 workload 身份')
    workload = _json(_task_ref(task_root, overview['workload_ref'], decision['task_id']))
    cases = workload_case_ids(workload)
    if set(overview['case_ids']) != cases:
        raise GraphError('路径概览必须穷尽真实 workload case 清单')
    scope = reasoning['current']['scope']

    def facts(keys, expected_scope=None):
        for key in keys:
            fact = reasoning['facts'].get(key)
            if fact is None or fact_state(reasoning, key) == 'unknown':
                raise GraphError('分析事实必须已知并绑定当前实现/workload/目标完整范围')
            validate_scope(fact['scope'], scope)
            if expected_scope is not None and not _same(fact['scope'], expected_scope):
                raise GraphError('成员分析不能借用其他目标实例的事实')

    def quantity(q, expected_scope=None):
        facts(q['fact_ids'], expected_scope)
        if q['mode'] == 'exact':
            if 'value' not in q or not math.isfinite(q['value']) or 'bounds' in q:
                raise GraphError('精确数量必须提供有限 value，不能只填定性文字')
        elif q['mode'] == 'range':
            b = q.get('bounds', {})
            if not b or not all(math.isfinite(v) for v in b.values()) or b['lower'] > b['upper'] or 'value' in q:
                raise GraphError('范围数量须有有序有限 bounds，不能伪装精确值')
        elif 'value' in q or 'bounds' in q:
            raise GraphError('符号/定性数量不能同时伪装成已确认数值')
        _unique(q['symbols'], 'name', '数量符号')
        if q['mode'] == 'symbolic' and not q['symbols']:
            raise GraphError('符号公式必须解释符号与单位')
        if q['basis'] == 'measured':
            if not any(reasoning['facts'][k].get('view') == 'profile' or
                       reasoning['facts'][k].get('predicate', k).startswith('symptom.profile.')
                       for k in q['fact_ids']):
                raise GraphError('实测数量必须有 profiling 事实，源码逻辑量不能冒充实测量')

    domains = _unique(overview['domains'], 'id', 'workload 域')
    seen = set()
    for domain in domains.values():
        members = set(domain['case_ids'])
        if seen & members or not members <= cases:
            raise GraphError('workload 分区重叠或引用范围外 case')
        seen |= members
        facts(domain['fact_ids'])
    if seen != cases:
        raise GraphError('workload 分区遗漏当前 case')
    stages = _unique(overview['stages'], 'id', '阶段')
    for stage in stages.values():
        if not set(stage['domain_ids']) <= set(domains):
            raise GraphError('阶段引用未知域')
        facts(stage['fact_ids'])
    if set().union(*(set(s['domain_ids']) for s in stages.values())) != set(domains):
        raise GraphError('路径阶段必须覆盖全部 workload 域')

    def work(rows, baseline=False, expected_scope=None):
        _unique(rows, 'id', '工作量')
        for row in rows:
            stage = stages.get(row['stage_id'])
            if stage is None or not set(row['domain_ids']) <= set(stage['domain_ids']):
                raise GraphError('工作量引用未知阶段或阶段之外的域')
            if (row['change'] == 'baseline') != baseline:
                raise GraphError('基线工作与拟变化必须分别标记')
            quantity(row['quantity'], expected_scope)

    work(overview['baseline_work'], baseline=True)
    if {w['stage_id'] for w in overview['baseline_work']} != set(stages):
        raise GraphError('所有路径阶段都必须说明基线工作')
    opportunities = {o['id']: o for o in decision['opportunities']}
    hypotheses = {h['hypothesis_id']: h for h in reasoning['candidates']}
    items = {}
    for op in opportunities.values():
        a = op['analysis']
        analysis_scope = hypotheses[op['hypothesis_id']]['scope']
        if op['action_id'] is None:
            if not a['intent_gap'] or op['action_instance_id'] is not None or op['performance_hypotheses']:
                raise GraphError('未注册意图需说明缺口，不能伪造实例或注册性能假设')
        elif a['intent_gap'] is not None:
            raise GraphError('注册 Action 的语义不足不能用 intent_gap 掩盖')
        if op['strongest_alternative_id'] is None and not a['no_alternative_reason']:
            raise GraphError('无合理替代时须说明完整路径审查后的理由，不凑数量')
        work(a['work_delta'], expected_scope=analysis_scope)
        coverage = _unique(a['coverage'], 'domain_id', '机会覆盖域')
        if set(coverage) != set(domains):
            raise GraphError('每个机会必须分别交代全部域：受影响/部分/未变/不适用/未知')
        affected = set()
        for row in coverage.values():
            facts(row['fact_ids'], analysis_scope)
            if row['status'] in {'affected', 'partial', 'unknown'}:
                affected.update(domains[row['domain_id']]['case_ids'])
        if set(op['case_ids']) != affected:
            raise GraphError('机会 case_ids 必须准确对应受影响/部分/未知域，不能冒充全域覆盖')
        for row in a['work_delta']:
            if row['change'] != 'retained' and any(coverage[d]['status'] not in {'affected', 'partial', 'unknown'} for d in row['domain_ids']):
                raise GraphError('新增/减少工作不能落入声明未变或不适用的域')
        for row in a['tradeoffs'] + a['residuals']:
            if not set(row['domain_ids']) <= set(domains):
                raise GraphError('代价/残余引用未知域')
            if 'change' in row:
                quantity(row['change'], analysis_scope)
            else:
                facts(row['fact_ids'], analysis_scope)
        remaining = {d for d, c in coverage.items() if c['status'] != 'affected'}
        if not remaining <= {d for r in a['residuals'] for d in r['domain_ids']}:
            raise GraphError('未变/部分/不适用/未知域必须保留残余工作及下一步')
        rows = a['work_delta'] + a['coverage'] + a['tradeoffs'] + a['residuals']
        items[op['id']] = _unique(rows, 'id', '机会分析项')
    return {'domains': domains, 'stages': stages, 'items': items, 'facts': facts, 'quantity': quantity, 'work': work}


def _validate_schemes(root, decision, reasoning, artifact, opportunities, requests, context):
    from .diagnosis_reasoning import action_status, fact_state
    schemes = _unique(decision['schemes'], 'id', '方案')
    instances = {i['instance_id']: i for i in reasoning['action_instances']}
    domains = context['domains']
    facts, quantity, work = context['facts'], context['quantity'], context['work']
    analyses, guarantees = {}, {}
    for scheme in schemes.values():
        members = _unique(scheme['members'], 'action_instance_id', '方案成员')
        member_opportunities = _unique(scheme['members'], 'opportunity_id', '方案成员机会')
        for identifier, member in members.items():
            op = opportunities.get(member['opportunity_id'])
            if (op is None or op['action_id'] is None or op['action_instance_id'] != identifier
                    or identifier not in instances):
                raise GraphError('方案成员必须精确绑定已注册机会及其独立 Action 实例')
        alt = scheme['strongest_alternative_id']
        if alt is not None and (alt == scheme['id'] or alt not in schemes):
            raise GraphError('方案最强替代必须引用另一个真实方案')
        if alt is None and not scheme['no_alternative_reason']:
            raise GraphError('没有独立替代方案时说明审查理由，不按数量凑方案')
        _unique(scheme['predictions'], 'id', '方案预测')
        if not any(p['kind'] == 'performance' for p in scheme['predictions']):
            raise GraphError('方案须提出整体性能假设，允许未知；源码工作减少不能代替性能预测')
        steps = _unique(scheme['steps'], 'id', '方案步骤')
        if set().union(*(set(s['action_instance_ids']) for s in steps.values())) != set(members):
            raise GraphError('方案步骤必须覆盖且仅覆盖自己的成员实例')
        ancestors = {}
        def visit(identifier, active):
            if identifier in active:
                raise GraphError('方案步骤依赖存在循环')
            if identifier in ancestors:
                return ancestors[identifier]
            if identifier not in steps:
                raise GraphError('方案步骤依赖未知步骤')
            direct = set(steps[identifier]['depends_on'])
            result = set(direct)
            for dep in direct:
                result.update(visit(dep, active | {identifier}))
            ancestors[identifier] = result
            return result
        for identifier in steps:
            visit(identifier, set())
        planned = {}
        for step in steps.values():
            for guarantee in step['guarantees']:
                if guarantee['id'] in planned:
                    raise GraphError('方案保证 ID 必须唯一')
                if not set(guarantee['target_instance_ids']) <= set(members):
                    raise GraphError('计划保证不能供其他方案或目标实例借用')
                for target in guarantee['target_instance_ids']:
                    consuming = [s for s in steps.values() if target in s['action_instance_ids'] and s['id'] != step['id']]
                    if not consuming or any(step['id'] not in ancestors[s['id']] for s in consuming):
                        raise GraphError('前置保证必须由依赖中的先行步骤产生，不能自证或越过步骤')
                    op = opportunities[members[target]['opportunity_id']]
                    action = next(a for a in artifact['records'] if a['id'] == op['action_id'])
                    expected = {p['fact']: p['state'] for p in action['preconditions']}
                    expected.update({u['fact']: u['expected_state'] for u in op['unknowns'] if u['kind'] == 'implementation_safety'})
                    if expected.get(guarantee['predicate']) is not guarantee['expected_state']:
                        raise GraphError('计划保证必须精确对应目标成员的实施条件，不能翻转 true/false')
                planned[guarantee['id']] = dict(guarantee, producer_step_id=step['id'])
        guarantees[scheme['id']] = planned
        a = scheme['analysis']
        work(a['work_delta'])
        coverage = _unique(a['coverage'], 'domain_id', '方案覆盖域')
        if set(coverage) != set(domains):
            raise GraphError('完整方案须交代全部 workload 域的覆盖及残余')
        for row in coverage.values():
            facts(row['fact_ids'])
            member_status = [next(c['status'] for c in opportunities[m['opportunity_id']]['analysis']['coverage']
                                  if c['domain_id'] == row['domain_id']) for m in members.values()]
            if row['status'] in {'affected', 'partial'} and not any(s in {'affected', 'partial'} for s in member_status):
                raise GraphError('方案不能把成员未影响的域宣称为覆盖')
        for row in a['work_delta']:
            if row['change'] != 'retained' and any(coverage[d]['status'] not in {'affected', 'partial', 'unknown'} for d in row['domain_ids']):
                raise GraphError('联合工作变化不能落入未变或不适用的域')
        for row in a['tradeoffs'] + a['residuals']:
            if not set(row['domain_ids']) <= set(domains):
                raise GraphError('方案代价/残余引用未知域')
            quantity(row['change']) if 'change' in row else facts(row['fact_ids'])
        remaining = {d for d, c in coverage.items() if c['status'] != 'affected'}
        if not remaining <= {d for r in a['residuals'] for d in r['domain_ids']}:
            raise GraphError('完整方案须保留未变/部分/未知域的残余工作')
        _validate_accounting(scheme, opportunities)
        _validate_resources(scheme, context, steps, set(members))
        analyses[scheme['id']] = _unique(a['work_delta'] + a['coverage'] + a['tradeoffs'] + a['residuals'] + a['resource_lifetimes'], 'id', '方案分析项')
    selection = decision['selection']
    selected = schemes.get(selection['scheme_id'])
    declared = {o['id'] for o in opportunities.values() if o['disposition'] == 'selected'}
    if selection['mode'] == 'stop':
        if selected is not None or selection['scheme_id'] is not None or declared or not selection['stop_reason']:
            raise GraphError('停止须说明外部范围或任务理由，不能伪装选中方案')
    elif selected is None:
        if selection['mode'] != 'collect_evidence' or selection['scheme_id'] is not None or declared:
            raise GraphError('决策必须对应一个实际比较过的完整方案')
    else:
        expected = {m['opportunity_id'] for m in selected['members']}
        if declared != expected:
            raise GraphError('所选机会集合必须精确等于所选方案成员，不能遗漏配套变换')
    if selection['mode'] in {'experiment', 'conditional_plan'} and not selection['concrete_plan']:
        raise GraphError('完整试验或条件规划须说明可实施方案，不能只列 unknown')
    roles = set()
    for basis in selection['comparison_basis']:
        sid = basis['scheme_id']
        if sid not in analyses or not set(basis['item_ids']) <= set(analyses[sid]):
            raise GraphError('方案选择依据必须引用实际联合工作/覆盖/代价项')
        if selected:
            if sid not in {selected['id'], selected['strongest_alternative_id']}:
                raise GraphError('方案比较依据引用无关替代')
            if (basis['role'] == 'alternative') != (sid != selected['id']):
                raise GraphError('方案与替代比较角色不一致')
        a = schemes[sid]['analysis']
        role = basis['role']
        if role != 'alternative':
            key = {'benefit': 'work_delta', 'cost': 'tradeoffs', 'coverage': 'coverage', 'residual': 'residuals'}[role]
            allowed = {r['id'] for r in a[key] if role != 'benefit' or r['change'] in {'reduced', 'rescheduled'}}
            if role == 'cost':
                allowed.update(r['id'] for r in a['resource_lifetimes'])
            if not set(basis['item_ids']) <= allowed:
                raise GraphError('方案选择角色须对应实际工作/覆盖/代价/残余项')
        roles.add(role)
    if selected:
        if not {'benefit', 'cost', 'coverage'} <= roles:
            raise GraphError('完整方案选择必须共同解释工作量、覆盖和代价')
        if selected['strongest_alternative_id'] is not None and 'alternative' not in roles:
            raise GraphError('最强替代方案不能从实际选择中消失')
        if selected['analysis']['residuals'] and 'residual' not in roles:
            raise GraphError('方案残余工作必须影响后继选择')
        if not any(c['status'] in {'affected', 'partial', 'unknown'} for c in selected['analysis']['coverage']):
            raise GraphError('完整未变/不适用方案不能进入 P/O')
        if selection['mode'] == 'experiment' and any(r['assessment'] == 'exceeds' for r in selected['analysis']['resource_lifetimes']):
            raise GraphError('已知联合生命周期容量超限，须修改方案或返回 C2 条件规划，不能授权试验')
    readiness = []
    if selected:
        hypotheses = {c['hypothesis_id']: c for c in reasoning['candidates']}
        for member in selected['members']:
            op = opportunities[member['opportunity_id']]
            instance = instances[member['action_instance_id']]
            status = action_status(root, reasoning, instance, artifact=artifact)
            missing, failed = set(status['missing']), set(status['failed'])
            unknowns = {u['fact']: u for u in op['unknowns'] if u['kind'] == 'implementation_safety'}
            if missing - set(unknowns):
                raise GraphError('每个成员缺失的安全条件均须具体声明 unknown 并补证据')
            for predicate, unknown in unknowns.items():
                bound = instance.get('evidence_bindings', {}).get(predicate, predicate)
                fact = reasoning['facts'].get(bound)
                if fact is None or fact_state(reasoning, bound) == 'unknown':
                    missing.add(predicate)
                elif fact.get('predicate', bound) != predicate or not _same(fact['scope'], hypotheses[op['hypothesis_id']]['scope']):
                    raise GraphError('成员安全事实的 predicate 或目标范围不匹配')
                elif fact_state(reasoning, bound) is not unknown['expected_state']:
                    failed.add(predicate)
            pending = []
            for request in requests.values():
                if (op['id'] in request['opportunity_ids'] and request['required_before_implementation']
                        and request['resolution'] != 'resolved'):
                    pending.extend(u['fact'] for u in op['unknowns'] if u['id'] in request['unknown_ids'])
            planned = [g for g in guarantees[selected['id']].values() if instance['instance_id'] in g['target_instance_ids']]
            readiness.append({'instance_id': instance['instance_id'], 'opportunity_id': op['id'],
                              'missing_safety': sorted(missing), 'failed_safety': sorted(failed),
                              'pending_required_evidence': sorted(set(pending)), 'planned_guarantees': planned})
    return selected, readiness


def _validate_accounting(scheme, opportunities):
    a = scheme['analysis']
    joint = {r['id']: r for r in a['work_delta']}
    source = {(m['opportunity_id'], row['id']): row for m in scheme['members']
              for row in opportunities[m['opportunity_id']]['analysis']['work_delta']}
    rows = _unique(a['work_accounting'], 'joint_work_id', '联合工作核算')
    if set(rows) != set(joint):
        raise GraphError('每项联合工作须有一次显式核算，不能省略共享工作')
    seen = set()
    for identifier, accounting in rows.items():
        keys = {(r['opportunity_id'], r['item_id']) for r in accounting['member_work_refs']}
        if len(keys) != len(accounting['member_work_refs']) or not keys <= set(source) or seen & keys:
            raise GraphError('成员工作必须且仅能核算一次，共享工作不能重复计收益')
        seen.update(keys)
        target = joint[identifier]
        sources = [source[k] for k in keys]
        if any(r['change'] != target['change'] or r['stage_id'] != target['stage_id'] or
               set(r['domain_ids']) != set(target['domain_ids']) or
               r['quantity']['unit'] != target['quantity']['unit'] for r in sources):
            raise GraphError('联合工作只能核算相同阶段、范围、变化类型及单位的成员工作')
        if accounting['accounting'] == 'shared_once':
            # 同一工作可有各自目标范围的来源；比较数量语义，不要求事实ID相同。
            def meaning(q):
                return {k: v for k, v in q.items() if k != 'fact_ids'}
            if len(sources) < 2 or any(not _same(meaning(r['quantity']), meaning(target['quantity'])) for r in sources):
                raise GraphError('shared_once 须将相同共享工作按一次核算，不能简单累加')
        elif all(r['quantity']['mode'] == 'exact' for r in sources) and target['quantity']['mode'] == 'exact':
            if not math.isclose(sum(r['quantity']['value'] for r in sources), target['quantity']['value'], rel_tol=1e-12, abs_tol=1e-12):
                raise GraphError('独立精确工作量的联合值须等于成员之和')
    if seen != set(source):
        raise GraphError('完整方案不能遗漏成员新增、保留或减少的工作')


def _validate_resources(scheme, context, steps, members):
    """按共同存活步骤核算峰值；静态分析不声称已证明实际硬件资源。"""
    for resource in scheme['analysis']['resource_lifetimes']:
        if not set(resource['domain_ids']) <= set(context['domains']):
            raise GraphError('生命周期资源引用未知 workload 域')
        allocations = _unique(resource['allocations'], 'id', '资源分配')
        quantities = [resource['capacity'], resource['peak']] + [a['quantity'] for a in allocations.values()]
        for q in quantities:
            context['quantity'](q)
        if len({q['unit'] for q in quantities}) != 1:
            raise GraphError('容量、分配和生命周期峰值必须采用同一单位')
        for allocation in allocations.values():
            if not set(allocation['member_instance_ids']) <= members or not set(allocation['live_step_ids']) <= set(steps):
                raise GraphError('资源分配只能绑定本方案成员及实际存活步骤')
        if not set(resource['peak_step_ids']) <= set(steps):
            raise GraphError('资源峰值引用未知步骤')
        if all(q['mode'] == 'exact' for q in quantities):
            if any(q['value'] < 0 for q in quantities):
                raise GraphError('资源容量及分配不能为负')
            totals = {s: sum(a['quantity']['value'] for a in allocations.values() if s in a['live_step_ids']) for s in steps}
            peak = max(totals.values())
            peaks = {s for s, n in totals.items() if math.isclose(n, peak, rel_tol=1e-12, abs_tol=1e-12)}
            if not math.isclose(resource['peak']['value'], peak, rel_tol=1e-12, abs_tol=1e-12) or set(resource['peak_step_ids']) != peaks:
                raise GraphError('资源峰值须对应共同生命周期，不能相加所有变量或漏算重叠')
            expected = 'fits' if peak <= resource['capacity']['value'] else 'exceeds'
            if resource['assessment'] != expected:
                raise GraphError('生命周期容量判断与精确工作核算矛盾')


def _validate_feedback(root, decision, reasoning, policies, task_root):
    from .action_decision import decision_schema
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
    prior_pair = {previous['current_parent_ref']['sha256']}
    attempted = feedback['reassessment']['attempt']['implementation_ref']
    if attempted is not None:
        prior_pair.add(attempted['sha256'])
    if feedback.get('parent_history_ref') is not None or decision['current_parent_ref']['sha256'] not in prior_pair:
        _validate_parent_history(root, decision, feedback, task_root)
    old_opportunities = {o["id"]: o for o in previous["opportunities"]}
    for opportunity in old_opportunities.values():
        if opportunity["action_id"] is None:
            if opportunity["performance_hypotheses"] or opportunity["action_instance_id"] is not None:
                raise GraphError("前轮未注册意图不能伪造 Action 实例或性能策略")
            continue
        policy = policies.get(opportunity["action_id"])
        if policy is None or {h["hypothesis_id"] for h in opportunity["performance_hypotheses"]} != {h["id"] for h in policy["performance_hypotheses"]}:
            raise GraphError("前轮记录必须完整保留该 Action 的性能假设")
        _performance_predictions(opportunity)
    previous_selected = selected_scheme(previous)
    expected_predictions = {p["id"] for p in previous_selected["predictions"]} if previous_selected else set()
    updates = _unique(feedback["prediction_updates"], "prediction_id", "反馈预测")
    if set(updates) != expected_predictions:
        raise GraphError("后继必须逐项评价前轮完整方案的预测")
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
                    request["baseline_source_sha256"] != previous["current_parent_ref"]["sha256"]):
                raise GraphError("反馈算子/父实现与前轮决策不匹配")
            if decision['current_parent_ref']['sha256'] not in {request['baseline_source_sha256'], request['candidate_source_sha256']} and feedback.get('parent_history_ref') is None:
                raise GraphError('当前父本既非前轮比较对象，也没有已核验的祖先父本')
        for prediction_id, update in updates.items():
            if update["judgement"] in {"supported", "weakened"} and not update["evidence_refs"]:
                raise GraphError("预测得到支持/削弱必须有对应结果依据")
            if measurement == "invalid" and prediction_kinds[prediction_id] == "performance" and update["judgement"] in {"supported", "weakened"}:
                raise GraphError("无效结果不能确认或削弱性能预测")
            for ref in update["evidence_refs"]:
                _task_ref(task_root, ref, decision["task_id"])
    selected = selected_scheme(decision)
    if selected and previous_selected:
        current_actions = {o['action_id'] for o in decision['opportunities'] if o['id'] in {m['opportunity_id'] for m in selected['members']}}
        previous_actions = {o['action_id'] for o in previous['opportunities'] if o['id'] in {m['opportunity_id'] for m in previous_selected['members']}}
        if current_actions == previous_actions and not feedback['same_scheme_reason']:
            raise GraphError('继续相同 Action 路线须说明值得检验的信息，不强制换 Action')
    _validate_reassessment(decision, task_root, reasoning)


def _validate_parent_history(root, decision, feedback, task_root):
    """仅复用线性不可变祖先中已绑定的父本，摘要或同 task 旁支均不授权。"""
    wanted = feedback.get('parent_history_ref')
    if wanted is None:
        raise GraphError('回到更早父本必须提供 parent_history_ref 及不可变祖先链')
    _task_ref(task_root, wanted, decision['task_id'])
    ref = feedback['previous_decision_ref']
    seen = set()
    expected_round = decision['round'] - 1
    while ref is not None:
        key = (ref['path'], ref['sha256'])
        if key in seen:
            raise GraphError('父本历史祖先链不能循环')
        seen.add(key)
        ancestor = _json(_task_ref(task_root, ref, decision['task_id']))
        if ancestor.get('schema_version') != VERSION:
            raise GraphError('父本历史祖先必须为显式 v3，不能投影或混装旧决策')
        validate_schema(Path(root), 'action-decision-v3', ancestor)
        if (ancestor['task_id'] != decision['task_id'] or ancestor['round'] != expected_round or
                ancestor['knowledge_hash'] != decision['knowledge_hash'] or
                not _same(ancestor['condition_policy_ref'], decision['condition_policy_ref']) or
                not _same(ancestor['routing_ref'], decision['routing_ref'])):
            raise GraphError('父本祖先链的 task/round/knowledge/policy/routing 身份不一致')
        workload = ancestor['path_overview']['workload_ref']
        if not _same(workload, decision['path_overview']['workload_ref']):
            raise GraphError('父本祖先链属于不同 workload，不能借摘要跨范围复用')
        _task_ref(task_root, workload, decision['task_id'])
        prior = _json(_task_ref(task_root, ancestor['reasoning_ref'], decision['task_id']))
        validate_schema(Path(root), 'diagnosis-reasoning', prior)
        if (content_hash(prior) != ancestor['reasoning_hash'] or prior['task_id'] != decision['task_id'] or
                prior['knowledge_hash'] != decision['knowledge_hash'] or prior['context_hash'] != ancestor['context_hash'] or
                not _same(prior['current']['implementation_ref'], ancestor['current_parent_ref']) or
                not _same(prior['current']['workload_ref'], workload)):
            raise GraphError('祖先父本必须由精确 reasoning 绑定，不能只填同 task 路径')
        _task_ref(task_root, ancestor['current_parent_ref'], decision['task_id'])
        scope = prior['current']['scope']
        if (scope['task_id'] != decision['task_id'] or scope['parent_implementation_hash'] != ancestor['current_parent_ref']['sha256']
                or scope['workload_hash'] != workload['sha256']):
            raise GraphError('祖先 reasoning scope 未绑定其父本及 workload')
        if _same(ref, wanted):
            if not _same(decision['current_parent_ref'], ancestor['current_parent_ref']):
                raise GraphError('parent_history_ref 没有绑定所请求的历史父本')
            return
        previous = ancestor['previous_feedback']
        ref = previous['previous_decision_ref'] if previous is not None else None
        expected_round -= 1
    raise GraphError('parent_history_ref 不是当前不可变链的祖先，不能借用同 task 旁支')


def _hypotheses(decision, scheme):
    ids = {m["opportunity_id"] for m in scheme["members"]}
    return {o["hypothesis_id"] for o in decision["opportunities"] if o["id"] in ids}


def _validate_reassessment(decision, task_root, reasoning):
    from .action_decision import _task_ref, _json, _same
    feedback = decision['previous_feedback']
    if feedback is None:
        return  # 原 validator 继续检查轮次
    r = feedback['reassessment']
    previous = _json(_task_ref(task_root, feedback['previous_decision_ref'], decision['task_id']))
    if previous.get('schema_version') != VERSION:
        raise GraphError('v3 后继需引用完整 v3 方案记录，不自动改写历史决策')
    attempt = r['attempt']
    if not _same(attempt['parent_ref'], previous['current_parent_ref']) or not _same(attempt['workload_ref'], previous['path_overview']['workload_ref']):
        raise GraphError('R2 尝试必须绑定前轮原始父本和完整 workload')
    has_impl = attempt['implementation_ref'] is not None
    if has_impl != (attempt['change_ref'] is not None):
        raise GraphError('已实施尝试须同时保留候选身份与实际变更引用')
    if (r['structure']['state'] == 'not_implemented' and has_impl) or (r['structure']['state'] in {'realized','partial','not_realized'} and not has_impl):
        raise GraphError('结构判断与是否存在已实施尝试不一致')
    if r['correctness']['state'] in {'passed','failed'} and not has_impl:
        raise GraphError('正确性结果必须绑定真实候选实现')
    for ref in attempt.values():
        if ref is not None:
            _task_ref(task_root, ref, decision['task_id'])
    if feedback['measurement'] == 'valid':
        result = _json(_task_ref(task_root, feedback['result_ref'], decision['task_id']))
        # 统一计时原始链已由共享 _feedback.verify_timing 验证，request 使用绝对路径。
        request = _json(Path(result['request']['path']))
        if not has_impl or attempt['implementation_ref']['sha256'] != request['candidate_source_sha256']:
            raise GraphError('反馈尝试身份与已验证计时候选不一致')
    prior_domains = {d['id'] for d in previous['path_overview']['domains']}
    if not set(r['measured_domain_ids']) <= prior_domains:
        raise GraphError('反馈测量域不属于前轮 workload')
    if feedback['measurement'] == 'not_measured' and (r['measured_domain_ids'] or r['measured_case_ids']):
        raise GraphError('未测反馈不能声明实测域')
    if feedback['measurement'] == 'valid' and not r['measured_domain_ids']:
        raise GraphError('有效反馈须声明实际测量域')
    if feedback['measurement'] == 'valid':
        actual_cases = {str(case['case_id']) for case in result['cases']}
        actual_domains = {d['id'] for d in previous['path_overview']['domains'] if set(d['case_ids']) & actual_cases}
        if (set(r['measured_case_ids']) != actual_cases or not actual_cases <= set(previous['path_overview']['case_ids'])
                or set(r['measured_domain_ids']) != actual_domains):
            raise GraphError('测量 case 必须精确对应真实结果，测量域仅表示相交域；不得扩大反馈范围')
        workload = _json(_task_ref(task_root, attempt['workload_ref'], decision['task_id']))
        case_workloads = workload_case_payloads(workload, previous['path_overview']['case_ids'])
        from .unified_timing import reference
        from .errors import ContractError
        try:
            for ref in request['candidate_captures']:
                capture_path = reference(Path(result['request']['path']).parent, ref)
                capture = _json(capture_path)
                captured_workload = _json(reference(capture_path.parent, capture['artifacts']['workload']))
                if not _same(case_workloads.get(str(capture['case_id'])), captured_workload):
                    raise GraphError('同 case 的计时 workload 与前轮冻结完整 payload 不同，不能归属本决策')
        except ContractError as exc:
            raise GraphError(f'反馈 workload 原始引用无效: {exc}') from exc
    expected_identity = {
        'parent_implementation_hash': attempt['parent_ref']['sha256'],
        'implementation_hash': attempt['implementation_ref']['sha256'] if has_impl else None,
        'workload_hash': attempt['workload_ref']['sha256']}

    def scoped_evidence(ref, *, direct_source=False):
        path = _task_ref(task_root, ref, decision['task_id'])
        if direct_source and any(_same(ref, attempt[key]) for key in ('implementation_ref', 'change_ref')):
            return
        if path.suffix != '.json':
            raise GraphError('反馈证据需含 attempt_identity 的 JSON 回执；原日志通过回执引用')
        record = _json(path)
        if not isinstance(record, dict) or record.get('attempt_identity') != expected_identity:
            raise GraphError('反馈证据属于其他候选/父本/workload，不能仅凭同 task 借用')
        for source_ref in record.get('source_refs', []):
            _task_ref(task_root, source_ref, decision['task_id'])

    prior_op = selected_scheme(previous)
    prediction_kinds = {p['id']: p['kind'] for p in prior_op['predictions']} if prior_op else {}
    for update in feedback['prediction_updates']:
        for ref in update['evidence_refs']:
            if feedback['measurement'] == 'valid' and _same(ref, feedback['result_ref']):
                continue  # 已由统一计时链及 attempt 候选身份校验，原结果无需重包成回执。
            scoped_evidence(ref, direct_source=prediction_kinds.get(update['prediction_id']) == 'source_work')

    for part in ('structure', 'correctness'):
        row = r[part]
        if row['state'] not in {'unknown','not_tested','not_implemented'} and not row['evidence_refs']:
            raise GraphError('结构/正确性判断必须有对应实际依据')
        for ref in row['evidence_refs']:
            scoped_evidence(ref, direct_source=part == 'structure')
    if r['correctness']['state'] == 'failed' and feedback['measurement'] == 'valid':
        raise GraphError('正确性失败不能声明有效性能测量')
    no_performance = feedback['measurement'] != 'valid' or r['correctness']['state'] != 'passed' or r['structure']['state'] in {'not_realized','not_implemented','unknown'}
    prior_op = selected_scheme(previous)
    kinds = {p['id']: p['kind'] for p in prior_op['predictions']} if prior_op else {}
    if no_performance and any(kinds.get(u['prediction_id']) == 'performance' and u['judgement'] in {'supported','weakened'} for u in feedback['prediction_updates']):
        raise GraphError('正确性/结构/测量未成立，性能预测不得被确认或否定')
    known_hypotheses = {c['hypothesis_id'] for c in reasoning['candidates']}
    for m in r['mechanisms']:
        if m['hypothesis_id'] not in known_hypotheses:
            raise GraphError('机制复盘须对应当前候选，不能凭空添加已确认机制')
        if m['judgement'] != 'undetermined' and (not m['evidence_refs'] or (no_performance and m['basis'] in {'performance','mixed'})):
            raise GraphError('机制性能判断需要可用测量；静态机制判断需独立证据')
        for ref in m['evidence_refs']:
            scoped_evidence(ref)
    if prior_op and len(prior_op['members']) > 1 and r['attribution']['kind'] == 'single_change':
        raise GraphError('联合方案的效果不能声明为已隔离的单项归因；不要求默认消融')
    if feedback['measurement'] == 'not_measured' and r['attribution']['kind'] != 'unmeasured':
        raise GraphError('无测量不能声明单一技巧或复合收益归因')
    nxt = r['next_step']
    opportunities = {o['id']: o for o in decision['schemes']}
    if not set(nxt['scheme_ids']) <= set(opportunities):
        raise GraphError('后继重新比较引用未知方案')
    selected_id = decision['selection']['scheme_id']
    if selected_id is not None and selected_id not in nxt['scheme_ids']:
        raise GraphError('后继重新比较必须包含当前完整方案')
    if nxt['kind'] == 'collect_evidence' and decision['selection']['mode'] == 'experiment':
        raise GraphError('补证据决定不能伪装为已选择实施试验')
    if nxt['kind'] == 'repair' and r['correctness']['state'] != 'failed' and r['structure']['state'] not in {'partial', 'not_realized'}:
        raise GraphError('修复后继需对应实际正确性或结构缺陷，不能改名绕过继续比较')
    if nxt['kind'] == 'change_mechanism' and prior_op and selected_id is not None and _hypotheses(decision, opportunities[selected_id]) == _hypotheses(previous, prior_op):
        raise GraphError('声明更换机制却仍绑定同一机制；应如实比较继续/重规划')
    selected_op = opportunities.get(selected_id)
    predictions = {p['id'] for p in selected_op['predictions']} if selected_op else set()
    if not set(nxt['discriminating_prediction_ids']) <= predictions:
        raise GraphError('后继必须引用当前真实判别预测')
    if nxt['kind'] in {'continue','retune'}:
        if not nxt['discriminating_prediction_ids']:
            raise GraphError('继续同方案必须给出本轮新的判别预测，不强制换 Action')
        old_predictions = {p['id']: p for p in prior_op['predictions']} if prior_op else {}
        current_predictions = {p['id']: p for p in selected_op['predictions']} if selected_op else {}
        changed = any((current_predictions[k]['statement'], current_predictions[k]['check_method']) !=
                      (old_predictions.get(k, {}).get('statement'), old_predictions.get(k, {}).get('check_method'))
                      for k in nxt['discriminating_prediction_ids'])
        updates = {u['prediction_id']: u for u in feedback['prediction_updates']}
        untested = all(updates.get(k, {}).get('judgement') in {'not_tested', 'undetermined'}
                       for k in nxt['discriminating_prediction_ids'])
        def hashes(value):
            if isinstance(value, dict):
                return ({value['sha256']} if 'sha256' in value else set()).union(*(hashes(v) for v in value.values()))
            if isinstance(value, list):
                return set().union(*(hashes(v) for v in value))
            return set()
        static_refs = r['structure']['evidence_refs'] + [ref for m in r['mechanisms']
                      if m['basis'] == 'static' for ref in m['evidence_refs']]
        new_static = any(ref['sha256'] not in hashes(previous) for ref in static_refs)
        prior_reasoning = _json(_task_ref(task_root, previous['reasoning_ref'], decision['task_id']))
        def instantiations(value, scheme):
            if scheme is None:
                return []
            registered = {i['instance_id']: i for i in value['action_instances']}
            rows = []
            for member in scheme['members']:
                instance = registered.get(member['action_instance_id'])
                if instance is None:
                    raise GraphError('后继参数比较需要前后真实 Action 实例，不能改名伪造新试验')
                rows.append({k: instance[k] for k in ('action_id', 'template_hash', 'targets', 'parameters')})
            # 列表顺序、实例改名不构成新的试验。
            from .jsonio import canonical_json
            return sorted(canonical_json(row) for row in rows)
        different_instantiation = instantiations(reasoning, selected_op) != instantiations(prior_reasoning, prior_op)
        recovery = r['correctness']['state'] == 'failed' or feedback['measurement'] == 'invalid'
        if not changed and not (different_instantiation or new_static or (untested and recovery)):
            raise GraphError('继续须有真实参数/方案变化、判别变化、独立新增静态依据，或恢复此前未测试预测的有效条件；不能仅重复表述')
    if nxt['kind'] == 'replan' and nxt['return_to'] != 'C2':
        raise GraphError('改变计划必须返回 C2')
    if nxt['kind'] == 'change_mechanism' and nxt['return_to'] != 'C1':
        raise GraphError('改变机制需回到 C1 比较')
    if (nxt['kind'] == 'stop') != (decision['selection']['mode'] == 'stop'):
        raise GraphError('后继停止与当前选择不一致')
