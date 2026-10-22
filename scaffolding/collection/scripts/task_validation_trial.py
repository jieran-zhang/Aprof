"""Validation-candidate orchestration under the original supervisor.

Only task-local evidence is written. The caller supplies the real reviewed draft
and candidate execution planning artifacts; this module invents neither routes
nor architecture evidence. The dispatcher still owns the actual final exit.
"""
import datetime as dt
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import time

import task_validation_controller as candidate
import task_candidate_pmu as pmu
from validation_host_evaluator import Commands
from timing_admission import require, number
from aprof_runtime import __version__ as runtime_version
from aprof_runtime.attestation import attest_route
from aprof_runtime.contracts import CandidateDraft, CandidateEpisode, Context, GateRequest, RouteDecision
from aprof_runtime.gates import prepare_gate_request
from aprof_runtime.graph import load_snapshot
from aprof_runtime.jsonio import content_hash, file_hash, to_primitive
from aprof_runtime.measurement_entry import replay_current_measurement_admission
from aprof_runtime.planning import select_dispatch, validate_planning_admission, validate_planning_contract, UNKEYED_MODE

bridge = candidate.bridge
ENABLED_IN_1_0 = False
PHASES = ('correctness', 'task_measurement', 'profile', 'online_admission')
KIND = 'validation_candidate_trial'
PRODUCERS = ('task_validation_trial.py', 'task_baseline_context.py', 'feedback_attempt_verify.py')


def _read(local, reference):
    return json.loads(local.verify_artifact(reference).read_text())


def _save(local, path, value):
    bridge.save(path, value)
    return local.register_artifact(path)


def _execution_context(local, baseline_context, execution_context, draft):
    """Permit explicit planning outputs, never new baseline facts/predicates."""
    base, actual = Context.from_dict(baseline_context), Context.from_dict(execution_context)
    require(all(getattr(base, k) == getattr(actual, k) for k in
        ('schema_version', 'task_id', 'operator', 'hardware_fingerprint', 'budget')),
        'candidate execution context changed qualified identity or budget')
    workload_keys = {'implementation_source_hash', 'plan_basis_source_hash', 'tiling_key', 'workload_group', 'complete_call_ref'}
    evidence_keys = {'optimization_stage', 'parallel_plan', 'parallel_plan_ref', 'dispatch_plan', 'dispatch_plan_ref'}
    require({k:v for k,v in base.workload.items() if k not in workload_keys}
            == {k:v for k,v in actual.workload.items() if k not in workload_keys}
        and {k:v for k,v in base.evidence.items() if k not in evidence_keys}
            == {k:v for k,v in actual.evidence.items() if k not in evidence_keys},
        'candidate changed qualified metadata, architecture or predicate evidence')
    require(actual.evidence.get('optimization_stage') == 'execution', 'candidate needs explicit execution planning')
    for key in ('architecture_profile', 'parallel_plan', 'dispatch_plan'):
        require(_read(local, actual.evidence[key+'_ref']) == actual.evidence[key],
                'candidate planning artifact differs from its indexed bytes')
    validate_planning_admission(actual, draft)
    return actual


def _inputs(local, *, candidate_plan_ref, draft_ref, registry_ref, derivation_ref):
    plan, _, _ = candidate._checked_candidate_plan(local, candidate_plan_ref)
    require(plan['case_ids'] == list(range(1, 21)), 'candidate requires all original 20 cases')
    route = candidate._pointer(local, plan['route'])
    registry = _read(local, registry_ref)
    require(route['registry_ref']['sha256'] == registry_ref
        and registry['derivation_ref'] == derivation_ref, 'candidate substituted its trusted route registry')
    from task_baseline_context import replay_baseline_contexts
    trusted = replay_baseline_contexts(local, derivation_ref=derivation_ref,
        qualification_ref=plan['baseline_qualification']['sha256'], registry_ref=registry_ref)
    require(trusted['valid'] is True and trusted['routes'][route['context_id']] == route['route'],
            'qualified baseline route did not independently replay')
    draft = CandidateDraft.from_dict(_read(local, draft_ref))
    submitted = json.loads((Path(plan['workspace'])/'candidate_plan.json').read_text())
    require(draft.candidate_id == plan['candidate_id'] and draft.session_id == plan['session_id']
        and to_primitive(draft.source_hashes) == plan['source_hashes']
        and to_primitive(draft.route) == route['route']
        and draft.transformation_id == submitted['transformation_id']
        and draft.transformation_id != 'transformation.noop' and draft.parameters == submitted['parameters']
        and draft.parent_candidate_id is None, 'candidate draft changed reviewed source/route/parameters')
    from feedback_attempt_verify import expected_patch
    sources = {role:{name:local.verify_artifact(reference).read_bytes()
        for name,reference in plan['roles'][role]['files'].items()} for role in bridge.ROLES}
    require(local.verify_artifact(draft.patch_artifact_hash).read_bytes()
        == expected_patch(sources['baseline'], sources['candidate']), 'candidate patch differs from reviewed sources')
    graph_path = local.verify_artifact(registry['graph']['sha256'])
    require(file_hash(registry['graph']['path']) == registry['graph']['sha256'], 'qualified graph bytes changed')
    graph, _ = load_snapshot(graph_path)
    require(content_hash(graph) == route['graph_hash'], 'candidate graph differs from reviewed route')
    transformation = next(item for item in graph['transformations'] if item['id'] == draft.transformation_id)
    require(draft.transformation_version == transformation['version'], 'candidate transformation version changed')
    return plan, route, trusted, draft, graph


