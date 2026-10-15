"""Unactivated local Task validation primitives, not an evaluation dispatcher.

The caller owns the original absolute deadline and actual process-exit receipt.
Baseline qualification is independently replayed before original-source assembly,
reviewed single-build execution and complete correctness for all five operators.
The existing evaluator/outer schema and PMU gate join still need activation; the
six-pair Teacher screen cannot supply an unregistered validation screen.

This module never archives, imports an episode into a store, or grants baseline
qualification. Post-task trace collection remains a separate owner and budget.
"""
from task_budget import budget_seconds, positive, collection_policy
import importlib.util
import json
from pathlib import Path
import sys
import time

import local_controller_bridge as bridge
import task_baseline_build as builder
import task_baseline_correctness as correctness
import task_baseline_qualification as baseline
from task_baseline_controller import verify_baseline_qualification
from eval_candidate_evidence import register_candidate_evidence, verify_candidate_evidence
from timing_admission import require, number

LocalEvidence = bridge.LocalEvidence
OPERATORS = baseline.OPERATORS
PROTOCOL = 'validation_candidate_task_v1'
ENABLED_IN_1_0 = False


def _local(local, deadline):
    bridge.remaining(deadline)
    if (not isinstance(local, LocalEvidence) or bridge.RELEASE.name != '1.0.0'
            or bridge.timing.PROTOCOL != 'shared_buffer_msprof_task_window_v5'):
        raise ValueError('validation primitives require selected 1.0.0 Task v5 and LocalEvidence')


def _operator(operator):
    if operator not in OPERATORS:
        raise ValueError('unknown original validation operator; no Teacher screen')


def _read(local, reference):
    return json.loads(local.verify_artifact(reference).read_text())


def _qualified(local, pointer):
    require(isinstance(pointer,dict) and set(pointer)=={'path','sha256'}, 'full baseline qualification pointer required')
    path=builder._path(pointer['path'])
    require(bridge.file_hash(path)==pointer['sha256'], 'baseline qualification file changed')
    value=_read(local,pointer['sha256'])
    rebuilt=verify_baseline_qualification(local,attempt_ref=value['attempt_ref'],result_ref=value['result_ref'])
    require(value==rebuilt and value['qualification_passed'] is True and value['status']=='passed',
            'baseline qualification must independently replay')
    return baseline.checked_plan(local,value['plan_ref'])


def _pointer(local, pointer):
    require(isinstance(pointer, dict) and set(pointer)=={'path','sha256'}, 'original dispatcher pointer required')
    path=builder._path(pointer['path'])
    require(bridge.file_hash(path)==pointer['sha256'], 'original dispatcher pointer changed')
    return _read(local,pointer['sha256'])


def _launch(local, reference, *, deadline, run_id, operator, model, qualification, physical_device):
    launch=_read(local,reference)
    require(set(launch)=={'attempt_ref','started_at','started_monotonic','deadline_monotonic',
        'issued_monotonic','child_timeout_seconds'}, 'original dispatcher launch scope differs')
    attempt=_pointer(local,launch['attempt_ref']);origin=_pointer(local,attempt['plan_ref'])
    job=_pointer(local,origin['job_ref']);freeze=_pointer(local,origin['freeze_ref'])
    matrix=_pointer(local,origin['matrix_ref'])
    budget=budget_seconds(_pointer(local,freeze['plan'])['equal_budget_evaluation'])
    require(set(attempt)=={'plan_ref','budget_seconds','created_at'} and budget_seconds(attempt)==budget
        and origin['schema_version']==1 and origin['kind']=='skill_release_trial_plan'
        and origin['run_id']==origin['row']['run_id']==run_id and origin['row']['operator']==operator
        and sum(row==origin['row'] for row in matrix['runs'])==1
        and budget_seconds(origin)==positive(job['timeout_seconds'])==budget
        and {key:freeze['model'][key] for key in ('name','reasoning_effort')}==model
        and freeze['tasks'][operator]['baseline_qualification']==qualification
        and job['environment']['APROF_SKILL_LIB']==str(bridge.RELEASE)
        and job['environment']['ASCEND_RT_VISIBLE_DEVICES']==str(physical_device)
        and job['environment']['APROF_PHYSICAL_DEVICE']==str(physical_device)
        and job['environment']['APROF_LOGICAL_DEVICE']=='0'
        and all(job['environment'].get(key)==value for key,value in builder.CPU_REFERENCE_ENV.items())
        and number(attempt['created_at'])<=number(launch['started_at'])
        and number(launch['deadline_monotonic'])==number(deadline)==number(launch['started_monotonic'])+budget
        and launch['started_monotonic']<=number(launch['issued_monotonic'])<deadline
        and number(launch['child_timeout_seconds'])==deadline-launch['issued_monotonic'],
        'candidate changed the original task identity, baseline, model or absolute deadline')
    return launch


