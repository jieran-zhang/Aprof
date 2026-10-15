"""Read-only Task v2-local cancellation history; never a campaign admission."""
import argparse
import contextlib
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import stat
import sys
import time

from measurement_source_archive import HistoricalEvidence, REPO
from replay_task_cancellation import bound_ref, verify_snapshot
from replay_timing_diagnosis import Evidence, read, require

REASON = 'root_cost_cancellation_during_uncached_readonly_admission_replay'
BUDGETS = {'campaign': 12600, 'confirmation': 3600, 'observation': 1200}
RUNTIME = REPO / 'skill-libs/graph-base/0.5.1/runtime/src'


def snapshot_view(inventory):
    """Adapt the saved v2 file schema without rewriting its original bytes."""
    root = Path(inventory['root']).resolve(strict=True)
    files = {}
    for name, item in inventory['files'].items():
        relative = Path(name)
        require(not relative.is_absolute() and '..' not in relative.parts
                and str(relative) == name and name != '.', 'invalid snapshot relative path')
        require(set(item) == {'sha256', 'size_bytes', 'mode'}, 'snapshot contains nonregular file')
        path = root / relative
        require(stat.S_IMODE(path.stat().st_mode) == item['mode'], 'snapshot file mode changed')
        files[str(path)] = {'sha256': item['sha256'], 'bytes': item['size_bytes']}
    return {'root': str(root), 'files': files, 'file_count': inventory['file_count'],
            'total_bytes': inventory['total_regular_file_bytes']}


def producer_index(full_reference, full):
    require(full.get('schema_version') == 1 and full.get('not_a_release') is True,
            'invalid full source archive')
    return {'schema_version': 1, 'not_a_release': True,
            'purpose': 'historical_cancelled_task_v2_local_producers_only',
            'source_archive_ref': full_reference,
            'files': {path: item for path, item in full['files'].items()
                      if HistoricalEvidence._producer_path(Path(path))}}


def validate_audit(audit):
    require(audit.get('schema_version') == 1 and audit.get('purpose') == 'preserve_actual_evidence_not_admission'
            and audit.get('complete') is False and audit.get('eligible_for_publication') is False
            and audit.get('not_actual_timeout') is True and audit.get('full_admission_replay_performed') is False
            and audit.get('cancellation_reason') == REASON, 'cancellation audit cannot confer admission')


def controls_pass(controls):
    return all(0 <= controls[phase][key] <= limit
               for phase in ('aa_before', 'formal', 'aa_after')
               for key, limit in (('baseline_cv', .05), ('candidate_cv', .05), ('role_bias', .02))) \
        and set(controls['drift']) == {'baseline', 'candidate'} \
        and all(0 <= value <= .02 for value in controls['drift'].values())


def timestamp(value):
    return datetime.fromisoformat(value).timestamp()


def check_cancel(cancel, outer, sigmoid):
    require(cancel['reason'] == REASON and cancel['max_attempts'] == 1 and cancel['resampling'] == 'none'
            and cancel['eligible_for_publication'] is False and cancel['exp_failed_before_cancellation'] is True,
            'explicit root cancellation reason changed')
    require(outer['exit_code'] == 143 and outer['status'] == 'failed'
            and outer['error'] == {'type': 'SystemExit', 'message': '143'}
            and 0 < outer['duration_seconds'] < BUDGETS['campaign']
            and timestamp(outer['started_at']) <= timestamp(sigmoid['finished_at'])
            <= cancel['recorded_at'] <= timestamp(outer['finished_at']),
            'cost cancellation is not a timeout or collector failure')
    require(sigmoid['status'] == 'passed' and sigmoid['exit_code'] == 0
            and cancel['sigmoid_collector_exit_code'] == 0 and cancel['sigmoid_raw_complete'] is True
            and cancel['sigmoid_collector_duration_seconds'] == sigmoid['duration_seconds']
            and abs(cancel['recorded_at'] - timestamp(sigmoid['finished_at'])
                    - cancel['replay_elapsed_seconds']) < .001,
            'completed collector and unfinished parent replay were conflated')


