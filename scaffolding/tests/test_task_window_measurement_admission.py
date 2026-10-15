"""Synthetic prospective Task replay, never real measurement qualification."""
from copy import deepcopy
import hashlib
import json

import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.traces import register_json_artifact
from aprof_runtime.measurement_admission import _phase_controls
from aprof_runtime.task_measurement_admission import select_mount
from aprof_runtime.task_window_measurement_admission import (
    PROTOCOL, PRODUCER_FILES, PROFILE_DEPENDENCY_PATHS, HEADER_FILE, SUMMARY_PYTHON, SUMMARY_ENTRY,
    commands, _profile_transition, replay_task_window_measurement_admission, summarize_task_window_raw,
)
from aprof_runtime.task_window_timing import partition_window_tasks, choose_task_repeat
from test_shared_measurement_admission import archive, draft, wire, pilot_wire, RELEASE, ROLES
from test_task_window_timing import rows_for, table


@pytest.fixture
def window_archive(archive):
    store, raw, config, registration, calibration, worker, _, expected, blob = archive
    raw, config, registration, calibration, worker = map(deepcopy, (raw, config, registration, calibration, worker))
    value = lambda item: register_json_artifact(store, item)
    load = lambda ref: json.loads(store.verify_artifact(ref).read_text())
    config['task_profile'] = {'profiler': '/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof',
        'scratch_root': '/synthetic/scratch', 'role_kernel_names': {r: ['exp_kernel'] for r in ROLES}}
    producers = {name: store.register_artifact(RELEASE / name) for name in PRODUCER_FILES}
    dependencies = {path: blob('synthetic dependency ' + path) for path in PROFILE_DEPENDENCY_PATHS}
    registration.update(protocol=PROTOCOL, producer_files=producers,
        profile_dependency_refs=dependencies,
        profiler_ref=dependencies[config['task_profile']['profiler']], task_profile=config['task_profile'],
        repeat_by_case={'1': 100})
    registration['inventory']['producer_files'] = deepcopy(producers)
    registration['inventory']['files'].update(dependencies)
    build_files = {**registration['inventory']['build_sources'], 'op_host/device_task_profile.h': producers[HEADER_FILE]}
    registration['inventory']['build_sources'] = build_files
    registration['identity']['build']['source_ref'] = value({'schema_version': '1.0.0', 'files': build_files})
    mountinfo = '1 0 0:1 / / rw - overlay overlay rw\n'
    registration['profile_storage_ref'] = value({'schema_version': 1, 'mode': 'local_profile_only',
        'scratch_root': '/synthetic/scratch', 'work_root': '/synthetic/results', 'created_at': 1.05,
        'host': raw['host'], 'directory_mode': 0o700, 'mountinfo_ref': blob(mountinfo),
        'scratch_mount': select_mount(mountinfo, '/synthetic/scratch'),
        'persistent_mount': select_mount(mountinfo, '/synthetic/results'),
        'collection_started_at': .1, 'timeout_seconds': 120})
    calibration.update(schema_version=1, protocol=PROTOCOL)
    raw.update(protocol=PROTOCOL, repeat_by_case={'1': 100})
    worker['worker_source_ref'] = producers['skills/ascendc-aprof-profiling/scripts/persistent_oracle.py']
    raw['verifier_worker_ref'] = value(worker)
    pilot = calibration['cases'][0]['pilot']
    all_sessions = [pilot, *raw['sessions']]
    for session in all_sessions:
        mode, cycle, directory = session['mode'], session['cycle'], session['cycle_dir']
        ready, events = pilot_wire(config) if mode == 'pilot' else wire(config, cycle, repeat=100)
        messages = [ready, *(event['message'] for event in events)]
        csv_text = table(rows_for(messages, config['task_profile']['role_kernel_names'], mode, cycle, 100,
                                  pilot_durations=('500',) * 3))
        table_ref = blob(csv_text)
        partition = partition_window_tasks(csv_text=csv_text, messages=messages, config=config,
            mode=mode, cycle=cycle, repeat=100, role_kernel_names=config['task_profile']['role_kernel_names'])
        stdout = blob('\n'.join('APROF_SHARED_TIMING_JSON:' + json.dumps(m) for m in messages) + '\n')
        basename = directory.rsplit('/', 1)[1]
        profile = '/synthetic/scratch/' + basename + '/profile'
        capture = {'argv': [token.replace('{cycle_dir}', directory) for token in config['cases'][0]['command']],
            'cwd': config['build']['source_dir'], 'started_at': session['started_at'] + .1,
            'ended_at': session['started_at'] + .9, 'exit_code': 0, 'error': None,
            'pid': ready['pid'], 'stdout_hash': stdout, 'stderr_hash': blob(''), 'timeout_seconds': 60,
            'environment': {'APROF_SHARED_TIMING': '1', 'APROF_SHARED_CYCLE': str(cycle),
                'APROF_SHARED_MODE': mode, 'APROF_SHARED_REPEAT': '100',
                'APROF_SHARED_COMMANDS': directory + '/commands.txt', 'APROF_TASK_PROFILE_DIR': profile}}
        capture['log_hash'] = value(capture)
        exported = {**capture, 'argv': [SUMMARY_PYTHON, SUMMARY_ENTRY, 'export', 'summary', '-dir',
                    profile + '/PROF_SYNTH', '--format', 'csv'],
            'started_at': session['started_at'] + .91, 'ended_at': session['started_at'] + 1,
            'pid': ready['pid'] + 1000, 'environment': {}, 'stdout_hash': blob('export complete')}
        exported.pop('log_hash'); exported['log_hash'] = value(exported)
        captured = {'PROF_SYNTH/device_0/data/raw': blob('synthetic original raw'),
                    'PROF_SYNTH/mindstudio_profiler_log/collection_device_0.log': blob('collection\n')}
        final = {**captured, 'PROF_SYNTH/mindstudio_profiler_output/op_summary.csv': table_ref}
        final['PROF_SYNTH/mindstudio_profiler_log/collection_device_0.log'] = blob('collection\nexport\n')
        final_ref = value(final)
        session.update(repeat=100, capture=capture, export=exported, commands_ref=blob(commands(mode)),
            task_table_ref=table_ref, native_messages_ref=value(messages), partition_ref=value(partition),
            capture_files_ref=value(captured), profile_files_ref=final_ref,
            control_summary=None if mode == 'pilot' else _phase_controls(partition['values_ns_per_call']),
            identity_before=deepcopy(registration['inventory']), identity_after=deepcopy(registration['inventory']))
        for key in ('ready', 'events', 'execution'):
            session.pop(key)
    selected = choose_task_repeat(load(pilot['partition_ref']))
    calibration['cases'][0] = {'case_id': 1, 'repeat': 100,
        'median_100_calls_ns_decimal': selected['median_100_calls_ns_decimal'], 'pilot': pilot}

    def seal(report_override=None):
        config_ref = value(config)
        registration['config_ref'] = calibration['config_ref'] = config_ref
        for item in calibration['cases']:
            item['case_ref'] = value({key: entry for key, entry in item.items() if key != 'case_ref'})
        registration['calibration_ref'] = value(calibration)
        raw['calibration_ref'] = registration['calibration_ref']
        raw['registration_ref'] = value(registration)
        receipt = {'schema_version': '1.0.0', 'protocol': PROTOCOL,
            **{key: config[key] for key in ('operator', 'run_id', 'session_id', 'candidate_id')},
            'source_hashes': registration['identity']['source_hashes'], 'config_ref': config_ref,
            'registration_ref': raw['registration_ref'], 'raw_ref': value(raw),
            'measurement_report_ref': value(summarize_task_window_raw(raw, config, store)
                                           if report_override is None else report_override)}
        return value(receipt)

    return store, raw, config, registration, calibration, seal, expected, blob, value, load


