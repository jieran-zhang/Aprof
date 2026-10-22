"""Six-pair Task screen; no formal admission, build retry or archive."""
import importlib.util
import json
from pathlib import Path
import time

from screen_parser import CASES, PROTOCOL, ROLES, messages, partition, case_summary, summarize

HERE = Path(__file__).resolve().parent
SCREEN_HEADER = HERE.parents[1] / 'benchmarks/cannbench/harness/device_task_screen.h'
spec = importlib.util.spec_from_file_location('screen_rule_adapter', HERE / 'shared_rule_adapter.py')
rule = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rule)
base, bridge = rule.base, rule.bridge
timing, capture = bridge.timing, bridge.profile_capture
file_hash, LocalEvidence = bridge.file_hash, bridge.LocalEvidence
remaining, save = bridge.remaining, bridge.save
_generated, _proof_for = rule.mechanism.generated, rule.mechanism.proof_for


def generated(operator, roles, headers):
    files = _generated(operator, roles, headers)
    name = f'op_host/{operator}.asc'
    host = files[name].decode()
    host = base.exact(host, '#include "device_task_profile.h"',
                      '#include "device_task_profile.h"\n#include "device_task_screen.h"')
    host = base.exact(host, '        const std::string mechanism_role = Arg(argc, argv, "--aprof-mechanism-role");',
        '''        const std::string screen = Arg(argc, argv, "--aprof-screen");
        const std::string mechanism_role = Arg(argc, argv, "--aprof-mechanism-role");
        if ((!screen.empty() && screen != "six_pairs") || (!screen.empty() && !mechanism_role.empty()))
            throw std::invalid_argument("screen mode or combined mechanism mode differs");''')
    host = base.exact(host, 'mechanism_role.empty() ? std::getenv("APROF_SHARED_CYCLE") : "0"',
                      '(mechanism_role.empty() && screen.empty()) ? std::getenv("APROF_SHARED_CYCLE") : "0"')
    host = base.exact(host, '        if (!mechanism_role.empty()) {', f'''        if (!screen.empty()) {{
            task_profile.Start(static_cast<uint32_t>(device));
            aprof::RunTaskScreen(stream, "{operator}", buffers, launch_baseline, launch_candidate, snapshot);
            task_profile.Finish();
        }} else if (!mechanism_role.empty()) {{''')
    files[name] = host.encode()
    files['op_host/device_task_screen.h'] = SCREEN_HEADER.read_bytes()
    return files


def proof_for(*args):
    proof = _proof_for(*args)
    proof['screen_entry'] = {'protocol': PROTOCOL, 'argv': ['--aprof-screen', 'six_pairs'],
        'warmup_per_role': 10, 'prime_order': ['baseline', 'candidate', 'candidate', 'baseline'],
        'prime_repeat': 100, 'pairs': 6, 'repeat': 100, 'tasks_per_case': 1622,
        'task_only': True, 'formal_admission': False}
    for path in (Path(__file__).resolve(), HERE / 'screen_parser.py', SCREEN_HEADER):
        proof['producer_files'][str(path)] = file_hash(path)
    return proof


rule.mechanism.generated = generated
rule.mechanism.proof_for = proof_for
assemble, source_identity = rule.assemble, rule.source_identity
build_once, checked_build = rule.build_once, rule.checked_build
ENABLED_IN_1_0 = False