def verify_missing_stages(root, roster, evidence):
    campaign = root / 'campaign'
    expected_ids = ['exp-confirmation', 'exp-observation-01', 'exp-observation-09',
                    'sigmoid-confirmation', 'sigmoid-observation-01', 'sigmoid-observation-04']
    require([slot['slot_id'] for slot in roster['slots']] == expected_ids,
            'registered six-slot scope changed')
    exp = read(campaign / 'exp-confirmation/terminal.json')
    require(exp['status'] == 'failed' and exp['execution'] == bound_ref(evidence, campaign / 'exp-confirmation/job/execution.json')
            and exp['started'] == bound_ref(evidence, campaign / 'exp-confirmation/started.json'),
            'failed exp parent terminal changed')
    previous = 'exp-confirmation'
    for name in expected_ids[1:3]:
        terminal = read(campaign / name / 'terminal.json')
        require(terminal['status'] == 'not_run' and terminal['slot_id'] == name
                and terminal['prerequisite_ref'] == bound_ref(evidence, campaign / previous / 'terminal.json')
                and not (campaign / name / 'started.json').exists()
                and not (campaign / name / 'job').exists(), 'exp observation acquired an invented execution')
        previous = name
    absent = ['campaign/campaign.json', 'campaign/sigmoid-confirmation/terminal.json',
              'campaign/sigmoid-confirmation/replay.json', 'campaign/exp-confirmation/replay.json',
              'campaign/sigmoid-observation-01', 'campaign/sigmoid-observation-04', 'observations']
    require(all(not (root / name).exists() for name in absent), 'cancelled campaign acquired an invented completion')
    return absent


def _runtime(freeze, evidence):
    # Only source identity is resolved through an archive. Execute the current
    # pure parser/math, whose bytes must still match this attempt exactly.
    for relative in ('aprof_runtime/task_timing.py', 'aprof_runtime/measurement_admission.py'):
        path = RUNTIME / relative
        evidence.bind(path, freeze['frozen_files'][str(path)])
    sys.path.insert(0, str(RUNTIME))
    from aprof_runtime import task_timing, measurement_admission, task_measurement_admission, store
    for module in (task_timing, measurement_admission, task_measurement_admission, store):
        require(Path(module.__file__).resolve().parent == RUNTIME / 'aprof_runtime', 'wrong runtime imported')
    return task_timing, measurement_admission, task_measurement_admission, store


def replay_exp(reader, raw, config, evidence, parser, math):
    require(raw['complete'] is False and raw.get('error') == {'type': 'ValueError', 'message': 'case 1 cycle 3: Task control failed'}
            and [(s['case_id'], s['cycle']) for s in raw['sessions']] == [(1, cycle) for cycle in range(4)],
            'exp failure prefix changed')
    rows = []
    for session in raw['sessions']:
        stdout = Path(session['cycle_dir']) / 'capture.stdout.log'
        evidence.bind(stdout, session['capture']['stdout_hash'])
        require(stdout.read_bytes() == reader.verify_artifact(session['capture']['stdout_hash']).read_bytes(),
                'actual capture stdout differs from CAS')
        messages = [json.loads(line.split(':', 1)[1]) for line in stdout.read_text().splitlines()
                    if line.startswith('APROF_SHARED_TIMING_JSON:')]
        require(messages == read(reader.verify_artifact(session['native_messages_ref'])),
                'native messages differ from actual stdout')
        partition = parser.partition_task_samples(reader.verify_artifact(session['task_table_ref']), messages,
            operator='exp', cycle=session['cycle'], repeat=100,
            role_kernel_names=config['task_profile']['role_kernel_names'])
        controls = math._phase_controls(partition['values_ns_per_call'])
        require(partition == read(reader.verify_artifact(session['partition_ref']))
                and controls == session['control_summary'], 'exp raw partition or controls differ')
        rows.append({'case_id': 1, 'cycle': session['cycle'], 'controls': controls,
                     'controls_passed': controls_pass(controls), 'partition_ref': session['partition_ref'],
                     'task_table_ref': session['task_table_ref'], 'stdout_ref': session['capture']['stdout_hash'],
                     'session_seconds': session['finished_at'] - session['started_at']})
    require([r['controls_passed'] for r in rows] == [True, True, True, False], 'exp first control failure changed')
    return {'raw_partition_replayed': True, 'full_admission_replayed': False, 'sessions': rows}


