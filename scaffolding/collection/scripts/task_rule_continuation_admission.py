"""Replay an original failed Exp task's completed prefix without upgrading it.

Only trusted current verifiers execute. Original source bytes, stage windows,
Task samples, failure and deadline remain unchanged. This module does not run a
capture or grant continuation, optimization, promotion or publication authority.
"""
import json
from pathlib import Path

from archived_rule_correctness import verify_archived_rule_correctness
from retained_source_review import replay_retained_source_review
from task_outer_admission import verify_task_screen
from task_rule_campaign import replay_task_rule_campaign
from task_rule_admission import _timestamp
from task_budget import rule_execution_job
from timing_admission import ReplayCache, checked_path, content_hash, identity, number, read, require
from aprof_runtime.measurement_entry import replay_current_measurement_admission
from aprof_runtime.measurement_admission import historical_producer_scope
from aprof_runtime.task_window_measurement_admission import PRODUCER_FILES
from shared_validation_adapter import selected_runtime
from task_profile_admission import _verify_capture_executions, verify_task_profile_window


PREFIX = ('correctness', 'boundary', 'screen', 'task_measurement')
ROLES = ('baseline', 'candidate')
REPORT_KEYS = dict(zip(PREFIX, ('correctness_report_ref', 'boundary_report_ref',
                              'screen_report_ref', 'measurement_admission_ref')))
# Full 23-file cohort from the original Exp Task registration. Not a per-file
# mix-and-match allowlist. No old Python is imported by this resolver.
KNOWN_PRODUCER_COHORT = 'sha256:d9d82e2f32cb7c58b652fcc5b2369f22d7d52139142ceaa37821538202b97494'


def retained_producer_scope(reader, *, anchor_ref, trusted_review_refs):
    """Authenticate the one retained cohort before enabling read-only replay."""
    require(set(trusted_review_refs) == {'archive_inventory_ref', 'producer_snapshot_ref'},
            'trusted producer archive references are required')
    anchor = read(reader, anchor_ref); plan = read(reader, anchor['controller_plan_ref'])
    snapshot = read(reader, trusted_review_refs['producer_snapshot_ref'])
    archive = read(reader, trusted_review_refs['archive_inventory_ref'])
    release = selected_runtime(); root = Path(plan['directory'])
    require(anchor['operator'] == 'exp' and Path(plan['release']) == release and release.name == '1.0.0'
            and snapshot['kind'] == 'frozen_task_producer_source_archive'
            and snapshot['owner'] == archive['owner'] == 'trace_collection'
            and snapshot['cost_scope'] == archive['cost_scope'] == 'post_task'
            and archive['producer_index_ref']['sha256'] == trusted_review_refs['producer_snapshot_ref']
            and snapshot['source_anchors']['exp'] == {'path': str(root / 'anchor.json'), 'sha256': anchor_ref}
            and snapshot['frozen_files_refs']['exp'] == plan['frozen_files_ref'],
            'producer archive is not bound to the original Exp freeze')
    frozen = read(reader, plan['frozen_files_ref'])
    cohort = {name: snapshot['files'][str(release / name)]['sha256'] for name in PRODUCER_FILES}
    require(content_hash(cohort) == KNOWN_PRODUCER_COHORT, 'unknown historical producer cohort')
    for name, reference in cohort.items():
        logical = str(release / name); retained = snapshot['files'][logical]
        require(frozen[logical] == reference and retained == archive['files'][logical],
                'producer differs across original freeze/snapshot/archive')
        path = checked_path(reader, retained['path'], reference)
        require(path.stat().st_size == retained['bytes'], 'retained producer size differs')

    def resolve(path, reference):
        relative = Path(path).relative_to(release).as_posix()
        require(cohort.get(relative) == reference, 'unapproved historical producer path/hash')
        return reader.verify_artifact(reference)

    return historical_producer_scope(resolve)


