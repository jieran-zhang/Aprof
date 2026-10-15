"""CPU-only boundaries for the fixed 24-slot Task Duration diagnosis."""
from copy import deepcopy
import csv
from pathlib import Path

import pytest
import diagnose_task_sampling_window as diagnostic

from aprof_runtime import __version__

if __version__ != '0.2.2':
    pytest.skip('select graph-base/0.5.1', allow_module_level=True)

from diagnose_task_sampling_window import (_costs, _oracle_sequence, _unique_native_identity, matrix,
    partition_slot, summarize_matrix, timeline_protocol)
from test_shared_measurement_admission import draft, wire


FIELDS = ['Op Name', 'Task Start Time(us)', 'Task Duration(us)', 'Task Type',
          'Stream ID', 'Task ID', 'Device_id']


def _messages(config, cycle, repeat):
    config = deepcopy(config)
    config['operator'] = 'exp'
    ready, events = wire(config, cycle, repeat=repeat)
    return config, [ready, *(event['message'] for event in events)]


def _table(path, messages, repeat, *, extra=False, missing=False, task_type='AI_CORE'):
    calls = []
    cycle = messages[0]['cycle_index']
    for slot in range(2):
        calls.extend([('baseline', None)] * 10 if (slot + cycle) % 2 == 0
                     else [('candidate', None)] * 10)
    for phase_index, phase in enumerate(('aa_before', 'formal', 'aa_after')):
        prime = messages[1 + 6 * phase_index]
        calls.extend((role if phase == 'formal' else 'baseline', None)
                     for role in prime['prime_order'] for _ in range(100))
        for pair in range(5):
            message = messages[2 + 6 * phase_index + pair]
            calls.extend((message[role]['implementation'], phase)
                         for role in message['order'] for _ in range(repeat))
    calls.extend([('baseline', None), ('candidate', None)])
    if missing: calls.pop()
    if extra: calls.append(('candidate', None))
    with Path(path).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS); writer.writeheader()
        for index, (_, phase) in enumerate(calls):
            writer.writerow({'Op Name': 'exp_kernel', 'Task Start Time(us)': str(index * 10 + 1),
                'Task Duration(us)': '4', 'Task Type': task_type if index == 40 else 'AI_CORE',
                'Stream ID': '7', 'Task ID': str(index + 1), 'Device_id': '0'})


def test_matrix_is_exact_24_fresh_slots_with_alternating_order():
    entries = matrix()
    assert len(entries) == len({row['slot_id'] for row in entries}) == 24
    for cycle in range(6):
        selected = [row for row in entries if row['cycle'] == cycle]
        assert [(row['case_id'], row['repeat']) for row in selected] == (
            [(1, 100), (1, 7300), (10, 100), (10, 7300)] if cycle % 2 == 0 else
            [(10, 7300), (10, 100), (1, 7300), (1, 100)])


@pytest.mark.parametrize('repeat,expected', [(100, 4222), (7300, 220222)])
def test_full_csv_yields_thirty_macro_pairs_not_thirty_times_repeat(tmp_path, draft, repeat, expected):
    config, messages = _messages(draft[1], 2, repeat)
    path = tmp_path / 'op_summary.csv'
    _table(path, messages, repeat)
    result = partition_slot(path, messages, config, cycle=2, repeat=repeat)
    assert result['task_count'] == result['csv_row_count'] == expected
    assert len(result['groups']) == 30
    assert sum(group['task_count'] for group in result['groups']) == 30 * repeat
    assert all(group['task_count'] == repeat for group in result['groups'])
    assert result['values_ns_per_call']['formal']['baseline'] == [4000.0] * 5
    assert result['values_ns_per_call']['formal']['candidate'] == [4000.0] * 5
    assert result['native_intervals'] == 'derived_payload_validation_only'


@pytest.mark.parametrize('cycle,repeat', [(cycle, repeat) for cycle in range(6) for repeat in (100, 7300)])
def test_native_state_machine_accepts_only_actual_cycle_and_repeat(draft, cycle, repeat):
    config, messages = _messages(draft[1], cycle, repeat)
    timeline_protocol(messages, config, repeat, cycle=cycle)
    with pytest.raises(ValueError):
        timeline_protocol(messages, config, 100 if repeat == 7300 else 7300, cycle=cycle)
    with pytest.raises(ValueError):
        timeline_protocol(messages, config, repeat, cycle=(cycle + 1) % 6)


@pytest.mark.parametrize('mutation', ('extra', 'missing', 'mixed', 'missing_phase'))
def test_invalid_full_table_or_phase_is_rejected(tmp_path, draft, mutation):
    config, messages = _messages(draft[1], 0, 100)
    path = tmp_path / 'op_summary.csv'
    _table(path, messages, 100, extra=mutation == 'extra', missing=mutation == 'missing',
           task_type='MIX_AIC' if mutation == 'mixed' else 'AI_CORE')
    if mutation == 'missing_phase': messages.pop(6)
    with pytest.raises((ValueError, KeyError)):
        partition_slot(path, messages, config, cycle=0, repeat=100)


