"""Read-only replay of registered Teacher trials; never a promotion gate.

The top-level reader supplies the trusted campaign and its immutable final
LocalEvidence index files. Each trial supplies its original reader (or a retained
CAS reader), index_ref and dispatcher_result_ref. Collecting these small indexes
after exit does not rewrite a child result. Archived successful trials additionally
supply the existing proof-bound source_archive_ref for the outer verifier.
"""
from task_budget import budget_seconds, positive, rule_execution_job, collection_policy
import ast
import json
from pathlib import Path
import re

from task_rule_admission import IDENTITY, PROTOCOL, STAGES, TASK_PROTOCOL, _timestamp
from timing_admission import checked_path, identity, number, read, require


MODEL = {'name': 'gpt-6-sol', 'reasoning_effort': 'max'}
CAMPAIGN_KEYS = {'schema_version', 'kind', 'protocol', 'task_protocol', 'runtime_build',
    'model', 'budget_seconds', 'budget_policy', 'reviewer_token_limit', 'max_attempts_per_operator',
    'stop_on_failure', 'resampling', 'created_at', 'attempts', 'source_freezes',
    'trace_index_sha256', 'split_index_sha256', 'prior_campaign_refs'}
BOUNDARY_ONLY_VERIFIER_CONTROLLER = 'sha256:4b6bfb94456a095282165358c31a6a0e971e01cc79d01b9f74df74fb1aac4515'
COMBINED_STREAM_BRIDGE = 'sha256:29a5c184601f4f0b8fe5bf7cdb36c77cfdeb4066f5298c76d1cbbf24000bff82'
COMBINED_STREAM_CAPTURE = 'sha256:701d51a65e946c00e2ee3b33deec8c2caa974601c6ac744976338cb23c81f2bc'


def _digest(value):
    require(isinstance(value, str) and re.fullmatch(r'sha256:[0-9a-f]{64}', value), 'invalid evidence digest')
    return value


def _path(value):
    require(isinstance(value, str) and '\0' not in value and Path(value).is_absolute()
            and str(Path(value)) == value and '..' not in Path(value).parts, 'invalid logical path')
    return Path(value)


def _pointer(reader, pointer):
    require(isinstance(pointer, dict) and set(pointer) == {'path', 'sha256'}, 'invalid evidence pointer')
    checked_path(reader, _path(pointer['path']), _digest(pointer['sha256']))
    return read(reader, pointer['sha256'])


def registered_operators(campaign, reader):
    """Only a frozen explicit user amendment narrows the historical two-slot roster."""
    operators = ('exp', 'sigmoid')
    if 'scope_amendment_ref' in campaign:
        amendment = _pointer(reader, campaign['scope_amendment_ref'])
        expected = {'schema_version': 1, 'kind': 'teacher_exp_only_scope_amendment',
            'authorization': 'user_requested_exp_only_release_on_success',
            'release_id': 'graph-base/1.0.0',
            'target': {'device': '910C', 'architecture': 'A3', 'cann_version': '9.0.0'},
            'operators': ['exp'], 'validation_45': 'not_run',
            'postseal_full_tests': 'not_run', 'other_rules': 'draft'}
        require(isinstance(amendment, dict) and set(amendment) == set(expected) | {'created_at'}
                and all(amendment[key] == value for key, value in expected.items())
                and 0 < number(amendment['created_at']) <= number(campaign['created_at']),
                'unsupported exp-only scope amendment')
        operators = ('exp',)
    attempts = campaign['attempts']
    require(isinstance(attempts, list) and len(attempts) == len(operators)
            and all(isinstance(a, dict) and set(a) == set(IDENTITY) for a in attempts)
            and tuple(a['operator'] for a in attempts) == operators
            and len({a['run_id'] for a in attempts}) == len({a['candidate_id'] for a in attempts}) == len(operators),
            'campaign must register exactly one attempt for every authorized operator')
    return operators


