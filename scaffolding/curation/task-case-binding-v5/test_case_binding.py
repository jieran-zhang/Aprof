"""CPU-only prospective v5 checks; run through run_cpu_checks.py."""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys

import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.measurement_admission import _config_identity
from aprof_runtime.task_window_timing import case_task_config, partition_window_tasks
import aprof_runtime.task_window_measurement_admission as admission
import device_task_window_timing as collector
import test_shared_measurement_admission as legacy_fixture
import test_task_window_measurement_admission as window_fixture
from test_shared_measurement_admission import archive, draft, pilot_wire, wire
from test_task_window_measurement_admission import window_archive
from test_task_window_timing import rows_for, table


@pytest.fixture(autouse=True)
def temporary_producers(monkeypatch):
    release = Path(os.environ['APROF_CASE_BINDING_TEST_RELEASE'])
    assert release.is_relative_to('/tmp')
    monkeypatch.setattr(legacy_fixture, 'RELEASE', release)
    monkeypatch.setattr(window_fixture, 'RELEASE', release)


@pytest.fixture
def case_config(draft):
    config = deepcopy(draft[1])
    config['operator'] = 'synthetic_gqa'
    config['expected_case_ids'] = [1, 2]
    second = deepcopy(config['cases'][0])
    second.update(case_id=2, workload={'shape': [2, 4, 64, 128], 'dtype': 'bfloat16'})
    config['cases'].append(second)
    # Repeated QK/PV names are intentional launches in a complete callback.
    names = {role: {
        '1': [f'reorder_{role}', f'qk_fp16_{role}', f'softmax_{role}',
              f'pv_fp16_{role}', f'scatter_{role}'],
        '2': [f'reorder_{role}', f'qk_bf16_{role}', f'qk_bf16_{role}',
              f'softmax_{role}', f'pv_bf16_{role}', f'pv_bf16_{role}', f'scatter_{role}'],
    } for role in ('baseline', 'candidate')}
    for role in names:
        config['roles'][role]['launches_per_operator'] = {
            cid: len(sequence) for cid, sequence in names[role].items()}
    config['task_profile'] = {'profiler': '/synthetic/msprof',
        'scratch_root': '/synthetic/scratch', 'role_kernel_names': names}
    return config


def native(config, case_id, mode, cycle):
    selected = case_task_config(config, case_id)
    ready, events = pilot_wire(selected) if mode == 'pilot' else wire(selected, cycle, repeat=100)
    messages = [ready, *(event['message'] for event in events)]
    counts = {role: selected['roles'][role]['launches_per_operator']
              for role in ('baseline', 'candidate')}
    for message in messages:
        message['launches_per_operator'] = dict(counts)
        for role in counts:
            if role in message:
                sample = message[role]
                sample['launches_per_operator'] = counts[sample['implementation']]
    return selected, messages


def parse(config, case_id, mode='confirmation', cycle=0, mutate=None):
    selected, messages = native(config, case_id, mode, cycle)
    names = selected['task_profile']['role_kernel_names']
    rows = rows_for(messages, names, mode, cycle, 100)
    if mutate:
        mutate(rows, messages, selected)
    return partition_window_tasks(csv_text=table(rows), messages=messages, config=selected,
        mode=mode, cycle=cycle, repeat=100,
        role_kernel_names=selected['task_profile']['role_kernel_names'])


@pytest.mark.parametrize('case_id', [1, 2])
@pytest.mark.parametrize('mode,cycle', [('pilot', 0), ('confirmation', 0), ('confirmation', 5)])
def test_cross_case_full_callbacks_and_repeated_names(case_config, case_id, mode, cycle):
    before = deepcopy(case_config)
    result = parse(case_config, case_id, mode, cycle)
    count = 5 if case_id == 1 else 7
    assert result['task_count'] == (722 if mode == 'pilot' else 4222) * count
    assert sum(group['task_count'] for group in result['groups']) == result['csv_row_count']
    if mode == 'confirmation':
        assert result['values_ns_per_call']['formal']['baseline'] == [count * 4000.0] * 5
    assert case_config == before


@pytest.mark.parametrize('fault', ['missing', 'extra', 'duplicate', 'wrong_name', 'wrong_case', 'wrong_native'])
def test_complete_task_sequence_corruption_is_rejected(case_config, fault):
    def mutate(rows, messages, selected):
        if fault == 'missing':
            rows.pop(77)
        elif fault == 'extra':
            rows.append(deepcopy(rows[-1]))
        elif fault == 'duplicate':
            rows[77] = deepcopy(rows[76])
        elif fault == 'wrong_name':
            rows[77]['Op Name'] = rows[78]['Op Name']
        elif fault == 'wrong_case':
            # Same count, wrong dtype: changing only the names cannot pass.
            selected['task_profile']['role_kernel_names']['baseline'][1] = 'qk_bf16_baseline'
        else:
            messages[0]['launches_per_operator']['candidate'] += 1
    with pytest.raises(ContractError):
        parse(case_config, 1, mutate=mutate)