def replay_reused_prefix(reader, *, campaign_ref, trials, operator='exp', trusted_review_refs):
    """Replay the failed campaign, original review/build and four complete stages.

    ``trials`` is the original replay_task_rule_campaign argument, including its
    real sigmoid not-run closure and Exp post-task source_archive_ref.
    ``trusted_review_refs`` has archive_inventory_ref and producer_snapshot_ref;
    these are trusted collection inputs, never selected by the old model review.
    The returned windows apply only to the original task. A continuation must
    separately bind its amendment, actual exit, new window and cumulative cost.
    """
    require(operator == 'exp', 'continuation prefix is restricted to Exp')
    supplied = trials[operator]
    result = read(supplied['reader'], supplied['dispatcher_result_ref'])
    with retained_producer_scope(supplied['reader'], anchor_ref=result['anchor_ref'],
                                 trusted_review_refs=trusted_review_refs):
        return _replay_reused_prefix(reader, campaign_ref=campaign_ref, trials=trials,
                                    operator=operator, trusted_review_refs=trusted_review_refs)


def _replay_reused_prefix(reader, *, campaign_ref, trials, operator, trusted_review_refs):
    campaign = replay_task_rule_campaign(reader, campaign_ref, trials=trials)
    require(campaign.get('valid') is True and campaign.get('complete') is True,
            'original campaign is not closed')
    selected = next(row for row in campaign['trials'] if row['operator'] == operator)
    require(selected['status'] == 'failed' and selected['execution_status'] == 'failed'
            and selected['exit_code'] == 2 and selected['components'] is None
            and selected['partial_roster'] == {'events': 9, 'completed_stages': list(PREFIX),
                                               'active_stage': 'profile'}
            and selected['controller_failure'] == {
                'type': 'JSONDecodeError', 'message': 'Extra data: line 3 column 1 (char 228)'},
            'reuse requires the original stopped PMU stream-parser failure')
    supplied = trials[operator]
    source_archive_ref = supplied.get('source_archive_ref')
    require(isinstance(source_archive_ref, str), 'retained prefix requires archived source evidence')
    store = ReplayCache(supplied['reader'])
    anchor = read(store, selected['anchor_ref'])
    child = read(store, selected['controller_result_ref'])
    execution = read(store, selected['execution_ref'])
    require(child['status'] == 'failed' and child['actual_builds'] == 1,
            'original failed task must contain exactly one build')
    report_ref = child['child_report_ref']; report = read(store, report_ref)
    protocol_ref = report['protocol_ref']; protocol = read(store, protocol_ref)
    expected = {key: anchor[key] for key in ('operator', 'run_id', 'candidate_id', 'source_hashes')}
    identity(report, expected); identity(protocol, expected)
    require(isinstance(trusted_review_refs, dict)
            and set(trusted_review_refs) == {'archive_inventory_ref', 'producer_snapshot_ref'},
            'trusted retained review archive references are required')
    archive = read(store, trusted_review_refs['archive_inventory_ref'])
    index = read(reader, supplied['index_ref'])
    launch_path = str(Path(selected['root']) / 'dispatcher-launch.json')
    launch_refs = [ref for ref, path in index['artifacts'].items()
                   if path == launch_path]
    require(len(launch_refs) <= 1, 'original dispatcher launch is ambiguous')
    if 'dispatcher_launch_ref' in protocol:
        require(not launch_refs or launch_refs == [protocol['dispatcher_launch_ref']],
                'protocol and original index disagree on dispatcher launch')
        launch_refs = [protocol['dispatcher_launch_ref']]
    elif not launch_refs:
        # The original dispatcher did not always index its own launch. The
        # trusted post-task archive keeps that original file; never rewrite the index.
        retained = archive.get('files', {}).get(launch_path)
        require(isinstance(retained, dict), 'original dispatcher launch is missing from trusted archive')
        launch_refs = [retained['sha256']]
        retained_path = checked_path(store, retained['path'], retained['sha256'])
        require(retained_path.stat().st_size == retained['bytes'], 'retained launch size differs')
    checked_path(store, launch_path, launch_refs[0])
    launch = read(store, launch_refs[0])
    start, finish = (_timestamp(execution[k]) for k in ('started_at', 'finished_at'))
    original_deadline = number(launch['started_at']) + number(anchor['budget_seconds'])
    require(launch['anchor_ref'] == selected['anchor_ref'] and launch['job_ref'] == anchor['job_ref']
            and 0 < number(execution['duration_seconds']) <= execution['job']['timeout_seconds']
            <= anchor['budget_seconds'] and number(anchor['created_at']) <= launch['started_at']
            <= start <= finish <= original_deadline
            and execution['job'] == rule_execution_job(lambda ref: read(store, ref), anchor,
                read(store, anchor['job_ref']), launch),
            'original execution escaped its unchanged budget')
    roster = read(store, report['attempt_roster_ref']); windows = {}
    for index_, stage in enumerate(PREFIX):
        begin, end = (read(store, ref) for ref in roster['events'][2 * index_:2 * index_ + 2])
        require(begin['stage'] == end['stage'] == stage and begin['state'] == 'started'
                and end['state'] == 'completed' and end['exit_status'] == 0
                and start <= number(begin['at']) <= number(end['at']) <= finish
                and report[REPORT_KEYS[stage]] in end['evidence_refs']
                and end['evidence_refs'] == report['stage_evidence'][stage],
                'reused component is outside its original completed stage')
        windows[stage] = [begin['at'], end['at']]
    profile_start = read(store, roster['events'][8])['at']
    require(windows['task_measurement'][1] <= profile_start <= finish,
            'original PMU start precedes completed Task evidence')
    require(source_archive_ref in archive['source_archive_refs'][operator],
            'source supplement is not in the trusted original archive')
    checks = {}
    for stage in ('correctness', 'boundary'):
        ref = report[REPORT_KEYS[stage]]
        require(read(store, ref)['kind'] == 'task_rule_' + stage, 'reused correctness kind differs')
        checks[stage] = verify_archived_rule_correctness(store, ref, protocol_ref=protocol_ref,
            expected=expected, window=windows[stage], source_archive_ref=source_archive_ref)
        require(checks[stage]['passed'] is True and checks[stage]['case_count'] ==
                (20 if stage == 'correctness' else 42), 'complete original correctness did not replay')
    checks['screen'] = verify_task_screen(store, report['screen_report_ref'], protocol_ref=protocol_ref,
        expected=expected, window=windows['screen'], source_archive_ref=source_archive_ref)
    require(checks['screen']['valid'] is True, 'original six-case screen did not replay')
    completion_ref = report['measurement_admission_ref']; completion = read(store, completion_ref)
    measurement_expected = {key: completion[key] for key in
        ('operator', 'run_id', 'candidate_id', 'session_id', 'source_hashes', 'measurement_report_ref')}
    require(all(measurement_expected[key] == expected[key] for key in ('operator', 'run_id', 'candidate_id'))
            and set(measurement_expected['source_hashes']) == set(ROLES)
            and all(read(store, measurement_expected['source_hashes'][role]) ==
                    read(store, expected['source_hashes'][role]) for role in ROLES),
            'Task identity or canonical source bundle changed')
    task = replay_current_measurement_admission(store, completion_ref, expected=measurement_expected)
    require(task['valid'] is True and task['completion_ref'] == completion_ref
            and content_hash(read(store, task['config_ref'])) == content_hash(read(store, protocol['task_config_ref'])),
            'original Task config/completion differs')
    config = read(store, task['config_ref']); screen_config = read(store, checks['screen']['config_ref'])
    registration = read(store, task['registration_ref']); build = registration['identity']['build']
    require(config['expected_case_ids'] == list(range(1, 21))
            and [case['case_id'] for case in config['cases']] == list(range(1, 21))
            and config['build'] == screen_config['build']
            and protocol['binary_hashes'] == {role: build['binary_ref'] for role in ROLES},
            'formal Task changed full coverage or the original single build')
    inputs = read(store, protocol['input_inventory_ref'])
    require(all(inputs.get(path) == ref for case in registration['identity']['cases'].values()
                for path, ref in case['prepared_files'].items()), 'formal Task changed frozen prepared inputs')
    require(windows['task_measurement'][0] <= number(completion['started_at'])
            <= number(completion['finished_at']) <= windows['task_measurement'][1]
            and {completion_ref, task['receipt_ref'], task['config_ref'], task['registration_ref'],
                 measurement_expected['measurement_report_ref']} <= set(report['stage_evidence']['task_measurement']),
            'formal Task evidence escaped its original registered stage')
    checks['task'] = task
    correct = read(store, report['correctness_report_ref']); boundary = read(store, report['boundary_report_ref'])
    require(correct['build_receipt_ref'] == boundary['build_receipt_ref'], 'correctness changed its one build')
    built = read(store, correct['build_receipt_ref']); attempt_pointer = built['attempt_ref']
    checked_path(store, attempt_pointer['path'], attempt_pointer['sha256'])
    attempt = read(store, attempt_pointer['sha256'])
    require(built['status'] == 'passed' and built['binary']['sha256'] == build['binary_ref']
            and built['source_review_hash'] == attempt['source_review_hash'] == protocol['source_review_ref']
            and attempt['route'] == {'mode': 'exploration', 'anchor_ref': selected['anchor_ref']},
            'original build, mechanical source proof or exploration authority differs')
    review = replay_retained_source_review(store, anchor_ref=selected['anchor_ref'],
        source_review_ref=attempt['independent_review']['sha256'], **trusted_review_refs)
    require(review.get('accepted') is True and review['source_review_ref'] == attempt['independent_review'],
            'original independent model review did not replay or changed before the one build')
    return dict(valid=True, scope='retained_failed_exp_passed_prefix', campaign=campaign,
        parent_status='failed', original_execution_ref=selected['execution_ref'],
        original_duration_seconds=execution['duration_seconds'], original_launch_ref=launch_refs[0],
        original_deadline_monotonic=launch['monotonic_deadline'], original_wall_deadline=original_deadline,
        anchor_ref=selected['anchor_ref'], report_ref=report_ref, protocol_ref=protocol_ref,
        protocol_task_config_ref=protocol['task_config_ref'], collected_task_config_ref=task['config_ref'],
        qualification_registration_ref=report['qualification_registration_ref'],
        source_archive_ref=source_archive_ref, build_receipt_ref=correct['build_receipt_ref'],
        source_review_ref=attempt['independent_review'], measurement_expected=measurement_expected,
        stage_windows=windows, original_profile_window=[profile_start, finish], checks=checks, review=review,
        admission_authority=False, eligible_for_publication=False,
        remaining_requirements=['registered continuation, candidate PMU, final gate and actual successful exit'])


