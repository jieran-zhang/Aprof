"""D7 测前完整映射、D6 回放及真实 v4 实施边界；全部为 CPU 合同测试。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from aprof_runtime import action_decision, bindings, diagnosis
from aprof_runtime.action_decision_v2 import workload_case_payloads
from aprof_runtime.errors import GraphError
from test_action_decision import persist_reasoning
from test_action_decision_v3 import (
    ROOT, make_v3_decision, selected_scheme,
    test_compound_feedback_support_and_regression_are_scoped_not_single_factor as check_measured_feedback,
)
from test_action_handoff_v3 import write_json
from test_action_handoff_v4 import real_chain, rebind


@pytest.fixture(scope='module')
def new_package(tmp_path_factory):
    root = tmp_path_factory.mktemp('d7-mapping-package') / 'package'
    shutil.copytree(ROOT, root, ignore=shutil.ignore_patterns('__pycache__', '.pytest_cache'))
    config = bindings.load_routing(root)
    artifacts, _ = bindings.load_frozen_bundle(root, bindings.routing_snapshot_ref(root, config))
    artifact = artifacts['diagnosis']
    assert artifact['version'] >= 'v0007', '新映射测试必须使用真实 D7 发布包，不能把 D6 改名'
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


@pytest.fixture
def new_sample(new_package, tmp_path):
    root, artifact = new_package
    task = tmp_path / 'task'
    decision, chain = make_v3_decision(root, artifact, task)
    return root, artifact, task, decision, chain


def check(sample, implementation=False):
    root, _, task, decision, _ = sample
    return action_decision.validate_decision(root, decision, task_root=task, implementation=implementation)


def freeze_workload(sample, value):
    _, _, task, decision, chain = sample
    ref = write_json(task / 'workload.json', value)
    reasoning = chain[0]['reasoning']
    reasoning['current']['workload_ref'] = deepcopy(ref)
    reasoning['current']['scope']['workload_hash'] = ref['sha256']
    for row in list(reasoning['facts'].values()) + reasoning['candidates'] + reasoning['action_instances']:
        row['scope']['workload_hash'] = ref['sha256']
    decision['path_overview']['workload_ref'] = deepcopy(ref)
    persist_reasoning(decision, chain, task)


def test_bare_matrix_is_analyzable_but_cannot_authorize_implementation(new_sample):
    payload = {'shape': [64], 'dtype': 'float32', 'layout': 'ND', 'attributes': {}}
    freeze_workload(new_sample, {'cases': [dict(payload, case_id='singleton')]})
    result = check(new_sample)
    assert result['status'] == 'conditional'
    assert result['missing_workload_mapping'] == ['workload.full_case_payloads_before_selection']
    assert not result['missing_safety']  # 映射缺口不冒充性能或安全前提。
    with pytest.raises(GraphError, match='测前冻结'): check(new_sample, True)
    new_sample[3]['selection']['mode'] = 'conditional_plan'
    assert check(new_sample)['missing_workload_mapping']
    new_sample[3]['selection']['mode'] = 'collect_evidence'
    assert check(new_sample)['missing_workload_mapping'] == []
    new_sample[3]['selection'].update(mode='stop', scheme_id=None, stop_reason='范围外，保留源码分析')
    new_sample[3]['opportunities'][0]['disposition'] = 'deferred'
    assert check(new_sample)['missing_workload_mapping'] == []


def test_canonical_payload_is_ready_in_first_round_and_remains_frozen(new_sample):
    payload = {'shape': [64], 'dtype': 'float32', 'layout': 'ND', 'attributes': {}}
    freeze_workload(new_sample, {'cases': [{'case_id': 'singleton', 'workload': payload}]})
    assert workload_case_payloads({'cases': [{'case_id': 'singleton', 'workload': payload}]}) == {'singleton': payload}
    assert check(new_sample, True)['status'] == 'ready'
    assert check(new_sample)['missing_workload_mapping'] == []
    # 修改冻结文件字节而不更改引用，不能事后补填成为原选择的映射。
    task = new_sample[2]
    (task / 'workload.json').write_text(json.dumps({'cases': [{'case_id': 'singleton', 'workload': dict(payload, shape=[128])}]}))
    with pytest.raises(GraphError, match='hash'): check(new_sample)


@pytest.mark.parametrize('value', [
    {'cases': []},
    {'cases': [{'case_id': 'singleton', 'workload': {}}]},
    {'cases': [{'case_id': 'singleton', 'workload': None}]},
    {'cases': [{'case_id': 'singleton', 'workload': {}}, {'case_id': 'singleton', 'workload': {}}]},
    {'cases': [{'case_id': 'singleton', 'workload': 'not-a-payload'}]},
    {'case_ids': ['singleton'], 'cases': [{'case_id': 'other', 'workload': {}}]},
    {'cases': [{'case_id': 'singleton', 'workload': {}}, {'case_id': 'other'}]},
])
def test_malformed_mapping_is_rejected_by_real_decision(new_sample, value):
    freeze_workload(new_sample, value)
    mixed = len(value['cases']) == 2 and 'workload' not in value['cases'][1]
    if mixed:
        decision = new_sample[3]
        decision['path_overview']['case_ids'] = ['singleton', 'other']
        decision['path_overview']['domains'][0]['case_ids'] = ['singleton', 'other']
        for opportunity in decision['opportunities']: opportunity['case_ids'] = ['singleton', 'other']
    with pytest.raises(GraphError, match='不可混装' if mixed else None): check(new_sample)


@pytest.mark.parametrize('wrong_payload', [False, True])
def test_first_and_effective_feedback_consume_same_full_payload(new_sample, wrong_payload):
    check_measured_feedback(new_sample, 80, 'supported', wrong_payload)


def test_real_v4_chain_propagates_mapping_gap_and_refuses_c3(new_package, tmp_path):
    root, artifact = new_package
    task = tmp_path / 'bare-chain'
    decision, chain = real_chain(root, artifact, task, multiple=True)
    result = bindings.validate_chain(root, *chain[:2], task_root=task)
    assert result['status'] == 'conditional'
    assert 'workload.full_case_payloads_before_selection' in result['missing']
    with pytest.raises(GraphError, match='测前冻结'):
        bindings.validate_chain(root, *chain, task_root=task)


@pytest.mark.parametrize('bad_id', [None, '', 'unselected.scheme', 'omitted'])
def test_real_v4_chain_and_direct_handoff_reject_invalid_scheme_identity(new_package, tmp_path, bad_id):
    root, artifact = new_package
    task = tmp_path / 'scheme-identity'
    decision, chain = real_chain(root, artifact, task, multiple=False)
    c1 = chain[0]
    if bad_id == 'omitted': c1.pop('scheme_id')
    else: c1['scheme_id'] = bad_id
    rebind(chain)
    instance_ids = [m['action_instance_id'] for m in selected_scheme(decision)['members']]
    with pytest.raises(GraphError):
        action_decision.validate_handoff_decision(root, c1, instance_ids, task_root=task, artifact=artifact, implementation=False)
    with pytest.raises(GraphError): bindings.validate_chain(root, *chain, task_root=task)


def test_v3_decision_cannot_be_replayed_in_v3_handoff(new_sample):
    root, artifact, task, decision, chain = new_sample
    c1 = chain[0]
    c1['artifacts'] = [write_json(task / 'decision.json', decision)]
    with pytest.raises(GraphError, match='旧 handoff/v3'):
        action_decision.validate_handoff_decision(root, c1, decision['opportunities'][0]['action_instance_id'],
            task_root=task, artifact=artifact, implementation=False)


def test_d7_single_opportunity_contract_cannot_bypass_mapping_gate(new_sample):
    decision = new_sample[3]
    decision['schema_version'] = 'aprof.action-decision/v2'
    decision.pop('schemes')
    opportunity = decision['opportunities'][0]
    decision['selection'].pop('scheme_id')
    decision['selection'].update(opportunity_id=opportunity['id'], action_instance_id=opportunity['action_instance_id'])
    for basis in decision['selection']['comparison_basis']:
        basis.pop('scheme_id'); basis['opportunity_id'] = opportunity['id']
    assert check(new_sample)['missing_workload_mapping']
    with pytest.raises(GraphError, match='测前冻结'): check(new_sample, True)
    freeze_workload(new_sample, {'cases': [{'case_id': 'singleton', 'workload': {'shape': [64], 'dtype': 'float32'}}]})
    assert check(new_sample, True)['status'] == 'ready'