def _submitted_planning(local, plan, trusted, draft, graph):
    """Project the reviewed submission; fill identities, never algorithm facts."""
    path = Path(plan['workspace'])/'candidate_plan.json'
    review = candidate._pointer(local, plan['independent_review'])
    require(review['plan_sha256'] == file_hash(path), 'submitted planning differs from the reviewed plan')
    submitted = json.loads(path.read_text())
    contexts = trusted['contexts']
    require(len(contexts) == 20 and {v['workload']['case_id'] for v in contexts.values()} == set(range(1, 21))
        and [c['case_id'] for c in plan['cases']] == list(range(1, 21)), 'planning requires all 20 original workloads')
    profile_refs = {v['evidence']['architecture_profile_ref'] for v in contexts.values()}
    require(len(profile_refs) == 1, 'qualified architecture differs across original cases')
    architecture_ref = next(iter(profile_refs))
    def bind(key, identity):
        value = submitted.get(key)
        require(isinstance(value, dict), 'same candidate submission must include '+key)
        require(all(k not in value or value[k] == v for k,v in identity.items()),
                'submitted planning changed machine-bound identity')
        return validate_planning_contract(key, {**value, **identity})
    parallel = bind('parallel_plan', dict(schema_version='1.0.0', operator=plan['operator'],
        source_hash=plan['source_hashes']['baseline'], architecture_profile_ref=architecture_ref))
    for group in parallel['groups']:
        for reference in group['selection_evidence']: local.verify_artifact(reference)
    parallel_ref = content_hash(parallel)
    if submitted.get('dispatch_plan', {}).get('mode') == UNKEYED_MODE:
        from task_baseline_context import unkeyed_dispatch_value
        identity = unkeyed_dispatch_value(plan,parallel,parallel_ref,
            dispatch_id=submitted['dispatch_plan'].get('dispatch_id'))
        dispatch = bind('dispatch_plan', identity)
    else:
        dispatch = bind('dispatch_plan', dict(schema_version='1.0.0', operator=plan['operator'],
            source_hash=plan['source_hashes']['candidate'], architecture_profile_ref=architecture_ref,
            parallel_plan_ref=parallel_ref, plan_basis_source_hash=plan['source_hashes']['baseline'],
            implementation_source_hash=plan['source_hashes']['candidate']))
    dispatch_ref = content_hash(dispatch); projected = {}
    cases = {c['case_id']:c for c in plan['cases']}
    for name, original in contexts.items():
        value = deepcopy(original); case = cases[value['workload']['case_id']]
        require(value['workload']['original_metadata_ref'] == case['metadata_ref']
            and value['workload']['original_workload'] == case['workload'], 'planning changed original case metadata')
        selected = select_dispatch(dispatch, value['workload']['metadata'])
        value['workload'].update(implementation_source_hash=plan['source_hashes']['candidate'],
            plan_basis_source_hash=plan['source_hashes']['baseline'],
            tiling_key=selected.get('tiling_key'), workload_group=selected['group_id'])
        if dispatch.get('mode') == UNKEYED_MODE:
            value['workload'].pop('tiling_key', None)
            value['workload']['complete_call_ref'] = content_hash(selected)
        value['evidence'].update(optimization_stage='execution', parallel_plan=parallel,
            parallel_plan_ref=parallel_ref, dispatch_plan=dispatch, dispatch_plan_ref=dispatch_ref)
        actual = Context.from_dict(value)
        validate_planning_admission(actual, draft)
        attest_route(context=actual, recorded=RouteDecision.from_dict(trusted['routes'][name]), graph_snapshot=graph,
            graph_hash=content_hash(graph), behavior_policy_checkpoint=None, policy_checkpoint_hash=None)
        projected[name] = value
    return parallel, dispatch, projected


