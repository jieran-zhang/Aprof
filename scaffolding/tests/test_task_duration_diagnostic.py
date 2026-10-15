"""CPU parser regressions; synthetic data never qualifies a device run."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import diagnose_task_duration as diagnostic

SPEC = importlib.util.spec_from_file_location('task_duration_fixture', Path(__file__).with_name('test_shared_measurement_admission.py'))
fixture = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(fixture)


@pytest.fixture
def capture(tmp_path, monkeypatch):
    monkeypatch.setattr(diagnostic, 'REPEAT', 100)
    _, config = fixture.draft.__wrapped__()
    config['operator'] = 'exp'
    ready, events = fixture.wire(config, 0, repeat=100)
    messages = [ready, *[event['message'] for event in events]]
    rows = [{'Op Name': 'exp_kernel', 'Task Start Time(us)': str(1000 + index * 2),
             'Task Duration(us)': '1', 'Device_id': '0', 'Task ID': str(index),
             'Stream ID': '3', 'Task Type': 'AI_VECTOR_CORE'} for index in range(4222)]
    def write(values):
        path = tmp_path / 'op_summary.csv'
        with path.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(values)
        return path
    return messages, config, rows, write


def test_all_tasks_partitioned_without_serializing_duplicate_task_table(capture):
    messages, config, rows, write = capture
    result = diagnostic.summary(write(rows), messages, config)
    assert result['events'] == 30 and result['complete_kernel_tasks'] == 4222
    assert result['accepted'] is False and result['publication_acceptance'] is False
    assert result['samples'][0]['task_indices'] == [420, 520]
    for sample in result['samples']:
        assert 'tasks' not in sample
        assert sample['kernel_total_duration_ns'] == 100000
        assert sample['span_minus_task_sum_ns'] == 99000
        assert sample['maximum_gap_ns'] == 1000
        assert sample['task_duration_us']['mean'] == 1


@pytest.mark.parametrize('change,match', [
    ('missing', 'launch count'), ('foreign', 'unregistered compute'),
    ('duplicate', 'duplicate'), ('stream', 'one device0 stream'), ('negative', 'overlapping|invalid production')])
def test_incomplete_or_ambiguous_task_tables_fail(capture, change, match):
    messages, config, rows, write = capture
    if change == 'missing': rows.pop()
    elif change == 'foreign': rows[100]['Op Name'] = 'other_kernel'
    elif change == 'duplicate': rows[101] = copy.deepcopy(rows[100])
    elif change == 'stream': rows[100]['Stream ID'] = '9'
    elif change == 'negative': rows[100]['Task Duration(us)'] = '-1'
    with pytest.raises(ValueError, match=match):
        diagnostic.summary(write(rows), messages, config)


def test_changed_native_identity_rejected_before_table_aggregation(capture):
    messages, config, rows, write = capture
    messages[2]['stream_address'] = 'different'
    with pytest.raises(Exception, match='identity changed'):
        diagnostic.summary(write(rows), messages, config)


def test_once_only_directory_and_frozen_input(tmp_path):
    with pytest.raises(ValueError, match='already exists'):
        diagnostic.prepare(tmp_path)
    path = tmp_path / 'input.bin'; path.write_bytes(b'original')
    files = {str(path): diagnostic.digest(path)}
    diagnostic.verify(files)
    path.write_bytes(b'changed')
    with pytest.raises(ValueError, match='frozen file changed'):
        diagnostic.verify(files)


def test_oracle_timeout_preserves_actual_attempt(tmp_path, monkeypatch):
    (tmp_path / 'baseline.bin').write_bytes(b'actual output')
    def timeout(argv, **kwargs):
        kwargs['stdout'].write(b'oracle ran before timeout\n')
        raise diagnostic.subprocess.TimeoutExpired(argv, 120)
    monkeypatch.setattr(diagnostic.subprocess, 'run', timeout)
    with pytest.raises(diagnostic.subprocess.TimeoutExpired):
        diagnostic.oracle(tmp_path, 'baseline', {'verify_commands': {'baseline': ['python', 'original.py']}}, str(tmp_path))
    row = json.loads((tmp_path / 'baseline-verify-receipt.json').read_text())
    assert row['status'] == 'failed' and row['exit_status'] is None
    assert row['error']['type'] == 'TimeoutExpired'
    assert row['output_sha256'] == row['output_after_sha256']
    assert row['log_sha256'] == diagnostic.digest(tmp_path / 'baseline-verify.log')
    assert row['started_at'] <= row['finished_at']


def test_execution_wrong_environment_order_and_budget_fail(tmp_path):
    stdout = tmp_path / 'stdout'; stdout.write_text('real log')
    job = {'argv': ['msprof'], 'environment': {'ASCEND_RT_VISIBLE_DEVICES': '0'}, 'timeout_seconds': 600}
    execution = {'job': job, 'exit_code': 0, 'status': 'passed', 'started_at': '1970-01-01T00:01:40Z',
        'finished_at': '1970-01-01T00:01:41Z', 'duration_seconds': 1,
        'stdout': diagnostic.binding(stdout), 'stderr': diagnostic.binding(stdout)}
    assert diagnostic.execution_interval(execution, job, 99, 102, diagnostic.Evidence()) == 101
    for change in ('order', 'budget', 'environment'):
        bad = copy.deepcopy(execution)
        if change == 'order': bad['started_at'] = '1970-01-01T00:01:38Z'
        elif change == 'budget': bad['duration_seconds'] = 601
        else: bad['job']['environment']['ASCEND_RT_VISIBLE_DEVICES'] = '1'
        with pytest.raises(ValueError, match='identity/time'):
            diagnostic.execution_interval(bad, job, 99, 102, diagnostic.Evidence())
