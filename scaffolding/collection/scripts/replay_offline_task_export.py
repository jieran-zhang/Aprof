"""Read retained offline export studies; never execute a profiler or old script."""
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path

from replay_timing_diagnosis import read, require

MSPROF = '/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof'
SUMMARY = '/usr/local/Ascend/cann-9.0.0/tools/profiler/profiler_tool/analysis/msprof/msprof.py'
PYTHON = '/usr/local/python3.11.15/bin/python3.11'
IDS = ('reports-v1-prepared-not-run', 'reports-v2-log-append-stop',
       'reports-v3-complete', 'summary-v1-complete')


def load(evidence, reference):
    evidence.bind(reference['path'], reference['sha256'])
    return read(reference['path'])


def stamp(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def tree(evidence, root, expected):
    root = Path(root)
    paths = list(root.rglob('*'))
    require(not any(path.is_symlink() for path in paths), 'symlink in retained output')
    require({str(p.relative_to(root)) for p in paths if p.is_file()} == set(expected),
            'complete retained file inventory differs')
    for name, item in expected.items():
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'unsafe inventory path')
        bound = evidence.bind(root / name, item['sha256'])
        require(bound['bytes'] == item['bytes'], 'retained file length differs')


def log_append(before, after):
    require(after.startswith(before), 'collection log was rewritten or truncated')
    suffix = after[len(before):]
    def binding(value):
        return {'sha256': 'sha256:' + hashlib.sha256(value).hexdigest(), 'bytes': len(value)}
    return {'transformation': 'append_only' if suffix else 'unchanged',
            'original_prefix_preserved': True, 'before': binding(before), 'after': binding(after),
            'appended': binding(suffix), 'appended_lines': len(suffix.splitlines())}


def count_csv(evidence, reference):
    evidence.bind(reference['path'], reference['sha256'])
    # Identical complete bytes imply identical rows; parse this shared CSV once.
    cache = getattr(evidence, '_task_csv_counts', {})
    if reference['sha256'] not in cache:
        count = 0
        with Path(reference['path']).open(newline='') as stream:
            for row in csv.DictReader(stream):
                require(row['Op Name'] == 'exp_kernel' and row['Task Type'] == 'AI_VECTOR_CORE',
                        'unexpected task in complete export CSV')
                count += 1
        cache[reference['sha256']] = count
        evidence._task_csv_counts = cache
    require(cache[reference['sha256']] == 220222, 'complete CSV task count differs')
    return cache[reference['sha256']]


def execution(evidence, value, job, *, copied_root=None, exit_code=0):
    require(value['job'] == job and value['exit_code'] == exit_code
            and value['status'] == ('passed' if exit_code == 0 else 'failed')
            and value['physical_device'] is None, 'offline execution identity or result differs')
    start, end = stamp(value['started_at']), stamp(value['finished_at'])
    duration = value['duration_seconds']
    require(math.isfinite(duration) and 0 < duration <= job['timeout_seconds']
            and start <= end and abs(end - start - duration) < .01, 'execution duration differs')
    for channel in ('stdout', 'stderr'):
        ref = value[channel]
        require(ref['path'] == str(Path(job['output_dir']) / (channel + '.log')), 'execution log path differs')
        actual = Path(copied_root) / 'job' / (channel + '.log') if copied_root else Path(ref['path'])
        evidence.bind(actual, ref['sha256'])
    return start, end


def frozen_job(plan, slot):
    target = str(Path(slot['scratch_root']) / slot['prof_name'])
    if slot['condition'] == 'summary':
        argv = [PYTHON, SUMMARY, 'export', 'summary', '-dir', target, '--format', 'csv']
    else:
        require(slot['condition'] in ('default', 'reports-off'), 'unknown export condition')
        argv = [MSPROF, '--export=on', '--type=text', '--output=' + target]
        if slot['condition'] == 'reports-off':
            argv.append('--reports=' + plan['reports_ref']['path'])
    return {'job_id': slot['id'], 'argv': argv, 'cwd': slot['scratch_root'],
            'output_dir': str(Path(slot['scratch_root']) / 'job'), 'timeout_seconds': 300,
            'environment': plan['environment']}