def _candidate_adapter(local, original):
    # The historical relocation is verified privately; public/frozen adapters stay unchanged.
    adapter,_=builder._adapter(original['operator'],local,original['preparation_ref'])
    if hasattr(adapter,'bridge'):
        return adapter,adapter.bridge
    spec=importlib.util.spec_from_file_location('validation_private_bridge',Path(bridge.__file__))
    execution=importlib.util.module_from_spec(spec);spec.loader.exec_module(execution)
    execution.adapter=adapter
    return adapter,execution


def prepare_candidate_assembly(local, *, workspace, destination, baseline_qualification):
    original=_qualified(local,baseline_qualification)
    adapter,_=_candidate_adapter(local,original)
    sources={r:builder._path(Path(workspace)/r) for r in bridge.ROLES}
    files={r:bridge.profile_capture.source_inventory(path) for r,path in sources.items()}
    proof=adapter.assemble(original['operator'],sources,builder._path(destination),
        expected_roles=files,expected_headers=original['headers'])
    local.register_artifact(Path(destination)/'source-review.json')
    return proof


def prepare_candidate_plan(local, *, assembly, workspace, model, baseline_qualification,
                           identity, scratch_root, deadline, launch_ref):
    _local(local,deadline)
    require(0<deadline-time.monotonic() and set(identity)=={'run_id','session_id','candidate_id'}
        and all(isinstance(v,str) and v for v in identity.values())
        and isinstance(model,dict) and set(model)=={'name','reasoning_effort'}
        and all(isinstance(v,str) and v for v in model.values()), 'candidate identity/model or original deadline differs')
    original=_qualified(local,baseline_qualification)
    launch=_launch(local,launch_ref,deadline=deadline,run_id=identity['run_id'],operator=original['operator'],
            model=model,qualification=baseline_qualification,physical_device=original['physical_device'])
    adapter,_=_candidate_adapter(local,original);proof=adapter.source_identity(assembly)
    review=verify_candidate_evidence(workspace,bridge.RELEASE,model=model,baseline_qualification=baseline_qualification)
    require(review['accepted'] is True, 'independent candidate review is not accepted')
    require(all(Path(proof['roles'][r]['path'])==builder._path(Path(workspace)/r) for r in bridge.ROLES),
            'candidate assembly differs from reviewed workspace')
    roles=proof['roles'];hashes={}
    for role in bridge.ROLES:
        for name,reference in roles[role]['files'].items():
            require(local.register_artifact(Path(roles[role]['path'])/name)==reference, 'candidate source changed')
        hashes[role]=local.register_json({'schema_version':'1.0.0','files':roles[role]['files']})
    require(hashes['baseline']==original['source_hashes']['baseline'], 'candidate baseline differs from qualification')
    producers=_producers(original)
    plan=dict(schema_version=1,kind='validation_candidate_plan',protocol=PROTOCOL,task_protocol=bridge.timing.PROTOCOL,
        budget_policy='time_only_v1',budget_seconds=budget_seconds(_pointer(local,_pointer(local,launch['attempt_ref'])['plan_ref'])),deadline_monotonic=deadline,launch_ref=launch_ref,
        created_at=time.time(),workspace=str(builder._path(workspace)),model=model,**identity,
        baseline_qualification=baseline_qualification,assembly_dir=str(builder._path(assembly)),
        scratch_root=str(builder._path(scratch_root)),roles=roles,source_hashes=hashes,
        source_review_ref=local.register_artifact(Path(assembly)/'source-review.json'),
        independent_review=review['source_review_ref'],route=review['route_receipt_ref'],
        producer_refs={path:local.register_artifact(path) for path in producers},
        **{key:original[key] for key in ('operator','preparation_ref','case_ids','cases','headers',
            'device','physical_device','toolchain_refs','profile','pmu_scope')})
    policy=_collection_policy(local,launch)
    if policy is not None: plan['collection_stop_policy']=policy
    return local.register_json(plan)


