#!/usr/bin/env python3
"""Record exp-006 special-value correctness qualification; default to dry-run.

Campaign.job delegates the physical-device lock and logical-device mapping to
run_aprof_job. Do not acquire that same device lock in this coordinator process.
"""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import re

from collect_level1_traces import Campaign, DEFAULT_RUN, WRITER_LOCK
from run_aprof_job import dump
from aprof_runtime.traces import register_json_artifact, utcnow

OPERATOR = 'exp'
CANDIDATE = 'exp-006'
QUALIFIED_PYTHON = '/usr/local/python3.11.15/bin/python3'
TIMING_VARIABLES = (
    'APROF_TIMING', 'APROF_TIMING_INTERACTIVE', 'APROF_WARMUP',
    'APROF_REPEAT', 'APROF_SAMPLES',
)


def read(path):
    return json.loads(Path(path).read_text())


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def without_timing(argv):
    return ['/usr/bin/env', *[part for key in TIMING_VARIABLES for part in ('-u', key)],
            *map(str, argv)]


def source(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': file_hash(path)}


def prepare(campaign, *, physical_device=0, host='local', attempt='001'):
    """Read and validate the prepared plan; no writes, jobs, or device access."""
    if not re.fullmatch(r'[A-Za-z0-9_-]+', attempt):
        raise ValueError('attempt must contain only letters, digits, underscores or hyphens')
    if type(physical_device) is not int or not 0 <= physical_device < 16:
        raise ValueError('physical_device must be an integer from 0 to 15')
    if host not in ('local', 'decode'):
        raise ValueError('host must be local or decode')
    task = campaign.task(OPERATOR)
    root = task / 'qualification/zero_affine'
    plan_path = root / 'execution_plan.json'
    plan = read(plan_path)
    binary = (task / 'candidates/006/op/build/exp').resolve()
    generator = (task / 'qualify_zero_affine.py').resolve()
    if (plan.get('candidate_id') != CANDIDATE or plan.get('case_count') != 9
            or len(plan.get('cases', [])) != 9 or len(plan.get('stages', [])) != 9):
        raise ValueError('expected the frozen nine-case exp-006 supplemental plan')
    if Path(plan['candidate_binary']).resolve() != binary:
        raise ValueError('prepared plan names a different candidate binary')
    if (Path(plan['generator']['path']).resolve() != generator
            or file_hash(generator) != plan['generator']['sha256']):
        raise ValueError('reference generator differs from the prepared plan')
    sources = [source(plan_path), source(generator), source(binary), source(__file__)]
    cases = []
    seen = set()
    for entry, stage in zip(plan['cases'], plan['stages']):
        case_id = entry['case_id']
        if case_id in seen or not re.fullmatch(r'[A-Za-z0-9_-]+', case_id):
            raise ValueError('duplicate or unsafe supplemental case identifier')
        seen.add(case_id)
        metadata_path = Path(entry['metadata']).resolve()
        if not metadata_path.is_relative_to(root.resolve()):
            raise ValueError('supplemental metadata is outside its prepared directory')
        metadata = read(metadata_path)
        if (stage.get('name') != case_id or metadata.get('case_id') != case_id
                or metadata.get('candidate_id') != CANDIDATE
                or metadata.get('dtype') not in ('float32', 'float16', 'bfloat16')
                or metadata.get('base') != -1 or metadata.get('scale') != 0
                or metadata.get('shift') != 0 or type(metadata.get('numel')) is not int
                or metadata['numel'] < 17):
            raise ValueError('supplemental case identity or zero-affine contract changed')
        sources.append(source(metadata_path))
        for key in ('input', 'expected_numpy', 'expected_torch'):
            path = Path(metadata[key]).resolve()
            if not path.is_relative_to(root.resolve()):
                raise ValueError('supplemental input/reference is outside the prepared directory')
            item = source(path)
            if item['sha256'] != metadata['sha256'][path.name]:
                raise ValueError('prepared input/reference hash changed: ' + str(path))
            sources.append(item)
        prepared_launch = [str(binary), '--numel', str(metadata['numel']), '--dtype', metadata['dtype'],
            '--input', metadata['input'], '--output', metadata['output'],
            '--base', '-1', '--scale', '0', '--shift', '0', '--device', '0']
        prepared_verify = [QUALIFIED_PYTHON, str(generator), 'verify', '--metadata', str(metadata_path)]
        if stage.get('commands') != [prepared_launch, prepared_verify]:
            raise ValueError('prepared stage commands differ from the verified metadata')
        directory = root / 'attempts' / attempt / 'cases' / case_id
        output = directory / 'output.bin'
        observation = directory / 'verification.json'
        launch = list(prepared_launch)
        launch[launch.index('--output') + 1] = str(output)
        # run_aprof_job exposes the selected physical device as logical zero.
        launch[launch.index('--device') + 1] = '0'
        verify = [*prepared_verify, '--output', str(output), '--report', str(observation)]
        cases.append({'case_id': case_id, 'metadata': str(metadata_path),
            'output': str(output), 'observation': str(observation),
            'launch_argv': without_timing(launch), 'verify_argv': without_timing(verify),
            'timeout_seconds': min(int(stage.get('timeout_seconds', 120)), 120)})
    return {'schema_version': '1.0.0', 'kind': 'supplemental_correctness_execution_manifest',
        'candidate_id': CANDIDATE, 'attempt': attempt, 'host': host,
        'physical_device': physical_device, 'logical_device': 0,
        'case_count': len(cases), 'timing_environment_unset': list(TIMING_VARIABLES),
        'purpose': 'correctness_only_no_performance_feedback',
        'lock_owner': 'run_aprof_job physical-device flock', 'sources': sources, 'cases': cases}


def artifact(campaign, value):
    with WRITER_LOCK, campaign.store(OPERATOR) as store:
        return register_json_artifact(store, value)


def file_artifact(campaign, path):
    with WRITER_LOCK, campaign.store(OPERATOR) as store:
        return store.register_artifact(path)


def decision(campaign, action, reason, refs, event_id):
    with WRITER_LOCK, campaign.store(OPERATOR) as store:
        return campaign.writer(OPERATOR, store).append('next_step_decided',
            {'action': action, 'reason': reason, 'evidence_refs': refs},
            candidate_id=CANDIDATE, attempt_id=CANDIDATE,
            artifact_refs=refs, event_id=event_id)


def bind_summary(campaign, summary, directory, root):
    # summary_ref addresses the canonical body before adding its own reference.
    value = {**summary, 'summary_ref': artifact(campaign, summary)}
    path = directory / 'hardware_validation.json'
    if path.exists() and read(path) != value:
        raise ValueError('supplemental attempt summary is immutable; select a new attempt')
    dump(path, value)
    report_ref = file_artifact(campaign, path)
    decision(campaign, 'record_supplemental_correctness_qualification',
        'Special-value correctness only; failed/interrupted qualification must block semantic acceptance. '
        'Success does not override another mandatory failure.',
        [report_ref, value['summary_ref'], value['run_manifest_ref']], value['event_id'])
    dump(root / 'hardware_validation.json', value)
    dump(directory / 'binding.json', {'artifact_ref': report_ref,
        'summary_ref': value['summary_ref'], 'event_id': value['event_id']})
    return value


def run(campaign=None, *, physical_device=0, host='local', attempt='001', execute=False):
    campaign = campaign or Campaign()
    manifest = prepare(campaign, physical_device=physical_device, host=host, attempt=attempt)
    if not execute:
        return {'status': 'dry_run', 'hardware_executed': False, 'manifest': manifest}
    task = campaign.task(OPERATOR)
    root = task / 'qualification/zero_affine'
    directory = root / 'attempts' / attempt
    directory.mkdir(parents=True, exist_ok=True)
    # This attempt lock prevents competing coordinators from sharing output files;
    # the child runner alone owns each hardware device lock.
    with (directory / 'coordinator.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        campaign.verify_source_identity(OPERATOR, '006')
        manifest_path = directory / 'execution_manifest.json'
        if manifest_path.exists() and read(manifest_path) != manifest:
            raise ValueError('supplemental execution manifest changed; select a new attempt')
        dump(manifest_path, manifest)
        source_refs = [file_artifact(campaign, item['path']) for item in manifest['sources']]
        manifest_ref = artifact(campaign, {**manifest, 'source_artifact_refs': source_refs})
        decision(campaign, 'execute_supplemental_correctness_cases',
            'Execute the predeclared zero-affine special-value cases with timing disabled; stop on first failure.',
            [manifest_ref], f'exp-006-special-values-{attempt}-started')
        summary_path = directory / 'hardware_validation.json'
        if summary_path.exists():
            summary = read(summary_path)
            if summary['run_manifest_ref'] != manifest_ref:
                raise ValueError('cached supplemental summary has a different manifest')
            summary.pop('summary_ref')
            return bind_summary(campaign, summary, directory, root)
        summary = {'schema_version': '1.0.0', 'kind': 'supplemental_correctness_validation',
            'candidate_id': CANDIDATE, 'attempt': attempt, 'host': host,
            'physical_device': physical_device, 'status': 'passed',
            'case_count': len(manifest['cases']), 'attempted_count': 0, 'passed_count': 0,
            'first_failure': None, 'cases': [], 'run_manifest_ref': manifest_ref,
            'event_id': f'exp-006-special-values-{attempt}-completed',
            'started_at': utcnow(), 'purpose': 'correctness_only_no_performance_feedback',
            'timing_environment_unset': list(TIMING_VARIABLES)}
        for case in manifest['cases']:
            Path(case['output']).parent.mkdir(parents=True, exist_ok=True)
            result = {'case_id': case['case_id'], 'status': 'passed', 'launch': None,
                'verify': None, 'observation_ref': None, 'output_ref': None, 'artifact_refs': [], 'reason': None}
            phase = 'launch'
            stage = None
            try:
                for phase in ('launch', 'verify'):
                    stage = f"006/special-values/{attempt}/{case['case_id']}/{phase}"
                    report = campaign.job(OPERATOR, stage, case[phase + '_argv'],
                        cwd=task / 'candidates/006/op', host=host,
                        device=physical_device if phase == 'launch' else None,
                        timeout=case['timeout_seconds'])
                    ref = campaign.record(OPERATOR, report, candidate='006',
                        stage='supplemental_special_values_' + phase)
                    result[phase] = {'execution_ref': ref, 'event_id': report['job']['job_id'] + '-completed',
                        'status': report['status'], 'exit_code': report['exit_code']}
                    result['artifact_refs'].append(ref)
                    if report['status'] != 'passed' or report['exit_code'] != 0:
                        result['status'] = 'failed' if report['status'] == 'failed' else 'interrupted'
                        result['reason'] = f"{phase}: status={report['status']}, exit_code={report['exit_code']}"
                        break
                if result['status'] == 'passed':
                    observation = read(case['observation'])
                    if (observation.get('case_id') != case['case_id']
                            or observation.get('candidate_id') != CANDIDATE
                            or observation.get('output') != case['output']
                            or observation.get('passed') is not True):
                        result['status'] = 'failed'
                        result['reason'] = 'Verifier observation does not attest this case and output as passed'
            except (Exception, KeyboardInterrupt) as error:
                result['status'] = 'interrupted'
                result['reason'] = f'{phase}: {type(error).__name__}: {error}'
                exception_ref = artifact(campaign, {'kind': 'supplemental_execution_interruption',
                    'candidate_id': CANDIDATE, 'case_id': case['case_id'], 'stage': stage,
                    'error': result['reason'], 'observed_at': utcnow()})
                result['artifact_refs'].append(exception_ref)
                transport = task / 'executions' / str(stage) / 'transport-failure.json'
                if transport.exists():
                    result['artifact_refs'].append(file_artifact(campaign, transport))
            for key, path in (('observation_ref', case['observation']), ('output_ref', case['output'])):
                if Path(path).is_file():
                    result[key] = file_artifact(campaign, path)
                    result['artifact_refs'].append(result[key])
            checkpoint = Path(case['output']).parent / 'case_validation.json'
            dump(checkpoint, result)
            result['case_validation_ref'] = file_artifact(campaign, checkpoint)
            summary['cases'].append(result)
            summary['attempted_count'] += 1
            if result['status'] != 'passed':
                summary['status'] = result['status']
                summary['first_failure'] = {'case_id': case['case_id'], 'phase': phase,
                    'reason': result['reason'], 'evidence_ref': result['case_validation_ref']}
                break
            summary['passed_count'] += 1
        summary['finished_at'] = utcnow()
        return bind_summary(campaign, summary, directory, root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--host', choices=['local', 'decode'], default='local')
    parser.add_argument('--physical-device', type=int, default=0)
    parser.add_argument('--attempt', default='001', help='Immutable execution attempt; use a new ID for a retry')
    parser.add_argument('--execute', action='store_true', help='Launch hardware; otherwise print the dry-run manifest')
    args = parser.parse_args()
    result = run(Campaign(args.run), physical_device=args.physical_device,
        host=args.host, attempt=args.attempt, execute=args.execute)
    print(json.dumps(result, allow_nan=False, indent=2))
    return 0 if result['status'] in ('passed', 'dry_run') else 1


if __name__ == '__main__':
    raise SystemExit(main())
