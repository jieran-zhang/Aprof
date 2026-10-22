"""Specific CPU-only checks for the fixed long diagnostic, never admission."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import diagnose_long_task_timeline as long_trace

spec = importlib.util.spec_from_file_location('submission_test_support', Path(__file__).with_name('test_submission_stall_diagnostic.py'))
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)
native = support.native


def test_unchanged_native_header_accepts_500_pair_command_file(native, tmp_path):
    command_file = tmp_path / 'commands.txt'
    command_file.write_text('\n'.join(long_trace.prior.commands(500)) + '\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith('APROF_')}
    env.update(APROF_SUBMISSION_DIAGNOSTIC_MODE='observe', APROF_SHARED_COMMANDS=str(command_file))
    result = subprocess.run([str(native), '1'], input='', capture_output=True, text=True, env=env, timeout=30)
    assert result.returncode == 0, result.stderr
    messages = [json.loads(line[len(long_trace.prior.PREFIX):]) for line in result.stdout.splitlines()
                if line.startswith(long_trace.prior.PREFIX)]
    long_trace.prior.validate_messages(messages, 1, 500)
    counts = json.loads(next(line[len('RESULT:'):] for line in result.stdout.splitlines() if line.startswith('RESULT:')))
    assert counts['baseline_calls'] + counts['candidate_calls'] == 100422


def test_exact_long_task_partition_and_tail_boundaries(tmp_path):
    path = tmp_path / 'tasks.csv'
    fields = ['Op Name', 'Task Type', 'Task Start Time(us)', 'Task Duration(us)', 'Task ID', 'Device_id', 'Stream ID']
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader()
        writer.writerows({'Op Name': 'exp_kernel', 'Task Type': 'AI_VECTOR_CORE',
                          'Task Start Time(us)': str(1791966861387739 + 2 * i), 'Task Duration(us)': '1',
                          'Task ID': str(i), 'Device_id': '0', 'Stream ID': '1'} for i in range(100422))
    sample = {'elapsed_ms': .2, 'enqueue_after_ns': 200, 'enqueue_before_ns': 100,
              'thread_cpu_enqueue_after_ns': 200, 'thread_cpu_enqueue_before_ns': 100,
              'started_monotonic_ns': 1, 'finished_monotonic_ns': 300}
    messages = [{}, {}] + [{'pair_index': i, 'order': ['baseline', 'candidate'] if i % 2 == 0 else ['candidate', 'baseline'],
                           'baseline': dict(sample), 'candidate': dict(sample)} for i in range(500)] + [{}]
    messages[2]['baseline']['elapsed_ms'] = .32
    spans = long_trace.task_spans(path, messages, 500)
    assert len(spans) == 1000
    assert spans[0]['task_indices'] == [420, 520]
    assert spans[-1]['task_indices'] == [100320, 100420]
    assert spans[0]['kernel_sum_us'] == 100 and spans[0]['first_last_span_us'] == 199
    assert spans[0]['maximum_intertask_gap_us'] == 1 and spans[0]['event_minus_task_span_us'] == 121
    assert spans[0]['descriptive_tail'] is True
    assert sum(row['descriptive_tail'] for row in spans) == 1
    # A lost final untimed verification kernel invalidates the whole timeline.
    text = path.read_text(); path.write_text(text.rsplit('\n', 2)[0] + '\n')
    with pytest.raises(ValueError, match='complete task count'):
        long_trace.task_spans(path, messages, 500)
