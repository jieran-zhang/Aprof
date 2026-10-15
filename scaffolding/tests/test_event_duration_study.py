"""Independent CPU tests; fake ACL never produces hardware qualification."""
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
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import run_event_duration_study as study

spec = importlib.util.spec_from_file_location('duration_header_test_support', Path(__file__).with_name('test_device_shared_timing_header.py'))
support = importlib.util.module_from_spec(spec)
spec.loader.exec_module(support)


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler = shutil.which('g++')
    if compiler is None:
        pytest.skip('C++ compiler required for fake ACL')
    directory = tmp_path_factory.mktemp('duration-study-fake-acl')
    (directory / 'acl').mkdir()
    (directory / 'acl/acl.h').write_text(support.FAKE_ACL)
    (directory / 'main.cpp').write_text(support.PROGRAM.replace('device_shared_timing.h', 'device_duration_study.h').replace(',1,2,', ',1,1,'))
    executable = directory / 'native'
    subprocess.run([compiler, '-std=c++17', '-O2', '-I', str(directory), '-I', str(study.HEADER.parent),
                    str(directory / 'main.cpp'), '-o', str(executable)], check=True, capture_output=True, text=True)
    return executable


def run(native, mode, repeat, cycle=0, commands=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('APROF_')}
    env.update(APROF_DURATION_MODE=mode, APROF_DURATION_REPEAT=str(repeat))
    completed = subprocess.run([str(native), str(cycle)], input='\n'.join(study.commands(mode) if commands is None else commands) + '\n',
                               capture_output=True, text=True, env=env, timeout=15)
    messages = [json.loads(s[len(study.PREFIX):]) for s in completed.stdout.splitlines() if s.startswith(study.PREFIX)]
    return completed, messages


def test_pilot_exactly_three_baseline_samples_and_independent_callback_oracles(native):
    result, messages = run(native, 'pilot', 100)
    assert result.returncode == 0, result.stderr
    study.validate(messages, 'pilot', 0, 100, 'fake_cpu_only')
    counts = json.loads(next(s[7:] for s in result.stdout.splitlines() if s.startswith('RESULT:')))
    assert counts['baseline_calls'] == 711 and counts['candidate_calls'] == 11
    assert counts['event_syncs'] == 3 and counts['record_events'] == 6
    assert counts['snapshots'] == ['baseline:101', 'candidate:202']


@pytest.mark.parametrize('cycle,repeat', [(0, 200), (1, 8000), (5, 100000)])
def test_all_complete_callbacks_repeat_with_order_crossover_and_no_extra_sync(native, cycle, repeat):
    result, messages = run(native, 'confirmation', repeat, cycle)
    assert result.returncode == 0, result.stderr
    study.validate(messages, 'confirmation', cycle, repeat, 'fake_cpu_only')
    counts = json.loads(next(s[7:] for s in result.stdout.splitlines() if s.startswith('RESULT:')))
    assert counts['baseline_calls'] + counts['candidate_calls'] == 1222 + 30 * repeat
    assert counts['event_syncs'] == 30 and counts['record_events'] == 60
    assert counts['stream_syncs'] == 11
    assert study.controls([{'messages': messages}])['passed'] is True


@pytest.mark.parametrize('mode,repeat', [('pilot', 200), ('confirmation', 99), ('confirmation', 101), ('confirmation', 100100)])
def test_invalid_repeat_or_pilot_setting_fails_before_native_ready(native, mode, repeat):
    result, messages = run(native, mode, repeat)
    assert result.returncode != 0 and messages == []


def test_pilot_missing_or_reordered_sample_cannot_finish(native):
    commands = study.commands('pilot')
    commands[2] = commands[1]
    result, messages = run(native, 'pilot', 100, commands=commands)
    assert result.returncode != 0 and not any(m['kind'] == 'complete' for m in messages)


def test_repeat_formula_once_median_keeps_all_three_values_and_never_clips():
    values = [.6, 1.4, .61]
    assert study.calibrated_repeat(values) == 8200
    assert values == [.6, 1.4, .61]
    assert study.calibrated_repeat([51, 52, 53]) == 100
    with pytest.raises(ValueError, match='cap'):
        study.calibrated_repeat([.01, .02, .03])
    with pytest.raises(ValueError, match='three'):
        study.calibrated_repeat([.6, .6])


def test_all_samples_affect_controls_and_49ms_does_not_trigger_recalibration(native):
    result, messages = run(native, 'confirmation', 8000)
    assert result.returncode == 0
    for message in messages:
        if message['kind'] == 'pair':
            for role in study.ROLES:
                message[role]['elapsed_ms'] = 49
    assert study.controls([{'messages': messages}])['passed'] is True
    messages[2]['baseline']['elapsed_ms'] = 100
    assert study.controls([{'messages': messages}])['passed'] is False
    changed = copy.deepcopy(messages)
    changed[2]['order'] = ['candidate', 'baseline']
    with pytest.raises(ValueError, match='order'):
        study.validate(changed, 'confirmation', 0, 8000, 'fake_cpu_only')


def test_replay_rejects_failed_last_cycle_even_if_aggregate_controls_pass(native, tmp_path, monkeypatch):
    receipts = []
    for cycle in range(6):
        result, messages = run(native, 'confirmation', 100, cycle)
        assert result.returncode == 0
        if cycle == 5:
            messages[2]['baseline']['elapsed_ms'] = 1.2
        receipts.append({'mode': 'confirmation', 'cycle': cycle, 'repeat': 100, 'operator': 'exp',
                         'case_id': 6, 'started_at': 10, 'messages': messages})
    assert study.controls(receipts)['passed'] is True
    assert study.controls([receipts[-1]])['passed'] is False
    row = {'status': 'complete_research_controls_passed', 'overall': study.controls(receipts),
           'cycles': [{'receipt': {'index': i}, 'controls': study.controls([r])} for i, r in enumerate(receipts)]}
    rows = {f'{op}-{case_id}': {'status': 'not_run'} for op, ids in study.ORDER.items() for case_id in ids}
    rows['exp-6'] = row
    (tmp_path / 'confirmation-terminal.json').write_text(json.dumps({'rows': rows}))
    monkeypatch.setattr(study, 'verify_plan', lambda *args, **kwargs: {})
    monkeypatch.setattr(study, 'replay_pilot', lambda *args: {'created_at': 1, 'repeats': {'exp-6': 100}})
    monkeypatch.setattr(study, 'replay_receipt', lambda reference, **kwargs: receipts[reference['index']])
    with pytest.raises(ValueError, match='individual-cycle'):
        study.replay(tmp_path, tmp_path / 'unused-anchor')


@pytest.mark.parametrize('wrong_command', [False, True])
def test_replay_binds_native_case_and_requires_both_oracles(tmp_path, wrong_command):
    directory = tmp_path / 'exp/case-06/pilot'
    directory.mkdir(parents=True)
    command = ['/bound/native', '--input', '/bound/input6', '--output', '{cycle_dir}/final.bin']
    receipt = {'operator': 'exp', 'case_id': 6, 'mode': 'pilot', 'cycle': 0, 'verifications': {},
               'argv': [v.replace('{cycle_dir}', str(directory)) for v in command]}
    if wrong_command:
        receipt['argv'][2] = '/other/input9'
    study.save_new(directory / 'receipt.json', receipt)
    plan = {'cases': {'exp': [{'case_id': 6, 'command': command}]}}
    with pytest.raises(ValueError, match='command or case' if wrong_command else 'both independent'):
        study.replay_receipt(study.binding(directory / 'receipt.json'), plan=plan, output=tmp_path)
