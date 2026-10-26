"""v2 机会比较和分层反馈。校验可追溯性，不替 Agent 排名或证明因果。"""
import math
from pathlib import Path

from .errors import GraphError

VERSION = 'aprof.action-decision/v2'


def workload_case_ids(value):
    """读取真实 workload 清单；单 workload 可用显式 case_id，否则用唯一 singleton。"""
    if isinstance(value, dict) and 'case_ids' in value:
        rows = value['case_ids']
    elif isinstance(value, dict) and 'cases' in value:
        rows = value['cases']
    elif isinstance(value, list):
        rows = value
    elif isinstance(value, dict):
        return {str(value.get('case_id', 'singleton'))}
    else:
        raise GraphError('workload 必须是对象或 case 清单')
    if not isinstance(rows, list) or not rows:
        raise GraphError('workload case 清单为空或不可解析')
    keys = []
    for row in rows:
        key = row.get('case_id', row.get('id')) if isinstance(row, dict) else row
        if not isinstance(key, (str, int)) or isinstance(key, bool):
            raise GraphError('workload 每个 case 必须有明确 case_id/id，不能按位置臆造身份')
        keys.append(str(key))
    if len(set(keys)) != len(keys):
        raise GraphError('workload case 身份重复')
    return set(keys)


def workload_case_payloads(value, expected_case_ids=None, *, required=True):
    """读取冻结的完整 payload；bare 清单只用于分析，不能按 case ID 归属测量。"""
    rows = value.get('cases') if isinstance(value, dict) else None
    mapped = isinstance(rows, list) and any(isinstance(row, dict) and 'workload' in row for row in rows)
    if not mapped and not required:
        return None
    if not isinstance(rows, list) or not rows or any(
            not isinstance(row, dict) or type(row.get('case_id')) not in (str, int)
            or not isinstance(row.get('workload'), dict) for row in rows):
        raise GraphError('需要测前冻结 cases[{case_id,workload}] 的完整测量映射；不可混装 bare 行或部分 payload，不能仅凭 case ID 归属计时')
    payloads = {str(row['case_id']): row['workload'] for row in rows}
    cases = set(expected_case_ids) if expected_case_ids is not None else workload_case_ids(value)
    if len(payloads) != len(rows) or set(payloads) != cases:
        raise GraphError('前轮测量映射必须唯一覆盖其完整 workload case 清单')
    return payloads


def missing_workload_mapping(decision, reasoning, task_root, artifact):
    """D7 新选择在实施前冻结映射；D6 历史记录继续按原版本回放。"""
    if artifact['version'] < 'v0007' or decision['selection']['mode'] not in {'experiment', 'conditional_plan'}:
        return []
    from .action_decision import _same, _task_ref, _json
    ref = decision['path_overview']['workload_ref']
    if not _same(ref, reasoning['current']['workload_ref']):
        raise GraphError('path_overview 必须绑定当前完整 workload 身份')
    workload = _json(_task_ref(task_root, ref, decision['task_id']))
    payloads = workload_case_payloads(workload, decision['path_overview']['case_ids'], required=False)
    if payloads is not None and any(not payload for payload in payloads.values()):
        raise GraphError('完整测量映射不能用空 workload payload 对象占位')
    return ['workload.full_case_payloads_before_selection'] if payloads is None else []


