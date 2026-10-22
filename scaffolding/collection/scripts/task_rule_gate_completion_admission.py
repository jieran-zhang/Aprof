"""Replay a CPU-only gate completion after two honestly failed Exp tasks.

The original Task samples and the later candidate PMU samples keep their own
windows, failures and costs. No failed dispatcher is relabeled successful.
"""
import copy
import json
from pathlib import Path

import task_rule_continuation_admission as previous
from timing_admission import ReplayCache, checked_path, content_hash, number, read, require


MISSING_REQUEST = 'sha256:8302ca30e327e57d149ebd3aa5dde652b76923870a62a932a67b72404d4fa3e4'
TERMINAL_KEYS = {'schema_version', 'kind', 'plan_ref', 'child_result_ref', 'execution_ref',
    'status', 'archive_performed', 'admission_authority', 'finished_at', 'launch_ref', 'job_ref'}


def _process(store, reference, *, kind, status, exit_code, allowance):
    """Bind one actual dispatcher exit to its immutable job and own deadline."""
    terminal = read(store, reference)
    require(set(terminal) == TERMINAL_KEYS and terminal['schema_version'] == 1
            and terminal['kind'] == kind and terminal['status'] == status
            and terminal['archive_performed'] is False and terminal['admission_authority'] is False,
            'gate completion changed a real dispatcher terminal')
    plan = read(store, terminal['plan_ref']); child = read(store, terminal['child_result_ref'])
    launch = read(store, terminal['launch_ref']); job = read(store, terminal['job_ref'])
    execution = read(store, terminal['execution_ref'])
    root = Path(plan['directory']); release = previous.selected_runtime(); repo = release.parents[2]
    require(root.is_absolute() and root.as_posix() == plan['directory'] and '..' not in root.parts,
            'invalid completion directory')
    for path, ref in ((root/'plan.json', terminal['plan_ref']), (root/'launch.json', terminal['launch_ref']),
                     (root/'job.json', terminal['job_ref']), (root/'result.json', terminal['child_result_ref']),
                     (root/'job/execution.json', terminal['execution_ref'])):
        checked_path(store, path, ref)
    require(set(launch) == {'schema_version', 'plan_ref', 'started_at', 'started_monotonic', 'deadline_monotonic'}
            and launch['schema_version'] == 1 and launch['plan_ref'] == terminal['plan_ref']
            and number(plan['created_at']) <= number(launch['started_at'])
            and number(plan['additional_budget_seconds']) == allowance > 0
            and number(launch['deadline_monotonic']) == number(launch['started_monotonic']) + allowance,
            'completion renewed or substituted its budget')
    start, finish = (previous._timestamp(execution[k]) for k in ('started_at', 'finished_at'))
    runner = 'task_rule_continuation.py' if kind == 'exp_pmu_continuation_dispatcher_v1' else 'task_rule_gate_completion.py'
    require(execution['kind'] == 'aprof_execution_report' and execution['schema_version'] == '1.0.0'
            and execution['job'] == job and execution['status'] == status
            and execution['exit_code'] == exit_code and not execution.get('error')
            and launch['started_at'] <= start <= finish <= launch['started_at'] + allowance
            and 0 < number(execution['duration_seconds']) <= allowance
            and job['timeout_seconds'] == allowance and job['deadline_monotonic'] == launch['deadline_monotonic']
            and job['cwd'] == str(repo) and job['output_dir'] == str(root/'job') and job['physical_device'] == 0
            and job['argv'][1:] == [str(repo/'scaffolding/collection/scripts'/runner), '--plan', str(root/'plan.json')],
            'completion execution differs from its original actual job/window')
    env = job['environment']
    require(env['APROF_SKILL_LIB'] == str(release) and env['ASCEND_RT_VISIBLE_DEVICES'] == '0'
            and env['PYTHONDONTWRITEBYTECODE'] == '1', 'completion device/runtime changed')
    for pointer in (execution['stdout'], execution['stderr']):
        checked_path(store, pointer['path'], pointer['sha256'])
    for path, ref in plan['frozen_files'].items():
        checked_path(store, path, ref)
    require(job['argv'][1] in plan['frozen_files']
            and child['schema_version'] == 1 and child['plan_ref'] == terminal['plan_ref']
            and child['status'] == status and child['parent_status'] == 'failed'
            and child['archive_performed'] is False and child['storage_mode'] == 'local_profile_only'
            and type(child['actual_new_builds']) is type(child['new_formal_timing_pairs']) is int
            and child['actual_new_builds'] == child['new_formal_timing_pairs'] == 0
            and start <= number(child['started_at']) <= number(child['finished_at']) <= finish
            <= number(terminal['finished_at'])
            and 0 < number(child['duration_seconds']) <= execution['duration_seconds'],
            'completion child escaped its process or performed another build/timing')
    return dict(terminal=terminal, plan=plan, child=child, execution=execution,
                launch=launch, root=root, start=start, finish=finish)


