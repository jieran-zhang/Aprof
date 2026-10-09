from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
import run_level1_exp_special_values as helper
from collect_level1_traces import Campaign
from aprof_runtime.traces import verify_trace


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + '\n')


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    run = tmp_path / 'run'
    dump(run / 'run-manifest.json', {'operators': ['exp'], 'validation_operators': []})
    campaign = Campaign(run)
    task = campaign.task('exp')
    binary = task / 'candidates/006/op/build/exp'
    binary.parent.mkdir(parents=True)
    binary.write_text('never executed: mocked hardware only')
    generator = task / 'qualify_zero_affine.py'
    generator.write_text('never executed: mocked verifier only')
    root = task / 'qualification/zero_affine'
    entries, stages = [], []
    for dtype in ('float32', 'float16', 'bfloat16'):
        for length in (17, 4097, 196673):
            case_id = f'zero-affine-{dtype}-n{length}'
            directory = root / case_id
            directory.mkdir(parents=True)
            inputs = {}
            hashes = {}
            for key, name in [('input', 'input.bin'), ('expected_numpy', 'expected_numpy.bin'),
                              ('expected_torch', 'expected_torch.bin')]:
                path = directory / name
                path.write_bytes(b'fixture-correctness-bytes')
                inputs[key] = str(path)
                hashes[name] = helper.file_hash(path)
            metadata = {'candidate_id': 'exp-006', 'case_id': case_id, 'dtype': dtype,
                'numel': length, 'base': -1, 'scale': 0, 'shift': 0,
                'output': str(directory / 'output.bin'), 'sha256': hashes, **inputs}
            mp = directory / 'metadata.json'
            dump(mp, metadata)
            entries.append({'case_id': case_id, 'metadata': str(mp)})
            stages.append({'name': case_id, 'timeout_seconds': 120, 'commands': [
                [str(binary), '--numel', str(length), '--dtype', dtype, '--input', inputs['input'],
                 '--output', metadata['output'], '--base', '-1', '--scale', '0', '--shift', '0', '--device', '0'],
                [helper.QUALIFIED_PYTHON, str(generator), 'verify', '--metadata', str(mp)]]})
    dump(root / 'execution_plan.json', {'candidate_id': 'exp-006', 'case_count': 9,
        'candidate_binary': str(binary), 'generator': {'path': str(generator), 'sha256': helper.file_hash(generator)},
        'cases': entries, 'stages': stages})
    monkeypatch.setattr(campaign, 'verify_source_identity', lambda *args: {})
    return campaign, root


class Jobs:
    """Simulate completed process reports while using the real Campaign.record/CAS."""
    def __init__(self, campaign, monkeypatch, failure=None):
        self.campaign, self.failure, self.calls = campaign, failure, []
        monkeypatch.setattr(campaign, 'job', self.run)

    def run(self, op, stage, argv, *, cwd, host, device, timeout):
        directory = self.campaign.task(op) / 'executions' / stage
        checkpoint = directory / 'execution.json'
        if checkpoint.exists():
            return helper.read(checkpoint)
        self.calls.append((stage, argv, host, device))
        phase = stage.split('/')[-1]
        failed = self.failure and self.failure(stage, phase)
        if failed == 'transport':
            dump(directory / 'transport-failure.json', {'error': 'mock transport unavailable'})
            raise RuntimeError('mock transport unavailable')
        directory.mkdir(parents=True, exist_ok=True)
        output = Path(argv[argv.index('--output') + 1])
        output.parent.mkdir(parents=True, exist_ok=True)
        if phase == 'launch':
            output.write_bytes(b'candidate result including partial failed output')
        else:
            metadata = helper.read(argv[argv.index('--metadata') + 1])
            dump(Path(argv[argv.index('--report') + 1]), {'case_id': metadata['case_id'],
                'candidate_id': 'exp-006', 'output': str(output), 'passed': not failed})
        stdout, stderr = directory / 'stdout.log', directory / 'stderr.log'
        stdout.write_text('mock command completed\n')
        stderr.write_text('mock error\n' if failed else '')
        exit_code = 2 if failed and failed != 'false_observation' else 0
        report = {'schema_version': '1.0.0', 'kind': 'aprof_execution_report',
            'job': {'job_id': 'exp-' + stage.replace('/', '-'), 'argv': argv,
                'cwd': str(cwd), 'output_dir': str(directory), 'timeout_seconds': timeout,
                'environment': {}, **({'physical_device': device} if device is not None else {})},
            'host': host, 'physical_device': device, 'started_at': '2026-09-07T00:00:00Z',
            'finished_at': '2026-09-07T00:00:01Z', 'exit_code': exit_code,
            'status': 'failed' if exit_code else 'passed',
            'stdout': {'path': str(stdout)}, 'stderr': {'path': str(stderr)}}
        dump(checkpoint, report)
        return report


