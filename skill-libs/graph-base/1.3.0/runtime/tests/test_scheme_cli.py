"""公开命令的显式版本分派；合成 C5 数值仅检验结构，不代表硬件结果。"""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from aprof_runtime import bindings
from aprof_runtime.errors import GraphError
from aprof_runtime.jsonio import content_hash
from aprof_runtime.knowledge_outcome import link_result_v3
from test_action_decision import attach, make_decision
from test_action_decision_v2 import v2_fields
from test_action_handoff_v3 import write_json
from test_action_handoff_v4 import synthetic_timing
from test_action_decision_v3 import scheme_package as _scheme_package_fixture

scheme_package = _scheme_package_fixture

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / 'workflows/references/optimization-schemes-1.3.0/examples'


@pytest.fixture
def example(tmp_path):
    task = tmp_path / 'task'
    shutil.copytree(EXAMPLES / 'multiple', task)
    chain = [json.loads((task / f'C{i}.json').read_text()) for i in (1, 2, 3)]
    return task, chain


def invoke(*args):
    return subprocess.run([str(ROOT / 'tools/aprofctl'), *args], text=True, capture_output=True)


def test_v4_chain_and_v3_decision_public_commands(example):
    task, chain = example
    replay = invoke('knowledge', 'validate-chain', '--root', str(ROOT), '--task-root', str(task),
                    '--c1', str(task / 'C1.json'), '--c2', str(task / 'C2.json'), '--c3', str(task / 'C3.json'))
    assert replay.returncode == 0, replay.stderr
    value = json.loads(replay.stdout)['result']
    assert value['status'] == 'implemented' and len(value['member_instance_ids']) == 2
    replay = invoke('contract', 'validate', '--kind', 'action-decision-v3', '--root', str(ROOT),
                    '--task-root', str(task), '--input', str(task / chain[0]['decision_ref']['path']))
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)['result']['valid'] is True


def test_public_result_link_records_every_actual_action_and_document(example):
    task, chain = example
    _, _, timing = synthetic_timing(task, chain)
    write_json(task / 'timing-ref.json', timing)
    replay = invoke('knowledge', 'link-result', '--root', str(ROOT), '--task-root', str(task),
                    '--c1', str(task / 'C1.json'), '--c2', str(task / 'C2.json'), '--c3', str(task / 'C3.json'),
                    '--timing-ref', str(task / 'timing-ref.json'))
    assert replay.returncode == 0, replay.stderr
    result = json.loads(replay.stdout)['result']
    assert len(set(result['executed_actions'])) == 2
    assert all(m['optimization_snapshots'] for m in result['actual_combination']['members'])
    assert result['causal_claim'] is False and result['legacy_episode_eligible'] is False


def test_public_chain_rejects_mixed_versions(example):
    task, chain = example
    chain[2]['schema_version'] = 'aprof.handoff/v3'
    write_json(task / 'C3.json', chain[2])
    replay = invoke('knowledge', 'validate-chain', '--root', str(ROOT), '--task-root', str(task),
                    '--c1', str(task / 'C1.json'), '--c2', str(task / 'C2.json'), '--c3', str(task / 'C3.json'))
    assert replay.returncode == 2
    assert '版本' in json.loads(replay.stderr)['error']


@pytest.mark.parametrize('mutation', ['missing', 'tampered'])
def test_handoff_bundle_rejects_missing_or_changed_frozen_routing(example, tmp_path, mutation):
    task, chain = example
    isolated = tmp_path / 'isolated-package'
    shutil.copytree(ROOT / 'schemas', isolated / 'schemas')
    config_hash = chain[1]['selection']['routing_config_hash']
    name = f"{bindings.ROUTING_SNAPSHOTS}/{config_hash.removeprefix('sha256:')}.json"
    if mutation == 'tampered':
        value = json.loads((ROOT / name).read_text())
        value['version'] = 'v9999'
        target = isolated / name
        target.parent.mkdir(parents=True)
        write_json(target, value)
    with pytest.raises(GraphError, match='快照缺失' if mutation == 'missing' else '内容地址'):
        bindings.load_handoff_bundle(isolated, chain[1])


def test_old_v3_link_uses_frozen_bundle_and_bound_sources(scheme_package, tmp_path):
    task = tmp_path / 'legacy'
    root, artifact = scheme_package
    assert artifact['version'] == 'v0006'
    decision, chain = make_decision(root, artifact, task)
    decision = v2_fields(decision, chain[0]['reasoning'])
    attach(decision, chain, task)
    request, measured, timing = synthetic_timing(task, chain)
    result = link_result_v3(root, *chain, timing, task_root=task, timing_ref=task / 'timing-ref.json')
    assert result['schema_version'] == 'aprof.knowledge-outcome/v2'
    assert result['executed_instances'] == chain[2]['execution']['executed_instances']
    assert result['actual_combination']['optimization_snapshots'][0]['body']
    # 同一源码清单可含多个算子；匹配source/candidate不允许跨operator关联。
    for request_operator, result_operator in [('other_operator', 'other_operator'), ('paper', 'other_operator')]:
        wrong_request, wrong_measured = deepcopy(request), deepcopy(measured)
        wrong_request['operator'] = request_operator
        wrong_measured['operator'] = result_operator
        wrong_measured['request'] = write_json(task / 'request-wrong-operator.json', wrong_request)
        wrong_measured['decision_hash'] = content_hash(
            {key: value for key, value in wrong_measured.items() if key != 'decision_hash'})
        wrong_timing = dict(write_json(task / 'timing-wrong-operator.json', wrong_measured),
                            candidate_id=timing['candidate_id'], protocol=timing['protocol'])
        with pytest.raises(GraphError, match='算子不同'):
            link_result_v3(root, *chain, wrong_timing, task_root=task, timing_ref=task / 'timing-ref.json')
    measured['speedup'] = 7
    timing.update(write_json(task / 'timing.json', measured))
    with pytest.raises(GraphError, match='decision_hash'):
        link_result_v3(root, *chain, timing, task_root=task, timing_ref=task / 'timing-ref.json')