def collect_screen(assembly, build_receipt, prepared, output, *, physical_device, deadline):
    """One fresh native process per fixed case; caller owns the same hard deadline."""
    remaining(deadline)
    started = time.time()
    output = timing.old.canonical_path(output)
    scratch = output.with_name(output.name + '-scratch')
    proof, build = checked_build(assembly, build_receipt)
    operator = proof['operator']
    if operator not in CASES:
        raise ValueError('only frozen exp/sigmoid screen scope is supported')
    # Derive all argv/attributes/oracles from the original prepared metadata.
    config = rule.task_config(assembly, build_receipt, prepared, scratch,
        run_id='screen-' + output.name, session_id='screen', candidate_id=output.name,
        physical_device=physical_device, profiler='/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof')
    config['expected_case_ids'] = CASES[operator]
    config['cases'] = [c for c in config['cases'] if c['case_id'] in CASES[operator]]
    # The separately registered six-pair screen remains a scalar single-kernel
    # protocol. Formal v5 maps apply only to the subsequent Task collection.
    for role in ROLES:
        config['roles'][role]['launches_per_operator'] = 1
    config['task_profile']['role_kernel_names'] = proof['role_kernel_names']
    if any(output.is_relative_to(config['roles'][r]['source_dir']) for r in ROLES) or output.is_relative_to(config['build']['source_dir']):
        raise ValueError('screen local output cannot change frozen sources')
    output.mkdir(mode=0o700, exist_ok=False)
    local = LocalEvidence(output / 'records')
    sessions, parts, result = [], {}, {'status': 'failed', 'protocol': PROTOCOL,
        'exploration_only': True, 'eligible_for_formal_admission': False, 'gate_projection': {},
        'archive_performed': False, 'error': None}
    try:
        storage_ref = timing.create_profile_storage(scratch, output, local,
            started_at=started, timeout_seconds=remaining(deadline))
        config_ref = local.register_json(config)
        frozen = timing.inventory(config)
        identity = timing.shared.bind_identity(config, frozen, local)
        for name, reference in frozen['producer_files'].items():
            if local.register_artifact(timing.RELEASE / name) != reference:
                raise ValueError('screen package producer changed')
        for path, reference in proof['producer_files'].items():
            if local.register_artifact(path) != reference:
                raise ValueError('screen mechanical producer changed')
        registration = {'protocol': PROTOCOL, 'config_ref': config_ref, 'storage_ref': storage_ref,
            'identity': identity, 'inventory': frozen,
            'case_ids': CASES[operator], 'source_review_ref': local.register_artifact(Path(assembly) / 'source-review.json'),
            'build_receipt_ref': local.register_artifact(build_receipt), 'created_at': time.time(),
            'attempt_policy': 'exactly_once_no_resume_no_resampling', 'exploration_only': True}
        registration_ref = local.register_json(registration)
        with timing.shared.device_lock(physical_device, remaining(deadline)):
            for case in config['cases']:
                remaining(deadline)
                case_id = case['case_id']
                directory = output / f'case-{case_id:02d}'
                directory.mkdir(mode=0o700)
                profile = scratch / directory.name / 'profile'
                profile.parent.mkdir(mode=0o700)
                profile.mkdir(mode=0o700)
                session = {'case_id': case_id, 'started_at': time.time(), 'status': 'failed', 'error': None}
                sessions.append(session)
                try:
                    source_identity(assembly)
                    before = timing.inventory(config, case)
                    expected = dict(frozen, files={p: frozen['files'].get(p) for p in before['files']})
                    if before != expected:
                        raise ValueError('screen identity differs from preregistration')
                    session['identity_before_ref'] = local.register_json(before)
                    argv = timing.shared.expanded(case['command'], directory) + ['--aprof-screen', 'six_pairs']
                    if argv[0] != build['binary']['path']:
                        raise ValueError('screen native binary differs')
                    timing.old._execution(argv, config['build']['source_dir'], directory / 'capture',
                        remaining(deadline), local, {'APROF_TASK_PROFILE_DIR': str(profile)}, session, 'capture')
                    session['capture_files_ref'], captured = timing.profile_ref(profile, local, deadline=deadline, capture=True)
                    if any(Path(p).name.startswith('op_summary') and p.endswith('.csv') for p in captured):
                        raise ValueError('screen capture unexpectedly contains an exported CSV')
                    roots = [p for p in profile.glob('PROF_*') if p.is_dir() and not p.is_symlink()]
                    if len(roots) != 1:
                        raise ValueError('screen capture requires one PROF root')
                    timing.old._execution(timing.export_argv(config, roots[0]), config['build']['source_dir'],
                        directory / 'export', remaining(deadline), local, {}, session, 'export')
                    session['profile_files_ref'], files = timing.profile_ref(profile, local, deadline=deadline)
                    timing.unchanged_captured_profile(captured, files, profile, local)
                    tables = [p for p in files if Path(p).name.startswith('op_summary') and p.endswith('.csv')]
                    if len(tables) != 1:
                        raise ValueError('screen requires one complete Task CSV')
                    session['task_table_ref'] = files[tables[0]]
                    table = local.verify_artifact(session['task_table_ref'])
                    wire = messages((directory / 'capture.stdout.log').read_text())
                    part = partition(table.read_text(), wire, operator=operator, device=config['device'],
                        role_kernel_names=proof['role_kernel_names'], expected_pid=session['capture']['pid'])
                    local.verify_artifact(session['task_table_ref'])
                    session['native_messages_ref'] = local.register_json(wire)
                    session['partition_ref'] = local.register_json(part)
                    session['output_hashes'], session['oracles'] = {}, {}
                    for role in ROLES:
                        paths = timing.shared.expanded(case['output_files'][role], directory)
                        if any(not Path(p).is_relative_to(directory) or Path(p).is_symlink() for p in paths):
                            raise ValueError('screen snapshot escaped its role directory')
                        session['output_hashes'].update({p: local.register_artifact(p) for p in paths})
                        command = timing.shared.expanded(case['verify_commands'][role], directory)
                        timing.old._execution(command, config['build']['source_dir'], directory / (role + '-oracle'),
                            remaining(deadline), local, {}, session['oracles'], role)
                        oracle_path = Path(command[command.index('--result') + 1])
                        oracle = json.loads(oracle_path.read_text())
                        log = (directory / (role + '-oracle.stdout.log')).read_text().strip()
                        if oracle.get('passed') is not True or oracle.get('case_id') != case_id or json.loads(log) != oracle:
                            raise ValueError('screen original output oracle failed')
                        session['oracles'][role]['result_ref'] = local.register_artifact(oracle_path)
                    if any(file_hash(p) != ref for p, ref in session['output_hashes'].items()):
                        raise ValueError('screen oracle mutated role snapshot')
                    source_identity(assembly)
                    after = timing.inventory(config, case)
                    session['identity_after_ref'] = local.register_json(after)
                    if before != after:
                        raise ValueError('screen source/binary/input identity changed')
                    session['summary'] = case_summary(case_id, part)
                    if not session['summary']['passed']:
                        raise ValueError('screen case CV or regression failed; no later case')
                    remaining(deadline)
                    parts[case_id] = part
                    session['status'] = 'passed'
                except BaseException as error:
                    session['error'] = {'type': type(error).__name__, 'message': str(error)}
                    raise
                finally:
                    session['finished_at'] = time.time()
                    save(directory / 'session.json', session)
                    local.register_artifact(directory / 'session.json')
        result['summary'] = summarize(operator, parts)
        if not result['summary']['passed']:
            raise ValueError('screen cross-case geometric mean failed')
        remaining(deadline)
        result['status'] = 'passed'
    except BaseException as error:
        result['error'] = {'type': type(error).__name__, 'message': str(error)}
    finally:
        result.update(started_at=started, finished_at=time.time(), sessions=sessions,
                      registration_ref=locals().get('registration_ref'))
        save(output / 'screen-result.json', result)
        ref = local.register_artifact(output / 'screen-result.json')
        index = local.write_index(output / 'local-evidence-index.json')
    return {'status': result['status'], 'report': str(output / 'screen-result.json'), 'report_ref': ref,
            'local_index': str(index), 'eligible_for_formal_admission': False, 'gate_projection': {}}
