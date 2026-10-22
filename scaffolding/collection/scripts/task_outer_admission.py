"""Replay online or retained exp/sigmoid evidence; no Teacher/runtime gate.

Post-task replay explicitly supplies a proof-bound source_archive_ref. Logical
original paths remain in commands and receipts; bytes come from the reader.
"""
import json
from pathlib import Path
import sys

import task_screen_bridge as screen
import task_rule_correctness as correctness
from archived_rule_correctness import verify_archived_rule_correctness, verify_mechanical_identity
from task_rule_admission import verify_task_attempt_roster
from task_profile_admission import verify_task_profile_window
from timing_admission import checked_path, digest, file_hash, number, read, require
from screen_parser import CASES, PROTOCOL as SCREEN_PROTOCOL, ROLES, messages, partition, case_summary, summarize
from aprof_runtime.measurement_admission import _config_identity, _registered_identity
from aprof_runtime.task_window_measurement_admission import PROFILE_DEPENDENCY_PATHS

IDENTITY = ('operator', 'run_id', 'candidate_id', 'source_hashes')
MEASUREMENT_IDENTITY = {*IDENTITY, 'session_id', 'measurement_report_ref'}
REMAINING_REQUIREMENTS = [
    'complete Teacher campaign and every registered failed/not-run attempt',
    'trusted generation, independent source review, route and whole-task time deadline with token cost accounting',
    'full runtime GateRequest, graph and raw-profile mechanism/metric gate',
]


class _ReadOnlyLocal:
    """Adapt the old correctness registration check without changing the index."""
    def __init__(self, reader):
        require(isinstance(reader, screen.LocalEvidence),
                'online replay requires LocalEvidence; retained replay requires source_archive_ref')
        self.reader = reader

    def verify_artifact(self, reference):
        return self.reader.verify_artifact(reference)

    def register_artifact(self, path):
        reference = file_hash(Path(path))
        checked_path(self.reader, path, reference)
        return reference


def _reader(reader, source_archive_ref):
    if source_archive_ref is None:
        return reader if isinstance(reader, _ReadOnlyLocal) else _ReadOnlyLocal(reader)
    require(not isinstance(reader, (screen.LocalEvidence, _ReadOnlyLocal)),
            'source_archive_ref is post-task collection evidence, not an online report field')
    return reader


def _logical_path(value):
    path = Path(value)
    require(isinstance(value, str) and path.is_absolute() and path.as_posix() == value
            and '..' not in path.parts and '\0' not in value, 'noncanonical original path')
    return path


def _inventory(reader, config, registration):
    frozen = registration['inventory']
    dependencies = {path: frozen['files'][path] for path in PROFILE_DEPENDENCY_PATHS}
    require(config['task_profile']['profiler'] in dependencies, 'screen profiler dependency missing')
    return _registered_identity(reader, {'source_hashes': registration['identity']['source_hashes']},
        config, dict(registration, producer_files=frozen['producer_files']),
        producer_files=screen.timing.PRODUCER_FILES, extra_files=dependencies)


def _selected_inventory(config, frozen, case):
    paths = {config['build']['binary'], *config['build']['receipt_files'],
             *PROFILE_DEPENDENCY_PATHS, *case['prepared_files']}
    for command in case['verify_commands'].values():
        paths.update(token for index, token in enumerate(command)
                     if index == 0 or ('{cycle_dir}' not in token and Path(token).suffix in {'.py', '.sh'}))
    return dict(frozen, files={path: frozen['files'][path] for path in paths})


