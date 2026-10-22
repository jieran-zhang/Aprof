"""Synthetic CPU checks for the diagnostic-only exp prewarm trust boundaries."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from aprof_runtime import __version__

if __version__ != '0.2.2':
    pytest.skip('select graph-base/0.5.1', allow_module_level=True)

from aprof_runtime.errors import ContractError
from diagnose_exp_case1_prewarm import (BATCHES, CALLS, ORIGINAL_TASKS, PREFIX_TASKS,
    full_task_partition, prewarm_patch, prewarm_receipt)
from test_shared_measurement_admission import draft, wire
from test_task_timing import table, task_rows


def _messages(draft):
    _, config = draft
    config = deepcopy(config)
    config['operator'] = 'exp'
    ready, events = wire(config, 0, repeat=100)
    return [ready, *(event['message'] for event in events)]


def _full_rows(messages):
    names = {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']}
    suffix = task_rows(messages, names)
    for index, row in enumerate(suffix):
        row['Task Start Time(us)'] = str(100001 + index * 10)
        row['Task ID'] = str(PREFIX_TASKS + index + 1)
    prefix = [{'Op Name': 'exp_kernel', 'Task Start Time(us)': str(1 + index * 10),
               'Task Duration(us)': '4', 'Task Type': 'AI_CORE', 'Stream ID': '7',
               'Task ID': str(index + 1), 'Device_id': '0'} for index in range(PREFIX_TASKS)]
    return prefix + suffix


def test_header_patch_is_one_exact_insertion():
    release = Path(__file__).resolve().parents[2] / 'skill-libs/graph-base/0.5.1'
    old = (release / 'skills/ascendc-aprof-profiling/assets/device_shared_timing.h').read_text()
    new = prewarm_patch(old)
    marker = '    const uint64_t warmup_started = Now();\n'
    assert old.count(marker) == new.count(marker) == 1
    assert new.split(marker)[1] == old.split(marker)[1]
    assert new.count('baseline(stream, buffers);') == old.count('baseline(stream, buffers);') + 1
    with pytest.raises(ValueError, match='marker'):
        prewarm_patch(old.replace(marker, ''))


def test_prewarm_receipt_requires_25_ordered_synchronized_batches(tmp_path, draft):
    messages = _messages(draft)
    ready = messages[0]
    start = ready['warmup_started_monotonic_ns'] - 1000
    row = {'schema_version': 1, 'protocol': 'exp_baseline_prewarm_v1',
           'operator': 'exp', 'cycle_index': 0,
           **{key: ready[key] for key in ('pid', 'device', 'context_address', 'stream_address')},
           'baseline_calls': PREFIX_TASKS, 'batch_count': BATCHES, 'calls_per_batch': CALLS,
           'started_monotonic_ns': start, 'finished_monotonic_ns': start + 999,
           'batches': [{'batch_index': i, 'calls': CALLS, 'cumulative_calls': (i + 1) * CALLS,
                        'started_monotonic_ns': start + i * 2,
                        'finished_monotonic_ns': start + i * 2 + 1} for i in range(BATCHES)]}
    stdout = tmp_path / 'stdout.log'

    def write(value):
        stdout.write_text('APROF_PREWARM_JSON:' + json.dumps(value) + '\n'
                          'APROF_SHARED_TIMING_JSON:' + json.dumps(ready) + '\n')

    write(row)
    assert prewarm_receipt(stdout, messages, 0, 'B') == row
    for changed in ({**row, 'baseline_calls': PREFIX_TASKS - 1},
                    {**row, 'batches': row['batches'][:-1]},
                    {**row, 'finished_monotonic_ns': ready['warmup_started_monotonic_ns'] + 1},
                    {**row, 'input_bytes_unchanged': True}):
        write(changed)
        with pytest.raises(ValueError):
            prewarm_receipt(stdout, messages, 0, 'B')
    write(row)
    with pytest.raises(ValueError, match='A unexpectedly'):
        prewarm_receipt(stdout, messages, 0, 'A')


@pytest.mark.parametrize('mutation', ('missing_prefix', 'unknown_type', 'overlap'))
def test_full_csv_retains_prefix_and_replays_original_4222_tasks(tmp_path, draft, mutation):
    messages = _messages(draft)
    rows = _full_rows(messages)
    if mutation == 'missing_prefix':
        rows.pop(10)
    elif mutation == 'unknown_type':
        rows[200]['Task Type'] = 'N/A'
    elif mutation == 'overlap':
        rows[200]['Task Start Time(us)'] = rows[199]['Task Start Time(us)']
    original = tmp_path / 'complete-op-summary.csv'
    original.write_text(table(rows))
    derived = tmp_path / 'derived-original-tasks.csv'
    if mutation:
        with pytest.raises((ValueError, ContractError)):
            full_task_partition(original, messages, cycle=0, arm='B', derived_path=derived)
        assert not derived.exists()


def test_valid_full_csv_and_read_only_derived_replay(tmp_path, draft):
    messages = _messages(draft)
    original = tmp_path / 'complete-op-summary.csv'
    original.write_text(table(_full_rows(messages)))
    derived = tmp_path / 'derived-original-tasks.csv'
    partition, audit = full_task_partition(original, messages, cycle=0, arm='B', derived_path=derived)
    assert partition['task_count'] == ORIGINAL_TASKS
    assert audit['full_task_count'] == PREFIX_TASKS + ORIGINAL_TASKS
    assert len(audit['prefix_batches']) == BATCHES
    assert full_task_partition(original, messages, cycle=0, arm='B',
                               derived_path=derived, allow_create=False) == (partition, audit)
    derived.unlink()
    with pytest.raises(ValueError, match='missing during read-only replay'):
        full_task_partition(original, messages, cycle=0, arm='B',
                            derived_path=derived, allow_create=False)
    assert not derived.exists()