def _boundary_dependency(reader, check, *, anchor, anchor_ref, plan, frozen, root,
                         controller_path, created_at):
    """Replay the known verifier-only defect from frozen bytes; never execute them."""
    require(set(check) == {'schema_version', 'kind', 'started_at', 'duration_seconds', 'method',
            'producer_snapshot', 'controller_snapshot', 'original_controller_path', 'oracle_files_expression',
            'boundary_plan_ref', 'required_oracle_refs', 'bound_oracle_refs', 'missing_oracle_refs',
            'passed', 'admission_authority'} and check['schema_version'] == 1
            and check['kind'] == 'frozen_boundary_oracle_binding_preflight'
            and check['method'] == 'parse exact frozen controller AST and compare its verifier-only oracle_files to the frozen boundary plan; no execution'
            and check['passed'] is False and check['admission_authority'] is False
            and anchor['created_at'] <= number(check['started_at'])
            <= number(check['started_at']) + number(check['duration_seconds']) <= number(created_at)
            and check['duration_seconds'] >= 0, 'invalid boundary dependency check')
    snapshot = _pointer(reader, check['producer_snapshot'])
    require(snapshot.get('schema_version') == 1 and snapshot.get('kind') == 'frozen_task_producer_source_archive'
            and snapshot.get('owner') == 'trace_collection' and snapshot.get('cost_scope') == 'post_task'
            and snapshot['source_anchors'][anchor['operator']] == {'path': str(root/'anchor.json'), 'sha256': anchor_ref}
            and snapshot['frozen_files_refs'][anchor['operator']] == plan['frozen_files_ref'],
            'dependency snapshot differs from the registered trial')
    source = check['controller_snapshot']
    require(set(source) == {'path', 'sha256'} and check['original_controller_path'] == controller_path
            and frozen[controller_path] == source['sha256'] == BOUNDARY_ONLY_VERIFIER_CONTROLLER
            and snapshot['files'][controller_path]['sha256'] == source['sha256']
            and snapshot['files'][controller_path]['path'] == source['path'],
            'dependency controller is not the exact frozen defective producer')
    path = checked_path(reader, _path(source['path']), _digest(source['sha256']))
    require(path.stat().st_size == snapshot['files'][controller_path]['bytes'], 'controller snapshot size differs')
    tree = ast.parse(path.read_text())
    expressions = [n.value for n in ast.walk(tree) if isinstance(n, ast.keyword) and n.arg == 'oracle_files']
    assignments = [n.value for n in ast.walk(tree) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'oracle' for t in n.targets)]
    expression = '{str(oracle): local.register_artifact(oracle)}'
    require(len(expressions) == len(assignments) == 1
            and ast.dump(expressions[0]) == ast.dump(ast.parse(expression, mode='eval').body)
            and ast.dump(assignments[0]) == ast.dump(ast.parse("workspace / 'baseline/scripts/verify_result.py'", mode='eval').body)
            and check['oracle_files_expression'] == expression, 'frozen oracle binding AST differs')
    boundary = _pointer(reader, check['boundary_plan_ref'])
    require(check['boundary_plan_ref']['sha256'] == anchor['boundary_plan_ref']
            and boundary['operator'] == anchor['operator'],
            'dependency boundary plan was not frozen by this trial')
    required = {name: _digest(boundary[name+'_ref']) for name in ('generator', 'verifier')}
    oracle_path = str(root/'worker/root/work/baseline/scripts/verify_result.py')
    bound = {oracle_path: frozen[oracle_path]}
    require(check['required_oracle_refs'] == required and check['bound_oracle_refs'] == bound
            and bound[oracle_path] == required['verifier']
            and all(reference in frozen.values() for reference in required.values()),
            'dependency oracle identities differ from frozen sources')
    for reference in required.values():
        reader.verify_artifact(reference)
    missing = sorted(set(required.values()) - set(bound.values()))
    require(missing == [required['generator']] == check['missing_oracle_refs'],
            'claimed missing boundary generator does not reproduce')
    return {'controller_ref': source['sha256'], 'boundary_plan_ref': anchor['boundary_plan_ref'],
            'missing_oracle_refs': missing, 'producer_snapshot_ref': check['producer_snapshot']['sha256']}