def _execution(reader, embedded, prefix, argv, cwd, environment, lower, upper):
    reference = embedded['log_hash']
    raw = read(reader, reference)
    require({k: v for k, v in embedded.items() if k != 'result_ref'} == dict(raw, log_hash=reference),
            'screen embedded execution differs from its actual receipt')
    checked_path(reader, str(prefix) + '.execution.json', reference)
    require(raw['argv'] == argv and raw['cwd'] == str(cwd) and raw['environment'] == environment
            and raw['exit_code'] == 0 and raw['error'] is None,
            'screen actual argv/environment/exit differs')
    require(lower <= number(raw['started_at']) <= number(raw['ended_at']) <= upper
            and 0 < number(raw['timeout_seconds'])
            and raw['ended_at'] - raw['started_at'] <= raw['timeout_seconds']
            and type(raw['pid']) is int and raw['pid'] > 0,
            'screen execution chronology/timeout/PID differs')
    for stream in ('stdout', 'stderr'):
        checked_path(reader, str(prefix) + '.' + stream + '.log', raw[stream + '_hash'])
    return raw


def _profile(reader, reference, directory):
    files = read(reader, reference)
    require(isinstance(files, dict) and files, 'screen complete profile inventory missing')
    for name, digest in files.items():
        path = Path(name)
        require(isinstance(name, str) and '\0' not in name and not path.is_absolute()
                and path.as_posix() == name and not {'.', '..'}.intersection(path.parts)
                and all(parent.as_posix() not in files for parent in path.parents if parent != Path('.')),
                'screen profile file roster is unsafe')
        checked_path(reader, directory / name, digest)
    if directory.exists() or directory.is_symlink():
        require({p.relative_to(directory).as_posix() for p in screen.timing.old.safe_files(directory)} == set(files),
                'screen complete local profile roster differs')
    return files


def _screen_config(reader, config, proof, build, build_path, prepared, output, scratch, plan, inputs):
    # Acquisition task_config() rejects an already-created scratch directory.
    # Replay uses its same mechanical argv/oracle builders on frozen metadata.
    base = screen.base
    for path in [*config['build']['receipt_files'], config['build']['source_dir'], config['build']['binary'],
                 *(config['roles'][role]['source_dir'] for role in ROLES), plan['profiler']]:
        _logical_path(path)
    require(all(config[k] == v for k, v in dict(operator=plan['operator'], run_id='screen-' + output.name,
        session_id='screen', candidate_id=output.name, device=0, physical_device=plan['physical_device'],
        expected_case_ids=plan['case_ids']).items())
        and config['task_profile'] == {'profiler': plan['profiler'], 'scratch_root': str(scratch),
                                      'role_kernel_names': proof['role_kernel_names']}, 'screen config identity differs')
    assembly = Path(config['build']['source_dir']).parent
    require(config['roles'] == {r: {'source_dir': proof['roles'][r]['path'], 'symbol': 'launch_' + r,
                                   'launches_per_operator': 1} for r in ROLES}
        and config['build'] == {'source_dir': str(assembly / 'source'), 'binary': build['binary']['path'],
            'receipt_files': [str(build_path), str(assembly / 'source-review.json'), build['attempt_ref']['path']]},
        'screen role/build config differs')
    for case in config['cases']:
        metadata_path = prepared / f"case_{case['case_id']:02d}/metadata.json"
        metadata = json.loads(checked_path(reader, metadata_path, inputs[str(metadata_path)]).read_text())
        checked_path(reader, metadata['input'], inputs[metadata['input']])
        outputs = {r: {'output': '{cycle_dir}/' + r + '-output.bin'} for r in ROLES}
        absolute = {r: {'output': outputs[r]['output'].replace('{cycle_dir}', '/APROF_CYCLE')} for r in ROLES}
        command = base.case_command(plan['operator'], build['binary']['path'], metadata, 0, absolute)
        routing = {absolute[r]['output']: outputs[r]['output'] for r in ROLES}
        wanted = {'case_id': case['case_id'], 'workload': base.old.json_contract({k: v for k, v in metadata.items() if k != 'output'}),
            'prepared_files': [str(metadata_path), metadata['input']],
            'command': [routing.get(v, v) for v in command],
            'verify_commands': {r: base.oracle_command(plan['operator'], assembly / 'source', Path(sys.executable).resolve(),
                metadata_path, outputs[r], '{cycle_dir}/' + r + '-result.json') for r in ROLES},
            'output_files': {r: [outputs[r]['output']] for r in ROLES}}
        require(case == wanted, 'screen frozen configuration/command/input differs')


