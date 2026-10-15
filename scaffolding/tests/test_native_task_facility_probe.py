"""Facility orchestration regressions; these fixtures never qualify hardware."""
from contextlib import nullcontext
from copy import deepcopy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import probe_native_task_profile as probe


def slot():
    return {'slot_id': 'exp-01', 'operator': 'exp', 'case_id': 1, 'source': '/frozen/source',
            'case': {'command': ['/frozen/native', '--output', '{cycle_dir}/final.bin']}}


def test_direct_native_and_exactly_one_export_budget(tmp_path):
    plan = {'profiler': {'path': '/frozen/msprof'}}; item = slot()
    native = probe.native_job(tmp_path, plan, item)
    assert native['argv'] == ['/frozen/native', '--output', str(tmp_path / 'exp-01/native/final.bin')]
    assert native['environment']['APROF_TASK_PROFILE_DIR'] == str(tmp_path / 'exp-01/profile')
    assert native['environment']['APROF_SHARED_REPEAT'] == '100'
    assert native['timeout_seconds'] == 120
    export = probe.export_job(tmp_path, plan, item, tmp_path / 'exp-01/profile/PROF_one')
    assert export['argv'] == ['/frozen/msprof', '--export=on', '--type=text', '--output=' + str(tmp_path / 'exp-01/profile/PROF_one')]
    assert export['timeout_seconds'] == 300 and probe.BUDGETS['outer'] == 1500
    assert probe.SLOTS == [('exp', 1), ('sigmoid', 4)]


@pytest.mark.parametrize('field', ['role_bias', 'baseline_cv', 'drift'])
def test_original_local_control_thresholds_are_not_relaxed(field):
    value = {p: {'role_bias': .01, 'baseline_cv': .01, 'candidate_cv': .01}
             for p in ('aa_before', 'formal', 'aa_after')}
    value['drift'] = {'baseline': .01, 'candidate': .01}; probe.check_controls(value)
    if field == 'drift': value['drift']['candidate'] = .02001
    else: value['formal'][field] = .05001 if field.endswith('_cv') else .02001
    with pytest.raises(ValueError, match='local Task A/A control'):
        probe.check_controls(value)


def test_failed_native_preserves_receipt_and_never_exports(tmp_path, monkeypatch):
    calls = []
    def fail(job):
        calls.append(job); directory = Path(job['output_dir']); directory.mkdir()
        probe.save_new(directory / 'execution.json', {'exit_code': 7, 'duration_seconds': 1.25})
        return {'exit_code': 7}
    monkeypatch.setattr(probe, 'job_run', fail)
    row = probe.run_slot(tmp_path, {'profiler': {'path': '/msprof'}}, slot())
    assert row['status'] == 'failed' and len(calls) == 1
    assert row['native-job'] == probe.binding(tmp_path / 'exp-01/native-job/execution.json')
    assert row['costs_seconds']['native'] >= 0 and row['verifications'] == {}
    assert not (tmp_path / 'exp-01/export-job').exists()
    with pytest.raises(FileExistsError): probe.run_slot(tmp_path, {}, slot())


def test_first_failed_slot_stops_entire_probe(tmp_path, monkeypatch):
    plan = {'slots': [slot(), {**slot(), 'slot_id': 'sigmoid-04', 'operator': 'sigmoid', 'case_id': 4}], 'cost_scope': 'cold CLI only'}
    anchor = tmp_path / 'anchor'; anchor.write_text('root')
    monkeypatch.setattr(probe, 'anchored', lambda *args: plan)
    monkeypatch.setattr(probe, 'locks', lambda *args: nullcontext())
    calls = []
    def fail(output, plan, item):
        calls.append(item['slot_id']); directory = output / item['slot_id']; directory.mkdir()
        row = {'status': 'failed'}; probe.save_new(directory / 'receipt.json', row); return row
    monkeypatch.setattr(probe, 'run_slot', fail)
    result = probe.run(tmp_path, anchor)
    assert calls == ['exp-01'] and result['facility_complete'] is False
    assert result['eligible_for_publication'] is False
    assert probe.read(tmp_path / 'sigmoid-04/receipt.json')['status'] == 'not_run'
    assert not (tmp_path / 'sigmoid-04/native').exists()


def test_once_only_prepare_refuses_existing_directory(tmp_path):
    with pytest.raises(ValueError, match='already exists'):
        probe.prepare(tmp_path, tmp_path)


@pytest.mark.parametrize('name', ['APROF_TASK_PROFILE_DIR', 'PROF_CONFIG'])
def test_unregistered_parent_profiling_environment_fails_before_run(monkeypatch, name):
    monkeypatch.setenv(name, '/foreign/profile')
    with pytest.raises(ValueError, match='inherited native timing/profiling'):
        probe.clean_parent_environment()


def test_source_archive_resolution_is_only_selected_by_replay(tmp_path, monkeypatch):
    probe.save_new(tmp_path / 'started.json', {'at': 10})
    captured = []; evidence = object(); references = [{'path': '/frozen/archive', 'sha256': 'sha256:fixture'}]
    def historical(refs, *, logical_paths):
        captured.append((refs, logical_paths)); return evidence
    def anchored(output, anchor, latest, supplied):
        assert supplied is evidence and latest == 10
        raise ValueError('reached read-only history boundary')
    monkeypatch.setattr(probe, 'HistoricalEvidence', historical)
    monkeypatch.setattr(probe, 'anchored', anchored)
    with pytest.raises(ValueError, match='read-only history boundary'):
        probe.replay(tmp_path, tmp_path / 'anchor', source_archive_refs=references)
    assert captured == [(references, True)]
