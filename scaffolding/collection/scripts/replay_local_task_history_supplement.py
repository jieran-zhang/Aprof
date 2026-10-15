"""Recursively replay rejected Task-method history; never publication admission."""
import csv
from datetime import datetime
import json
import math
from pathlib import Path
import statistics

from measurement_source_archive import HistoricalEvidence
from replay_task_cancellation import bound_ref, verify_snapshot
from replay_task_local_cancellation import replay_task_local_cancellation
from replay_task_measurement_history import replay_task_history
from replay_timing_diagnosis import Evidence, read, require


def _load(evidence, reference):
    evidence.bind(reference['path'], reference['sha256'])
    return read(reference['path'])


def replay_prewarm_facility_failure(reference, evidence):
    """Keep the failed cycle check and both persistent/raw scratch inventories."""
    audit = _load(evidence, reference)
    require(audit['purpose'] == 'exp_prewarm_v1_cycle_validation_facility_failure'
            and audit['complete'] is False and audit['eligible_for_publication'] is False
            and audit['completed_slots'] == ['cycle-0-A', 'cycle-0-B']
            and audit['failed_slot'] == 'cycle-1-B' and audit['unexecuted_slots'] == 9,
            'prewarm facility failure was relabeled')
    root, _ = verify_snapshot(evidence, _load(evidence, audit['actual_inventory']))
    retained = _load(evidence, audit['scratch_preservation'])
    scratch = Path(retained['retained_root'])
    entries = {}
    for name, item in retained['files'].items():
        path = Path(name)
        require(not path.is_absolute() and '..' not in path.parts, 'scratch path escaped retained root')
        entries[str(scratch / path)] = item
    verify_snapshot(evidence, {'root': str(scratch), 'files': entries,
        'file_count': retained['file_count'], 'total_bytes': sum(v['bytes'] for v in entries.values())})
    original = HistoricalEvidence([audit['producer_archive']], logical_paths=True)
    frozen = read(root / 'freeze.json')
    for path, expected in frozen['frozen_files'].items():
        original.bind(path, expected)
    began = read(root / 'campaign/started.json'); anchor = _load(evidence, began['anchor'])
    require(began['freeze'] == anchor['freeze'] == bound_ref(evidence, root / 'freeze.json')
            and frozen['created_at'] <= datetime.fromisoformat(anchor['recorded_at_utc']).timestamp() <= began['at'],
            'failed facility lacks its prior frozen root anchor')
    terminal = _load(evidence, audit['terminal']); failed = _load(evidence, terminal['failed_slot'])
    require(terminal['status'] == failed['status'] == 'failed'
            and terminal['accepted'] is False and terminal['publication_acceptance'] is False
            and terminal['error'] == failed['error'] == {
                'type': 'ContractError', 'message': 'measurement admission: READY cycle_index differs'}
            and failed['cycle'] == 1 and failed['arm'] == 'B' and failed['verifications'] == {},
            'facility failure reason or partial stage changed')
    for slot, ref in zip(audit['completed_slots'], terminal['slots'], strict=True):
        require(ref == bound_ref(evidence, root / 'campaign' / slot / 'result.json')
                and _load(evidence, ref)['status'] == 'complete_diagnostic_only', 'completed prefix changed')
    present = {p.name for p in (root / 'campaign').iterdir() if p.is_dir() and p.name.startswith('cycle-')}
    require(present == {'cycle-0-A', 'cycle-0-B', 'cycle-1-B'}
            and not (root / 'campaign/analysis.json').exists(), 'facility acquired unexecuted results')
    capture = _load(evidence, failed['capture']); outer = _load(evidence, audit['outer_execution'])
    require(capture['exit_code'] == 0 and outer['exit_code'] != 0,
            'native capture failure was conflated with the cycle-check failure')
    for execution in (capture, outer):
        for name in ('stdout', 'stderr'):
            evidence.bind(execution[name]['path'], execution[name]['sha256'])
    from run_shared_timing_confirmation import native_messages, timeline_protocol
    from diagnose_exp_case1_prewarm import _case_and_failure
    messages = native_messages(Path(capture['stdout']['path']))
    config, _ = _case_and_failure()
    timeline_protocol(messages, config, 100, cycle=1)
    require(messages[0]['cycle_index'] == 1 and messages[-1]['kind'] == 'complete',
            'failed cycle did not contain its actual complete native wire')
    try:
        timeline_protocol(messages, config, 100, cycle=0)
    except Exception as error:
        require(type(error).__name__ == 'ContractError' and str(error) == terminal['error']['message'],
                'old incorrect cycle check does not reproduce the retained failure')
    else:
        raise ValueError('old incorrect cycle check unexpectedly passed')
    return {'valid': True, 'authority': 'historical_facility_failure', 'complete': False,
            'eligible_for_publication': False, 'completed_slots': audit['completed_slots'],
            'failed_slot': audit['failed_slot'], 'preserved_scratch_files': retained['file_count'],
            'resolved_producers': original.resolved_files}


