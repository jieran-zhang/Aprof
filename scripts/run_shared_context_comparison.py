#!/usr/bin/env python3
"""One explicitly declared candidate timing group; no search decisions or retries.

Search: run --run RUN --operator exp --candidate exp001 --purpose search.
Final: prepare --purpose final, freeze its ledger-plan.json, then collect --group
.../comparisons/final. No final native session can start before that exact freeze.

An optional --comparison-inputs JSON has a `comparisons` array ordered parent,
original (one original entry when those controls coincide). Each entry supplies
control, build, control_build and qualification_report. Distinct parents require
independent true parent/candidate and original/candidate builds and qualified A/A
controls; ratios are never composed. Paths in that JSON resolve relative to it.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
import time
from types import SimpleNamespace

import cannbench_shared_context as native
from feedback_hardware import run_process
import shared_context_build as build_tools
import shared_context_campaign as campaign
import shared_context_wrapper_evidence as wrapper_evidence

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'shared_context_comparison_group_v1'
load, save, sha = native.load, native.save, native.sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pointer(path):
    path = Path(path).resolve()
    return {'path': str(path), 'sha256': sha(path)}


def verify_pointer(value):
    require(sha(value['path']) == value['sha256'], 'frozen file changed: ' + value['path'])
    return Path(value['path'])


def source_binding(archive, directory, expected, build, role):
    """Use the shared snapshot-v1 validator for tar, native source and binary."""
    archive, directory = Path(archive).resolve(), Path(directory).resolve()
    require(Path(build['roles'][role]['source_dir']).resolve() == directory,
            'native role uses the wrong source directory: ' + role)
    bound = wrapper_evidence.archive_native_binding({'path': str(archive), 'sha256': expected}, build, (role,))
    return {'archive': bound['archive'], 'source_dir': str(directory),
            'native_source_hash': campaign.identity(bound['native_roles'][role]['source_sha256']),
            'snapshot_manifest_hash': bound['snapshot_manifest_hash'], 'snapshot_kind': bound['snapshot_kind'],
            'snapshot_file_count': bound['snapshot_file_count'], 'identity_scopes': bound['identity_scopes']}


def _bindings(run, operator, candidate_id, ledger, comparisons):
    taskdir = run / 'tasks' / operator
    candidate = ledger.state['tasks'][operator]['candidates'][candidate_id]
    original = (taskdir / 'baseline-source.tar', taskdir / 'baseline', ledger.config['tasks'][operator]['baseline_source_hash'])
    candidate_dir = taskdir / 'candidates' / candidate_id
    changed = (candidate_dir / 'source.tar', candidate_dir / 'source', candidate['source_hash'])
    parent_id = candidate['source_parent']['candidate_id']
    parent_dir = taskdir / 'candidates' / parent_id if parent_id else taskdir
    parent = (parent_dir / 'source.tar', parent_dir / 'source', candidate['source_parent']['source_hash']) if parent_id else original
    locations = {'original': original, 'parent': parent, 'candidate': changed}
    bindings = {}
    for row in comparisons:
        for key, roles in (('build', {'A': row['control'], 'B': 'candidate'}),
                           ('control_build', {'A': row['control'], 'B': row['control']})):
            path = row[key]['path'] if isinstance(row[key], dict) else row[key]
            build = load(path)
            require(build['operator'] == operator and set(build['roles']) == {'A', 'B'}, 'foreign operator or invalid native roles')
            for role, label in roles.items():
                bound = source_binding(*locations[label], build, role)
                require(label not in bindings or bindings[label] == bound, 'comparison roles disagree on semantic source identity')
                bindings[label] = bound
    if 'parent' not in bindings:
        require(candidate['source_parent']['source_hash'] == original[2], 'missing direct parent comparison')
        bindings['parent'] = bindings['original']
    return bindings


def _memory_bindings(run, operator, candidate_id, cases, comparisons):
    taskdir = run / 'tasks' / operator
    result = {}
    for row in comparisons:
        plans = {}
        for key, label_key, needs_swapped in (('build', 'memory_label', False), ('control_build', 'control_memory_label', True)):
            path = row[key]['path'] if isinstance(row[key], dict) else row[key]
            label = wrapper_evidence.safe_token(row[label_key])
            bound = wrapper_evidence.memory_preflight(run, taskdir, label, path, cases, qualification=needs_swapped)
            require(bound['prospective'] is True, 'comparison memory plan must be prospective')
            plans['ab' if key == 'build' else 'aa'] = bound
        result[row['control']] = plans
    return result


def _check_build(path, operator, first, second):
    build = load(path)
    require(build['operator'] == operator and set(build['roles']) == {'A', 'B'}, 'foreign operator or invalid native roles')
    for role, binding in (('A', first), ('B', second)):
        item = build['roles'][role]
        require(Path(item['source_dir']).resolve() == Path(binding['source_dir']), 'native role uses the wrong source directory: ' + role)
        require(campaign.identity(item['source_sha256']) == binding['native_source_hash'], 'native role source hash differs: ' + role)
    return build


def prepare_group(run_dir, operator, candidate_id, purpose, comparison_inputs=None, *, device=0, cpu='8', timeout=21600):
    require(purpose in {'search', 'final'}, 'purpose must be search or final')
    run = Path(run_dir).resolve()
    ledger = campaign.Ledger(run / 'ledger')
    require(operator in ledger.state['tasks'], 'unknown operator')
    task = ledger.state['tasks'][operator]
    require(candidate_id in task['candidates'], 'candidate must already be registered')
    candidate = task['candidates'][candidate_id]
    require(not task['frozen'], 'prepare must precede final freeze; collect the existing frozen group')
    taskdir = run / 'tasks' / operator
    group = taskdir / 'candidates' / candidate_id / 'comparisons' / purpose
    require(not group.exists(), 'existing comparison preparation is immutable evidence')
    original_hash = ledger.config['tasks'][operator]['baseline_source_hash']
    controls = ['original'] if candidate['source_parent']['source_hash'] == original_hash else ['parent', 'original']
    if comparison_inputs is None:
        require(controls == ['original'], 'a distinct direct parent requires explicit parent and original comparison builds')
        rows = [{'control': 'original', 'build': str(taskdir / 'candidates' / candidate_id / 'ab-build/build_manifest.json'),
                 'control_build': str(taskdir / 'aa-build/build_manifest.json'),
                 'qualification_report': str(taskdir / 'qualification/report.json')}]
    else:
        path = Path(comparison_inputs).resolve()
        specification = load(path)
        require(set(specification) == {'comparisons'}, 'comparison inputs requires only a comparisons array')
        rows = deepcopy(specification['comparisons'])
        for row in rows:
            require({'control', 'build', 'control_build', 'qualification_report'} <= set(row) <= {'control', 'build', 'control_build', 'qualification_report', 'memory_label', 'control_memory_label'}, 'each comparison requires explicit build and qualified control build')
            for key in ('build', 'control_build', 'qualification_report'):
                value = Path(row[key])
                row[key] = str((value if value.is_absolute() else path.parent / value).resolve())
    require([r['control'] for r in rows] == controls, 'comparison order/controls must match direct parent and original, merging equal controls')
    for row in rows:
        row.setdefault('memory_label', candidate_id)
        row.setdefault('control_memory_label', 'baseline' if row['control'] == 'original' else candidate['source_parent']['candidate_id'])
    bindings = _bindings(run, operator, candidate_id, ledger, rows)
    for row in rows:
        _check_build(row['build'], operator, bindings[row['control']], bindings['candidate'])
        _check_build(row['control_build'], operator, bindings[row['control']], bindings[row['control']])
    cases = campaign.ALL_CASES if purpose == 'final' else campaign.SENTINELS + [p['case_id'] for p in candidate['probes']]
    memories = _memory_bindings(run, operator, candidate_id, cases, rows)
    require(timeout > 0, 'timeout must be positive')
    producers = wrapper_evidence.producers([__file__, wrapper_evidence.__file__, ROOT / 'scripts/shared_context_memory_plan.py',
        native.__file__, ROOT / 'scripts/shared_context_build.py', ROOT / 'scripts/shared_context_report.py',
        ROOT / 'scripts/cannbench_device_timing.py', ROOT / 'scripts/feedback_hardware.py', ROOT / 'scripts/run_level1_serial.py'])
    group.mkdir(parents=True)
    producer_snapshots = wrapper_evidence.snapshot_producers(group, producers)
    save(group / 'memory-plan-bindings.json', memories)
    save(group / 'source-native-bindings.json', bindings)
    comparisons = []
    for row in rows:
        label = row['control']
        directory = group / label
        args = SimpleNamespace(output=str(directory), build=row['build'], control_build=row['control_build'],
            input_bindings=str(taskdir / 'input-bindings.json'), environment=str(run / 'bootstrap/environment.json'),
            opdir=str(taskdir / 'baseline'), cases=','.join(map(str, cases)), phases='before,reverse,ab,after',
            device=device, cpu=cpu, comparison_id=f'{operator}-{candidate_id}-{purpose}-{label}', attempt_id=candidate_id,
            run_id=ledger.config['campaign_id'], comparison_kind=label, qualification_report=row['qualification_report'])
        native.prepare(args)
        comparisons.append({'control': label, 'control_source_hash': bindings[label]['archive']['sha256'],
            'candidate_source_hash': candidate['source_hash'], 'directory': str(directory),
            'manifest': pointer(directory / 'manifest.json'), 'execution_plan': pointer(directory / 'execution-plan.json'),
            'build': pointer(row['build']), 'control_build': pointer(row['control_build']),
            'qualification_report': pointer(row['qualification_report']),
            'memory_label': row['memory_label'], 'control_memory_label': row['control_memory_label']})
    document = {'schema_version': VERSION, 'run': str(run), 'run_id': ledger.config['campaign_id'],
        'config_hash': ledger.config_hash, 'operator': operator, 'candidate_id': candidate_id, 'purpose': purpose,
        'source_hash': candidate['source_hash'], 'source_parent': candidate['source_parent'], 'case_ids': cases,
        'device': device, 'cpu': cpu, 'timeout': timeout, 'comparisons': comparisons,
        'source_native_bindings': pointer(group / 'source-native-bindings.json'),
        'memory_plan_bindings': pointer(group / 'memory-plan-bindings.json'),
        'producer_version': wrapper_evidence.VERSION, 'producers': producers, 'producer_snapshots': producer_snapshots,
        'formal_sample_scope': 'AB event samples only; AA control event samples are separate actual costs',
        'wrapper_source': pointer(__file__), 'production_gate': 'not_evaluated', 'episode_ref': None}
    save(group / 'group-manifest.json', document)
    plan = campaign.timing_plan(candidate, original_hash, purpose=purpose, manifest_ref=sha(group / 'group-manifest.json'))
    save(group / 'ledger-plan.json', plan)
    return {'group': str(group), 'manifest': str(group / 'group-manifest.json'), 'ledger_plan': plan,
            'ledger_plan_path': str(group / 'ledger-plan.json'), 'hardware_executed': False}


def _preflight(group):
    document, plan = load(group / 'group-manifest.json'), load(group / 'ledger-plan.json')
    require(document['schema_version'] == VERSION, 'unknown comparison group schema')
    ledger = campaign.Ledger(Path(document['run']) / 'ledger')
    require(document['config_hash'] == ledger.config_hash and document['run_id'] == ledger.config['campaign_id'], 'campaign config changed')
    operator, cid = document['operator'], document['candidate_id']
    expected_group = Path(document['run']) / 'tasks' / operator / 'candidates' / cid / 'comparisons' / document['purpose']
    require(group == expected_group.resolve(), 'comparison group moved outside its frozen location')
    task = ledger.state['tasks'][operator]
    candidate = task['candidates'][cid]
    expected = campaign.timing_plan(candidate, ledger.config['tasks'][operator]['baseline_source_hash'],
                                  purpose=document['purpose'], manifest_ref=sha(group / 'group-manifest.json'))
    require(plan == expected and document['case_ids'] == expected['case_ids'], 'ledger plan differs from frozen candidate cases or manifest')
    require(document['source_hash'] == candidate['source_hash'] and document['source_parent'] == candidate['source_parent'], 'candidate/source parent identity changed')
    if document['purpose'] == 'final':
        require(task['frozen'] and cid in task['selection'] and plan == task['final_plans'][cid], 'final collection requires the exact frozen plan')
    else:
        require(not task['frozen'], 'search cannot execute after final freeze')
    verify_pointer(document['wrapper_source'])
    wrapper_evidence.verify_refs(document['producers'])
    for original, snapshot in document['producer_snapshots'].items():
        require(snapshot['sha256'] == document['producers'][original], 'producer snapshot binding changed')
        wrapper_evidence.verify_refs({snapshot['snapshot']: snapshot['sha256']})
    bindings = load(verify_pointer(document['source_native_bindings']))
    require(bindings == _bindings(Path(document['run']), operator, cid, ledger, document['comparisons']), 'source/native binding changed')
    require([{k: r[k] for k in ('control_source_hash', 'candidate_source_hash')} for r in document['comparisons']] == plan['comparisons'],
            'comparison source identities differ from ledger')
    memories = load(verify_pointer(document['memory_plan_bindings']))
    require(memories == _memory_bindings(Path(document['run']), operator, cid, plan['case_ids'], document['comparisons']), 'memory plan binding changed')
    for row in document['comparisons']:
        directory = Path(row['directory'])
        require(directory == group / row['control'], 'comparison output directory changed')
        for key in ('manifest', 'execution_plan', 'build', 'control_build', 'qualification_report'):
            verify_pointer(row[key])
        manifest, execution = load(row['manifest']['path']), load(row['execution_plan']['path'])
        require(manifest['run_id'] == document['run_id'] and manifest['task_id'] == operator and manifest['attempt_id'] == cid,
                'native manifest belongs to a different candidate/run')
        require([c['case_id'] for c in manifest['cases']] == list(map(str, plan['case_ids'])) and manifest['stages'] == ['before', 'reverse', 'ab', 'after'],
                'native schedule differs from declared search/final cases or control phases')
        require(manifest['comparison_kind'] == row['control'], 'comparison control label changed')
        require(execution['build'] == row['build']['path'] and execution['control_build'] == row['control_build']['path'], 'native build path differs')
        _check_build(row['build']['path'], operator, bindings[row['control']], bindings['candidate'])
        _check_build(row['control_build']['path'], operator, bindings[row['control']], bindings[row['control']])
        native.attest_files(manifest, execution)
        require(not (directory / 'collection-started.json').exists() and not (group / (row['control'] + '-execution')).exists(),
                'attempted collection cannot be implicitly retried')
    return document, plan, ledger


def sample_costs(directory, manifest):
    costs = {'ab_event_samples': 0, 'aa_event_samples': 0, 'native_sessions_completed': 0, 'journal_parse_errors': 0}
    for session in manifest['session_plan']:
        journal = directory / session['session_id'] / 'journal.jsonl'
        if not journal.exists():
            continue
        try:
            lines = journal.read_text().splitlines()
        except (OSError, UnicodeError):
            costs['journal_parse_errors'] += 1
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except (ValueError, TypeError):
                costs['journal_parse_errors'] += 1
                continue
            if not isinstance(row, dict):
                costs['journal_parse_errors'] += 1
                continue
            if row.get('type') == 'sample':
                costs['ab_event_samples' if session['phase'] == 'ab' else 'aa_event_samples'] += 1
            if row.get('type') == 'session_end' and row.get('exit_code') == 0:
                costs['native_sessions_completed'] += 1
    return costs


def collect_group(group_dir):
    group = Path(group_dir).resolve()
    with (group / '.collect.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require(not (group / 'group-result.json').exists() and not (group / 'group-started.json').exists(), 'completed/attempted group cannot be retried')
        document, plan, ledger = _preflight(group)
        operator, cid, purpose = document['operator'], document['candidate_id'], document['purpose']
        stage = f'{cid}-timing-{purpose}'
        require(stage not in ledger.state['tasks'][operator]['stages'], 'ledger already records this group; explicit recovery review required')
        # All prerequisite/freeze checks and the budget charge are atomic in ledger.
        ledger.start_stage(event_id=stage + '-start', workload=operator, candidate_id=cid, stage_id=stage, kind='timing', plan=plan)
        started = time.time()
        save(group / 'group-started.json', {'started_at': started, 'stage_id': stage, 'plan_hash': sha(group / 'ledger-plan.json')})
        evaluations, error, interrupted = [], None, None
        totals = {'ab_event_samples': 0, 'aa_event_samples': 0, 'native_sessions_completed': 0, 'journal_parse_errors': 0}
        for row in document['comparisons']:
            directory = Path(row['directory'])
            evaluation = {k: row[k] for k in ('control', 'control_source_hash', 'candidate_source_hash')}
            evaluation.update(stage_id=stage, comparison_id=load(row['manifest']['path'])['comparison_id'], status='not_run', evidence={})
            evaluations.append(evaluation)
            if error is not None:
                evaluation['reason'] = 'A prior comparison execution failed; unexecuted declared comparison remains visible.'
                continue
            try:
                run_process([sys.executable, ROOT / 'scripts/cannbench_shared_context.py', 'collect', '--output', directory],
                    ROOT, group / (row['control'] + '-execution'), device=document['device'], cpu=document['cpu'], timeout=document['timeout'])
                native.verify_directory(directory)
                report = load(directory / 'report.json')
                evaluation.update(status='passed' if report['measurement_quality']['observed_checks_pass'] else 'quality_failed',
                    measurement_quality=report['measurement_quality'], suite=report['phases']['ab']['suite'],
                    cases=report['phases']['ab']['cases'], case_attributes=report['case_attributes'],
                    qualification_scope=load(row['manifest']['path'])['qualification_scope'])
            except BaseException as exc:
                error = {'type': type(exc).__name__, 'message': str(exc)}
                evaluation.update(status='execution_failed', error=error)
                if not isinstance(exc, Exception):
                    interrupted = exc
            finally:
                costs = sample_costs(directory, load(row['manifest']['path']))
                for key, count in costs.items():
                    totals[key] += count
                evaluation['actual_costs'] = costs
                files = [directory / name for name in ('manifest.json', 'execution-plan.json', 'report.json', 'sessions.json', 'collection-completion.json')]
                files.append(group / (row['control'] + '-execution') / 'execution.json')
                evaluation['evidence'] = {str(p): sha(p) for p in files if p.is_file()}
        expected_samples = len(plan['case_ids']) * len(plan['comparisons']) * 6 * 30 * 2
        if error is None and (totals['ab_event_samples'] != expected_samples or totals['journal_parse_errors']):
            error = {'type': 'IncompleteSamples', 'message': 'Raw AB sample count or journal parsing does not match the frozen plan.'}
        status = 'execution_failed' if error else 'quality_failed' if any(e['status'] == 'quality_failed' for e in evaluations) else 'passed'
        totals.update(event_samples=totals['ab_event_samples'] + totals['aa_event_samples'], wall_seconds=max(0, int(time.time() - started)))
        result = {'schema_version': VERSION, 'run_id': document['run_id'], 'operator': operator, 'candidate_id': cid,
            'purpose': purpose, 'stage_id': stage, 'status': status, 'started_at': started, 'ended_at': time.time(),
            'formal_samples': totals['ab_event_samples'], 'actual_costs': totals, 'error': error, 'evaluations': evaluations,
            'producer_version': document['producer_version'], 'producers': document['producers'],
            'memory_plan_bindings': document['memory_plan_bindings'],
            'manifest': pointer(group / 'group-manifest.json'), 'ledger_plan': pointer(group / 'ledger-plan.json'),
            'production_gate': 'not_evaluated', 'episode_ref': None, 'feedback_closed': False,
            'next_action': 'Review the recorded evidence and explicitly record feedback; no lesson or next candidate was generated.'}
        save(group / 'group-result.json', result)
        ledger.finish_stage(event_id=stage + '-finish', workload=operator, stage_id=stage,
            outcome='interrupted' if interrupted else 'failed' if error else 'quality_failed' if status == 'quality_failed' else 'success',
            formal_samples=totals['ab_event_samples'], evidence={str(group / 'group-result.json'): sha(group / 'group-result.json')},
            reason=None if status == 'passed' else json.dumps(error or [e.get('measurement_quality', {}).get('failures', []) for e in evaluations]), actual_costs=totals)
        if interrupted:
            raise interrupted
        return result


def run(run_dir, operator, candidate_id, purpose='search', comparison_inputs=None, **kwargs):
    require(purpose == 'search', 'final requires prepare, explicit ledger freeze, then collect')
    prepared = prepare_group(run_dir, operator, candidate_id, purpose, comparison_inputs, **kwargs)
    return collect_group(prepared['group'])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'run'):
        sub = commands.add_parser(command)
        for flag in ('run', 'operator', 'candidate'):
            sub.add_argument('--' + flag, required=True)
        sub.add_argument('--purpose', choices=('search', 'final'), default='search')
        sub.add_argument('--comparison-inputs')
        sub.add_argument('--device', type=int, default=0)
        sub.add_argument('--cpu', default='8')
        sub.add_argument('--timeout', type=float, default=21600)
    sub = commands.add_parser('collect')
    sub.add_argument('--group', required=True)
    args = parser.parse_args(argv)
    if args.command == 'collect':
        result = collect_group(args.group)
    else:
        function = run if args.command == 'run' else prepare_group
        result = function(args.run, args.operator, args.candidate, args.purpose, args.comparison_inputs,
                          device=args.device, cpu=args.cpu, timeout=args.timeout)
    print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
    return 2 if result.get('status') == 'execution_failed' else 0


if __name__ == '__main__':
    wrapper_evidence.install_termination_handler()
    raise SystemExit(main())