def verify_task_screen(reader, report_ref, *, protocol_ref, expected, window, source_archive_ref=None):
    """Replay six real screen sessions using the existing Task parser/oracles.

    screen_plan_ref fixes schema_version/protocol/operator/case_ids/repeat/pairs,
    prepared_dir/output_dir/physical_device/profiler. It is an outer pre-launch
    plan, distinct from the screen collector's later registration/config.
    """
    reader = _reader(reader, source_archive_ref)
    protocol, result = read(reader, protocol_ref), read(reader, report_ref)
    require(all(protocol[k] == expected[k] for k in IDENTITY), 'screen outer identity differs')
    plan = read(reader, protocol['screen_plan_ref'])
    require(set(plan) == {'schema_version', 'protocol', 'operator', 'case_ids', 'repeat', 'pairs',
                         'prepared_dir', 'output_dir', 'physical_device', 'profiler'}
            and plan['schema_version'] == 1 and plan['protocol'] == SCREEN_PROTOCOL
            and plan['operator'] == expected['operator'] and plan['case_ids'] == CASES[expected['operator']]
            and plan['repeat'] == 100 and plan['pairs'] == 6, 'frozen screen plan differs')
    output = _logical_path(plan['output_dir'])
    prepared = _logical_path(plan['prepared_dir'])
    scratch = output.with_name(output.name + '-scratch')
    checked_path(reader, output / 'screen-result.json', report_ref)
    require(result['protocol'] == SCREEN_PROTOCOL and result['status'] == 'passed' and result['error'] is None
            and result['exploration_only'] is True and result['eligible_for_formal_admission'] is False
            and result['gate_projection'] == {} and result['archive_performed'] is False
            and window[0] <= number(result['started_at']) <= number(result['finished_at']) <= window[1],
            'screen result status/authority/window differs')
    registration = read(reader, result['registration_ref'])
    config = read(reader, registration['config_ref'])
    _config_identity(reader, dict(config, config_ref=registration['config_ref']), extra_fields=('task_profile',))
    build_path = _logical_path(config['build']['receipt_files'][0])
    checked_path(reader, build_path, registration['build_receipt_ref'])
    assembly = _logical_path(config['build']['source_dir']).parent
    if source_archive_ref is None:
        proof, build = screen.checked_build(assembly, build_path)
    else:
        proof, build = read(reader, registration['source_review_ref']), read(reader, registration['build_receipt_ref'])
        verify_mechanical_identity(reader, proof, build, registration, source_archive_ref)
    require(registration['source_review_ref'] == protocol['source_review_ref']
            and checked_path(reader, assembly / 'source-review.json', protocol['source_review_ref'])
            and proof['operator'] == expected['operator']
            and protocol['binary_hashes'] == {r: build['binary']['sha256'] for r in ROLES}
            and {r: proof['historical_source_binding']['roles'][r]['sha256'] for r in ROLES} == expected['source_hashes'],
            'screen source/build/original-role binding differs')
    inputs = read(reader, protocol['input_inventory_ref'])
    _screen_config(reader, config, proof, build, build_path, prepared, output, scratch, plan, inputs)
    frozen = _inventory(reader, config, registration)
    require(frozen['sources'] == {role: proof['roles'][role]['files'] for role in ROLES}
            and frozen['build_sources'] == proof['adapted_files'], 'screen frozen source/build tree differs')
    if source_archive_ref is None:
        require(screen.timing.inventory(config) == frozen, 'screen live source/build/input inventory changed')
    require(registration['inventory'] == frozen and registration['protocol'] == SCREEN_PROTOCOL
            and registration['case_ids'] == plan['case_ids'] and registration['exploration_only'] is True
            and registration['attempt_policy'] == 'exactly_once_no_resume_no_resampling'
            and result['started_at'] <= number(registration['created_at']) <= result['finished_at'],
            'screen preregistration/current frozen sources differ')
    for path, reference in {**frozen['files'], **proof['producer_files']}.items():
        checked_path(reader, path, reference)
    for case in config['cases']:
        require(all(inputs.get(path) == frozen['files'][path] for path in case['prepared_files']),
                'screen inputs differ from outer frozen inventory')
    identity = registration['identity']
    require(identity['build']['binary_ref'] == build['binary']['sha256'], 'screen registered binary differs')
    for role in ROLES:
        require(read(reader, identity['source_hashes'][role]) == read(reader, expected['source_hashes'][role]) ==
                {'schema_version': '1.0.0', 'files': frozen['sources'][role]}, 'screen source bundle differs')
    require(read(reader, identity['build']['source_ref']) ==
            {'schema_version': '1.0.0', 'files': frozen['build_sources']}, 'screen build source bundle differs')
    storage = read(reader, registration['storage_ref'])
    require(storage['mode'] == 'local_profile_only' and storage['work_root'] == str(output)
            and storage['scratch_root'] == str(scratch) and storage['collection_started_at'] == result['started_at'],
            'screen local storage differs')
    require([s['case_id'] for s in result['sessions']] == plan['case_ids'], 'screen session roster differs')
    previous, parts, pids = registration['created_at'], {}, set()
    for case, session in zip(config['cases'], result['sessions'], strict=True):
        cid = case['case_id']; directory = output / f'case-{cid:02d}'; profile = scratch / directory.name / 'profile'
        # The original collector saved this exact serialization and registered it.
        session_ref = digest((json.dumps(session, sort_keys=True, indent=2, allow_nan=False) + '\n').encode())
        require(read(reader, session_ref) == session
                and session['status'] == 'passed' and session['error'] is None
                and previous <= number(session['started_at']) <= number(session['finished_at']) <= result['finished_at'],
                'screen session receipt/status/order differs')
        before = read(reader, session['identity_before_ref'])
        selected = _selected_inventory(config, frozen, case)
        if source_archive_ref is None:
            require(screen.timing.inventory(config, case) == selected, 'screen live session input/source changed')
        require(before == selected == read(reader, session['identity_after_ref'])
                and selected == dict(frozen, files={p: frozen['files'].get(p) for p in selected['files']}),
                'screen input/source before/after differs')
        cap = _execution(reader, session['capture'], directory / 'capture',
            screen.timing.shared.expanded(case['command'], directory) + ['--aprof-screen', 'six_pairs'],
            config['build']['source_dir'], {'APROF_TASK_PROFILE_DIR': str(profile)},
            session['started_at'], session['finished_at'])
        require(cap['pid'] not in pids, 'screen reused native PID'); pids.add(cap['pid'])
        # Capture snapshots contain pre-export logs; current live logs may have grown.
        captured = read(reader, session['capture_files_ref'])
        final = _profile(reader, session['profile_files_ref'], profile)
        require(isinstance(captured, dict) and captured and not any(Path(p).name.startswith('op_summary')
                and p.endswith('.csv') for p in captured), 'screen capture already contains Task export')
        for name, reference in captured.items():
            require(name in final, 'screen export removed captured bytes')
            before_path = reader.verify_artifact(reference)
            if final[name] != reference:
                require(screen.timing.COLLECTION_LOG.fullmatch(name) is not None,
                        'screen export changed non-log captured bytes')
                with before_path.open('rb') as source, reader.verify_artifact(final[name]).open('rb') as after:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        require(after.read(len(chunk)) == chunk, 'screen collection log prefix changed')
        roots = {Path(name).parts[0] for name in final}
        require(len(roots) == 1 and next(iter(roots)).startswith('PROF_'), 'screen PROF roster differs')
        exported = _execution(reader, session['export'], directory / 'export',
            screen.timing.export_argv(config, profile / next(iter(roots))), config['build']['source_dir'], {},
            cap['ended_at'], session['finished_at'])
        tables = [name for name in final if Path(name).name.startswith('op_summary') and name.endswith('.csv')]
        require(len(tables) == 1 and final[tables[0]] == session['task_table_ref'], 'screen Task table binding differs')
        wire = messages(reader.verify_artifact(cap['stdout_hash']).read_text())
        require(wire == read(reader, session['native_messages_ref']), 'screen stdout/message binding differs')
        part = partition(reader.verify_artifact(session['task_table_ref']).read_text(), wire,
            operator=expected['operator'], device=config['device'], role_kernel_names=proof['role_kernel_names'],
            expected_pid=cap['pid'])
        require(part == read(reader, session['partition_ref']), 'screen partition differs from full Task CSV')
        require(set(session['oracles']) == set(ROLES), 'screen needs both original oracles')
        paths = [p for r in ROLES for p in screen.timing.shared.expanded(case['output_files'][r], directory)]
        require(set(session['output_hashes']) == set(paths), 'screen output roster differs')
        clock = exported['ended_at']
        for role in ROLES:
            command = screen.timing.shared.expanded(case['verify_commands'][role], directory)
            oracle = _execution(reader, session['oracles'][role], directory / (role + '-oracle'), command,
                config['build']['source_dir'], {}, clock, session['finished_at'])
            result_ref = session['oracles'][role]['result_ref']
            checked_path(reader, command[command.index('--result') + 1], result_ref)
            verdict = read(reader, result_ref)
            require(verdict.get('passed') is True and verdict.get('case_id') == cid
                    and json.loads(reader.verify_artifact(oracle['stdout_hash']).read_text().strip()) == verdict,
                    'screen original oracle result/stdout differs')
            clock = oracle['ended_at']
        for path, reference in session['output_hashes'].items():
            content = checked_path(reader, path, reference)
            require(content.stat().st_size == case['workload']['numel'] *
                    (4 if case['workload']['dtype'] == 'float32' else 2), 'screen full output length differs')
        row = case_summary(cid, part)
        require(row == session['summary'] and row['passed'], 'screen case statistics differ or fail')
        parts[cid], previous = part, session['finished_at']
    summary = summarize(expected['operator'], parts)
    require(summary == result['summary'] and summary['passed'], 'screen complete statistics differ or fail')
    return {'valid': True, 'report_ref': report_ref, 'registration_ref': result['registration_ref'],
            'config_ref': registration['config_ref'], 'screen_plan_ref': protocol['screen_plan_ref'],
            'case_ids': plan['case_ids'], 'task_count': sum(p['task_count'] for p in parts.values()),
            'admission_authority': False, 'summary': summary}


