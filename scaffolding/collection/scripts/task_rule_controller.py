#!/usr/bin/env python3
"""Run one preregistered exp/sigmoid rule trial using only task-local evidence.

The trusted dispatcher supplies the anchor and records the real process exit.
This process includes blind review, one build, correctness, boundary, screen,
Task controls, PMU and the runtime gate in one wall deadline. It never archives
or writes an EpisodeStore. The separate collector owns post-task replay.
"""
from __future__ import annotations
from task_budget import teacher_budget, rule_execution_job, collection_policy, collection_unit_deadline

import argparse
import json
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace

import task_screen_bridge as screen
from eval_candidate_evidence import verify_blind_source_review
from evaluate_skill_release import review_candidate
from task_rule_admission import PROTOCOL, TASK_PROTOCOL
from task_rule_recorder import TaskRuleRecorder
from timing_admission import read, require
from validation_host_evaluator import Commands, freeze_candidate

bridge, ROLES = screen.bridge, screen.ROLES
from aprof_runtime.exploration import ExplorationGate, freeze_exploration_manifest
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.traces import (TraceWriter, make_optimization_trace, register_json_artifact,
                                  validate_optimization_trace)

MODEL = {'name': 'gpt-6-sol', 'reasoning_effort': 'max'}
GAP = ('Explicit independent Teacher rule experiment with frozen original sources; '
       'missing graph predicates remain unknown and no graph edge or policy episode is claimed.')


def reference(path):
    path = Path(path).resolve(strict=True)
    return {'path': str(path), 'sha256': bridge.file_hash(path)}


def profile_configs(assembly, build_path, config, choice, output):
    """Freeze complete-call commands before the first device stage."""
    proof, build = screen.checked_build(assembly, build_path)
    require(set(choice) == {'case_id', 'kernel', 'metric', 'expected_direction'}
            and choice['kernel'] == proof['operator'] + '_kernel'
            and choice['expected_direction'] == 'decrease', 'unregistered rule mechanism choice')
    case = next(c for c in config['cases'] if c['case_id'] == choice['case_id'])
    return {role: dict(backend='auto', architecture='Ascend910C', soc='Ascend910_9392',
        device=0, physical_device=config['physical_device'], chip=0, case_id=choice['case_id'],
        role=role, kernel=proof['role_kernel_names'][role][0], source_dir=proof['roles'][role]['path'],
        binary=build['binary']['path'], cwd=str(Path(assembly) / 'source'), workload=case['workload'],
        command=[arg.replace('{cycle_dir}', str(output)) for arg in case['command']]
                + ['--aprof-mechanism-role', role], warmups=10, repeats=5, timeout_seconds=180)
        for role in ROLES}


def _api():
    # Task bind_identity freezes canonical JSON. Preserve that identity from
    # the proposal onward, including the unchanged source-file hashes.
    def source_bundle(source, _output, local):
        return local.register_json(dict(schema_version='1.0.0',
            files=bridge.profile_capture.source_inventory(source, local)))
    return dict(profiler=SimpleNamespace(source_bundle=source_bundle), TraceWriter=TraceWriter,
        freeze_exploration_manifest=freeze_exploration_manifest,
        register_json_artifact=register_json_artifact)


def _register_review(local, workspace, model):
    review = verify_blind_source_review(workspace, bridge.RELEASE, model=model)
    require(review['accepted'] is True, 'independent source review failed or remained unknown')
    value = review['source_review']
    references = [review['source_review_ref'], value['worker_receipt_ref']]
    references += [value[k] for k in ('contract_ref', 'checklist_ref', 'boundaries_ref', 'prompt_ref')]
    worker = json.loads(Path(value['worker_receipt_ref']['path']).read_text())
    references += [worker[k] for k in ('events_ref', 'broker_ref', 'qualification_ref')]
    for pointer in references:
        require(local.register_artifact(pointer['path']) == pointer['sha256'], 'review reference changed')
    return review['source_review_ref']['sha256'], worker['usage']['totalTokens']