def _collection_policy(local,launch):
    origin=_pointer(local,_pointer(local,launch['attempt_ref'])['plan_ref'])
    freeze=_pointer(local,origin['freeze_ref'])
    return collection_policy(_pointer(local,freeze['plan'])['equal_budget_evaluation'])


def _producers(original):
    return set(original['producer_refs']) | {str(Path(__file__).with_name(name)) for name in
        ('task_validation_controller.py','eval_candidate_evidence.py','qualify_eval_tools.py',
         'isolated_eval_worker.py','review_packet.py','task_candidate_pmu.py','task_baseline_pmu.py')}


def _checked_candidate_plan(local, plan_ref):
    plan=_read(local,plan_ref)
    require(plan.get('kind')=='validation_candidate_plan' and plan.get('protocol')==PROTOCOL
        and plan.get('task_protocol')==bridge.timing.PROTOCOL and plan.get('budget_policy')=='time_only_v1'
        and budget_seconds(plan)>0, 'candidate plan protocol/budget differs')
    original=_qualified(local,plan['baseline_qualification'])
    for key in ('operator','preparation_ref','case_ids','cases','headers','device','physical_device',
                'toolchain_refs','profile','pmu_scope'):
        require(plan[key]==original[key], 'candidate changed original qualification '+key)
    launch=_launch(local,plan['launch_ref'],deadline=plan['deadline_monotonic'],run_id=plan['run_id'],
        operator=plan['operator'],model=plan['model'],qualification=plan['baseline_qualification'],
        physical_device=plan['physical_device'])
    require(budget_seconds(plan)==budget_seconds(_pointer(local,_pointer(local,launch['attempt_ref'])['plan_ref']))
        and launch['started_at']<=number(plan['created_at'])<=launch['started_at']+budget_seconds(plan),
            'candidate plan is outside the original task window')
    require(collection_policy(plan)==_collection_policy(local,launch), 'candidate changed frozen collection-stop policy')
    producers=_producers(original)
    builder._need(set(plan['producer_refs'])==producers, 'candidate producer roster differs')
    builder._bindings(local,plan['producer_refs']);builder._bindings(local,plan['toolchain_refs'])
    adapter,execution=_candidate_adapter(local,original);proof=adapter.source_identity(plan['assembly_dir'])
    require(proof['roles']==plan['roles'] and proof['trusted_headers']==plan['headers']
        and bridge.file_hash(Path(plan['assembly_dir'])/'source-review.json')==plan['source_review_ref'],
        'candidate mechanical proof changed')
    local.verify_artifact(plan['source_review_ref'])
    for role in bridge.ROLES:
        require(Path(plan['roles'][role]['path'])==builder._path(Path(plan['workspace'])/role)
            and _read(local,plan['source_hashes'][role])=={'schema_version':'1.0.0','files':plan['roles'][role]['files']},
            'candidate source bundle or reviewed role differs')
        for name,reference in plan['roles'][role]['files'].items():
            correctness._file(local,Path(plan['roles'][role]['path'])/name,reference)
    require(plan['source_hashes']['baseline']==original['source_hashes']['baseline'], 'qualified baseline source differs')
    review=verify_candidate_evidence(plan['workspace'],bridge.RELEASE,model=plan['model'],
                                    baseline_qualification=plan['baseline_qualification'])
    require(review['accepted'] is True and review['source_review_ref']==plan['independent_review']
        and review['route_receipt_ref']==plan['route'], 'candidate blind review or legal route changed')
    return plan,proof,execution


