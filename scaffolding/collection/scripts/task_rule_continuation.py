#!/usr/bin/env python3
"""Complete the missing PMU role of a separately verified, failed exp trial.

This is a continuation, not a retry of its measurements or its original job.
It never builds, reviews, runs formal timing, edits parent evidence or archives.
Only the known, reviewed original collector bytes may execute from retention.
"""
from __future__ import annotations

import argparse
import importlib.machinery
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time

from shared_validation_adapter import selected_runtime

RELEASE = selected_runtime()
sys.path.insert(0, str(RELEASE / 'skills/ascendc-aprof-profiling/scripts'))
from aprof_runtime.jsonio import file_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.profile_evidence import load_capture_manifest, normalize_profile
from normalize_profile import expand_specs
from timing_admission import read, require

ORIGINAL_COLLECTOR = 'sha256:701d51a65e946c00e2ee3b33deec8c2caa974601c6ac744976338cb23c81f2bc'


class Evidence:
    """New task-local records plus read-only, content-addressed parent evidence."""
    def __init__(self, local, object_roots):
        self.local, self.object_roots = local, tuple(Path(p) for p in object_roots)

    def verify_artifact(self, reference):
        require(isinstance(reference, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', reference),
                'invalid continuation evidence reference')
        if reference in self.local._paths:
            return self.local.verify_artifact(reference)
        digest = reference[7:]
        for root in self.object_roots:
            path = root / digest[:2] / digest[2:]
            if path.is_file():
                require(not path.is_symlink() and file_hash(path) == reference, 'retained evidence changed')
                return path
        raise ValueError('continuation evidence not found: ' + reference)

    def register_json(self, value):
        return self.local.register_json(value)

    def register_artifact(self, path, **kwargs):
        return self.local.register_artifact(path, **kwargs)

    def object_path(self, reference):
        return self.verify_artifact(reference)


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def original_collector(reader):
    path = reader.verify_artifact(ORIGINAL_COLLECTOR)
    loader = importlib.machinery.SourceFileLoader('aprof_exp_original_profile_capture', str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    require(module.file_hash(path) == ORIGINAL_COLLECTOR, 'original collector identity changed')
    return module


def merge_local(local, index):
    other = LocalEvidence.from_index(index)
    for reference in json.loads(Path(index).read_text())['artifacts']:
        require(local.register_artifact(other.verify_artifact(reference)) == reference,
                'new PMU evidence changed')


def validate_capture_plan(reader, plan, prefix, output):
    """Derive all executable arguments from admitted Task bytes and fresh paths."""
    config = read(reader, prefix['checks']['task']['config_ref'])
    protocol = read(reader, prefix['protocol_ref'])
    original = read(reader, protocol['profile_configs']['candidate'])
    case = next(row for row in config['cases'] if row['case_id'] == 3)
    expand = lambda values: [token.replace('{cycle_dir}', str(output)) for token in values]
    wanted = dict(original, command=expand(case['command']) + ['--aprof-mechanism-role', 'candidate'])
    oracle = expand(case['verify_commands']['candidate'])
    paths = expand(case['output_files']['candidate'])
    require(plan['candidate_profile_config'] == wanted and plan['oracle_command'] == oracle
            and plan['output_files'] == paths,
            'continuation changed the admitted PMU/oracle command or output routing')
    registration = read(reader, prefix['checks']['task']['registration_ref'])
    require(plan['source_hashes'] == prefix['measurement_expected']['source_hashes']
            and plan['binary_ref'] == registration['identity']['build']['binary_ref'],
            'continuation changed the admitted source or binary')
    # The combined launch can write either role's outputs. Every output and the
    # oracle result must stay in the fresh continuation directory.
    writes = [p for role in ('baseline', 'candidate') for p in expand(case['output_files'][role])]
    writes.append(oracle[oracle.index('--result') + 1])
    for name in writes:
        path = Path(name)
        require(path.is_absolute() and path.resolve() == path and path.is_relative_to(output)
                and path != output and not path.exists() and not path.is_symlink(),
                'continuation would overwrite evidence or write outside its fresh workspace')
    require(not (output / 'candidate').exists(), 'candidate PMU has already been attempted')
    return wanted


def finalize_gate(reader, plan, prefix, candidate_profile):
    """Apply the unchanged machine gate to old timings and the completed PMU pair."""
    from task_rule_controller import _gate, _trace
    report = read(reader, prefix['report_ref'])
    protocol = read(reader, prefix['protocol_ref'])
    frozen = read(reader, plan['frozen_candidate_ref'])
    baseline_manifest = load_capture_manifest(reader, plan['baseline_manifest_ref'])
    baseline = normalize_profile(reader, plan['baseline_manifest_ref'], expand_specs(baseline_manifest, plan['specs']))
    baseline_ref = reader.register_json(baseline)
    candidate_ref = reader.register_json(candidate_profile)
    metric = plan['choice']['metric']
    mechanism = dict(schema_version='1.0.0', candidate_id=prefix['measurement_expected']['candidate_id'],
        hypothesis_basis='heuristic', metrics=[dict(name=metric, unit=plan['specs'][metric]['unit'],
            expected_direction=plan['choice']['expected_direction'],
            baseline=baseline['metrics'][metric]['value'], candidate=candidate_profile['metrics'][metric]['value'],
            baseline_profile_hash=baseline_ref, candidate_profile_hash=candidate_ref)])
    completion = read(reader, report['measurement_admission_ref'])
    proof = read(reader, completion['proof_ref'])
    artifacts = dict(source_review=prefix['source_review_ref']['sha256'], build_log=prefix['build_receipt_ref'],
        accuracy_report=report['correctness_report_ref'], boundary_report=report['boundary_report_ref'],
        measurement_admission=report['measurement_admission_ref'], measurement_report=proof['measurement_report_ref'],
        timing_raw=proof['raw_ref'], timing_config=proof['config_ref'],
        mechanism_report=reader.register_json(mechanism), hardware_report=baseline_manifest['hardware_hash'],
        qualification_registration=prefix['qualification_registration_ref'], qualification_campaign=plan['campaign_ref'],
        continuation_plan=plan['plan_ref'], continuation_amendment=plan['amendment_ref'])
    artifacts['scope_report'] = reader.register_json(dict(passed=True, source_review_ref=artifacts['source_review'],
        correctness_ref=artifacts['accuracy_report'], boundary_ref=artifacts['boundary_report'],
        scope='exp only; original frozen 910C/A3 CANN 9.0.0 full workload; reused evidence and missing candidate PMU'))
    measurement = read(reader, artifacts['measurement_report'])
    request, outcome = _gate(reader, frozen, artifacts, measurement)
    request_ref, outcome_ref = reader.register_json(request), reader.register_json(outcome)
    trace_ref = reader.register_json(_trace(reader, frozen, 'exp', artifacts, measurement, outcome, outcome_ref))
    return dict(exploration_request_ref=request_ref, exploration_outcome_ref=outcome_ref, trace_ref=trace_ref,
        formal_outcome=outcome['verdict'], baseline_profile_ref=baseline_ref,
        mechanism_report_ref=artifacts['mechanism_report'], hardware_report_ref=artifacts['hardware_report'],
        measurement_expected=prefix['measurement_expected'],
        profile_configs=dict(baseline=protocol['profile_configs']['baseline'],
                             candidate=reader.register_json(plan['candidate_profile_config'])))


def run(plan_path):
    started, mono = time.time(), time.monotonic()
    plan_path = Path(plan_path).resolve(strict=True)
    plan = json.loads(plan_path.read_text())
    output = Path(plan['directory'])
    require(output == plan_path.parent and output.resolve() == output and not (output / 'result.json').exists(),
            'continuation must use a fresh canonical task workspace')
    require(plan['kind'] == 'exp_pmu_continuation_v1' and plan['new_roles'] == ['candidate']
            and plan['actual_new_builds'] == 0 and plan['new_formal_timing_pairs'] == 0,
            'continuation may only fill the missing candidate PMU role')
    require(file_hash(Path(__file__)) == plan['runner_ref'], 'continuation runner changed after registration')
    require(all(type(plan[k]) in (int, float) and math.isfinite(plan[k]) for k in
                ('created_at', 'parent_duration_seconds', 'total_budget_seconds', 'additional_budget_seconds'))
            and plan['created_at'] <= started and 0 < plan['parent_duration_seconds'] < 5400
            and plan['total_budget_seconds'] == 5400
            and plan['additional_budget_seconds'] == 5400 - plan['parent_duration_seconds'],
            'continuation changed the separately authorized cumulative budget')
    launch = json.loads((output / 'launch.json').read_text())
    require(launch['plan_ref'] == file_hash(plan_path)
            and plan['created_at'] <= launch['started_at'] <= started
            and 0 < launch['started_monotonic'] <= mono
            and launch['deadline_monotonic'] == launch['started_monotonic'] + plan['additional_budget_seconds'],
            'continuation changed its new dispatcher deadline')
    deadline = launch['deadline_monotonic']
    local = LocalEvidence(output / 'records')
    reader = Evidence(local, plan['object_roots'])
    local.register_artifact(plan_path)
    local.register_artifact(output / 'launch.json')
    result = dict(schema_version=1, kind='exp_pmu_continuation_result_v1', status='failed',
        plan_ref=file_hash(plan_path), started_at=started, actual_new_builds=0,
        new_formal_timing_pairs=0, archive_performed=False, storage_mode='local_profile_only',
        parent_status='failed', error=None)
    try:
        for path, reference in plan['frozen_files'].items():
            require(file_hash(Path(path)) == reference, 'continuation frozen input/producer changed: ' + path)
            local.register_artifact(path)
        # A separately recorded read-only replay is a precondition. Publication
        # replays these raw components independently; this summary cannot admit.
        prefix = read(reader, plan['prefix_replay_ref'])
        require(prefix['valid'] is True and prefix['parent_status'] == 'failed'
                and prefix['eligible_for_publication'] is False,
                'continuation lacks the independently replayed failed-parent prefix')
        collector = original_collector(reader)
        config = validate_capture_plan(reader, plan, prefix, output)
        require(config['role'] == 'candidate' and config['warmups'] == 10 and config['repeats'] == 5
                and config['case_id'] == 3 and config['command'][-2:] == ['--aprof-mechanism-role', 'candidate'],
                'candidate PMU scope changed')
        require(time.monotonic() < deadline, 'continuation budget exhausted before capture')
        save(output / 'profile-start.json', dict(started_at=time.time(), plan_ref=file_hash(plan_path)))
        # The dispatcher owns the device lock and cumulative timeout. Retain the
        # original collector, including its per-command timeout, for comparison.
        captured = collector.capture(config, output / 'candidate')
        merge_local(local, captured['local_index'])
        manifest = load_capture_manifest(reader, captured['manifest_hash'])
        require(manifest['collector_hash'] == ORIGINAL_COLLECTOR, 'PMU collector changed')
        require(manifest['binary_hash'] == plan['binary_ref'] and manifest['source_hash'] == plan['source_hashes']['candidate'],
                'candidate source/binary differs from reused formal timing')
        outputs = {path: local.register_artifact(path) for path in plan['output_files']}
        require(time.monotonic() < deadline, 'continuation budget exhausted before oracle')
        oracle = collector.run(plan['oracle_command'], Path(config['cwd']), output / 'candidate-oracle',
                               min(120, deadline - time.monotonic()), local)
        verdict_path = Path(plan['oracle_command'][plan['oracle_command'].index('--result') + 1])
        # The repair: parse stdout only. Preserve stderr as separate raw evidence.
        verdict = json.loads(verdict_path.read_text())
        require(oracle['exit_code'] == 0 and oracle['error'] is None and verdict.get('passed') is True
                and verdict.get('case_id') == 3
                and json.loads(reader.verify_artifact(oracle['stdout_hash']).read_text()) == verdict,
                'candidate complete-output oracle failed')
        require(outputs == {path: file_hash(Path(path)) for path in outputs}, 'oracle changed full output')
        result['candidate_oracle_result_ref'] = local.register_artifact(verdict_path)
        result['candidate_oracle_ref'] = oracle['log_hash']
        result['candidate_output_hashes'] = outputs
        profile = normalize_profile(reader, captured['manifest_hash'], expand_specs(manifest, plan['specs']))
        result['candidate_profile_ref'] = local.register_json(profile)
        result['candidate_manifest_ref'] = captured['manifest_hash']
        result['profile_finished_at'] = time.time()
        result['gate_started_at'] = time.time()
        from task_rule_continuation_admission import retained_producer_scope
        with retained_producer_scope(reader, anchor_ref=plan['parent_anchor_ref'],
                                     trusted_review_refs=plan['trusted_review_refs']):
            result.update(finalize_gate(reader, dict(plan, plan_ref=file_hash(plan_path)), prefix, profile))
        result['gate_finished_at'] = time.time()
        require(result['formal_outcome'] == 'production_safe_gain', 'continued candidate did not pass the machine gate')
        for path, reference in plan['frozen_files'].items():
            require(file_hash(Path(path)) == reference, 'continuation frozen bytes changed during capture')
        require(time.monotonic() < deadline, 'continuation exceeded its separately registered budget')
        result['status'] = 'passed'
    except BaseException as exc:
        result['error'] = {'type': type(exc).__name__, 'message': str(exc)}
        partial = output / 'candidate/local-index.json'
        if partial.exists():
            merge_local(local, partial)
    finally:
        result.update(finished_at=time.time(), duration_seconds=time.monotonic() - mono)
        result['cumulative_online_seconds'] = plan['parent_duration_seconds'] + time.monotonic() - launch['started_monotonic']
        save(output / 'result.json', result)
        local.register_artifact(output / 'result.json')
        for name in ('profile-start.json',):
            if (output / name).exists(): local.register_artifact(output / name)
        local.write_index(output / 'local-index.json')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    args = parser.parse_args()
    outcome = run(args.plan)
    print(json.dumps(outcome, sort_keys=True))
    raise SystemExit(0 if outcome['status'] == 'passed' else 2)