def _screen_stage(local, recorder, plan, assembly, build_path, directory, *, deadline, policy):
    """The fixed six-case screen is one complete task collection unit."""
    recorder.start('screen')
    unit_ref, unit_deadline = None, deadline
    if policy is not None:
        unit_started, unit_wall = time.monotonic(), time.time()
        unit_deadline = collection_unit_deadline(deadline, policy, 'task', now=unit_started)
        unit_path = directory / 'screen-collection-unit.json'
        bridge.save(unit_path, dict(schema_version=1, started_at=unit_wall,
            started_monotonic=unit_started, deadline_monotonic=unit_deadline))
        unit_ref = local.register_artifact(unit_path)
    screened = screen.collect_screen(assembly, build_path, plan['prepared_dir'], directory / 'screen',
        physical_device=plan['physical_device'], deadline=unit_deadline)
    bridge.merge_index(local, screened['local_index'])
    screen_ref = local.register_artifact(directory / 'screen/screen-result.json')
    require(read(local, screen_ref)['status'] == 'passed', 'exploratory screen rejected')
    bridge.remaining(unit_deadline)
    recorder.complete('screen', [screen_ref] + ([unit_ref] if unit_ref is not None else []),
                      report_ref=screen_ref)


def _gate(local, frozen, artifacts, report):
    evidence = dict(candidate_id=frozen['candidate']['candidate_id'],
        static_review='passed', build='passed', accuracy='passed', runtime='passed',
        semantic='passed', scope='passed', portability='passed', artifacts=artifacts,
        mechanism_alignment=None, **report['gate_projection'])
    request = dict(schema_version='1.0.0', frozen_manifest_hash=frozen['frozen_manifest_hash'],
        candidates=[frozen['candidate']], evidence=[evidence], config={})
    outcomes = ExplorationGate().evaluate(request, store=local)
    return request, outcomes[0]


def _trace(local, frozen, operator, artifacts, report, outcome, outcome_ref):
    candidate = frozen['candidate']
    stages = {name: {'status': 'passed', 'reason': 'actual source-bound rule trial stage',
        'artifact_refs': [artifacts[artifact]]} for name, artifact in (
        ('static_review', 'source_review'), ('build', 'build_log'),
        ('correctness', 'accuracy_report'), ('runtime', 'accuracy_report'),
        ('timing', 'measurement_report'), ('profile', 'mechanism_report'))}
    trace = make_optimization_trace(dict(run_id=frozen['run_id'], task_id=operator,
        session_id=candidate['session_id'], attempt_id=candidate['candidate_id'],
        candidate_id=candidate['candidate_id'], operator=operator, split='train',
        source_parent_hash=candidate['source_hashes']['baseline']),
        provenance=dict(baseline_source_hash=candidate['source_hashes']['baseline'],
            candidate_source_hash=candidate['source_hashes']['candidate'], patch_hash=candidate['patch_artifact_hash']),
        intervention=dict(handler=dict(id=candidate['handler_id'], version=candidate['handler_version'],
            producer_hash=None), parameters=candidate['parameters']),
        routing=dict(mode='exploration', route=None, coverage_gap=GAP),
        workload=dict(case_ids=list(range(1, 21)), hardware_fingerprint=artifacts['hardware_report']),
        validation=dict(**stages, case_count=20, passed_count=20, timing_case_ids=list(range(1, 21))),
        result=dict(verdict=outcome['verdict'], speedup=outcome['speedup'], speedup_lcb=outcome['speedup_lcb'],
            max_regression=report['max_case_regression'], exploration_outcome_ref=outcome_ref))
    # evaluate() already replays the complete evidence above. The independent
    # post-task verifier replays the saved request/outcome/trace against raw data.
    validate_optimization_trace(trace)
    return trace


