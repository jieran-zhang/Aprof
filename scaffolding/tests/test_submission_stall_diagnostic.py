"""CPU-only diagnostic protocol checks; no device or admission evidence."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scaffolding/collection/scripts'
sys.path.insert(0, str(SCRIPTS))
import diagnose_submission_stalls as diagnostic

spec = importlib.util.spec_from_file_location('shared_header_test_support', Path(__file__).with_name('test_device_shared_timing_header.py'))
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler = shutil.which('g++')
    if compiler is None:
        pytest.skip('C++ compiler required for fake ACL test')
    directory = tmp_path_factory.mktemp('submission-fake-acl')
    (directory / 'acl').mkdir()
    (directory / 'acl/acl.h').write_text(support.FAKE_ACL)
    program = support.PROGRAM.replace('"device_shared_timing.h"', '"device_submission_diagnostic.h"').replace(',1,2,', ',1,1,')
    (directory / 'main.cpp').write_text(program)
    executable = directory / 'native'
    subprocess.run([compiler, '-std=c++17', '-O2', '-I', str(directory), '-I', str(diagnostic.HEADER.parent),
                    str(directory / 'main.cpp'), '-o', str(executable)], check=True, capture_output=True, text=True)
    return executable


def run(native, cycle, pairs, *, mode=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('APROF_')}
    env['APROF_SUBMISSION_DIAGNOSTIC_MODE'] = mode or ('observe' if pairs == 500 else 'profile')
    result = subprocess.run([str(native), str(cycle)], input='\n'.join(diagnostic.commands(pairs)) + '\n',
                            capture_output=True, text=True, timeout=30, env=env)
    messages = [json.loads(line[len(diagnostic.PREFIX):]) for line in result.stdout.splitlines()
                if line.startswith(diagnostic.PREFIX)]
    return result, messages


@pytest.mark.parametrize('cycle,pairs', [(0, 5), (1, 5), (0, 500), (1, 500)])
def test_aggregate_instrumentation_counts_and_chronology(native, cycle, pairs):
    result, messages = run(native, cycle, pairs)
    assert result.returncode == 0, result.stderr
    diagnostic.validate_messages(messages, cycle, pairs)
    counts = json.loads(next(line[len('RESULT:'):] for line in result.stdout.splitlines() if line.startswith('RESULT:')))
    assert counts['baseline_calls'] == counts['candidate_calls'] == 211 + pairs * 100
    assert counts['event_syncs'] == pairs * 2
    assert counts['record_events'] == pairs * 4
    assert counts['snapshots'] == ['baseline:101', 'candidate:202']
    assert all(msg['protocol'] == diagnostic.PROTOCOL for msg in messages)


def test_unknown_mode_rejected_before_protocol(native):
    result, messages = run(native, 0, 5, mode='unregistered')
    assert result.returncode != 0 and not messages


def test_missing_pair_and_backwards_resources_rejected(native):
    result, messages = run(native, 0, 5)
    assert result.returncode == 0
    with pytest.raises(ValueError, match='incomplete native protocol'):
        diagnostic.validate_messages(messages[:-2] + messages[-1:], 0, 5)
    changed = copy.deepcopy(messages)
    changed[2]['baseline']['thread_usage_before']['nivcsw'] = 10**9
    with pytest.raises(ValueError, match='resource counter'):
        diagnostic.validate_messages(changed, 0, 5)


def test_sync_switches_are_reported_separately_and_do_not_create_admission(native):
    result, messages = run(native, 0, 5)
    assert result.returncode == 0
    sample = messages[2]['baseline']
    for name in ('thread_usage_before', 'thread_usage_start_record_after', 'thread_usage_enqueue_after', 'thread_usage_end_record_after'):
        sample[name] = dict.fromkeys(diagnostic.USAGE, 0)
    for name in ('thread_usage_synchronize_after', 'thread_usage_after'):
        sample[name] = dict.fromkeys(diagnostic.USAGE, 0)
        sample[name]['nvcsw'] = 2
    sample['elapsed_ms'] = 2
    report = diagnostic.summarize([{'cycle': 0, 'messages': messages}])
    row = report['events'][0]
    assert row['enqueue_resource_delta']['nvcsw'] == 0
    assert row['synchronize_resource_delta']['nvcsw'] == 2
    assert row['descriptive_tail'] is True
    assert report['accepted'] is False
    assert len(report['events']) == 10


def test_absolute_profiler_clock_subtracted_before_float_conversion():
    tasks = [{'Task Start Time(us)': '1791966861387739.206', 'Task Duration(us)': '6.003'},
             {'Task Start Time(us)': '1791966861387745.210', 'Task Duration(us)': '6.002'}]
    assert diagnostic.task_intervals(tasks) == {'kernel_sum_us': 12.005, 'first_last_span_us': 12.006,
                                                'maximum_intertask_gap_us': .001}
    tasks[1]['Task Start Time(us)'] = '1791966861387745.200'
    with pytest.raises(ValueError, match='overlapping'):
        diagnostic.task_intervals(tasks)
