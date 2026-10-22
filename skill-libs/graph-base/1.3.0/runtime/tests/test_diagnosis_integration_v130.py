"""真实202条知识包与隔离目录演练；fixture全为CPU合成声明，不是实测案例。"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from aprof_runtime import bindings, diagnosis
from aprof_runtime.diagnosis_reasoning import validate_case, validate_proposal
from aprof_runtime.jsonio import content_hash
from test_action_decision import attach, make_decision
from test_action_decision_v2 import v2_fields
from test_action_handoff_v3 import write_json

ROOT = Path(__file__).resolve().parents[2]


def test_profile_retrieval_requires_explicit_time_basis():
    artifact = diagnosis.verify(ROOT)
    symptom = next(r for r in artifact['records'] if r['kind'] == 'symptom' and r['view'] == 'profile')
    keys = [c['id'] for c in symptom['observation']['required_components']] or [symptom['id']]
    context = {'schema_version': 'aprof.evidence/v1', 'task_id': 'paper-time',
        'source_context_ref': {'path': 'context.json', 'sha256': content_hash({'paper': True})},
        'attributes': {}, 'facts': {key: {'state': True, 'kind': 'raw', 'evidence_id': key,
            'ref': {'path': 'paper-capture.json', 'sha256': content_hash({'paper': True}), 'locator': key}}
            for key in keys}}
    def state():
        return next(r['state'] for r in diagnosis.retrieve(artifact, context, ROOT)['observations']
                    if r['id'] == symptom['id'])
    assert state() == 'unknown'
    for fact in context['facts'].values():
        fact['time_range'] = {'kind': 'full_artifact', 'aggregation': 'all_recorded_samples'}
    assert state() is True
    context['facts'][keys[0]]['time_range'] = {'kind': 'interval', 'start': 2, 'end': 1,
                                             'unit': 'ns', 'origin': 'synthetic capture'}
    assert state() == 'unknown'


def test_real_templates_route_and_cli_handoff(tmp_path):
    artifact = diagnosis.verify(ROOT)
    assert len(artifact['records']) == 202
    decision, chain = make_decision(ROOT, artifact, tmp_path / 'task', workload={'cases': [{'case_id': 'singleton', 'workload': {'shape': [64], 'dtype': 'float32', 'layout': 'ND'}}]})
    decision = v2_fields(decision, chain[0]['reasoning'])
    attach(decision, chain, tmp_path / 'task')
    result = bindings.validate_chain(ROOT, *chain, task_root=tmp_path / 'task')
    assert result['status'] == 'implemented'
    assert 'optimization' not in chain[1]['selection']
    assert result['actual_combination']['optimization_snapshots'][0]['body']
    for index, record in enumerate(chain, 1):
        write_json(tmp_path / f'C{index}.json', record)
    command = [str(ROOT / 'tools/aprofctl'), 'knowledge', 'validate-chain', '--root', str(ROOT),
               '--task-root', str(tmp_path / 'task')]
    for index in (1, 2, 3):
        command += [f'--c{index}', str(tmp_path / f'C{index}.json')]
    replay = subprocess.run(command, text=True, capture_output=True)
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert json.loads(replay.stdout)['result']['status'] == 'implemented'
    # 三类材料分开；纸面输入和pending意图不能伪装成经过实验支持的模板。
    skill = ROOT / 'skills/ascendc-aprof-diagnosis'
    for path in (skill / 'examples').glob('*.json'):
        assert validate_case(ROOT, json.loads(path.read_text()))['outcome']['status'] == 'not_run'
    for path in (skill / 'proposals').glob('*.json'):
        assert not validate_proposal(ROOT, json.loads(path.read_text()))['promotion']['eligible']


def test_v7_package_relocates_and_replays_without_checkout_network_or_scratch(tmp_path):
    package = tmp_path / 'retained-package'
    shutil.copytree(ROOT, package, ignore=shutil.ignore_patterns(
        '__pycache__', '.pytest_cache', '.runtime-env', '*.egg-info'))
    artifact = diagnosis.verify(package)
    decision, chain = make_decision(package, artifact, package / 'task', workload={'cases': [{'case_id': 'singleton', 'workload': {'shape': [64], 'dtype': 'float32', 'layout': 'ND'}}]})
    decision = v2_fields(decision, chain[0]['reasoning'])
    attach(decision, chain, package / 'task')
    for index, record in enumerate(chain, 1):
        write_json(package / f'C{index}.json', record)
    script = r'''
import json, os, sys
from pathlib import Path
root = Path(sys.argv[1]).resolve()
blocked = [Path(p).resolve() for p in sys.argv[2:]]
def isolated(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('offline package forbids network')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        path = Path(os.fsdecode(args[0])).resolve()
        if any(path.is_relative_to(parent) for parent in blocked):
            raise RuntimeError('external package dependency: ' + str(path))
sys.addaudithook(isolated)
sys.path.insert(0, str(root / 'runtime/src'))
from aprof_runtime import __version__, bindings, diagnosis
from aprof_runtime.graph import load_snapshot
from aprof_runtime.knowledge import verify as verify_tree
from aprof_runtime.diagnosis_reasoning import validate_case, validate_proposal
assert __version__ == '0.8.1'
assert diagnosis.verify(root)['version'] == 'v0007'
for owner, version in (('parallel-planning', 'v0004'), ('optimization', 'v0007')):
    assert verify_tree(root, owner)['version'] == version
for version in ('v0003', 'v0004', 'v0005', 'v0006'):
    old, _ = load_snapshot(root / 'skills/ascendc-aprof-diagnosis/graph/versions' / version)
    assert old['version'] == version
chain = [json.loads((root / f'C{i}.json').read_text()) for i in (1, 2, 3)]
assert bindings.validate_chain(root, *chain, task_root=root / 'task')['status'] == 'implemented'
skill = root / 'skills/ascendc-aprof-diagnosis'
for path in (skill / 'examples').glob('*.json'):
    validate_case(root, json.loads(path.read_text()))
for path in (skill / 'proposals').glob('*.json'):
    validate_proposal(root, json.loads(path.read_text()))
sys.path.insert(0, str(root / 'tools'))
from release import verify_unsealed
assert verify_unsealed(root)['publication_accepted'] is False
print(json.dumps({'standalone': True, 'network': False, 'original_tree': False,
                  'hardware': False, 'timing': False, 'causal_claim': False}))
'''
    # -I忽略宿主PYTHONPATH；只显式加载保留目录内runtime。
    replay = subprocess.run([sys.executable, '-I', '-c', script, str(package), str(ROOT),
        '/tmp/aprof-diagnosis-v4-exy42mhk', '/tmp/aprof-knowledge-sources-1SHAlx',
        *([os.environ['APROF_TEST_SOURCE_REPO']] if os.environ.get('APROF_TEST_SOURCE_REPO') else [])],
        cwd=package, text=True, capture_output=True)
    assert replay.returncode == 0, replay.stdout + replay.stderr
    assert json.loads(replay.stdout)['standalone']