def _scope_amendment(reader, reference, created_at):
    amendment = read(reader, reference)
    expected = dict(schema_version=1, kind='teacher_exp_only_scope_amendment',
        authorization='user_requested_exp_only_release_on_success', release_id='graph-base/1.0.0',
        target={'device': '910C', 'architecture': 'A3', 'cann_version': '9.0.0'}, operators=['exp'],
        validation_45='not_run', postseal_full_tests='not_run', other_rules='draft')
    require(set(amendment) == set(expected) | {'created_at'}
            and all(amendment[k] == v for k, v in expected.items())
            and 0 < number(amendment['created_at']) <= created_at, 'invalid exp-only continuation amendment')
    return amendment


def _profile_oracle(reader, *, record_ref, result_ref, output_hashes, command, cwd, window, workload):
    execution, result = read(reader, record_ref), read(reader, result_ref)
    require(execution['argv'] == command and execution['cwd'] == cwd and execution['environment'] == {}
            and execution['exit_code'] == 0 and execution['error'] is None
            and window[0] <= number(execution['started_at']) <= number(execution['ended_at']) <= window[1]
            and 0 <= execution['ended_at'] - execution['started_at'] <= number(execution['timeout_seconds'])
            and execution['timeout_seconds'] > 0, 'complete PMU oracle execution differs')
    reader.verify_artifact(execution['stderr_hash'])
    require(json.loads(reader.verify_artifact(execution['stdout_hash']).read_text()) == result
            and result.get('passed') is True and result.get('case_id') == workload['case_id'],
            'PMU stdout/result/original oracle failed')
    require(len(output_hashes) == 1, 'Exp PMU must retain its complete output')
    for path, ref in output_hashes.items():
        actual = checked_path(reader, path, ref)
        require(actual.stat().st_size == workload['numel'] * (4 if workload['dtype'] == 'float32' else 2),
                'PMU output is incomplete')