def test_dry_run_is_read_only_and_removes_actual_inherited_timing_environment(prepared):
    campaign, root = prepared
    result = helper.run(campaign, physical_device=7)
    assert result['status'] == 'dry_run' and not (root / 'attempts').exists()
    env = os.environ.copy()
    env.update({key: 'must disappear' for key in helper.TIMING_VARIABLES})
    command = helper.without_timing([sys.executable, '-c',
        'import os,json; print(json.dumps({k:v for k,v in os.environ.items() if k.startswith("APROF_")}))'])
    # This subprocess only inspects CPU environment; it does not import/launch NPU code.
    observed = json.loads(subprocess.check_output(command, env=env, text=True))
    assert not any(key in observed for key in helper.TIMING_VARIABLES)
    first = result['manifest']['cases'][0]
    assert first['launch_argv'][-1] == '0'
    assert helper.QUALIFIED_PYTHON in first['verify_argv']


def test_success_records_all_jobs_outputs_and_idempotent_summary(prepared, monkeypatch):
    campaign, root = prepared
    jobs = Jobs(campaign, monkeypatch)
    result = helper.run(campaign, physical_device=7, execute=True)
    assert result['status'] == 'passed'
    assert result['case_count'] == result['attempted_count'] == result['passed_count'] == 9
    assert len(jobs.calls) == 18
    for stage, argv, _, device in jobs.calls:
        assert argv[:11] == helper.without_timing([])
        assert device == (7 if stage.endswith('/launch') else None)
    with campaign.store('exp') as store:
        assert verify_trace(campaign.task('exp') / 'trace_events.jsonl', store)['event_count'] == 20
        for case in result['cases']:
            for ref in case['artifact_refs'] + [case['case_validation_ref']]:
                store.verify_artifact(ref)
    assert helper.run(campaign, physical_device=7, execute=True) == result
    assert len(jobs.calls) == 18
    assert helper.read(root / 'hardware_validation.json') == result


def test_failed_launch_stops_before_verifier_and_retry_preserves_first_attempt(prepared, monkeypatch):
    campaign, root = prepared
    jobs = Jobs(campaign, monkeypatch, lambda stage, phase: phase == 'launch' and 'n4097/' in stage)
    failed = helper.run(campaign, execute=True)
    assert failed['status'] == 'failed' and failed['attempted_count'] == 2 and failed['passed_count'] == 1
    assert len(jobs.calls) == 3
    assert failed['cases'][-1]['verify'] is None and failed['cases'][-1]['output_ref']
    original = (root / 'attempts/001/hardware_validation.json').read_bytes()
    assert helper.run(campaign, execute=True) == failed
    assert len(jobs.calls) == 3
    jobs.failure = None
    passed = helper.run(campaign, attempt='002', execute=True)
    assert passed['status'] == 'passed'
    assert (root / 'attempts/001/hardware_validation.json').read_bytes() == original
    assert helper.read(root / 'hardware_validation.json')['attempt'] == '002'


@pytest.mark.parametrize('failure', [True, 'false_observation'])
def test_verification_failure_is_recorded_and_never_bypassed(prepared, monkeypatch, failure):
    campaign, root = prepared
    jobs = Jobs(campaign, monkeypatch, lambda stage, phase: failure if phase == 'verify' else False)
    result = helper.run(campaign, execute=True)
    assert result['status'] == 'failed' and result['attempted_count'] == 1
    assert result['passed_count'] == 0 and len(jobs.calls) == 2
    assert result['cases'][0]['observation_ref'] and result['cases'][0]['output_ref']
    with campaign.store('exp') as store:
        assert verify_trace(campaign.task('exp') / 'trace_events.jsonl', store)['valid']


def test_transport_failure_has_cas_summary_and_stops_future_cases(prepared, monkeypatch):
    campaign, root = prepared
    jobs = Jobs(campaign, monkeypatch, lambda stage, phase: 'transport')
    result = helper.run(campaign, execute=True)
    assert result['status'] == 'interrupted' and result['attempted_count'] == 1
    assert len(jobs.calls) == 1
    assert 'transport unavailable' in result['first_failure']['reason']
    assert len(result['cases'][0]['artifact_refs']) == 2
    assert (root / 'hardware_validation.json').exists()


def test_changed_prepared_input_is_rejected_before_any_execution(prepared, monkeypatch):
    campaign, root = prepared
    jobs = Jobs(campaign, monkeypatch)
    entry = helper.read(root / 'execution_plan.json')['cases'][0]
    Path(helper.read(entry['metadata'])['input']).write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash changed'):
        helper.run(campaign, execute=True)
    assert jobs.calls == []