def input_split(plan):
    source = plan['source_files']; raw = {}; logs = {}
    for name, item in source.items():
        parts = Path(name).parts
        if len(parts) >= 3 and parts[1] in ('host', 'device_0') and 'sqlite' not in parts:
            raw[name] = item
        elif len(parts) == 3 and parts[1] == 'mindstudio_profiler_log' and parts[2] in (
                'collection_host.log', 'collection_device_0.log'):
            logs[name] = item
    require(len(raw) == 97 and len(logs) == 2, 'fixed 97 raw / two log selection differs')
    inputs = raw | logs
    require(plan.get('copied_input_files', plan.get('copied_raw_files')) == inputs,
            'fresh export inputs differ')
    if 'immutable_raw_files' in plan:
        require(plan['immutable_raw_files'] == raw and plan['append_only_collection_logs'] == logs,
                'raw / append-only split differs')
    return inputs, raw, logs


def check_terminal(result, slots, index):
    completed = index >= 2
    attempted = 1 if index == 1 else 4
    require(result['complete'] is completed and result['eligible_for_publication'] is False
            and result['kernel_measurement'] is False and result['original_profile_unchanged'] is True
            and len(result['slots']) == attempted
            and result['unrun_slots'] == [s['id'] for s in slots[attempted:]],
            'historical failed or unrun slots were lost')
    require([r['id'] for r in result['slots']] == [s['id'] for s in slots[:attempted]],
            'attempt order differs')
    require([r['status'] for r in result['slots']] == (['failed'] if index == 1 else ['passed'] * 4),
            'historical result state differs')
    if index == 1:
        name = slots[0]['prof_name'] + '/mindstudio_profiler_log/collection_device_0.log'
        require(result['error'] == {'type': 'ValueError', 'message': 'raw or collection metadata changed: ' + name},
                'original v2 log failure was replaced')
    else:
        require('error' not in result, 'completed study contains an execution failure')


def replay_slot(evidence, directory, plan, slot, saved, reference, *, earliest, latest, failed):
    destination = Path(slot['persistent_root'])
    require(destination == directory / ('slot-' + slot['id']), 'slot output escaped study')
    manifest = load(evidence, reference['complete_output_inventory_ref'])
    require(Path(reference['complete_output_inventory_ref']['path']) == directory / (destination.name + '-inventory.json'),
            'slot inventory path differs')
    tree(evidence, destination, manifest['files'])
    hashes = {name: item['sha256'] for name, item in manifest['files'].items()}
    transfer = manifest['transfer']
    require(manifest['source_root'] == slot['scratch_root'] and manifest['persistent_root'] == str(destination)
            and transfer['source_dir'] == slot['scratch_root'] and transfer['destination_dir'] == str(destination)
            and all(transfer[key] == hashes for key in ('source_inventory', 'persisted_inventory', 'source_after_inventory'))
            and manifest['file_count'] == len(hashes)
            and manifest['bytes'] == sum(item['bytes'] for item in manifest['files'].values())
            and saved['persistence'] == {k: v for k, v in manifest.items() if k != 'files'},
            'complete fsync copy evidence differs')
    job = frozen_job(plan, slot)
    require(slot['job'] == job and evidence.json(directory / (slot['id'] + '-job.json')) == job, 'export argv/env differs')
    require(Path(reference['execution_ref']['path']) == destination / 'job/execution.json', 'export receipt path differs')
    actual = load(evidence, reference['execution_ref'])
    start, end = execution(evidence, actual, job, copied_root=destination)
    require(earliest <= saved['started_at'] <= start <= end <= transfer['started_at']
            <= transfer['finished_at'] <= saved['finished_at'] <= latest, 'slot chronology differs')
    inputs, raw, logs = input_split(plan)
    for name, item in raw.items():
        require(manifest['files'][name] == item, 'raw changed during export')
    transforms = {name: log_append((Path(plan['source_profile']) / name).read_bytes(),
                                  (destination / name).read_bytes()) for name in logs}
    if failed:
        require(all(item['appended']['bytes'] > 0 for item in transforms.values()), 'v2 recorded append failure missing')
    else:
        require(saved['raw_unchanged'] is True and saved['collection_log_transforms'] == transforms,
                'recorded log transformation differs from bytes')
    tables = [name for name in hashes if Path(name).match('*/mindstudio_profiler_output/op_summary*.csv')]
    require(len(tables) == 1 and hashes[tables[0]] == plan['source_csv_ref']['sha256'], 'complete output CSV differs')
    require(saved['csv_sha256'] == hashes[tables[0]] and saved['csv_rows'] == 220222
            and saved['csv_byte_equal'] is True and saved['cloned_bytes'] == sum(v['bytes'] for v in inputs.values())
            and saved['generated_files'] == {k: v for k, v in manifest['files'].items() if k not in inputs},
            'derived output or CSV receipt differs')
    require(saved['export_seconds'] == actual['duration_seconds'], 'export cost differs from actual execution')
    costs = [saved[k] for k in ('clone_seconds', 'clone_verify_seconds', 'csv_verify_seconds')]
    costs += [manifest[k] for k in ('inventory_seconds', 'copy_seconds', 'total_persistence_seconds')]
    require(all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in costs)
            and manifest['total_persistence_seconds'] >= manifest['inventory_seconds'] + manifest['copy_seconds']
            and manifest['copy_seconds'] >= transfer['finished_at'] - transfer['started_at'], 'invalid recorded copy costs')
    return {'id': slot['id'], 'status': saved['status'], 'csv_rows': 220222, 'immutable_files': len(raw),
            'collection_log_transforms': transforms, 'retained_files': len(hashes), 'retained_bytes': manifest['bytes'],
            'export_seconds': actual['duration_seconds'], 'recorded_clone_seconds': saved['clone_seconds'],
            'recorded_full_persistence_seconds': manifest['total_persistence_seconds'],
            'clone_export_persist_seconds': saved['clone_seconds'] + actual['duration_seconds'] + manifest['total_persistence_seconds']}