def _submitted_selections(plan):
    choice = json.loads((Path(plan['workspace'])/'candidate_plan.json').read_text()).get('mechanism')
    require(isinstance(choice, dict) and set(choice) == {'case_id','kernel','metric','expected_direction'}
        and type(choice['case_id']) is int and choice['case_id'] == plan['profile']['case_id']
        and choice['kernel'] in plan['profile']['kernels'] and choice['metric'] in plan['profile']['metrics']
        and choice['expected_direction'] in ('increase','decrease'), 'submitted PMU choice differs from frozen scope')
    return [dict(name=choice['metric'], kernel=choice['kernel'], expected_direction=choice['expected_direction'],
                 unit=plan['profile']['metrics'][choice['metric']]['unit'])]


def materialize_submitted_planning(local, *, candidate_plan_ref, draft_ref, registry_ref, derivation_ref):
    """Accept planning JSON inside submit_candidate(plan); no extra file tool.

    All semantic/group/dispatch declarations must be submitted. Identity fields
    may be omitted; supplied conflicting identities are rejected, not replaced.
    """
    plan, route, trusted, draft, graph = _inputs(local, candidate_plan_ref=candidate_plan_ref,
        draft_ref=draft_ref, registry_ref=registry_ref, derivation_ref=derivation_ref)
    candidate._local(local, plan['deadline_monotonic'])
    parallel, dispatch, contexts = _submitted_planning(local, plan, trusted, draft, graph)
    selections = _submitted_selections(plan)
    result = dict(parallel_plan_ref=local.register_json(parallel), dispatch_plan_ref=local.register_json(dispatch),
        execution_context_ref=local.register_json(contexts[route['context_id']]),
        submitted_plan_ref=local.register_artifact(Path(plan['workspace'])/'candidate_plan.json'),
        independent_review_ref=plan['independent_review'], selections=selections, checked_case_ids=list(range(1,21)))
    bridge.remaining(plan['deadline_monotonic'])
    return result


def _checked_trial(local, trial_ref):
    trial = _read(local, trial_ref)
    require(set(trial) == {'schema_version', 'kind', 'candidate_plan_ref', 'draft_ref', 'registry_ref',
        'derivation_ref', 'execution_context_ref', 'selections', 'directory', 'created_at', 'producer_refs'}
        and trial['schema_version'] == 1 and trial['kind'] == KIND,
        'candidate trial registration differs')
    require(trial['producer_refs'] == {str(Path(__file__).with_name(name)):file_hash(Path(__file__).with_name(name))
        for name in PRODUCERS}, 'candidate trial producer changed')
    for reference in trial['producer_refs'].values(): local.verify_artifact(reference)
    plan, route, trusted, draft, graph = _inputs(local, **{k:trial[k] for k in
        ('candidate_plan_ref','draft_ref','registry_ref','derivation_ref')})
    launch = _read(local, plan['launch_ref'])
    require(launch['started_at'] <= number(trial['created_at']) <= launch['started_at'] + plan['budget_seconds'],
            'candidate trial was registered outside the original task')
    root = candidate.builder._path(trial['directory'])
    require(root.is_relative_to(local.directory.parent), 'candidate trial must remain task-local')
    require(bridge.timing.old.select_mount(Path('/proc/self/mountinfo').read_text(), root)['filesystem_type']
        in bridge.timing.old.LOCAL_PROFILE_FILESYSTEMS, 'candidate trial requires a local filesystem')
    _, _, contexts = _submitted_planning(local, plan, trusted, draft, graph)
    supplied = _read(local, trial['execution_context_ref'])
    require(supplied == contexts[route['context_id']], 'execution Context differs from the reviewed planning submission')
    context = _execution_context(local, trusted['contexts'][route['context_id']], supplied, draft)
    require(trial['selections'] == _submitted_selections(plan), 'candidate changed its submitted PMU hypothesis')
    pmu._selections(plan['pmu_scope'], trial['selections'])
    return trial, plan, to_primitive(context), to_primitive(draft), graph