def verify_continuation(reader, continuation_ref, *, campaign_ref, trials, amendment_ref, trusted_review_refs):
    """Actual new exit + unchanged failed prefix + one missing PMU role + full gate."""
    from aprof_runtime.profile_evidence import load_capture_manifest, compare_profiles
    from aprof_runtime.planning import architecture_id
    from aprof_runtime.traces import validate_optimization_trace
    from task_rule_promotion import _ReadOnlyRuntime

    store = reader if isinstance(reader, ReplayCache) else ReplayCache(reader)
    terminal = read(store, continuation_ref)
    require(set(terminal) == {'schema_version', 'kind', 'plan_ref', 'child_result_ref', 'execution_ref',
        'status', 'archive_performed', 'admission_authority', 'finished_at', 'launch_ref', 'job_ref'}
        and terminal['schema_version'] == 1 and terminal['kind'] == 'exp_pmu_continuation_dispatcher_v1'
        and terminal['status'] == 'passed' and terminal['archive_performed'] is False
        and terminal['admission_authority'] is False, 'continuation lacks its real successful dispatcher exit')
    plan_ref = terminal['plan_ref']; plan = read(store, plan_ref)
    _scope_amendment(store, amendment_ref, number(plan['created_at']))
    require(plan['kind'] == 'exp_pmu_continuation_v1' and plan['campaign_ref'] == campaign_ref
            and plan['amendment_ref'] == amendment_ref and plan['trusted_review_refs'] == trusted_review_refs
            and plan['new_roles'] == ['candidate'] and type(plan['actual_new_builds']) is int
            and type(plan['new_formal_timing_pairs']) is int
            and plan['actual_new_builds'] == plan['new_formal_timing_pairs'] == 0,
            'continuation changed its registered scope')
    # The immutable preflight summary is a binding, never a substitute for replay.
    prefix = replay_reused_prefix(store, campaign_ref=campaign_ref,
        trials={op: dict(value, reader=store) for op, value in trials.items()}, trusted_review_refs=trusted_review_refs)
    require(plan['parent_anchor_ref'] == prefix['anchor_ref']
            and read(store, plan['prefix_replay_ref']) == prefix,
            'continuation substituted its original prefix')
    child = read(store, terminal['child_result_ref']); launch = read(store, terminal['launch_ref'])
    job = read(store, terminal['job_ref']); execution = read(store, terminal['execution_ref'])
    root = Path(plan['directory']); release = selected_runtime(); repo = release.parents[2]
    for path, reference in [(root/'plan.json', plan_ref), (root/'launch.json', terminal['launch_ref']),
                            (root/'job.json', terminal['job_ref']), (root/'result.json', terminal['child_result_ref']),
                            (root/'job/execution.json', terminal['execution_ref'])]:
        checked_path(store, path, reference)
    original_root = Path(read(store, read(store, prefix['anchor_ref'])['controller_plan_ref'])['directory'])
    require(root.is_absolute() and root.as_posix() == plan['directory'] and '..' not in root.parts
            and not root.is_relative_to(original_root) and not original_root.is_relative_to(root),
            'invalid or overlapping continuation task directory')
    require(set(launch) == {'schema_version', 'plan_ref', 'started_at', 'started_monotonic', 'deadline_monotonic'}
            and launch['schema_version'] == 1 and launch['plan_ref'] == plan_ref
            and plan['created_at'] <= number(launch['started_at'])
            and number(plan['parent_duration_seconds']) == prefix['original_duration_seconds']
            and plan['total_budget_seconds'] == 5400
            and 0 < number(plan['additional_budget_seconds']) == 5400 - prefix['original_duration_seconds']
            and number(launch['deadline_monotonic']) == number(launch['started_monotonic']) + plan['additional_budget_seconds'],
            'continuation changed the cumulative budget or renewed its new deadline')
    wall_deadline = launch['started_at'] + plan['additional_budget_seconds']
    start, finish = (_timestamp(execution[k]) for k in ('started_at', 'finished_at'))
    require(execution['kind'] == 'aprof_execution_report' and execution['schema_version'] == '1.0.0'
            and execution['job'] == job and execution['status'] == 'passed'
            and execution['exit_code'] == 0 and not execution.get('error')
            and launch['started_at'] <= start <= finish <= wall_deadline
            and 0 < number(execution['duration_seconds']) <= job['timeout_seconds']
            and job['timeout_seconds'] == plan['additional_budget_seconds']
            and job['deadline_monotonic'] == launch['deadline_monotonic']
            and job['cwd'] == str(repo) and job['output_dir'] == str(root/'job')
            and job['physical_device'] == 0 and job['argv'][1:] ==
                [str(repo/'scaffolding/collection/scripts/task_rule_continuation.py'), '--plan', str(root/'plan.json')],
            'actual continuation process escaped its job or original new window')
    env = job['environment']
    require(env['APROF_SKILL_LIB'] == str(release) and env['ASCEND_RT_VISIBLE_DEVICES'] == '0'
            and env['PYTHONDONTWRITEBYTECODE'] == '1', 'continuation job device/runtime differs')
    for pointer in (execution['stdout'], execution['stderr']):
        checked_path(store, pointer['path'], pointer['sha256'])
    for path, ref in plan['frozen_files'].items():
        checked_path(store, path, ref)
    require(plan['frozen_files'].get(job['argv'][1]) == plan['runner_ref']
            and child['schema_version'] == 1 and child['kind'] == 'exp_pmu_continuation_result_v1'
            and child['plan_ref'] == plan_ref and child['status'] == 'passed' and child['error'] is None
            and child['parent_status'] == 'failed' and type(child['actual_new_builds']) is int
            and type(child['new_formal_timing_pairs']) is int
            and child['actual_new_builds'] == child['new_formal_timing_pairs'] == 0
            and child['archive_performed'] is False and child['storage_mode'] == 'local_profile_only'
            and start <= number(child['started_at']) <= number(child['profile_finished_at'])
            <= number(child['gate_started_at']) <= number(child['gate_finished_at'])
            <= number(child['finished_at']) <= finish <= number(terminal['finished_at'])
            and 0 < number(child['duration_seconds']) <= execution['duration_seconds']
            and prefix['original_duration_seconds'] + child['duration_seconds'] <=
                number(child['cumulative_online_seconds']) <= 5400
            and prefix['original_duration_seconds'] + finish - launch['started_at'] <= 5400,
            'continuation child/gate did not finish within the actual cumulative allowance')
    original = read(store, prefix['report_ref']); protocol = read(store, prefix['protocol_ref'])
    old_anchor = read(store, prefix['anchor_ref']); old_plan = read(store, old_anchor['controller_plan_ref'])
    archive = read(store, trusted_review_refs['archive_inventory_ref'])
    frozen_path = str(Path(old_plan['directory']) / 'frozen-candidate.json')
    require(archive['files'][frozen_path]['sha256'] == plan['frozen_candidate_ref'],
            'continuation replaced the original frozen candidate')
    checked_path(store, frozen_path, plan['frozen_candidate_ref'])
    choice = read(store, old_anchor['profile_plan_ref'])
    require(plan['choice'] == choice['choice'] and plan['specs'] == choice['specs'], 'mechanism choice changed')
    task_config = read(store, prefix['checks']['task']['config_ref'])
    task_registration = read(store, prefix['checks']['task']['registration_ref'])
    require(plan['source_hashes'] == prefix['measurement_expected']['source_hashes']
            and plan['binary_ref'] == task_registration['identity']['build']['binary_ref'],
            'continued plan changed the original source or binary')
    case = next(c for c in task_config['cases'] if c['case_id'] == choice['choice']['case_id'])
    old_directory = Path(old_plan['directory'])/'mechanism'
    candidate_config = dict(read(store, protocol['profile_configs']['candidate']),
        command=[t.replace('{cycle_dir}', str(root)) for t in case['command']] + ['--aprof-mechanism-role', 'candidate'])
    require(plan['candidate_profile_config'] == candidate_config
            and child['profile_configs'] == {'baseline': protocol['profile_configs']['baseline'],
                'candidate': content_hash(candidate_config)}
            and child['measurement_expected'] == prefix['measurement_expected'],
            'continuation changed frozen profile command or admitted Task identity')
    profiles = {role: read(store, child[role+'_profile_ref']) for role in ROLES}
    manifests = {role: load_capture_manifest(store, profiles[role]['capture_manifest_hash']) for role in ROLES}
    require(profiles['baseline']['capture_manifest_hash'] == plan['baseline_manifest_ref']
            and profiles['candidate']['capture_manifest_hash'] == child['candidate_manifest_ref'],
            'continued PMU pair changed its capture manifests')
    metric = choice['choice']['metric']
    require(read(store, child['mechanism_report_ref']) == dict(schema_version='1.0.0',
        candidate_id=prefix['measurement_expected']['candidate_id'], hypothesis_basis='heuristic',
        metrics=[dict(name=metric, unit=choice['specs'][metric]['unit'],
            expected_direction=choice['choice']['expected_direction'],
            baseline=profiles['baseline']['metrics'][metric]['value'],
            candidate=profiles['candidate']['metrics'][metric]['value'],
            baseline_profile_hash=child['baseline_profile_ref'], candidate_profile_hash=child['candidate_profile_ref'])]),
        'mechanism report changed the original choice or verified PMU pair')
    old_index = read(store, trials['exp']['index_ref'])['artifacts']
    require(plan['baseline_manifest_ref'] in old_index, 'baseline PMU is not original retained evidence')
    profile_windows = {'baseline': prefix['original_profile_window'],
                       'candidate': [child['started_at'], child['profile_finished_at']]}
    for role in ROLES:
        manifest = manifests[role]
        require(manifest['collector_hash'] == 'sha256:701d51a65e946c00e2ee3b33deec8c2caa974601c6ac744976338cb23c81f2bc',
                'continuation changed the original exact PMU collector')
        _verify_capture_executions(store, manifest, profile_windows[role])
        lower = read(store, manifest['captures'][-1]['log_hash'])['capture']['ended_at']
        directory = old_directory if role == 'baseline' else root
        command = [t.replace('{cycle_dir}', str(directory)) for t in case['verify_commands'][role]]
        values = plan if role == 'baseline' else child
        outputs = values[role+'_output_hashes']
        require(set(outputs) == {p.replace('{cycle_dir}', str(directory)) for p in case['output_files'][role]},
                'PMU output paths changed')
        if role == 'baseline':
            require({values['baseline_oracle_ref'], values['baseline_oracle_result_ref'], *outputs.values()}
                    <= set(old_index), 'baseline oracle/output was not retained by original task')
        _profile_oracle(store, record_ref=values[role+'_oracle_ref'], result_ref=values[role+'_oracle_result_ref'],
            output_hashes=outputs, command=command, cwd=task_config['build']['source_dir'],
            window=[lower, profile_windows[role][1]], workload=case['workload'])
    require(compare_profiles(store, profiles['baseline'], profiles['candidate'], choice['choice']['metric'],
                source_hashes=prefix['measurement_expected']['source_hashes']), 'PMU samples are missing or unstable')
    with retained_producer_scope(store, anchor_ref=prefix['anchor_ref'], trusted_review_refs=trusted_review_refs):
        profile_join = verify_task_profile_window(store, child['mechanism_report_ref'],
            window=[profile_windows['baseline'][0], profile_windows['candidate'][1]],
            measurement_admission_ref=original['measurement_admission_ref'], expected=prefix['measurement_expected'],
            profile_configs=child['profile_configs'])
        machine = _continued_machine(store, child, plan, prefix, plan_ref, campaign_ref, amendment_ref)
        validate_optimization_trace(read(store, machine['trace_ref']), _ReadOnlyRuntime(store))
    hardware = read(store, child['hardware_report_ref'])
    require(architecture_id(hardware.get('soc', '')) == '910c'
            and hardware.get('cann_version', {}).get('version') == '9.0.0'
            and all(m['hardware_hash'] == child['hardware_report_ref'] for m in manifests.values()),
            'continued hardware is not the same 910C/A3 CANN 9.0.0')
    return dict(valid=True, eligible_for_rule=True, eligible_for_publication=False,
        continuation_ref=continuation_ref, parent_status='failed', prefix=prefix, profile=profile_join,
        machine=machine, cumulative_online_seconds=prefix['original_duration_seconds'] + finish - launch['started_at'])


