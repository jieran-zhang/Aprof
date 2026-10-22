"""Pure prospective Task-window partition tests; no publication or hardware."""
import csv
from copy import deepcopy
from io import StringIO

import pytest

from aprof_runtime import __version__

if __version__ != '0.2.2':
    pytest.skip('select graph-base/0.5.1', allow_module_level=True)

from aprof_runtime.errors import ContractError
from aprof_runtime.task_window_timing import partition_window_tasks, choose_task_repeat
from test_shared_measurement_admission import draft, pilot_wire, wire

FIELDS = ['Op Name', 'Task Start Time(us)', 'Task Duration(us)', 'Task Type',
          'Stream ID', 'Task ID', 'Device_id']


def messages(config, mode, cycle=0, repeat=100):
    config = deepcopy(config); config['operator'] = 'exp'
    ready, events = pilot_wire(config) if mode == 'pilot' else wire(config, cycle, repeat=repeat)
    return config, [ready, *(event['message'] for event in events)]


def rows_for(messages, names, mode, cycle, repeat, *, pilot_durations=('4', '4', '4')):
    calls = []
    if mode == 'pilot':
        calls.extend([('baseline', None)] * 20)
        calls.extend([('baseline', None)] * 400)
        for index in range(3): calls.extend([('baseline', index)] * 100)
    else:
        for slot in range(2): calls.extend([( ('baseline', 'candidate')[(slot + cycle) % 2], None)] * 10)
        for phase_index, phase in enumerate(('aa_before', 'formal', 'aa_after')):
            prime = messages[1 + 6 * phase_index]
            calls.extend((role if phase == 'formal' else 'baseline', None)
                         for role in prime['prime_order'] for _ in range(100))
            for pair_index in range(5):
                pair = messages[2 + 6 * phase_index + pair_index]
                calls.extend((pair[role]['implementation'], phase)
                             for role in pair['order'] for _ in range(repeat))
    calls.extend([('baseline', None), ('candidate', None)])
    result = []
    for implementation, tag in calls:
        for name in names[implementation]:
            index = len(result)
            duration = pilot_durations[tag] if mode == 'pilot' and type(tag) is int else '4'
            result.append({'Op Name': name, 'Task Start Time(us)': str(index * 1000 + 1),
                'Task Duration(us)': duration, 'Task Type': 'AI_CORE', 'Stream ID': '7',
                'Task ID': str(index + 1), 'Device_id': '0'})
    return result


def table(rows):
    stream = StringIO()
    writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader(); writer.writerows(rows)
    return stream.getvalue()