def _stream_dependency(reader, check, *, frozen, created_at):
    """Reproduce the observed parser failure from retained bytes, without execution."""
    require(set(check) == {'schema_version', 'kind', 'created_at', 'producer_snapshot',
            'bridge_path', 'capture_path', 'oracle_execution_ref', 'oracle_result_ref',
            'parse_error', 'passed', 'admission_authority'}
            and check['schema_version'] == 1 and check['kind'] == 'shared_oracle_stream_dependency'
            and check['passed'] is False and check['admission_authority'] is False
            and 0 < number(check['created_at']) <= number(created_at), 'invalid stream dependency check')
    snapshot = _pointer(reader, check['producer_snapshot'])
    require(snapshot.get('kind') == 'frozen_task_producer_source_archive'
            and snapshot.get('owner') == 'trace_collection' and snapshot.get('cost_scope') == 'post_task',
            'stream dependency lacks retained producer bytes')
    for name, reference in [('bridge_path', COMBINED_STREAM_BRIDGE), ('capture_path', COMBINED_STREAM_CAPTURE)]:
        path = str(_path(check[name])); source = snapshot['files'][path]
        require(frozen.get(path) == source['sha256'] == reference, 'unstarted trial used a different stream parser')
        actual = checked_path(reader, _path(source['path']), reference)
        require(actual.stat().st_size == source['bytes'], 'stream parser snapshot size differs')
    bridge = reader.verify_artifact(COMBINED_STREAM_BRIDGE).read_text()
    expression = ast.dump(ast.parse("json.loads(record['text'].strip())", mode='eval').body)
    require(any(isinstance(node, ast.Call) and ast.dump(node) == expression
                for node in ast.walk(ast.parse(bridge))), 'frozen combined-stream parser expression differs')
    execution = _pointer(reader, check['oracle_execution_ref'])
    result = _pointer(reader, check['oracle_result_ref'])
    require(execution.get('exit_code') == 0 and execution.get('error') is None
            and execution['started_at'] <= execution['ended_at'] <= check['created_at']
            and result.get('passed') is True, 'blocking oracle did not succeed before parsing')
    stdout = reader.verify_artifact(execution['stdout_hash']).read_bytes()
    stderr = reader.verify_artifact(execution['stderr_hash']).read_bytes()
    require(json.loads(stdout) == result and stderr.strip(), 'stream failure lacks valid stdout and separate stderr')
    try:
        json.loads((stdout + b'\n' + stderr).decode(errors='replace').strip())
    except json.JSONDecodeError as error:
        actual_error = {'type': type(error).__name__, 'message': str(error)}
        require(check['parse_error'] == actual_error, 'claimed stream failure does not reproduce')
    else:
        raise ValueError('combined stream did not reproduce a parser failure')
    return {'bridge_ref': COMBINED_STREAM_BRIDGE, 'capture_ref': COMBINED_STREAM_CAPTURE,
            'parse_error': actual_error, 'oracle_execution_ref': check['oracle_execution_ref'],
            'oracle_result_ref': check['oracle_result_ref'], 'producer_snapshot': snapshot}