def _same(actual, expected):
    """Only compensate serialization-level floating arithmetic, never a gate."""
    if isinstance(expected, float):
        return isinstance(actual, (int, float)) and math.isfinite(actual) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(_same(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_same(a, e) for a, e in zip(actual, expected))
    return actual == expected


def _stage(index, prefix):
    if index < prefix:
        return 'prewarm_batch_' + str(index // 400)
    index -= prefix
    if index < 20:
        return 'warmup_baseline' if index < 10 else 'warmup_candidate'
    if index >= 4220:
        return 'untimed_snapshot'
    phase, offset = divmod(index - 20, 1400)
    name = ('aa_before', 'formal', 'aa_after')[phase]
    return name + ('_prime' if offset < 400 else '_pair_' + str((offset - 400) // 200))


def analysis_rows(slot, tasks, prefix):
    """Rebuild every registered descriptive block/window, including final tails."""
    blocks = {100: [], 400: []}; windows = []
    first, native = tasks[0]['start_us'], tasks[prefix]['start_us']
    mean = lambda rows: float(sum(t['duration_us'] for t in rows) / len(rows))
    scopes = ([('prefix', 0, prefix)] if prefix else []) + [('native', prefix, len(tasks))]
    for scope, begin, end in scopes:
        for size in blocks:
            for index, start in enumerate(range(begin, end, size)):
                stop = min(start + size, end); values = tasks[start:stop]
                blocks[size].append({'slot': slot, 'scope': scope, 'block_size': size, 'block_index': index,
                    'full_start': start, 'full_end_exclusive': stop,
                    'native_start': start - prefix if scope == 'native' else '',
                    'native_end_exclusive': stop - prefix if scope == 'native' else '', 'task_count': len(values),
                    'stage_start': _stage(start, prefix), 'stage_end': _stage(stop - 1, prefix),
                    'time_from_first_ms': float((values[0]['start_us'] - first) / 1000),
                    'time_from_native_ms': float((values[0]['start_us'] - native) / 1000) if scope == 'native' else '',
                    'end_from_first_ms': float((values[-1]['end_us'] - first) / 1000),
                    'mean_duration_us': mean(values), 'min_duration_us': float(min(t['duration_us'] for t in values)),
                    'max_duration_us': float(max(t['duration_us'] for t in values)),
                    'sum_duration_us': float(sum(t['duration_us'] for t in values))})
        for boundary in range(begin + 400, end - 399, 100):
            prior, after = mean(tasks[boundary - 400:boundary]), mean(tasks[boundary:boundary + 400])
            windows.append({'slot': slot, 'scope': scope, 'boundary_full_index': boundary,
                'boundary_scope_index': boundary - begin, 'stage_before': _stage(boundary - 1, prefix),
                'stage_after': _stage(boundary, prefix),
                'time_from_first_ms': float((tasks[boundary]['start_us'] - first) / 1000),
                'time_from_native_ms': float((tasks[boundary]['start_us'] - native) / 1000) if scope == 'native' else '',
                'prior_400_mean_us': prior, 'next_400_mean_us': after,
                'delta_us': after - prior, 'delta_percent': (after - prior) / prior * 100})
    largest = {scope: max((r for r in windows if r['scope'] == scope), key=lambda r: abs(r['delta_us']), default=None)
               for scope in ('native', 'prefix')}
    native_tasks = tasks[prefix:]
    stages = {'warmup': mean(native_tasks[:20]), 'untimed_snapshot': mean(native_tasks[4220:])}
    for phase, begin in zip(('aa_before', 'formal', 'aa_after'), (20, 1420, 2820)):
        stages[phase + '_prime'] = mean(native_tasks[begin:begin + 400])
        stages[phase + '_pairs'] = mean(native_tasks[begin + 400:begin + 1400])
    return blocks, windows, {'largest_adjacent_400_window_change': largest,
        'main_first_task_ms': float((native - first) / 1000),
        'main_last_task_ms': float((tasks[-1]['start_us'] - first) / 1000),
        'prefix_task_count': prefix, 'stage_means_us': stages}


def _check_csv(path, expected, keys, evidence):
    evidence.bind(path)
    with Path(path).open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    def identity(row):
        return tuple(str(row[key]) for key in keys)
    actual = {identity(row): row for row in rows}
    require(len(rows) == len(actual) == len(expected), 'descriptive analysis omitted or duplicated rows')
    for row in expected:
        saved = actual.get(identity(row))
        require(saved is not None and set(saved) == set(row), 'descriptive analysis scope/columns differ')
        converted = {k: float(saved[k]) if isinstance(v, float) else int(saved[k]) if isinstance(v, int) else saved[k]
                     for k, v in row.items()}
        require(_same(converted, row), 'descriptive analysis changed raw arithmetic')


def replay_task_analysis(summary_reference, evidence, *, diagnostic_root, historical_task_ref):
    summary = _load(evidence, summary_reference)
    require(summary['accepted'] is False and summary['publication_eligible'] is False,
            'descriptive analysis acquired admission authority')
    names = {f'cycle-{c}-{a}' for c in range(6) for a in ('A', 'B')} | {'original-case1-cycle3'}
    require(set(summary['sources']) == set(summary['slots']) == names, 'analysis omitted historical or diagnostic slots')
    from diagnose_exp_case1_prewarm import task_modules
    task_modules()
    from aprof_runtime.task_timing import _tasks
    blocks = {100: [], 400: []}; windows = []
    for slot in sorted(names):
        source = summary['sources'][slot]
        for key, value in source.items():
            if isinstance(value, dict):
                actual = evidence.bind(value['path'], value['sha256'])
                require(actual['bytes'] == value['bytes'], 'analysis source length differs')
        historical = slot == 'original-case1-cycle3'; arm = 'historical' if historical else slot[-1]
        prefix = 10000 if arm == 'B' else 0
        if historical:
            require(source['csv']['sha256'] == historical_task_ref, 'analysis historical Task table changed')
        else:
            for name in ('partition.json', 'result.json', 'task-audit.json'):
                require(Path(source[name]['path']) == diagnostic_root / 'campaign' / slot / name, 'analysis slot source escaped')
            audit = read(source['task-audit.json']['path'])
            require(source['csv']['sha256'] == audit['original_table']['sha256'], 'analysis raw CSV differs from replayed slot')
        rows, tasks, extra = _tasks(Path(source['csv']['path']).read_text(), {'device': 0},
                                  {'baseline': ['exp_kernel'], 'candidate': ['exp_kernel']})
        require(not extra and len(rows) == len(tasks) == source['task_count'] == prefix + 4222,
                'analysis must include every original Task row')
        local_blocks, local_windows, expected = analysis_rows(slot, tasks, prefix)
        expected.update(arm=arm, control=None, sample_means_us_per_call=None)
        if not historical:
            result = read(source['result.json']['path']); partition = read(source['partition.json']['path'])
            expected['control'] = result['task_controls']
            expected['sample_means_us_per_call'] = {phase: {role: statistics.fmean(values) / 1000
                for role, values in roles.items()} for phase, roles in partition['values_ns_per_call'].items()}
            for batch in read(source['task-audit.json']['path'])['prefix_batches']:
                start, end = batch['task_indices']
                require(float(sum(t['duration_us'] for t in tasks[start:end]) * 1000) == batch['task_duration_total_ns'],
                        'prefix batch arithmetic changed')
        require(_same(summary['slots'][slot], expected), 'analysis summary differs from original tasks')
        for size in blocks: blocks[size].extend(local_blocks[size])
        windows.extend(local_windows)
    folder = Path(summary_reference['path']).parent
    for size in blocks:
        _check_csv(folder / f'task-blocks-{size}.csv', blocks[size], ('slot', 'scope', 'block_index'), evidence)
    _check_csv(folder / 'adjacent-400-task-windows.csv', windows, ('slot', 'scope', 'boundary_full_index'), evidence)
    return {'valid': True, 'authority': 'descriptive_raw_task_analysis', 'eligible_for_publication': False,
            'raw_tables': 13, 'raw_tasks': 114886, 'block_rows': {str(k): len(v) for k, v in blocks.items()},
            'window_rows': len(windows), 'production_prewarm_accepted': False}


def replay_local_task_history_supplement(reference):
    evidence = Evidence(); supplement = _load(evidence, reference)
    require(supplement['schema_version'] == 1 and supplement['not_a_release'] is True
            and supplement['eligible_for_publication'] is False
            and supplement['purpose'] == 'explicit_history_source_supplement_for_future_protocol_registration'
            and supplement['publication_verifier_integration']['status'] == 'not_integrated',
            'supplement is not a historical-only source list')
    refs = supplement['references']
    for value in refs.values(): evidence.bind(value['path'], value['sha256'])
    older = replay_task_history(refs['base_local_task_method_history'])
    require(older['valid'] is True and older['eligible_for_publication'] is False, 'older history failed')
    cancellation = replay_task_local_cancellation(refs['task_v2_local_cancellation_audit'],
        producer_archive_ref=refs['task_v2_local_producer_only_archive'])
    require(cancellation['valid'] is True and cancellation['complete'] is False
            and cancellation['eligible_for_publication'] is False, 'cancelled campaign history failed')
    prior = _load(evidence, refs['task_v2_local_historical_replay'])
    require(prior['audit'] == cancellation['audit'] and prior['snapshot'] == cancellation['snapshot']
            and prior['complete'] is False and prior['eligible_for_publication'] is False,
            'previous historical replay scope changed')
    facility = replay_prewarm_facility_failure(refs['prewarm_v1_facility_failure_audit'], evidence)
    from diagnose_exp_case1_prewarm import replay
    preservation = _load(evidence, refs['prewarm_v2_preservation'])
    require(preservation['source_archive_ref'] == refs['prewarm_v2_source_archive']
            and preservation['freeze_ref'] == refs['prewarm_v2_freeze'], 'prewarm source preservation chain differs')
    root = Path(refs['prewarm_v2_plan']['path']).parent
    prewarm = replay(root, Path(refs['prewarm_v2_root_anchor']['path']),
                     source_archive_refs=[refs['prewarm_v2_source_archive']])
    require(prewarm['complete'] is True and prewarm['accepted'] is False
            and prewarm['eligible_for_publication'] is False, 'diagnostic became a production admission')
    analysis = replay_task_analysis(refs['prewarm_v2_raw_task_analysis_summary'], evidence, diagnostic_root=root,
        historical_task_ref=cancellation['operators']['exp']['sessions'][-1]['task_table_ref'])
    return {'valid': True, 'authority': 'historical_task_method_supplement', 'eligible_for_publication': False,
            'production_admission': False, 'supplement': reference, 'older_history': older,
            'cancelled_local_attempt': cancellation, 'prewarm_v1_failure': facility,
            'prewarm_v2_diagnostic': prewarm, 'raw_task_analysis': analysis,
            'files': {path: value['sha256'] for path, value in evidence.files.items()}}
