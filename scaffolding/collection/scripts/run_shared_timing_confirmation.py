#!/usr/bin/env python3
"""Once-only full-case confirmation and independent production task timelines.

Registration is offline. A repository anchor must bind the roster before run.
Failures are terminal; this dispatcher deliberately has no resume/retry option.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
from datetime import datetime
from decimal import Decimal
import fcntl
import json
import math
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys
import time

from replay_timing_diagnosis import Evidence, digest, read, require

ROOT = Path(__file__).resolve().parents[3]
RELEASE = ROOT / 'skill-libs/graph-base/0.5.1'
SCRIPTS = RELEASE / 'skills/ascendc-aprof-profiling/scripts'
QUALIFY = Path(__file__).with_name('qualify_shared_timing_v051.py')
ROLES = ('baseline', 'candidate')
PHASES = ('aa_before', 'formal', 'aa_after')
ORDER = ['exp-confirmation', 'exp-timeline-01', 'exp-timeline-09',
         'sigmoid-confirmation', 'sigmoid-timeline-01', 'sigmoid-timeline-04']
PROFILE_FLAGS = ['--task-time=l1', '--ai-core=on', '--aic-metrics=PipeUtilization',
                 '--ascendcl=off', '--runtime-api=off', '--type=text']
BASE_ENVIRONMENT = {'PYTHONDONTWRITEBYTECODE': '1', 'ASCEND_RT_VISIBLE_DEVICES': '0',
                    'OMP_NUM_THREADS': '32', 'MKL_NUM_THREADS': '32', 'OPENBLAS_NUM_THREADS': '32'}


def save_new(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False); stream.write('\n')


def prefixed(value):
    return value if value.startswith('sha256:') else 'sha256:' + value


def binding(path):
    return {'path': str(Path(path).resolve(strict=True)), 'sha256': digest(path)}


def verify_freeze(directory, evidence):
    directory = Path(directory).resolve(strict=True)
    frozen = evidence.json(directory / 'freeze.json'); plan = evidence.json(directory / 'plan.json')
    require(prefixed(frozen['plan_sha256']) == digest(directory / 'plan.json'), 'qualification plan changed')
    for bindings in (plan['frozen_files'], frozen['frozen_files']):
        for path, expected in bindings.items():
            evidence.bind(path, prefixed(expected))
    if 'predecessor' in plan:
        replay_zero_sample_predecessor(plan['predecessor'],
                                      source_archive_refs=getattr(evidence, 'archive_references', None))
        verify_replacement_semantics(directory, plan, frozen, evidence)
    return frozen, plan


def tagged_metadata(value):
    if isinstance(value, float) and not math.isfinite(value):
        return {'__aprof_nonfinite_float__': 'NaN' if math.isnan(value) else ('Infinity' if value > 0 else '-Infinity')}
    if isinstance(value, list):
        return [tagged_metadata(item) for item in value]
    if isinstance(value, dict):
        return {key: tagged_metadata(item) for key, item in value.items()}
    return value


def verify_replacement_semantics(directory, plan, frozen, evidence):
    """The amendment permits metadata encoding and new output paths only."""
    predecessor = plan['predecessor']; old_root = Path(predecessor['qualification_dir'])
    amendment = read(predecessor['amendment_ref']['path'])
    require(Path(amendment['replacement_dir']).resolve() == directory, 'replacement is outside the amended one-attempt directory')
    old_frozen = read(predecessor['freeze_ref']['path']); old_plan = read(old_root / 'plan.json')
    def relocate(value):
        if isinstance(value, str):
            return value.replace(str(old_root), str(directory))
        if isinstance(value, list):
            return [relocate(item) for item in value]
        if isinstance(value, dict):
            return {key: relocate(item) for key, item in value.items()}
        return value
    for op in ('exp', 'sigmoid'):
        expected = relocate(read(old_frozen['configs'][op]))
        expected.update(run_id=directory.name, session_id=directory.name + '-' + op)
        for case in expected['cases']:
            case['workload'] = tagged_metadata(case['workload'])
        actual = evidence.json(frozen['configs'][op])
        require(actual == expected, 'replacement changed more than descriptive metadata encoding and output identity')
        previous_review = read(old_plan['operators'][op]['source_review'])
        current_review = evidence.json(plan['operators'][op]['source_review'])
        require(current_review['adapted_files'] == previous_review['adapted_files']
                and current_review['original_files'] == previous_review['original_files'],
                'replacement modified native kernel/header/oracle source')


def replay_zero_sample_predecessor(predecessor: dict, *, source_archive_refs=None) -> dict:
    """Audit the one known strict-JSON entrance failure without rewriting it.

    The original registered producer bytes are resolved through hash-matching
    snapshots. No historical producer is executed, and no success boolean can
    substitute for the two actual failed CLI logs and all six terminal slots.
    """
    if source_archive_refs is None:
        evidence = Evidence()
    else:
        from measurement_source_archive import HistoricalEvidence
        evidence = HistoricalEvidence(source_archive_refs)
    directory = Path(predecessor['qualification_dir']).resolve(strict=True)
    names = ('freeze_ref', 'roster_ref', 'campaign_ref', 'root_anchor_ref', 'failed_replay_ref',
             'producer_snapshots_ref', 'amendment_ref')
    for name in names:
        item = predecessor[name]; evidence.bind(item['path'], prefixed(item['sha256']))
    frozen = read(predecessor['freeze_ref']['path']); roster = read(predecessor['roster_ref']['path'])
    campaign = read(predecessor['campaign_ref']['path']); anchor = read(predecessor['root_anchor_ref']['path'])
    amendment = read(predecessor['amendment_ref']['path']); snapshots = read(predecessor['producer_snapshots_ref']['path'])
    require(predecessor['freeze_ref']['path'] == str(directory / 'freeze.json')
            and predecessor['roster_ref']['path'] == str(directory / 'roster.json')
            and predecessor['campaign_ref']['path'] == str(directory / 'campaign/campaign.json'), 'predecessor artifacts relocated')
    require(snapshots['schema_version'] == 1 and len(snapshots['source_indexes']) == 2, 'historical producer snapshot identity differs')
    merged = {}
    for source_index in snapshots['source_indexes']:
        evidence.bind(source_index['path'], source_index['sha256'])
        value = read(source_index['path'])
        values = value['files'] if 'files' in value else value
        require(not set(values).intersection(merged), 'duplicate historical producer snapshot')
        merged.update(values)
    require(merged == snapshots['files'], 'historical producer snapshot indexes do not agree')
    archived = snapshots['files']
    allowed_names = {'qualify_shared_timing_v051.py', 'verify_measurement_release.py',
                     'verify_measurement_publication.py', 'run_shared_timing_confirmation.py', 'replay_timing_diagnosis.py'}
    require(len(archived) == 4 and all(Path(path).name in allowed_names for path in archived), 'unexpected historical producer override')
    def old_bind(path, expected):
        if path in archived:
            item = archived[path]
            require(prefixed(item['sha256']) == prefixed(expected), 'archived producer does not match its original frozen hash')
            evidence.bind(item['path'], prefixed(expected))
        else:
            evidence.bind(path, prefixed(expected))
    old_plan_path = directory / 'plan.json'; plan = evidence.json(old_plan_path)
    require(prefixed(frozen['plan_sha256']) == digest(old_plan_path), 'old plan changed')
    for inventory in (plan['frozen_files'], frozen['frozen_files'], roster['producer_files']):
        for path, expected in inventory.items():
            old_bind(path, expected)
    for path, item in archived.items():
        expected = next((inventory[path] for inventory in (plan['frozen_files'], frozen['frozen_files'], roster['producer_files']) if path in inventory), None)
        require(expected is not None, 'unfrozen historical producer snapshot')
        old_bind(path, expected)
    require(roster['order'] == ORDER and [s['slot_id'] for s in roster['slots']] == ORDER
            and roster['max_attempts_per_slot'] == 1 and roster['resampling'] == 'none', 'old finite roster changed')
    require(anchor['purpose'] == 'preregistered_production_measurement_confirmation'
            and anchor['roster'] == binding(directory / 'roster.json') == campaign['roster'], 'old trusted anchor differs')
    require(amendment['schema_version'] == 1 and amendment['purpose'] == 'preregistered_nonfinite_workload_metadata_encoding_fix'
            and amendment['predecessor_roster'] == predecessor['roster_ref']
            and amendment['predecessor_campaign'] == predecessor['campaign_ref']
            and amendment['producer_snapshots'] == predecessor['producer_snapshots_ref']
            and amendment['allowed_change'] == 'nonfinite_workload_metadata_to_tagged_json'
            and Path(amendment['replacement_dir']).resolve() != directory, 'amendment is not the narrow zero-sample metadata repair')
    require(datetime.fromisoformat(anchor['recorded_at_utc']).timestamp() <= campaign['finished_at']
            <= datetime.fromisoformat(amendment['recorded_at_utc']).timestamp(), 'amendment predates the old failure')
    require(campaign['accepted'] is False and set(campaign['slots']) == set(ORDER)
            and {p.name for p in (directory / 'campaign').iterdir() if p.is_dir()} == set(ORDER), 'old six-slot terminal inventory differs')
    terminal_rows = {}; nonfinite = {}; costs = {}
    for slot in roster['slots']:
        slot_id = slot['slot_id']; op = slot['operator']; terminal_path = directory / 'campaign' / slot_id / 'terminal.json'
        require(campaign['slots'][slot_id] == binding(terminal_path), 'old terminal hash changed')
        terminal = evidence.json(terminal_path); terminal_rows[slot_id] = terminal
        require(terminal['slot_id'] == slot_id and terminal['roster'] == binding(directory / 'roster.json'), 'old terminal slot identity changed')
        if slot['kind'] == 'timeline':
            dependency = slot['prerequisite_slot']
            require(terminal['status'] == 'not_run' and dependency in terminal_rows
                    and terminal_rows[dependency]['status'] in ('failed', 'not_run')
                    and terminal['prerequisite_ref'] == binding(directory / 'campaign' / dependency / 'terminal.json')
                    and 'execution' not in terminal and not (terminal_path.parent / 'started.json').exists()
                    and not Path(slot['output_dir']).exists()
                    and not (directory / op / f"timeline-case-{slot['case_id']:02d}").exists(), 'historical timeline actually ran or lacks its failed dependency')
            continue
        require(terminal['status'] == 'failed' and not Path(slot['output_dir']).exists(), 'old collector created output or is not failed')
        start = evidence.json(terminal_path.parent / 'started.json')
        require(start['slot'] == slot and terminal['started'] == binding(terminal_path.parent / 'started.json'), 'old started slot differs')
        execution_path = terminal_path.parent / 'job/execution.json'
        require(terminal['execution'] == binding(execution_path), 'old execution ref differs')
        execution = evidence.json(execution_path)
        require(execution['exit_code'] != 0 and execution['status'] == 'failed'
                and execution['job']['argv'] == slot['argv'] and execution['job']['environment'] == BASE_ENVIRONMENT,
                'old CLI did not fail exactly as registered')
        require(start['started_at'] <= datetime.fromisoformat(execution['started_at']).timestamp()
                <= datetime.fromisoformat(execution['finished_at']).timestamp() <= terminal['finished_at'], 'old execution time lies outside slot')
        for name in ('stdout', 'stderr'):
            evidence.bind(execution[name]['path'], execution[name]['sha256'])
        stderr = Path(execution['stderr']['path']).read_text(); stdout = Path(execution['stdout']['path']).read_text()
        require('ContractError: invalid JSON number: -Infinity' in stderr
                and 'collect(_json(args.config.read_text()), args.output, store)' in stderr
                and 'APROF_SHARED_TIMING_JSON:' not in stdout, 'old failure is not the strict config-JSON entrance error')
        config_path = Path(frozen['configs'][op]); config = read(config_path)
        try:
            json.loads(config_path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except ValueError as error:
            require(str(error) == '-Infinity', 'old config fails for a different reason')
        else:
            raise ValueError('old config no longer reproduces strict JSON entrance failure')
        found = []
        for case in config['cases']:
            for index, value in enumerate(case['workload'].get('value_range', [])):
                if isinstance(value, float) and not math.isfinite(value):
                    found.append({'case_id': case['case_id'], 'field': f'value_range[{index}]',
                                  'value': 'nan' if math.isnan(value) else ('-inf' if value < 0 else 'inf')})
        expected = [{'case_id': 12, 'field': 'value_range[0]', 'value': '-inf'},
                    {'case_id': 12, 'field': 'value_range[1]', 'value': 'inf'},
                    {'case_id': 13, 'field': 'value_range[0]', 'value': 'nan'},
                    {'case_id': 13, 'field': 'value_range[1]', 'value': 'nan'}]
        require(found == expected, 'old nonfinite metadata defect differs')
        nonfinite[op] = found
        store_path = directory / op / 'evidence.sqlite'
        evidence.bind(store_path)
        with contextlib.closing(sqlite3.connect(store_path.as_uri() + '?mode=ro', uri=True)) as connection:
            require(connection.execute('SELECT COUNT(*) FROM artifacts').fetchone()[0] == 0
                    and connection.execute('SELECT COUNT(*) FROM episodes').fetchone()[0] == 0,
                    'old failed attempt contains registered hardware/measurement artifacts')
        objects = store_path.with_suffix(store_path.suffix + '.objects')
        if objects.exists():
            require(not any(p.is_file() for p in objects.rglob('*')), 'old failed attempt has CAS objects')
        costs[op] = {'duration_seconds': execution['duration_seconds'], 'execution': binding(execution_path)}
    old_replay = evidence.json(predecessor['failed_replay_ref']['path'])
    require(old_replay['complete'] is True and old_replay['accepted'] is False and old_replay['slots'] == terminal_rows,
            'old saved negative replay disagrees with actual terminals')
    outer = evidence.json(directory / 'campaign-job/execution.json')
    require(outer['exit_code'] == 0 and outer['job']['argv'][2] == 'run', 'old campaign did not close normally')
    for name in ('stdout', 'stderr'):
        evidence.bind(outer[name]['path'], outer[name]['sha256'])
    return {'valid': True, 'authority': 'zero_native_strict_json_infrastructure_predecessor_only',
            'native_cycles': 0, 'measurement_samples': 0, 'hardware_profiles': 0, 'slots': terminal_rows,
            'nonfinite_metadata': nonfinite, 'execution_costs': costs,
            'amendment': predecessor['amendment_ref'], 'replacement_dir': amendment['replacement_dir'],
            'files': {path: item['sha256'] for path, item in evidence.files.items()}}


def register(directory, output):
    directory = Path(directory).resolve(strict=True); evidence = Evidence()
    frozen, plan = verify_freeze(directory, evidence)
    timeline = evidence.json(directory / 'timeline-plan.json')
    profiler = Path(shutil.which('msprof') or '/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof').resolve(strict=True)
    slots = []
    for op in ('exp', 'sigmoid'):
        config = read(frozen['configs'][op])
        require(config['physical_device'] == config['device'] == 0, 'this campaign requires physical/logical device 0')
        confirmation = directory / op / 'confirmation'
        slots.append({'slot_id': op + '-confirmation', 'operator': op, 'kind': 'confirmation', 'case_id': None,
                      'output_dir': str(confirmation), 'prerequisite_slot': None,
                      'environment': BASE_ENVIRONMENT,
                      'argv': [sys.executable, str(SCRIPTS / 'device_shared_timing.py'), '--config', frozen['configs'][op],
                               '--output', str(confirmation), '--store', str(directory / op / 'evidence.sqlite')]})
        for item in [x for x in timeline['runs'] if x['operator'] == op]:
            cid = item['case_id']; slot_id = f'{op}-timeline-{cid:02d}'
            slots.append({'slot_id': slot_id, 'operator': op, 'kind': 'timeline', 'case_id': cid,
                          'output_dir': str(directory / op / f'timeline-profile-{cid:02d}'),
                          'prerequisite_slot': op + '-confirmation' if cid == 1 else op + '-timeline-01',
                          'environment': dict(BASE_ENVIRONMENT, **item['environment']),
                          'argv': [str(profiler), '--output=' + str(directory / op / f'timeline-profile-{cid:02d}' / 'profile'),
                                   *PROFILE_FLAGS,
                                   '--application=' + shlex.join(item['application'])]})
    require([s['slot_id'] for s in slots] == ORDER, 'timeline plan changed the fixed six slots')
    producers = [Path(__file__), QUALIFY, Path(__file__).with_name('run_aprof_job.py'),
                 Path(__file__).with_name('replay_timing_diagnosis.py')]
    roster = {'schema_version': 1, 'purpose': 'once_only_measurement_confirmation', 'qualification_dir': str(directory),
              'freeze': binding(directory / 'freeze.json'), 'timeline_plan': binding(directory / 'timeline-plan.json'),
              'producer_files': {str(p.resolve()): digest(p) for p in producers},
              'tools': {'python': binding(sys.executable), 'profiler': binding(profiler)},
              'slots': slots, 'order': ORDER, 'max_attempts_per_slot': 1, 'resampling': 'none', 'created_at': time.time(),
              'failure_policy': 'No retries. The first failed slot blocks the remaining slots for that operator; judge both operators.',
              'environment': BASE_ENVIRONMENT,
              'lock_policy': 'Outer host-serial and device1..15; collector owns device0; profiler acquires device0 separately.'}
    save_new(output, roster)
    return binding(output)


def checked_roster(roster_path, evidence, *, qualification_dir):
    roster = evidence.json(roster_path); directory = Path(qualification_dir).resolve(strict=True)
    require(roster['schema_version'] == 1 and roster['purpose'] == 'once_only_measurement_confirmation'
            and roster['qualification_dir'] == str(directory) and roster['order'] == ORDER
            and [s['slot_id'] for s in roster['slots']] == ORDER and roster['max_attempts_per_slot'] == 1
            and roster['resampling'] == 'none', 'invalid fixed confirmation roster')
    for item in (roster['freeze'], roster['timeline_plan'], *roster['tools'].values()):
        evidence.bind(item['path'], item['sha256'])
    for path, expected in roster['producer_files'].items():
        evidence.bind(path, expected)
    frozen, plan = verify_freeze(directory, evidence)
    require(roster['freeze']['path'] == str(directory / 'freeze.json')
            and roster['timeline_plan']['path'] == str(directory / 'timeline-plan.json'), 'roster freeze relocated')
    require(roster['environment'] == BASE_ENVIRONMENT, 'registered environment differs')
    profiles = read(directory / 'timeline-plan.json')['runs']
    for slot in roster['slots']:
        op = slot['operator']; config = read(frozen['configs'][op])
        require(op in ('exp', 'sigmoid') and config['expected_case_ids'] == list(range(1, 21))
                and config['device'] == config['physical_device'] == 0, 'full20 scope/device changed')
        if slot['kind'] == 'confirmation':
            require(slot['slot_id'] == op + '-confirmation' and slot['case_id'] is None
                    and slot['prerequisite_slot'] is None and slot['environment'] == BASE_ENVIRONMENT
                    and slot['output_dir'] == str(directory / op / 'confirmation'), 'confirmation slot semantics changed')
            expected_argv = [roster['tools']['python']['path'], str(SCRIPTS / 'device_shared_timing.py'),
                '--config', frozen['configs'][op], '--output', slot['output_dir'], '--store', str(directory / op / 'evidence.sqlite')]
        else:
            require(slot['kind'] == 'timeline', 'unexpected slot kind')
            matches = [x for x in profiles if x['operator'] == op and x['case_id'] == slot['case_id']]
            require(len(matches) == 1, 'unregistered timeline case')
            item = matches[0]; cid = slot['case_id']
            require(slot['slot_id'] == f'{op}-timeline-{cid:02d}'
                    and slot['prerequisite_slot'] == (op + '-confirmation' if cid == 1 else op + '-timeline-01')
                    and slot['environment'] == dict(BASE_ENVIRONMENT, **item['environment'])
                    and slot['output_dir'] == str(directory / op / f'timeline-profile-{cid:02d}'), 'timeline slot semantics changed')
            expected_argv = [roster['tools']['profiler']['path'], '--output=' + str(Path(slot['output_dir']) / 'profile'),
                             *PROFILE_FLAGS, '--application=' + shlex.join(item['application'])]
        # The spelling of python may be a symlink; its frozen bytes are checked.
        require(slot['argv'][1:] == expected_argv[1:], 'slot command does not follow frozen input/config')
        evidence.bind(slot['argv'][0], roster['tools']['python' if slot['kind'] == 'confirmation' else 'profiler']['sha256'])
    return roster, frozen, plan


@contextlib.contextmanager
def locks(names):
    with contextlib.ExitStack() as stack:
        directory = Path('/tmp/aprof-device-locks'); directory.mkdir(exist_ok=True)
        for name in names:
            stream = stack.enter_context((directory / name).open('a+'))
            fcntl.flock(stream, fcntl.LOCK_EX)
        yield


def runtime_modules():
    sys.path.insert(0, str(RELEASE / 'runtime/src'))
    from aprof_runtime.measurement_admission import replay_measurement_admission, _session_samples
    from aprof_runtime.store import EpisodeStore
    return replay_measurement_admission, _session_samples, EpisodeStore


def confirmation_admission(directory, op, *, historical_evidence=None):
    replay, _, _ = runtime_modules()
    from aprof_runtime.store import _ReadOnlyArtifacts, default_object_directory
    config = read(directory / op / 'config.json')
    artifacts = read(directory / op / 'confirmation/artifacts.json')
    receipt = read(directory / op / 'confirmation/measurement_admission.json')
    require(config['expected_case_ids'] == list(range(1, 21)) and receipt['source_hashes']['baseline'] == receipt['source_hashes']['candidate'],
            'confirmation must use all20 cases and identical baseline source roles')
    path = directory / op / 'evidence.sqlite'
    with contextlib.closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as connection:
        store = _ReadOnlyArtifacts(connection, default_object_directory(path))
        expected = {
            'operator': op, 'run_id': config['run_id'], 'session_id': config['session_id'],
            'candidate_id': config['candidate_id'], 'source_hashes': receipt['source_hashes']}
        if historical_evidence is None:
            result = replay(store, artifacts['measurement_admission'], expected=expected)
        else:
            from aprof_runtime.measurement_admission import replay_historical_measurement_admission
            historical = replay_historical_measurement_admission(store, artifacts['measurement_admission'],
                expected=expected, producer_resolver=historical_evidence.resolve_producer)
            require(historical['eligible_for_publication'] is False, 'historical replay cannot grant admission')
            result = historical['replay']
    # The normal production gate correctly permits formal A/B gains. This
    # confirmation uses the identical baseline for both callbacks, so its
    # predeclared A/A role-bias bound also applies to formal samples.
    for row in result['report']['controls']:
        for stratum in [row['overall'], *row['cycles']]:
            require(stratum['formal']['role_bias'] <= .02, 'baseline-only formal role bias exceeds 2%')
    return result


def native_messages(path):
    prefix = 'APROF_SHARED_TIMING_JSON:'
    return [json.loads(line[len(prefix):]) for line in Path(path).read_text().splitlines() if line.startswith(prefix)]


def confirmation_repeat(directory, operator, case_id):
    folder = Path(directory) / operator / 'confirmation'
    receipt = read(folder / 'measurement_admission.json')
    require(digest(folder / 'registration.json') == receipt['registration_ref'], 'confirmation calibration registration changed')
    registration = read(folder / 'registration.json')
    require(registration['protocol'] == 'shared_buffer_acl_event_v2', 'timeline needs calibrated production protocol')
    repeat = registration['repeat_by_case'][str(case_id)]
    require(type(repeat) is int and 100 <= repeat <= 100000 and repeat % 100 == 0, 'invalid frozen confirmation repeat')
    return repeat


def resolved_environment(environment, directory, operator, case_id):
    actual = dict(environment)
    if actual.get('APROF_SHARED_REPEAT') == '{confirmation_repeat}':
        actual['APROF_SHARED_REPEAT'] = str(confirmation_repeat(directory, operator, case_id))
    return actual


def task_counts(repeat):
    require(type(repeat) is int and 100 <= repeat <= 100000 and repeat % 100 == 0, 'invalid timeline repeat')
    return {'baseline': 1011 + 25 * repeat, 'candidate': 211 + 5 * repeat}


def timeline_protocol(messages, config, expected_repeat, *, cycle=0):
    """Use the runtime state-machine replay without inventing controller ACKs.

    For a pipe-fed profiling run there are no controller request timestamps.
    Envelopes below are explicitly derived from the native intervals solely to
    call the same payload validator; they are never emitted as raw receipts.
    """
    require(len(messages) == 20, 'timeline needs READY plus exactly 19 native commands')
    require(all(m.get('mode') == 'confirmation' for m in messages), 'timeline is not a confirmation cycle')
    events = []
    for message in messages[1:]:
        if message['kind'] == 'complete':
            start = message['untimed_verifications'][0]['started_monotonic_ns']
            finish = message['untimed_verifications'][-1]['finished_monotonic_ns']
        else:
            start, finish = message['started_monotonic_ns'], message['finished_monotonic_ns']
        events.append({'request_monotonic_ns': start, 'response_monotonic_ns': finish, 'message': message})
    _, validate, _ = runtime_modules()
    validate({'mode': 'confirmation', 'cycle': cycle, 'ready': messages[0],
              'execution': {'pid': messages[0]['pid']}, 'events': events},
             config, expected_repeat=expected_repeat)


def timeline_spans(table, messages, operator):
    repeat = messages[0]['repeat']
    expected_tasks = sum(task_counts(repeat).values())
    with Path(table).open(newline='') as stream:
        reader = csv.DictReader(stream)
        require({'Op Name', 'Task Start Time(us)', 'Task Duration(us)', 'Task Type', 'Stream ID', 'Task ID', 'Device_id'}
                <= set(reader.fieldnames or []), 'unknown task table schema')
        rows = list(reader)
        require(all(row['Op Name'] == operator + '_kernel' or row['Task Type'] not in ('AI_CORE', 'AI_VECTOR_CORE', 'MIX_AIC', 'MIX_AIV')
                    for row in rows), 'unregistered compute kernel in production timeline')
        tasks = [row for row in rows if row['Op Name'] == operator + '_kernel']
    require(len(tasks) == expected_tasks, 'production timeline complete kernel launch count differs')
    tasks.sort(key=lambda row: Decimal(row['Task Start Time(us)'].strip()))
    require({row['Device_id'] for row in tasks} == {'0'} and len({row['Stream ID'] for row in tasks}) == 1,
            'production task timeline is not one device0 stream')
    identities = [(r['Device_id'], r['Stream ID'], r['Task ID'], r['Task Start Time(us)']) for r in tasks]
    require(len(set(identities)) == len(identities), 'duplicate production task records')
    for left, right in zip(tasks, tasks[1:]):
        require(Decimal(right['Task Start Time(us)'].strip()) >= Decimal(left['Task Start Time(us)'].strip())
                + Decimal(left['Task Duration(us)'].strip()) - Decimal('0.002'), 'overlapping kernel tasks')
    for task in tasks:
        require(all(math.isfinite(float(task[k])) and float(task[k]) > 0 for k in ('Task Start Time(us)', 'Task Duration(us)')),
                'invalid production task timestamp/duration')
    spans = []; cursor = 20
    for message in messages[1:-1]:
        if message['kind'] == 'prime':
            cursor += 400
            continue
        for role in message['order']:
            selected = tasks[cursor:cursor + repeat]
            require(len(selected) == repeat, 'incomplete event task group')
            origin = Decimal(selected[0]['Task Start Time(us)'])
            starts = [float((Decimal(t['Task Start Time(us)']) - origin) * 1000) for t in selected]
            durations = [float(t['Task Duration(us)']) * 1000 for t in selected]
            sample = message[role]
            spans.append({'phase': message['phase'], 'pair_index': message['pair_index'], 'role': role,
                          'implementation': sample['implementation'], 'task_indices': [cursor, cursor + repeat],
                          'task_count': repeat, 'kernel_total_duration_ns': math.fsum(durations),
                          'first_last_kernel_span_ns': max(s + d for s, d in zip(starts, durations)) - min(starts),
                          'acl_event_range_ns': sample['elapsed_ns'] * repeat,
                          'native_started_monotonic_ns': sample['started_monotonic_ns'],
                          'native_finished_monotonic_ns': sample['finished_monotonic_ns'], 'tasks': selected})
            cursor += repeat
    require(cursor == expected_tasks - 2 and len(spans) == 30, 'production phase-to-task partition differs')
    return spans


def production_oracle(driver_dir, role, case, receipt, evidence):
    verification = receipt['verifications'][role]
    expand = lambda tokens: [t.replace('{cycle_dir}', str(driver_dir)) for t in tokens]
    require(verification['argv'] == expand(case['verify_commands'][role]) and verification['exit_status'] == 0
            and receipt['started_at'] <= verification['started_at'] < verification['finished_at'] <= receipt['finished_at'],
            'timeline oracle invocation or interval differs')
    evidence.bind(driver_dir / f'{role}.bin', prefixed(verification['output_sha256']))
    log = driver_dir / f'{role}-verify.log'; evidence.bind(log, prefixed(verification['log_sha256']))
    result = evidence.json(driver_dir / f'{role}-result.json')
    printed = []
    for line in log.read_text().splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and 'case_id' in value:
            printed.append(value)
    require(printed == [result], 'timeline oracle result differs from actual stdout')
    workload = case['workload']
    for key in ('case_id', 'shape', 'numel', 'dtype'):
        require(result[key] == workload[key], 'timeline oracle workload differs')
    attrs = {k: workload[k] for k in ('base', 'scale', 'shift')} if 'base' in workload else {}
    threshold = {'float16': 2**-10, 'bfloat16': 2**-7, 'float32': 2**-13}[workload['dtype']]
    require(result['attrs'] == attrs and result['threshold'] == threshold and result['special_values_match'] is True
            and result['passed'] is True and all(math.isfinite(result[k]) and result[k] >= 0 for k in ('mere', 'mare'))
            and result['mere'] < threshold and result['mare'] < 10 * threshold, 'timeline native numerical gate failed')
    require((driver_dir / f'{role}.bin').stat().st_size == workload['numel'] * (4 if workload['dtype'] == 'float32' else 2),
            'timeline independent output snapshot length differs')


def replay_production_timeline(report_path: Path, *, qualification_dir: Path, operator: str, case_id: int,
                               source_archive_refs=None) -> dict:
    if source_archive_refs is None:
        evidence = Evidence()
    else:
        from measurement_source_archive import HistoricalEvidence
        evidence = HistoricalEvidence(source_archive_refs, logical_paths=True)
    directory = Path(qualification_dir).resolve(strict=True)
    frozen, plan = verify_freeze(directory, evidence); supplied = evidence.json(report_path)
    confirmation_admission(directory, operator,
                           historical_evidence=evidence if source_archive_refs is not None else None)
    repeat = confirmation_repeat(directory, operator, case_id)
    expected_calls = task_counts(repeat)
    evidence.bind(directory / operator / 'confirmation/registration.json')
    timeline_plan = evidence.json(directory / 'timeline-plan.json')
    matches = [x for x in timeline_plan['runs'] if x['operator'] == operator and x['case_id'] == case_id]
    require(len(matches) == 1 and supplied['operator'] == operator and supplied['case_id'] == case_id,
            'unexpected production timeline workload')
    item = matches[0]; driver_dir = Path(item['output']); capture_dir = directory / operator / f'timeline-profile-{case_id:02d}'
    require(Path(report_path).resolve() == capture_dir / 'timeline-report.json', 'timeline report outside its unique slot')
    receipt = evidence.json(driver_dir / 'receipt.json'); started = evidence.json(driver_dir / 'started.json')
    config = read(frozen['configs'][operator]); case = next(c for c in config['cases'] if c['case_id'] == case_id)
    require(receipt['purpose'] == 'timeline_only_not_formal_samples' and receipt['operator'] == operator and receipt['case_id'] == case_id
            and receipt['status'] == 'native_complete_pending_external_trace_review' and receipt['exit_status'] == 0
            and prefixed(receipt['freeze_sha256']) == digest(directory / 'freeze.json'), 'native timeline failed or wrong freeze')
    require(started['started_at'] == receipt['started_at'] and started['argv'] == receipt['argv'], 'timeline started receipt differs')
    expected_command = [t.replace('{cycle_dir}', str(driver_dir)) for t in case['command']]
    require(receipt['argv'] == expected_command and prefixed(receipt['binary_sha256']) == digest(config['build']['binary']), 'timeline binary/argv differs')
    evidence.bind(driver_dir / 'stdout.log', prefixed(receipt['stdout_sha256']))
    messages = native_messages(driver_dir / 'stdout.log')
    require(messages == receipt['messages'], 'native timeline messages differ from actual stdout')
    timeline_protocol(messages, config, repeat)
    from qualify_shared_timing_v051 import protocol_commands
    require(receipt['commands'] == protocol_commands(), 'production timeline stdin protocol changed')
    execution = evidence.json(capture_dir / 'job/execution.json'); job = execution['job']
    require(execution['exit_code'] == 0 and job['argv'][-1] == '--application=' + shlex.join(item['application']), 'actual profiler application differs')
    require(job['argv'][1:] == ['--output=' + str(capture_dir / 'profile'), *PROFILE_FLAGS,
            '--application=' + shlex.join(item['application'])], 'profiling mode differs')
    evidence.bind(item['command_file']['path'], prefixed(item['command_file']['sha256']))
    require(Path(item['command_file']['path']).read_text().splitlines() == protocol_commands()
            and job['environment'] == resolved_environment(dict(BASE_ENVIRONMENT, **item['environment']), directory, operator, case_id),
            'frozen native command file/environment differs')
    evidence.bind(job['argv'][0], supplied['profiler']['sha256'])
    for key in ('stdout', 'stderr'):
        evidence.bind(execution[key]['path'], execution[key]['sha256'])
    tables = list((capture_dir / 'profile').rglob('op_summary*.csv'))
    require(len(tables) == 1, 'expected exactly one production task table')
    evidence.bind(tables[0]); spans = timeline_spans(tables[0], messages, operator)
    for role in ROLES:
        production_oracle(driver_dir, role, case, receipt, evidence)
    require(supplied['sample_spans'] == spans and supplied['complete_kernel_tasks'] == sum(expected_calls.values())
            and supplied['expected_calls'] == expected_calls and supplied['repeat'] == repeat, 'timeline summary does not replay')
    if (capture_dir / 'export-job/execution.json').exists():
        exported = evidence.json(capture_dir / 'export-job/execution.json')
        require(exported['exit_code'] == 0 and exported['job']['argv'][:3] == [job['argv'][0], '--export=on', '--type=text'], 'task export failed')
        for key in ('stdout', 'stderr'):
            evidence.bind(exported[key]['path'], exported[key]['sha256'])
    result = {'qualified': True, 'operator': operator, 'case_id': case_id, 'sample_spans': spans,
            'expected_calls': expected_calls, 'complete_kernel_tasks': sum(expected_calls.values()), 'repeat': repeat,
            'files': evidence.semantic_files() if source_archive_refs is not None else
                     {p: r['sha256'] for p, r in evidence.files.items()},
            'authority': 'independent_task_timeline_not_formal_timing_samples',
            'clock_note': 'Native monotonic and profiler clocks are not assumed equal; frozen complete launch order partitions each R-task event.'}
    if source_archive_refs is not None:
        return {'replay': result, 'eligible_for_publication': False,
                'resolved_producers': evidence.resolved_files, 'source_archives': source_archive_refs}
    return result


def timeline_capture(slot, roster, directory):
    from run_aprof_job import run as job_run
    output = Path(slot['output_dir']); output.mkdir(exist_ok=False)
    frozen = read(directory / 'freeze.json'); config = read(frozen['configs'][slot['operator']])
    case = next(c for c in config['cases'] if c['case_id'] == slot['case_id'])
    item = next(c for c in read(directory / 'timeline-plan.json')['runs']
                if c['operator'] == slot['operator'] and c['case_id'] == slot['case_id'])
    repeat = confirmation_repeat(directory, slot['operator'], slot['case_id'])
    expected_calls = task_counts(repeat)
    driver = Path(item['output']); driver.mkdir(exist_ok=False)
    from qualify_shared_timing_v051 import protocol_commands
    receipt = {'purpose': 'timeline_only_not_formal_samples', 'operator': slot['operator'], 'case_id': slot['case_id'],
               'started_at': time.time(), 'freeze_sha256': digest(directory / 'freeze.json'), 'argv': item['application'],
               'binary_sha256': digest(config['build']['binary']), 'commands': protocol_commands(), 'verifications': {},
               'accepted': False, 'status': 'started', 'requires_external_trace_review': True,
               'command_file': item['command_file'], 'execution_mode': 'direct_native_msprof_application'}
    save_new(driver / 'started.json', receipt)
    job = {'job_id': slot['slot_id'], 'argv': slot['argv'], 'cwd': config['build']['source_dir'], 'output_dir': str(output / 'job'),
           'timeout_seconds': 1200,
           'environment': resolved_environment(slot['environment'], directory, slot['operator'], slot['case_id'])}
    save_new(output / 'job.json', job)
    with locks(['device-0.lock']):
        execution = job_run(job)
    receipt['exit_status'] = execution['exit_code']
    receipt['exit_status_source'] = 'profiler_job_exit_and_required_native_complete_ACK'
    shutil.copyfile(output / 'job/stdout.log', driver / 'stdout.log')
    receipt['stdout_sha256'] = digest(driver / 'stdout.log')
    try:
        require(execution['exit_code'] == 0, 'independent production profiler execution failed')
        receipt['messages'] = native_messages(driver / 'stdout.log')
        timeline_protocol(receipt['messages'], config, repeat)
        for role in ROLES:
            command = [t.replace('{cycle_dir}', str(driver)) for t in case['verify_commands'][role]]
            output_hash = digest(driver / (role + '.bin')); started = time.time()
            with (driver / (role + '-verify.log')).open('xb') as log:
                completed = subprocess.run(command, cwd=config['build']['source_dir'], env=dict(os.environ, **BASE_ENVIRONMENT),
                                           stdout=log, stderr=subprocess.STDOUT, timeout=180)
            receipt['verifications'][role] = {'argv': command, 'started_at': started, 'finished_at': time.time(),
                'exit_status': completed.returncode, 'output_sha256': output_hash,
                'log_sha256': digest(driver / (role + '-verify.log'))}
            require(completed.returncode == 0 and digest(driver / (role + '.bin')) == output_hash, 'independent callback oracle failed')
        receipt['status'] = 'native_complete_pending_external_trace_review'
    except Exception as error:
        receipt.update(status='failed', error={'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
        receipt['finished_at'] = time.time(); save_new(driver / 'receipt.json', receipt)
    tables = list((output / 'profile').rglob('op_summary*.csv'))
    if not tables:
        profiles = list((output / 'profile').glob('PROF_*'))
        require(len(profiles) == 1, 'ambiguous production profiler output')
        export = dict(job, job_id=slot['slot_id'] + '-export', output_dir=str(output / 'export-job'),
                      argv=[slot['argv'][0], '--export=on', '--type=text', '--output=' + str(profiles[0])])
        save_new(output / 'export-job.json', export)
        require(job_run(export)['exit_code'] == 0, 'production task export failed')
        tables = list((output / 'profile').rglob('op_summary*.csv'))
    require(len(tables) == 1, 'production task table count differs')
    spans = timeline_spans(tables[0], native_messages(driver / 'stdout.log'), slot['operator'])
    report = {'schema_version': 1, 'operator': slot['operator'], 'case_id': slot['case_id'], 'profiler': roster['tools']['profiler'],
              'sample_spans': spans, 'complete_kernel_tasks': sum(expected_calls.values()),
              'expected_calls': expected_calls, 'repeat': repeat,
              'authority': 'task_partition_only_pending_replay', 'qualified': False}
    report_path = output / 'timeline-report.json'; save_new(report_path, report)
    replay = replay_production_timeline(report_path, qualification_dir=directory, operator=slot['operator'], case_id=slot['case_id'])
    save_new(output / 'timeline-replay.json', replay)
    return {'execution': binding(output / 'job/execution.json'), 'report': binding(report_path), 'replay': binding(output / 'timeline-replay.json')}


def run(roster_path, expected_hash, anchor_path):
    roster_path = Path(roster_path).resolve(strict=True); evidence = Evidence()
    evidence.bind(roster_path, expected_hash)
    anchor = evidence.json(anchor_path)
    require(anchor['schema_version'] == 1 and anchor['purpose'] == 'preregistered_production_measurement_confirmation'
            and anchor['roster'] == {'path': str(roster_path), 'sha256': expected_hash}, 'repository anchor does not bind this campaign')
    require(datetime.fromisoformat(anchor['recorded_at_utc']).timestamp() <= time.time(), 'anchor is dated after campaign start')
    directory = Path(read(roster_path)['qualification_dir']); roster, _, _ = checked_roster(roster_path, evidence, qualification_dir=directory)
    campaign_dir = directory / 'campaign'; campaign_dir.mkdir(exist_ok=False)
    save_new(campaign_dir / 'started.json', {'roster': binding(roster_path), 'anchor': binding(anchor_path), 'started_at': time.time()})
    terminals = {}
    with locks(['host-serial.lock', *[f'device-{i}.lock' for i in range(1, 16)]]):
        for slot in roster['slots']:
            slot_dir = campaign_dir / slot['slot_id']; slot_dir.mkdir(exist_ok=False)
            prerequisite = slot['prerequisite_slot']
            if prerequisite and terminals[prerequisite]['status'] != 'passed':
                terminal = {'slot_id': slot['slot_id'], 'status': 'not_run', 'roster': binding(roster_path),
                            'prerequisite_ref': binding(campaign_dir / prerequisite / 'terminal.json'), 'finished_at': time.time()}
            else:
                started = {'slot': slot, 'roster': binding(roster_path), 'started_at': time.time()}
                save_new(slot_dir / 'started.json', started)
                terminal = {'slot_id': slot['slot_id'], 'roster': binding(roster_path), 'started': binding(slot_dir / 'started.json'), 'status': 'failed'}
                try:
                    checked_roster(roster_path, Evidence(), qualification_dir=directory)
                    if slot['kind'] == 'confirmation':
                        from run_aprof_job import run as job_run
                        job = {'job_id': slot['slot_id'], 'argv': slot['argv'], 'cwd': str(directory),
                               'output_dir': str(slot_dir / 'job'), 'timeout_seconds': 14400, 'environment': slot['environment']}
                        save_new(slot_dir / 'job.json', job); execution = job_run(job)
                        terminal['execution'] = binding(slot_dir / 'job/execution.json')
                        require(execution['exit_code'] == 0, 'full-case collector failed')
                        accepted = confirmation_admission(directory, slot['operator'])
                        save_new(slot_dir / 'admission-replay.json', accepted)
                        terminal['admission_replay'] = binding(slot_dir / 'admission-replay.json')
                    else:
                        terminal.update(timeline_capture(slot, roster, directory))
                    terminal['status'] = 'passed'
                except Exception as error:
                    terminal['error'] = {'type': type(error).__name__, 'message': str(error)}
                    output = Path(slot['output_dir'])
                    actual = slot_dir / 'job/execution.json' if slot['kind'] == 'confirmation' else output / 'job/execution.json'
                    if actual.exists():
                        terminal['execution'] = binding(actual)
                terminal['finished_at'] = time.time()
            save_new(slot_dir / 'terminal.json', terminal); terminals[slot['slot_id']] = terminal
            print(json.dumps({'slot_id': slot['slot_id'], 'status': terminal['status'], 'finished_at': terminal['finished_at']}), flush=True)
    campaign = {'schema_version': 1, 'roster': binding(roster_path), 'anchor': binding(anchor_path), 'finished_at': time.time(),
                'slots': {name: binding(campaign_dir / name / 'terminal.json') for name in ORDER},
                'accepted': all(t['status'] == 'passed' for t in terminals.values()), 'resampling': 'none'}
    save_new(campaign_dir / 'campaign.json', campaign)
    return campaign


def replay_confirmation_campaign(roster_path: Path, *, qualification_dir: Path, source_archive_refs=None) -> dict:
    if source_archive_refs is None:
        evidence = Evidence()
    else:
        from measurement_source_archive import HistoricalEvidence
        evidence = HistoricalEvidence(source_archive_refs, logical_paths=True)
    directory = Path(qualification_dir).resolve(strict=True)
    roster, _, _ = checked_roster(roster_path, evidence, qualification_dir=directory)
    campaign_dir = directory / 'campaign'; campaign = evidence.json(campaign_dir / 'campaign.json')
    if source_archive_refs is not None:
        require(campaign.get('accepted') is False, 'historical source aliases cannot admit a campaign')
    started = evidence.json(campaign_dir / 'started.json'); anchor = evidence.json(started['anchor']['path'])
    evidence.bind(started['anchor']['path'], started['anchor']['sha256'])
    require(anchor['roster'] == campaign['roster'] == started['roster'] == binding(roster_path), 'campaign anchor/roster identity differs')
    require(anchor['schema_version'] == 1 and anchor['purpose'] == 'preregistered_production_measurement_confirmation'
            and roster['created_at'] <= datetime.fromisoformat(anchor['recorded_at_utc']).timestamp() <= started['started_at'],
            'campaign was not anchored before execution')
    require(set(campaign['slots']) == set(ORDER) and campaign['resampling'] == 'none', 'missing terminal slots')
    require({p.name for p in campaign_dir.iterdir() if p.is_dir()} == set(ORDER), 'unknown attempted slot')
    require(roster['created_at'] <= started['started_at'], 'roster was registered after campaign started')
    previous = started['started_at']; terminals = {}; accepted = True
    for slot in roster['slots']:
        slot_id = slot['slot_id']; path = campaign_dir / slot_id / 'terminal.json'
        require(campaign['slots'][slot_id] == binding(path), 'campaign terminal binding differs')
        terminal = evidence.json(path); terminals[slot_id] = terminal
        require(terminal['slot_id'] == slot_id and terminal['roster'] == binding(roster_path), 'wrong slot identity')
        if terminal['status'] == 'not_run':
            prerequisite = slot['prerequisite_slot']
            require(prerequisite is not None and terminals[prerequisite]['status'] != 'passed'
                    and terminal['prerequisite_ref'] == binding(campaign_dir / prerequisite / 'terminal.json')
                    and not (path.parent / 'started.json').exists() and 'execution' not in terminal,
                    'unjustified not-run slot or fabricated execution')
            accepted = False
        else:
            require(terminal['status'] in ('passed', 'failed'), 'unknown terminal status')
            entry = evidence.json(path.parent / 'started.json')
            require(entry['slot'] == slot and entry['roster'] == binding(roster_path)
                    and previous <= entry['started_at'] <= terminal['finished_at'], 'slot order/start identity differs')
            evidence.bind(terminal['started']['path'], terminal['started']['sha256'])
            if 'execution' in terminal:
                evidence.bind(terminal['execution']['path'], terminal['execution']['sha256'])
                execution = evidence.json(terminal['execution']['path'])
                expected_environment = resolved_environment(slot['environment'], directory, slot['operator'], slot['case_id'])
                require(execution['job']['argv'] == slot['argv'] and execution['job']['environment'] == expected_environment,
                        'actual slot command/environment differs')
                require(entry['started_at'] <= datetime.fromisoformat(execution['started_at']).timestamp()
                        <= datetime.fromisoformat(execution['finished_at']).timestamp() <= terminal['finished_at'],
                        'actual job lies outside slot interval')
                for name in ('stdout', 'stderr'):
                    evidence.bind(execution[name]['path'], execution[name]['sha256'])
            if terminal['status'] == 'passed':
                require('execution' in terminal and execution['exit_code'] == 0, 'passed slot has failed/missing execution')
                if slot['kind'] == 'confirmation':
                    actual = confirmation_admission(directory, slot['operator'],
                        historical_evidence=evidence if source_archive_refs is not None else None)
                    evidence.bind(terminal['admission_replay']['path'], terminal['admission_replay']['sha256'])
                    require(read(terminal['admission_replay']['path']) == actual, 'confirmation admission does not replay')
                else:
                    evidence.bind(terminal['report']['path'], terminal['report']['sha256'])
                    actual = replay_production_timeline(Path(terminal['report']['path']), qualification_dir=directory,
                        operator=slot['operator'], case_id=slot['case_id'], source_archive_refs=source_archive_refs)
                    if source_archive_refs is not None:
                        require(actual['eligible_for_publication'] is False, 'historical timeline cannot grant admission')
                        actual = actual['replay']
                    evidence.bind(terminal['replay']['path'], terminal['replay']['sha256'])
                    require(read(terminal['replay']['path']) == actual, 'production timeline replay differs')
            else:
                accepted = False
        require(previous <= terminal['finished_at'], 'terminal time order differs'); previous = terminal['finished_at']
    require(campaign['accepted'] is accepted and campaign['finished_at'] >= previous, 'campaign result does not replay')
    result = {'complete': True, 'accepted': accepted, 'slots': terminals,
              'files': evidence.semantic_files() if source_archive_refs is not None else
                       {p: r['sha256'] for p, r in evidence.files.items()}}
    if source_archive_refs is not None:
        result.update(eligible_for_publication=False, resolved_producers=evidence.resolved_files,
                      source_archives=source_archive_refs)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='action', required=True)
    registration = sub.add_parser('register'); registration.add_argument('--qualification-dir', type=Path, required=True); registration.add_argument('--output', type=Path, required=True)
    execute = sub.add_parser('run'); execute.add_argument('--roster', type=Path, required=True); execute.add_argument('--expected-sha256', required=True); execute.add_argument('--anchor', type=Path, required=True)
    args = parser.parse_args()
    result = register(args.qualification_dir, args.output) if args.action == 'register' else run(args.roster, args.expected_sha256, args.anchor)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
