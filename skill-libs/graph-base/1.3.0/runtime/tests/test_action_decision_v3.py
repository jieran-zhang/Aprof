"""完整方案、共享工作、后继反馈及版本隔离的 CPU 合同测试。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from aprof_runtime import action_decision, bindings, diagnosis
from aprof_runtime.action_decision_v3 import selected_scheme, validate_decision
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash, file_hash
from test_action_decision import make_decision, persist_reasoning, safety_unknown
from test_action_decision_v2 import v2_fields, feedback_fields
from test_action_handoff_v3 import write_json

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def scheme_package(tmp_path_factory):
    root = tmp_path_factory.mktemp('scheme-package') / 'package'
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    # 历史 v3 样例显式冻结 D6，发布 D7 不应重写其测前准入语义。
    candidates = []
    for path in (root / bindings.ROUTING_SNAPSHOTS).glob('*.json'):
        config = json.loads(path.read_text())
        if config.get('bases', {}).get('diagnosis', {}).get('version') == 'v0006':
            candidates.append((path, config))
    assert candidates, '缺少 D6 冻结 routing bundle'
    path, _ = sorted(candidates, key=lambda pair: pair[1]['version'])[-1]
    artifacts, _ = bindings.load_frozen_bundle(root, {'path': str(path.relative_to(root)), 'sha256': file_hash(path)})
    (root / bindings.CONFIG).write_bytes(path.read_bytes())
    artifact = artifacts['diagnosis']
    import test_action_handoff_v3 as handoff_fixture
    original_diagnosis, original_tree = diagnosis.verify, bindings.verify_tree
    def frozen_diagnosis(candidate):
        return deepcopy(artifact) if Path(candidate).resolve() == root.resolve() else original_diagnosis(candidate)
    def frozen_tree(candidate, owner):
        return deepcopy(artifacts[owner]) if Path(candidate).resolve() == root.resolve() else original_tree(candidate, owner)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(diagnosis, 'verify', frozen_diagnosis)
        patch.setattr(bindings, 'verify_tree', frozen_tree)
        patch.setattr(handoff_fixture, 'verify_tree', frozen_tree)
        yield root, artifact


def v3_fields(decision, reasoning):
    d = v2_fields(decision, reasoning)
    d['schema_version'] = 'aprof.action-decision/v3'
    op = d['opportunities'][0]
    instance = op['action_instance_id']
    analysis = deepcopy(op['analysis'])
    analysis.pop('intent_gap'); analysis.pop('no_alternative_reason')
    analysis['work_accounting'] = [{'joint_work_id': r['id'],
        'member_work_refs': [{'opportunity_id': op['id'], 'item_id': r['id']}],
        'accounting': 'distinct', 'explanation': '一次核算成员工作，不当作实测时间'}
        for r in analysis['work_delta']]
    analysis['resource_lifetimes'] = []
    scheme = {'id': 'scheme.transfer', 'goal': '在原输出所有权内完成连续块搬运方案',
        'members': [{'opportunity_id': op['id'], 'action_instance_id': instance,
                     'role': '连续块搬运', 'rationale': '主体与尾块一起实施'}],
        'steps': [{'id': 'transfer', 'action_instance_ids': [instance], 'depends_on': [],
                   'description': '同一候选实现主体与尾部，不人为拆轮', 'guarantees': []}],
        'analysis': analysis, 'predictions': deepcopy(op['predictions']),
        'strongest_alternative_id': None, 'no_alternative_reason': '已检查完整路径，无独立方向，不凑数量',
        'reason': '减少有源码依据的调用，容量与性能分别讨论'}
    d['schemes'] = [scheme]
    d['selection'].pop('opportunity_id'); d['selection'].pop('action_instance_id')
    d['selection']['scheme_id'] = scheme['id']
    for basis in d['selection']['comparison_basis']:
        basis.pop('opportunity_id'); basis['scheme_id'] = scheme['id']
    return d


def make_v3_decision(root, artifact, task, *, workload=None, routing_features=None, routing_structure=None):
    d, chain = make_decision(root, artifact, task, workload=workload, routing_features=routing_features, routing_structure=routing_structure)
    return v3_fields(d, chain[0]['reasoning']), chain


@pytest.fixture
def sample(scheme_package, tmp_path):
    root, artifact = scheme_package
    task = tmp_path / 'task'
    d, chain = make_v3_decision(root, artifact, task)
    return root, artifact, task, d, chain


def check(sample, implementation=False):
    root, _, task, d, _ = sample
    return validate_decision(root, d, task_root=task, implementation=implementation)


def add_member(d, chain, task):
    """同一注册 Action 的另一实例；每个实例仍须独立核对条件。"""
    instance = deepcopy(chain[0]['reasoning']['action_instances'][0])
    instance['instance_id'] += '.second'
    chain[0]['reasoning']['action_instances'].append(instance)
    op = deepcopy(d['opportunities'][0])
    op['id'] += '.second'; op['action_instance_id'] = instance['instance_id']
    for u in op['unknowns']: u['id'] += '.second'
    for h in op['performance_hypotheses']:
        if h['unknown_id'] is not None: h['unknown_id'] += '.second'
    for request in list(d['evidence_requests']):
        if d['opportunities'][0]['id'] in request['opportunity_ids']:
            other = deepcopy(request)
            other['id'] += '.second'
            other['opportunity_ids'] = [op['id']]
            other['unknown_ids'] = [k + '.second' for k in other['unknown_ids']]
            d['evidence_requests'].append(other)
    d['opportunities'].append(op)
    d['knowledge_use'][0]['opportunity_ids'].append(op['id'])
    s = selected_scheme(d)
    s['members'].append({'opportunity_id': op['id'], 'action_instance_id': instance['instance_id'],
                         'role': '配套步骤', 'rationale': '一并完成依赖，不人为新增轮次'})
    s['steps'].append({'id': 'consumer', 'action_instance_ids': [instance['instance_id']],
                       'depends_on': ['transfer'], 'description': '消费先行步骤的数据', 'guarantees': []})
    for row in s['analysis']['work_accounting']:
        row['member_work_refs'].append({'opportunity_id': op['id'], 'item_id': row['joint_work_id']})
        row['accounting'] = 'shared_once'
        row['explanation'] = '共同消除同一调用组，只计算一次'
    persist_reasoning(d, chain, task)
    return instance, op


def successor(d, task, name):
    prev = write_json(task / name, d)
    nxt = deepcopy(d); nxt['round'] += 1
    nxt['selection']['mode'] = 'conditional_plan'
    s = selected_scheme(nxt)
    nxt['previous_feedback'] = {'previous_decision_ref': prev, 'result_ref': None,
        'measurement': 'not_measured', 'result_limits': 'CPU无硬件计时',
        'prediction_updates': [{'prediction_id': p['id'], 'judgement': 'not_tested',
            'reason': '逻辑工作不是实测时间', 'evidence_refs': []}
            for p in selected_scheme(d)['predictions']],
        'current_parent_ref': deepcopy(nxt['current_parent_ref']), 'parent_reason': '保留原父本',
        'same_scheme_reason': '尚未回答的覆盖和成本问题，不强制换Action',
        'new_information': '保留未测身份，先做条件分析'}
    feedback_fields(nxt)
    step = nxt['previous_feedback']['reassessment']['next_step']
    step.pop('opportunity_ids'); step['scheme_ids'] = [s['id']]
    return nxt


def test_single_member_dispatch_and_unknown_performance(sample):
    result = check(sample, True)
    assert result['status'] == 'ready'
    assert result['schema_version'] == 'aprof.action-decision-validation/v3'
    assert 'missing_workload_mapping' not in result  # D6 显式保留旧首轮准入。
    assert result['performance_claim'] is False
    assert action_decision.validate_decision(sample[0], sample[3], task_root=sample[2]) == result


def test_multi_member_shared_work_is_counted_once(sample):
    add_member(sample[3], sample[4], sample[2])
    result = check(sample, True)
    assert len(result['member_instance_ids']) == 2
    assert len(result['member_readiness']) == 2


@pytest.mark.parametrize('mutation', ['missing_member', 'borrow_instance', 'double_work', 'omit_work', 'missing_cost', 'wrong_role', 'cycle', 'unknown_step'])
def test_scheme_must_be_complete_and_jointly_compared(sample, mutation):
    d = sample[3]; add_member(d, sample[4], sample[2]); s = selected_scheme(d)
    if mutation == 'missing_member': s['members'].pop()
    if mutation == 'borrow_instance': s['members'][1]['action_instance_id'] = s['members'][0]['action_instance_id']
    if mutation == 'double_work': s['analysis']['work_accounting'][0]['member_work_refs'].append(deepcopy(s['analysis']['work_accounting'][0]['member_work_refs'][0]))
    if mutation == 'omit_work': s['analysis']['work_accounting'][0]['member_work_refs'].pop()
    if mutation == 'missing_cost': d['selection']['comparison_basis'] = [b for b in d['selection']['comparison_basis'] if b['role'] != 'cost']
    if mutation == 'wrong_role': d['selection']['comparison_basis'][0]['item_ids'] = ['ub']
    if mutation == 'cycle': s['steps'][0]['depends_on'] = ['consumer']
    if mutation == 'unknown_step': s['steps'][1]['depends_on'] = ['absent']
    with pytest.raises(GraphError): check(sample)


def test_safety_unknown_and_planned_guarantee_are_not_actual_facts(sample):
    d, chain, task = sample[3], sample[4], sample[2]
    safety_unknown(d, chain, task)
    instance, _ = add_member(d, chain, task)
    s = selected_scheme(d)
    s['steps'][0]['guarantees'] = [{'id': 'capacity.after', 'predicate': 'constraint.capacity',
        'expected_state': True, 'target_instance_ids': [instance['instance_id']],
        'check_method': 'C3精确绑定最终源码与共同计划'}]
    result = check(sample)
    assert result['status'] == 'conditional'
    assert result['member_readiness'][1]['planned_guarantees'][0]['id'] == 'capacity.after'
    assert chain[0]['reasoning']['facts']['constraint.capacity']['state'] == 'unknown'
    with pytest.raises(GraphError, match='计划保证'): check(sample, True)


def test_lifetime_peak_uses_concurrent_allocations(sample):
    d = sample[3]; add_member(d, sample[4], sample[2]); s = selected_scheme(d)
    base = deepcopy(s['analysis']['work_delta'][0]['quantity'])
    def q(n): return dict(base, mode='exact', expression=str(n), unit='bytes', symbols=[], value=n)
    members = [m['action_instance_id'] for m in s['members']]
    s['analysis']['resource_lifetimes'] = [{'id': 'shared.ub', 'resource': 'UB', 'domain_ids': ['all'],
        'capacity': q(96), 'allocations': [
            {'id': 'producer', 'member_instance_ids': [members[0]], 'quantity': q(64), 'live_step_ids': ['transfer']},
            {'id': 'consumer', 'member_instance_ids': [members[1]], 'quantity': q(64), 'live_step_ids': ['consumer']}],
        'peak': q(64), 'peak_step_ids': ['transfer', 'consumer'], 'assessment': 'fits',
        'consequence': '不同时存活则复用容量，不直接相加全部变量'}]
    assert check(sample)['status'] == 'ready'
    s['analysis']['resource_lifetimes'][0]['allocations'][0]['live_step_ids'].append('consumer')
    with pytest.raises(GraphError, match='峰值'): check(sample)


def test_round_three_replays_complete_feedback_without_forced_action_change(sample):
    root, artifact, task, d, chain = sample
    d = successor(d, task, 'r1.json')
    assert check((root, artifact, task, d, chain))['status'] == 'conditional'
    d = successor(d, task, 'r2.json')
    assert d['round'] == 3
    assert check((root, artifact, task, d, chain))['status'] == 'conditional'
    d['previous_feedback']['prediction_updates'][1]['judgement'] = 'supported'
    with pytest.raises(GraphError): check((root, artifact, task, d, chain))


def test_whole_scheme_predictions_drive_feedback(sample):
    root, artifact, task, d, chain = sample
    selected_scheme(d)['predictions'][0]['id'] = 'whole.source'
    nxt = successor(d, task, 'r1.json')
    assert check((root, artifact, task, nxt, chain))['status'] == 'conditional'
    nxt['previous_feedback']['prediction_updates'][0]['prediction_id'] = d['opportunities'][0]['predictions'][0]['id']
    with pytest.raises(GraphError, match='完整方案'): check((root, artifact, task, nxt, chain))


def test_handoff_v4_requires_exact_scheme_and_all_members(sample):
    root, artifact, task, d, chain = sample
    add_member(d, chain, task)
    c1 = deepcopy(chain[0]); c1['schema_version'] = 'aprof.handoff/v4'
    c1['decision_ref'] = write_json(task / 'decision.json', d)
    c1['artifacts'] = [c1['decision_ref']]
    c1['scheme_id'] = selected_scheme(d)['id']; c1['scheme_hash'] = content_hash(selected_scheme(d))
    ids = [m['action_instance_id'] for m in selected_scheme(d)['members']]
    result = action_decision.validate_handoff_decision(root, c1, ids, task_root=task, artifact=artifact, implementation=False)
    assert result['member_instance_ids'] == ids
    with pytest.raises(GraphError, match='精确对应'):
        action_decision.validate_handoff_decision(root, c1, ids[:1], task_root=task, artifact=artifact, implementation=False)
    c1['schema_version'] = 'aprof.handoff/v3'
    with pytest.raises(GraphError, match='旧 handoff/v3'):
        action_decision.validate_handoff_decision(root, c1, ids[0], task_root=task, artifact=artifact, implementation=False)


@pytest.mark.parametrize('candidate_us,judgement,wrong_payload', [(80, 'supported', False), (110, 'weakened', False), (80, 'supported', True)])
def test_compound_feedback_support_and_regression_are_scoped_not_single_factor(sample, candidate_us, judgement, wrong_payload):
    import json
    from aprof_runtime.unified_timing import finalize_timing
    from aprof_runtime.jsonio import file_hash
    from test_unified_timing import campaign
    from test_action_decision_v2 import attempt_identity
    root, artifact, task, d, chain = sample
    add_member(d, chain, task)
    measurement = task / 'measurement'; measurement.mkdir()
    request_path, config = campaign(measurement, candidate_us=candidate_us)  # CPU FakeRunner，无设备。
    request = json.loads(request_path.read_text())
    sources = {}
    for role in ('baseline', 'candidate'):
        capture_path = measurement / request[role + '_captures'][0]['path']
        capture = json.loads(capture_path.read_text())
        source = task / (role + '-source.json')
        shutil.copyfile(capture_path.parent / capture['artifacts']['source']['path'], source)
        sources[role] = {'path': source.name, 'sha256': file_hash(source)}
    reasoning = chain[0]['reasoning']
    reasoning['current']['implementation_ref'] = sources['baseline']
    measured_workload = deepcopy(config['cases'][0]['workload'])
    if wrong_payload: measured_workload['shape'] = [64]
    workload = write_json(task / 'workload.json', {'cases': [
        {'case_id': 1, 'workload': measured_workload},
        {'case_id': 2, 'workload': dict(measured_workload, shape=[128])}]})
    reasoning['current']['workload_ref'] = workload
    scope = reasoning['current']['scope']
    scope['parent_implementation_hash'] = sources['baseline']['sha256']
    scope['workload_hash'] = workload['sha256']
    for row in list(reasoning['facts'].values()) + reasoning['candidates'] + reasoning['action_instances']:
        row['scope'] = deepcopy(scope)
    context_path = task / reasoning['source_context_ref']['path']
    context = json.loads(context_path.read_text()); context['operator'] = request['operator']
    reasoning['source_context_ref'] = write_json(context_path, context)
    reasoning['context_snapshot']['source_context_ref'] = deepcopy(reasoning['source_context_ref'])
    reasoning['context_hash'] = content_hash(reasoning['context_snapshot'])
    d['context_hash'] = reasoning['context_hash']; d['current_parent_ref'] = deepcopy(sources['baseline'])
    persist_reasoning(d, chain, task)
    d['path_overview']['workload_ref'] = workload
    d['path_overview']['case_ids'] = ['1', '2']
    d['path_overview']['domains'][0]['case_ids'] = ['1', '2']
    for op in d['opportunities']: op['case_ids'] = ['1', '2']
    assert check((root, artifact, task, d, chain), True)['status'] == 'ready'
    nxt = successor(d, task, 'r1.json')
    f = nxt['previous_feedback']; r = f['reassessment']
    result_path = measurement / 'result.json'; finalize_timing(request_path, result_path)
    f.update(measurement='valid', result_ref={'path': str(result_path.relative_to(task)), 'sha256': file_hash(result_path)})
    r['attempt']['implementation_ref'] = sources['candidate']
    r['attempt']['change_ref'] = write_json(task / 'change.json', {'task_id': d['task_id'], 'changes': ['完整联合方案']})
    evidence = write_json(task / 'feedback-evidence.json', {'task_id': d['task_id'],
        'attempt_identity': attempt_identity(nxt), 'source_refs': [f['result_ref']]})
    r['structure'] = {'state': 'partial', 'evidence_refs': [evidence], 'finding': 'CPU回执：方案部分结构实现，收益不拆归单项'}
    r['correctness'] = {'state': 'passed', 'evidence_refs': [evidence], 'finding': 'CPU FakeRunner原oracle链'}
    r.update(measured_domain_ids=['all'], measured_case_ids=['1'],
             attribution={'kind': 'compound', 'limits': '仅case1支持或削弱整体方案，不证明任一成员机制，不要求默认消融'})
    f['prediction_updates'][1].update(judgement=judgement, evidence_refs=[f['result_ref']],
        reason='只评价匹配范围的整体预测；CPU数据不代表真实设备')
    data = (root, artifact, task, nxt, chain)
    if wrong_payload:
        with pytest.raises(GraphError, match='冻结完整 payload'): check(data)
        return
    assert check(data)['status'] == 'conditional'
    r['attribution']['kind'] = 'single_change'
    with pytest.raises(GraphError, match='单项归因'): check(data)


def test_invalid_measurement_and_repair_do_not_force_new_action(sample):
    from test_action_decision_v2 import attempt_identity
    root, artifact, task, d, chain = sample
    nxt = successor(d, task, 'r1.json'); f = nxt['previous_feedback']; r = f['reassessment']
    f.update(measurement='invalid', result_ref=write_json(task / 'invalid.json', {'task_id': d['task_id'], 'reason': 'CPU合成无效计时'}))
    r['next_step'].update(kind='continue', discriminating_prediction_ids=['time'])
    assert check((root, artifact, task, nxt, chain))['status'] == 'conditional'
    r['attempt']['implementation_ref'] = write_json(task / 'candidate.json', {'task_id': d['task_id'], 'changed': True})
    r['attempt']['change_ref'] = write_json(task / 'change.json', {'task_id': d['task_id'], 'change': '尾块'})
    evidence = write_json(task / 'failed.json', {'task_id': d['task_id'], 'attempt_identity': attempt_identity(nxt)})
    r['structure'] = {'state': 'partial', 'evidence_refs': [evidence], 'finding': '尾块未完成'}
    r['correctness'] = {'state': 'failed', 'evidence_refs': [evidence], 'finding': '原oracle失败'}
    r['next_step'].update(kind='repair', return_to='C3', discriminating_prediction_ids=[])
    assert check((root, artifact, task, nxt, chain))['status'] == 'conditional'
    f['prediction_updates'][1].update(judgement='supported', evidence_refs=[evidence])
    with pytest.raises(GraphError): check((root, artifact, task, nxt, chain))


def test_rescheduling_can_improve_overlap_without_falsely_claiming_less_work(sample):
    d = sample[3]; s = selected_scheme(d)
    row = d['opportunities'][0]['analysis']['work_delta'][0]
    row['change'] = 'rescheduled'
    row['explanation'] = '总搬运字节及调用数不变，发射与消费顺序改为允许重叠；是否减少等待仍须验证'
    s['analysis']['work_delta'][0] = deepcopy(row)
    s['predictions'][1]['statement'] = '若搬运计算可重叠，整体时间下降；不声称总工作减少'
    assert check(sample)['status'] == 'ready'
    row['change'] = 'retained'; s['analysis']['work_delta'][0]['change'] = 'retained'
    with pytest.raises(GraphError, match='角色'): check(sample)


def test_members_can_have_distinct_targets_without_borrowing_evidence(sample):
    d, chain, task = sample[3], sample[4], sample[2]
    instance, op = add_member(d, chain, task)
    reasoning = chain[0]['reasoning']
    reasoning['current']['scope']['target_ids'].append('tensor.y')
    reasoning['current']['objects'].append({'object_id': 'tensor.y', 'kind': 'tensor', 'description': '独立目标'})
    mapping = {k: k + '.target_y' for k in reasoning['facts']}
    for key, fact in list(reasoning['facts'].items()):
        other = deepcopy(fact); other['scope']['target_ids'] = ['tensor.y']
        other['derived_from'] = [mapping[k] for k in other['derived_from']]
        if 'components' in other: other['components'] = [mapping[k] for k in other['components']]
        reasoning['facts'][mapping[key]] = other
    candidate = deepcopy(reasoning['candidates'][0]); candidate['hypothesis_id'] += '.target_y'
    candidate['scope']['target_ids'] = ['tensor.y']; candidate['targets'] = ['tensor.y']
    for key in ('support', 'counter', 'unknown', 'excluded_by'):
        candidate[key] = [mapping[k] for k in candidate[key]]
    candidate['independent_evidence_groups'] = [[mapping[k] for k in group] for group in candidate['independent_evidence_groups']]
    reasoning['candidates'].append(candidate)
    instance['scope']['target_ids'] = ['tensor.y']; instance['hypothesis_id'] = candidate['hypothesis_id']
    instance['targets'] = {k: ('tensor.y' if v == 'tensor.x' else v) for k, v in instance['targets'].items()}
    instance['evidence_bindings'] = {k: mapping[v] for k, v in instance['evidence_bindings'].items()}
    op['hypothesis_id'] = candidate['hypothesis_id']; op['source_fact_ids'] = [mapping[k] for k in op['source_fact_ids']]
    for h in op['performance_hypotheses']: h['evidence_fact_ids'] = [mapping[k] for k in h['evidence_fact_ids']]
    for row in op['analysis']['work_delta']: row['quantity']['fact_ids'] = [mapping[k] for k in row['quantity']['fact_ids']]
    for row in op['analysis']['coverage'] + op['analysis']['residuals']: row['fact_ids'] = [mapping[k] for k in row['fact_ids']]
    for row in op['analysis']['tradeoffs']: row['change']['fact_ids'] = [mapping[k] for k in row['change']['fact_ids']]
    s = selected_scheme(d)
    for row in s['analysis']['work_accounting']: row['accounting'] = 'distinct'
    q = s['analysis']['work_delta'][0]['quantity']
    q['expression'] = 'Nx/B + Ny/B'
    q['symbols'] = [{'name': 'Nx', 'meaning': 'x元素数', 'unit': 'elements'},
                    {'name': 'Ny', 'meaning': 'y元素数', 'unit': 'elements'},
                    {'name': 'B', 'meaning': '复制粒度', 'unit': 'elements/call'}]
    q['fact_ids'] += [mapping[k] for k in q['fact_ids']]
    persist_reasoning(d, chain, task)
    assert check(sample)['status'] == 'ready'
    op['analysis']['work_delta'][0]['quantity']['fact_ids'] = d['opportunities'][0]['source_fact_ids']
    with pytest.raises(GraphError, match='其他目标'): check(sample)


def add_distinct_action(d, chain, task, artifact, action_id='action.batch_writeback', *, root=None):
    """从冻结注册模板/政策构造真实异构成员，不将首 Action 改名冒充。"""
    from aprof_runtime.knowledge_history import knowledge_source
    from test_action_decision import body_locator
    root = Path(root) if root is not None else ROOT
    instance, op = add_member(d, chain, task)
    action = next(r for r in artifact['records'] if r['id'] == action_id)
    _, policies = action_decision.condition_policy(root, artifact)
    policy = policies[action_id]
    instance['action_id'] = action_id; instance['template_hash'] = content_hash(action)
    # 本helper选取相同slot结构的搬入/写回；模板不同导致的条件分别绑定原始回执。
    assert set(instance['targets']) == {s['name'] for s in action['slots']}
    op['action_id'] = action_id
    reasoning = chain[0]['reasoning']
    values = {p['fact']: p['state'] for p in policy['safety_conditions']}
    nodes = {r['id']: r for r in artifact['records']}
    composites = {}
    for predicate, state in list(values.items()):
        components = [c['id'] for c in nodes.get(predicate, {}).get('observation', {}).get('required_components', [])]
        if components:
            composites[predicate] = components
            for index, component in enumerate(components):
                values[component] = state if index == 0 else True
    source = write_json(task / 'writeback-source.json', {'task_id': d['task_id'],
        'kind': 'CPU_source_fixture', 'declared_states': values, 'description': '同owner相邻输出在完成后批量写回'})
    for predicate, state in values.items():
        key = 'writeback.' + predicate
        reasoning['facts'][key] = {'state': state, 'kind': 'raw', 'predicate': predicate,
            'evidence_id': key, 'ref': dict(source, locator=predicate), 'derived_from': [],
            'scope': deepcopy(instance['scope'])}
        if nodes.get(predicate, {}).get('view'):
            reasoning['facts'][key]['view'] = nodes[predicate]['view']
        instance['evidence_bindings'][predicate] = key
    for predicate, components in composites.items():
        keys = ['writeback.' + c for c in components]
        reasoning['facts']['writeback.' + predicate].update(kind='derived', evidence_id=None,
            ref=None, derived_from=keys, components=keys)
    fact = 'writeback.symptom.source.fragmented_writeback'
    op['source_fact_ids'] = [fact]
    op['cost_mechanism'] = '延迟释放合法相邻输出，降低写回发射数，并计入更长buffer存活'
    op['performance_hypotheses'] = []
    op['unknowns'] = []
    for h in policy['performance_hypotheses']:
        unknown = 'writeback.u.' + h['id']
        op['unknowns'].append({'id': unknown, 'kind': 'performance', 'fact': (h['legacy_condition'] or {}).get('fact'),
            'expected_state': None, 'statement': '写回粒度收益未测', 'affects': '性能优先级', 'resolution': 'test_in_experiment'})
        op['performance_hypotheses'].append({'hypothesis_id': h['id'], 'state': 'unknown',
            'evidence_fact_ids': [], 'prediction_id': 'time', 'unknown_id': unknown, 'reason': '有来源和结构，性能待测'})
    for row in op['analysis']['work_delta']: row['quantity']['fact_ids'] = [fact]
    for row in op['analysis']['coverage'] + op['analysis']['residuals']: row['fact_ids'] = [fact]
    for row in op['analysis']['tradeoffs']: row['change']['fact_ids'] = [fact]
    s = selected_scheme(d)
    s['goal'] = '在同一输出所有权下共同调整搬入和写回，完成块搬运、计算与批量释放'
    s['reason'] = '分别减少输入搬入和输出写回发射，共同核算UB与更长存活期，整体收益待测'
    s['predictions'][0]['statement'] = '两类发射均按各自地址和完成边界减少，有效输入/输出字节及覆盖不变'
    s['predictions'][1]['statement'] = '合法的联合搬入和写回方案可能缩短整体时间，净效应包含缓冲滞留成本'
    s['members'][1].update(role='输出批量写回', rationale='搬入与写回共同调整缓冲和释放点，两个真实意图共享一份计划')
    s['steps'][1]['description'] = '输出完成后批量写回；减少写回发射但有效输出字节不变'
    for row in s['analysis']['work_accounting']:
        row['accounting'] = 'distinct'; row['explanation'] = '搬入与写回是不同工作，分别计入联合方案'
    q = s['analysis']['work_delta'][0]['quantity']
    q['expression'] = 'Nin/Bin + Nout/Bout'
    q['symbols'] = [{'name': k, 'meaning': k, 'unit': 'elements' if k.startswith('N') else 'elements/call'}
                    for k in ('Nin', 'Bin', 'Nout', 'Bout')]
    q['fact_ids'].append(fact)
    doc_ref = {'path': action['source_path'], 'sha256': action['source_hash']}
    d['knowledge_use'].append({'opportunity_ids': [op['id']], 'owner': 'diagnosis',
        'document_ref': doc_ref, 'locator': body_locator(knowledge_source(root, doc_ref)), 'effect_kind': 'applicability',
        'before': '只关注搬入合并', 'after': '纳入输出owner、释放点与额外存活期后比较批量写回',
        'applicability': '同owner且相邻输出已完成，容量与写回边界合法'})
    persist_reasoning(d, chain, task)
    return instance, op


def test_distinct_registered_actions_share_scheme_but_not_policies(sample):
    d, chain, task, artifact = sample[3], sample[4], sample[2], sample[1]
    instance, op = add_distinct_action(d, chain, task, artifact, root=sample[0])
    result = check(sample, True)
    assert len({o['action_id'] for o in d['opportunities']}) == 2
    assert len(result['member_readiness']) == 2
    # 首成员的两项策略不能冒充写回Action仅有的一项性能政策。
    original = deepcopy(op['performance_hypotheses'])
    op['performance_hypotheses'] = deepcopy(d['opportunities'][0]['performance_hypotheses'])
    with pytest.raises(GraphError): check(sample)
    op['performance_hypotheses'] = original
    # 首成员不要求output_ownership，不能用其ready状态授权第二成员。
    del instance['evidence_bindings']['constraint.output_ownership']
    persist_reasoning(d, chain, task)
    with pytest.raises(GraphError): check(sample, True)


def test_shared_work_cannot_be_numerically_double_counted(sample):
    d = sample[3]; add_member(d, sample[4], sample[2]); s = selected_scheme(d)
    for op in d['opportunities']:
        op['analysis']['work_delta'][0]['quantity'].update(mode='exact', value=3, expression='3', symbols=[])
    q = s['analysis']['work_delta'][0]['quantity']
    q.update(mode='exact', value=6, expression='6', symbols=[])
    with pytest.raises(GraphError, match='共享工作'): check(sample)
    q.update(value=3, expression='3')
    assert check(sample)['status'] == 'ready'


def test_real_parameter_change_can_retest_same_prediction_but_renaming_cannot(sample):
    root, artifact, task, d, chain = sample
    nxt = successor(d, task, 'r1.json')
    nxt['previous_feedback']['reassessment']['next_step'].update(kind='retune', return_to='C2', discriminating_prediction_ids=['time'])
    data = (root, artifact, task, nxt, chain)
    with pytest.raises(GraphError, match='继续须有'): check(data)
    newer = deepcopy(chain[0]['reasoning'])
    old_id = newer['action_instances'][0]['instance_id']
    newer['action_instances'][0]['instance_id'] = old_id + '.renamed'
    selected_scheme(nxt)['members'][0]['action_instance_id'] = old_id + '.renamed'
    selected_scheme(nxt)['steps'][0]['action_instance_ids'] = [old_id + '.renamed']
    nxt['opportunities'][0]['action_instance_id'] = old_id + '.renamed'
    nxt['reasoning_ref'] = write_json(task / 'reasoning-r2-renamed.json', newer)
    nxt['reasoning_hash'] = content_hash(newer)
    with pytest.raises(GraphError, match='继续须有'): check(data)
    newer['action_instances'][0]['parameters']['tile'] = 128
    nxt['reasoning_ref'] = write_json(task / 'reasoning-r2-retuned.json', newer)
    nxt['reasoning_hash'] = content_hash(newer)
    assert check(data)['status'] == 'conditional'


def test_round_three_can_return_to_bound_ancestor_parent_with_exact_lineage(sample):
    import json
    from aprof_runtime.jsonio import file_hash
    root, artifact, task, d, chain = sample
    original_reasoning = deepcopy(chain[0]['reasoning'])
    r2 = successor(d, task, 'history-r1.json')
    historical_ref = deepcopy(r2['previous_feedback']['previous_decision_ref'])
    path = task / 'exploration-r1.cpp'; path.write_text('CPU paper exploration parent\n')
    parent = {'path': path.name, 'sha256': file_hash(path)}
    newer = deepcopy(original_reasoning)
    newer['current']['implementation_ref'] = parent
    newer['current']['scope']['parent_implementation_hash'] = parent['sha256']
    for row in list(newer['facts'].values()) + newer['candidates'] + newer['action_instances']:
        row['scope']['parent_implementation_hash'] = parent['sha256']
    r2['reasoning_ref'] = write_json(task / 'history-reasoning-r2.json', newer)
    r2['reasoning_hash'] = content_hash(newer); r2['current_parent_ref'] = parent
    f = r2['previous_feedback']; f['current_parent_ref'] = deepcopy(parent)
    attempt = f['reassessment']['attempt']
    attempt['implementation_ref'] = parent
    attempt['change_ref'] = write_json(task / 'history-change-r1.json', {'task_id': d['task_id'], 'kind': 'CPU_fixture', 'change': 'paper exploration'})
    identity = {'parent_implementation_hash': attempt['parent_ref']['sha256'], 'implementation_hash': parent['sha256'], 'workload_hash': attempt['workload_ref']['sha256']}
    receipt = write_json(task / 'history-correctness-r1.json', {'task_id': d['task_id'], 'attempt_identity': identity, 'kind': 'CPU_fixture_only'})
    f['reassessment']['structure'].update(state='realized', evidence_refs=[receipt], finding='CPU合同夹具结构，不表示真实NPU实现')
    f['reassessment']['correctness'].update(state='passed', evidence_refs=[receipt], finding='CPU合同夹具正确性状态，不表示硬件oracle')
    assert check((root, artifact, task, r2, chain))['status'] == 'conditional'
    r3 = successor(r2, task, 'history-r2.json')
    r3['current_parent_ref'] = deepcopy(d['current_parent_ref'])
    r3['previous_feedback']['current_parent_ref'] = deepcopy(d['current_parent_ref'])
    r3['reasoning_ref'] = write_json(task / 'history-reasoning-r3.json', original_reasoning)
    r3['reasoning_hash'] = content_hash(original_reasoning)
    data = (root, artifact, task, r3, chain)
    with pytest.raises(GraphError, match='parent_history_ref'): check(data)
    r3['previous_feedback']['parent_history_ref'] = historical_ref
    assert check(data)['status'] == 'conditional'
    # 同task有效文件仍不等于当前线性祖先。
    side = write_json(task / 'history-side-branch.json', json.loads((task / historical_ref['path']).read_text()))
    r3['previous_feedback']['parent_history_ref'] = side
    with pytest.raises(GraphError, match='旁支'): check(data)
    r3['previous_feedback']['parent_history_ref'] = dict(historical_ref, sha256='sha256:' + '0' * 64)
    with pytest.raises(GraphError, match='hash'): check(data)
    # 篡改为另一个workload的完整有效JSON链同样不得借用。
    wrong_workload = write_json(task / 'history-other-workload.json', {'shape': [7], 'dtype': 'float32'})
    wrong_r1 = json.loads((task / historical_ref['path']).read_text())
    wrong_r1['path_overview']['workload_ref'] = wrong_workload
    wrong_ref = write_json(task / 'history-wrong-r1.json', wrong_r1)
    wrong_r2 = deepcopy(r2); wrong_r2['previous_feedback']['previous_decision_ref'] = wrong_ref
    r3['previous_feedback']['previous_decision_ref'] = write_json(task / 'history-wrong-r2.json', wrong_r2)
    r3['previous_feedback']['parent_history_ref'] = wrong_ref
    with pytest.raises(GraphError, match='不同 workload'): check(data)
