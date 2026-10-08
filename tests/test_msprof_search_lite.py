"""CPU evidence replay and compiled fake ACL; never imports an NPU runtime."""
import copy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import cannbench_msprof_timing as timing
import msprof_exploration_report as report
from msprof_search_protocol import LITE_PROTOCOL, LITE_ANALYSIS, LITE_PRODUCER, LITE_DESIGN
from test_msprof_exploration_report import setup_inputs, make_session, make_cohort, data, put


def lite_cohort(tmp_path, ratios=(1.2, 1.22)):
    request, build = setup_inputs(tmp_path, ids=(1, 8), kind='ab', search_lite=True)
    plan = {'protocol': LITE_PROTOCOL, 'analysis_version': LITE_ANALYSIS,
            'comparison_kind': 'ab', 'case_ids': [1, 8],
            'calibration_scope': {'epoch': 'lite-test'}, 'schedule': []}
    directories = []
    for number, design in enumerate(LITE_DESIGN):
        req = copy.deepcopy(request)
        req.update(zip(('load_order', 'first_order', 'buffer_configs'), design))
        name = f'p{number + 1:02d}'
        plan['schedule'].append({'name': name, 'request': req})
        directories.append(make_session(tmp_path, req, build, number, ratios[number], name=name))
    return directories, plan


def test_lite_full_evidence_replay_counts_and_descriptive_uncertainty(tmp_path):
    directories, plan = lite_cohort(tmp_path)
    result = report.analyze_task_cohort(directories, plan)
    assert result['protocol'] == LITE_PROTOCOL
    assert result['analysis_version'] == LITE_ANALYSIS
    assert len(result['sessions']) == 2
    assert result['graph_policy_eligible'] is False and result['episode_ref'] is None
    assert result['formal_admission'] == 'not_evaluated'
    for row in result['results']:
        assert row['speedup'] == pytest.approx(math.sqrt(1.2 * 1.22))
        assert row['ci95'] is None and row['df'] is None
        assert row['observed_process_range'] == pytest.approx([1.2, 1.22])
        assert row['qualified_performance_eligible'] is False
        assert row['additive_factors']['support'] == 'not_estimable_two_process_design'
    for directory in directories:
        parsed = report.load(directory / 'samples.json')
        # Two cases, two configurations, six AB pairs, ten complete calls.
        assert len(parsed['samples']) == 2 * 2 * 6 * 2
        assert parsed['warmup_tasks_excluded'] == 2 * 2 * 10 * 2
        assert parsed['target_tasks'] == 2 * 2 * (10 + 6 * 10) * 2
        assert parsed['version'] == LITE_PRODUCER
    producer = timing.summarize(directories)
    assert producer['version'] == LITE_PRODUCER
    assert all(row['ci95'] is None for row in producer['results'])


@pytest.mark.parametrize('change', ['extra_process', 'legacy_label', 'wrong_pairs', 'output', 'samples'])
def test_lite_rejects_mixed_design_or_tampered_evidence(tmp_path, change):
    directories, plan = lite_cohort(tmp_path)
    if change == 'extra_process':
        plan['schedule'].append(copy.deepcopy(plan['schedule'][0]))
    elif change == 'legacy_label':
        plan.update(protocol=report.PROTOCOL_V2, analysis_version=report.ANALYSIS_V2)
    elif change == 'wrong_pairs':
        path = directories[0] / 'native/journal.jsonl'
        path.write_text(path.read_text().replace('"pairs": 6', '"pairs": 30'))
    elif change == 'output':
        (directories[0] / 'native/1_normal_A.bin').write_bytes(b'tampered output')
    else:
        path = directories[0] / 'samples.json'; value = report.load(path)
        value['samples'][0]['task_us'] *= 2; put(path, value)
    with pytest.raises(ValueError):
        report.analyze_task_cohort(directories, plan)


def test_in_process_cache_reuses_full_verification_but_external_replay_does_not(tmp_path, monkeypatch):
    directories, plan = lite_cohort(tmp_path)
    actual_verify = report.verify_observation
    calls = []
    def counted(*args, **kwargs):
        calls.append(str(args[0]))
        return actual_verify(*args, **kwargs)
    monkeypatch.setattr(report, 'verify_observation', counted)
    cache = report.ObservationCache()
    for directory, entry in zip(directories, plan['schedule']):
        cache.verify(directory, entry['request'])
    cached = report.analyze_task_cohort(directories, plan, _verified_sessions=cache)
    assert len(calls) == 2
    assert report.analyze_task_cohort(directories, plan) == cached
    assert len(calls) == 4
    with pytest.raises(ValueError, match='in-process observation cache'):
        report.analyze_task_cohort(directories, plan, _verified_sessions=cached['sessions'])
    path = directories[0] / 'native/1_normal_A.bin'
    old = path.stat()
    path.write_bytes(b'x' * old.st_size)
    os.utime(path, ns=(old.st_atime_ns, old.st_mtime_ns))
    with pytest.raises(ValueError, match='changed after in-process verification'):
        report.analyze_task_cohort(directories, plan, _verified_sessions=cache)
    with pytest.raises(ValueError, match='output hash'):
        report.analyze_task_cohort(directories, plan)