def prepare_trial(local, *, candidate_plan_ref, draft_ref, registry_ref, derivation_ref,
                  execution_context_ref, selections, destination):
    """Bind existing trusted inputs; does not build, collect, or author a draft."""
    plan = _read(local, candidate_plan_ref)
    candidate._local(local, plan['deadline_monotonic'])
    root = candidate.builder._path(destination)
    require(root.is_relative_to(local.directory.parent) and not root.exists(), 'trial destination is not fresh/local')
    trial = dict(schema_version=1, kind=KIND, candidate_plan_ref=candidate_plan_ref, draft_ref=draft_ref,
        registry_ref=registry_ref, derivation_ref=derivation_ref, execution_context_ref=execution_context_ref,
        selections=selections, directory=str(root), created_at=time.time(), producer_refs={
            str(Path(__file__).with_name(name)):local.register_artifact(Path(__file__).with_name(name)) for name in PRODUCERS})
    reference = local.register_json(trial)
    _checked_trial(local, reference)
    bridge.remaining(plan['deadline_monotonic'])
    root.mkdir(mode=0o700)
    return _save(local, root/'trial.json', trial)


def _request(local, trial, plan, draft, build_ref, correctness_ref, task_artifacts, profile_artifacts):
    build = _read(local, build_ref)
    artifacts = {**build['artifacts'], **task_artifacts, **profile_artifacts,
        'accuracy_report': correctness_ref, 'task_launch': plan['launch_ref'], 'build_window': build_ref}
    report = _read(local, artifacts['measurement_report'])
    for reference in artifacts.values(): local.verify_artifact(reference)
    evidence = dict(candidate_id=plan['candidate_id'], artifacts=artifacts, mechanism_alignment=None,
        **{key:'passed' for key in ('static_review', 'build', 'accuracy', 'runtime', 'semantic', 'scope', 'portability')},
        **report['gate_projection'])
    request = dict(schema_version='1.0.0', candidates=[draft], evidence=[evidence], config={})
    GateRequest.from_dict(request)
    return request


def run_trial(local, *, trial_ref):
    """One reviewed build and four ordered phases; called only by trusted child."""
    trial, plan, context, draft, graph = _checked_trial(local, trial_ref)
    deadline = plan['deadline_monotonic']; candidate._local(local, deadline)
    root = Path(trial['directory'])
    start_ref = _save(local, root/'started.json', dict(trial_ref=trial_ref, started_at=time.time(),
        started_monotonic=time.monotonic(), deadline_monotonic=deadline))
    commands = Commands(root/'commands', deadline)
    result = dict(schema_version=1, kind=KIND, trial_ref=trial_ref, launch_ref=plan['launch_ref'],
        deadline_monotonic=deadline, start_ref=start_ref, status='failed', error=None, build_receipt_ref=None, pmu_plan_ref=None,
        stages=[], archive_performed=False, admission_authority=False, eligible_for_publication=False)
    current = None

    def start(name):
        nonlocal current
        require(name == PHASES[len(result['stages'])], 'candidate stage order differs')
        bridge.remaining(deadline)
        current = dict(name=name, started_at=time.time(), started_monotonic=time.monotonic(),
            deadline_monotonic=deadline, trial_ref=trial_ref)
        current['start_ref'] = _save(local, root/(name+'-started.json'), current)

    def complete(artifacts):
        nonlocal current
        for reference in artifacts.values(): local.verify_artifact(reference)
        bridge.remaining(deadline)
        value = {**current, 'finished_at':time.time(), 'finished_monotonic':time.monotonic(), 'artifacts':artifacts}
        reference = _save(local, root/(current['name']+'-completed.json'), value)
        result['stages'].append(reference); current = None

    try:
        built = candidate.reviewed_build_once(plan['assembly_dir'], plan['workspace'], commands, local,
            model=plan['model'], baseline_qualification=plan['baseline_qualification'], plan_ref=trial['candidate_plan_ref'])
        build_ref = result['build_receipt_ref'] = built['build_receipt_ref']
        result['pmu_plan_ref'] = pmu.prepare_candidate_pmu_plan(local, candidate_plan_ref=trial['candidate_plan_ref'],
            build_receipt_ref=build_ref, selections=trial['selections'], destination=root/'pmu-plan')
        start('correctness')
        accuracy = candidate.collect_candidate_correctness(local, plan_ref=trial['candidate_plan_ref'],
            build_receipt_ref=build_ref, commands=commands, destination=root/'correctness')
        require(candidate.verify_candidate_correctness(local, plan_ref=trial['candidate_plan_ref'],
            build_receipt_ref=build_ref, report_ref=accuracy)['valid'] is True, 'complete correctness replay failed')
        complete({'accuracy_report':accuracy})
        start('task_measurement')
        measured = candidate.collect_candidate_task(local, plan_ref=trial['candidate_plan_ref'],
            build_receipt_ref=build_ref, correctness_ref=accuracy, output=root/'measurement', deadline=deadline)
        complete(measured['artifacts'])
        start('profile')
        profile = pmu.collect_candidate_pmu(local, plan_ref=result['pmu_plan_ref'],
            completion_ref=measured['artifacts']['measurement_admission'], destination=root/'profile', deadline=deadline)
        require(profile['replay']['valid'] is True, 'complete PMU replay failed')
        complete(profile['artifacts'])  # Unknown alignment stays unknown at the runtime gate.
        start('online_admission')
        request = _request(local, trial, plan, draft, build_ref, accuracy, measured['artifacts'], profile['artifacts'])
        request_ref = local.register_json(request)
        finalized = candidate.finalize_local(context, request, graph, local, deadline=deadline)
        require(len(finalized['episodes']) == 1 and finalized['archive_performed'] is False
            and finalized['store_sequences'] == [], 'candidate finalization changed local single-attempt scope')
        finalized_ref = local.register_json(finalized)
        complete({'gate_request':request_ref, 'finalization':finalized_ref})
        bridge.remaining(deadline)
        result['status'] = 'completed'
    except Exception as exc:
        result['error'] = dict(type=type(exc).__name__, message=str(exc))
        if getattr(exc, 'report_ref', None): result['error']['report_ref'] = exc.report_ref
    finally:
        if time.monotonic() >= deadline:
            result['status'] = 'failed'
            result['error'] = result['error'] or dict(type='TimeoutError', message='original task deadline expired')
        result.update(active_stage=current, finished_at=time.time(), finished_monotonic=time.monotonic())
        result_ref = _save(local, root/'result.json', result)
        index = local.write_index(root/'local-index.json')
    return dict(result_ref=result_ref, local_index=str(index), status=result['status'],
        admission_authority=False, eligible_for_publication=False, archive_performed=False)