def replay_offline_study(evidence, item, index):
    require(item['id'] == IDS[index] and item['eligible_for_publication'] is False
            and item['hardware_samples'] == 0, 'offline study identity or authority differs')
    directory = Path(item['directory']); plan = load(evidence, item['plan_ref'])
    require(Path(item['plan_ref']['path']) == directory / 'plan.json' and item['script_ref'] in plan['dependencies'],
            'study plan or script binding differs')
    conditions = ['reports-off', 'summary', 'summary', 'reports-off'] if index == 3 else ['default', 'reports-off', 'reports-off', 'default']
    require(plan['conditions'] == conditions and [s['condition'] for s in plan['slots']] == conditions
            and [s['id'] for s in plan['slots']] == [f'{i}-{c}' for i, c in enumerate(conditions)]
            and plan['max_attempts_per_slot'] == 1 and plan['stop_on_first_failure'] is True
            and plan['outer_timeout_seconds'] == 1800 and plan['expected_csv_rows'] == 220222
            and plan['eligible_for_publication'] is False and plan['kernel_measurement'] is False,
            'fixed offline roster, budget or scope differs')
    for ref in plan['dependencies'] + [v for k, v in plan.items() if k.endswith('_ref')]:
        evidence.bind(ref['path'], ref['sha256'])
    reports = read(plan['reports_ref']['path']); sample = read(plan['sample_ref']['path'])
    require(set(reports) == set(sample) == {'json_process'} and len(sample['json_process']) == 26
            and reports['json_process'] == dict.fromkeys(sample['json_process'], False), 'reports selection differs')
    source = Path(plan['source_profile'])
    tree(evidence, source, plan['source_files'])
    require(read(plan['source_inventory_ref']['path']) == {k: v['sha256'] for k, v in plan['source_files'].items()},
            'original full profile inventory differs')
    input_split(plan); count_csv(evidence, plan['source_csv_ref'])
    for slot in plan['slots']:
        require(slot['job'] == frozen_job(plan, slot), 'frozen command changed')
    if index == 0:
        require(item['status'] == 'prepared_not_run' and item['export_attempts'] == 0
                and not any((directory / p).exists() for p in ('started.json', 'result.json', 'campaign-job.json', 'execution'))
                and not list(directory.glob('slot-*')) and not list(directory.glob('*-job.json')),
                'prepared-only predecessor contains an execution')
        load(evidence, item['explanation_ref'])
        evidence.bind(item['preparation_stdout_ref']['path'], item['preparation_stdout_ref']['sha256'])
        return {'id': item['id'], 'status': 'prepared_not_run', 'export_attempts': 0, 'eligible_for_publication': False}
    anchor = load(evidence, item['root_anchor_ref']); started = load(evidence, item['started_ref'])
    result = load(evidence, item['result_ref']); outer = load(evidence, item['outer_execution_ref'])
    outer_job = load(evidence, item['outer_job_ref'])
    require(anchor['purpose'] == ('root_anchored_offline_summary_export_cost_study' if index == 3
                                 else 'root_anchored_offline_reports_export_cost_study')
            and anchor['plan_ref'] == item['plan_ref'] and anchor['script_ref'] == item['script_ref']
            and anchor['max_attempts_per_slot'] == 1 and anchor['eligible_for_publication'] is False
            and plan['created_at'] <= stamp(anchor['recorded_at_utc']) <= started['at']
            and started['plan_ref'] == result['plan_ref'] == item['plan_ref']
            and started['anchor_ref'] == item['root_anchor_ref'], 'root preregistration chain differs')
    require(outer_job['argv'][1:] == [item['script_ref']['path'], 'run', '--anchor', item['root_anchor_ref']['path']]
            and outer_job['cwd'] == str(directory) and outer_job['output_dir'] == str(directory / 'execution')
            and outer_job['timeout_seconds'] == 1800, 'outer execution command differs')
    evidence.bind(outer_job['argv'][0], evidence.bind(PYTHON)['sha256'])
    start, end = execution(evidence, outer, outer_job, exit_code=2 if index == 1 else 0)
    preflight = load(evidence, item['loader_preflight_ref'])
    require(item['loader_preflight_ref'] == plan['loader_preflight_ref']
            and preflight['argv'] == ([PYTHON, SUMMARY, 'export', 'summary', '--help'] if index == 3 else [MSPROF, '--help'])
            and preflight['environment'] == plan['environment'] and preflight['exit_code'] == 0
            and preflight['scope'] == 'loader_only_no_export_no_device'
            and preflight['timeout_seconds'] == 30
            and preflight['started_at'] <= preflight['finished_at'] <= plan['created_at'], 'loader preflight differs')
    for channel in ('stdout', 'stderr'):
        evidence.bind(preflight[channel]['path'], preflight[channel]['sha256'])
    require(start <= started['at'] <= end and 0 < result['total_seconds'] <= end - started['at'] + .01,
            'study total cost or execution window differs')
    require(json.loads(Path(outer['stdout']['path']).read_text()) == {
        'result_ref': item['result_ref'], 'complete': result['complete'], 'error': result.get('error')},
        'outer stdout differs from retained result')
    check_terminal(result, plan['slots'], index)
    require(item['export_attempts'] == len(result['slots']) and len(item['slots']) == len(result['slots'])
            and item['unrun_slots'] == result['unrun_slots'], 'retained attempt count differs')
    rows = []; previous = started['at']
    for slot, saved, ref in zip(plan['slots'], result['slots'], item['slots']):
        require(ref['id'] == saved['id'] and ref['status'] == saved['status'], 'slot source mapping differs')
        rows.append(replay_slot(evidence, directory, plan, slot, saved, ref, earliest=previous, latest=end, failed=index == 1))
        previous = saved['finished_at']
    for slot in plan['slots'][len(rows):]:
        require(not Path(slot['persistent_root']).exists() and not (directory / (slot['id'] + '-job.json')).exists(),
                'unrun slot has execution evidence')
    require({p.name for p in directory.glob('slot-*') if p.is_dir()} == {'slot-' + r['id'] for r in rows},
            'extra retained attempt exists')
    if index == 1:
        load(evidence, item['difference_audit_ref'])
    return {'id': item['id'], 'complete': result['complete'], 'slots': rows, 'unrun_slots': result['unrun_slots'],
            'outer_seconds': outer['duration_seconds'], 'recorded_total_seconds': result['total_seconds'],
            'eligible_for_publication': False, 'kernel_measurement': False}