def verify_task_rule_admission(reader, report_ref, *, expected, measurement_expected, source_archive_ref=None):
    """Verify components; caller still owns all REMAINING_REQUIREMENTS.

    source_archive_ref is separate post-task trace-collection evidence. It never
    changes the original online report or makes a failed execution admissible.

    expected.execution_ref MUST come from the trusted dispatcher after real exit.
    Named report references must occur in the verified stage roster. The derived
    outer protocol fixes task_config_ref/profile_configs before device stages.
    """
    reader = _reader(reader, source_archive_ref)
    require(set(measurement_expected) == MEASUREMENT_IDENTITY
            and all(measurement_expected[k] == expected[k] for k in IDENTITY if k != 'source_hashes'),
            'Task measurement identity differs from dispatcher identity')
    require(set(measurement_expected['source_hashes']) == set(expected['source_hashes']) == set(ROLES)
            and all(read(reader, measurement_expected['source_hashes'][r]) == read(reader, expected['source_hashes'][r])
                    for r in ROLES), 'Task and original source bundle contents differ')
    roster = verify_task_attempt_roster(reader, report_ref, expected=expected)
    report, protocol = read(reader, report_ref), read(reader, expected['protocol_ref'])
    windows, evidence = roster['stage_windows'], roster['stage_evidence']
    bindings = {'correctness': 'correctness_report_ref', 'boundary': 'boundary_report_ref',
        'screen': 'screen_report_ref', 'task_measurement': 'measurement_admission_ref',
        'profile': 'mechanism_report_ref'}
    for stage, key in bindings.items():
        require(report.get(key) in evidence[stage], 'stage does not bind ' + key)
    common = {key: expected[key] for key in IDENTITY}
    checks = {}
    for stage in ('correctness', 'boundary'):
        reference = report[bindings[stage]]
        require(read(reader, reference).get('kind') == 'task_rule_' + stage, 'correctness stage report was substituted')
        if source_archive_ref is None:
            checks[stage] = correctness.verify_rule_correctness(reader, reference,
                protocol_ref=expected['protocol_ref'], expected=common, window=windows[stage])
        else:
            checks[stage] = verify_archived_rule_correctness(reader, reference,
                protocol_ref=expected['protocol_ref'], expected=common, window=windows[stage],
                source_archive_ref=source_archive_ref)
    checks['screen'] = verify_task_screen(reader, report['screen_report_ref'],
        protocol_ref=expected['protocol_ref'], expected=common, window=windows['screen'],
        source_archive_ref=source_archive_ref)
    # This existing helper performs the one complete current runtime replay; its
    # returned refs then join the formal stage and frozen post-build config.
    checks['task_and_profile'] = verify_task_profile_window(reader, report['mechanism_report_ref'],
        window=windows['profile'], measurement_admission_ref=report['measurement_admission_ref'],
        expected=measurement_expected, profile_configs=protocol['profile_configs'])
    task = checks['task_and_profile']; completion = read(reader, task['completion_ref'])
    require(task['config_ref'] == protocol['task_config_ref'], 'formal Task config differs from frozen protocol')
    config = read(reader, task['config_ref'])
    screen_config = read(reader, checks['screen']['config_ref'])
    require(config['expected_case_ids'] == list(range(1, 21))
            and [c['case_id'] for c in config['cases']] == list(range(1, 21))
            and config['build'] == screen_config['build']
            and protocol['binary_hashes'] == {r: task['build']['binary_ref'] for r in ROLES},
            'formal Task needs all 20 cases and the same single screen/correctness build')
    task_registration = read(reader, task['task_registration_ref'])
    frozen_inputs = read(reader, protocol['input_inventory_ref'])
    require(all(frozen_inputs.get(path) == reference
                for case in task_registration['identity']['cases'].values()
                for path, reference in case['prepared_files'].items()),
            'formal Task prepared input differs from the outer frozen inventory')
    require(windows['task_measurement'][0] <= number(completion['started_at'])
            <= number(completion['finished_at']) <= windows['task_measurement'][1],
            'Task completion is outside its registered stage')
    required = {task[k] for k in ('completion_ref', 'proof_ref', 'config_ref', 'task_registration_ref')}
    required.add(measurement_expected['measurement_report_ref'])
    require(required <= set(evidence['task_measurement']), 'formal stage omitted actual Task replay bindings')
    require(all(checks[k].get('passed') is True for k in ('correctness', 'boundary', 'task_and_profile'))
            and checks['screen'].get('valid') is True, 'component verifier did not validate its evidence')
    return {'valid': True, 'scope': ('online_exp_sigmoid_task_components' if source_archive_ref is None
                                    else 'retained_exp_sigmoid_task_components'), 'source_archive_ref': source_archive_ref, 'report_ref': report_ref,
            'protocol_ref': expected['protocol_ref'], 'execution_ref': expected['execution_ref'],
            'qualification_registration_ref': expected['qualification_registration_ref'],
            'measurement_expected': measurement_expected, 'original_source_hashes': expected['source_hashes'],
            'roster': roster, 'checks': checks,
            'admission_authority': False, 'eligible_for_publication': False,
            'remaining_requirements': list(REMAINING_REQUIREMENTS)}