def validate_analysis(root, decision, reasoning, task_root):
    from .action_decision import _same, _task_ref, _json, _unique
    from .diagnosis_reasoning import fact_state
    overview = decision['path_overview']
    if not _same(overview['workload_ref'], reasoning['current']['workload_ref']):
        raise GraphError('path_overview 必须绑定当前完整 workload 身份')
    workload = _json(_task_ref(task_root, overview['workload_ref'], decision['task_id']))
    cases = workload_case_ids(workload)
    if set(overview['case_ids']) != cases:
        raise GraphError('路径概览必须穷尽真实 workload case 清单')
    scope = reasoning['current']['scope']

    def facts(keys):
        for key in keys:
            fact = reasoning['facts'].get(key)
            if fact is None or fact_state(reasoning, key) == 'unknown' or not _same(fact['scope'], scope):
                raise GraphError('分析事实必须已知并绑定当前实现/workload/目标完整范围')

    def quantity(q):
        facts(q['fact_ids'])
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

    def work(rows, baseline=False):
        _unique(rows, 'id', '工作量')
        for row in rows:
            stage = stages.get(row['stage_id'])
            if stage is None or not set(row['domain_ids']) <= set(stage['domain_ids']):
                raise GraphError('工作量引用未知阶段或阶段之外的域')
            if (row['change'] == 'baseline') != baseline:
                raise GraphError('基线工作与拟变化必须分别标记')
            quantity(row['quantity'])

    work(overview['baseline_work'], baseline=True)
    if {w['stage_id'] for w in overview['baseline_work']} != set(stages):
        raise GraphError('所有路径阶段都必须说明基线工作')
    opportunities = {o['id']: o for o in decision['opportunities']}
    items = {}
    for op in opportunities.values():
        a = op['analysis']
        if op['action_id'] is None:
            if not a['intent_gap'] or op['action_instance_id'] is not None or op['performance_hypotheses']:
                raise GraphError('未注册意图需说明缺口，不能伪造实例或注册性能假设')
        elif a['intent_gap'] is not None:
            raise GraphError('注册 Action 的语义不足不能用 intent_gap 掩盖')
        if op['strongest_alternative_id'] is None and not a['no_alternative_reason']:
            raise GraphError('无合理替代时须说明完整路径审查后的理由，不凑数量')
        work(a['work_delta'])
        coverage = _unique(a['coverage'], 'domain_id', '机会覆盖域')
        if set(coverage) != set(domains):
            raise GraphError('每个机会必须分别交代全部域：受影响/部分/未变/不适用/未知')
        affected = set()
        for row in coverage.values():
            facts(row['fact_ids'])
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
                quantity(row['change'])
            else:
                facts(row['fact_ids'])
        remaining = {d for d, c in coverage.items() if c['status'] != 'affected'}
        if not remaining <= {d for r in a['residuals'] for d in r['domain_ids']}:
            raise GraphError('未变/部分/不适用/未知域必须保留残余工作及下一步')
        rows = a['work_delta'] + a['coverage'] + a['tradeoffs'] + a['residuals']
        items[op['id']] = _unique(rows, 'id', '机会分析项')
    sel = decision['selection']
    selected = sel['opportunity_id']
    roles = set()
    for basis in sel['comparison_basis']:
        op_id = basis['opportunity_id']
        if op_id not in items or not set(basis['item_ids']) <= set(items[op_id]):
            raise GraphError('选择依据必须引用实际比较过的具体工作/覆盖/代价项')
        if selected is not None:
            alt = opportunities[selected]['strongest_alternative_id']
            if op_id not in {selected, alt}:
                raise GraphError('选择依据不能引用无关机会充当最强替代比较')
            if (basis['role'] == 'alternative') != (op_id != selected):
                raise GraphError('所选方向与替代方向的比较角色不一致')
        roles.add(basis['role'])
        expected = {'benefit': 'work_delta', 'cost': 'tradeoffs', 'coverage': 'coverage', 'residual': 'residuals'}
        if basis['role'] in expected:
            allowed = {r['id'] for r in opportunities[op_id]['analysis'][expected[basis['role']]]
                       if basis['role'] != 'benefit' or r['change'] == 'reduced'}
            if not set(basis['item_ids']) <= allowed:
                raise GraphError('选择依据角色必须对应工作/代价/覆盖/残余的正确分析项')
    if selected is not None:
        if sel['mode'] in {'experiment', 'conditional_plan'} and not opportunities[selected]['case_ids']:
            raise GraphError('完全未变/不适用的机会不能作为正式实施或 C2 计划选择')
        if not {'benefit', 'cost', 'coverage'} <= roles:
            raise GraphError('选择必须同时解释工作变化、覆盖和代价怎样影响判断')
        if opportunities[selected]['strongest_alternative_id'] and 'alternative' not in roles:
            raise GraphError('已识别最强替代不能从最终选择比较中消失')
        if opportunities[selected]['analysis']['residuals'] and 'residual' not in roles:
            raise GraphError('已知残余问题必须进入优先级与后续选择说明')
        if opportunities[selected]['action_id'] is None and sel['mode'] in {'experiment', 'conditional_plan'}:
            raise GraphError('未注册意图只能补证据/提案，不能直接进入正式 P/O')
    validate_reassessment(decision, task_root, reasoning)


def validate_reassessment(decision, task_root, reasoning):
    from .action_decision import _task_ref, _json, _same
    feedback = decision['previous_feedback']
    if feedback is None:
        return  # 原 validator 继续检查轮次
    r = feedback['reassessment']
    previous = _json(_task_ref(task_root, feedback['previous_decision_ref'], decision['task_id']))
    if previous.get('schema_version') != VERSION:
        raise GraphError('v2 后继需引用完整 v2 比较记录，不自动改写历史 v1')
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

    prior_op = next((o for o in previous['opportunities'] if o['id'] == previous['selection']['opportunity_id']), None)
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
    prior_op = next((o for o in previous['opportunities'] if o['id'] == previous['selection']['opportunity_id']), None)
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
    if feedback['measurement'] == 'not_measured' and r['attribution']['kind'] != 'unmeasured':
        raise GraphError('无测量不能声明单一技巧或复合收益归因')
    nxt = r['next_step']
    opportunities = {o['id']: o for o in decision['opportunities']}
    if not set(nxt['opportunity_ids']) <= set(opportunities):
        raise GraphError('后继重新比较引用未知机会')
    selected_id = decision['selection']['opportunity_id']
    if selected_id is not None and selected_id not in nxt['opportunity_ids']:
        raise GraphError('后继重新比较必须包含当前所选机会')
    if nxt['kind'] == 'collect_evidence' and decision['selection']['mode'] == 'experiment':
        raise GraphError('补证据决定不能伪装为已选择实施试验')
    if nxt['kind'] == 'repair' and r['correctness']['state'] != 'failed' and r['structure']['state'] not in {'partial', 'not_realized'}:
        raise GraphError('修复后继需对应实际正确性或结构缺陷，不能改名绕过继续比较')
    if nxt['kind'] == 'change_mechanism' and prior_op and selected_id is not None and opportunities[selected_id]['hypothesis_id'] == prior_op['hypothesis_id']:
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
        recovery = r['correctness']['state'] == 'failed' or feedback['measurement'] == 'invalid'
        if not changed and not (new_static or (untested and recovery)):
            raise GraphError('继续须有判别变化、独立新增静态依据，或恢复此前未测试预测的有效条件；不能仅重复表述')
    if nxt['kind'] == 'replan' and nxt['return_to'] != 'C2':
        raise GraphError('改变计划必须返回 C2')
    if nxt['kind'] == 'change_mechanism' and nxt['return_to'] != 'C1':
        raise GraphError('改变机制需回到 C1 比较')
    if (nxt['kind'] == 'stop') != (decision['selection']['mode'] == 'stop'):
        raise GraphError('后继停止与当前选择不一致')