def _continued_machine(reader, child, plan, prefix, plan_ref, campaign_ref, amendment_ref):
    request = read(reader, child['exploration_request_ref']); outcome = read(reader, child['exploration_outcome_ref'])
    trace = read(reader, child['trace_ref']); expected = prefix['measurement_expected']
    require(len(request['candidates']) == len(request['evidence']) == 1 and request['config'] == {}
            and child['formal_outcome'] == outcome['verdict'] == trace['result']['verdict'] == 'production_safe_gain'
            and outcome['request_hash'] == child['exploration_request_ref']
            and trace['result']['exploration_outcome_ref'] == child['exploration_outcome_ref']
            and trace['routing']['mode'] == 'exploration'
            and all(trace['identity'][k] == expected[k] for k in ('operator', 'run_id', 'candidate_id', 'session_id')),
            'continued final gate changed original identity or did not accept')
    frozen = read(reader, plan['frozen_candidate_ref']); candidate, evidence = request['candidates'][0], request['evidence'][0]
    require(request['frozen_manifest_hash'] == frozen['frozen_manifest_hash'] and candidate == frozen['candidate']
            and candidate['candidate_id'] == evidence['candidate_id'] == expected['candidate_id']
            and candidate['source_hashes'] == expected['source_hashes'], 'continued gate changed the single candidate')
    report = read(reader, prefix['report_ref'])
    bindings = dict(source_review=prefix['source_review_ref']['sha256'], build_log=prefix['build_receipt_ref'],
        accuracy_report=report['correctness_report_ref'], boundary_report=report['boundary_report_ref'],
        measurement_admission=report['measurement_admission_ref'], measurement_report=expected['measurement_report_ref'],
        mechanism_report=child['mechanism_report_ref'], hardware_report=child['hardware_report_ref'],
        qualification_campaign=campaign_ref, qualification_registration=prefix['qualification_registration_ref'],
        continuation_plan=plan_ref, continuation_amendment=amendment_ref)
    require(all(evidence['artifacts'].get(k) == ref for k, ref in bindings.items())
            and trace['identity']['split'] == 'train' and trace['identity']['task_id'] == 'exp'
            and trace['identity']['source_parent_hash'] == expected['source_hashes']['baseline']
            and trace['workload']['case_ids'] == trace['validation']['timing_case_ids'] == list(range(1, 21))
            and trace['validation']['case_count'] == trace['validation']['passed_count'] == 20
            and trace['workload']['hardware_fingerprint'] == child['hardware_report_ref'],
            'continued final gate substituted reused evidence or full-case coverage')
    return dict(trace_ref=child['trace_ref'], request_ref=child['exploration_request_ref'],
        outcome_ref=child['exploration_outcome_ref'], hardware_report_ref=child['hardware_report_ref'],
        source_review_ref=prefix['source_review_ref'], verdict=outcome['verdict'],
        retained_source_review_replay_complete=True)