def _profiles(store, prefix, pmu, child, trials):
    """Replay retained roles only, using each role's actual collection window."""
    from aprof_runtime.profile_evidence import load_capture_manifest, compare_profiles
    from aprof_runtime.planning import architecture_id
    plan, failed = pmu['plan'], pmu['child']
    original = read(store, prefix['report_ref']); protocol = read(store, prefix['protocol_ref'])
    anchor = read(store, prefix['anchor_ref']); original_plan = read(store, anchor['controller_plan_ref'])
    choice = read(store, anchor['profile_plan_ref'])
    require(plan['choice'] == choice['choice'] and plan['specs'] == choice['specs'], 'retained PMU choice changed')
    config = read(store, prefix['checks']['task']['config_ref'])
    registration = read(store, prefix['checks']['task']['registration_ref'])
    require(plan['source_hashes'] == prefix['measurement_expected']['source_hashes']
            and plan['binary_ref'] == registration['identity']['build']['binary_ref'],
            'retained PMU source/binary changed')
    case = next(c for c in config['cases'] if c['case_id'] == choice['choice']['case_id'])
    wanted = dict(read(store, protocol['profile_configs']['candidate']), command=
        [t.replace('{cycle_dir}', str(pmu['root'])) for t in case['command']] + ['--aprof-mechanism-role', 'candidate'])
    require(plan['candidate_profile_config'] == wanted and child['profile_configs'] ==
            {'baseline': protocol['profile_configs']['baseline'], 'candidate': content_hash(wanted)}
            and child['measurement_expected'] == prefix['measurement_expected'],
            'gate completion changed retained PMU configuration')
    for key in ('candidate_manifest_ref', 'candidate_profile_ref', 'candidate_oracle_ref',
                'candidate_oracle_result_ref', 'candidate_output_hashes'):
        require(child[key] == failed[key], 'gate completion substituted a retained candidate PMU artifact')
    profiles = {role: read(store, child[role+'_profile_ref']) for role in previous.ROLES}
    manifests = {role: load_capture_manifest(store, profiles[role]['capture_manifest_hash']) for role in previous.ROLES}
    require(profiles['baseline']['capture_manifest_hash'] == plan['baseline_manifest_ref']
            and profiles['candidate']['capture_manifest_hash'] == failed['candidate_manifest_ref'],
            'gate completion changed PMU manifests')
    metric = choice['choice']['metric']
    require(read(store, child['mechanism_report_ref']) == dict(schema_version='1.0.0',
        candidate_id=prefix['measurement_expected']['candidate_id'], hypothesis_basis='heuristic', metrics=[dict(
            name=metric, unit=choice['specs'][metric]['unit'], expected_direction=choice['choice']['expected_direction'],
            baseline=profiles['baseline']['metrics'][metric]['value'], candidate=profiles['candidate']['metrics'][metric]['value'],
            baseline_profile_hash=child['baseline_profile_ref'], candidate_profile_hash=child['candidate_profile_ref'])]),
        'gate completion mechanism differs from the retained pair')
    old_index = read(store, trials['exp']['index_ref'])['artifacts']
    require(plan['baseline_manifest_ref'] in old_index, 'baseline PMU was not original retained evidence')
    windows = {'baseline': prefix['original_profile_window'],
               'candidate': [failed['started_at'], failed['profile_finished_at']]}
    for role in previous.ROLES:
        manifest = manifests[role]
        require(manifest['collector_hash'] == 'sha256:701d51a65e946c00e2ee3b33deec8c2caa974601c6ac744976338cb23c81f2bc',
                'gate completion changed the exact retained PMU collector')
        previous._verify_capture_executions(store, manifest, windows[role])
        lower = read(store, manifest['captures'][-1]['log_hash'])['capture']['ended_at']
        directory = Path(original_plan['directory'])/'mechanism' if role == 'baseline' else pmu['root']
        values = plan if role == 'baseline' else failed
        outputs = values[role+'_output_hashes']
        require(set(outputs) == {p.replace('{cycle_dir}', str(directory)) for p in case['output_files'][role]},
                'retained PMU output paths changed')
        if role == 'baseline':
            require({values['baseline_oracle_ref'], values['baseline_oracle_result_ref'], *outputs.values()}
                    <= set(old_index), 'baseline oracle/output was not retained by original task')
        _retained_oracle(store, record_ref=values[role+'_oracle_ref'], result_ref=values[role+'_oracle_result_ref'],
            output_hashes=outputs, command=[t.replace('{cycle_dir}', str(directory)) for t in case['verify_commands'][role]],
            cwd=config['build']['source_dir'], window=[lower, windows[role][1]], workload=case['workload'])
    require(compare_profiles(store, profiles['baseline'], profiles['candidate'], metric,
        source_hashes=prefix['measurement_expected']['source_hashes']), 'retained PMU pair is missing or unstable')
    with previous.retained_producer_scope(store, anchor_ref=prefix['anchor_ref'], trusted_review_refs=plan['trusted_review_refs']):
        joined = previous.verify_task_profile_window(store, child['mechanism_report_ref'],
            window=[windows['baseline'][0], windows['candidate'][1]],
            measurement_admission_ref=original['measurement_admission_ref'], expected=prefix['measurement_expected'],
            profile_configs=child['profile_configs'])
    hardware = read(store, child['hardware_report_ref'])
    require(architecture_id(hardware.get('soc', '')) == '910c'
            and hardware.get('cann_version', {}).get('version') == '9.0.0'
            and all(m['hardware_hash'] == child['hardware_report_ref'] for m in manifests.values()),
            'gate completion hardware changed')
    return joined