def reviewed_build_once(assembly, workspace, commands, local, *, model, baseline_qualification, plan_ref):
    """Actual blind/legal-route review plus one mechanical five-operator build."""
    _local(local, commands.deadline)
    started,mono=time.time(),time.monotonic()
    plan,proof,execution=_checked_candidate_plan(local,plan_ref)
    require(plan['assembly_dir']==str(builder._path(assembly)) and plan['workspace']==str(builder._path(workspace))
        and plan['model']==model and plan['baseline_qualification']==baseline_qualification
        and plan['deadline_monotonic']==commands.deadline, 'candidate build differs from original plan/deadline')
    builder._environment(plan)
    evidence = register_candidate_evidence(local, workspace, bridge.RELEASE,
        model=model, baseline_qualification=baseline_qualification)
    receipt = execution.build_once(assembly, workspace, commands,
        model=model, baseline_qualification=baseline_qualification)
    _, build = execution.checked_build(assembly, receipt)
    binary_ref = local.register_artifact(build['binary']['path'])
    if binary_ref != build['binary']['sha256']:
        raise ValueError('combined validation binary changed before registration')
    for pointer in [build['attempt_ref'], *[row[key] for row in build['commands'] for key in ('stdout', 'stderr')]]:
        if local.register_artifact(pointer['path']) != pointer['sha256']:
            raise ValueError('combined validation build evidence changed')
    evidence['build_log'] = local.register_artifact(receipt)
    for stage,record in zip(('configure','build'),build['commands'],strict=True):
        builder._record(local,record,Path(commands.directory)/stage/'execution.json',register=True)
    wrapper=dict(schema_version=1,kind='reviewed_candidate_build',plan_ref=plan_ref,
        receipt_ref=evidence['build_log'],command_directory=str(builder._path(commands.directory)),
        started_at=started,finished_at=time.time(),started_monotonic=mono,finished_monotonic=time.monotonic(),
        deadline_monotonic=commands.deadline,launch_ref=plan['launch_ref'],artifacts=evidence)
    wrapper_path=Path(assembly)/'candidate-build.json';bridge.save(wrapper_path,wrapper)
    bridge.remaining(commands.deadline)
    return dict(build_receipt=str(receipt),build_receipt_ref=local.register_artifact(wrapper_path),
                binary_ref=binary_ref, artifacts=evidence,
                admission_authority=False, archive_performed=False)


def checked_candidate_build(local, *, plan_ref, build_receipt_ref):
    plan,proof,execution=_checked_candidate_plan(local,plan_ref)
    return _checked_build(local,plan_ref,build_receipt_ref,plan,proof,execution)


def _checked_build(local, plan_ref, build_receipt_ref, plan, proof, execution):
    wrapper=_read(local,build_receipt_ref);assembly=Path(plan['assembly_dir'])
    require(bridge.file_hash(assembly/'candidate-build.json')==build_receipt_ref
        and wrapper['kind']=='reviewed_candidate_build' and wrapper['schema_version']==1
        and wrapper['plan_ref']==plan_ref and wrapper['deadline_monotonic']==plan['deadline_monotonic']
        and wrapper['launch_ref']==plan['launch_ref']
        and plan['created_at']<=wrapper['started_at']<=wrapper['finished_at']
        and wrapper['started_monotonic']<=wrapper['finished_monotonic']<=wrapper['deadline_monotonic']
        <=wrapper['started_monotonic']+budget_seconds(plan), 'candidate build wrapper identity/time differs')
    require(local.verify_artifact(wrapper['receipt_ref'])==assembly/'build-receipt.json', 'candidate build receipt path differs')
    require(wrapper['artifacts']=={'build_log':wrapper['receipt_ref'],
        'source_review':plan['independent_review']['sha256'],'route_receipt':plan['route']['sha256']},
        'candidate build artifact bindings differ')
    _,built=execution.checked_build(assembly,assembly/'build-receipt.json')
    attempt=_read(local,built['attempt_ref']['sha256'])
    require(attempt['independent_review']==plan['independent_review'] and attempt['route']==plan['route'],
            'candidate build omitted its actual blind review/legal route')
    for stage,record in zip(('configure','build'),built['commands'],strict=True):
        builder._record(local,record,Path(wrapper['command_directory'])/stage/'execution.json',register=False)
    local.verify_artifact(built['binary']['sha256'])
    return proof,{**built,**{key:wrapper[key] for key in ('started_at','finished_at','started_monotonic',
        'finished_monotonic','deadline_monotonic')}}


