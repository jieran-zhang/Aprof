"""Read-only leaf audit of the one failed Task-window qualification attempt.

This validates the old source/package bytes and the actual failed roster. It
never substitutes archived raw data for measurement admission and never runs
the historical collector or the earlier long method history.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

from measurement_source_archive import HistoricalEvidence, REPO
from replay_timing_diagnosis import Evidence, read, require

PACKAGE = REPO / 'skill-libs/graph-base/0.5.1'
KIND = 'historical_failed_task_window_v1'
SLOTS = ('exp-confirmation', 'exp-observation-01', 'exp-observation-09',
         'sigmoid-confirmation', 'sigmoid-observation-01', 'sigmoid-observation-04')
STATUSES = ('failed', 'not_run', 'not_run', 'failed', 'not_run', 'not_run')
BUDGETS = {'confirmation': 3600, 'observation': 1200, 'campaign': 12600}


def bound(evidence, reference, path=None):
    require(isinstance(reference, dict) and set(reference) == {'path', 'sha256'}, 'invalid frozen reference')
    if path is not None:
        require(Path(reference['path']) == Path(path), 'frozen reference path differs')
    actual = evidence.bind(reference['path'], reference['sha256'])
    return actual


def timestamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def _exact_attempt_statuses(statuses):
    require(list(statuses) == list(SLOTS)
            and tuple(statuses.values()) == STATUSES,
            'failed attempt has a different slot roster or status')


def _files(evidence, manifest, attempt):
    source_ref = manifest['source_archive_ref']
    payload_ref = manifest['payload_index_ref']
    source, payload = read(bound(evidence, source_ref)['path']), read(bound(evidence, payload_ref)['path'])
    freeze = read(bound(evidence, manifest['freeze_ref'], attempt / 'freeze.json')['path'])
    candidate = read(bound(evidence, manifest['candidate_inventory_ref'], attempt / 'candidate-inventory.json')['path'])
    require(source['schema_version'] == payload['schema_version'] == 1
            and source['not_a_release'] is payload['not_a_release'] is True
            and source['purpose'] == 'historical_failed_task_window_v1_producers'
            and payload['purpose'] == 'historical_failed_task_window_v1_payload'
            and source['freeze_ref'] == manifest['freeze_ref']
            and source['payload_index_ref'] == payload_ref
            and payload['candidate_inventory_ref'] == manifest['candidate_inventory_ref']
            and candidate['root'] == payload['root'] == str(PACKAGE)
            and len(candidate['files']) == len(payload['files']) == 213,
            'old package/source archive identity differs')
    archive_root = Path(payload['archive_root'])
    require(archive_root == Path(payload_ref['path']).parent / 'payload/graph-base/0.5.1'
            and archive_root.is_dir() and not archive_root.is_symlink(),
            'old package archive root differs')
    entries = list(archive_root.rglob('*'))
    require(all(not path.is_symlink() and (path.is_file() or path.is_dir()) for path in entries),
            'old payload contains an unsupported entry')
    actual_files = {p.relative_to(archive_root).as_posix() for p in entries if p.is_file()}
    require(actual_files == set(candidate['files']) == set(payload['files']),
            'old payload has added or removed files')
    for relative, expected in candidate['files'].items():
        item = payload['files'][relative]
        path = archive_root / relative
        require(set(item) == {'original_path', 'path', 'sha256'}
                and item == {'original_path': str(PACKAGE / relative), 'path': str(path), 'sha256': expected}
                and not path.is_symlink(), 'old payload path/identity differs')
        evidence.bind(path, expected)
    expected_producers = {path: digest if digest.startswith('sha256:') else 'sha256:' + digest
                          for path, digest in freeze['frozen_files'].items()
                          if HistoricalEvidence._producer_path(Path(path))}
    require(len(expected_producers) == len(source['files']) == 52
            and set(source['files']) == set(expected_producers), 'old producer archive roster differs')
    historical = HistoricalEvidence([source_ref], logical_paths=True)
    for original, expected in expected_producers.items():
        item = source['files'][original]
        producer_path = Path(item['path'])
        in_payload = Path(original).is_relative_to(PACKAGE)
        expected_path = (Path(payload['files'][Path(original).relative_to(PACKAGE).as_posix()]['path'])
                         if in_payload else Path(source_ref['path']).parent / 'producers' /
                         Path(original).relative_to(REPO))
        require(set(item) == {'path', 'sha256'} and item['sha256'] == expected
                and producer_path == expected_path and not producer_path.is_symlink(),
                'old producer archive entry differs')
        historical.bind(original, expected)
    # Package data is resolved from its complete old payload. Workload, binary,
    # hardware and raw paths must still be checked at their original location.
    for original, digest in freeze['frozen_files'].items():
        expected = digest if digest.startswith('sha256:') else 'sha256:' + digest
        if original in expected_producers:
            continue
        path = Path(original)
        if path.is_relative_to(PACKAGE):
            relative = path.relative_to(PACKAGE).as_posix()
            require(candidate['files'].get(relative) == expected, 'old payload/freeze conflict')
            evidence.bind(payload['files'][relative]['path'], expected)
        else:
            evidence.bind(path, expected)
    return freeze, candidate


def _partial(evidence, manifest):
    index = read(bound(evidence, manifest['partial_scratch_ref'])['path'])
    require(index['schema_version'] == 1
            and index['purpose'] == 'preserve_actual_partial_task_window_v1_scratch'
            and index['eligible_for_publication'] is False
            and set(index['roots']) == {'exp', 'sigmoid'}, 'partial scratch index differs')
    counts = {}
    for op, row in index['roots'].items():
        root = Path(row['archive_root'])
        require(row['source_root'] == f'/tmp/aprof-task-production-task-window-confirmation-v1-{op}'
                and root == Path(manifest['partial_scratch_ref']['path']).parent / 'partial-scratch' / op
                and root.is_dir() and not root.is_symlink(), 'partial scratch identity differs')
        entries = list(root.rglob('*'))
        require(all(not path.is_symlink() and (path.is_file() or path.is_dir()) for path in entries),
                'partial scratch contains an unsupported entry')
        actual_files = {p.relative_to(root).as_posix() for p in entries if p.is_file()}
        actual_dirs = {p.relative_to(root).as_posix() for p in entries if p.is_dir()}
        require(actual_files == set(row['files'])
                and actual_dirs == {item['relative_path'] for item in row['directories']}
                and row['file_count'] == len(actual_files), 'partial scratch roster differs')
        size = 0
        for relative, item in row['files'].items():
            path = root / relative
            require(item['source_path'] == str(Path(row['source_root']) / relative)
                    and item['archive_path'] == str(path) and not path.is_symlink()
                    and path.stat().st_size == item['source_identity']['size_bytes'],
                    'partial scratch file identity differs')
            evidence.bind(path, item['sha256'])
            size += path.stat().st_size
        require(size == row['total_regular_file_bytes'], 'partial scratch bytes differ')
        counts[op] = {'files': len(actual_files), 'bytes': size}
    require(counts == {'exp': {'files': 18, 'bytes': 8111},
                       'sigmoid': {'files': 92, 'bytes': 141469920}},
            'partial scratch actual scope differs')
    return counts


def _core(evidence, manifest, attempt):
    index = read(bound(evidence, manifest['core_receipts_ref'])['path'])
    require(index['schema_version'] == 1
            and index['purpose'] == 'retain_actual_failed_task_window_v1_core_receipts'
            and index['eligible_for_publication'] is False and len(index['files']) == 8,
            'failed core receipt index differs')
    for op in ('exp', 'sigmoid'):
        for name in ('evidence.sqlite', 'confirmation/raw_measurements.json',
                     'confirmation/calibration.json', 'confirmation/registration.json'):
            original = attempt / op / name
            item = index['files'].get(str(original))
            saved = Path(manifest['core_receipts_ref']['path']).parent / 'failure-receipts' / op / name
            require(item and item['archive_path'] == str(saved)
                    and item['bytes'] == original.stat().st_size == saved.stat().st_size,
                    'failed core receipt scope differs')
            # Raw and CAS are never resolved through a source archive.
            evidence.bind(original, item['sha256'])
            evidence.bind(saved, item['sha256'])


def _campaign(evidence, manifest, attempt, freeze):
    terminal_index = read(bound(evidence, manifest['terminal_index_ref'])['path'])
    for key in ('plan_ref', 'roster_ref', 'root_anchor_ref', 'campaign_started_ref', 'campaign_ref'):
        require(terminal_index[key] == manifest[key], 'failure leaf reference chain differs')
    plan = read(bound(evidence, terminal_index['plan_ref'], attempt / 'plan.json')['path'])
    roster = read(bound(evidence, terminal_index['roster_ref'], attempt / 'roster.json')['path'])
    started = read(bound(evidence, terminal_index['campaign_started_ref'], attempt / 'campaign/started.json')['path'])
    campaign = read(bound(evidence, terminal_index['campaign_ref'], attempt / 'campaign/campaign.json')['path'])
    anchor = read(bound(evidence, terminal_index['root_anchor_ref'])['path'])
    require(terminal_index['freeze_ref'] == manifest['freeze_ref']
            and terminal_index['candidate_inventory_ref'] == manifest['candidate_inventory_ref']
            and terminal_index['source_archive_ref'] == manifest['source_archive_ref']
            and terminal_index['payload_index_ref'] == manifest['payload_index_ref']
            and freeze['plan'] == terminal_index['plan_ref']
            and freeze['candidate_inventory'] == manifest['candidate_inventory_ref']
            and roster['freeze'] == manifest['freeze_ref']
            and plan['protocol'] == 'shared_buffer_msprof_task_window_v1'
            and plan['purpose'] == roster['purpose'] == 'preregistered_task_window_native_method_qualification'
            and plan['budgets'] == BUDGETS and roster['timeout_seconds'] == BUDGETS['campaign']
            and plan['max_attempts'] == roster['max_attempts'] == 1
            and plan['resampling'] == roster['resampling'] == campaign['resampling'] == 'none'
            and plan['publication_acceptance'] is False
            and started['roster'] == campaign['roster'] == terminal_index['roster_ref']
            and started['anchor'] == terminal_index['root_anchor_ref']
            and anchor['roster'] == terminal_index['roster_ref']
            and anchor['max_attempts'] == 1 and anchor['resampling'] == 'none'
            and freeze['created_at'] <= roster['created_at'] <= timestamp(anchor['recorded_at_utc']) <= started['at'],
            'failed qualification freeze/anchor chain differs')
    outer_job = read(bound(evidence, manifest['outer_job_ref'], attempt / 'campaign-job.json')['path'])
    outer = read(bound(evidence, manifest['outer_execution_ref'], attempt / 'campaign-execution/execution.json')['path'])
    require(outer['job'] == outer_job and outer_job['timeout_seconds'] == BUDGETS['campaign']
            and outer_job['argv'] == [plan['interpreter']['path'],
                                      str(REPO / 'scaffolding/collection/scripts/qualify_task_window_timing_v051.py'),
                                      'run', '--roster', str(attempt / 'roster.json'), '--anchor',
                                      terminal_index['root_anchor_ref']['path']]
            and outer['status'] == 'passed' and outer['exit_code'] == 0
            and 0 < outer['duration_seconds'] <= BUDGETS['campaign']
            and timestamp(outer['started_at']) <= started['at'] <= timestamp(outer['finished_at'])
            and outer['physical_device'] is None,
            'outer failed-campaign job differs')
    for key in ('stdout', 'stderr'):
        bound(evidence, outer[key])
    require(Path(outer['stderr']['path']).stat().st_size == 0, 'outer stderr changed')
    require([slot['slot_id'] for slot in roster['slots']] == list(SLOTS)
            and set(campaign['slots']) == set(terminal_index['slots']) == set(SLOTS)
            and campaign['accepted'] is False
            and campaign['authority'] == 'method_qualification_only_no_publication',
            'failed six-slot roster/aggregate differs')
    _exact_attempt_statuses({name: terminal_index['slots'][name]['status'] for name in SLOTS})
    campaign_root = attempt / 'campaign'
    expected_files = {'started.json', 'campaign.json'}
    for name, status in zip(SLOTS, STATUSES, strict=True):
        expected_files.add(f'{name}/terminal.json')
        if status == 'failed':
            expected_files.update({f'{name}/started.json', f'{name}/job/execution.json',
                                   f'{name}/job/stdout.log', f'{name}/job/stderr.log'})
    entries = list(campaign_root.rglob('*'))
    require(all(not path.is_symlink() and (path.is_file() or path.is_dir()) for path in entries)
            and {path.relative_to(campaign_root).as_posix() for path in entries if path.is_file()}
            == expected_files, 'failed campaign contains an extra or missing attempt file')
    previous = started['at']; statuses = {}
    for spec, expected in zip(roster['slots'], STATUSES, strict=True):
        name = spec['slot_id']; folder = attempt / 'campaign' / name
        row = terminal_index['slots'][name]
        terminal = read(bound(evidence, row['terminal'], folder / 'terminal.json')['path'])
        require(campaign['slots'][name] == row['terminal']
                and terminal['slot_id'] == name and terminal['status'] == row['status'] == expected
                and terminal['kind'] == spec['kind'] and terminal['operator'] == spec['operator']
                and previous <= terminal['finished_at'] <= timestamp(outer['finished_at']),
                'failed terminal identity/chronology differs')
        if expected == 'failed':
            begun = read(bound(evidence, terminal['started'], folder / 'started.json')['path'])
            execution = read(bound(evidence, terminal['execution'], folder / 'job/execution.json')['path'])
            require(spec['kind'] == 'confirmation' and spec['prerequisite_slot'] is None
                    and begun['slot'] == spec and previous <= begun['at'] <= terminal['finished_at']
                    and execution['job'] == spec['job']
                    and execution['status'] == 'timeout' and execution['exit_code'] == 143
                    and execution['job']['timeout_seconds'] == BUDGETS['confirmation']
                    and BUDGETS['confirmation'] <= execution['duration_seconds'] < BUDGETS['confirmation'] + 5
                    and terminal['error'] == {'type': 'ValueError', 'message': 'qualification slot failed'}
                    and row['started'] == terminal['started'] and row['execution'] == terminal['execution']
                    and row['stdout'] == execution['stdout'] and row['stderr'] == execution['stderr']
                    and 'replay_execution' not in terminal and 'replay' not in terminal,
                    'actual timeout was relabeled or replayed as passed')
            for key in ('stdout', 'stderr'):
                bound(evidence, execution[key])
            require(begun['at'] <= timestamp(execution['started_at'])
                    <= timestamp(execution['finished_at']) <= terminal['finished_at'],
                    'timeout execution outside failed slot')
        else:
            prior = spec['prerequisite_slot']
            require(spec['kind'] == 'observation' and prior in statuses and statuses[prior] != 'passed'
                    and terminal['prerequisite_ref'] == row['prerequisite_ref']
                    == terminal_index['slots'][prior]['terminal']
                    and not (folder / 'started.json').exists()
                    and not (folder / 'job/execution.json').exists()
                    and 'execution' not in terminal and 'started' not in terminal,
                    'not-run observation acquired an attempt')
        previous = terminal['finished_at']; statuses[name] = expected
    stdout_lines = [json.loads(line) for line in Path(outer['stdout']['path']).read_text().splitlines()]
    require(previous - started['at'] <= BUDGETS['campaign']
            and stdout_lines == [{'slot': name, 'status': statuses[name]} for name in SLOTS] + [campaign],
            'failed campaign duration/stdout differs')
    return statuses


def replay_task_window_failure(reference):
    """Verify this historical failed attempt without new measurement authority."""
    evidence = Evidence()
    manifest = read(bound(evidence, reference)['path'])
    require(manifest['schema_version'] == 1 and manifest['purpose'] == KIND
            and manifest['accepted'] is False and manifest['eligible_for_publication'] is False
            and manifest['complete_method_qualification'] is False,
            'failure leaf cannot grant acceptance')
    bound(evidence, manifest['leaf_source_ref'], Path(__file__))
    attempt = Path(manifest['attempt_dir'])
    require(attempt.name == 'production-task-window-confirmation-v1'
            and attempt.is_dir(), 'failure leaf attempt path differs')
    freeze, _ = _files(evidence, manifest, attempt)
    statuses = _campaign(evidence, manifest, attempt, freeze)
    _core(evidence, manifest, attempt)
    partial = _partial(evidence, manifest)
    saved = read(bound(evidence, manifest['old_replay_result_ref'])['path'])
    job = read(bound(evidence, manifest['old_replay_job_ref'])['path'])
    execution = read(bound(evidence, manifest['old_replay_execution_ref'])['path'])
    bound(evidence, manifest['old_replay_script_ref'])
    require(saved['complete'] is True and saved['accepted'] is False
            and saved['protocol'] == 'shared_buffer_msprof_task_window_v1'
            and saved['authority'] == 'method_qualification_only_no_publication'
            and {name: row['status'] for name, row in saved['slots'].items()} == statuses
            and execution['job'] == job and execution['exit_code'] == 0
            and execution['status'] == 'passed' and execution['duration_seconds'] <= job['timeout_seconds']
            and job['argv'][1] == manifest['old_replay_script_ref']['path'],
            'saved old-code roster replay differs')
    for key in ('stdout', 'stderr'):
        bound(evidence, execution[key])
    return {'valid': True, 'authority': KIND, 'accepted': False,
            'eligible_for_publication': False, 'complete_method_qualification': False,
            'measurement_admission_replayed': False, 'slot_statuses': statuses,
            'partial_scratch': partial, 'source_archive': manifest['source_archive_ref'],
            'payload_archive': manifest['payload_index_ref']}