def test_summary_uses_thirty_pairs_per_arm_and_keeps_quality_failures_diagnostic():
    config = {'operator': 'exp', 'expected_case_ids': [1, 10],
              'cases': [{'case_id': i} for i in range(1, 11)]}
    rows = []
    for entry in matrix():
        value = 4000.0 if entry['repeat'] == 100 else 4040.0
        values = {phase: {role: [value] * 5 for role in ('baseline', 'candidate')}
                  for phase in ('aa_before', 'formal', 'aa_after')}
        if entry['case_id'] == 10 and entry['repeat'] == 7300 and entry['cycle'] == 5:
            values['formal']['candidate'] = [value * 1.2] * 5
        rows.append({**entry, 'partition': {'values_ns_per_call': values},
                     'costs': {key: 1.0 for key in ('capture_seconds', 'export_seconds',
                             'copy_seconds', 'oracle_seconds', 'total_wall_seconds')}})
    report = summarize_matrix(rows, config)
    assert report['accepted'] is report['eligible_for_publication'] is False
    assert all(arm['formal_pairs'] == 30 for arm in report['arms'])
    assert all(item['ratio'] > 1 for item in report['long_over_short'])
    assert next(arm for arm in report['arms'] if arm['case_id'] == 10 and arm['repeat'] == 7300)['stable_controls'] is False
    with pytest.raises(ValueError):
        summarize_matrix(rows[:-1], config)


def test_failed_slot_costs_retain_observed_work_without_inventing_unrun_stages(tmp_path):
    row = {'started_at': 10.0, 'finished_at': 13.0, 'verifications': {}}
    missing = _costs(row, tmp_path)
    assert missing['capture_seconds'] is missing['export_seconds'] is None
    assert missing['copy_seconds'] is missing['oracle_seconds'] is None
    assert missing['total_wall_seconds'] == 3.0
    capture = tmp_path / 'capture.json'
    capture.write_text('{"duration_seconds":1.25}')
    row['capture'] = {'path': str(capture)}
    row['verifications']['baseline'] = {'started_at': 11.0, 'finished_at': 11.5}
    partial = _costs(row, tmp_path)
    assert partial['capture_seconds'] == 1.25
    assert partial['oracle_seconds'] is None
    assert partial['oracle_by_role_seconds'] == {'baseline': .5, 'candidate': None}


def test_oracles_must_follow_profile_transfer_in_order_with_120s_cap():
    def receipt(start, finish):
        return {'status': 'passed', 'exit_status': 0, 'started_at': start,
                'finished_at': finish, 'output_sha256': 'sha256:x',
                'output_after_sha256': 'sha256:x'}
    valid = {'baseline': receipt(20, 30), 'candidate': receipt(31, 40)}
    assert _oracle_sequence(valid, 19, 41) == 40
    for changed in ({'baseline': receipt(18, 30), 'candidate': valid['candidate']},
                    {'baseline': valid['baseline'], 'candidate': receipt(29, 40)},
                    {'baseline': receipt(20, 141), 'candidate': valid['candidate']},
                    {'baseline': {**valid['baseline'], 'status': 'failed'}, 'candidate': valid['candidate']},
                    {'baseline': {**valid['baseline'], 'output_after_sha256': 'sha256:y'},
                     'candidate': valid['candidate']}):
        with pytest.raises(ValueError):
            _oracle_sequence(changed, 19, 200)


def test_unregistered_repeat_cannot_reuse_diagnostic_parser(tmp_path, draft):
    config, messages = _messages(draft[1], 0, 100)
    with pytest.raises(ValueError, match='fixed matrix'):
        partition_slot(tmp_path / 'missing.csv', messages, config, cycle=0, repeat=500)


def test_analysis_cannot_be_saved_when_frozen_helpers_changed(tmp_path, monkeypatch):
    campaign = tmp_path / 'campaign'
    campaign.mkdir()
    monkeypatch.setattr(diagnostic, 'summarize_matrix', lambda rows, config: {'accepted': False})
    monkeypatch.setattr(diagnostic, '_anchored', lambda output, anchor: (_ for _ in ()).throw(
        ValueError('frozen helper changed')))
    with pytest.raises(ValueError, match='frozen helper changed'):
        diagnostic._save_checked_analysis(tmp_path, tmp_path / 'anchor.json', campaign, [], {})
    assert not (campaign / 'analysis.json').exists()
    monkeypatch.setattr(diagnostic, '_anchored', lambda output, anchor: ({}, {}))
    reference = diagnostic._save_checked_analysis(tmp_path, tmp_path / 'anchor.json', campaign, [], {})
    assert reference['path'] == str(campaign / 'analysis.json')
    assert (campaign / 'analysis.json').read_text().find('"accepted": false') >= 0


def test_native_process_identity_allows_pid_reuse_only_with_new_capture_start():
    seen = set()
    assert _unique_native_identity(123, '2026-10-14T10:00:00Z', seen) == (123, '2026-10-14T10:00:00Z')
    assert _unique_native_identity(123, '2026-10-14T10:01:00Z', seen) == (123, '2026-10-14T10:01:00Z')
    with pytest.raises(ValueError, match='reused'):
        _unique_native_identity(123, '2026-10-14T10:00:00Z', seen)
    with pytest.raises(ValueError, match='invalid'):
        _unique_native_identity(0, '2026-10-14T10:02:00Z', seen)
