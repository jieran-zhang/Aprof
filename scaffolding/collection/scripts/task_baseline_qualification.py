"""Unactivated baseline A/A plan and Task/exit replay; no capture or archive.

This does not grant a baseline graph qualification. task_baseline_controller
joins the one build, independent correctness, full-occurrence PMU, online replay
and actual dispatcher exit. Task completion replays every oracle and CSV.
"""
from task_budget import budget_seconds, positive, collection_policy
from datetime import datetime
import json
from pathlib import Path
import sys

import local_controller_bridge as bridge
import shared_multikernel_adapter as multi
from eval_tool_broker import BUDGET_POLICY
from aprof_runtime.jsonio import content_hash, file_hash
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.measurement_entry import replay_current_measurement_admission
from aprof_runtime.task_window_measurement_admission import PRODUCER_FILES
from task_baseline_pmu import PROFILE_DEPENDENCY_PATHS
from aprof_runtime.task_window_timing import case_task_config
from timing_admission import number, require

PROTOCOL = 'validation_baseline_task_v1'
OPERATORS = ('dynamic_quant', 'gelu', 'group_norm', 'gqa', 'weight_quant_batch_matmul')
CASE_IDS = list(range(1, 21))
ROLES = ('baseline', 'candidate')
ENABLED_IN_1_0 = False


def producer_paths():
    names = ('task_budget.py', 'task_baseline_qualification.py', 'task_baseline_build.py', 'task_baseline_correctness.py',
             'task_baseline_pmu.py', 'task_baseline_controller.py', 'validation_host_evaluator.py', 'shared_validation_adapter.py',
             'shared_mechanism_adapter.py', 'shared_multikernel_adapter.py', 'local_controller_bridge.py',
             'validation_operator_adapter.py', 'run_aprof_job.py', 'timing_admission.py', 'eval_tool_broker.py')
    return {str(Path(__file__).with_name(name)) for name in names} | {
        str(bridge.RELEASE / name) for name in PRODUCER_FILES} | {str(bridge.adapter.base.old.HEADER)}


def _local(local):
    bridge.adapter.base.selected_runtime()
    require(isinstance(local, LocalEvidence) and bridge.RELEASE.name == '1.0.0'
            and bridge.timing.PROTOCOL == 'shared_buffer_msprof_task_window_v5',
            'baseline Task qualification requires selected 1.0.0/v5 LocalEvidence')


def _read(local, reference):
    return json.loads(local.verify_artifact(reference).read_text())


def _path(value):
    path = Path(value)
    require(path.is_absolute() and path.resolve() == path and '..' not in path.parts,
            'baseline paths must be canonical absolute paths')
    return path


def _bindings(local, values, required):
    require(isinstance(values, dict) and set(values) == set(required), 'baseline dependency roster differs')
    for name, reference in values.items():
        path = _path(name)
        local.verify_artifact(reference)
        require(path.is_file() and not path.is_symlink() and file_hash(path) == reference,
                'baseline dependency/source changed')


def case_scope(operator, metadata):
    require(operator in OPERATORS, 'unsupported validation baseline operator')
    if operator in multi.OPERATORS:
        return multi.case_binding(operator, metadata)
    return {'launches_per_call': {role: 1 for role in ROLES},
            'role_kernel_names': {role: [f'aprof_{role}_{operator}_kernel'] for role in ROLES}}


