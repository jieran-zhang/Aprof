"""Local helpers only. No controller dispatch, hardware qualification or archive.

The existing outer controller retains its absolute deadline and model/reviewer
budgets. It owns process-tree cancellation. These helpers never reset that clock.
"""
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
import time

# A private adapter permits the frozen-rule/screen branches to specialize it
# without changing the public validation adapter in this Python process.
_spec = importlib.util.spec_from_file_location('local_mechanism_adapter',
    Path(__file__).resolve().with_name('shared_mechanism_adapter.py'))
adapter = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(adapter)
RELEASE = adapter.base.selected_runtime()
sys.path.insert(0, str(RELEASE / 'skills/ascendc-aprof-profiling/scripts'))
from aprof_runtime.contracts import Context, GateRequest
from aprof_runtime.episodes import finalize_episodes
from aprof_runtime.jsonio import file_hash, to_primitive
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.profile_evidence import load_capture_manifest, normalize_profile
from normalize_profile import expand_specs
import device_task_window_timing as timing
import profile_capture
adapter.base.selected_runtime()
EXPECTED_PROTOCOL = {'0.5.1': 'shared_buffer_msprof_task_window_v4',
                     '1.0.0': 'shared_buffer_msprof_task_window_v5',
                     '1.0.1': 'shared_buffer_msprof_task_window_v5'}[RELEASE.name]
if timing.PROTOCOL != EXPECTED_PROTOCOL:
    raise ValueError('selected release does not provide its declared Task-window protocol')
from eval_candidate_evidence import verify_candidate_evidence, verify_blind_source_review

ENABLED_IN_1_0 = False
ROLES = adapter.ROLES


def remaining(deadline):
    value = deadline - time.monotonic()
    if not math.isfinite(value) or value <= 0:
        raise TimeoutError('original controller deadline expired')
    return value