def _partial(reader, report, anchor, anchor_ref, started, finished, failure_ref=None):
    """A stopped recorder is a prefix, never a fabricated successful roster."""
    identity(report, anchor)
    require(report.get('schema_version') == 1 and report.get('protocol') == PROTOCOL
            and report.get('anchor_ref') == anchor_ref and 'execution_ref' not in report,
            'child report identity or exit authority differs')
    protocol = read(reader, report['protocol_ref'])
    require(all(protocol.get(key) == value for key, value in anchor.items() if key != 'created_at')
            and protocol.get('anchor_ref') == anchor_ref, 'partial protocol changed its preregistration')
    registration_ref = report['qualification_registration_ref']
    registration = read(reader, registration_ref)
    require(registration.get('schema_version') == 1 and registration.get('protocol_ref') == report['protocol_ref']
            and registration.get('anchor_ref') == anchor_ref
            and all(registration.get(key) == anchor[key] for key in ('run_id', 'candidate_id'))
            and registration.get('stages') == list(STAGES) and registration.get('max_attempts') == 1
            and registration.get('stop_on_failure') is True and registration.get('resampling') == 'none',
            'partial registration differs')
    clock = number(registration['created_at'])
    require(started <= number(protocol['created_at']) <= clock <= finished, 'partial registration time differs')
    roster = read(reader, report['attempt_roster_ref'])
    events = roster.get('events')
    require(roster.get('schema_version') == 1 and roster.get('registration_ref') == registration_ref
            and isinstance(events, list) and len(events) == len(set(events)) and len(events) <= 2 * len(STAGES),
            'partial stage roster differs')
    evidence = report.get('stage_evidence')
    require(isinstance(evidence, dict), 'partial stage evidence is missing')
    previous, started_stages = registration_ref, set()
    for sequence, reference in enumerate(events):
        event = read(reader, reference)
        stage, state = STAGES[sequence // 2], ('started', 'completed')[sequence % 2]
        require(event.get('sequence') == sequence and event.get('previous_ref') == previous
                and event.get('registration_ref') == registration_ref and event.get('stage') == stage
                and event.get('state') == state and clock <= number(event['at']) <= finished,
                'failure continued, repeated or reordered a stage')
        if state == 'started':
            started_stages.add(stage)
            require(not event.get('evidence_refs') and event.get('exit_status') is None,
                    'started stage claims a completed exit')
        else:
            require(event.get('exit_status') == 0 and event.get('evidence_refs')
                    and event['evidence_refs'] == evidence.get(stage)
                    and failure_ref not in event['evidence_refs'], 'failed stage was completed or evidence changed')
        previous, clock = reference, number(event['at'])
    require(set(evidence) <= started_stages
            and set(STAGES[:len(events) // 2]) <= set(evidence), 'failure has unregistered or omitted stage evidence')
    for refs in evidence.values():
        require(isinstance(refs, list) and refs and len(refs) == len(set(refs)), 'invalid partial evidence list')
        for reference in refs:
            reader.verify_artifact(reference)
    return {'events': len(events), 'completed_stages': list(STAGES[:len(events) // 2]),
            'active_stage': STAGES[len(events) // 2] if len(events) % 2 else None}


def _trial(top, campaign_ref, campaign, attempt, supplied):
    require(isinstance(supplied, dict) and {'reader', 'index_ref'} <= set(supplied)
            and len({'dispatcher_result_ref', 'not_run_ref'} & set(supplied)) == 1
            and set(supplied) <= {'reader', 'index_ref', 'dispatcher_result_ref', 'not_run_ref', 'source_archive_ref'},
            'trial reader/index/result inputs differ')
    reader = supplied['reader']
    index = read(top, supplied['index_ref'])
    require(set(index) == {'schema_version', 'kind', 'directory', 'artifacts'} and index['schema_version'] == 1
            and index['kind'] == 'local_evidence_index' and isinstance(index['artifacts'], dict),
            'final local index differs')
    root = _path(index['directory']).parent
    require(Path(index['directory']).name == 'records', 'trial evidence directory differs')
    for digest, path in index['artifacts'].items():
        _digest(digest); _path(path)

    def artifact(reference, path=None):
        require(reference in index['artifacts'], 'referenced trial evidence was omitted from its final index')
        if path is not None:
            checked_path(reader, path, reference)
        return read(reader, reference)

    unstarted = read(top, supplied['not_run_ref']) if 'not_run_ref' in supplied else None
    result = None if unstarted is not None else artifact(supplied['dispatcher_result_ref'], root / 'dispatcher-result.json')
    if result is not None:
        require(result.get('schema_version') == 1 and result.get('status') in ('failed', 'completed_child')
                and result.get('archive_performed') is False and result.get('admission_authority') is False,
                'trial lacks an actual dispatcher terminal')
    anchor_ref = unstarted['anchor_ref']['sha256'] if unstarted is not None else result['anchor_ref']
    anchor = artifact(anchor_ref, root / 'anchor.json')
    identity(anchor, attempt)
    require(anchor.get('schema_version') == 1 and anchor.get('protocol') == PROTOCOL
            and anchor.get('task_protocol') == TASK_PROTOCOL and anchor.get('purpose') == 'promotion'
            and anchor.get('campaign_ref') == campaign_ref and budget_seconds(anchor) == budget_seconds(campaign)
            and collection_policy(anchor)==collection_policy(campaign)
            and campaign['created_at'] <= number(anchor['created_at']), 'trial anchor changed its campaign')
    for reference in anchor['source_hashes'].values():
        artifact(reference)
    require(isinstance(anchor.get('history_refs'), list)
            and {p['sha256'] for p in campaign['prior_campaign_refs']} <= set(anchor['history_refs']),
            'trial omitted prior failed campaign history')
    for reference in anchor['history_refs']:
        reader.verify_artifact(reference)
    plan = artifact(anchor['controller_plan_ref'], root / 'controller-plan.json')
    require(plan.get('directory') == str(root) and plan.get('launch_path') == str(root / 'dispatcher-launch.json')
            and plan.get('model') == MODEL and Path(plan['release']).name == '1.0.0', 'controller plan differs')
    qualification = _pointer(reader, plan['worker_qualification'])
    require(qualification.get('model') == MODEL['name'] and qualification.get('reasoning_effort') == MODEL['reasoning_effort']
            and qualification.get('budget_policy') == 'time_only_v1'
            and qualification.get('review_submission_protocol') == 'final_json_review_v1',
            'trial did not bind the qualified time-only reviewer interface')
    frozen = artifact(plan['frozen_files_ref'])
    require(isinstance(frozen, dict) and campaign_ref in frozen.values(), 'campaign was not frozen by preparation')
    if 'scope_amendment_ref' in campaign:
        scope = campaign['scope_amendment_ref']
        require(frozen.get(scope['path']) == scope['sha256'], 'scope amendment was not frozen by preparation')
        artifact(scope['sha256'], _path(scope['path']))
    job = artifact(anchor['job_ref'], root / 'job.json')
    argv = job.get('argv', [])
    require(job.get('job_id') == attempt['run_id'] and positive(job.get('timeout_seconds')) == budget_seconds(campaign)
            and job.get('output_dir') == str(root / 'job') and 'physical_device' not in job
            and len(argv) == 6 and Path(argv[1]).name == 'task_rule_controller.py'
            and argv[2:] == ['--anchor', str(root / 'anchor.json'), '--local-index', str(root / 'prepared-local-index.json')]
            and argv[1] in frozen, 'actual controller job differs from preregistration')
    env = job.get('environment', {})
    require(env.get('APROF_SKILL_LIB') == plan['release'] and env.get('PYTHONDONTWRITEBYTECODE') == '1'
            and env.get('ASCEND_RT_VISIBLE_DEVICES') == env.get('APROF_PHYSICAL_DEVICE') == str(plan['physical_device'])
            and env.get('APROF_LOGICAL_DEVICE') == '0', 'actual job device/runtime environment differs')
    if unstarted is not None:
        common = {'schema_version', 'kind', 'status', 'created_at', 'anchor_ref', 'campaign_ref',
                'run_id', 'candidate_id', 'operator', 'reason', 'blocking_controller_result_ref',
                'blocking_execution_ref', 'actual_builds', 'hardware_stages_started',
                'admission_authority', 'archive_performed'}
        version = unstarted.get('schema_version')
        require(version in (1, 2, 3) and set(unstarted) == common | (
                {'affected_metadata_ref', 'static_check'} if version == 1 else {'dependency_check_ref'})
                and unstarted['kind'] == 'unstarted_task_dependency_closure'
                and unstarted['status'] == 'not_run' and unstarted['campaign_ref'] == campaign_ref
                and all(unstarted[key] == attempt[key] for key in ('operator', 'run_id', 'candidate_id'))
                and unstarted['anchor_ref'] == {'path': str(root / 'anchor.json'), 'sha256': anchor_ref}
                and unstarted['actual_builds'] == unstarted['hardware_stages_started'] == 0
                and unstarted['admission_authority'] is False and unstarted['archive_performed'] is False
                and isinstance(unstarted['reason'], str) and unstarted['reason'], 'invalid not-run dependency closure')
        forbidden = ('dispatcher-launch.json', 'dispatcher-result.json', 'controller-start.json',
                     'controller-result.json', 'job', 'assembly/build-attempt.json')
        require(all(not (root / name).exists() and not (root / name).is_symlink() for name in forbidden)
                and not any(Path(path).is_relative_to(root / 'job') or path in {str(root / n) for n in forbidden}
                            for path in index['artifacts'].values()), 'not-run trial actually launched or built')
        dependency = None
        if version == 2:
            artifact(anchor['boundary_plan_ref'])  # Bound directly by the prelaunch anchor/index.
            require(unstarted['dependency_check_ref']['path'] == str(root/'dependency-check.json'),
                    'dependency check path differs')
            dependency = _boundary_dependency(top, _pointer(top, unstarted['dependency_check_ref']),
                anchor=anchor, anchor_ref=anchor_ref, plan=plan, frozen=frozen, root=root,
                controller_path=argv[1], created_at=unstarted['created_at'])
        elif version == 3:
            require(unstarted['dependency_check_ref']['path'] == str(root/'dependency-check.json'),
                    'stream dependency check path differs')
            dependency = _stream_dependency(top, _pointer(top, unstarted['dependency_check_ref']),
                frozen=frozen, created_at=unstarted['created_at'])
        else:
            metadata = _pointer(reader, unstarted['affected_metadata_ref'])
            inputs = artifact(anchor['input_inventory_ref'])
            pointer = unstarted['affected_metadata_ref']
            require(inputs.get(pointer['path']) == pointer['sha256'], 'not-run prerequisite is not an original frozen input')
            static = unstarted['static_check']
            require(set(static) == {'started_at', 'duration_seconds', 'error', 'method'}
                    and static['method'] == 'json.dumps(original_metadata, allow_nan=False); no source or input mutation'
                    and anchor['created_at'] <= number(static['started_at']) <= number(unstarted['created_at'])
                    and number(static['duration_seconds']) >= 0, 'not-run static prerequisite evidence differs')
            try:
                json.dumps(metadata, allow_nan=False)
            except ValueError as error:
                require(static['error'] == str(error), 'not-run static error changed')
            else:
                raise ValueError('not-run prerequisite failure does not reproduce')
        for key in ('blocking_controller_result_ref', 'blocking_execution_ref'):
            require(set(unstarted[key]) == {'path', 'sha256'}, 'not-run blocking pointer differs')
            _path(unstarted[key]['path']); _digest(unstarted[key]['sha256'])
        return {'operator': attempt['operator'], 'run_id': attempt['run_id'], 'status': 'not_run',
            'index_ref': supplied['index_ref'], 'not_run_ref': supplied['not_run_ref'], 'anchor_ref': anchor_ref,
            'job_ref': anchor['job_ref'], 'execution_ref': None, 'controller_result_ref': None, 'components': None,
            'root': str(root), 'closure': unstarted, 'failure': unstarted['reason'],
            'dependency_replay': dependency, 'frozen_controller_ref': frozen[argv[1]]}
    execution_ref = result.get('execution_ref')
    execution = artifact(execution_ref, root / 'job/execution.json')
    launch_refs=[ref for ref,path in index['artifacts'].items() if path == str(root / 'dispatcher-launch.json')]
    launch=artifact(launch_refs[0],root/'dispatcher-launch.json') if len(launch_refs)==1 else None
    actual_job=rule_execution_job(lambda ref: artifact(ref),anchor,job,launch)
    require(execution.get('schema_version') == '1.0.0' and execution.get('kind') == 'aprof_execution_report'
            and execution.get('job') == actual_job and execution.get('status') in ('passed', 'failed', 'timeout')
            and type(execution.get('exit_code')) is int and number(execution['duration_seconds']) > 0,
            'actual dispatcher exit is missing or differs')
    started, finished = (_timestamp(execution[k]) for k in ('started_at', 'finished_at'))
    require(anchor['created_at'] <= started <= finished <= number(result['finished_at']), 'dispatcher chronology differs')
    for name in ('stdout', 'stderr'):
        pointer = execution[name]
        require(set(pointer) == {'path', 'sha256'} and pointer['path'] == str(root / 'job' / (name + '.log'))
                and pointer['sha256'] in index['artifacts'], 'actual dispatcher log binding differs')
        checked_path(reader, pointer['path'], pointer['sha256'])
    child = None
    if result.get('controller_result_ref'):
        child = artifact(result['controller_result_ref'], root / 'controller-result.json')
        require(child.get('schema_version') == 1 and child.get('anchor_ref') == anchor_ref
                and child.get('status') in ('passed', 'failed') and child.get('archive_performed') is False
                and child.get('storage_mode') == 'local_profile_only' and type(child.get('actual_builds')) is int
                and child['actual_builds'] in (0, 1) and started <= number(child['started_at'])
                <= number(child['finished_at']) <= finished and number(child['duration_seconds']) > 0,
                'controller terminal identity, chronology or build count differs')
    else:
        require(str(root / 'controller-result.json') not in index['artifacts'].values()
                and execution['status'] != 'passed', 'dispatcher omitted an existing/successful child result')
    partial, component = None, None
    child_ref = child.get('child_report_ref') if child else None
    if child_ref:
        report = artifact(child_ref)
        failure_refs = [ref for ref, path in index['artifacts'].items()
                        if path == str(root / 'admission/stage-failure.json')]
        require(len(failure_refs) <= 1, 'failure record changed within one attempt')
        partial = _partial(reader, report, anchor, anchor_ref, started, finished,
                           failure_refs[0] if failure_refs else None)
        require(result.get('child_report_ref', child_ref) == child_ref, 'dispatcher substituted the child report')
        if result.get('report_ref'):
            require(artifact(result['report_ref']) == dict(report, execution_ref=execution_ref),
                    'dispatcher rewrote the child evidence rather than binding its actual exit')
    else:
        require(not any(result.get(k) for k in ('child_report_ref', 'report_ref', 'expected', 'measurement_expected')),
                'pre-build failure fabricated a full report')
    if result['status'] == 'completed_child':
        require(execution['status'] == 'passed' and execution['exit_code'] == 0 and not execution.get('error')
                and execution['duration_seconds'] <= actual_job['timeout_seconds'] and finished - started <= actual_job['timeout_seconds']
                and (launch is None or launch['schema_version']==1 or finished <= launch['started_at']+budget_seconds(campaign))
                and child and child['status'] == 'passed' and not child.get('error') and result.get('error') is None
                and child_ref and result.get('report_ref'), 'failed or over-budget attempt cannot be completed')
        expected = {key: anchor[key] for key in IDENTITY}
        expected.update(anchor_ref=anchor_ref, protocol_ref=report['protocol_ref'],
            qualification_registration_ref=report['qualification_registration_ref'], execution_ref=execution_ref)
        require(result.get('expected') == expected and result.get('measurement_expected') == child.get('measurement_expected')
                and isinstance(result.get('measurement_expected'), dict), 'dispatcher changed the complete handoff')
        from task_outer_admission import verify_task_rule_admission
        component = verify_task_rule_admission(reader, result['report_ref'], expected=expected,
            measurement_expected=result['measurement_expected'], source_archive_ref=supplied.get('source_archive_ref'))
        require(component.get('valid') is True and component.get('admission_authority') is False,
                'complete Task components did not replay')
    else:
        require(isinstance(result.get('error'), dict) and result['error'].get('type')
                and result['error'].get('message'), 'failed dispatcher lost its actual failure')
    return {'operator': attempt['operator'], 'run_id': attempt['run_id'], 'status': result['status'],
        'index_ref': supplied['index_ref'], 'dispatcher_result_ref': supplied['dispatcher_result_ref'],
        'anchor_ref': anchor_ref, 'execution_ref': execution_ref, 'controller_result_ref': result.get('controller_result_ref'),
        'job_ref': anchor['job_ref'], 'exit_code': execution['exit_code'], 'execution_status': execution['status'],
        'duration_seconds': execution['duration_seconds'], 'failure': result.get('error'),
        'controller_failure': child.get('error') if child else None, 'partial_roster': partial,
        'components': component, 'root': str(root), 'finished_at': finished,
        'frozen_controller_ref': frozen[argv[1]]}


def replay_task_rule_campaign(reader, campaign_ref, *, trials):
    """Close the registered slots with actual exits or a bound prerequisite closure."""
    campaign = read(reader, campaign_ref)
    require(set(campaign) - {'collection_stop_policy', 'scope_amendment_ref'} == CAMPAIGN_KEYS and campaign['schema_version'] == 1
            and campaign['kind'] == 'teacher_task_rule_campaign' and campaign['protocol'] == PROTOCOL
            and campaign['task_protocol'] == TASK_PROTOCOL and campaign['runtime_build'] == 'aprof-runtime/0.2.3'
            and campaign['model'] == MODEL and budget_seconds(campaign) > 0
            and campaign['budget_policy'] == 'time_only_v1' and campaign['reviewer_token_limit'] is None
            and campaign['max_attempts_per_operator'] == 1 and campaign['stop_on_failure'] is True
            and campaign['resampling'] == 'none' and number(campaign['created_at']) > 0,
            'unsupported finite time-only Teacher campaign')
    collection_policy(campaign)
    operators = registered_operators(campaign, reader)
    attempts = campaign['attempts']
    require(isinstance(trials, dict) and set(trials) == set(operators), 'omitted or unregistered trial/retry')
    require(isinstance(campaign['source_freezes'], list) and len(campaign['source_freezes']) == len(operators),
            'original source freezes are missing')
    for attempt, pointer in zip(attempts, campaign['source_freezes'], strict=True):
        freeze = _pointer(reader, pointer)
        require(freeze.get('schema_version') == 1 and freeze.get('operator') == attempt['operator']
                and freeze.get('source_hashes') == attempt['source_hashes']
                and set(attempt['source_hashes']) == {'baseline', 'candidate'}, 'original frozen sources differ')
        for reference in attempt['source_hashes'].values():
            _digest(reference)
    require(isinstance(campaign['prior_campaign_refs'], list), 'prior campaign history must be explicit')
    for pointer in campaign['prior_campaign_refs']:
        _pointer(reader, pointer)  # Old budget rejection evidence stays history, not a current attempt.
    _digest(campaign['trace_index_sha256']); _digest(campaign['split_index_sha256'])
    results = [_trial(reader, campaign_ref, campaign, a, trials[a['operator']]) for a in attempts]
    executed = [r for r in results if r['execution_ref'] is not None]
    require(len({r['root'] for r in results}) == len(operators)
            and len({r['execution_ref'] for r in executed}) == len(executed),
            'registered trials reused one task workspace or actual exit')
    for row in results:
        if row['status'] != 'not_run':
            continue
        closure = row['closure']
        blockers = [r for r in executed if r['execution_ref'] == closure['blocking_execution_ref']['sha256']
                    and r['controller_result_ref'] == closure['blocking_controller_result_ref']['sha256']]
        require(row['operator'] == 'sigmoid' and len(blockers) == 1 and blockers[0]['operator'] == 'exp'
                and blockers[0]['status'] == 'failed' and blockers[0]['finished_at'] <= closure['created_at'],
                'not-run slot is not justified by the earlier registered failure')
        if closure['schema_version'] == 2:
            blocker = blockers[0]
            require(row['dependency_replay']['controller_ref'] == blocker['frozen_controller_ref']
                    and blocker['controller_failure'] == {'type': 'StageFailure',
                        'message': 'boundary oracle differs from frozen protocol'}
                    and blocker['partial_roster'] == {'events': 3, 'completed_stages': ['correctness'],
                                                      'active_stage': 'boundary'},
                    'dependency closure does not match the actual shared boundary failure')
        elif closure['schema_version'] == 3:
            blocker = blockers[0]; dependency = row['dependency_replay']
            snapshot = dependency['producer_snapshot']
            require(snapshot['source_anchors']['exp'] == {
                        'path': str(Path(blocker['root'])/'anchor.json'), 'sha256': blocker['anchor_ref']}
                    and dependency['oracle_execution_ref']['path'] == str(Path(blocker['root'])/'mechanism/baseline-oracle.execution.json')
                    and dependency['oracle_result_ref']['path'] == str(Path(blocker['root'])/'mechanism/baseline-result.json')
                    and blocker['controller_failure'] == dependency['parse_error']
                    and blocker['partial_roster'] == {'events': 9,
                        'completed_stages': ['correctness', 'boundary', 'screen', 'task_measurement'], 'active_stage': 'profile'},
                    'dependency closure does not match the actual shared stream failure')
        for key, name in [('blocking_execution_ref', 'job/execution.json'),
                          ('blocking_controller_result_ref', 'controller-result.json')]:
            require(closure[key]['path'] == str(Path(blockers[0]['root']) / name), 'not-run blocker path differs')
    return {'valid': True, 'complete': True, 'scope': 'registered_teacher_task_campaign_components',
        'campaign_ref': campaign_ref, 'trials': results, 'prior_campaign_refs': campaign['prior_campaign_refs'],
        'all_components_valid': all(r['components'] is not None for r in results),
        'admission_authority': False, 'eligible_for_publication': False,
        'remaining_requirements': ['independent source review and route',
            'full runtime gate and Teacher promotion policy; campaign completion alone grants neither']}