def _candidate_preflight(local, plan_ref, build_receipt_ref):
    plan,proof,execution=_checked_candidate_plan(local,plan_ref)
    _,built=_checked_build(local,plan_ref,build_receipt_ref,plan,proof,execution)
    oracle=Path(plan['roles']['baseline']['path'])/'scripts/verify_result.py'
    reference=plan['roles']['baseline']['files']['scripts/verify_result.py']
    correctness._file(local,oracle,reference)
    python=str(Path(sys.executable).resolve())
    require(plan['toolchain_refs'].get(python)==bridge.file_hash(python), 'candidate oracle Python is unbound')
    require(proof['mechanism_entry']=={'flag':'--aprof-mechanism-role','roles':list(bridge.ROLES),
        'calls':1,'snapshot_all_outputs':True,'task_api_enabled':False}, 'candidate lacks complete callback')
    return plan,proof,built,oracle,reference


def collect_candidate_correctness(local, *, plan_ref, build_receipt_ref, commands, destination):
    return correctness._collect_complete(local,plan_ref=plan_ref,build_receipt_ref=build_receipt_ref,
        commands=commands,destination=destination,preflight=_candidate_preflight,kind='reviewed_candidate_correctness')


def verify_candidate_correctness(local, *, plan_ref, build_receipt_ref, report_ref):
    return correctness._verify_complete(local,plan_ref=plan_ref,build_receipt_ref=build_receipt_ref,
        report_ref=report_ref,preflight=_candidate_preflight,kind='reviewed_candidate_correctness')


def candidate_task_config(local, *, plan_ref, build_receipt_ref):
    plan,proof,execution=_checked_candidate_plan(local,plan_ref)
    _,built=_checked_build(local,plan_ref,build_receipt_ref,plan,proof,execution)
    return bridge.timing.config_value(baseline._task_config(local,plan,
        local.verify_artifact(_read(local,build_receipt_ref)['receipt_ref']),built))


def _cases(config):
    _operator(config['operator'])
    ids = list(range(1, 21))
    if config['expected_case_ids'] != ids or [c['case_id'] for c in config['cases']] != ids:
        raise ValueError('validation requires every original case exactly once in order')
    if set(config['roles']) != set(bridge.ROLES):
        raise ValueError('validation needs both complete source roles')
    try:
        scopes={str(c['case_id']):baseline.case_scope(config['operator'],c['workload']) for c in config['cases']}
    except (KeyError,TypeError) as exc:
        raise ValueError('validation complete-callback workload is malformed') from exc
    for role in bridge.ROLES:
        if (config['roles'][role]['launches_per_operator'] != {cid:s['launches_per_call'][role] for cid,s in scopes.items()}
                or config['task_profile']['role_kernel_names'][role] != {
                    cid:s['role_kernel_names'][role] for cid,s in scopes.items()}):
            raise ValueError('validation complete-callback task scope differs')
    return config['cases']


def correctness_calls(config, destination):
    """Pure 20-case/two-role plan from the trusted bridge.task_config result.

    Each native command selects exactly one complete callback and its snapshot.
    The independent original oracle receives every output (DQ includes scale).
    This is an execution plan, not a correctness report or a passed stage.
    """
    root = Path(destination).absolute()
    if root.resolve() != root:
        raise ValueError('correctness output must be canonical')
    cases = _cases(config)
    count = 2 if config['operator'] == 'dynamic_quant' else 1
    rows = []
    for case in cases:
        if (set(case['output_files']) != set(bridge.ROLES)
                or any(len(case['output_files'][r]) != count for r in bridge.ROLES)
                or '--aprof-mechanism-role' in case['command'] or '--aprof-screen' in case['command']
                or case['command'][0] != config['build']['binary']):
            raise ValueError('complete callback/output scope differs')
        for role in bridge.ROLES:
            directory = root / f"case-{case['case_id']:02d}" / role
            replace = lambda value: value.replace('{cycle_dir}', str(directory))
            outputs = {r: [replace(p) for p in case['output_files'][r]] for r in bridge.ROLES}
            all_outputs = [path for paths in outputs.values() for path in paths]
            if (len(set(all_outputs)) != 2 * count or any(not Path(p).is_relative_to(directory)
                    or '..' in Path(p).parts for p in all_outputs)):
                raise ValueError('role snapshots overlap or escape the case directory')
            argv = [replace(value) for value in case['command']] + ['--aprof-mechanism-role', role]
            oracle = [replace(value) for value in case['verify_commands'][role]]
            if any(path not in argv for path in all_outputs) or any(path not in oracle for path in outputs[role]):
                raise ValueError('native/oracle command omitted a complete output')
            rows.append(dict(case_id=case['case_id'], role=role, argv=argv, oracle_argv=oracle,
                cwd=config['build']['source_dir'], environment={'APROF_SHARED_CYCLE': '0'},
                output_files=outputs[role], inactive_output_files=outputs['candidate' if role == 'baseline' else 'baseline'],
                prepared_files=list(case['prepared_files'])))
    return rows