def _retained_oracle(store, *, record_ref, result_ref, output_hashes, command, cwd, window, workload):
    """Exact 701d collector receipts have no environment/timeout declaration.

The caller binds that collector, frozen argv and actual parent job/window.
Absent fields are not manufactured and mixed stdout/stderr is never parsed.
"""
    execution, result = read(store, record_ref), read(store, result_ref)
    require(set(execution) == {'argv', 'cwd', 'started_at', 'ended_at', 'exit_code',
                               'error', 'stdout_hash', 'stderr_hash'}
            and execution['argv'] == command and execution['cwd'] == cwd
            and execution['exit_code'] == 0 and execution['error'] is None
            and window[0] <= number(execution['started_at']) <= number(execution['ended_at']) <= window[1],
            'retained PMU oracle execution differs from the exact original collector')
    store.verify_artifact(execution['stderr_hash'])
    require(json.loads(store.verify_artifact(execution['stdout_hash']).read_text()) == result
            and result.get('passed') is True and result.get('case_id') == workload['case_id'],
            'retained PMU stdout/result/original oracle failed')
    require(len(output_hashes) == 1, 'Exp PMU must retain its complete output')
    for path, ref in output_hashes.items():
        actual = checked_path(store, path, ref)
        require(actual.stat().st_size == workload['numel'] * (4 if workload['dtype'] == 'float32' else 2),
                'retained PMU output is incomplete')