def run(anchor_path, index_path):
    started, monotonic_started = time.time(), time.monotonic()
    local = LocalEvidence.from_index(index_path)
    anchor_ref = local.register_artifact(anchor_path)
    anchor = read(local, anchor_ref)
    require(anchor['schema_version'] == 1 and anchor['protocol'] == PROTOCOL
            and anchor['task_protocol'] == TASK_PROTOCOL and anchor['purpose'] == 'promotion'
            and anchor['operator'] in ('exp', 'sigmoid') and teacher_budget(lambda ref: read(local, ref), anchor) > 0,
            'rule trial needs the frozen finite promotion protocol')
    plan = read(local, anchor['controller_plan_ref'])
    directory = Path(plan['directory']); workspace = directory / 'worker/root/work'
    require(plan['model'] == MODEL and Path(plan['release']).resolve() == bridge.RELEASE
            and bridge.RELEASE.name == '1.0.0', 'rule controller/model/release differs')
    require(Path(index_path).resolve().is_relative_to(directory.resolve())
            and Path(anchor_path).resolve().is_relative_to(directory.resolve()), 'trial files escaped workspace')
    require(not (directory / 'controller-result.json').exists(), 'rule attempt already has a terminal result')
    with (directory / 'controller-start.json').open('x') as stream:
        json.dump({'started_at': started, 'anchor_ref': anchor_ref}, stream)
    launch = json.loads(Path(plan['launch_path']).read_text())
    require(launch['schema_version'] in (1, 2) and launch['anchor_ref'] == anchor_ref
            and launch['job_ref'] == anchor['job_ref'] and launch['started_at'] <= started,
            'dispatcher launch differs from the frozen trial')
    rule_execution_job(lambda ref: read(local, ref), anchor, read(local, anchor['job_ref']), launch)
    deadline = launch['monotonic_deadline']
    require(deadline <= monotonic_started + anchor['budget_seconds'], 'child renewed the original budget')
    bridge.remaining(deadline)
    commands = Commands(directory / 'commands', deadline)
    assembly = Path(plan['assembly']); proof = screen.source_identity(assembly)
    require(bridge.file_hash(assembly / 'source-review.json') == anchor['source_review_ref']
            and {r: proof['historical_source_binding']['roles'][r]['sha256'] for r in ROLES} == anchor['source_hashes']
            and all(Path(proof['roles'][r]['path']) == workspace / r for r in ROLES), 'preregistered source identity differs')
    profile_plan = read(local, anchor['profile_plan_ref'])
    choice, specs = profile_plan['choice'], profile_plan['specs']
    require(set(specs) == {choice['metric']}, 'rule has one predeclared mechanism metric')
    expected = {k: anchor[k] for k in ('run_id', 'candidate_id', 'operator', 'source_hashes')}
    recorder, failure, outcome, child_ref = None, None, None, None
    artifacts, result = {}, {'schema_version': 1, 'status': 'failed', 'anchor_ref': anchor_ref,
        'started_at': started, 'archive_performed': False, 'storage_mode': 'local_profile_only'}
    try:
        import task_outer_admission as outer
        correctness = outer.correctness
        correctness.preflight_boundary_plan(local,operator=anchor['operator'],source_hashes=anchor['source_hashes'],
            boundary_plan_ref=anchor['boundary_plan_ref'],oracle_files=plan['boundary_oracle_files'])
        manifest = dict(tasks={anchor['operator']: plan['review_inputs']}, model=MODEL,
                        worker_qualification=plan['worker_qualification'], budget_plan={'path':str(local.verify_artifact(anchor['campaign_ref'])),'sha256':anchor['campaign_ref']})
        review_result = {'status': 'running'}
        review_candidate(manifest, {'operator': anchor['operator']}, directory,
                         deadline - anchor['budget_seconds'], review_result)
        require(review_result['status'] == 'running' and review_result['reviewer']['status'] == 'completed',
                'independent reviewer rejected or did not finish')
        artifacts['source_review'], result['reviewer_tokens'] = _register_review(local, workspace, MODEL)
        commands.remaining()
        frozen = freeze_candidate(_api(), local, workspace, directory, anchor['operator'],
            anchor['run_id'], choice, split='train', handler_id='teacher.fixed_task_rule', coverage_gap=GAP)
        require(frozen['candidate']['candidate_id'] == anchor['candidate_id'], 'candidate identity differs')
        for role in ROLES:
            require(read(local, frozen['candidate']['source_hashes'][role]) == read(local, anchor['source_hashes'][role]),
                    'Task source bundle differs from original frozen source files')
        build_path = bridge.build_teacher_rule_once(assembly, workspace, commands,
            model=MODEL, local=local, anchor_ref=anchor_ref)
        proof, build = screen.checked_build(assembly, build_path)
        require(local.register_artifact(build['binary']['path']) == build['binary']['sha256'],
                'compiled binary changed before registration')
        for pointer in [build['attempt_ref'], *[row[key] for row in build['commands'] for key in ('stdout', 'stderr')]]:
            require(local.register_artifact(pointer['path']) == pointer['sha256'], 'build evidence changed')
        artifacts['build_log'] = local.register_artifact(build_path)
        config = bridge.task_config(assembly, build_path, plan['prepared_dir'], plan['scratch_dir'],
            run_id=anchor['run_id'], session_id=frozen['candidate']['session_id'], candidate_id=anchor['candidate_id'],
            physical_device=plan['physical_device'], profiler=plan['profiler'])
        profiles = profile_configs(assembly, build_path, config, choice, directory / 'mechanism')
        oracle = workspace / 'baseline/scripts/verify_result.py'
        recorder = TaskRuleRecorder(local, directory / 'admission', anchor_ref=anchor_ref,
            post_build=dict(binary_hashes={r: build['binary']['sha256'] for r in ROLES},
                oracle_files={**plan['boundary_oracle_files'],str(oracle): local.register_artifact(oracle)},
                task_config_ref=local.register_json(config),
                profile_configs={r: local.register_json(v) for r, v in profiles.items()}), deadline=deadline)
        # The private verifier uses the identical screen-enabled assembly.
        for stage, prepared in (('correctness', plan['prepared_dir']), ('boundary', plan['boundary_dir'])):
            recorder.start(stage)
            collected = correctness.collect_correctness(assembly, build_path, prepared, directory / stage, local,
                expected=expected, deadline=deadline, protocol_ref=recorder.protocol_ref, stage=stage)
            artifacts['accuracy_report' if stage == 'correctness' else 'boundary_report'] = collected['report_ref']
            recorder.complete(stage, [collected['report_ref']], report_ref=collected['report_ref'])
        _screen_stage(local, recorder, plan, assembly, build_path, directory,
                      deadline=deadline, policy=collection_policy(anchor))
        recorder.start('task_measurement')
        measured = bridge.collect_task(config, directory / 'measurement', local, deadline=deadline,
            budget_binding={'kind':'teacher','launch_ref':local.register_artifact(plan['launch_path'])})
        completion_ref = measured['measurement_admission_ref']; completion = read(local, completion_ref)
        proof_ref = completion['proof_ref']; measurement = read(local, proof_ref)
        artifacts.update(measurement_admission=completion_ref, measurement_report=measurement['measurement_report_ref'],
            timing_raw=measurement['raw_ref'], timing_config=measurement['config_ref'])
        formal_refs = [completion_ref, proof_ref, measurement['config_ref'], measurement['registration_ref'],
                       measurement['measurement_report_ref']]
        recorder.complete('task_measurement', formal_refs, report_ref=completion_ref)
        recorder.start('profile')
        captured = bridge.capture_mechanism(assembly, build_path, config, choice, specs,
                                          directory / 'mechanism', local, deadline=deadline,
            budget_binding={'kind':'teacher','launch_ref':local.register_artifact(plan['launch_path'])})
        metric = choice['metric']
        mechanism = dict(schema_version='1.0.0', candidate_id=anchor['candidate_id'], hypothesis_basis='heuristic',
            metrics=[dict(name=metric, unit=specs[metric]['unit'], expected_direction=choice['expected_direction'],
                baseline=captured['baseline']['profile']['metrics'][metric]['value'],
                candidate=captured['candidate']['profile']['metrics'][metric]['value'],
                baseline_profile_hash=captured['baseline']['digest'], candidate_profile_hash=captured['candidate']['digest'])])
        artifacts['mechanism_report'] = local.register_json(mechanism)
        artifacts['hardware_report'] = captured['baseline']['hardware']
        profile_evidence=[artifacts['mechanism_report'], artifacts['hardware_report']]
        if 'collection_stop_policy' in anchor:
            profile_evidence += [captured[r]['collection_receipt_ref'] for r in ('baseline','candidate')]
        recorder.complete('profile', profile_evidence,
                          report_ref=artifacts['mechanism_report'])
        recorder.start('online_admission')
        artifacts['qualification_registration'] = recorder.registration_ref
        artifacts['qualification_campaign'] = anchor['campaign_ref']
        artifacts['scope_report'] = local.register_json(dict(passed=True,
            source_review_ref=artifacts['source_review'], correctness_ref=artifacts['accuracy_report'],
            boundary_ref=artifacts['boundary_report'], scope='frozen 910C/A3 complete original workload'))
        report = read(local, artifacts['measurement_report'])
        request, outcome = _gate(local, frozen, artifacts, report)
        request_ref, outcome_ref = local.register_json(request), local.register_json(outcome)
        trace_ref = local.register_json(_trace(local, frozen, anchor['operator'], artifacts, report, outcome, outcome_ref))
        commands.remaining()
        recorder.complete('online_admission', [request_ref, outcome_ref, trace_ref])
        child_ref = recorder.finish()
        result.update(status='passed', formal_outcome=outcome['verdict'], child_report_ref=child_ref,
            protocol_ref=recorder.protocol_ref, qualification_registration_ref=recorder.registration_ref,
            exploration_request_ref=request_ref, exploration_outcome_ref=outcome_ref, trace_ref=trace_ref,
            measurement_expected=dict(operator=anchor['operator'], run_id=anchor['run_id'],
                session_id=frozen['candidate']['session_id'], candidate_id=anchor['candidate_id'],
                source_hashes=frozen['candidate']['source_hashes'], measurement_report_ref=artifacts['measurement_report']))
    except Exception as exc:
        failure = {'type': type(exc).__name__, 'message': str(exc)}
        if recorder is not None:
            partial = getattr(exc, 'result', {}).get('report_ref')
            recorder.fail_active(exc, evidence=[partial] if partial else [])
            result['child_report_ref'] = recorder.partial_report()
    finally:
        if time.monotonic() >= deadline:
            result['status'] = 'failed'
            failure = failure or {'type': 'TimeoutError', 'message': 'original whole-trial deadline expired'}
        result.update(error=failure, finished_at=time.time(), duration_seconds=time.monotonic() - monotonic_started,
                      actual_builds=int((assembly / 'build-attempt.json').exists()))
        bridge.save(directory / 'controller-result.json', result)
        local.register_artifact(directory / 'controller-result.json')
        local.write_index(directory / 'controller-local-index.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--anchor', required=True, type=Path)
    parser.add_argument('--local-index', required=True, type=Path)
    args = parser.parse_args()
    def terminate(_signal, _frame):
        raise TimeoutError('trusted dispatcher terminated the rule trial')
    signal.signal(signal.SIGTERM, terminate)
    result = run(args.anchor, args.local_index)
    print(json.dumps({'status': result['status'], 'formal_outcome': result.get('formal_outcome')}))
    return 0 if result['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
