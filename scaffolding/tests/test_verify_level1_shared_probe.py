"""Scoped, CPU-only tests for the sealed shared hardware identity exception."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
from verify_level1_campaign import CampaignVerifier, ReadOnlyStore
from aprof_runtime.errors import StoreError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


def fingerprint(run):
    return {str(path.relative_to(run)): (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in run.rglob('*') if path.is_file()}


def build_probe(tmp_path, mutate=lambda state: None):
    run = tmp_path / 'run'
    directory = run / 'tasks/exp/executions/device-probe-local'
    output = {'attributes': {
        name: {'attribute_id': number, 'source': 'aclrtGetDeviceInfo', 'status_code': 0, 'value': value}
        for name, number, value in [('ai_core_count', 101, 24), ('cube_core_count', 102, 24),
                                   ('vector_core_count', 201, 48), ('ub_bytes_per_vector_core', 204, 0)]},
        'host': 'fixture-host', 'logical_device': 0, 'soc': 'Ascend910_9392', 'visible_physical_devices': '15'}
    execution = {'schema_version': '1.0.0', 'kind': 'aprof_execution_report',
        'host': 'fixture-host', 'physical_device': 15, 'status': 'passed', 'exit_code': 0,
        'started_at': '2026-09-07T15:49:50Z', 'finished_at': '2026-09-07T15:49:52Z',
        'job': {'argv': ['python3', str(ROOT / 'scaffolding/collection/scripts/probe_aprof_device.py')],
                'output_dir': str(directory), 'physical_device': 15},
        'stdout': {'path': str(directory / 'stdout.log'), 'sha256': None}}
    environment = {'hosts': [{**deepcopy(output), 'probe_execution': str(directory / 'execution.json')}]}
    record = {'path': str(directory / 'stdout.log'), 'sha256': None,
              'read_at': '2026-09-07T15:52:28+00:00', 'purpose': 'Root-authorized shared identity'}
    state = {'run': run, 'directory': directory, 'output': output, 'execution': execution,
             'environment': environment, 'record': record, 'missing': set()}
    mutate(state)
    dump(directory / 'stdout.log', output)
    digest = file_hash(directory / 'stdout.log')
    if record['sha256'] is None:
        record['sha256'] = digest.removeprefix('sha256:')
    if execution['stdout']['sha256'] is None:
        execution['stdout']['sha256'] = digest
    dump(directory / 'execution.json', execution)
    dump(run / 'environment_manifest.json', environment)
    with EpisodeStore(run / 'train/episodes.sqlite') as store:
        store.register_artifact(directory / 'stdout.log')
        execution_hash = store.register_artifact(directory / 'execution.json')
        environment_hash = store.register_artifact(run / 'environment_manifest.json')
        for op in ['exp', 'foreach_norm']:
            hardware = [{'path': str(run / 'environment_manifest.json'), 'content_hash': environment_hash}]
            if op == 'exp' and 'owner_execution' not in state['missing']:
                hardware.append({'path': str(directory / 'execution.json'), 'content_hash': execution_hash})
            if op == 'foreach_norm' and 'environment' in state['missing']:
                hardware = []
            hardware_hash = register_json_artifact(store, hardware)
            summaries, events = [], []
            for identifier in ['001', '002']:
                knowledge = [{'path': str(directory / 'stdout.log'), 'content_hash': digest, 'purpose': 'identity'}]
                if op == 'foreach_norm' and 'knowledge' in state['missing'] and identifier == '002':
                    knowledge = []
                summary = {'identity': {'candidate_id': op + '-' + identifier, 'task_id': op,
                                       'operator': op, 'split': 'train'},
                           'knowledge': {'loaded': knowledge}, 'workload': {'hardware_fingerprint': hardware_hash}}
                summary_hash = register_json_artifact(store, summary)
                summaries.append(summary)
                if not (op == 'foreach_norm' and 'summary_event' in state['missing'] and identifier == '002'):
                    events.append({'event_type': 'attempt_finished', 'candidate_id': op + '-' + identifier,
                                   'payload': {'summary_ref': summary_hash}})
            task = run / 'tasks' / op
            task.mkdir(parents=True, exist_ok=True)
            (task / 'optimization_traces.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in summaries))
            (task / 'trace_events.jsonl').write_text(''.join(json.dumps(event) + '\n' for event in events))
    dump(run / 'tasks/foreach_norm/worker_knowledge_reads.jsonl', record)
    state.update(stdout_hash=digest, execution_hash=execution_hash, environment_hash=environment_hash)
    return state


def boundary(state):
    verifier = CampaignVerifier(state['run'])
    verifier.manifest = {'validation_operators': ['gelu'], 'sentinel_case_ids': [1, 8, 14, 20],
                         'acceptance_case_ids': list(range(1, 21))}
    with ReadOnlyStore(state['run'] / 'train/episodes.sqlite') as store:
        verifier.stores['train'] = store
        return verifier.boundaries('foreach_norm')


def test_bound_shared_probe_passes_without_writes_or_claiming_prior_manifest_authorization(tmp_path):
    state = build_probe(tmp_path)
    before = fingerprint(state['run'])
    result = boundary(state)
    assert fingerprint(state['run']) == before
    [entry] = result['shared_hardware_identity_reads']
    assert entry['classification'] == 'shared_hardware_identity_only'
    assert entry['content_hash'] == state['stdout_hash']
    assert entry['execution_hash'] == state['execution_hash']
    assert entry['physical_device'] == 15
    assert 'does not assert advance' in entry['authorization_note']


@pytest.mark.parametrize('relative', [
    'tasks/exp/optimization_traces.jsonl', 'tasks/gelu/optimization_traces.jsonl',
    'tasks/exp/executions/fake-device-probe/stdout.log', 'validation/optimization_traces.jsonl'])
def test_other_results_and_unbound_probe_names_remain_forbidden(tmp_path, relative):
    state = build_probe(tmp_path)
    path = state['run'] / relative
    if not path.exists():
        dump(path, state['output'])
    state['record']['path'] = str(path)
    state['record']['sha256'] = file_hash(path)
    dump(state['run'] / 'tasks/foreach_norm/worker_knowledge_reads.jsonl', state['record'])
    with pytest.raises(StoreError, match='sealed task boundary|outcome split/store'):
        boundary(state)


@pytest.mark.parametrize('target,key,value', [
    ('execution', 'status', 'failed'), ('execution', 'exit_code', 1),
    ('execution', 'host', 'another-host'), ('execution', 'physical_device', 14),
    ('record', 'sha256', 'a' * 64), ('record', 'content_hash', 'sha256:' + 'b' * 64),
    ('record', 'read_at', '2026-09-07T15:49:51Z'), ('record', 'read_at', '2026-09-07T15:52:28'),
    ('output', 'profile_duration_ns', 123), ('output', 'logical_device', True),
    ('output', 'visible_physical_devices', '14'), ('output', 'host', 'another-host')])
def test_probe_chain_mismatches_fail_closed(tmp_path, target, key, value):
    state = build_probe(tmp_path, lambda state: state[target].__setitem__(key, value))
    with pytest.raises(StoreError, match='sealed task boundary'):
        boundary(state)


@pytest.mark.parametrize('mutation', [
    lambda state: state['execution']['job'].__setitem__('argv', ['python3', 'fake/probe_aprof_device.py']),
    lambda state: state['execution']['job'].__setitem__('argv', ['python3', str(ROOT / 'scaffolding/collection/scripts/probe_aprof_device.py'), '--extra']),
    lambda state: state['execution']['job'].__setitem__('physical_device', 14),
    lambda state: state['execution']['job'].__setitem__('output_dir', '/tmp/fake'),
    lambda state: state['execution']['stdout'].__setitem__('sha256', 'sha256:' + 'c' * 64),
    lambda state: state['execution']['stdout'].__setitem__('path', '/tmp/stdout.log'),
    lambda state: state['environment']['hosts'][0].__setitem__('host', 'another-host'),
    lambda state: state['environment']['hosts'][0].__setitem__('probe_execution', '/tmp/execution.json'),
    lambda state: state['output']['attributes']['ai_core_count'].__setitem__('performance', 100),
    lambda state: state['output']['attributes']['ai_core_count'].__setitem__('attribute_id', 201),
])
def test_execution_identity_and_closed_output_contract(tmp_path, mutation):
    state = build_probe(tmp_path, mutation)
    with pytest.raises(StoreError, match='sealed task boundary'):
        boundary(state)


@pytest.mark.parametrize('key,value', [('performance', 100), ('attribute_id', 201), ('value', 24.5)])
def test_matching_environment_cannot_authorize_nonidentity_attribute_payload(tmp_path, key, value):
    def mutation(state):
        state['output']['attributes']['ai_core_count'][key] = value
        state['environment']['hosts'][0]['attributes'] = deepcopy(state['output']['attributes'])
    state = build_probe(tmp_path, mutation)
    with pytest.raises(StoreError, match='invalid hardware attribute data'):
        boundary(state)


@pytest.mark.parametrize('missing', ['knowledge', 'environment', 'owner_execution', 'summary_event'])
def test_every_summary_and_owner_execution_digest_must_already_be_bound(tmp_path, missing):
    state = build_probe(tmp_path, lambda state: state['missing'].add(missing))
    with pytest.raises(StoreError, match='sealed task boundary'):
        boundary(state)


@pytest.mark.parametrize('name', ['stdout.log', 'execution.json', 'environment_manifest.json'])
def test_current_file_cannot_diverge_from_sealed_source(tmp_path, name):
    state = build_probe(tmp_path)
    path = state['run'] / name if name == 'environment_manifest.json' else state['directory'] / name
    path.write_text(path.read_text() + ' ')
    with pytest.raises(StoreError, match='sealed task boundary'):
        boundary(state)


@pytest.mark.parametrize('which', ['stdout_hash', 'execution_hash', 'environment_hash'])
def test_missing_cas_source_is_rejected_without_repair(tmp_path, which):
    state = build_probe(tmp_path)
    with ReadOnlyStore(state['run'] / 'train/episodes.sqlite') as store:
        path = store.object_path(state[which])
    path.unlink()
    before = fingerprint(state['run'])
    with pytest.raises(StoreError, match='CAS object is missing'):
        boundary(state)
    assert fingerprint(state['run']) == before


@pytest.mark.parametrize('which', ['stdout_hash', 'execution_hash', 'environment_hash'])
def test_corrupted_cas_source_is_rejected_without_repair(tmp_path, which):
    state = build_probe(tmp_path)
    with ReadOnlyStore(state['run'] / 'train/episodes.sqlite') as store:
        path = store.object_path(state[which])
    path.write_bytes(b'corrupted CAS object')
    before = fingerprint(state['run'])
    with pytest.raises(StoreError, match='CAS object content does not match'):
        boundary(state)
    assert fingerprint(state['run']) == before


def test_newly_registered_execution_cannot_replace_owner_sealed_execution(tmp_path):
    state = build_probe(tmp_path)
    state['execution']['started_at'] = '2026-09-07T15:49:49Z'
    dump(state['directory'] / 'execution.json', state['execution'])
    with EpisodeStore(state['run'] / 'train/episodes.sqlite') as store:
        store.register_artifact(state['directory'] / 'execution.json')
    with pytest.raises(StoreError, match='file differs from its bound digest'):
        boundary(state)


def test_symlink_cannot_alias_the_allowed_stdout(tmp_path):
    state = build_probe(tmp_path)
    alias = state['directory'] / 'alias.log'
    alias.symlink_to(state['directory'] / 'stdout.log')
    state['record']['path'] = str(alias)
    dump(state['run'] / 'tasks/foreach_norm/worker_knowledge_reads.jsonl', state['record'])
    with pytest.raises(StoreError, match='canonical regular file'):
        boundary(state)