def verify_gate_continuation(reader, continuation_ref, *, campaign_ref, trials, amendment_ref, trusted_review_refs):
    """Require both real failures, retained full evidence and a new successful CPU gate."""
    from aprof_runtime.traces import validate_optimization_trace
    from task_rule_promotion import _ReadOnlyRuntime
    store = reader if isinstance(reader, ReplayCache) else ReplayCache(reader)
    terminal = read(store, continuation_ref); plan = read(store, terminal['plan_ref'])
    previous._scope_amendment(store, amendment_ref, number(plan['created_at']))
    require(plan['kind'] == 'exp_gate_completion_v1' and plan['campaign_ref'] == campaign_ref
            and plan['amendment_ref'] == amendment_ref and plan['trusted_review_refs'] == trusted_review_refs
            and plan['total_budget_seconds'] == 5400
            and all(type(plan[k]) is int and plan[k] == 0 for k in
                    ('actual_new_builds', 'new_formal_timing_pairs', 'actual_new_captures')),
            'unsupported gate-only completion plan')
    prefix = previous.replay_reused_prefix(store, campaign_ref=campaign_ref,
        trials={op: dict(value, reader=store) for op, value in trials.items()}, trusted_review_refs=trusted_review_refs)
    original_cost = prefix['original_duration_seconds']
    pmu = _process(store, plan['pmu_continuation_ref'], kind='exp_pmu_continuation_dispatcher_v1',
                   status='failed', exit_code=2, allowance=5400-original_cost)
    old, failed = pmu['plan'], pmu['child']
    pmu_cost = pmu['finish'] - pmu['launch']['started_at']
    require(old['kind'] == 'exp_pmu_continuation_v1' and old['campaign_ref'] == campaign_ref
            and old['amendment_ref'] == amendment_ref and old['trusted_review_refs'] == trusted_review_refs
            and old['new_roles'] == ['candidate'] and old['actual_new_builds'] == old['new_formal_timing_pairs'] == 0
            and old['parent_anchor_ref'] == prefix['anchor_ref'] and old['parent_duration_seconds'] == original_cost
            and old['total_budget_seconds'] == 5400 and plan['pmu_plan_ref'] == pmu['terminal']['plan_ref']
            and failed['kind'] == 'exp_pmu_continuation_result_v1'
            and failed['error'] == {'type': 'ValueError', 'message': 'continuation evidence not found: '+MISSING_REQUEST}
            and failed['started_at'] <= number(failed['profile_finished_at']) <= number(failed['gate_started_at'])
            <= failed['finished_at']
            and original_cost + failed['duration_seconds'] <= number(failed['cumulative_online_seconds']) <= 5400
            and read(store, old['prefix_replay_ref']) == read(store, plan['prefix_replay_ref']) == prefix,
            'retained PMU task did not fail solely at the known request-registration boundary')
    require(plan['original_parent_seconds'] == original_cost and plan['pmu_execution_seconds'] == pmu_cost
            and pmu['finish'] <= number(plan['created_at'])
            and all(plan[k] == old[k] for k in ('frozen_candidate_ref', 'source_hashes', 'binary_ref')),
            'gate completion substituted a previous cost/source or started before PMU exit')
    new = _process(store, continuation_ref, kind='exp_gate_completion_dispatcher_v1',
                   status='passed', exit_code=0, allowance=5400-original_cost-pmu_cost)
    child = new['child']
    require(child['kind'] == 'exp_gate_completion_result_v1' and child['error'] is None
            and child['pmu_continuation_ref'] == plan['pmu_continuation_ref']
            and type(child['actual_new_captures']) is int and child['actual_new_captures'] == 0
            and child['started_at'] <= number(child['gate_started_at']) <= number(child['gate_finished_at'])
            <= child['finished_at']
            and original_cost + pmu_cost + child['duration_seconds'] <= number(child['cumulative_online_seconds']) <= 5400
            and original_cost + pmu_cost + new['finish'] - new['launch']['started_at'] <= 5400
            and not new['root'].is_relative_to(pmu['root']) and not pmu['root'].is_relative_to(new['root']),
            'gate-only completion recaptured or exceeded its remaining cumulative budget')
    archive = read(store, trusted_review_refs['archive_inventory_ref'])
    source_plan = read(store, read(store, prefix['anchor_ref'])['controller_plan_ref'])
    frozen_path = str(Path(source_plan['directory'])/'frozen-candidate.json')
    require(archive['files'][frozen_path]['sha256'] == old['frozen_candidate_ref'], 'original frozen candidate changed')
    checked_path(store, frozen_path, old['frozen_candidate_ref'])
    joined = _profiles(store, prefix, pmu, child, trials)
    with previous.retained_producer_scope(store, anchor_ref=prefix['anchor_ref'], trusted_review_refs=trusted_review_refs):
        machine = previous._continued_machine(store, child, old, prefix, terminal['plan_ref'], campaign_ref, amendment_ref)
        original_request = copy.deepcopy(read(store, machine['request_ref']))
        original_request['evidence'][0]['artifacts']['continuation_plan'] = plan['pmu_plan_ref']
        require(content_hash(original_request) == MISSING_REQUEST,
                'completed gate is not the exact retained request that failed local registration')
        validate_optimization_trace(read(store, machine['trace_ref']), _ReadOnlyRuntime(store))
    return dict(valid=True, eligible_for_rule=True, eligible_for_publication=False, continuation_ref=continuation_ref,
        parent_status='failed', pmu_parent_status='failed', prefix=prefix, profile=joined, machine=machine,
        pmu_continuation_ref=plan['pmu_continuation_ref'], original_parent_seconds=original_cost,
        pmu_execution_seconds=pmu_cost, gate_execution_seconds=new['execution']['duration_seconds'],
        cumulative_online_seconds=original_cost+pmu_cost+new['finish']-new['launch']['started_at'])