def replay_task_local_cancellation(reference, *, producer_archive_ref):
    evidence = Evidence(); evidence.bind(reference['path'], reference['sha256'])
    audit = read(reference['path']); validate_audit(audit)
    for key, value in audit.items():
        if key.endswith('_ref'):
            evidence.bind(value['path'], value['sha256'])
    archive_ref = audit['source_archive_ref']; full = read(archive_ref['path'])
    evidence.bind(producer_archive_ref['path'], producer_archive_ref['sha256'])
    require(read(producer_archive_ref['path']) == producer_index(archive_ref, full),
            'producer-only archive differs from frozen full archive')
    original = HistoricalEvidence([producer_archive_ref], logical_paths=True)
    for item in full['files'].values():
        evidence.bind(item['path'], item['sha256'])
    snapshot_ref = audit['snapshot_inventory_ref']; snapshot = read(snapshot_ref['path'])
    snapshot_clock = time.monotonic()
    root, _ = verify_snapshot(evidence, snapshot_view(snapshot))
    snapshot_seconds = time.monotonic() - snapshot_clock
    require(audit['snapshot_file_count'] == snapshot['file_count']
            and audit['snapshot_total_bytes'] == snapshot['total_regular_file_bytes'], 'snapshot summary differs')
    plan, freeze, roster = (read(root / (name + '.json')) for name in ('plan', 'freeze', 'roster'))
    for name in ('plan', 'freeze', 'roster'):
        require(audit[name + '_ref'] == bound_ref(evidence, root / (name + '.json')), 'audit root reference differs')
    require(freeze['plan'] == audit['plan_ref'] == full['plan_ref']
            and roster['freeze'] == audit['freeze_ref'] == full['freeze_ref']
            and freeze['candidate_inventory'] == full['candidate_inventory_ref'], 'frozen archive chain differs')
    candidate = read(freeze['candidate_inventory']['path'])
    evidence.bind(freeze['candidate_inventory']['path'], freeze['candidate_inventory']['sha256'])
    for relative, digest in candidate['files'].items():
        archived = full['files'][str(Path(candidate['root']) / relative)]
        require(archived['sha256'] == 'sha256:' + digest.removeprefix('sha256:'), 'archived candidate payload differs')
    for path, digest in freeze['frozen_files'].items():
        original.bind(path, digest)
    start = read(root / 'campaign/started.json')
    evidence.bind(start['anchor']['path'], start['anchor']['sha256']); anchor = read(start['anchor']['path'])
    require(start['roster'] == anchor['roster'] == bound_ref(evidence, root / 'roster.json')
            and anchor['schema_version'] == roster['schema_version'] == 1
            and anchor['purpose'] == roster['purpose'] == plan['purpose']
            and anchor['max_attempts'] == roster['max_attempts'] == plan['max_attempts'] == 1
            and anchor['resampling'] == roster['resampling'] == plan['resampling'] == 'none'
            and plan['created_at'] <= freeze['created_at'] <= roster['created_at']
            <= timestamp(anchor['recorded_at_utc']) <= start['at'], 'pre-execution root anchor differs')
    require(plan['budgets'] == BUDGETS and plan['protocol'] == 'shared_buffer_msprof_task_v2', 'frozen scope/budget changed')
    absent = verify_missing_stages(root, roster, evidence)
    outer = read(root / 'campaign-outer-job/execution.json'); cancel = read(audit['cancellation_ref']['path'])
    require(outer['job'] == read(root / 'campaign-job.json') and outer['job']['timeout_seconds'] == BUDGETS['campaign'],
            'outer job differs')
    executions = {}
    for operator, slot in zip(('exp', 'sigmoid'), (roster['slots'][0], roster['slots'][3]), strict=True):
        folder = root / 'campaign' / slot['slot_id']; began = read(folder / 'started.json')
        execution = read(folder / 'job/execution.json'); executions[operator] = execution
        require(began['slot'] == slot and execution['job'] == slot['job']
                and execution['job']['timeout_seconds'] == BUDGETS['confirmation']
                and start['at'] <= began['at'] <= timestamp(execution['started_at'])
                <= timestamp(execution['finished_at']) <= cancel['recorded_at']
                and 0 < execution['duration_seconds'] < BUDGETS['confirmation'], 'collector execution scope/time differs')
        require(audit['operators'][operator]['collector_execution_ref'] == bound_ref(evidence, folder / 'job/execution.json')
                and audit['operators'][operator]['collector_execution'] == {key: execution[key] for key in
                    ('started_at', 'finished_at', 'duration_seconds', 'exit_code', 'status')}, 'saved collector cost differs')
        for key in ('stdout', 'stderr'):
            evidence.bind(execution[key]['path'], execution[key]['sha256'])
    require(executions['exp']['exit_code'] == 1 and executions['exp']['status'] == 'failed', 'exp failure changed')
    check_cancel(cancel, outer, executions['sigmoid'])
    cleanup = read(audit['cleanup_ref']['path'])
    require(cleanup['outer_execution'] == outer and cleanup['npu_idle'] is True
            and set(cleanup['owned_pids_absent']) == {cancel[key] for key in ('outer_pid', 'qualifier_pid', 'supervisor_pid')}
            and cleanup['checked_at'] >= timestamp(outer['finished_at']), 'actual cleanup evidence differs')
    evidence.bind(cleanup['log']['path'], 'sha256:' + cleanup['log']['sha256'].removeprefix('sha256:'))
    parser, math, admission, store = _runtime(freeze, evidence)
    results = {}
    for operator in ('exp', 'sigmoid'):
        config = read(root / operator / 'config.json'); folder = root / operator / 'confirmation'
        receipt = read(folder / 'measurement_admission.json'); refs = read(folder / 'artifacts.json')
        require(config['expected_case_ids'] == list(range(1, 21))
                and receipt['source_hashes']['baseline'] == receipt['source_hashes']['candidate'], 'full same-source scope differs')
        path = root / operator / 'evidence.sqlite'
        with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
            connection.execute('BEGIN')
            reader = store._ReadOnlyArtifacts(connection, store.default_object_directory(path))
            require(read(reader.verify_artifact(refs['measurement_admission'])) == receipt, 'collector receipt CAS differs')
            raw = read(reader.verify_artifact(receipt['raw_ref']))
            require(raw == read(folder / 'raw_measurements.json'), 'actual raw differs from CAS')
            saved = audit['operators'][operator]
            require(saved['raw_complete'] == raw['complete'] and saved['session_count'] == len(raw['sessions'])
                    and saved['case_cycle_pairs'] == [[s['case_id'], s['cycle']] for s in raw['sessions']]
                    and saved['collector_receipt_ref'] == bound_ref(evidence, folder / 'measurement_admission.json')
                    and saved['raw_ref']['sha256'] == receipt['raw_ref'], 'saved operator prefix differs from actual raw')
            if operator == 'exp':
                results[operator] = replay_exp(reader, raw, config, evidence, parser, math)
            else:
                began = time.monotonic()
                try:
                    result = admission.replay_historical_task_measurement_admission(reader,
                        refs['measurement_admission'], expected={**{key: config[key] for key in
                        ('operator', 'run_id', 'session_id', 'candidate_id')}, 'source_hashes': receipt['source_hashes']},
                        producer_resolver=original.resolve_producer)
                    require(result['eligible_for_publication'] is False and result['replay']['valid'] is True
                            and 'gate_projection' not in result['replay']
                            and 'gate_projection' not in result['replay']['report'], 'history acquired admission authority')
                    require(all(controls_pass(c) for case in result['replay']['report']['controls']
                                for c in [case['overall'], *case['cycles']]), 'same-source sigmoid controls failed')
                    results[operator] = result
                except Exception as error:
                    results[operator] = {'authority': 'historical_task_measurement',
                        'eligible_for_publication': False, 'valid': False,
                        'error': {'type': type(error).__name__, 'message': str(error)}}
                results[operator]['historical_replay_seconds'] = time.monotonic() - began
            results[operator]['cas_verified_unique_objects'] = len(reader.verified)
            results[operator]['cas_verified_unique_bytes'] = sum(value[3] for value in reader.verified.values())
    return {'valid': 'error' not in results['sigmoid'], 'authority': 'historical_task_local_cancellation', 'complete': False,
            'eligible_for_publication': False, 'actual_timeout': False, 'reason': REASON,
            'audit': reference, 'snapshot': snapshot_ref, 'source_archive': archive_ref,
            'snapshot_seconds': snapshot_seconds, 'snapshot_file_count': snapshot['file_count'],
            'snapshot_bytes': snapshot['total_regular_file_bytes'],
            'producer_only_source_archive': producer_archive_ref, 'root_anchor': start['anchor'],
            'outer_wall_seconds': outer['duration_seconds'], 'parent_replay_before_cancel_seconds': cancel['replay_elapsed_seconds'],
            'collector_costs': {op: {k: e[k] for k in ('started_at', 'finished_at', 'duration_seconds', 'exit_code')}
                                for op, e in executions.items()},
            'absent_stages': absent, 'operators': results, 'resolved_producers': original.resolved_files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); args.output.mkdir(exist_ok=False)
    sys.dont_write_bytecode = True
    started, clock = time.time(), time.monotonic()
    (args.output / 'started.json').write_text(json.dumps({'started_at': started, 'audit_path': str(args.audit.resolve())}) + '\n')
    try:
        evidence = Evidence(); audit_ref = bound_ref(evidence, args.audit); audit = read(args.audit)
        archive = audit['source_archive_ref']; evidence.bind(archive['path'], archive['sha256'])
        path = args.output / 'producer-only-index.json'
        path.write_text(json.dumps(producer_index(archive, read(archive['path'])), indent=2, sort_keys=True) + '\n')
        result = replay_task_local_cancellation(audit_ref, producer_archive_ref=bound_ref(evidence, path))
    except Exception as error:
        result = {'valid': False, 'complete': False, 'eligible_for_publication': False,
                  'authority': 'historical_task_local_cancellation',
                  'error': {'type': type(error).__name__, 'message': str(error)}}
    result.update(started_at=started, finished_at=time.time(), duration_seconds=time.monotonic() - clock)
    (args.output / 'replay.json').write_text(json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + '\n')
    print(json.dumps({'valid': result['valid'], 'complete': False, 'eligible_for_publication': False}))
    if not result['valid']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