def test_complete_native_pilot_and_six_cycles_replay_without_publication_authority(window_archive):
    store, raw, config, registration, calibration, seal, expected, *_ = window_archive
    result = replay_task_window_measurement_admission(store, seal(), expected=expected)
    assert result['valid'] and result['eligible_for_publication'] is False
    assert result['repeat_by_case'] == {'1': 100}
    assert len(result['gate_projection']['baseline_samples_ns']) == 30
    assert result['report']['speedup'] == pytest.approx(1)
    assert calibration['cases'][0]['pilot']['control_summary'] is None


def test_replay_uses_only_verify_artifact_reader_contract(window_archive):
    store, _, _, _, _, seal, expected, *_ = window_archive

    class FilesystemReader:
        def verify_artifact(self, reference):
            path = store.object_path(reference)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == reference.removeprefix('sha256:')
            return path

    assert replay_task_window_measurement_admission(FilesystemReader(), seal(), expected=expected)['valid']


@pytest.mark.parametrize('location', ['receipt', 'registration', 'calibration', 'raw'])
@pytest.mark.parametrize('legacy_protocol', ['shared_buffer_msprof_task_window_v1',
    'shared_buffer_msprof_task_window_v2', 'shared_buffer_msprof_task_window_v3'])
def test_legacy_protocol_cannot_enter_current_replay(window_archive, location, legacy_protocol):
    from aprof_runtime.measurement_entry import replay_current_measurement_admission
    store, raw, config, registration, calibration, seal, expected, blob, value, load = window_archive
    assert PROTOCOL == 'shared_buffer_msprof_task_window_v4'
    if location == 'receipt':
        receipt = load(seal())
        receipt['protocol'] = legacy_protocol
        reference = value(receipt)
    else:
        {'registration': registration, 'calibration': calibration, 'raw': raw}[location]['protocol'] = \
            legacy_protocol
        reference = seal()
    with pytest.raises(ContractError):
        replay_current_measurement_admission(store, reference, expected=expected)