def verify_continuation_promotion(reader, promotion_ref, *, campaign_ref, trials, amendment_ref,
                                  trusted_before_inventory_ref, repo, release, trusted_review_refs):
    import task_rule_promotion as promotion
    repo, release = Path(repo).resolve(), Path(release).resolve()
    require(previous.selected_runtime() == release == repo/'skill-libs/graph-base/1.0.0', 'wrong promotion release')
    receipt = read(reader, promotion_ref)
    require(set(receipt) == promotion.KEYS | {'continuation_ref', 'amendment_ref'}
            and receipt['schema_version'] == 1 and receipt['kind'] == 'teacher_exp_continuation_promotion'
            and receipt['wiki_id'] == 'exp-tile8192' and receipt['proposal_id']
            and receipt['target_skill'] == promotion.SCOPES['exp-tile8192']['target_skill']
            and receipt['source_keys'] == promotion.SCOPES['exp-tile8192']['source_keys']
            and receipt['campaign_ref'] == campaign_ref and receipt['amendment_ref'] == amendment_ref,
            'unsupported or mixed gate-completion promotion')
    continued = verify_gate_continuation(reader, receipt['continuation_ref'], campaign_ref=campaign_ref,
        trials=trials, amendment_ref=amendment_ref, trusted_review_refs=trusted_review_refs)
    machine = continued['machine']
    require(receipt['selected_run_id'] == continued['prefix']['measurement_expected']['run_id']
            and receipt['trace_ref'] == machine['trace_ref']
            and receipt['hardware_report_ref'] == machine['hardware_report_ref'], 'promotion selected another gate completion')
    edit = promotion._skills(reader, receipt, release, trusted_before_inventory_ref)
    sources = promotion._sources(reader, receipt, read(reader, campaign_ref), repo, release)
    return dict(valid=True, operator='exp', scope='one_operator_teacher_continuation_edit',
        promotion_ref=promotion_ref, continuation=continued, campaign_ref=campaign_ref, amendment_ref=amendment_ref,
        edit=edit, sources=sources, machine=machine, eligible_for_teacher_edit=True,
        eligible_for_publication=False, graph_policy_eligible=False)