def test_cache_keeps_legacy_report_exact(tmp_path):
    directories, plan = make_cohort(tmp_path, ids=(1,))
    full = report.analyze_task_cohort(directories, plan)
    cache = report.ObservationCache()
    for directory, entry in zip(directories, plan['schedule']):
        cache.verify(directory, entry['request'])
    assert report.analyze_task_cohort(directories, plan, _verified_sessions=cache) == full
    assert all(row['df'] == 5 and row['ci95'] is not None for row in full['results'])


def test_cohort_collector_full_verifies_each_process_only_once(tmp_path, monkeypatch):
    import msprof_exploration_execute as execute
    request, build = setup_inputs(tmp_path / 'inputs', ids=(1,), kind='ab', search_lite=True)
    plan = {'protocol': LITE_PROTOCOL, 'analysis_version': LITE_ANALYSIS,
            'comparison_kind': 'ab', 'case_ids': [1],
            'calibration_scope': {'epoch': 'collector-test'}, 'schedule': []}
    for number, design in enumerate(LITE_DESIGN):
        req = copy.deepcopy(request)
        req.update(zip(('load_order', 'first_order', 'buffer_configs'), design))
        plan['schedule'].append({'name': f'p{number + 1:02d}', 'request': req})
    calls = []
    def collect(request_path, directory):
        number = len(calls); calls.append('collect')
        make_session(directory.parent, report.load(request_path), build, number, 1.2, name=directory.name)
    actual_verify = report.verify_observation
    verifications = []
    def verify(*args, **kwargs):
        verifications.append(str(args[0]))
        return actual_verify(*args, **kwargs)
    monkeypatch.setattr(report, 'verify_observation', verify)
    monkeypatch.setattr(execute, 'preflight_cohort', lambda plan: {'producer_bindings': []})
    monkeypatch.setattr(execute, 'execution_modules', lambda: (SimpleNamespace(collect=collect, summarize=timing.summarize), None, None))
    result = execute.collect_cohort(plan, tmp_path / 'cohort')
    assert len(calls) == len(verifications) == 2
    assert len(result['sessions']) == 2
    completion = report.load(tmp_path / 'cohort/group-completion.json')
    assert completion['status'] == 'passed'
    elapsed = completion['elapsed_seconds']
    assert len(elapsed['sessions']) == 2
    phases = ['identity_preflight', 'native_collection', 'observation_verification', 'report_analysis', 'producer_summary']
    assert all(elapsed[key] >= 0 for key in phases)
    assert elapsed['total'] >= sum(elapsed[key] for key in phases)
    # A separate consumer still verifies from source evidence, not report.json.
    report.analyze_task_cohort([tmp_path / 'cohort' / row['name'] for row in plan['schedule']], plan)
    assert len(verifications) == 4


def test_generated_lite_native_runner_executes_six_balanced_pairs_and_frozen_repeats(tmp_path):
    if not shutil.which('g++'):
        pytest.skip('g++ unavailable')
    from test_shared_context_native import FAKE_ACL, FAKE_ROLE
    data(tmp_path / 'acl/acl.h', FAKE_ACL.encode())
    data(tmp_path / 'role.cpp', FAKE_ROLE.encode())
    harness = ROOT / 'benchmarks/cannbench/harness/shared_context'
    generated = timing.instrument((harness / 'runner.cpp').read_text(), 10, per_case=True, search_lite=True)
    source = data(tmp_path / 'runner.cpp', generated.encode())
    subprocess.run(['g++', '-std=c++17', '-I' + str(tmp_path), '-I' + str(harness), source, '-ldl', '-o', str(tmp_path / 'runner')], check=True, capture_output=True)
    for role in 'AB':
        subprocess.run(['g++', '-std=c++17', '-shared', '-fPIC', '-Wl,-Bsymbolic', '-I' + str(harness), '-DROLE="' + role + '"', str(tmp_path / 'role.cpp'), '-o', str(tmp_path / (role + '.so'))], check=True, capture_output=True)
    (tmp_path / 'cases.tsv').write_text('1\t--numel\t1\t--aprof-repeat\t1\n2\t--numel\t1\t--aprof-repeat\t10\n')
    process = subprocess.run([str(tmp_path / 'runner'), '--role-a', str(tmp_path / 'A.so'), '--role-b', str(tmp_path / 'B.so'),
                              '--cases', str(tmp_path / 'cases.tsv'), '--output-dir', str(tmp_path / 'native'), '--session-id', 'fake-lite',
                              '--load-order', 'BA', '--first-order', 'BA', '--buffer-configs', 'swapped,normal'],
                             env={**os.environ, 'FAKE_ACL_LOG': str(tmp_path / 'acl.log')}, capture_output=True, text=True)
    assert process.returncode == 0, process.stderr
    records = [json.loads(line) for line in (tmp_path / 'native/journal.jsonl').read_text().splitlines()]
    assert all(row['timing_protocol'] == LITE_PRODUCER for row in records[:-1])
    for case, repeat in [('1', 1), ('2', 10)]:
        for config in ('normal', 'swapped'):
            samples = [row for row in records if row['type'] == 'sample' and row['case_id'] == case and row['buffer_config'] == config]
            assert len(samples) == 12
            assert [row['order'] for row in samples[::2]] == ['BA', 'AB'] * 3
            assert all(row['repeat'] == repeat for row in samples)
            for role in 'AB':
                assert (tmp_path / 'native' / f'{case}_{config}_{role}.bin').read_text() == str(10 + 6 * repeat)
    assert [row['complete_calls_since_prepare'] for row in records if row['type'] == 'output'] == [16] * 4 + [70] * 4