def _case(local, operator, metadata_path, bind):
    metadata_path = _path(metadata_path)
    metadata_ref = bind(metadata_path)
    metadata = _read(local, metadata_ref)
    require(type(metadata.get('case_id')) is int, 'original metadata case id must be an integer')
    output_keys = ['output_y', 'output_scale'] if operator == 'dynamic_quant' else ['output']
    inputs = {}
    def visit(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key not in output_keys: visit(child)
        elif isinstance(value, list):
            for child in value: visit(child)
        elif isinstance(value, str) and Path(value).is_absolute():
            inputs[str(_path(value))] = bind(value)
    visit(metadata)
    require(inputs, 'baseline case lacks original input files')
    return {'case_id': metadata['case_id'], 'metadata_path': str(metadata_path), 'metadata_ref': metadata_ref,
            'input_files': dict(sorted(inputs.items())),
            'workload': bridge.adapter.base.old.json_contract({k:v for k,v in metadata.items() if k not in output_keys}),
            **case_scope(operator, metadata)}


def _profile(profile, cases):
    require(isinstance(profile, dict) and set(profile) == {'case_id', 'kernels', 'metrics'}
            and type(profile['case_id']) is int and profile['case_id'] in CASE_IDS,
            'baseline needs fixed PMU choices before collection')
    names = cases[profile['case_id']-1]['role_kernel_names']['baseline']
    names = {name.removeprefix('aprof_baseline_') for name in names}
    require(isinstance(profile['kernels'], list) and profile['kernels']
            and len(set(profile['kernels'])) == len(profile['kernels'])
            and set(profile['kernels']) <= names, 'PMU choices differ from exact complete-call kernel names')
    require(isinstance(profile['metrics'], dict) and profile['metrics'], 'fixed PMU metric scope missing')
    for name, spec in profile['metrics'].items():
        require(isinstance(name, str) and name and set(spec) == {
            'unit','file','format','field','row_aggregation','aggregation'}
            and all(isinstance(value,str) and value for value in spec.values())
            and spec['file']=='op_summary*.csv' and spec['format']=='csv'
            and spec['row_aggregation']==spec['aggregation']=='median',
            'PMU metric cell and median reducers must be frozen')


def prepare_baseline_plan(local, *, operator, sources, assembly, prepared_inputs, scratch_root,
                          preparation_ref, profile, job_ref, identity, physical_device, created_at,
                          toolchain_refs, producer_refs, collection_stop_policy=None, _replay=False):
    """Freeze existing inputs only; no generation, assembly, build, capture or copy."""
    _local(local)
    def bind(path):
        if not _replay:
            return local.register_artifact(path)
        reference = file_hash(_path(path))
        local.verify_artifact(reference)
        return reference
    require(operator in OPERATORS and set(sources)==set(ROLES) and set(identity)=={
        'run_id','session_id','candidate_id'} and all(isinstance(v,str) and v for v in identity.values()),
        'baseline plan identity differs')
    preparation = _read(local, preparation_ref)
    require(preparation['operator']==operator and preparation['schema_version']==1
            and preparation['state']=='cpu_prepared_awaiting_baseline_qualification',
            'original source preparation receipt differs')
    roles, hashes = {}, {}
    for role in ROLES:
        source = _path(sources[role])
        files = bridge.profile_capture.source_inventory(source)
        require(all(bind(source/name)==reference for name,reference in files.items()), 'source changed while binding')
        require(files == preparation['source_files'], 'baseline A/A source differs from original preparation')
        roles[role] = {'path':str(source),'files':files}
        bundle={'schema_version':'1.0.0','files':files}
        hashes[role] = content_hash(bundle) if _replay else local.register_json(bundle)
        local.verify_artifact(hashes[role])
    require(roles['baseline']['path'] != roles['candidate']['path'] and hashes['baseline']==hashes['candidate'],
            'baseline A/A needs distinct role directories and identical complete source bytes')
    cases = [_case(local,operator,_path(prepared_inputs)/f'case_{cid:02d}/metadata.json',bind) for cid in CASE_IDS]
    require([case['case_id'] for case in cases]==CASE_IDS, 'all original 20 cases are required in order')
    _profile(profile,cases)
    job = _read(local,job_ref)
    budget = positive(job['timeout_seconds'])
    require(type(physical_device) is int and physical_device>=0, 'physical device identity differs')
    _bindings(local,toolchain_refs,PROFILE_DEPENDENCY_PATHS)
    _bindings(local,producer_refs,producer_paths())
    headers = {name:bind(bridge.adapter.base.ASSETS/name) for name in bridge.adapter.base.HEADERS}
    plan = {'schema_version':1,'kind':'task_baseline_qualification_plan','protocol':PROTOCOL,
        'task_protocol':bridge.timing.PROTOCOL,'budget_policy':BUDGET_POLICY,'operator':operator,**identity,
        'case_ids':CASE_IDS,'device':0,'physical_device':physical_device,'budget_seconds':budget,
        'job_ref':job_ref,'created_at':number(created_at),'assembly_dir':str(_path(assembly)),
        'scratch_root':str(_path(scratch_root)),'preparation_ref':preparation_ref,
        'source_review_ref':bind(_path(assembly)/'source-review.json'),
        'roles':roles,'source_hashes':hashes,'headers':headers,'toolchain_refs':toolchain_refs,
        'producer_refs':producer_refs,'cases':cases,'profile':profile}
    if collection_stop_policy is not None:
        plan['collection_stop_policy']=collection_stop_policy
        collection_policy(plan)
    from task_baseline_pmu import scope_from_plan
    plan['pmu_scope'] = scope_from_plan(plan)
    return content_hash(plan) if _replay else local.register_json(plan)


def checked_plan(local, plan_ref):
    _local(local)
    plan = _read(local,plan_ref)
    require(plan.get('protocol')==PROTOCOL and plan.get('kind')=='task_baseline_qualification_plan'
            and plan.get('task_protocol')==bridge.timing.PROTOCOL and plan.get('budget_policy')==BUDGET_POLICY
            and plan['case_ids']==CASE_IDS, 'unsupported baseline qualification plan')
    # Recompute the same immutable plan from every currently indexed original byte.
    rebuilt = prepare_baseline_plan(local,operator=plan['operator'],
        sources={r:plan['roles'][r]['path'] for r in ROLES},assembly=plan['assembly_dir'],
        prepared_inputs=Path(plan['cases'][0]['metadata_path']).parent.parent,
        scratch_root=plan['scratch_root'],preparation_ref=plan['preparation_ref'],profile=plan['profile'],
        job_ref=plan['job_ref'],identity={k:plan[k] for k in ('run_id','session_id','candidate_id')},
        physical_device=plan['physical_device'],created_at=plan['created_at'],
        toolchain_refs=plan['toolchain_refs'],producer_refs=plan['producer_refs'],
        collection_stop_policy=plan.get('collection_stop_policy'),_replay=True)
    require(rebuilt==plan_ref, 'baseline plan differs from independently reconstructed source/input scope')
    return plan


def _task_config(local, plan, build_receipt, build):
    operator = plan['operator']; source = Path(plan['assembly_dir'])/'source'; binary = build['binary']['path']
    adapter = multi if operator in multi.OPERATORS else bridge.adapter.base
    keys = ['output_y','output_scale'] if operator=='dynamic_quant' else ['output']
    config = {'schema_version':'1.0.0','operator':operator,
        **{key:plan[key] for key in ('run_id','session_id','candidate_id','device','physical_device')},
        'expected_case_ids':CASE_IDS,
        'roles':{r:{'source_dir':plan['roles'][r]['path'],'symbol':'launch_'+r,
            'launches_per_operator':{str(c['case_id']):c['launches_per_call'][r] for c in plan['cases']}} for r in ROLES},
        'build':{'source_dir':str(source),'binary':binary,'receipt_files':[str(build_receipt),
            str(Path(plan['assembly_dir'])/'source-review.json'),build['attempt_ref']['path']]},
        'task_profile':{'profiler':'/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof',
            'scratch_root':plan['scratch_root'],'role_kernel_names':{
                r:{str(c['case_id']):c['role_kernel_names'][r] for c in plan['cases']} for r in ROLES}},'cases':[]}
    for case in plan['cases']:
        metadata = _read(local,case['metadata_ref'])
        outputs = {r:{key:'{cycle_dir}/'+r+'-'+key+'.bin' for key in keys} for r in ROLES}
        absolute = {r:{key:value.replace('{cycle_dir}','/APROF_CYCLE') for key,value in files.items()} for r,files in outputs.items()}
        routing = {absolute[r][key]:outputs[r][key] for r in ROLES for key in keys}
        command = [routing.get(v,v) for v in adapter.case_command(operator,binary,metadata,0,absolute)]
        config['cases'].append({'case_id':case['case_id'],'workload':case['workload'],
            'prepared_files':[case['metadata_path'],*sorted(case['input_files'])],'command':command,
            'verify_commands':{r:adapter.oracle_command(operator,source,Path(sys.executable).resolve(),
                Path(case['metadata_path']),outputs[r],'{cycle_dir}/'+r+'-result.json') for r in ROLES},
            'output_files':{r:list(outputs[r].values()) for r in ROLES}})
    case_task_config(config)
    return config


def baseline_task_config(local, *, plan_ref, build_receipt_ref):
    """Bind the new baseline-only build, without inventing a candidate route receipt."""
    from task_baseline_build import checked_baseline_build
    plan = checked_plan(local,plan_ref)
    receipt = local.verify_artifact(build_receipt_ref)
    _, build = checked_baseline_build(local,plan_ref=plan_ref,build_receipt_ref=build_receipt_ref)
    return bridge.timing.config_value(_task_config(local,plan,receipt,build))


def replay_baseline_task(local, *, plan_ref, build_receipt_ref, completion_ref, execution_ref):
    """Full Task replay plus real outer exit; explicitly not full PMU qualification."""
    from task_baseline_build import checked_baseline_build
    plan = checked_plan(local,plan_ref)
    job = _read(local,plan['job_ref']); execution = _read(local,execution_ref)
    require(file_hash(_path(job['output_dir'])/'execution.json')==execution_ref
            and execution.get('kind')=='aprof_execution_report' and execution.get('schema_version')=='1.0.0'
            and execution.get('job')==job and execution.get('status')=='passed'
            and type(execution.get('exit_code')) is int and execution['exit_code']==0 and not execution.get('error'),
            'baseline needs the original successful dispatcher exit, not a claimed passed summary')
    def timestamp(value):
        parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
        require(parsed.tzinfo is not None, 'dispatcher timestamp needs an explicit timezone')
        return number(parsed.timestamp())
    start,end = [timestamp(execution[key]) for key in ('started_at','finished_at')]
    require(number(plan['created_at'])<=start<end and end-start<=budget_seconds(plan)
            and 0<number(execution['duration_seconds'])<=positive(job['timeout_seconds'])==budget_seconds(plan), 'whole baseline job exceeds its original deadline')
    for key in ('stdout','stderr'):
        ref=execution[key];_bindings(local,{ref['path']:ref['sha256']},{ref['path']})
    receipt=local.verify_artifact(build_receipt_ref)
    _,build=checked_baseline_build(local,plan_ref=plan_ref,build_receipt_ref=build_receipt_ref)
    completion=_read(local,completion_ref)
    require(start<=number(build['started_at'])<=number(build['finished_at'])<=number(completion['started_at'])
            <number(completion['finished_at'])<=end, 'baseline build/Task/dispatcher chronology differs')
    expected={key:plan[key] for key in ('operator','run_id','session_id','candidate_id','source_hashes')}
    replay=replay_current_measurement_admission(local,completion_ref,expected=expected)
    require(replay['valid'] is True and _read(local,replay['config_ref'])==_task_config(local,plan,receipt,build),
            'baseline Task evidence differs from original complete-call plan')
    return {'valid':True,'scope':'baseline_AA_Task_and_actual_exit','plan_ref':plan_ref,
        'completion_ref':completion_ref,'execution_ref':execution_ref,'measurement':replay,
        'qualification_passed':False,'admission_authority':False,'eligible_for_publication':False,
        'archive_performed':False,'missing_joins':['independent_correctness_stage','fixed_PMU_occurrence_scope',
                                                'online_qualification_dispatcher']}