def replay_trial(local, *, trial_ref, result_ref):
    """Recheck raw leaves and finalized runtime episode; no actual exit is invented."""
    trial, plan, context, draft, graph = _checked_trial(local, trial_ref)
    result = _read(local, result_ref); root = Path(trial['directory']); deadline = plan['deadline_monotonic']
    require(file_hash(root/'result.json') == result_ref and result['trial_ref'] == trial_ref
        and result['launch_ref'] == plan['launch_ref'] and result['deadline_monotonic'] == deadline
        and result['archive_performed'] is False and result['admission_authority'] is False
        and result['eligible_for_publication'] is False, 'candidate result binding differs')
    require(result['status'] == 'completed' and result['error'] is None and result['active_stage'] is None
        and len(result['stages']) == len(PHASES) and number(result['finished_monotonic']) <= deadline,
        'failed or incomplete candidate cannot replay as completed')
    start = _read(local, result['start_ref'])
    require(file_hash(root/'started.json') == result['start_ref']
        and start['trial_ref'] == trial_ref and start['deadline_monotonic'] == deadline
        and number(start['started_monotonic']) <= number(result['finished_monotonic']) <= deadline
        and number(start['started_at']) <= number(result['finished_at']), 'candidate task start binding differs')
    _, build = candidate.checked_candidate_build(local, plan_ref=trial['candidate_plan_ref'],
        build_receipt_ref=result['build_receipt_ref'])
    require(start['started_at'] <= build['started_at'] <= build['finished_at'] <= result['finished_at']
        and start['started_monotonic'] <= build['started_monotonic'] <= build['finished_monotonic']
        <= result['finished_monotonic'], 'actual build escaped its original trial window')
    stage_values = []; wall, mono = build['finished_at'], build['finished_monotonic']
    for name, reference in zip(PHASES, result['stages'], strict=True):
        value = _read(local, reference)
        require(file_hash(root/(name+'-completed.json')) == reference and value['name'] == name
            and value['trial_ref'] == trial_ref and value['deadline_monotonic'] == deadline
            and wall <= number(value['started_at']) <= number(value['finished_at']) <= result['finished_at']
            and mono <= number(value['started_monotonic']) <= number(value['finished_monotonic'])
            <= number(result['finished_monotonic']) <= deadline,
            'candidate stage order/chronology/deadline differs')
        start = _read(local, value['start_ref'])
        require(start == {k:value[k] for k in ('name','started_at','started_monotonic','deadline_monotonic','trial_ref')}
            and file_hash(root/(name+'-started.json')) == value['start_ref'], 'candidate stage start changed')
        for artifact in value['artifacts'].values(): local.verify_artifact(artifact)
        stage_values.append(value); wall, mono = value['finished_at'], value['finished_monotonic']
    a, t, p, g = (value['artifacts'] for value in stage_values)
    accuracy = candidate.verify_candidate_correctness(local, plan_ref=trial['candidate_plan_ref'],
        build_receipt_ref=result['build_receipt_ref'], report_ref=a['accuracy_report'])
    task = replay_current_measurement_admission(local, t['measurement_admission'], expected={
        k:plan[k] for k in ('operator','run_id','session_id','candidate_id','source_hashes')})
    config = candidate.candidate_task_config(local, plan_ref=trial['candidate_plan_ref'], build_receipt_ref=result['build_receipt_ref'])
    require(accuracy['valid'] is True and task['valid'] is True and _read(local, task['config_ref']) == config,
            'candidate correctness or full Task replay differs')
    profile = pmu.verify_candidate_pmu(local, plan_ref=result['pmu_plan_ref'],
        completion_ref=t['measurement_admission'], report_ref=p['mechanism_report'])
    require(profile['valid'] is True and p['mechanism_plan'] == result['pmu_plan_ref']
        and p['measurement_admission'] == t['measurement_admission'], 'candidate PMU binding differs')
    require(p['build_window'] == result['build_receipt_ref'] and p['task_launch'] == plan['launch_ref']
        and p['measurement_report'] == t['measurement_report'], 'candidate profile changed original build/task bindings')
    proof = _read(local, t['measurement_proof'])
    require(t == dict(measurement_admission=t['measurement_admission'], measurement_proof=task['receipt_ref'],
        measurement_report=proof['measurement_report_ref'], timing_config=task['config_ref'],
        timing_raw=proof['raw_ref'], measurement_registration=task['registration_ref']),
        'candidate formal phase omitted or substituted Task evidence')
    capture = _read(local, _read(local, p['mechanism_report'])['capture_report_ref'])
    for stage, evidence in zip(stage_values, (_read(local,a['accuracy_report']), _read(local,t['measurement_admission']), capture)):
        require(stage['started_at'] <= evidence['started_at'] <= evidence['finished_at'] <= stage['finished_at'],
                'actual component escaped its recorded phase')
    request = _request(local, trial, plan, draft, result['build_receipt_ref'], a['accuracy_report'], t, p)
    require(_read(local, g['gate_request']) == request, 'candidate changed its actual runtime request')
    prepared = prepare_gate_request(GateRequest.from_dict(request), store=local)
    finalized = _read(local, g['finalization'])
    require(finalized['archive_performed'] is False and finalized['store_sequences'] == []
        and len(finalized['episodes']) == 1, 'candidate episode scope differs')
    episode = CandidateEpisode.from_dict(finalized['episodes'][0])
    timestamp = dt.datetime.fromisoformat(episode.finalized_at.replace('Z','+00:00')).timestamp()
    require(episode.context == Context.from_dict(context) and episode.gate_request == prepared
        and episode.draft == CandidateDraft.from_dict(draft) and episode.graph_snapshot == graph
        and episode.evidence == prepared.evidence[0] and len(prepared.evidence) == 1
        and episode.runtime_build == 'aprof-runtime/' + runtime_version
        and episode.behavior_policy_checkpoint is None and episode.policy_checkpoint_hash is None
        and stage_values[-1]['started_at'] <= timestamp <= stage_values[-1]['finished_at'],
        'actual finalized episode differs from full current replay/window')
    return dict(valid=True, scope='candidate_components_without_dispatcher_exit', trial_ref=trial_ref,
        result_ref=result_ref, verdict=episode.outcome.verdict.value, pmu_alignment=profile['alignment'],
        admission_authority=False, eligible_for_publication=False,
        remaining_requirements=['actual original supervisor exit and complete 45-trial publication replay'])