@pytest.mark.parametrize('change', ['protocol', 'missing_pilot', 'late_calibration', 'repeat', 'pilot_commands',
    'pilot_pid', 'no_native_profile', 'export_env', 'export_format', 'export_python', 'export_entry',
    'old_reports_field', 'missing_export', 'changed_raw', 'missing_dependency', 'missing_summary_dependency',
    'build_header', 'old_persistence_field', 'wrong_work_root', 'remote_work_mount', 'early_oracle', 'pilot_oracle',
    'total_budget', 'partial', 'report'])
def test_window_replay_rejects_missing_or_substituted_evidence(window_archive, change):
    store, raw, config, registration, calibration, seal, expected, blob, value, load = window_archive
    pilot = calibration['cases'][0]['pilot']
    session = raw['sessions'][0]
    override = None
    if change == 'protocol': raw['protocol'] = 'shared_buffer_msprof_task_v2'
    elif change == 'missing_pilot': calibration['cases'] = []
    elif change == 'late_calibration': calibration['finished_at'] = 4
    elif change == 'repeat': calibration['cases'][0]['repeat'] = 200
    elif change == 'pilot_commands': pilot['commands_ref'] = blob(commands('confirmation'))
    elif change == 'pilot_pid': pilot['capture']['pid'] += 1
    elif change == 'no_native_profile': session['capture']['environment'].pop('APROF_TASK_PROFILE_DIR')
    elif change == 'export_env': session['export']['environment'] = session['capture']['environment']
    elif change == 'export_format': session['export']['argv'][-1] = 'json'
    elif change == 'export_python': session['export']['argv'][0] = '/usr/bin/python3'
    elif change == 'export_entry': session['export']['argv'][1] = '/unfrozen/msprof.py'
    elif change == 'old_reports_field': registration['reports_ref'] = blob('{}')
    elif change == 'missing_export': session['export'] = None
    elif change == 'changed_raw':
        final = load(session['profile_files_ref']); final['PROF_SYNTH/device_0/data/raw'] = blob('other raw')
        session['profile_files_ref'] = value(final)
    elif change == 'missing_dependency': registration['profile_dependency_refs'].pop(PROFILE_DEPENDENCY_PATHS[0])
    elif change == 'missing_summary_dependency': registration['profile_dependency_refs'].pop(SUMMARY_ENTRY)
    elif change == 'build_header':
        files = registration['inventory']['build_sources']; files.pop('op_host/device_task_profile.h')
        registration['identity']['build']['source_ref'] = value({'schema_version': '1.0.0', 'files': files})
    elif change == 'old_persistence_field': session['profile_persistence_ref'] = blob('{}')
    elif change == 'wrong_work_root':
        storage = load(registration['profile_storage_ref']); storage['work_root'] = '/synthetic/other'
        registration['profile_storage_ref'] = value(storage)
    elif change == 'remote_work_mount':
        storage = load(registration['profile_storage_ref'])
        storage['persistent_mount']['filesystem_type'] = 'fuse.juicefs'
        registration['profile_storage_ref'] = value(storage)
    elif change == 'early_oracle':
        session['verifications']['baseline']['started_at'] = session['export']['ended_at'] - .01
    elif change == 'pilot_oracle': pilot['verifications']['candidate']['output_refs'] = {}
    elif change == 'total_budget':
        storage = load(registration['profile_storage_ref']); storage['timeout_seconds'] = 10
        registration['profile_storage_ref'] = value(storage)
    elif change == 'partial': raw.update(complete=False, error={'message': 'real stopped collection'})
    elif change == 'report':
        seal(); override = summarize_task_window_raw(raw, config, store)
        override['gate_projection']['candidate_samples_ns'][0] /= 2
    with pytest.raises(ContractError):
        replay_task_window_measurement_admission(store, seal(override), expected=expected)


@pytest.mark.parametrize('name,after', [
    ('PROF_X/device_0/data/raw', 'original\nextra'),
    ('PROF_X/mindstudio_profiler_log/collection_other.log', 'original\nextra'),
    ('PROF_X/mindstudio_profiler_log/collection_host.log', 'rewritten'),
])
def test_only_original_collection_logs_can_append(window_archive, name, after):
    store, *_, blob, value, load = window_archive
    with pytest.raises(ContractError, match='changed captured'):
        _profile_transition(store, {name: blob('original\n')}, {name: blob(after)})


def test_window_partial_draft_never_retains_gate_samples(window_archive):
    store, raw, config, *_ = window_archive
    raw['complete'] = False
    report = summarize_task_window_raw(raw, config, store)
    assert not report['stable'] and report['reasons']
    assert report['gate_projection']['baseline_samples_ns'] == []
