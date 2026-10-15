"""Preserve the incomplete Task attempt without granting measurement admission."""
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys

from measurement_source_archive import HistoricalEvidence, REPO
from replay_timing_diagnosis import Evidence, read, require


def bound_ref(evidence, path):
    item = evidence.bind(path)
    return {key: item[key] for key in ('path', 'sha256')}


def verify_snapshot(evidence, inventory):
    root = Path(inventory['root']).resolve(strict=True)
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'cancelled attempt contains a symlink')
        if path.is_file():
            actual.add(str(path))
    require(actual == set(inventory['files']) and len(actual) == inventory['file_count'],
            'cancelled attempt files were added or removed')
    total = 0
    by_hash = {}
    for name, item in inventory['files'].items():
        path = Path(name)
        require(path.is_absolute() and path.is_relative_to(root)
                and set(item) == {'sha256', 'bytes'}, 'invalid cancelled attempt file')
        evidence.bind(path, item['sha256'])
        require(path.stat().st_size == item['bytes'], 'cancelled attempt file size changed')
        total += item['bytes']
        by_hash.setdefault(item['sha256'], path)
    require(total == inventory['total_bytes'], 'cancelled attempt byte count differs')
    return root, by_hash


def replay_task_cancellation(reference, *, producer_archive_ref=None):
    evidence = Evidence()
    evidence.bind(reference['path'], reference['sha256'])
    audit = read(reference['path'])
    require(audit.get('schema_version') == 1
            and audit.get('purpose') == 'historical_explicit_cost_projection_cancellation_audit'
            and audit.get('complete') is False and audit.get('eligible_for_publication') is False
            and audit.get('formal_admission_replayed') is False and audit.get('actual_timeout') is False,
            'cancelled Task attempt cannot confer admission')
    full_archive_ref = audit['source_archive_ref']
    evidence.bind(full_archive_ref['path'], full_archive_ref['sha256'])
    full_archive = read(full_archive_ref['path'])
    require(full_archive.get('schema_version') == 1 and full_archive.get('not_a_release') is True
            and isinstance(full_archive.get('files'), dict), 'invalid full cancellation source archive')
    require(producer_archive_ref is not None and set(producer_archive_ref) == {'path', 'sha256'},
            'explicit producer-only source archive is required')
    evidence.bind(producer_archive_ref['path'], producer_archive_ref['sha256'])
    selected = {path: item for path, item in full_archive['files'].items()
                if HistoricalEvidence._producer_path(Path(path))}
    require(read(producer_archive_ref['path']) == {
        'schema_version': 1, 'not_a_release': True,
        'purpose': 'historical_cancelled_task_producers_only',
        'source_archive_ref': full_archive_ref, 'files': selected},
        'producer-only archive differs from the complete frozen source archive')
    original = HistoricalEvidence([producer_archive_ref], logical_paths=True)
    snapshot = audit['actual_inventory_ref']
    evidence.bind(snapshot['path'], snapshot['sha256'])
    root, by_hash = verify_snapshot(evidence, read(snapshot['path']))
    for name, ref in audit['references'].items():
        require(Path(ref['path']) == root / name, 'cancelled attempt reference escaped its root')
        evidence.bind(ref['path'], ref['sha256'])
    plan, freeze, roster = (read(root / (name + '.json')) for name in ('plan', 'freeze', 'roster'))
    for path, expected in freeze['frozen_files'].items():
        original.bind(path, expected)
    require(freeze['plan'] == bound_ref(evidence, root / 'plan.json')
            and roster['freeze'] == bound_ref(evidence, root / 'freeze.json'), 'cancelled freeze chain differs')
    start = read(root / 'campaign/started.json')
    evidence.bind(start['anchor']['path'], start['anchor']['sha256'])
    anchor = read(start['anchor']['path'])
    require(start['anchor'] == audit['root_anchor_ref']
            and anchor['roster'] == bound_ref(evidence, root / 'roster.json')
            and freeze['created_at'] <= roster['created_at']
            <= datetime.fromisoformat(anchor['recorded_at_utc']).timestamp() <= start['at'],
            'cancelled attempt was not anchored before execution')
    cancel = read(root / 'root-cost-projection-cancellation.json')
    require(cancel['purpose'] == 'root_requested_early_campaign_cancellation_cost_projection'
            and cancel['continue_sigmoid'] is False, 'cancellation reason changed')
    require(plan['budgets'] == audit['budgets'] == {'campaign': 12600, 'confirmation': 3600, 'observation': 1200},
            'cancelled attempt budget changed')
    outer = read(root / 'campaign-outer-job/execution.json')
    inner = read(root / 'campaign/exp-confirmation/job/execution.json')
    require(outer['job'] == read(root / 'campaign-job.json') and inner['job'] == roster['slots'][0]['job'],
            'cancelled execution differs from its registered job')
    for execution, budget in ((outer, 12600), (inner, 3600)):
        require(execution['exit_code'] == 143 and execution['status'] == 'failed'
                and execution['error'] == {'type': 'SystemExit', 'message': '143'}
                and 0 < execution['duration_seconds'] < budget
                and datetime.fromisoformat(execution['started_at']).timestamp() <= cancel['recorded_at']
                <= datetime.fromisoformat(execution['finished_at']).timestamp(),
                'explicit early cancellation was relabeled as a timeout')
    require(audit['actual_wall_seconds'] == outer['duration_seconds'] and audit['exit_code'] == 143,
            'cancellation cost summary differs')
    cleanup = read(root / 'post-cancellation-cleanup.json')
    require(cleanup['outer_execution'] == bound_ref(evidence, root / 'campaign-outer-job/execution.json')
            and all(value == 'absent' for value in cleanup['pre_signal_process_states'].values()),
            'cancelled process cleanup was not retained')
    for name in ('campaign/campaign.json', 'campaign/exp-confirmation/terminal.json',
                 'sigmoid/confirmation', 'campaign/sigmoid-confirmation'):
        require(not (root / name).exists(), 'incomplete attempt acquired an invented completion')
    config = read(root / 'exp/config.json')
    raw = read(root / 'exp/confirmation/raw_measurements.json')
    require(raw['complete'] is False and raw['finished_at'] is None and raw['verifier_worker_ref'] is None
            and 'error' not in raw, 'cancelled raw state differs')
    expected = [(cid, cycle) for cid in (1, 2) for cycle in range(6)] + [(3, 0), (3, 1)]
    require([(s['case_id'], s['cycle']) for s in raw['sessions']] == expected, 'cancelled session prefix differs')
    runtime = REPO / 'skill-libs/graph-base/0.5.1/runtime/src'
    # The live pure parser/math must still match the frozen version; no archived
    # collector or archived Python code is executed by this history verifier.
    for relative in ('aprof_runtime/task_timing.py', 'aprof_runtime/measurement_admission.py'):
        path = runtime / relative
        evidence.bind(path, freeze['frozen_files'][str(path)])
    sys.path.insert(0, str(runtime))
    from aprof_runtime.task_timing import partition_task_samples
    from aprof_runtime.measurement_admission import _phase_controls
    require(Path(sys.modules[partition_task_samples.__module__].__file__).resolve() == runtime / 'aprof_runtime/task_timing.py',
            'wrong pure Task parser imported')
    rows = audit['completed_saved_sessions']
    require([(r['case_id'], r['cycle']) for r in rows] == expected, 'audit omitted saved sessions')
    for session, row in zip(raw['sessions'], rows, strict=True):
        messages = [json.loads(line.split(':', 1)[1])
                    for line in Path(row['stdout_ref']['path']).read_text().splitlines()
                    if line.startswith('APROF_SHARED_TIMING_JSON:')]
        for key in ('stdout_ref', 'task_table_ref'):
            evidence.bind(row[key]['path'], row[key]['sha256'])
        result = partition_task_samples(row['task_table_ref']['path'], messages,
            operator=config['operator'], cycle=session['cycle'], repeat=100,
            role_kernel_names=config['task_profile']['role_kernel_names'])
        require(result == read(by_hash[session['partition_ref']])
                and session['partition_ref'] == row['saved_partition_ref']
                and _phase_controls(result['values_ns_per_call']) == session['control_summary'] == row['controls'],
                'saved cancelled partition or controls differ from raw replay')
        require(row['session_seconds'] == session['finished_at'] - session['started_at']
                and row['capture_seconds'] == session['capture']['ended_at'] - session['capture']['started_at'],
                'saved cancellation cycle cost differs')
    partial = root / 'exp/confirmation/case-03-cycle-2'
    actual_partial = {p: v for p, v in read(snapshot['path'])['files'].items() if Path(p).is_relative_to(partial)}
    require(actual_partial == audit['partial_session']['files']
            and not (root / 'exp/confirmation/oracle-worker/receipt-0029.json').exists()
            and audit['partial_session']['committed_to_raw'] is False,
            'partial final cycle acquired a completion')
    return {'valid': True, 'complete': False, 'eligible_for_publication': False,
            'authority': 'historical_cancellation', 'audit': reference, 'snapshot': snapshot,
            'completed_saved_sessions': len(rows), 'partial_cycle': [3, 2],
            'median_session_seconds': statistics.median(row['session_seconds'] for row in rows),
            'actual_wall_seconds': outer['duration_seconds'], 'actual_timeout': False,
            'formal_admission_replayed': False, 'source_archive': full_archive_ref,
            'producer_only_source_archive': producer_archive_ref,
            'resolved_producers': original.resolved_files}
