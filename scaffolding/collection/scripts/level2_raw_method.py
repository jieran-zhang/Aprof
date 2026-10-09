#!/usr/bin/env python3
"""One-process local-raw qualification, explicitly not an A/A calibration.

Execute only after all old capture processes stop and new engineering is frozen.
Every invocation requires a fresh group; failures never trigger an automatic retry.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import time

from level2_campaign import OPERATORS
from msprof_exploration_campaign import Campaign
from msprof_exploration_execute import (cohort_plan, event, execution_modules, load,
    native_started_in, pointer, preflight_cohort, save, sha, task_paths)
from msprof_exploration_report import verify_observation
from msprof_raw_storage import LOCAL
from run_msprof_exploration_stage import actual_costs, measurement_options, verify_source_snapshot

VERSION = 'level2_local_raw_method_qualification_v1'


def qualify(run, operator, *, case_id=1, group='raw-local-method-01', epoch='local-raw-01'):
    if operator not in OPERATORS or type(case_id) is not int or not 1 <= case_id <= 20:
        raise ValueError('one declared Level2 operator/case is required')
    if not isinstance(group, str) or re.fullmatch(r'raw-local-method-[A-Za-z0-9][A-Za-z0-9_-]*', group) is None:
        raise ValueError('a fresh named raw-local-method-* group is required')
    measurement_options({'epoch': epoch, 'capture_storage': LOCAL})
    run, split, task, parent, source = task_paths(run, operator, 'baseline')
    out = parent / 'stages' / group
    if out.exists():
        raise FileExistsError(out)
    ledger = Campaign(run / split / 'ledger')
    baseline_hash = ledger.config['tasks'][operator]['baseline_source_hash']
    if sha(task / 'baseline-source.tar') != baseline_hash:
        raise ValueError('method source differs from original baseline')
    verify_source_snapshot(task / 'baseline-source.tar', source)
    template = cohort_plan(task, parent / 'build/build_manifest.json', run / 'tools/timing/build.json',
                           [case_id], 'aa', group, epoch=epoch, capture_storage=LOCAL)
    request = deepcopy(template['schedule'][0]['request'])
    if (request.get('version') != 'msprof_kernel_time_study_v2' or request.get('warmup', 10) != 10
            or request.get('pairs', 30) != 30 or request.get('buffer_configs') != 'normal,swapped'
            or request.get('load_order') != 'AB' or request.get('first_order') != 'AB'
            or [row['case_id'] for row in request['cases']] != [case_id]
            or request['cases'][0].get('repeat') not in (1, 10)):
        raise ValueError('method request differs from reviewed complete-call protocol')
    sid = 'baseline-' + group
    plan = {'version': VERSION, 'protocol': template['protocol'], 'case_ids': [case_id],
        'source_hash': baseline_hash, 'manifest_ref': sha(task / 'manifest.json'),
        'control_type': 'method', 'control_phase': group, 'group': group,
        'producer': pointer(__file__), 'request': request,
        'cohort_template': template, 'selected_schedule_index': 0,
        'declared_native_processes': 1, 'calibration_eligible': False,
        'template_scope': 'Six-entry template provides frozen input/build identities; only entry zero executes.'}
    ledger.validate_start(workload=operator, candidate_id=None, stage_id=sid, kind='control', plan=plan)
    out.mkdir(parents=True, exist_ok=False)
    save(out / 'stage-plan.json', plan)
    save(out / 'request.json', request)
    ledger.start(event_id=operator+'-'+sid+'-start', workload=operator, candidate_id=None,
                 stage_id=sid, kind='control', plan=plan)
    event(task, 'stage_started', {'candidate_id': None, 'stage': sid, 'kind': 'control',
                                'plan': pointer(out / 'stage-plan.json')})
    started = time.time();error = None;verified = None;provenance = []
    try:
        save(out / 'identity-preflight.json', preflight_cohort(template))
        timing, _, _ = execution_modules()
        # collect() owns the same host/device locks and profiling flags as every
        # formal session. This method wrapper does not nest or replace that lock.
        timing.collect(out / 'request.json', out / 'evidence')
        verified = verify_observation(out / 'evidence', expected_request=request, provenance_out=provenance)
        save(out / 'observation.json', verified)
        costs = actual_costs(out)
        if (costs['native_processes_started'] != 1 or costs['native_processes_completed'] != 1
                or costs['role_samples'] != 120 or costs['warmup_complete_calls'] != 40
                or costs['timed_complete_calls'] != 120 * request['cases'][0]['repeat']):
            raise ValueError('single-process method execution/counts differ')
        save(out / 'method-qualification.json', {'version': VERSION, 'status': 'passed',
            'request': pointer(out / 'request.json'), 'observation': pointer(out / 'observation.json'),
            'native_processes': 1, 'case_ids': [case_id], 'calibration_eligible': False,
            'six_process_cohort_report_emitted': False,
            'scope': 'Complete-call parser, correctness, transport closure and actual-argv replay for one native process only.'})
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
    costs = actual_costs(out)
    costs['wall_seconds'] = int(time.time() - started)
    native_started = costs['native_processes_started'] > 0 or bool(native_started_in(out))
    result = {'status': 'failed' if error else 'passed', 'kind': 'control', 'control_type': 'method',
        'stage_id': sid, 'candidate_id': None, 'started_at': started, 'ended_at': time.time(),
        'error': error, 'native_started': native_started, 'actual_costs': costs,
        'calibration_eligible': False, 'formal_admission': 'not_evaluated',
        'graph_policy_eligible': False, 'episode_ref': None}
    save(out / 'identity-resolution.json', {'read_only_resolution': True, 'producer_bindings': provenance})
    save(out / 'result.json', result)
    evidence = {'result': pointer(out / 'result.json'), 'request': pointer(out / 'request.json'),
                'stage_plan': pointer(out / 'stage-plan.json')}
    if verified is not None:
        evidence['observation'] = pointer(out / 'observation.json')
    if (out / 'method-qualification.json').is_file():
        evidence['method_qualification'] = pointer(out / 'method-qualification.json')
    ledger.finish(event_id=operator+'-'+sid+'-finish', workload=operator, stage_id=sid,
        outcome='failed' if error else 'success', evidence=evidence, native_started=native_started,
        formal_samples=costs['role_samples'], actual_costs=costs, reason=json.dumps(error) if error else None)
    event(task, 'stage_completed', {'candidate_id': None, 'stage': sid, 'result': pointer(out / 'result.json')})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--operator', choices=OPERATORS, default='maximum')
    parser.add_argument('--case', type=int, default=1)
    parser.add_argument('--group', default='raw-local-method-01')
    parser.add_argument('--epoch', default='local-raw-01')
    args = parser.parse_args()
    result = qualify(args.run, args.operator, case_id=args.case, group=args.group, epoch=args.epoch)
    print(json.dumps(result), flush=True)
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
