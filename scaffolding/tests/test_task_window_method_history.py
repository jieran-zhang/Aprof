"""Small file fixtures exercise offline historical evidence boundaries."""
import copy
import json
from pathlib import Path

import pytest

import replay_offline_task_export as offline
import replay_task_window_method_history as bridge
from replay_timing_diagnosis import Evidence, digest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return {'path': str(path), 'sha256': digest(path)}


def test_complete_inventory_rejects_removed_derived_output(tmp_path):
    raw = tmp_path / 'raw'; raw.write_bytes(b'raw')
    expected = {'raw': {'sha256': digest(raw), 'bytes': 3},
                'derived.json': {'sha256': 'sha256:' + '0' * 64, 'bytes': 10}}
    with pytest.raises(ValueError, match='complete retained file inventory'):
        offline.tree(Evidence(), tmp_path, expected)


def test_raw_mutation_rejected_even_at_same_length(tmp_path):
    raw = tmp_path / 'raw'; raw.write_bytes(b'old')
    expected = {'raw': {'sha256': digest(raw), 'bytes': 3}}
    raw.write_bytes(b'new')
    with pytest.raises(ValueError, match='changed evidence'):
        offline.tree(Evidence(), tmp_path, expected)


def test_log_append_preserves_original_and_binds_suffix():
    result = offline.log_append(b'original\n', b'original\nnew\n')
    assert result['before']['bytes'] == 9 and result['appended']['bytes'] == 4
    assert result['appended_lines'] == 1 and result['transformation'] == 'append_only'
    for data in (b'original', b'rewritten\nnew\n'):
        with pytest.raises(ValueError, match='rewritten or truncated'):
            offline.log_append(b'original\n', data)


def test_full_csv_count_not_summary_passed_flag(tmp_path):
    path = tmp_path / 'op_summary.csv'
    path.write_text('Op Name,Task Type\nexp_kernel,AI_VECTOR_CORE\n')
    with pytest.raises(ValueError, match='complete CSV task count'):
        offline.count_csv(Evidence(), {'path': str(path), 'sha256': digest(path)})


def terminal_fixture():
    slots = [{'id': '0-default', 'prof_name': 'PROF_x'}, {'id': '1-reports-off'},
             {'id': '2-reports-off'}, {'id': '3-default'}]
    result = {'complete': False, 'eligible_for_publication': False, 'kernel_measurement': False,
              'original_profile_unchanged': True, 'slots': [{'id': '0-default', 'status': 'failed'}],
              'unrun_slots': ['1-reports-off', '2-reports-off', '3-default'],
              'error': {'type': 'ValueError', 'message': 'raw or collection metadata changed: '
                        'PROF_x/mindstudio_profiler_log/collection_device_0.log'}}
    return slots, result


def test_v2_failure_and_three_unrun_are_mandatory():
    slots, result = terminal_fixture()
    offline.check_terminal(result, slots, 1)
    for change in ({'complete': True}, {'unrun_slots': []}, {'slots': [{'id': '0-default', 'status': 'passed'}]}):
        with pytest.raises(ValueError):
            offline.check_terminal(result | change, slots, 1)


def test_frozen_commands_never_clear_or_select_task_subset():
    plan = {'reports_ref': {'path': '/reports.json'}, 'environment': {'LANG': 'C.UTF-8'}}
    slot = {'id': '1-summary', 'condition': 'summary', 'scratch_root': '/tmp/fresh', 'prof_name': 'PROF_x'}
    assert offline.frozen_job(plan, slot)['argv'] == [offline.PYTHON, offline.SUMMARY, 'export', 'summary',
                                                    '-dir', '/tmp/fresh/PROF_x', '--format', 'csv']
    slot['condition'] = 'reports-off'
    assert offline.frozen_job(plan, slot)['argv'][-1] == '--reports=/reports.json'
    assert not any('--clear' in x for x in offline.frozen_job(plan, slot)['argv'])


def test_execution_rejects_cost_or_chronology_forgery(tmp_path):
    job = {'argv': ['tool'], 'output_dir': str(tmp_path), 'timeout_seconds': 300}
    logs = {}
    for name in ('stdout', 'stderr'):
        p = tmp_path / (name + '.log'); p.write_text('')
        logs[name] = {'path': str(p), 'sha256': digest(p)}
    value = dict(logs, job=job, exit_code=0, status='passed', physical_device=None,
                 started_at='2026-10-14T00:00:00Z', finished_at='2026-10-14T00:00:02Z', duration_seconds=2)
    offline.execution(Evidence(), value, job)
    with pytest.raises(ValueError, match='duration'):
        offline.execution(Evidence(), value | {'duration_seconds': .5}, job)


def test_bridge_invokes_prior_chain_once_and_never_grants_admission(tmp_path, monkeypatch):
    proposal = write(tmp_path / 'proposal.json', {})
    items = [{'id': name} for name in offline.IDS]
    value = {'schema_version': 1, 'purpose': bridge.PURPOSE, 'protocol': bridge.PROTOCOL,
             'not_a_release': True, 'eligible_for_publication': False, 'source_archive_refs': [],
             'prior_window_history_ref': {'path': '/prior', 'sha256': 'sha256:' + '1' * 64},
             'offline_export_studies': items, 'oracle_cpu_cost': {}, 'proposal_ref': proposal}
    reference = write(tmp_path / 'history.json', value); calls = []
    def prior(ref):
        calls.append(ref)
        return {'valid': True, 'accepted': False, 'eligible_for_publication': False}
    monkeypatch.setattr(bridge, 'replay_task_sampling_window_history', prior)
    monkeypatch.setattr(bridge, 'replay_offline_study', lambda evidence, item, index: {'id': item['id']})
    monkeypatch.setattr(bridge, 'replay_cpu_cost', lambda evidence, source: {'hardware_samples': 0})
    result = bridge.replay_task_window_method_history(reference)
    assert calls == [value['prior_window_history_ref']]
    assert result['valid'] and not result['accepted'] and not result['eligible_for_publication']
    value['offline_export_studies'] = items[1:]
    reference = write(tmp_path / 'history.json', value)
    with pytest.raises(ValueError, match='predecessor roster'):
        bridge.replay_task_window_method_history(reference)
    assert len(calls) == 1