def collect_task_artifacts(config, output, local, *, deadline, budget_binding=None):
    """Collect with the same deadline and expose actual completion/proof keys.

    The collector performs full local replay. The machine gate subsequently
    independently validates this completion; this join does not claim a verdict.
    Failure keeps the collector's original local index/files and propagates.
    """
    _local(local, deadline)
    _cases(config)
    result = bridge.collect_task(config, output, local, deadline=deadline, budget_binding=budget_binding)
    read = lambda ref: json.loads(local.verify_artifact(ref).read_text())
    completion_ref = result['measurement_admission_ref']
    completion = read(completion_ref)
    proof_ref = completion['proof_ref']
    proof = read(proof_ref)
    if (completion['protocol'] != bridge.timing.PROTOCOL
            or completion['kind'] != 'local_measurement_completion'
            or completion['status'] != 'passed' or completion['error'] is not None
            or any(completion[key] != config[key] for key in ('operator', 'run_id', 'session_id', 'candidate_id'))
            or any(proof[key] != completion[key] for key in ('protocol', 'operator', 'run_id', 'session_id',
                                                           'candidate_id', 'source_hashes', 'measurement_report_ref'))
            or read(proof['config_ref']) != config
            or read(proof['measurement_report_ref']) != result['report']):
        raise ValueError('Task completion/proof differs from this local validation collection')
    for role in bridge.ROLES:
        expected = {'schema_version': '1.0.0', 'files': bridge.profile_capture.source_inventory(
            config['roles'][role]['source_dir'])}
        if read(completion['source_hashes'][role]) != expected:
            raise ValueError('Task completion source differs from validation role')
    artifacts = dict(measurement_admission=completion_ref, measurement_proof=proof_ref,
        measurement_report=proof['measurement_report_ref'], timing_config=proof['config_ref'],
        timing_raw=proof['raw_ref'], measurement_registration=proof['registration_ref'])
    for reference in artifacts.values():
        local.verify_artifact(reference)
    bridge.remaining(deadline)
    return dict(artifacts=artifacts, report=result['report'], local_index=result['local_index'],
                admission_authority=False, archive_performed=False)


def collect_candidate_task(local, *, plan_ref, build_receipt_ref, correctness_ref, output, deadline):
    """Authenticated complete correctness must precede the same-budget Task job."""
    _local(local,deadline)
    plan=_read(local,plan_ref)
    require(deadline==plan['deadline_monotonic'], 'candidate Task reset the original deadline')
    verify_candidate_correctness(local,plan_ref=plan_ref,build_receipt_ref=build_receipt_ref,
                                 report_ref=correctness_ref)
    config=candidate_task_config(local,plan_ref=plan_ref,build_receipt_ref=build_receipt_ref)
    result=collect_task_artifacts(config,output,local,deadline=deadline,
        budget_binding={'kind':'validation','launch_ref':plan['launch_ref']})
    completion=_read(local,result['artifacts']['measurement_admission'])
    require(_read(local,correctness_ref)['finished_at']<=completion['started_at'],
            'candidate Task started before complete correctness')
    return result


def finalize_local(context, request, graph, local, *, deadline, policy=None):
    """Actual runtime gate/episode objects, without episode append or archive.

    The future validation dispatcher supplies the fully qualified Context and
    GateRequest; no status dictionary or baseline qualification is manufactured.
    """
    _local(local, deadline)
    return bridge.finalize_online(context, request, graph, local, deadline=deadline, policy=policy)
