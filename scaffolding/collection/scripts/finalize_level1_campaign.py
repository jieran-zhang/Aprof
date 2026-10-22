#!/usr/bin/env python3
"""Seal and verify a finished Level1 roster; never launch hardware or edit candidates."""
from __future__ import annotations

from aprof_layout import skill_lib

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(skill_lib() / 'runtime/src'))
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.exploration import (ExplorationGate, freeze_exploration_manifest,
    mechanism_alignment_from_artifacts, verify_exploration)
from aprof_runtime.jsonio import canonical_json, content_hash, file_hash
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import (TraceWriter, export_episodes, make_optimization_trace,
    merge_trace_streams, register_json_artifact, validate_trace_contract,
    verify_optimization_traces, verify_trace, write_optimization_trace,
    write_optimization_traces)
from cannbench_device_timing import summarize_multicase
from collect_level1_traces import Campaign, DEFAULT_RUN


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()] if Path(path).exists() else []


def save(path, value):
    """Deterministic, immutable finalization checkpoints also make retries safe."""
    path = Path(path)
    payload = canonical_json(value) + '\n'
    if path.exists():
        if path.read_text() != payload:
            raise StoreError(f'finalized evidence changed: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.finalize-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def text_items(values):
    return [value if isinstance(value, str) else canonical_json(value) for value in values]


def finite_metadata(value):
    """Upstream special values are opaque metadata; JSONL spells them explicitly."""
    if isinstance(value, float) and not math.isfinite(value):
        return 'NaN' if math.isnan(value) else ('+Infinity' if value > 0 else '-Infinity')
    if isinstance(value, dict):
        return {key: finite_metadata(item) for key, item in value.items()}
    if isinstance(value, list):
        return [finite_metadata(item) for item in value]
    return value


class Evidence:
    def __init__(self, store, task):
        self.store, self.task, self.registered = store, task, {}

    def file(self, path, expected=None):
        path = Path(path).resolve()
        digest = self.registered.get(path)
        if digest is None:
            digest = self.store.register_artifact(path)
            self.registered[path] = digest
        if expected and digest != ('sha256:' + expected.removeprefix('sha256:')):
            raise StoreError(f'bound artifact changed: {path}')
        return digest

    def tree(self, directory, suffixes=('.json', '.jsonl', '.log', '.csv')):
        return [self.file(p) for p in sorted(Path(directory).rglob('*'))
                if p.is_file() and p.suffix in suffixes]

    def supplemental_correctness(self, report_path, candidate_id):
        """Bind qualification evidence without interpreting or changing gate status."""
        report_path = Path(report_path)
        report = read(report_path)
        if (report.get('kind') != 'supplemental_correctness_validation'
                or report.get('candidate_id') != candidate_id
                or not isinstance(report.get('attempt'), str)
                or not report['attempt'].isdigit()):
            raise StoreError('supplemental correctness report identity mismatch')
        attempt = report_path.parent / 'attempts' / report['attempt']
        binding_path = attempt / 'binding.json'
        binding = read(binding_path)
        body = {key: value for key, value in report.items() if key != 'summary_ref'}
        if (report.get('summary_ref') != content_hash(body)
                or binding.get('summary_ref') != report['summary_ref']
                or binding.get('event_id') != report.get('event_id')):
            raise StoreError('supplemental correctness summary/binding mismatch')
        if read(self.store.verify_artifact(report['summary_ref'])) != body:
            raise StoreError('supplemental correctness summary differs from its CAS body')
        manifest_ref = report['run_manifest_ref']
        manifest = read(self.store.verify_artifact(manifest_ref))
        if (manifest.get('kind') != 'supplemental_correctness_execution_manifest'
                or any(manifest.get(key) != report.get(key)
                    for key in ('candidate_id', 'attempt', 'case_count', 'purpose', 'timing_environment_unset'))):
            raise StoreError('supplemental correctness execution manifest identity mismatch')
        manifest_path = attempt / 'execution_manifest.json'
        if read(manifest_path) != {key: value for key, value in manifest.items() if key != 'source_artifact_refs'}:
            raise StoreError('supplemental correctness execution manifest changed')
        return {'supplemental_correctness': self.file(report_path, binding['artifact_ref']),
            'supplemental_correctness_manifest': manifest_ref,
            'supplemental_correctness_summary': report['summary_ref'],
            'supplemental_correctness_binding': self.file(binding_path),
            'supplemental_correctness_execution_manifest': self.file(manifest_path)}

    def recorded_file(self, path, digest):
        """A read log binds historical bytes, even when the live context changed."""
        digest = 'sha256:' + digest.removeprefix('sha256:')
        try:
            self.store.verify_artifact(digest)
            return digest
        except StoreError:
            pass
        path = Path(path)
        for candidate in [path, path.with_name(path.stem + '.initial' + path.suffix)]:
            if candidate.is_file() and file_hash(candidate) == digest:
                return self.file(candidate, digest)
        raise StoreError(f'recorded knowledge bytes are unavailable: {path} ({digest})')

    def measurement(self, directory, expected_cases):
        directory = Path(directory)
        report_path, raw_path = directory / 'measurement_report.json', directory / 'raw_measurements.json'
        report = read(report_path) if report_path.exists() else None
        if report is not None and not raw_path.exists():
            raise StoreError(f'measurement report lacks its raw measurements: {report_path}')
        raw = read(raw_path) if raw_path.exists() else {}
        if report is not None and summarize_multicase(raw, expected_cases) != report:
            raise StoreError(f'measurement report does not reproduce raw pairs: {report_path}')
        for source in raw.get('case_sources', []):
            self.file(source['path'], source['sha256'])
            part = read(source['path'])
            actual = [dict(row, device=part['device'], host=part['host']) for row in part['records']]
            if actual != [row for row in raw['records'] if row['case_id'] == source['case_id']]:
                raise StoreError('aggregate records differ from their recorded case source')
        # Register executables, producer, immutable metadata and input binaries
        # named by actual device measurements, not arbitrary hashes in prose.
        for part_path in sorted(directory.glob('case-*/raw_measurements.json')) + ([raw_path] if raw_path.exists() else []):
            part = read(part_path)
            for execution in part.get('case_executions', []):
                metadata_path = Path(execution['metadata_path'])
                self.file(metadata_path, execution['metadata_sha256'])
                metadata = read(metadata_path)
                for key, digest in execution.get('input_hashes', {}).items():
                    self.file(metadata[key], digest)
                for label, command in execution.get('commands', {}).items():
                    digest = part.get(label + '_executable_sha256')
                    if digest:
                        self.file(command['argv'][0], digest)
            if part.get('producer_sha256'):
                self.file(ROOT / 'scaffolding/collection/scripts/cannbench_device_timing.py', part['producer_sha256'])
        refs = self.tree(directory)
        return report, self.file(report_path) if report is not None else None, refs

    def profiles(self, directory):
        refs = self.tree(directory, ('.json', '.csv'))
        # Normalizer output keeps both file-byte and canonical-document hashes.
        for path in sorted(Path(directory).rglob('*.json')):
            document = read(path)
            if isinstance(document, dict) and set(document) == {'schema_version', 'case_id', 'kernel', 'metrics'}:
                validate_trace_contract('normalized-profile', document)
                refs.append(register_json_artifact(self.store, document))
        return sorted(set(refs))


def stage(status='not_run', reason='No recorded execution or review.', refs=()):
    return {'status': status, 'reason': reason, 'artifact_refs': sorted(set(refs))}


def first_failure(validation, verdict):
    for name in ('static_review', 'build', 'correctness', 'runtime', 'timing', 'profile'):
        if validation[name]['status'] in ('failed', 'interrupted'):
            return name
    return {'static_rejected': 'static_review', 'build_failed': 'build',
        'accuracy_failed': 'correctness', 'runtime_failed': 'runtime',
        'artifacts_incomplete': 'artifacts', 'measurement_unstable': 'timing',
        'attribution_uncertain': 'mechanism_alignment', 'heldout_regression': 'heldout_regression',
        'stable_no_gain': 'performance_gain', 'benchmark_specialized_gain': 'production_safety'}.get(verdict)


def lesson_for(outcome, validation, report, mechanism, refs, *, mechanism_plan=None, mechanism_binding=None,
        timing_blocked=False):
    effective, ineffective, counterexamples, limitations = [], [], [], []
    failed = first_failure(validation, outcome['verdict'])
    status = 'inconclusive'
    source_failed = validation['build']['status'] == 'failed' or validation['correctness']['status'] == 'failed'
    if source_failed:
        status = 'refuted'
        ineffective.append(f'This exact source fails {failed}; the intended usable optimization is refuted for this attempt.')
    if report and report['stable']:
        measured = (f"20-case paired geometric speedup={outcome['speedup']:.9g}; "
                    f"gate lower bound={outcome['speedup_lcb']:.9g}; "
                    f"largest signed per-case regression={report['max_case_regression']:.9g}.")
        effective.append(measured)
        for case in report['per_case']:
            if case['regression'] > .03:
                counterexamples.append(f"case {case['case_id']}: paired candidate/baseline - 1={case['regression']:.9g} exceeds 0.03")
        if outcome['verdict'] in ('production_safe_gain', 'benchmark_specialized_gain'):
            status = 'supported'
        elif outcome['verdict'] in ('stable_no_gain', 'heldout_regression'):
            status = 'refuted'
            ineffective.append('; '.join(outcome['reasons']))
    elif report:
        limitations.extend(report['reasons'])
    else:
        limitations.append('No final all20 paired measurement report; search timing cannot establish acceptance.')
    if mechanism:
        for metric in mechanism['metrics']:
            sentence = (f"{metric['name']}: baseline={metric['baseline']:.9g}, candidate={metric['candidate']:.9g} "
                        f"{metric['unit']}; expected {metric['expected_direction']}.")
            follows = metric['candidate'] > metric['baseline'] if metric['expected_direction'] == 'increase' else metric['candidate'] < metric['baseline']
            (effective if follows else ineffective).append(sentence)
        limitations.append('Directional counter agreement supports the stated hypothesis; it does not establish exclusive causality.')
    elif not mechanism_binding:
        limitations.append('No bound before/after mechanism report; mechanism attribution remains unknown.')
    if mechanism_plan and mechanism_binding is None:
        limitations.append('Mechanism predictions were frozen, but no complete binding result was collected.')
        limitations.extend(prediction['limitation'] for prediction in mechanism_plan['predictions'] if prediction.get('limitation'))
    if mechanism_binding:
        binding_status = mechanism_binding['status']
        limitations.append(f"Predeclared mechanism set is {binding_status}: {mechanism_binding['reason']}")
        for comparison in mechanism_binding['comparisons']:
            detail = (f"case {comparison['case_id']} {comparison['kernel']} {comparison['name']}: "
                      f"baseline={comparison.get('baseline_value')}, candidate={comparison.get('candidate_value')} "
                      f"{comparison.get('unit')}; expected {comparison['expected_direction']}; "
                      f"{comparison['status']}: {comparison.get('reason') or 'No complete comparison.'}")
            limitations.append(detail)
            if comparison['status'] == 'refuted':
                ineffective.append(detail)
        if binding_status == 'refuted':
            if not timing_blocked:
                status = 'refuted'
            ineffective.append('The predeclared mechanism hypothesis is refuted by these counters.')
            limitations.append('The predeclared mechanism hypothesis is refuted by these counters; any measured gain does not validate that explanation.')
        elif binding_status != 'supported' and status == 'supported':
            status = 'inconclusive'
        if binding_status != 'supported':
            limitations.append('No causal mechanism success is claimed from this incomplete or inconsistent prediction set.')
    if timing_blocked:
        status = 'inconclusive'
        limitations.append('Timing is blocked; mechanism counter results do not establish whether this optimization improves performance.')
    if source_failed:
        status = 'refuted'
    limitations.append('Evidence applies to the frozen workload and recorded device/software environment.')
    if outcome['verdict'] == 'benchmark_specialized_gain':
        limitations.append('Production scope or portability review is incomplete; any selected gain is qualified only for this benchmark workload.')
    return {'status': status, 'effective_conditions': effective, 'ineffective_conditions': ineffective,
        'counterexamples': counterexamples, 'limitations': limitations,
        'next_step': 'Retain the verified benchmark source and preserve its scope limitations.' if outcome['verdict'] in ('production_safe_gain', 'benchmark_specialized_gain') else
            'Retain baseline; use the recorded first failure and missing evidence to design a new attempt.',
        'evidence_refs': sorted(set(refs))}


class Finalizer:
    def __init__(self, run=DEFAULT_RUN):
        self.campaign = Campaign(run)
        self.run = self.campaign.run

    def preflight(self, op):
        task = self.campaign.task(op)
        roster = read(task / 'frozen-roster.json')
        registrations = {read(p)['candidate_id']: p for p in (task / 'candidates').glob('*/registration.json')}
        plans = list((task / 'candidates').glob('*/candidate_plan.json'))
        ids = [item['candidate_id'] for item in roster['candidates']]
        if len(ids) != len(set(ids)) or set(ids) != set(registrations) or len(plans) != len(ids):
            raise StoreError('frozen roster must include every candidate attempt exactly once')
        if not 1 <= len(ids) <= self.campaign.manifest['budget']['candidate_limit']:
            raise StoreError('frozen candidate budget exceeded')
        items = []
        for frozen in roster['candidates']:
            path = registrations[frozen['candidate_id']]
            registration, plan = read(path), read(path.parent / 'candidate_plan.json')
            if any(frozen.get(key) != value for key, value in registration.items()):
                raise StoreError('registration differs from frozen roster')
            if file_hash(path.parent / 'candidate_plan.json') != frozen['frozen_plan_sha256']:
                raise StoreError('candidate plan changed after roster freeze')
            if plan['candidate_id'] != registration['candidate_id']:
                raise StoreError('candidate plan identity differs from registration')
            if plan.get('mode', 'exploration') not in ('exploration', 'graph'):
                raise ContractError('candidate mode must be exploration or graph')
            items.append((path.parent.name, registration, plan))
        for path in sorted((task / 'jobs').glob('*.json')):
            job = read(path)
            directory = Path(job['output_dir'])
            report = directory / 'execution.json'
            if report.exists():
                if read(report).get('status') not in ('passed', 'failed', 'interrupted', 'timed_out', 'timeout'):
                    raise StoreError(f'job is not terminal: {path}')
            elif not (directory / 'transport-failure.json').exists():
                raise StoreError(f'job lacks a terminal execution record: {path}')
        return task, roster, items

    def context(self, task, evidence):
        manifest_path = task / 'knowledge/manifest.json'
        manifest = read(manifest_path) if manifest_path.exists() else {}
        loaded = []
        for path in (task / 'knowledge/knowledge_reads.jsonl', task / 'worker_knowledge_reads.jsonl'):
            for entry in rows(path):
                digest = entry.get('content_hash') or entry.get('sha256')
                if not digest or not entry.get('path'):
                    continue
                digest = evidence.recorded_file(entry['path'], digest)
                normalized = {'path': entry['path'], 'content_hash': digest, 'purpose': entry.get('purpose', entry.get('used_for', 'Recorded worker knowledge read'))}
                if normalized not in loaded:
                    loaded.append(normalized)
        graph = manifest.get('graph')
        graph_hash = evidence.file(graph['path'], graph.get('sha256')) if graph else None
        knowledge = {'manifest_hash': evidence.file(manifest_path) if manifest_path.exists() else None, 'loaded': loaded}
        dependencies = {name: item['commit'] for name, item in manifest.get('dependencies', {}).items() if isinstance(item, dict) and item.get('commit')}
        dependencies['campaign_git_commit'] = self.campaign.manifest.get('git_commit', 'not recorded')
        harness_files = [p for p in (task / 'baseline/harness_manifest.json', task / 'baseline/harness.patch',
            task / 'baseline/op_host/aprof_device_timer.h', ROOT / 'scaffolding/collection/scripts/cannbench_device_timing.py',
            ROOT / 'scaffolding/collection/scripts/cannbench_prepared_validate.py', ROOT / 'scaffolding/collection/scripts/run_aprof_job.py') if p.is_file()]
        harness = register_json_artifact(evidence.store, {'files': [{'path': str(p), 'content_hash': evidence.file(p)} for p in harness_files]})
        producer = evidence.file(Path(__file__))
        policy_path = task / 'input-policy.json'
        policy = read(policy_path) if policy_path.exists() else {}
        prepared = Path(policy.get('prepared_root', task / 'prepared'))
        cases, shapes, dtypes, attributes = [], {}, set(), {}
        for path in sorted(prepared.glob('case_*/metadata.json')):
            metadata = read(path)
            case_id = metadata['case_id']
            cases.append({'case_id': case_id, 'metadata_hash': evidence.file(path)})
            shapes[str(case_id)] = {key: finite_metadata(metadata[key]) for key in ('shape', 'shapes', 'lengths', 'numel') if key in metadata}
            for key in ('dtype', 'x_dtype', 'mask_dtype'):
                if metadata.get(key):
                    dtypes.add(metadata[key])
            attributes[str(case_id)] = finite_metadata({key: value for key, value in metadata.items()
                if key not in ('case_id', 'dtype', 'shape', 'shapes', 'lengths', 'numel') and not (isinstance(value, str) and Path(value).is_absolute())})
        input_refs = [evidence.file(policy_path)] if policy else []
        if policy.get('qualification_report'):
            input_refs.append(evidence.file(policy['qualification_report']))
        input_manifest = register_json_artifact(evidence.store, {'prepared_root': str(prepared), 'cases': cases, 'qualification_refs': input_refs})
        hardware_paths = sorted((self.run / 'setup').glob('*capacity*.json')) + sorted((task / 'executions').glob('device-probe-*/execution.json'))
        if (self.run / 'environment_manifest.json').is_file():
            hardware_paths.append(self.run / 'environment_manifest.json')
        hardware = [{'path': str(p), 'content_hash': evidence.file(p)} for p in hardware_paths]
        fingerprint = content_hash(hardware) if hardware else None
        if hardware:
            register_json_artifact(evidence.store, hardware)
        prompt = next((entry['content_hash'] for entry in loaded if Path(entry['path']).name == 'worker_context.json'), None)
        if (task / 'isolated-worker/prompt.txt').exists():
            launch = read(task / 'isolated-worker/launch.json')
            prompt = evidence.file(task / 'isolated-worker/prompt.txt', launch['prompt_sha256'])
        precision = manifest.get('task_parity', {}).get('precision_contract')
        accuracy_contract = canonical_json(precision) if precision else (
            'Unchanged local baseline verifier and tolerance; exact NaN/Inf position checks where specified by the workload.' if cases else None)
        return {'knowledge': knowledge, 'provenance': {'dependencies': dependencies, 'graph_hash': graph_hash,
            'skill_manifest_hash': knowledge['manifest_hash'], 'prompt_hash': prompt, 'producer_hash': producer, 'harness_hash': harness},
            'workload': {'manifest_hash': input_manifest, 'case_ids': [case['case_id'] for case in cases],
                'shapes': shapes, 'dtypes': sorted(dtypes), 'layouts': ['contiguous'] if cases else [], 'attributes': attributes,
                'accuracy_contract': accuracy_contract,
                'hardware_fingerprint': fingerprint}, 'input_refs': input_refs, 'policy': policy}

    def attempt(self, task, identifier, registration, plan, evidence, events):
        directory = task / 'candidates' / identifier
        candidate_id = registration['candidate_id']
        artifacts = {'candidate_plan': evidence.file(directory / 'candidate_plan.json'),
            'registration': evidence.file(directory / 'registration.json')}
        if plan.get('contradicting_evidence'):
            artifacts['predeclared_contradicting_evidence'] = register_json_artifact(evidence.store, {
                'schema_version': '1.0.0', 'kind': 'predeclared_diagnostic_conditions',
                'candidate_id': candidate_id, 'candidate_plan_hash': artifacts['candidate_plan'],
                'source_field': '$.contradicting_evidence',
                'conditions': plan['contradicting_evidence'],
                'classification': 'predeclared_hypothesis_or_limitation', 'measured_counterexample': False,
                'evidence_refs': [artifacts['candidate_plan']]})
        supplemental_path = task / 'qualification/zero_affine/hardware_validation.json'
        if candidate_id == 'exp-006' and supplemental_path.is_file():
            artifacts.update(evidence.supplemental_correctness(supplemental_path, candidate_id))
        for digest in [*registration['source_hashes'].values(), registration['patch_artifact_hash'], registration['plan_hash']]:
            evidence.store.verify_artifact(digest)
        refs = evidence.tree(task / 'executions' / identifier)
        candidate_events = [event for event in events if event['candidate_id'] == candidate_id]
        validations = {name: stage() for name in ('static_review', 'build', 'correctness', 'runtime', 'timing', 'profile')}
        static = plan.get('static_review')
        if static:
            validations['static_review'] = stage('passed', 'Recorded candidate source/semantic reasoning; runtime evidence is assessed separately.', [artifacts['candidate_plan']])
        build_events = [event for event in candidate_events if event['event_type'] == 'stage_completed' and event['payload']['stage'] in ('configure', 'build')]
        if build_events:
            build_status = next((event['payload']['status'] for event in build_events if event['payload']['status'] != 'passed'),
                                'passed' if any(event['payload']['stage'] == 'build' for event in build_events) else 'not_run')
            validations['build'] = stage(build_status, 'Recorded configure/build command outcomes.', [digest for event in build_events for digest in event['payload']['artifact_refs']])
            artifacts['build_log'] = register_json_artifact(evidence.store, {'events': build_events})
        accuracy_path = self.campaign.accuracy_report(task.name, identifier)
        accuracy = read(accuracy_path) if accuracy_path.exists() else None
        if accuracy:
            accuracy_refs = sorted(set(evidence.tree(task / 'correctness' / identifier) + evidence.tree(accuracy_path.parent)))
            verifier = directory / 'op/scripts/verify_result.py'
            if verifier.is_file():
                evidence.file(verifier)
            passed = accuracy['status'] == 'passed' and accuracy['case_ids'] == list(range(1, 21)) and accuracy['passed_count'] == 20
            validations['correctness'] = stage('passed' if passed else 'failed', f"{accuracy['passed_count']}/{accuracy['case_count']} cases passed the unchanged verifier.", accuracy_refs)
            runtime_status = 'passed' if passed else ('failed' if any(case.get('kernel_exit_code', 0) != 0 for case in accuracy['cases']) else 'not_run')
            validations['runtime'] = stage(runtime_status, 'Device kernel execution results from full correctness.', accuracy_refs)
            artifacts['accuracy_report'] = evidence.file(accuracy_path)
        search, search_hash, search_refs = evidence.measurement(task / 'timing/search' / identifier, self.campaign.manifest['sentinel_case_ids'])
        report, report_hash, timing_refs = evidence.measurement(task / 'timing/final' / identifier, list(range(1, 21)))
        if search_hash:
            artifacts['search_measurement_report'] = search_hash
        def timing_event(event, phase=None):
            payload = event['payload']
            stage_name = (payload.get('stage') or (payload.get('reason') or '').split(':', 1)[0]).replace('-', '_')
            names = (phase + '_timing', phase + '_aggregation') if phase else ('search_timing', 'final_timing', 'search_aggregation', 'final_aggregation')
            return any(name in stage_name for name in names)
        execution_events = [event for event in candidate_events if event['event_type'] in ('stage_completed', 'execution_interrupted')]
        final_attempted = any(timing_event(event, 'final') for event in execution_events)
        if report_hash:
            artifacts['measurement_report'] = report_hash
            final_attempted |= any(case['pair_count'] for case in report['per_case'])
            validations['timing'] = stage('passed' if report['stable'] else ('failed' if final_attempted else 'not_run'),
                'All20 paired measurements passed stability checks.' if report['stable'] else
                ('; '.join(report['reasons']) if final_attempted else 'No final timing execution; the empty aggregate preserves the skipped case set.'), timing_refs)
        elif timing_refs:
            validations['timing'] = stage('interrupted', 'Raw final timing evidence exists without a completed aggregate report.', timing_refs)
        timing_failures = [event for event in candidate_events if timing_event(event) and (
            event['event_type'] == 'execution_interrupted' or
            (event['event_type'] == 'stage_completed' and event['payload']['status'] in ('failed', 'interrupted')) or
            (event['event_type'] == 'next_step_decided' and event['payload']['action'] == 'stop_candidate_after_execution_failure'))]
        if timing_failures:
            failure_ref = register_json_artifact(evidence.store, {'events': timing_failures})
            artifacts['timing_execution_failures'] = failure_ref
            failure_refs = [failure_ref, *search_refs, *timing_refs]
            for event in timing_failures:
                failure_refs.extend(event['artifact_refs'])
                failure_refs.extend(event['payload'].get('artifact_refs', []))
                failure_refs.extend(event['payload'].get('evidence_refs', []))
            validations['timing'] = stage('failed', 'A recorded search/final timing execution or controller operation failed; later skipped timing does not erase that failure.', failure_refs)
        calibration_block_path = task / 'queue/calibration_block.json'
        calibration_block = read(calibration_block_path) if calibration_block_path.exists() else None
        if calibration_block:
            if calibration_block.get('measurement_status') != 'blocked' or calibration_block.get('timing_qualification_claimed') is not False:
                raise StoreError('invalid calibration block attestation')
            if report and (report['stable'] or any(case['pair_count'] for case in report['per_case'])):
                raise StoreError('blocked diagnostics cannot contain admitted or collected final timing')
            artifacts['calibration_block'] = evidence.file(calibration_block_path)
            if not timing_failures:
                validations['timing'] = stage('not_run', calibration_block['reason'],
                    [artifacts['calibration_block'], *timing_refs])
        profile_refs = evidence.profiles(task / 'profiles' / identifier)
        profile_events = [event for event in candidate_events if event['event_type'] == 'stage_completed' and event['payload']['stage'] == 'profile']
        if profile_events:
            profile_status = next((event['payload']['status'] for event in profile_events if event['payload']['status'] != 'passed'), 'passed')
            validations['profile'] = stage(profile_status, 'Recorded profiler command outcomes; normalized metric evidence is bound separately.', profile_refs)
        profile_recovery = None
        recovered_profile_events = set()
        if (task / 'profile_preflight_recovery.json').exists():
            from recover_level1_profile_preflight import load_verified_recovery
            profile_recovery = load_verified_recovery(self.campaign, task.name, evidence.store)
            recovered_profile_events = set(profile_recovery['ignored_event_ids'])
            artifacts['profile_preflight_recovery'] = profile_recovery['manifest_ref']
        profile_interruptions = [event for event in candidate_events if event['event_type'] == 'execution_interrupted'
            and 'profile' in event['payload']['stage'] and event['event_id'] not in recovered_profile_events]
        if profile_interruptions:
            interruption_ref = register_json_artifact(evidence.store, {'events': profile_interruptions})
            refs.append(interruption_ref)
            validations['profile'] = stage('interrupted', 'Profiler collection or its controller operation was interrupted; earlier successful commands do not erase the failure.',
                [interruption_ref, *profile_refs, *(digest for event in profile_interruptions for digest in event['artifact_refs'])])
        mechanism = None
        mechanism_paths = [directory / 'mechanism_report.json', task / 'profiles' / identifier / 'mechanism_report.json']
        existing = [path for path in mechanism_paths if path.exists()]
        if existing:
            mechanism = read(existing[0])
            if any(read(path) != mechanism for path in existing[1:]):
                raise StoreError('conflicting mechanism reports')
            validate_trace_contract('mechanism-report', mechanism)
            artifacts['mechanism_report'] = evidence.file(existing[0])
        mechanism_plan_path, mechanism_binding_path = directory / 'mechanism_plan.json', directory / 'mechanism_binding.json'
        mechanism_plan = read(mechanism_plan_path) if mechanism_plan_path.exists() else None
        mechanism_binding = read(mechanism_binding_path) if mechanism_binding_path.exists() else None
        if mechanism_plan:
            from bind_level1_mechanisms import MechanismBinder
            if mechanism_plan['candidate_id'] != candidate_id:
                raise StoreError('mechanism plan candidate identity mismatch')
            MechanismBinder(self.run).verify_plan_event(task.name, mechanism_plan, evidence.store)
            artifacts['mechanism_plan'] = evidence.file(mechanism_plan_path)
        if mechanism_binding:
            if mechanism_binding['candidate_id'] != candidate_id or not mechanism_plan or mechanism_binding['mechanism_plan_hash'] != content_hash(mechanism_plan):
                raise StoreError('mechanism binding differs from the frozen prediction plan')
            artifacts['mechanism_binding'] = evidence.file(mechanism_binding_path)
            refs.extend(evidence.tree(directory / 'mechanism_bindings'))
            admitted = mechanism_binding['status'] == 'supported'
            comparisons = mechanism_binding['comparisons']
            keys = ('case_id', 'kernel', 'name', 'expected_direction', 'baseline_profile_hash')
            expected = [tuple(prediction.get(key) for key in keys) for prediction in mechanism_plan['predictions']]
            observed = [tuple(comparison.get(key) for key in keys) for comparison in comparisons]
            if observed != expected or (admitted and (not comparisons or any(item['status'] != 'supported' for item in comparisons))):
                raise StoreError('mechanism binding omitted or contradicted a predeclared comparison')
            if admitted != bool(mechanism) or (mechanism and (mechanism_binding['mechanism_report_hash'] != content_hash(mechanism) or len(mechanism['metrics']) != len(expected))):
                raise StoreError('mechanism report disagrees with the complete predeclared binding result')
            MechanismBinder(self.run).verify_binding(task.name, identifier, mechanism_plan,
                mechanism_binding, evidence.store)
        elif mechanism_plan and mechanism:
            raise StoreError('predeclared mechanism report requires its complete binding result')
        reviews = read(directory / 'gate_review.json') if (directory / 'gate_review.json').exists() else {}
        if reviews:
            artifacts['gate_review'] = evidence.file(directory / 'gate_review.json')
        gate = {'candidate_id': candidate_id, 'static_review': validations['static_review']['status'],
            'build': validations['build']['status'], 'accuracy': validations['correctness']['status'],
            'runtime': validations['runtime']['status'], 'semantic': validations['correctness']['status'],
            'scope': 'not_run', 'portability': 'not_run', 'artifacts': artifacts,
            'baseline_samples_ns': [], 'candidate_samples_ns': [], 'heldout_regressions': [], 'mechanism_alignment': None}
        for key in ('static_review', 'semantic', 'scope', 'portability'):
            review = reviews.get(key)
            if review:
                if review.get('status') not in ('passed', 'failed', 'not_run') or not review.get('reason'):
                    raise ContractError(f'gate_review.{key} requires a runtime status and explicit review reason')
                gate[key] = review['status']
                if key == 'static_review':
                    validations[key] = stage(review['status'], review['reason'], [artifacts['gate_review']])
        for key in ('static_review', 'build', 'accuracy', 'runtime', 'semantic'):
            if gate[key] == 'interrupted':
                gate[key] = 'failed'
        if report:
            gate.update(report['gate_projection'])
        gate['mechanism_alignment'] = mechanism_alignment_from_artifacts(gate, evidence.store)
        evidence_refs = sorted(set(refs + search_refs + timing_refs + profile_refs + list(artifacts.values())))
        return {'identifier': identifier, 'registration': registration, 'plan': plan, 'gate': gate,
            'validation': {**validations, 'case_count': accuracy['case_count'] if accuracy else 0,
                'passed_count': accuracy['passed_count'] if accuracy else 0,
                'timing_case_ids': [case['case_id'] for case in report['per_case'] if case['pair_count']] if report else []},
            'report': report, 'search_report': search, 'mechanism': mechanism,
            'mechanism_plan': mechanism_plan, 'mechanism_binding': mechanism_binding, 'refs': evidence_refs,
            'calibration_block': calibration_block,
            'profile_preflight_recovery': profile_recovery,
            'recovered_execution_failures': [event['payload']['stage'] for event in candidate_events
                if event['event_type'] == 'stage_completed' and event['payload']['status'] != 'passed'
                and 'correctness' in event['payload']['stage'] and validations['correctness']['status'] == 'passed']}

    @staticmethod
    def graph_episode(item, store, task):
        """Import only a complete, replay-verified SQLite graph episode."""
        from aprof_runtime.contracts import CandidateEpisode
        candidate_id = item['registration']['candidate_id']
        row = store.connection.execute('SELECT payload_json FROM episodes WHERE candidate_id=?', (candidate_id,)).fetchone()
        if row is None:
            raise StoreError('graph candidate requires an independently finalized real episode already in this split store: ' + candidate_id)
        episode = json.loads(row[0])
        CandidateEpisode.from_dict(episode)
        draft, evidence = episode['draft'], episode['evidence']
        registration, gate = item['registration'], item['gate']
        if (draft['source_hashes'] != registration['source_hashes'] or
                draft['patch_artifact_hash'] != registration['patch_artifact_hash'] or
                draft['parameters'] != item['plan']['parameters'] or
                episode['context']['task_id'] != task.name or draft['session_id'] != task.name + '-campaign'):
            raise StoreError('graph episode does not match frozen candidate/task/session')
        for key in ('static_review', 'build', 'accuracy', 'runtime', 'semantic', 'scope', 'portability',
                    'baseline_samples_ns', 'candidate_samples_ns', 'heldout_regressions'):
            if evidence.get(key, []) != gate[key]:
                raise StoreError('graph episode differs from recorded evidence: ' + key)
        for key in ('accuracy_report', 'measurement_report', 'mechanism_report'):
            if evidence['artifacts'].get(key) != gate['artifacts'].get(key):
                raise StoreError('graph episode differs from bound artifact: ' + key)
        sealed = evidence['artifacts'].get('attempt_evidence')
        if not sealed:
            raise StoreError('graph episode must bind pre-outcome attempt_evidence')
        fragment = json.loads(store.verify_artifact(sealed).read_text())
        if (fragment.get('attempt_id') != candidate_id or fragment.get('identity') !=
                {'run_id': task.parent.parent.name, 'task_id': task.name, 'session_id': draft['session_id']}):
            raise StoreError('graph sealed attempt identity mismatch')
        if any(event['event_type'] == 'attempt_finished' for event in fragment['events']):
            raise StoreError('graph attempt evidence was sealed after its outcome')
        proposals = [event for event in fragment['events'] if event['event_type'] == 'candidate_proposed']
        if len(proposals) != 1 or proposals[0]['payload']['mode'] != 'graph':
            raise StoreError('graph attempt must contain one real graph proposal')
        return episode

    def finalize_operator(self, op):
        task, roster, items = self.preflight(op)
        split = self.campaign.split(op)
        with self.campaign.store(op) as store:
            evidence = Evidence(store, task)
            writer = self.campaign.writer(op, store)
            verify_trace(writer.path, store)
            if (task / 'finalization_report.json').exists():
                self.verify_operator(op, store)
                return read(task / 'finalization_report.json')
            context = self.context(task, evidence)
            evidence.profiles(task / 'profiles/baseline')
            events = rows(writer.path)
            attempts = [self.attempt(task, identifier, registration, plan, evidence, events) for identifier, registration, plan in items]
            store.verify_integrity()
            graph_episodes = {item['registration']['candidate_id']: self.graph_episode(item, store, task)
                for item in attempts if item['plan'].get('mode', 'exploration') == 'graph'}
            exploration_attempts = [item for item in attempts if item['plan'].get('mode', 'exploration') == 'exploration']
            frozen_path = task / 'exploration_request.json'
            request = None
            if exploration_attempts and not frozen_path.exists():
                if context['policy']:
                    writer.append('next_step_decided', {'action': 'record_input_reference_qualification',
                        'reason': context['policy']['reason'], 'evidence_refs': context['input_refs']},
                        event_id=op + '-finalizer-input-qualification')
                frozen = []
                for item in exploration_attempts:
                    registration, plan = item['registration'], item['plan']
                    candidate_id = registration['candidate_id']
                    writer.append('next_step_decided', {'action': 'seal_recorded_attempt',
                        'reason': 'Candidate roster is frozen; preserve all available successes, failures and missing evidence before evaluating the machine gate.',
                        'evidence_refs': item['refs']}, attempt_id=candidate_id, candidate_id=candidate_id,
                        event_id=candidate_id + '-finalizer-seal')
                    sealed = writer.seal_attempt(candidate_id)
                    frozen.append({'candidate_id': candidate_id, 'session_id': op + '-campaign',
                        'source_hashes': registration['source_hashes'], 'patch_artifact_hash': registration['patch_artifact_hash'],
                        'handler_id': plan['handler_id'], 'handler_version': plan.get('handler_version', '1.0.0'),
                        'parameters': plan['parameters'], 'coverage_gap': plan['coverage_gap'], 'attempt_evidence_hash': sealed})
                manifest_hash = freeze_exploration_manifest(store, run_id=self.run.name, task_id=op, split=split,
                    candidates=frozen, frozen_at=roster['frozen_at'])
                request = {'schema_version': '1.0.0', 'frozen_manifest_hash': manifest_hash,
                    'candidates': frozen, 'evidence': [item['gate'] for item in exploration_attempts], 'config': {}}
                save(frozen_path, request)
            elif exploration_attempts:
                request = read(frozen_path)
                if request['evidence'] != [item['gate'] for item in exploration_attempts]:
                    raise StoreError('evidence changed after final acceptance request was frozen')
            exploration_outcomes = list(ExplorationGate().evaluate(request, store=store)) if request else []
            if request:
                verify_exploration(request, exploration_outcomes, store=store)
                save(task / 'exploration_outcomes.json', exploration_outcomes)
            outcome_map = {outcome['candidate_id']: outcome for outcome in exploration_outcomes}
            outcome_map.update({candidate_id: episode['outcome'] for candidate_id, episode in graph_episodes.items()})
            outcomes = [outcome_map[item['registration']['candidate_id']] for item in attempts]
            sealed_map = {item['candidate_id']: item['attempt_evidence_hash'] for item in request['candidates']} if request else {}
            sealed_map.update({candidate_id: episode['evidence']['artifacts']['attempt_evidence'] for candidate_id, episode in graph_episodes.items()})
            summaries = []
            for item, outcome in zip(attempts, outcomes, strict=True):
                registration, plan = item['registration'], item['plan']
                episode = graph_episodes.get(registration['candidate_id'])
                outcome_ref = register_json_artifact(store, outcome)
                measured = bool(item['report'] and item['report']['stable'] and outcome['speedup'] > 0)
                supporting = []
                for source in plan.get('supporting_evidence', []):
                    path = Path(source)
                    if path.is_file():
                        supporting.append(evidence.file(path))
                anchors = []
                for anchor in plan.get('source_anchors', []):
                    if isinstance(anchor, str):
                        anchors.append(anchor)
                    else:
                        supporting.append(evidence.recorded_file(anchor['path'], anchor['sha256']) if anchor.get('sha256') else evidence.file(anchor['path']))
                        anchors.append(canonical_json(anchor))
                missing = [] if item['mechanism'] else ([f"Mechanism binding is {item['mechanism_binding']['status']}: {item['mechanism_binding']['reason']}"]
                    if item['mechanism_binding'] else ['A complete admitted before/after mechanism binding is missing.'])
                diagnosis = {'symptoms': text_items(plan.get('symptoms', [])), 'mechanisms': text_items(plan.get('mechanisms', [])),
                    'assessment_basis': plan.get('hypothesis_basis', 'heuristic'), 'supporting_evidence': sorted(set(supporting)),
                    'contradicting_evidence': [item['gate']['artifacts']['predeclared_contradicting_evidence']]
                        if 'predeclared_contradicting_evidence' in item['gate']['artifacts'] else [],
                    'missing_evidence': missing, 'source_anchors': anchors}
                if diagnosis['assessment_basis'] == 'user':
                    diagnosis['assessment_basis'] = 'manual'
                result = {'verdict': outcome['verdict'], 'first_failed_stage': first_failure(item['validation'], outcome['verdict']),
                    'speedup': outcome['speedup'] if measured else None, 'speedup_lcb': outcome['speedup_lcb'] if measured else None,
                    'max_regression': item['report']['max_case_regression'] if item['report'] else None,
                    'machine_outcome_ref': outcome_ref, 'episode_ref': episode['episode_hash'] if episode else None,
                    'exploration_outcome_ref': None if episode else outcome_ref,
                    'graph_policy_eligible': bool(episode and outcome['policy_update_eligible']),
                    'attempt_evidence_hash': sealed_map[registration['candidate_id']]}
                record = make_optimization_trace({'run_id': self.run.name, 'task_id': op, 'session_id': op + '-campaign',
                    'attempt_id': registration['candidate_id'], 'candidate_id': registration['candidate_id'], 'operator': op,
                    'split': split, 'parent_attempt_id': plan.get('parent_attempt_id'), 'source_parent_hash': registration['source_hashes']['baseline']},
                    provenance={**context['provenance'], 'baseline_source_hash': registration['source_hashes']['baseline'],
                        'candidate_source_hash': registration['source_hashes']['candidate'], 'patch_hash': registration['patch_artifact_hash']},
                    knowledge=context['knowledge'], workload=context['workload'], diagnosis=diagnosis,
                    intervention={'intent': plan['intent'], 'rationale': plan.get('rationale', plan['intent']),
                        'expected_effects': text_items(plan['expected_effects']), 'handler': {'id': plan['handler_id'],
                            'version': plan.get('handler_version', '1.0.0'), 'producer_hash': None},
                        'parameters': plan['parameters'], 'alternatives': text_items(plan.get('alternatives', []))},
                    routing={'mode': 'graph' if episode else 'exploration', 'route': episode['draft']['route'] if episode else None,
                        'coverage_gap': None if episode else plan['coverage_gap']},
                    validation=item['validation'], result=result,
                    lesson=lesson_for(outcome, item['validation'], item['report'], item['mechanism'], [outcome_ref, *item['refs']],
                        mechanism_plan=item['mechanism_plan'], mechanism_binding=item['mechanism_binding'],
                        timing_blocked=bool(item['calibration_block'])))
                record['lesson']['limitations'].extend(text_items(plan.get('contradicting_evidence', [])))
                if item['calibration_block']:
                    record['lesson']['limitations'].append(item['calibration_block']['reason'])
                    record['lesson']['next_step'] = 'Resolve the recorded A/A measurement-protocol/context instability before a new frozen performance evaluation; no source is accepted on counter changes alone.'
                if item['profile_preflight_recovery']:
                    record['lesson']['limitations'].extend(item['profile_preflight_recovery']['warnings'])
                if item['recovered_execution_failures']:
                    record['lesson']['limitations'].append('Earlier correctness command failures were superseded by the indexed qualified run; the original execution/environment evidence remains preserved and is not a final kernel correctness rejection.')
                for path in record['null_reasons']:
                    record['null_reasons'][path] = ('No admitted stable all20 timing reaches the performance gate.' if path in ('$.result.speedup', '$.result.speedup_lcb') else
                        'Exploration has no graph route or episode and is excluded from graph policy training.' if path in ('$.routing.route', '$.result.episode_ref') else
                        'Candidate author/handler implementation was not independently identified; collector source is recorded separately.' if path == '$.intervention.handler.producer_hash' else
                        'Independent baseline-derived attempt; no parent attempt.' if path == '$.identity.parent_attempt_id' else
                        'All machine gates passed; no failed stage.' if path == '$.result.first_failed_stage' else
                        'No recorded artifact or applicable value for this field; see stage records and lesson limitations.')
                write_optimization_trace(task / 'optimization_traces.jsonl', record, store)
                summary_ref = register_json_artifact(store, record)
                writer.append('attempt_finished', {'verdict': outcome['verdict'], 'summary_ref': summary_ref,
                    'reason': '; '.join(outcome['reasons'])}, attempt_id=registration['candidate_id'], candidate_id=registration['candidate_id'],
                    event_id=registration['candidate_id'] + '-finished')
                summaries.append({'candidate_id': registration['candidate_id'], 'summary_ref': summary_ref,
                    'verdict': outcome['verdict'], 'first_failed_stage': result['first_failed_stage'],
                    'speedup': result['speedup'], 'speedup_lcb': result['speedup_lcb'], 'max_regression': result['max_regression'],
                    'lesson_status': record['lesson']['status'], 'outcome_ref': outcome_ref})
            eligible = [outcome for outcome in outcomes if outcome['verdict'] in ('production_safe_gain', 'benchmark_specialized_gain')]
            best = min(eligible, key=lambda outcome: (-outcome['utility'], outcome['candidate_id'])) if eligible else None
            selected = next((item for item in attempts if best and item['registration']['candidate_id'] == best['candidate_id']), None)
            source_hash = (selected['registration']['source_hashes']['candidate'] if selected else attempts[0]['registration']['source_hashes']['baseline'])
            selection = {'candidate_id': best['candidate_id'] if best else None, 'source_hash': source_hash,
                'reason': 'Verified benchmark gain (correctness, stability, LCB, regression and mechanism gates) with greatest machine utility; production scope remains as recorded.' if best else 'No candidate passed the correctness, stability, gain, regression and mechanism gates; retain the validated baseline.',
                'source_directory': str(task / 'best_source'), 'graph_policy_eligible': False,
                'verdict': best['verdict'] if best else 'baseline_retained'}
            save(task / 'best_source_selection.json', selection)
            self.copy_snapshot(store, source_hash, task / 'best_source')
            report = {'schema_version': '1.0.0', 'run_id': self.run.name, 'operator': op, 'split': split,
                'status': 'completed', 'attempt_count': len(attempts), 'attempts': summaries, 'best_source': selection,
                'exploration_verification': verify_exploration(request, exploration_outcomes, store=store) if request else None,
                'graph_policy_eligible': bool(graph_episodes), 'episode_count_added': 0, 'graph_episode_count_imported': len(graph_episodes)}
            if any(item['calibration_block'] for item in attempts):
                report['measurement_status'] = 'blocked'
                report['measurement_reason'] = next(item['calibration_block']['reason'] for item in attempts if item['calibration_block'])
            report_ref = register_json_artifact(store, report)
            writer.append('task_finished', {'status': 'completed', 'reason': 'Frozen bounded campaign evaluated; all candidate attempts retained and verified.',
                'attempt_count': len(attempts), 'summary_ref': report_ref}, event_id=op + '-finished')
            self.verify_operator(op, store)
            save(task / 'finalization_report.json', report)
            return report

    @staticmethod
    def copy_snapshot(store, digest, destination):
        source = store.verify_artifact(digest)
        expected = {}
        with tarfile.open(source) as archive:
            for member in archive.getmembers():
                if member.name == 'APROF_SOURCE_SNAPSHOT.json':
                    continue
                parts = Path(member.name).parts
                if not parts or parts[0] != 'source' or len(parts) < 2 or not member.isfile():
                    raise StoreError('unsafe source snapshot member')
                relative = Path(*parts[1:])
                if relative.is_absolute() or '..' in relative.parts:
                    raise StoreError('unsafe source snapshot member')
                with archive.extractfile(member) as incoming:
                    expected[relative] = (incoming.read(), member.mode & 0o777)
        if not expected:
            raise StoreError('source snapshot contains no source files')
        if destination.exists():
            existing = {path.relative_to(destination) for path in destination.rglob('*') if path.is_file()}
            if existing != set(expected) or any((destination / relative).read_bytes() != payload
                    for relative, (payload, _) in expected.items()):
                raise StoreError('best_source no longer matches the verified source snapshot')
            return
        temporary = destination.with_name('.best-source-staging')
        temporary.mkdir(parents=True, exist_ok=True)
        try:
            for relative, (payload, mode) in expected.items():
                target = temporary / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)
                target.chmod(mode)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)

    def verify_operator(self, op, store):
        task = self.campaign.task(op)
        selection_path = task / 'best_source_selection.json'
        if selection_path.exists():
            self.copy_snapshot(store, read(selection_path)['source_hash'], task / 'best_source')
        return {'events': verify_trace(task / 'trace_events.jsonl', store),
            'summaries': verify_optimization_traces(task / 'optimization_traces.jsonl', store),
            'exploration': verify_exploration(read(task / 'exploration_request.json'), read(task / 'exploration_outcomes.json'), store=store)
                if (task / 'exploration_request.json').exists() else None,
            'store': store.verify_integrity()}

    def export(self):
        reports = [read(self.campaign.task(op) / 'finalization_report.json') for op in self.campaign.manifest['operators']]
        reports_by_operator = dict(zip(self.campaign.manifest['operators'], reports))
        verification = {}
        for split in ('train', 'validation'):
            ops = [op for op in self.campaign.manifest['operators'] if self.campaign.split(op) == split]
            directory = self.run / split
            with EpisodeStore(directory / 'episodes.sqlite') as store:
                streams = [self.campaign.task(op) / 'trace_events.jsonl' for op in ops]
                merged = merge_trace_streams(streams, directory / 'trace_events.jsonl', store)
                summaries = []
                for op in ops:
                    task_records = rows(self.campaign.task(op) / 'optimization_traces.jsonl')
                    report = reports_by_operator[op]
                    expected = [item['candidate_id'] for item in report['attempts']]
                    observed = [record['identity']['candidate_id'] for record in task_records]
                    if (report['attempt_count'] != len(expected) or len(expected) != len(set(expected))
                            or len(observed) != len(set(observed)) or set(observed) != set(expected)
                            or any(record['identity']['task_id'] != op
                                or record['identity']['run_id'] != self.run.name
                                or record['identity']['split'] != split for record in task_records)):
                        raise StoreError('task summary candidate coverage/identity differs from finalization report: ' + op)
                    summaries.extend(task_records)
                expected_summaries = {canonical_json(record) for record in summaries}
                try:
                    existing_summaries = rows(directory / 'optimization_traces.jsonl')
                except (ValueError, UnicodeError) as exc:
                    raise StoreError('invalid existing split summary stream') from exc
                if any(canonical_json(record) not in expected_summaries for record in existing_summaries):
                    raise StoreError('existing split summary differs from the complete finalized candidate set')
                write_optimization_traces(directory / 'optimization_traces.jsonl', summaries, store)
                verification[split] = {'events': merged, 'summaries': verify_optimization_traces(directory / 'optimization_traces.jsonl', store),
                    'episodes': export_episodes(store, directory / 'episodes.jsonl'), 'store': store.verify_integrity()}
        # Compatibility files combine split outputs; verification remains against
        # each split's own CAS rather than pretending there is one shared store.
        merge_trace_streams([self.run / split / 'trace_events.jsonl' for split in ('train', 'validation')], self.run / 'trace_events.jsonl')
        for name in ('optimization_traces.jsonl', 'episodes.jsonl'):
            payload = ''.join((self.run / split / name).read_text() for split in ('train', 'validation') if (self.run / split / name).exists())
            path = self.run / name
            if path.exists() and path.read_text() != payload:
                raise StoreError('campaign compatibility export differs from existing finalized bytes')
            path.write_text(payload)
        result = {'schema_version': '1.0.0', 'run_id': self.run.name, 'status': 'completed',
            'operator_count': len(reports), 'attempt_count': sum(report['attempt_count'] for report in reports),
            'operators': reports, 'verification': verification, 'policy_updates': False}
        save(self.run / 'campaign_summary.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, default=DEFAULT_RUN)
    parser.add_argument('--operator', help='Finalize one operator; omit to finalize and export the entire campaign.')
    parser.add_argument('--export-only', action='store_true', help='Merge and verify already-finalized operator outputs.')
    args = parser.parse_args()
    finalizer = Finalizer(args.run)
    if args.export_only:
        if args.operator:
            parser.error('--export-only cannot be combined with --operator')
        result = finalizer.export()
    elif args.operator:
        result = finalizer.finalize_operator(args.operator)
    else:
        for op in finalizer.campaign.manifest['operators']:
            finalizer.finalize_operator(op)
        result = finalizer.export()
    print(json.dumps(result, allow_nan=False))


if __name__ == '__main__':
    main()
