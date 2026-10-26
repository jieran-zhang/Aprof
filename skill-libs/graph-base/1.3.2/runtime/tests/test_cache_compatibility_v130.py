"""L2 方法兼容门禁：保留旧路由标签和冻结快照，不进行性能推断。"""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from aprof_runtime import bindings
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.knowledge import route_tree

ROOT = Path(__file__).resolve().parents[2]
L2 = 'implementation.memory-transfer.l2-reuse-order'
UB = 'implementation.memory-transfer.input-tile-residency'
CACHE = 'constraint.l2_cache_enabled'
ACTION = 'action.reuse_input_tiles'
# 来自一个明确的双消费者纸面程序，不遍历路由条件自动补 true。
METHOD_FACTS = {
    'constraint.semantic_equivalence': '原 x 保持只读；两个独立输出保持原数值调用及舍入。',
    'constraint.capacity': '假设256KiB UB；独立物理槽合计192KiB，另无scratch或别名。',
    'constraint.plan_freedom': '已确认纸面计划允许本地搬运顺序与生命周期调整。',
    'constraint.output_ownership': '两输出每片仍由原 owner 写入，无跨核归并。',
    'constraint.dependency_lifetime': '载入完成后读取，最后异步消费者完成后再覆盖。',
    'constraint.reuse_domain': '两个消费者都属于当前 owner，重复读原 x 的同一片。',
    'constraint.same_input_region': 'FP32、stride=1、base与有效长度完全相同。',
    'constraint.input_value_preserved': '消费者均写独立输出，xUb到最后消费者完成前不改写。',
}


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    return {'path': path.name, 'sha256': file_hash(path)}


@pytest.fixture(scope='module')
def bundle():
    config = json.loads((ROOT / bindings.CONFIG).read_text())
    return bindings.load_frozen_bundle(ROOT, bindings.routing_snapshot_ref(ROOT, config))


def context(tmp_path, state='absent'):
    values = {key: True for key in METHOD_FACTS}
    if state != 'absent':
        values[CACHE] = state
    ref = dump(tmp_path / 'method-review.json', {
        'synthetic_only': True, 'review': METHOD_FACTS, 'states': values,
        'cache_review': 'NORMAL=true，DISABLE=false；未核对的路径为unknown。'})
    return {'schema_version': 'aprof.evidence/v1', 'task_id': 'cache-paper',
        'source_context_ref': ref,
        'attributes': {'platform': 'dav-2201', 'family': ['elementwise'],
                       'dtype': 'float32', 'features': ['memory-transfer']},
        'facts': {key: {'state': value, 'kind': 'source_review', 'evidence_id': key,
                        'ref': {**ref, 'locator': 'states.' + key}}
                  for key, value in values.items()}}


def trace(bundle, ctx):
    artifacts, config = bundle
    row = next(r for r in config['actions'] if r['action_id'] == ACTION)
    return bindings.route_candidates(artifacts['optimization'], ctx,
                                     row['optimization_subtrees'])


@pytest.mark.parametrize('state,ready', [(True, True), (False, False), ('unknown', False), ('absent', False)])
def test_l2_cache_gate_applies_to_generic_and_action_routing(bundle, tmp_path, state, ready):
    artifacts, _ = bundle
    ctx = context(tmp_path, state)
    for result in (route_tree(artifacts['optimization'], ctx), trace(bundle, ctx)):
        match = next(m for m in result['matches'] if m['id'] == L2)
        assert (match['status'] == 'reference_ready') is ready
        assert (CACHE in match['missing']) is not ready
        assert next(m for m in result['matches'] if m['id'] == UB)['status'] == 'reference_ready'


@pytest.mark.parametrize('state', [False, 'unknown', 'absent'])
def test_c3_cannot_select_l2_when_compatibility_is_not_true(bundle, tmp_path, state):
    artifacts, _ = bundle
    result = trace(bundle, context(tmp_path, state))
    nodes = {r['id']: r for r in artifacts['optimization']['records']}
    # 此函数由 validate_chain 在C3的实际O选择处以hard=True调用。
    with pytest.raises(GraphError, match='C3 recipe/plan 所需证据未知.*l2_cache_enabled'):
        bindings._chosen(result, [L2], 'CHANGE', nodes, hard=True)
    assert bindings._chosen(result, [UB], 'CHANGE', nodes, hard=True) == []


