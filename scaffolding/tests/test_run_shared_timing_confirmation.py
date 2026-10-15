"""Synthetic CPU-only regressions; these do not qualify a hardware protocol."""
import copy
import csv
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'skill-libs/graph-base/0.5.1/runtime/src'))
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import run_shared_timing_confirmation as confirmation
from test_device_shared_timing_header import executable, run as native_header_run

SPEC = importlib.util.spec_from_file_location('shared_fixture', Path(__file__).with_name('test_shared_measurement_admission.py'))
fixture = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(fixture)


def native_cycle(repeat=100):
    _, config = fixture.draft.__wrapped__()
    config['operator'] = 'exp'
    ready, events = fixture.wire(config, 0, repeat=repeat)
    return [ready, *[event['message'] for event in events]], config


def test_profiling_native_messages_use_same_physical_identity_state_machine():
    messages, config = native_cycle()
    confirmation.timeline_protocol(messages, config, 100)
    wrong = copy.deepcopy(messages); wrong[2]['stream_address'] = '3000'
    with pytest.raises(Exception, match='identity changed'):
        confirmation.timeline_protocol(wrong, config, 100)
    wrong = copy.deepcopy(messages); wrong[-1]['input_bytes_unchanged'] = False
    with pytest.raises(Exception, match='mutated input'):
        confirmation.timeline_protocol(wrong, config, 100)


def test_timeline_replays_all_six_real_native_cycles_and_rejects_wrong_cycle(executable):
    _, config = fixture.draft.__wrapped__()
    config['operator'] = 'fake_cpu_only'
    config['roles']['baseline'].update(symbol='launch_baseline', launches_per_operator=1)
    config['roles']['candidate'].update(symbol='launch_candidate', launches_per_operator=2)
    for cycle in range(6):
        execution, messages = native_header_run(executable, cycle=cycle)
        assert execution.returncode == 0, execution.stderr
        assert len(messages) == 20 and messages[0]['cycle_index'] == cycle
        confirmation.timeline_protocol(messages, config, 100, cycle=cycle)
        with pytest.raises(ValueError, match='READY cycle_index differs'):
            confirmation.timeline_protocol(messages, config, 100, cycle=(cycle + 1) % 6)


@pytest.mark.parametrize("repeat", [100, 300])
def test_independent_profile_partitions_all_tasks_and_preserves_gaps(tmp_path, repeat):
    messages, _ = native_cycle(repeat)
    table = tmp_path / 'op_summary.csv'
    with table.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=['Op Name', 'Task Start Time(us)', 'Task Duration(us)', 'Device_id', 'Task ID', 'Stream ID', 'Task Type'])
        writer.writeheader()
        for index in range(1222 + 30 * repeat):
            writer.writerow({'Op Name': 'exp_kernel', 'Task Start Time(us)': 1000 + index * 2, 'Task Duration(us)': 1,
                             'Device_id': '0', 'Task ID': index, 'Stream ID': '3', 'Task Type': 'AI_VECTOR_CORE'})
    spans = confirmation.timeline_spans(table, messages, 'exp')
    assert len(spans) == 30 and spans[0]['task_indices'] == [420, 420 + repeat]
    assert spans[-1]['task_indices'] == [1220 + 29 * repeat, 1220 + 30 * repeat]
    assert all(row['task_count'] == repeat and row['kernel_total_duration_ns'] == repeat * 1000
               and row['first_last_kernel_span_ns'] == (repeat * 2 - 1) * 1000 for row in spans)
    assert len([r for r in spans if r['implementation'] == 'candidate']) == 5
    table.write_text('\n'.join(table.read_text().splitlines()[:-1]) + '\n')
    with pytest.raises(ValueError, match='launch count'):
        confirmation.timeline_spans(table, messages, 'exp')


def test_identical_baseline_formal_bias_blocks_even_when_normal_ab_gate_passes(tmp_path, monkeypatch):
    directory = tmp_path / 'exp'; (directory / 'confirmation').mkdir(parents=True)
    (directory / 'config.json').write_text(json.dumps(dict(run_id='run', session_id='session', candidate_id='candidate', expected_case_ids=list(range(1, 21)))))
    (directory / 'confirmation/artifacts.json').write_text(json.dumps({'measurement_admission': 'sha256:fixture'}))
    (directory / 'confirmation/measurement_admission.json').write_text(json.dumps({'source_hashes': {'baseline': 'same', 'candidate': 'same'}}))
    sqlite3.connect(directory / 'evidence.sqlite').close()
    control = dict(overall={'formal': {'role_bias': 0.}}, cycles=[{'formal': {'role_bias': .03}}])
    result = {'valid': True, 'report': {'controls': [control]}}
    monkeypatch.setattr(confirmation, 'runtime_modules', lambda: (lambda *a, **k: result, None, None))
    with pytest.raises(ValueError, match='formal role bias'):
        confirmation.confirmation_admission(tmp_path, 'exp')
    control['cycles'][0]['formal']['role_bias'] = 0.
    assert confirmation.confirmation_admission(tmp_path, 'exp') == result


def test_metadata_amendment_cannot_change_workload_or_native_sources(tmp_path):
    old, new = tmp_path / 'old', tmp_path / 'new'
    old.mkdir(); new.mkdir()
    def put(path, value):
        path.write_text(json.dumps(value)); return str(path)
    old_plan = {'operators': {}}; old_frozen = {'configs': {}}; frozen = {'configs': {}}
    plan = {'operators': {}, 'predecessor': {'qualification_dir': str(old),
        'freeze_ref': {'path': str(old / 'freeze.json')},
        'amendment_ref': {'path': put(tmp_path / 'amendment.json', {'replacement_dir': str(new)})}}}
    for op in ('exp', 'sigmoid'):
        previous = {'run_id': 'old', 'session_id': 'old-' + op, 'binary': str(old / op),
                    'cases': [{'workload': {'shape': [4], 'dtype': 'float16', 'value_range': [float('-inf'), float('inf')]}}]}
        old_frozen['configs'][op] = put(old / (op + '.json'), previous)
        current = copy.deepcopy(previous); current.update(run_id='new', session_id='new-' + op, binary=str(new / op))
        current['cases'][0]['workload'] = confirmation.tagged_metadata(current['cases'][0]['workload'])
        frozen['configs'][op] = put(new / (op + '.json'), current)
        review = {'adapted_files': {'kernel.cpp': 'original'}, 'original_files': {'kernel.cpp': 'original'}}
        old_plan['operators'][op] = {'source_review': put(old / (op + '-source.json'), review)}
        plan['operators'][op] = {'source_review': put(new / (op + '-source.json'), review)}
    put(old / 'freeze.json', old_frozen); put(old / 'plan.json', old_plan)
    confirmation.verify_replacement_semantics(new, plan, frozen, confirmation.Evidence())
    changed = confirmation.read(frozen['configs']['exp']); changed['cases'][0]['workload']['shape'] = [8]
    put(Path(frozen['configs']['exp']), changed)
    with pytest.raises(ValueError, match='changed more than'):
        confirmation.verify_replacement_semantics(new, plan, frozen, confirmation.Evidence())
    changed['cases'][0]['workload']['shape'] = [4]; put(Path(frozen['configs']['exp']), changed)
    review = confirmation.read(plan['operators']['exp']['source_review']); review['adapted_files']['kernel.cpp'] = 'modified'
    put(Path(plan['operators']['exp']['source_review']), review)
    with pytest.raises(ValueError, match='modified native'):
        confirmation.verify_replacement_semantics(new, plan, frozen, confirmation.Evidence())