@pytest.mark.parametrize('fault', ['missing_case', 'extra_case', 'integer_key', 'scalar_count',
    'global_names', 'count_mismatch', 'bool_count', 'empty_name', 'unknown_case'])
def test_maps_have_exact_case_role_scope(case_config, fault):
    count = case_config['roles']['candidate']['launches_per_operator']
    names = case_config['task_profile']['role_kernel_names']['candidate']
    if fault == 'missing_case':
        names.pop('2')
    elif fault == 'extra_case':
        count['3'] = 7
    elif fault == 'integer_key':
        count[2] = count.pop('2')
    elif fault == 'scalar_count':
        case_config['roles']['candidate']['launches_per_operator'] = 5
    elif fault == 'global_names':
        case_config['task_profile']['role_kernel_names']['candidate'] = names['1']
    elif fault == 'count_mismatch':
        count['2'] -= 1
    elif fault == 'bool_count':
        count['2'] = True
    elif fault == 'empty_name':
        names['2'][0] = ''
    with pytest.raises(ContractError):
        # A bad unselected case is rejected too.
        case_task_config(case_config, 3 if fault == 'unknown_case' else 1)


def test_two_role_counts_are_independent(case_config):
    names = case_config['task_profile']['role_kernel_names']['candidate']['2']
    names.pop(2)
    case_config['roles']['candidate']['launches_per_operator']['2'] -= 1
    result = parse(case_config, 2)
    assert result['values_ns_per_call']['formal']['baseline'] == [28000.0] * 5
    assert result['values_ns_per_call']['formal']['candidate'] == [24000.0] * 5


def test_collector_retains_all_case_maps_and_legacy_source_checks(case_config, tmp_path):
    def file(name, content=b'synthetic source'):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return str(path)
    for role in ('baseline', 'candidate'):
        file(role + '/kernel.cpp')
        case_config['roles'][role]['source_dir'] = str(tmp_path / role)
    file('build/op_host/device_task_profile.h', collector.HEADER_ASSET.read_bytes())
    case_config['build'] = {'source_dir': str(tmp_path / 'build'),
        'binary': file('build/kernel'), 'receipt_files': [file('build/build.json', b'{}')]}
    prepared, verifier = file('input.bin'), file('verify.py')
    for case in case_config['cases']:
        case['prepared_files'] = [prepared]
        case['command'] = [case_config['build']['binary'], '--case-id', str(case['case_id'])]
        case['verify_commands'] = {role: [str(Path(sys.executable).resolve()), verifier,
            '--output', '{cycle_dir}/' + role + '.bin'] for role in ('baseline', 'candidate')}
    case_config['task_profile'].update(profiler=file('msprof'), scratch_root=str(tmp_path / 'scratch'))
    result = collector.config_value(case_config)
    assert result == case_config
    assert len(result['cases']) == 2
    result['roles']['baseline']['launches_per_operator']['2'] = 99
    assert case_config['roles']['baseline']['launches_per_operator']['2'] == 7
    Path(verifier).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        collector.config_value(case_config)


def test_identity_count_map_is_opt_in(case_config, tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(case_config))
    class Reader:
        def verify_artifact(self, ref):
            assert ref == 'config'
            return path
    receipt = {'config_ref': 'config', **{key: case_config[key]
        for key in ('operator', 'run_id', 'session_id', 'candidate_id')}}
    assert _config_identity(Reader(), receipt, extra_fields=('task_profile',),
                            case_launch_counts=True) == case_config
    with pytest.raises(ContractError, match='invalid callback binding'):
        _config_identity(Reader(), receipt, extra_fields=('task_profile',))


def test_full_replay_binds_maps_and_rejects_old_protocol(window_archive):
    store, raw, config, registration, calibration, seal, expected, blob, value, load = window_archive
    for role in ('baseline', 'candidate'):
        config['roles'][role]['launches_per_operator'] = {'1': 1}
        config['task_profile']['role_kernel_names'][role] = {'1': ['exp_kernel']}
    reference = seal()
    assert admission.PROTOCOL == collector.PROTOCOL == 'shared_buffer_msprof_task_window_v5'
    assert admission.replay_task_window_measurement_admission(store, reference, expected=expected)['valid']
    receipt = load(reference)
    receipt['protocol'] = 'shared_buffer_msprof_task_window_v4'
    with pytest.raises(ContractError, match='unsupported Task window admission receipt'):
        admission.replay_task_window_measurement_admission(store, value(receipt), expected=expected)
    # A role name swapped after registration cannot reuse the original Task CSV.
    config['task_profile']['role_kernel_names']['candidate']['1'] = ['other_kernel']
    with pytest.raises(ContractError):
        admission.replay_task_window_measurement_admission(store, seal(), expected=expected)