def reasoning_for_two_inputs(tmp_path, artifact):
    """两个同Action实例；仅缓存证据已知，原Action其他硬前提显式保持unknown。"""
    parent = tmp_path / 'parent.cpp'
    parent.write_text('// synthetic only: x uses NORMAL; y uses DISABLE\n')
    parent_ref = {'path': parent.name, 'sha256': file_hash(parent)}
    workload_ref = dump(tmp_path / 'workload.json', {'shape': [128], 'dtype': 'float32'})
    raw_ref = dump(tmp_path / 'cache-config.json', {'tensor.x': {'mode': 'NORMAL'}, 'tensor.y': {'mode': 'DISABLE'}})
    attrs = {'platform': 'dav-2201', 'family': ['elementwise'], 'dtype': 'float32', 'features': ['memory-transfer']}
    authority = {'schema_version': 'aprof.evidence/v1', 'task_id': 'cache-paper',
                 'source_context_ref': raw_ref, 'attributes': attrs, 'facts': {}}
    authority_ref = dump(tmp_path / 'context-authority.json', authority)
    snapshot = {**authority, 'source_context_ref': authority_ref}
    scope = {'task_id': 'cache-paper', 'parent_implementation_hash': parent_ref['sha256'],
             'workload_hash': workload_ref['sha256'], 'target_ids': ['tensor.x', 'tensor.y'], 'stage': 'kernel.main'}
    objects = [{'object_id': t, 'kind': 'tensor', 'description': '两个输入分别核对缓存路径'} for t in scope['target_ids']]
    roles = {'stage': 'kernel.main', 'workload': 'workload.current', 'implementation': 'implementation.current'}
    objects += [{'object_id': value, 'kind': key, 'description': '当前纸面范围'} for key, value in roles.items()]
    action = next(r for r in artifact['records'] if r['id'] == ACTION)
    facts, candidates, instances = {}, [], []
    for target, state in [('tensor.x', True), ('tensor.y', False)]:
        local_scope = {**scope, 'target_ids': [target]}
        fact_id = target + '.cache'
        facts[fact_id] = {'state': state, 'kind': 'raw', 'predicate': CACHE,
            'evidence_id': fact_id, 'ref': {**raw_ref, 'locator': target + '.mode'},
            'derived_from': [], 'scope': local_scope}
        hypothesis = 'temporary.' + target
        candidates.append({'hypothesis_id': hypothesis, 'problem_id': None,
            'mechanism': '待分析重复输入读取', 'targets': [target], 'scope': local_scope,
            'support': [], 'counter': [], 'unknown': [], 'alternatives': [], 'checks': ['补原Action证据'],
            'status': 'plausible', 'reason': '仅检查缓存隔离，未断言机制成立',
            'excluded_by': [], 'independent_evidence_groups': []})
        targets = {slot['name']: roles.get(slot['kind'], target) for slot in action['slots'] if slot['required']}
        instances.append({'instance_id': 'instance.' + target, 'action_id': ACTION,
            'template_hash': content_hash(action), 'hypothesis_id': hypothesis, 'targets': targets,
            'scope': local_scope, 'parameters': {}, 'evidence_bindings': {},
            'unknowns': [p['fact'] for p in action['preconditions']], 'status': 'conditional',
            'reason': '未补齐硬前提；只做范围投影测试', 'parent_plan_hash': None})
    return {'schema_version': 'aprof.diagnosis-reasoning/v1', 'task_id': 'cache-paper',
        'context_hash': content_hash(snapshot), 'knowledge_hash': content_hash(artifact),
        'source_context_ref': authority_ref, 'context_snapshot': snapshot,
        'current': {'implementation_ref': parent_ref, 'workload_ref': workload_ref, 'scope': scope, 'objects': objects},
        'facts': facts, 'candidates': candidates, 'action_instances': instances, 'predecessor_ref': None}


def test_same_action_instances_do_not_borrow_other_input_cache_evidence(bundle, tmp_path):
    artifact = bundle[0]['diagnosis']
    reasoning = reasoning_for_two_inputs(tmp_path, artifact)
    contexts = [bindings.routing_context(ROOT, reasoning, instance, task_root=tmp_path, artifact=artifact)
                for instance in reasoning['action_instances']]
    assert contexts[0]['facts'][CACHE]['state'] is True
    assert contexts[1]['facts'][CACHE]['state'] is False
    # 明确借另一输入的绑定也必须拒绝，不能靠同Action名称授权。
    bad = deepcopy(reasoning)
    bad['action_instances'][1]['evidence_bindings'][CACHE] = 'tensor.x.cache'
    with pytest.raises(GraphError, match='跨目标借用'):
        bindings.routing_context(ROOT, bad, bad['action_instances'][1], task_root=tmp_path, artifact=artifact)


def test_routing_hint_cannot_supply_cache_fact(bundle):
    artifacts, config = bundle
    row = next(r for r in config['actions'] if r['action_id'] == ACTION)
    hint = {'parallel-planning': row['planning_subtrees'], 'optimization': row['optimization_subtrees'],
            'facts': {CACHE: True}}
    with pytest.raises(GraphError, match='不能含 facts 或 attributes'):
        bindings._hint(config, {'action_id': ACTION}, hint)


def test_frozen_v3_replays_original_gate_instead_of_latest(bundle, tmp_path):
    old = next(json.loads(p.read_text()) for p in (ROOT / bindings.ROUTING_SNAPSHOTS).glob('*.json')
               if json.loads(p.read_text())['bases']['optimization']['version'] == 'v0003')
    artifacts, _ = bindings.load_frozen_bundle(ROOT, bindings.routing_snapshot_ref(ROOT, old))
    old_result = route_tree(artifacts['optimization'], context(tmp_path, False))
    old_l2 = next(m for m in old_result['matches'] if m['id'] == L2)
    assert old_l2['status'] == 'reference_ready'
    # 这是历史v3语义保留，不是用旧资料授权当前v4交接。
    assert CACHE not in old_l2['missing']
    current = next(m for m in trace(bundle, context(tmp_path, False))['matches'] if m['id'] == L2)
    assert current['status'] == 'needs_evidence'