def partition(config, messages, rows, *, mode, cycle=0, repeat=100, names=None):
    names = names or {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    return partition_window_tasks(csv_text=table(rows), messages=messages, config=config,
                                  mode=mode, cycle=cycle, repeat=repeat, role_kernel_names=names)


def test_pilot_exact_722_tasks_and_candidate_snapshot_not_calibration(draft):
    config, native = messages(draft[1], 'pilot')
    names = {'baseline': ['base_kernel'], 'candidate': ['candidate_kernel']}
    rows = rows_for(native, names, 'pilot', 0, 100, pilot_durations=('99.99999', '100', '101'))
    result = partition(config, native, rows, mode='pilot', names=names)
    assert result['task_count'] == result['csv_row_count'] == 722
    assert len(result['groups']) == 10
    assert result['pilot_samples_task_total_ns_decimal'] == ['9999999.00000', '10000000', '10100000']
    assert result['groups'][-1]['implementation'] == 'candidate'
    assert result['groups'][-1]['task_indices'] == [721, 722]
    assert result['native_intervals'] == 'derived_payload_validation_only'
    selected = choose_task_repeat(result)
    assert selected['repeat'] == 100 and selected['median_100_calls_ns_decimal'] == '10000000'
    assert selected['target_ms'] == 10 and selected['pilot_excluded_from_confirmation'] is True


def test_decimal_ceil_boundary_and_cap_are_exact(draft):
    config, native = messages(draft[1], 'pilot')
    names = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    one_below = partition(config, native,
        rows_for(native, names, 'pilot', 0, 100, pilot_durations=('99.99999',) * 3),
        mode='pilot')
    assert choose_task_repeat(one_below)['repeat'] == 200
    cap = partition(config, native,
        rows_for(native, names, 'pilot', 0, 100, pilot_durations=('0.1',) * 3), mode='pilot')
    assert choose_task_repeat(cap)['repeat'] == 100000
    over_cap = partition(config, native,
        rows_for(native, names, 'pilot', 0, 100, pilot_durations=('0.099',) * 3), mode='pilot')
    with pytest.raises(ContractError, match='maximum repeat'):
        choose_task_repeat(over_cap)


def test_csv_pilot_sum_stays_below_10ms_beyond_default_decimal_precision(draft):
    config, native = messages(draft[1], 'pilot')
    names = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    almost_100_us = '99.' + '9' * 35
    pilot = partition(config, native,
        rows_for(native, names, 'pilot', 0, 100,
                 pilot_durations=(almost_100_us,) * 3), mode='pilot')
    assert pilot['task_count'] == 722
    assert pilot['pilot_samples_task_total_ns_decimal'] == [
        '9999999.' + '9' * 30 + '0' * 5] * 3
    assert choose_task_repeat(pilot)['repeat'] == 200


def test_integer_ceil_stays_exact_beyond_decimal_default_precision(draft):
    config, native = messages(draft[1], 'pilot')
    names = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    pilot = partition(config, native, rows_for(native, names, 'pilot', 0, 100), mode='pilot')
    just_below = '9999999.' + '9' * 35
    pilot['pilot_samples_task_total_ns_decimal'] = [just_below] * 3
    for group in pilot['groups']:
        if group['kind'] == 'pilot_sample':
            group['task_duration_total_ns_decimal'] = just_below
    assert choose_task_repeat(pilot)['repeat'] == 200
    below_cap = '9999.' + '9' * 35
    pilot['pilot_samples_task_total_ns_decimal'] = [below_cap] * 3
    for group in pilot['groups']:
        if group['kind'] == 'pilot_sample':
            group['task_duration_total_ns_decimal'] = below_cap
    with pytest.raises(ContractError, match='maximum repeat'):
        choose_task_repeat(pilot)


@pytest.mark.parametrize('missing', ['task_duration_total_ns_decimal', 'implementation', 'role', 'calls'])
def test_incomplete_pilot_group_has_contract_error(draft, missing):
    config, native = messages(draft[1], 'pilot')
    names = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    pilot = partition(config, native, rows_for(native, names, 'pilot', 0, 100), mode='pilot')
    next(group for group in pilot['groups'] if group['kind'] == 'pilot_sample').pop(missing)
    with pytest.raises(ContractError):
        choose_task_repeat(pilot)


@pytest.mark.parametrize('repeat,expected', [(100, 4222), (7300, 220222)])
def test_confirmation_keeps_30_macro_pairs_at_real_repeat(draft, repeat, expected):
    config, native = messages(draft[1], 'confirmation', cycle=3, repeat=repeat)
    names = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    result = partition(config, native, rows_for(native, names, 'confirmation', 3, repeat),
                       mode='confirmation', cycle=3, repeat=repeat)
    assert result['task_count'] == expected and result['csv_row_count'] == expected
    assert sum(group['kind'] == 'pair' for group in result['groups']) == 30
    assert all(len(result['values_ns_per_call'][phase][role]) == 5
               for phase in ('aa_before', 'formal', 'aa_after') for role in ('baseline', 'candidate'))
    assert result['values_ns_per_call']['formal']['candidate'] == [4000.0] * 5
    assert result['native_protocol'] == 'shared_buffer_acl_event_v2'


def test_serial_two_kernel_callback_requires_each_call_in_order(draft):
    config, native = messages(draft[1], 'confirmation')
    names = {'baseline': ['base_a', 'base_b'], 'candidate': ['cand_a', 'cand_b']}
    for role in ('baseline', 'candidate'):
        config['roles'][role]['launches_per_operator'] = 2
    for message in native:
        message['launches_per_operator'] = {'baseline': 2, 'candidate': 2}
        if message['kind'] == 'pair':
            for role in ('baseline', 'candidate'):
                message[role]['launches_per_operator'] = 2
    rows = rows_for(native, names, 'confirmation', 0, 100)
    result = partition(config, native, rows, mode='confirmation', names=names)
    assert result['task_count'] == 8444
    assert result['groups'][0]['task_count'] == 20
    rows[42]['Op Name'] = 'base_b' if rows[42]['Op Name'] == 'base_a' else 'base_a'
    with pytest.raises(ContractError, match='serial callback kernel order'):
        partition(config, native, rows, mode='confirmation', names=names)


@pytest.mark.parametrize('mutation', ('missing', 'extra', 'mixed', 'pilot_candidate', 'wrong_native'))
def test_pilot_incomplete_or_polluted_evidence_is_rejected(draft, mutation):
    config, native = messages(draft[1], 'pilot')
    names = {'baseline': ['base_kernel'], 'candidate': ['cand_kernel']}
    rows = rows_for(native, names, 'pilot', 0, 100)
    if mutation == 'missing': rows.pop(10)
    elif mutation == 'extra': rows.append({**rows[-1], 'Task ID': '999', 'Task Start Time(us)': '999999'})
    elif mutation == 'mixed': rows[450]['Task Type'] = 'MIX_AIC'
    elif mutation == 'pilot_candidate': rows[450]['Op Name'] = 'cand_kernel'
    else: native[2]['baseline']['implementation'] = 'candidate'
    with pytest.raises((ContractError, ValueError)):
        partition(config, native, rows, mode='pilot', names=names)


@pytest.mark.parametrize('repeat', [0, 99, 101, 100001, True])
def test_invalid_confirmation_repeat_is_rejected(draft, repeat):
    config, native = messages(draft[1], 'confirmation')
    with pytest.raises(ContractError, match='repeat'):
        partition_window_tasks(csv_text='', messages=native, config=config, mode='confirmation',
                               cycle=0, repeat=repeat,
                               role_kernel_names={'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']})
