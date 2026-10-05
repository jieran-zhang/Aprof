"""Synthetic finalized records exercise reporting, without device execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/summarize_level1_lessons.py'
SPEC = importlib.util.spec_from_file_location('summarize_level1_lessons', SCRIPT)
lessons = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lessons)
OPERATORS = ['foreach_norm', 'exp', 'masked_scale', 'foreach_addcdiv_scalar', 'mish', 'sigmoid', 'gelu']


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False))


def cas(run, split, value):
    data = json.dumps(value, sort_keys=True).encode()
    digest = 'sha256:' + hashlib.sha256(data).hexdigest()
    path = lessons.cas_path(run, split, digest)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return digest


def measurement():
    return {'stable': False, 'reasons': ['case 8 candidate CV exceeds limit'],
        # Deliberately different from the equal-case descriptive ratio.
        'speedup': None, 'speedup_lcb_95': None, 'per_case': [
            {'case_id': 1, 'speedup': 2.0, 'regression': -0.5, 'pair_count': 1,
                'baseline_cv': 0.01, 'candidate_cv': 0.02,
                'baseline_median_ns': 200, 'candidate_median_ns': 100},
            {'case_id': 8, 'speedup': 0.5, 'regression': 1.0, 'pair_count': 3,
                'baseline_cv': 0.03, 'candidate_cv': 0.20,
                'baseline_median_ns': 10000, 'candidate_median_ns': 20000}]}


def campaign(tmp_path, *, full=False, count=2):
    run = tmp_path / 'synthetic-finalized-run'
    operators = OPERATORS if full else ['exp']
    save(run / 'run-manifest.json', {'operators': operators, 'validation_operators': ['gelu'],
        'sentinel_case_ids': [1, 8, 14, 20]})
    save(run / 'setup/platform_capacity.json', {'soc': 'Ascend910_9392',
        'ub_bytes': 196352, 'aiv': 48, 'aic': 24})
    for op in operators:
        split = 'validation' if op == 'gelu' else 'train'
        task = run / 'tasks' / op
        n = (6 if op == 'exp' else 3) if full else count
        baseline = cas(run, split, {'kind': 'source', 'operator': op, 'baseline': True})
        fingerprint = cas(run, split, {'host': 'recorded-host', 'soc': 'Ascend910_9392'})
        traces = []
        for index in range(1, n + 1):
            cid = f'{op}-{index:03d}'
            directory = task / f'candidates/{index:03d}'
            source = cas(run, split, {'source': cid})
            patch = cas(run, split, {'patch': cid})
            plan = {'candidate_id': cid, 'handler_id': 'exp.attribute_identity_dispatch',
                'parameters': {'tile': 4096, 'dtype': 'runtime'},
                'missing_evidence': ['Missing overlap counter; duration alone cannot establish overlap.']}
            save(directory / 'candidate_plan.json', plan)
            save(directory / 'mechanism_binding.json', {'candidate_id': cid, 'status': 'inconclusive',
                'reason': 'Mixed supported/refuted/missing predictions.', 'comparisons': [
                    {'case_id': 1, 'name': 'Scalar_time', 'unit': 'ns', 'baseline_value': 30,
                        'candidate_value': 20, 'expected_direction': 'decrease',
                        'status': 'supported', 'reason': 'Observed expected counter direction.'},
                    {'case_id': 8, 'name': 'MTE2_time', 'unit': 'ns', 'baseline_value': 10,
                        'candidate_value': 12, 'expected_direction': 'decrease',
                        'status': 'refuted', 'reason': 'Opposite direction.', 'limitation': 'Tail-sensitive case.'},
                    {'case_id': 14, 'name': 'overlap', 'unit': None, 'baseline_value': None,
                        'candidate_value': None, 'expected_direction': 'increase',
                        'status': 'inconclusive', 'reason': 'Profiler does not export overlap.'}]})
            result = {'verdict': 'measurement_unstable', 'first_failed_stage': 'timing',
                'speedup': None, 'speedup_lcb': None, 'max_regression': None}
            traces.append({'identity': {'candidate_id': cid, 'attempt_id': cid,
                    'operator': op, 'split': split, 'run_id': run.name},
                'provenance': {'baseline_source_hash': baseline, 'candidate_source_hash': source,
                    'patch_hash': patch},
                'intervention': {'handler': {'id': plan['handler_id']}, 'intent': 'Frozen intervention',
                    'rationale': 'Frozen hypothesis', 'parameters': plan['parameters']},
                'workload': {'dtypes': ['float32', 'float16'], 'shapes': [[17], [4097]],
                    'attributes': {'scale': [0, 1]}, 'layouts': ['ND'], 'case_ids': list(range(1, 21)),
                    'accuracy_contract': 'unchanged verifier', 'hardware_fingerprint': fingerprint},
                'diagnosis': {'symptoms': ['A source-level performance hypothesis.'],
                    'missing_evidence': ['No formal pipeline overlap metric.']},
                'routing': {'mode': 'exploration', 'coverage_gap': 'Frozen graph has no matching handler route.'},
                'validation': {'build': {'status': 'passed'}, 'correctness': {'status': 'passed'},
                    'timing': {'status': 'failed', 'reason': 'Unstable paired timing.'},
                    'profile': {'status': 'passed'}, 'case_count': 20, 'passed_count': 20},
                'result': result,
                'lesson': {'status': 'inconclusive', 'effective_conditions': [],
                    'ineffective_conditions': ['MTE2 counter refutes the predicted direction.'],
                    'counterexamples': ['case 8 slowed down'], 'limitations': ['Evidence only covers frozen workload.'],
                    'next_step': 'Resolve timing noise and missing overlap evidence before attribution.'},
                'null_reasons': {'$.result.speedup': 'No admitted stable all20 timing reaches the performance gate.',
                    '$.result.speedup_lcb': 'No admitted stable all20 timing reaches the performance gate.'}})
            for phase in ('search', 'final'):
                save(task / f'timing/{phase}/{index:03d}/measurement_report.json', measurement())
                save(task / f'timing/{phase}/{index:03d}/raw_measurements.json', {'records': []})
            # Logical device zero is intentionally different from physical 14.
            save(task / f'executions/{index:03d}/final-timing-case-01/execution.json',
                {'host': 'recorded-host', 'physical_device': 14, 'job': {'device': 0}})
        save(task / 'frozen-roster.json', {'candidates': [{'candidate_id': row['identity']['candidate_id']} for row in traces]})
        (task / 'optimization_traces.jsonl').write_text('\n'.join(json.dumps(row) for row in traces) + '\n')
        selection = {'candidate_id': None, 'source_hash': baseline, 'reason': 'No qualified gain.',
            'source_directory': str(task / 'best_source'), 'graph_policy_eligible': False, 'verdict': 'baseline_retained'}
        save(task / 'best_source_selection.json', selection)
        save(task / 'finalization_report.json', {'status': 'completed', 'attempt_count': n,
            'attempts': [{'candidate_id': row['identity']['candidate_id'], **row['result'],
                'lesson_status': row['lesson']['status']} for row in traces], 'best_source': selection})
    return run


def rewrite_trace(run, index, mutate):
    task = run / 'tasks/exp'
    path = task / 'optimization_traces.jsonl'
    traces = lessons.rows(path)
    mutate(traces[index])
    path.write_text('\n'.join(json.dumps(row) for row in traces) + '\n')
    final = lessons.read(task / 'finalization_report.json')
    final['attempts'][index].update(traces[index]['result'])
    final['attempts'][index]['lesson_status'] = traces[index]['lesson']['status']
    save(task / 'finalization_report.json', final)
    return traces[index]


def snapshots(run):
    return {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in run.rglob('*') if path.is_file()}


def test_all_24_attempts_separate_splits_preserve_evidence_and_inputs(tmp_path):
    run = campaign(tmp_path, full=True)
    before = snapshots(run)
    text = lessons.render(run)
    assert snapshots(run) == before
    assert '7 个算子、24 个冻结尝试' in text
    assert 'train（训练）：6 个算子，21 次尝试' in text
    assert 'validation（独立验证）：1 个算子，3 次尝试' in text
    assert '性能问题（假设） | 干预 | 证据 | 适用条件 | 实测结果' in text
    for op in OPERATORS:
        for index in range(1, (6 if op == 'exp' else 3) + 1):
            assert text.count(f'**{op}-{index:03d} 的证据与反证**') == 1
    assert '生产范围 0 个，仅基准范围 0 个' in text
    assert 'supported=0，refuted=0，inconclusive=24' in text
    assert 'recorded-host/物理设备14' in text and '物理设备0' not in text
    assert 'Ascend910_9392' in text and '196352' in text
    assert '图覆盖缺口：Frozen graph has no matching handler route.' in text
    assert 'refuted：Opposite direction.；Tail-sensitive case.' in text
    assert '未知：Profiler does not export overlap.' in text
    assert '后续方向（归档记录）' in text
    assert '正确性通过/总 case：20/20' in text
    assert text.count('冻结工作负载：') == 7 and '4097' in text
    assert str(run / 'validation/episodes.sqlite.objects/sha256') in text
    assert str(run / 'tasks/exp/timing/final/001/raw_measurements.json') in text


def test_equal_case_observation_keeps_noise_regressions_and_null_gate_distinct(tmp_path):
    run = campaign(tmp_path)
    text = lessons.render(run, 2, 1)
    assert '观测几何比 1×（2/2 case）' in text
    assert 'case 8 最低 0.5×，case 1 最高 2×' in text
    assert '最大 CV 基线/候选 3%/20%' in text
    assert '配对数 1–3' in text
    assert '最差有符号回归 case 8=100%' in text
    assert '变慢 1 个，超过 3% 共 1 个：case 8 100%' in text
    assert '禁止作为合格收益' in text
    assert '门禁 speedup=未知：No admitted stable all20 timing reaches the performance gate.' in text
    assert '机器交付：基线' in text
    assert '合格收益 1' not in text


def test_renderer_echoes_machine_selection_without_reranking(tmp_path):
    run = campaign(tmp_path)
    task = run / 'tasks/exp'
    def gain(trace):
        trace['result'].update(verdict='benchmark_specialized_gain', first_failed_stage='production_safety',
            speedup=1.08, speedup_lcb=1.03, max_regression=.01)
        trace['lesson']['status'] = 'supported'
    chosen = rewrite_trace(run, 0, gain)
    # The other raw observation is much faster, but fails the machine gate.
    report = measurement()
    for case in report['per_case']:
        case['speedup'] = 10
        case['regression'] = -.9
    save(task / 'timing/final/002/measurement_report.json', report)
    selection = lessons.read(task / 'best_source_selection.json')
    selection.update(candidate_id='exp-001', source_hash=chosen['provenance']['candidate_source_hash'],
        verdict='benchmark_specialized_gain', reason='Final machine selection.')
    save(task / 'best_source_selection.json', selection)
    final = lessons.read(task / 'finalization_report.json')
    final['best_source'] = selection
    save(task / 'finalization_report.json', final)
    text = lessons.render(run, 2, 1)
    assert '机器交付：exp-001；仅基准范围收益通过' in text
    assert '机器交付：exp-002' not in text
    assert '生产范围 0 个，仅基准范围 1 个' in text
    assert '合格收益 1.08×' in text and 'LCB=1.03' in text
    assert '观测几何比 10×' in text
    # Preserve the distinction between machine lesson and measured mechanism set.
    assert '经验 supported；机制集 inconclusive' in text


@pytest.mark.parametrize('failure', ['unfinished', 'missing_attempt', 'duplicate_roster', 'selection', 'verdict', 'parameters', 'missing_raw'])
def test_incomplete_or_conflicting_archive_is_rejected(tmp_path, failure):
    run = campaign(tmp_path)
    task = run / 'tasks/exp'
    if failure == 'unfinished':
        path = task / 'finalization_report.json'
        value = lessons.read(path)
        value['status'] = 'in_progress'
    elif failure == 'missing_attempt':
        path = task / 'optimization_traces.jsonl'
        path.write_text(json.dumps(lessons.rows(path)[0]) + '\n')
    elif failure == 'duplicate_roster':
        path = task / 'frozen-roster.json'
        value = lessons.read(path)
        value['candidates'].append(value['candidates'][0])
    elif failure == 'selection':
        path = task / 'best_source_selection.json'
        value = lessons.read(path)
        value['candidate_id'] = 'exp-002'
    elif failure == 'verdict':
        path = task / 'finalization_report.json'
        value = lessons.read(path)
        value['attempts'][0]['verdict'] = 'production_safe_gain'
    elif failure == 'parameters':
        path = task / 'candidates/001/candidate_plan.json'
        value = lessons.read(path)
        value['parameters']['tile'] = 8192
    else:
        path = task / 'timing/final/001/raw_measurements.json'
        path.unlink()
    if failure not in ('missing_attempt', 'missing_raw'):
        save(path, value)
    with pytest.raises(ValueError):
        lessons.render(run, 2, 1)
    assert not (run / 'optimization_lessons.md').exists()


def test_cas_integrity_and_explicit_unknown_hardware(tmp_path):
    run = campaign(tmp_path)
    trace = rewrite_trace(run, 0, lambda row: row['workload'].update(hardware_fingerprint=None))
    text = lessons.render(run, 2, 1)
    assert '平台指纹：未知（未记录平台分母）' in text
    path = lessons.cas_path(run, 'train', trace['provenance']['candidate_source_hash'])
    path.write_bytes(b'changed source artifact')
    with pytest.raises(ValueError, match='bytes differ'):
        lessons.render(run, 2, 1)
    path.unlink()
    with pytest.raises(ValueError, match='artifact is missing'):
        lessons.render(run, 2, 1)


def test_empty_blocked_aggregate_is_not_invented_as_zero_or_gain(tmp_path):
    run = campaign(tmp_path)
    task = run / 'tasks/exp'
    save(task / 'timing/final/001/measurement_report.json',
        {'stable': False, 'per_case': [], 'reasons': ['Calibration blocked; no candidate hardware timing.']})
    rewrite_trace(run, 0, lambda row: row['validation']['timing'].update(
        status='not_run', reason='No final timing execution; empty aggregate preserves skipped cases.'))
    text = lessons.render(run, 2, 1)
    assert '最终：未知：Calibration blocked; no candidate hardware timing.' in text
    assert '未执行阶段：timing=not_run：No final timing execution' in text
    assert '观测几何比 0×' not in text


def test_hardware_separates_correctness_from_unexecuted_timing(tmp_path):
    task = tmp_path / 'task'
    save(task / 'executions/006/correctness/execution.json',
        {'host': 'decode', 'physical_device': 14, 'job': {'device': 0}})
    save(task / 'executions/006/build/execution.json', {'host': 'decode', 'physical_device': None})
    text = lessons.hardware(task, '006')
    assert '正确性：decode/物理设备14' in text
    assert '没有实际计时执行设备记录' in text
    assert '物理设备0' not in text and '物理设备None' not in text


def test_cli_writes_only_report_and_preserves_different_existing_output(tmp_path):
    run = campaign(tmp_path)
    before = snapshots(run)
    command = [sys.executable, str(SCRIPT), '--run', str(run), '--expected-attempts', '2', '--expected-operators', '1']
    completed = subprocess.run(command, text=True, capture_output=True)
    assert completed.returncode == 0, completed.stderr
    output = run / 'optimization_lessons.md'
    receipt = json.loads(completed.stdout)
    assert receipt['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
    after = snapshots(run)
    assert {key: value for key, value in after.items() if key != str(output)} == before
    output.write_text('existing reviewer notes\n')
    refused = subprocess.run(command, text=True, capture_output=True)
    assert refused.returncode != 0
    assert 'refusing to overwrite' in refused.stderr
    assert output.read_text() == 'existing reviewer notes\n'


@pytest.mark.parametrize('value', [float('nan'), float('inf'), 0, -1, True])
def test_invalid_observed_ratio_is_rejected(value):
    with pytest.raises(ValueError):
        lessons.observed({'per_case': [{'case_id': 1, 'speedup': value}]})