def _bind_pointer(local, pointer):
    require(isinstance(pointer, dict) and set(pointer) == {'path', 'sha256'}, 'evaluation needs an exact file pointer')
    path = candidate.builder._path(pointer['path'])
    require(local.register_artifact(path) == pointer['sha256'], 'evaluation pointer bytes changed')
    return path


def _evaluation_draft(local, plan_ref, *, workspace, submission_workspace, model, qualification):
    """Bind the actual model submission to its reviewed route and source bundles."""
    from eval_tool_broker import BUDGET_POLICY, CONFIG, inventory
    from feedback_attempt_verify import expected_patch
    plan = _read(local, plan_ref)
    submitted_path = workspace / 'candidate_plan.json'
    submitted = json.loads(submitted_path.read_text())
    worker_path = submission_workspace.parents[1] / 'worker.json'
    worker = json.loads(worker_path.read_text())
    require(worker['status'] == 'completed' and worker['role'] == 'proposer'
        and worker['model'] == model['name'] and worker['reasoning_effort'] == model['reasoning_effort']
        and worker['qualification_ref'] == qualification and worker['config'] == CONFIG
        and worker['worker_builds'] == 0 and worker['budget_policy'] == BUDGET_POLICY
        and worker['usage'] is not None and worker['submission'] == {
            'plan': {'path': str(submission_workspace / 'candidate_plan.json'), 'sha256': file_hash(submitted_path)},
            'source_inventory': inventory(workspace / 'candidate')}, 'candidate differs from the completed model submission')
    require(submitted.get('actual_parent') == 'original baseline'
        and isinstance(submitted.get('intent'), str) and submitted['intent'].strip(),
        'candidate must name its original parent and concrete intent')
    for pointer in (qualification, worker['events_ref'], worker['broker_ref']): _bind_pointer(local, pointer)
    local.register_artifact(worker_path)
    local.register_artifact(submitted_path)
    route = candidate._pointer(local, plan['route'])
    registry = candidate._pointer(local, route['registry_ref'])
    graph, _ = load_snapshot(local.verify_artifact(registry['graph']['sha256']))
    require(content_hash(graph) == route['graph_hash'], 'submitted route graph changed')
    transformation = next(item for item in graph['transformations'] if item['id'] == submitted['transformation_id'])
    files = {role: {name: local.verify_artifact(reference).read_bytes()
        for name, reference in plan['roles'][role]['files'].items()} for role in bridge.ROLES}
    patch = expected_patch(files['baseline'], files['candidate'])
    require(patch, 'candidate contains no source intervention')
    patch_path = local.directory.parent / 'candidate.patch'
    with patch_path.open('xb') as stream: stream.write(patch)
    draft = CandidateDraft.from_dict(dict(schema_version='1.0.0', candidate_id=plan['candidate_id'],
        session_id=plan['session_id'], route=route['route'], transformation_id=submitted['transformation_id'],
        transformation_version=transformation['version'], parameters=submitted['parameters'],
        source_hashes=plan['source_hashes'], patch_artifact_hash=local.register_artifact(patch_path),
        producer_hashes=dict(model=local.register_json(dict(model=model, qualification_ref=qualification)),
            prompt=local.register_artifact(workspace / 'prompt.txt'),
            agent=local.register_artifact(Path(__file__).with_name('isolated_eval_worker.py'))),
        proposed_by=worker['model'], created_at=dt.datetime.now(dt.timezone.utc).isoformat(),
        parent_candidate_id=None))
    return local.register_json(to_primitive(draft))