def verify_continuation_promotion(reader, promotion_ref, *, campaign_ref, trials, amendment_ref,
                                  trusted_before_inventory_ref, repo, release, trusted_review_refs):
    import task_rule_promotion as promotion
    repo, release = Path(repo).resolve(), Path(release).resolve()
    require(selected_runtime() == release == repo/'skill-libs/graph-base/1.0.0', 'wrong promotion release')
    receipt = read(reader, promotion_ref)
    require(set(receipt) == promotion.KEYS | {'continuation_ref', 'amendment_ref'}
            and receipt['schema_version'] == 1 and receipt['kind'] == 'teacher_exp_continuation_promotion'
            and receipt['wiki_id'] == 'exp-tile8192' and receipt['proposal_id']
            and receipt['target_skill'] == promotion.SCOPES['exp-tile8192']['target_skill']
            and receipt['source_keys'] == promotion.SCOPES['exp-tile8192']['source_keys']
            and receipt['campaign_ref'] == campaign_ref and receipt['amendment_ref'] == amendment_ref,
            'unsupported or mixed continuation promotion')
    continued = verify_continuation(reader, receipt['continuation_ref'], campaign_ref=campaign_ref,
        trials=trials, amendment_ref=amendment_ref, trusted_review_refs=trusted_review_refs)
    machine = continued['machine']
    require(receipt['selected_run_id'] == continued['prefix']['measurement_expected']['run_id']
            and receipt['trace_ref'] == machine['trace_ref']
            and receipt['hardware_report_ref'] == machine['hardware_report_ref'], 'promotion selected another continuation')
    edit = promotion._skills(reader, receipt, release, trusted_before_inventory_ref)
    sources = promotion._sources(reader, receipt, read(reader, campaign_ref), repo, release)
    return dict(valid=True, operator='exp', scope='one_operator_teacher_continuation_edit',
        promotion_ref=promotion_ref, continuation=continued, campaign_ref=campaign_ref, amendment_ref=amendment_ref,
        edit=edit, sources=sources, machine=machine, eligible_for_teacher_edit=True,
        eligible_for_publication=False, graph_policy_eligible=False)