def save(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def _check_build_route(route):
    """Check the recorded provenance shape; the outer verifier checks authority."""
    if not isinstance(route, dict):
        raise ValueError('combined build route must be a graph pointer or explicit exploration anchor')
    if set(route) == {'path', 'sha256'}:
        path, reference = route['path'], route['sha256']
        if (isinstance(path, str) and Path(path).is_absolute() and Path(path).as_posix() == path
                and '..' not in Path(path).parts and '\0' not in path
                and isinstance(reference, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', reference)):
            return
    if (set(route) == {'mode', 'anchor_ref'} and route['mode'] == 'exploration'
            and isinstance(route['anchor_ref'], str)
            and re.fullmatch(r'sha256:[0-9a-f]{64}', route['anchor_ref'])):
        return
    raise ValueError('combined build route must be a graph pointer or explicit exploration anchor')


def checked_build(assembly, receipt):
    assembly = Path(assembly).absolute()
    proof = adapter.source_identity(assembly)
    build = json.loads(Path(receipt).read_text())
    binary = assembly / 'build' / proof['operator']
    attempt_path = assembly / 'build-attempt.json'
    source_hash = file_hash(assembly / 'source-review.json')
    records = build.get('commands')
    if (build['status'] != 'passed' or build.get('error') is not None
            or build['source_review_hash'] != source_hash
            or build['binary']['path'] != str(binary) or binary.resolve() != binary
            or build['binary']['sha256'] != file_hash(binary)
            or build.get('attempt_ref') != {'path': str(attempt_path), 'sha256': file_hash(attempt_path)}
            or not isinstance(records, list) or len(records) != 2):
        raise ValueError('combined build no longer matches mechanical source review')
    attempt = json.loads(attempt_path.read_text())
    if set(attempt) != {'source_review_hash', 'independent_review', 'route'} or attempt['source_review_hash'] != source_hash:
        raise ValueError('combined build attempt differs from reviewed assembly')
    _check_build_route(attempt['route'])
    for stage, record in zip(('configure', 'build'), records, strict=True):
        if (record['argv'] != proof['commands'][stage] or record.get('cwd') != str(assembly / 'source')
                or type(record['exit_status']) is not int or record['exit_status'] != 0
                or record['error'] is not None):
            raise ValueError('combined build command differs from the one trusted configure/compile')
    import sdk_build_evidence
    sdk_build_evidence.verify(build, proof)
    return proof, build


def build_once(assembly, workspace, commands, *, model, baseline_qualification):
    """Trusted configure + one compile; existing blind review is still mandatory."""
    commands.remaining()
    review = verify_candidate_evidence(workspace, RELEASE, model=model,
                                      baseline_qualification=baseline_qualification)
    if not review['accepted']:
        raise ValueError('independent source review failed or remained unknown')
    proof = adapter.source_identity(assembly)
    return _build_reviewed_once(assembly, workspace, commands, proof, review, review['route_receipt_ref'])


def build_teacher_rule_once(assembly, workspace, commands, *, model, local, anchor_ref):
    """Build one explicitly anchored fixed-rule exploration; no route/admission."""
    commands.remaining()
    if not isinstance(local, LocalEvidence):
        raise ValueError('Teacher rule build requires task-local evidence')
    if not isinstance(model, dict) or any(not isinstance(model.get(k), str) or not model[k].strip()
                                          for k in ('name', 'reasoning_effort')):
        raise ValueError('Teacher rule build requires the frozen reviewer model and effort')
    anchor = json.loads(local.verify_artifact(anchor_ref).read_text())
    proof = adapter.source_identity(assembly)
    if (anchor.get('schema_version') != 1 or anchor.get('purpose') != 'promotion'
            or anchor.get('protocol') != 'rule_task_admission_v1'
            or anchor.get('task_protocol') != timing.PROTOCOL
            or anchor.get('operator') not in {'exp', 'sigmoid'}
            or anchor['operator'] != proof['operator']):
        raise ValueError('Teacher rule build anchor protocol/purpose/operator differs')
    sources = {role: proof['historical_source_binding']['roles'][role]['sha256'] for role in ROLES}
    if anchor.get('source_hashes') != sources:
        raise ValueError('Teacher rule build anchor differs from the frozen role sources')
    for reference in sources.values():
        local.verify_artifact(reference)
    review_ref = file_hash(Path(assembly) / 'source-review.json')
    if anchor.get('source_review_ref') != review_ref:
        raise ValueError('Teacher rule build anchor differs from the mechanical source proof')
    local.verify_artifact(review_ref)
    review = verify_blind_source_review(workspace, RELEASE, model=model)
    if review['accepted'] is not True:
        raise ValueError('independent source review failed or remained unknown')
    import sdk_build_evidence as sdk_build
    contract = sdk_build.contract_from_review(review['source_review_ref'])
    binding = None
    if 'sdk_resource_evidence' in contract:
        plan = json.loads(local.verify_artifact(anchor['controller_plan_ref']).read_text())
        binding = plan.get('sdk_build_binding_ref')
        if binding is None:
            raise ValueError('SDK evidence contract lacks preregistered build binding')
        sdk_build.verify_binding(sdk_build.value(binding), live=True)
        if sdk_build.value(binding)['contract_ref'] != review['source_review']['contract_ref']:
            raise ValueError('preregistered SDK contract differs from actual blind review')
    return _build_reviewed_once(assembly, workspace, commands, proof, review,
                               {'mode': 'exploration', 'anchor_ref': anchor_ref}, sdk_binding=binding, local=local)


def _build_reviewed_once(assembly, workspace, commands, proof, review, route, *, sdk_binding=None, local=None):
    _check_build_route(route)
    for role in ROLES:
        if Path(proof['roles'][role]['path']) != (Path(workspace) / role).resolve():
            raise ValueError('assembly roles differ from independently reviewed workspace')
    assembly = Path(assembly).absolute()
    save(assembly / 'build-attempt.json', {'source_review_hash': file_hash(assembly / 'source-review.json'),
        'independent_review': review['source_review_ref'], 'route': route})
    records, status, error, sdk_receipt = [], 'failed', None, None
    import sdk_build_evidence as sdk_build
    try:
        for stage in ('configure', 'build'):
            commands.remaining()
            options = {}
            if sdk_binding is not None:
                sdk_build.verify_binding(sdk_build.value(sdk_binding), live=True)
                options['environment'] = sdk_build.value(sdk_binding)['environment']
            record = commands.run(stage, proof['commands'][stage], assembly / 'source', **options)
            records.append(record)
            if record['exit_status'] != 0 or record['error']:
                raise RuntimeError('combined ' + stage + ' failed; no retry')
        adapter.source_identity(assembly)
        binary = assembly / 'build' / proof['operator']
        binding = {'path': str(binary), 'sha256': file_hash(binary)}
        if sdk_binding is not None:
            sdk_receipt = sdk_build.finish(local, sdk_binding, assembly, proof['operator'])
        commands.remaining()
        status = 'passed'
        return assembly / 'build-receipt.json'
    except BaseException as exc:
        error = {'type': type(exc).__name__, 'message': str(exc)}
        raise
    finally:
        save(assembly / 'build-receipt.json', {'status': status, 'error': error,
            'attempt_ref': {'path': str(assembly / 'build-attempt.json'), 'sha256': file_hash(assembly / 'build-attempt.json')},
            'source_review_hash': file_hash(assembly / 'source-review.json'), 'commands': records,
            'binary': binding if status == 'passed' else None,
            **({'sdk_build_ref': sdk_receipt} if sdk_receipt is not None else {})})


def task_config(assembly, build_receipt, prepared, scratch, *, run_id, session_id, candidate_id,
                physical_device, profiler):
    """All 20 cases, two complete outputs for DQ, unchanged per-case pilot rule."""
    proof, build = checked_build(assembly, build_receipt)
    op, binary = proof['operator'], build['binary']['path']
    source = Path(assembly) / 'source'
    config = {'schema_version': '1.0.0', 'operator': op, 'run_id': run_id, 'session_id': session_id,
        'candidate_id': candidate_id, 'device': 0, 'physical_device': physical_device,
        'expected_case_ids': list(range(1, 21)),
        'roles': {r: {'source_dir': proof['roles'][r]['path'], 'symbol': 'launch_' + r,
                      'launches_per_operator': 1} for r in ROLES},
        'build': {'source_dir': str(source), 'binary': binary,
                  'receipt_files': [str(build_receipt), str(Path(assembly) / 'source-review.json'),
                                    build['attempt_ref']['path']]},
        'task_profile': {'profiler': str(profiler), 'scratch_root': str(scratch),
                         'role_kernel_names': proof['role_kernel_names']}, 'cases': []}
    for case_id in config['expected_case_ids']:
        metadata_path = Path(prepared) / f'case_{case_id:02d}/metadata.json'
        metadata = json.loads(metadata_path.read_text())
        outputs = {r: {key: '{cycle_dir}/' + r + '-' + key + '.bin' for key in proof['output_keys']} for r in ROLES}
        # Existing assembler requires absolute paths; substitute an absolute
        # placeholder only while deriving the command, then restore the token.
        absolute = {r: {k: v.replace('{cycle_dir}', '/APROF_CYCLE') for k, v in files.items()} for r, files in outputs.items()}
        command = adapter.base.case_command(op, binary, metadata, 0, absolute)
        routing = {absolute[r][k]: outputs[r][k] for r in ROLES for k in outputs[r]}
        command = [routing.get(v, v) for v in command]
        inputs = []
        def visit(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key not in proof['output_keys']: visit(child)
            elif isinstance(value, list):
                for child in value: visit(child)
            elif isinstance(value, str) and Path(value).is_absolute() and Path(value).is_file():
                inputs.append(value)
        visit(metadata)
        config['cases'].append({'case_id': case_id,
            'workload': adapter.base.old.json_contract({k: v for k, v in metadata.items() if k not in proof['output_keys']}),
            'prepared_files': [str(metadata_path), *sorted(set(inputs))], 'command': command,
            'verify_commands': {r: adapter.base.oracle_command(op, source, Path(sys.executable).resolve(), metadata_path,
                outputs[r], '{cycle_dir}/' + r + '-result.json') for r in ROLES},
            'output_files': {r: list(outputs[r].values()) for r in ROLES}})
    if timing.PROTOCOL.endswith('_v5'):
        for role in ROLES:
            config['roles'][role]['launches_per_operator'] = {
                str(cid): 1 for cid in config['expected_case_ids']}
            config['task_profile']['role_kernel_names'][role] = {
                str(cid): list(proof['role_kernel_names'][role]) for cid in config['expected_case_ids']}
    return timing.config_value(config)


def merge_index(local, path):
    """Full-read existing files into one local index; no bytes copied or archived."""
    other = LocalEvidence.from_index(path)
    for reference in json.loads(Path(path).read_text())['artifacts']:
        if local.register_artifact(other.verify_artifact(reference)) != reference:
            raise ValueError('local artifact changed while combining indexes')


def collect_task(config, output, local, *, deadline, budget_binding=None):
    result = timing.collect_local(config, output, timeout_seconds=remaining(deadline),
        deadline_monotonic=deadline, budget_binding=budget_binding, budget_reader=local)
    merge_index(local, result['local_index'])
    remaining(deadline)
    if result['status'] != 'passed':
        raise RuntimeError('local Task measurement failed; no resampling')
    return result


def verify_mechanism_oracle(local, record, result_path, case_id):
    """Read the verifier verdict from stdout; stderr remains separate evidence."""
    oracle = json.loads(Path(result_path).read_text())
    stdout = json.loads(local.verify_artifact(record['stdout_hash']).read_text())
    if oracle.get('passed') is not True or oracle.get('case_id') != case_id or stdout != oracle:
        raise ValueError('mechanism complete output oracle failed or differs from stdout')
    return oracle


def capture_mechanism(assembly, build_receipt, task_config_value, choice, specs, output, local, *, deadline, budget_binding=None):
    proof, build = checked_build(assembly, build_receipt)
    if (set(choice) != {'case_id', 'kernel', 'metric', 'expected_direction'}
            or choice['kernel'] != proof['operator'] + '_kernel'
            or set(specs) != {choice['metric']} or choice['expected_direction'] not in ('increase', 'decrease')
            or choice['case_id'] not in task_config_value['expected_case_ids']):
        raise ValueError('mechanism choice is outside the frozen single-kernel scope')
    case = next(c for c in task_config_value['cases'] if c['case_id'] == choice['case_id'])
    output = Path(output); output.mkdir(mode=0o700, exist_ok=False)
    from task_budget import collection_unit_deadline, CollectionBoundaryStop
    budget=timing.replay_task_budget(local,budget_binding,expected=task_config_value) if budget_binding is not None else None
    if budget is not None and budget['deadline_monotonic'] != deadline:
        raise ValueError('mechanism changed the original parent deadline')
    policy=budget.get('collection_stop_policy') if budget is not None else None
    profiles = {}
    for role in ROLES:
        try:
            unit_started=time.monotonic();unit_wall=time.time()
            unit_deadline=collection_unit_deadline(deadline,policy,'pmu',now=unit_started)
        except CollectionBoundaryStop:
            stop={'kind':'collection_budget_stop','next_unit':{'role':role},'scope':'whole_role_10warmups_5captures_original_oracle',
                'deadline_monotonic':deadline,'stopped_monotonic':time.monotonic(),'complete':False,'policy':policy}
            save(output/'budget-stop.json',stop);local.register_artifact(output/'budget-stop.json')
            local.write_index(output/'partial-local-index.json')
            raise
        unit_ref=None
        if policy is not None:
            unit_path=output/(role+'-collection-unit.json')
            save(unit_path,dict(schema_version=1,started_at=unit_wall,started_monotonic=unit_started,deadline_monotonic=unit_deadline))
            unit_ref=local.register_artifact(unit_path)
        config = {'backend': 'auto', 'architecture': 'Ascend910C', 'soc': 'Ascend910_9392',
            'device': 0, 'physical_device': task_config_value['physical_device'], 'chip': 0,
            'case_id': choice['case_id'], 'role': role, 'kernel': proof['role_kernel_names'][role][0],
            'source_dir': proof['roles'][role]['path'], 'binary': build['binary']['path'],
            'cwd': str(Path(assembly) / 'source'), 'workload': case['workload'],
            'command': [t.replace('{cycle_dir}', str(output)) for t in case['command']] + ['--aprof-mechanism-role', role],
            'warmups': 10, 'repeats': 5, 'timeout_seconds': min(180, remaining(unit_deadline))}
        if config['command'][0] != build['binary']['path']:
            raise ValueError('mechanism command changed the combined binary')
        with timing.shared.device_lock(task_config_value['physical_device'], remaining(unit_deadline)):
            try:
                result = profile_capture.capture(config, output / role, deadline_monotonic=unit_deadline)
            except BaseException:
                partial=output/role/'local-index.json'
                if partial.is_file(): merge_index(local,partial)
                local.write_index(output/'partial-local-index.json')
                raise
        reader = LocalEvidence.from_index(result['local_index'])
        manifest = load_capture_manifest(reader, result['manifest_hash'])
        expected = {'role': role, 'kernel': config['kernel'], 'case_id': choice['case_id'],
                    'binary_hash': build['binary']['sha256']}
        if any(manifest[key] != value for key, value in expected.items()):
            raise ValueError('captured role/kernel/case/binary differs from frozen request')
        source = json.loads(reader.verify_artifact(manifest['source_hash']).read_text())
        if source != {'schema_version': '1.0.0', 'files': proof['roles'][role]['files']}:
            raise ValueError('capture source differs from the mechanically bound role')
        profile = normalize_profile(reader, result['manifest_hash'], expand_specs(manifest, specs))
        merge_index(local, result['local_index'])
        paths = [Path(p.replace('{cycle_dir}', str(output))) for p in case['output_files'][role]]
        before = {str(p): local.register_artifact(p) for p in paths}
        verify = [t.replace('{cycle_dir}', str(output)) for t in case['verify_commands'][role]]
        record = profile_capture.run(verify, Path(assembly) / 'source', output / (role + '-oracle'),
                                     min(120, remaining(unit_deadline)), local)
        result_path = Path(verify[verify.index('--result') + 1])
        verify_mechanism_oracle(local, record, result_path, choice['case_id'])
        if before != {str(p): file_hash(p) for p in paths}:
            raise ValueError('mechanism complete output oracle failed or mutated output')
        local.register_artifact(result_path)
        profiles[role] = {'profile': profile, 'digest': local.register_json(profile),
                          'hardware': manifest['hardware_hash'], 'oracle': record['log_hash']}
        if unit_ref is not None: profiles[role]['collection_unit_ref']=unit_ref
        adapter.source_identity(assembly)
        remaining(unit_deadline)
        checkpoint=output/(role+'-completed.json')
        saved=profiles[role]
        if unit_ref is not None:
            saved=dict(kind='complete_role_collection_v1',role=role,profile_ref=profiles[role]['digest'],
                oracle_ref=record['log_hash'],collection_unit_ref=unit_ref,finished_at=time.time())
        save(checkpoint,saved)
        checkpoint_ref=local.register_artifact(checkpoint)
        if unit_ref is not None: profiles[role]['collection_receipt_ref']=checkpoint_ref
        local.write_index(output/(role+'-completed-local-index.json'))
        remaining(unit_deadline)
    if profiles['baseline']['hardware'] != profiles['candidate']['hardware']:
        raise ValueError('mechanism captures have different hardware identities')
    return profiles


def finalize_online(context, request, graph, local, *, deadline, policy=None):
    remaining(deadline)
    episodes = finalize_episodes(Context.from_dict(context), GateRequest.from_dict(request),
                                 graph=graph, behavior_policy=policy, store=local)
    remaining(deadline)
    return {'episodes': to_primitive(episodes), 'store_sequences': [], 'storage_mode': 'local_profile_only',
            'archive_performed': False, 'enabled_in_1_0': False, 'cost_scope': 'online_controller'}