def execute_evaluation(manifest, row, workspace, result_path, *, launch_path, launch_sha256):
    """Trusted evaluator entry; retain local failures and never reset the parent clock."""
    import evaluate_skill_release as evaluator
    workspace = candidate.builder._path(workspace)
    result_path = candidate.builder._path(result_path)
    launch_path = candidate.builder._path(launch_path)
    output = launch_path.parents[2]
    directory = output / 'runs' / row['run_id']
    submission_workspace = directory / 'worker/root/work'
    require(result_path.parent == directory and not result_path.exists()
        and workspace == directory / 'controller-workspace', 'evaluation output/workspace differs from the parent trial')
    local_parent = evaluator._task_local_root(manifest)
    root = Path(tempfile.mkdtemp(prefix='aprof-task-validation-', dir=str(local_parent)))
    local = candidate.LocalEvidence(root / 'records')
    receipt = dict(schema_version=1, kind='task_validation_evaluation', measurement_protocol=bridge.timing.PROTOCOL,
        row=row, task_root=str(root), task_launch_ref={'path': str(launch_path), 'sha256': launch_sha256},
        candidate_tree_sha256=None, status='failed', error=None, started_at=time.time(),
        started_monotonic=time.monotonic(), deadline_monotonic=None, candidate_plan_ref=None,
        draft_ref=None, trial_ref=None, result_ref=None, online_replay_ref=None, local_index=None,
        archive_performed=False, admission_authority=False, eligible_for_publication=False)
    bridge.save(result_path.with_name(result_path.stem + '-started.json'), receipt)
    def pointer(reference):
        return {'path': str(local.verify_artifact(reference)), 'sha256': reference}
    try:
        launch, _ = evaluator._load_launch(output, row['run_id'], launch_path, launch_sha256)
        deadline = receipt['deadline_monotonic'] = launch['deadline_monotonic']
        bridge.remaining(deadline)
        require(manifest == evaluator.load(output / 'freeze.json')
            and sum(value == row for value in evaluator.load(output / 'matrix.json')['runs']) == 1,
            'evaluation arguments differ from the frozen parent')
        from eval_tool_broker import inventory
        require(all(inventory(workspace / role) == inventory(submission_workspace / role) for role in bridge.ROLES)
            and all(file_hash(workspace / name) == file_hash(submission_workspace / name) for name in
                ('candidate_plan.json', 'candidate_review.json', 'route_receipt.json', 'prompt.txt')),
            'controller workspace differs from the original reviewed model submission')
        task = manifest['tasks'][row['operator']]
        imported = candidate.LocalEvidence.from_index(_bind_pointer(local, task['baseline_local_index']))
        local._paths.update(imported._paths)  # Index handoff only; raw/profile files stay in place.
        for key in ('evaluation_plan', 'baseline_qualification', 'route_registry'):
            _bind_pointer(local, task[key])
        derivation = _read(local, task['context_derivation_ref'])
        qualification = candidate._pointer(local, task['baseline_qualification'])
        require(qualification['plan_ref'] == derivation['plan_ref'] == task['evaluation_plan']['sha256']
            and _read(local, task['evaluation_plan']['sha256'])['operator'] == row['operator'],
            'evaluation baseline/derivation belongs to a different task')
        # Register the already authenticated parent chain for candidate._launch.
        launch_ref = local.register_artifact(launch_path)
        attempt = json.loads(_bind_pointer(local, launch['attempt_ref']).read_text())
        origin = json.loads(_bind_pointer(local, attempt['plan_ref']).read_text())
        for key in ('freeze_ref', 'matrix_ref', 'job_ref'): _bind_pointer(local, origin[key])
        _bind_pointer(local, manifest['plan'])
        candidate._local(local, deadline)
        model = {key: manifest['model'][key] for key in ('name', 'reasoning_effort')}
        candidate.register_candidate_evidence(local, workspace, bridge.RELEASE, model=model,
            baseline_qualification=task['baseline_qualification'])
        receipt['candidate_tree_sha256'] = evaluator.tree_sha(workspace / 'candidate')
        candidate.prepare_candidate_assembly(local, workspace=workspace, destination=root / 'assembly',
            baseline_qualification=task['baseline_qualification'])
        candidate_id = row['run_id'] + '-candidate'
        plan_ref = candidate.prepare_candidate_plan(local, assembly=root / 'assembly', workspace=workspace,
            model=model, baseline_qualification=task['baseline_qualification'],
            identity=dict(run_id=row['run_id'], session_id=candidate_id, candidate_id=candidate_id),
            scratch_root=root / 'scratch', deadline=deadline, launch_ref=launch_ref)
        receipt['candidate_plan_ref'] = pointer(plan_ref)
        draft_ref = _evaluation_draft(local, plan_ref, workspace=workspace, submission_workspace=submission_workspace, model=model,
            qualification=manifest['worker_qualification'])
        receipt['draft_ref'] = pointer(draft_ref)
        inputs = dict(candidate_plan_ref=plan_ref, draft_ref=draft_ref,
            registry_ref=task['route_registry']['sha256'], derivation_ref=task['context_derivation_ref'])
        planning = materialize_submitted_planning(local, **inputs)
        trial_ref = prepare_trial(local, **inputs, execution_context_ref=planning['execution_context_ref'],
            selections=planning['selections'], destination=root / 'trial')
        receipt['trial_ref'] = pointer(trial_ref)
        result = run_trial(local, trial_ref=trial_ref)
        receipt['result_ref'] = pointer(result['result_ref'])
        require(result['status'] == 'completed', 'candidate trial failed: ' + str(_read(local, result['result_ref'])['error']))
        bridge.remaining(deadline)
        replay = replay_trial(local, trial_ref=trial_ref, result_ref=result['result_ref'])
        require(replay['valid'] is True, 'candidate online replay failed')
        receipt['online_replay_ref'] = pointer(local.register_json(replay))
        bridge.remaining(deadline)
        receipt['status'] = 'completed'
    except Exception as exc:
        receipt['error'] = dict(type=type(exc).__name__, message=str(exc))
        if getattr(exc, 'report_ref', None): receipt['error']['report_ref'] = exc.report_ref
    finally:
        index = local.write_index(root / 'evaluation-local-index.json')
        receipt['local_index'] = {'path': str(index), 'sha256': file_hash(index)}
        receipt.update(finished_at=time.time(), finished_monotonic=time.monotonic())
        if receipt['deadline_monotonic'] is not None and receipt['finished_monotonic'] >= receipt['deadline_monotonic']:
            receipt.update(status='failed', error=dict(type='TimeoutError', message='original task deadline expired'))
        bridge.save(result_path, receipt)
    return receipt


if __name__ == '__main__':
    raise SystemExit('disabled: trusted evaluator integration and complete baseline qualification are required')
