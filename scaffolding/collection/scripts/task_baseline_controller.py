#!/usr/bin/env python3
"""Finite original-baseline jobs, LocalEvidence only; not activated by evaluation.

The original dispatcher deadline covers build, correctness, Task, PMU and online
replay. An independent reader joins actual exit to recomputed components. No
candidate route is fabricated; graph Context integration remains separate.
"""
from task_budget import budget_seconds, positive, collection_policy
import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
import time

import task_baseline_build as builder
import task_baseline_correctness as correctness
import task_baseline_pmu as pmu
import task_baseline_qualification as baseline
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.jsonio import file_hash
from aprof_runtime.measurement_entry import replay_current_measurement_admission
from run_aprof_job import run as run_job
from validation_host_evaluator import Commands
from timing_admission import number, require

bridge=baseline.bridge
ENABLED_IN_1_0=False
KINDS=('build_receipt_ref','correctness_ref','completion_ref','pmu_ref')


def job(directory, *, operator, physical_device, budget_seconds=3600):
    root=Path(directory).absolute()
    require(operator in baseline.OPERATORS, 'unknown original baseline')
    return dict(job_id='baseline-'+operator,argv=[str(Path(sys.executable).resolve()),str(Path(__file__).resolve()),
        '--attempt',str(root/'baseline-attempt.json'),'--local-index',str(root/'prepared-local-index.json')],
        cwd=str(bridge.adapter.base.REPO),output_dir=str(root/'job'),timeout_seconds=positive(budget_seconds),
        environment=dict(APROF_SKILL_LIB=str(bridge.RELEASE),ASCEND_HOME_PATH=builder.CANN_HOME,
            ASCEND_RT_VISIBLE_DEVICES=str(physical_device),APROF_PHYSICAL_DEVICE=str(physical_device),
            APROF_LOGICAL_DEVICE='0',PYTHONDONTWRITEBYTECODE='1',**builder.CPU_REFERENCE_ENV))


def _read(local,ref):
    return json.loads(local.verify_artifact(ref).read_text())


def _save(local,path,value):
    bridge.save(path,value)
    return local.register_artifact(path)


def prepare_attempt(local, *, plan_ref, directory):
    plan=baseline.checked_plan(local,plan_ref);root=Path(directory)
    require(root.is_absolute() and root.resolve()==root and root.is_relative_to(local.directory.parent),
            'baseline attempt must remain inside task-local work')
    require(_read(local,plan['job_ref'])==job(root,operator=plan['operator'],physical_device=plan['physical_device'],budget_seconds=plan['budget_seconds']),
            'baseline plan needs this exact finite dispatcher job')
    root.mkdir(parents=True,exist_ok=True)
    require(not any((root/name).exists() for name in ('dispatcher-launch.json','controller-result.json','job')),
            'baseline attempt already started')
    attempt=dict(schema_version=1,kind='baseline_task_attempt',plan_ref=plan_ref,operator=plan['operator'],
        directory=str(root),created_at=time.time(),max_attempts=1,budget_seconds=plan['budget_seconds'],budget_policy='time_only_v1')
    reference=_save(local,root/'baseline-attempt.json',attempt)
    local.write_index(root/'prepared-local-index.json')
    return reference


def _checked(local,attempt_ref):
    attempt=_read(local,attempt_ref);plan=baseline.checked_plan(local,attempt['plan_ref']);root=Path(attempt['directory'])
    require(set(attempt)=={'schema_version','kind','plan_ref','operator','directory','created_at','max_attempts',
            'budget_seconds','budget_policy'} and attempt['schema_version']==1 and attempt['kind']=='baseline_task_attempt'
        and attempt['operator']==plan['operator'] and attempt['budget_policy']=='time_only_v1'
        and number(plan['created_at'])<=number(attempt['created_at'])
        and root.is_absolute() and root.resolve()==root and root.is_relative_to(local.directory.parent)
        and attempt['max_attempts']==1 and budget_seconds(attempt)==budget_seconds(plan)
        and file_hash(root/'baseline-attempt.json')==attempt_ref
        and _read(local,plan['job_ref'])==job(root,operator=plan['operator'],physical_device=plan['physical_device'],budget_seconds=plan['budget_seconds']),
        'baseline preregistration or original job differs')
    return attempt,plan,root


def replay_components(local, *, plan_ref, references):
    """Always invoke the real correctness/Task/PMU readers, never saved verdicts."""
    require(set(references)==set(KINDS), 'baseline stage roster differs')
    plan=baseline.checked_plan(local,plan_ref);build_ref=references['build_receipt_ref']
    _,build=builder.checked_baseline_build(local,plan_ref=plan_ref,build_receipt_ref=build_ref)
    accuracy=correctness.verify_baseline_correctness(local,plan_ref=plan_ref,build_receipt_ref=build_ref,
                                                   report_ref=references['correctness_ref'])
    task=replay_current_measurement_admission(local,references['completion_ref'],expected={
        key:plan[key] for key in ('operator','run_id','session_id','candidate_id','source_hashes')})
    require(task['valid'] is True and _read(local,task['config_ref'])==baseline._task_config(
        local,plan,local.verify_artifact(build_ref),build), 'baseline Task config differs from complete-call plan')
    profile=pmu.verify_baseline_pmu(local,plan_ref=plan_ref,build_receipt_ref=build_ref,report_ref=references['pmu_ref'])
    require(accuracy['valid'] is True and profile['valid'] is True and profile['pmu_complete'] is True
        and all(cell.get('status')=='known' and cell.get('stable') is True
            for kernels in profile['metrics'].values() for metrics in kernels.values() for cell in metrics.values()),
        'baseline correctness or fixed full-occurrence PMU availability/stability failed')
    a,t,p=(_read(local,references[k]) for k in ('correctness_ref','completion_ref','pmu_ref'))
    require(build['finished_at']<=a['started_at']<=a['finished_at']<=t['started_at']<=t['finished_at']
        <=p['started_at']<=p['finished_at']
        and a['deadline_monotonic']==p['deadline_monotonic']==build['deadline_monotonic'],
        'baseline stages overlap, reorder, or reset the task budget')
    return dict(valid=True,scope='original_baseline_correctness_Task_v5_full_PMU',
        plan_ref=plan_ref,references=references,task=task,correctness=accuracy,
        pmu=dict(valid=True,pmu_complete=True,metrics=profile['metrics']),admission_authority=False)


def run_child(attempt_path,index_path):
    started,mono=time.time(),time.monotonic()
    local=LocalEvidence.from_index(index_path);attempt_ref=local.register_artifact(attempt_path)
    raw=_read(local,attempt_ref);root=Path(raw['directory'])
    budget=budget_seconds(raw)
    launch=json.loads((root/'dispatcher-launch.json').read_text())
    deadline=number(launch['deadline_monotonic'])
    require(launch['attempt_ref']==attempt_ref and launch['started_at']<=started
        and deadline==number(launch['started_monotonic'])+budget and deadline<=mono+budget,
        'child must inherit original dispatcher deadline')
    _save(local,root/'controller-start.json',dict(attempt_ref=attempt_ref,started_at=started))
    plan=None
    references={};result=dict(schema_version=1,status='failed',attempt_ref=attempt_ref,started_at=started,
        started_monotonic=mono,deadline_monotonic=deadline,references=references,error=None,
        qualification_passed=False,archive_performed=False)
    try:
        bridge.remaining(deadline)
        attempt,plan,root=_checked(local,attempt_ref)
        commands=Commands(root/'commands',deadline)
        references['build_receipt_ref']=builder.build_baseline_once(local,plan_ref=attempt['plan_ref'],commands=commands)
        with bridge.timing.shared.device_lock(plan['physical_device'],bridge.remaining(deadline)):
            references['correctness_ref']=correctness.collect_baseline_correctness(local,plan_ref=attempt['plan_ref'],
                build_receipt_ref=references['build_receipt_ref'],commands=commands,destination=root/'correctness')
        config=baseline.baseline_task_config(local,plan_ref=attempt['plan_ref'],build_receipt_ref=references['build_receipt_ref'])
        measured=bridge.collect_task(config,root/'measurement',local,deadline=deadline,
            budget_binding={'kind':'baseline','launch_ref':local.register_artifact(root/'dispatcher-launch.json')})
        references['completion_ref']=measured['measurement_admission_ref']
        references['pmu_ref']=pmu.collect_baseline_pmu(local,plan_ref=attempt['plan_ref'],
            build_receipt_ref=references['build_receipt_ref'],destination=root/'pmu',deadline=deadline)
        bridge.remaining(deadline)
        result['online_replay_started_at']=time.time()
        online=replay_components(local,plan_ref=attempt['plan_ref'],references=references)
        bridge.remaining(deadline)
        result['online_replay_ref']=local.register_json(online)
        result['status']='components_completed'
    except BaseException as error:
        result['error']=dict(type=type(error).__name__,message=str(error))
        if getattr(error,'report_ref',None):result['partial_report_ref']=error.report_ref
    finally:
        result.update(finished_at=time.time(),finished_monotonic=time.monotonic())
        if result['finished_monotonic']>=deadline:
            result.update(status='failed',error=dict(type='TimeoutError',message='original baseline task deadline expired'))
        # Build/correctness failures already have their original partial receipts.
        partials=[('partial_pmu_ref',root/'pmu/pmu-report.json')]
        if plan:partials.append(('partial_build_ref',Path(plan['assembly_dir'])/'build-receipt.json'))
        for name,path in partials:
            if path.is_file():result[name]=local.register_artifact(path)
        _save(local,root/'controller-result.json',result)
        local.write_index(root/'controller-local-index.json')
    return result


def dispatch(local, *, attempt_ref):
    started,mono=time.time(),time.monotonic()
    attempt,plan,root=_checked(local,attempt_ref)
    budget=budget_seconds(plan)
    require(not (root/'job').exists(), 'baseline dispatcher cannot reuse a job')
    issued=time.monotonic();remaining=mono+budget-issued
    require(remaining>0, 'baseline preparation exhausted original deadline')
    _save(local,root/'dispatcher-launch.json',dict(attempt_ref=attempt_ref,started_at=started,
        started_monotonic=mono,deadline_monotonic=mono+budget,issued_monotonic=issued,
        child_timeout_seconds=remaining))
    result=dict(schema_version=1,attempt_ref=attempt_ref,status='failed',started_at=started,error=None,
                qualification_passed=False,archive_performed=False)
    try:
        bridge.remaining(mono+budget)
        actual_job=dict(_read(local,plan['job_ref']),timeout_seconds=remaining,deadline_monotonic=mono+budget)
        execution=run_job(actual_job)
        if (root/'controller-local-index.json').is_file():
            child=LocalEvidence.from_index(root/'controller-local-index.json')
            require(child.directory==local.directory, 'child evidence escaped original local workspace')
            local=child
        execution_ref=local.register_artifact(root/'job/execution.json')
        require(_read(local,execution_ref)==execution and execution['job']==actual_job, 'actual dispatcher result differs')
        result['execution_ref']=execution_ref
        if (root/'controller-result.json').is_file():
            result['controller_result_ref']=local.register_artifact(root/'controller-result.json')
            terminal=_read(local,result['controller_result_ref'])
            require(terminal['attempt_ref']==attempt_ref, 'child substituted baseline attempt')
            if execution['status']=='passed' and execution['exit_code']==0 and terminal['status']=='components_completed':
                bridge.remaining(mono+budget)
                result['status']='completed_child'
    except BaseException as error:
        result['error']=dict(type=type(error).__name__,message=str(error))
    finally:
        if (root/'job/execution.json').is_file():
            result['execution_ref']=local.register_artifact(root/'job/execution.json')
            for key in ('stdout','stderr'):
                pointer=_read(local,result['execution_ref'])[key]
                require(local.register_artifact(pointer['path'])==pointer['sha256'], 'dispatcher log changed')
        result['finished_at']=time.time()
        result['finished_monotonic']=time.monotonic()
        if result['finished_monotonic']>=mono+budget:
            result.update(status='failed',error=dict(type='TimeoutError',message='original baseline task deadline expired'))
        _save(local,root/'dispatcher-result.json',result)
        local.write_index(root/'dispatcher-local-index.json')
    return result


def verify_baseline_qualification(local, *, attempt_ref, result_ref):
    attempt,plan,root=_checked(local,attempt_ref);result=_read(local,result_ref)
    require(file_hash(root/'dispatcher-result.json')==result_ref and result['attempt_ref']==attempt_ref
        and result['status']=='completed_child' and result['error'] is None
        and result['qualification_passed'] is result['archive_performed'] is False,
        'baseline dispatcher did not complete')
    execution=_read(local,result['execution_ref']);child=_read(local,result['controller_result_ref'])
    launch=json.loads((root/'dispatcher-launch.json').read_text())
    start,end=(datetime.fromisoformat(execution[key].replace('Z','+00:00')) for key in ('started_at','finished_at'))
    expected_job=dict(_read(local,plan['job_ref']),timeout_seconds=launch['child_timeout_seconds'])
    if 'deadline_monotonic' in execution['job']:
        expected_job['deadline_monotonic']=launch['deadline_monotonic']
    elif budget_seconds(plan)!=3600:
        raise ValueError('adjustable baseline needs its original absolute job deadline')
    require(start.tzinfo and end.tzinfo and execution['job']==expected_job
        and execution.get('schema_version')=='1.0.0' and execution.get('kind')=='aprof_execution_report'
        and file_hash(root/'job/execution.json')==result['execution_ref'] and execution['status']=='passed'
        and type(execution['exit_code']) is int and execution['exit_code']==0 and not execution.get('error')
        and 0<number(execution['duration_seconds'])<=launch['child_timeout_seconds']
        and attempt['created_at']<=launch['started_at']<=start.timestamp()<=child['started_at']
        <=child['finished_at']<=end.timestamp()<=result['finished_at']
        and result['finished_monotonic']<=launch['deadline_monotonic']==child['deadline_monotonic']
        ==launch['started_monotonic']+budget_seconds(plan) and child['status']=='components_completed'
        and launch['started_monotonic']<=launch['issued_monotonic']<launch['deadline_monotonic']
        and launch['child_timeout_seconds']==launch['deadline_monotonic']-launch['issued_monotonic']
        and launch['attempt_ref']==attempt_ref and result['started_at']==launch['started_at']
        and launch['issued_monotonic']<=child['started_monotonic']<=child['finished_monotonic']
        <=result['finished_monotonic'] and child['qualification_passed'] is child['archive_performed'] is False
        and child['error'] is None and child['attempt_ref']==attempt_ref
        and file_hash(root/'controller-result.json')==result['controller_result_ref'],
        'baseline actual exit, whole deadline, or child identity differs')
    for key in ('stdout','stderr'):
        pointer=execution[key];require(file_hash(pointer['path'])==pointer['sha256'],'baseline dispatcher log changed')
        local.verify_artifact(pointer['sha256'])
    rebuilt=replay_components(local,plan_ref=attempt['plan_ref'],references=child['references'])
    build=_read(local,child['references']['build_receipt_ref'])
    require(build['deadline_monotonic']==child['deadline_monotonic']
        and child['started_at']<=build['started_at']
        and child['started_monotonic']<=build['started_monotonic'], 'baseline build restarted the task deadline')
    require(rebuilt==_read(local,child['online_replay_ref']) and child['online_replay_started_at']
        >=_read(local,child['references']['pmu_ref'])['finished_at']
        and child['online_replay_started_at']<=child['finished_at'], 'saved online baseline replay differs')
    return dict(valid=True,status='passed',qualification_passed=True,attempt_ref=attempt_ref,
        operator=plan['operator'],plan_ref=attempt['plan_ref'],
        result_ref=result_ref,execution_ref=result['execution_ref'],components=rebuilt,
        scope='original_baseline_AA_Task_v5_full_PMU',graph_route_granted=False,archive_performed=False)


def prepare_campaign(local, attempts):
    require([item['operator'] for item in attempts]==list(baseline.OPERATORS), 'finite campaign must cover all five originals')
    frozen=[]; budgets=[]; policies=[]
    for item in attempts:
        require(set(item)=={'operator','attempt_ref','local_index'}, 'baseline campaign fields differ')
        reader=LocalEvidence.from_index(item['local_index'])
        attempt,plan,root=_checked(reader,item['attempt_ref'])
        policies.append(collection_policy(plan))
        budgets.append(budget_seconds(attempt))
        require(attempt['operator']==item['operator'] and not (root/'dispatcher-launch.json').exists(),
                'campaign cannot register an existing launch')
        frozen.append(dict(item,local_index_ref=local.register_artifact(item['local_index'])))
    require(len(set(budgets))==1 and all(p==policies[0] for p in policies), 'all original baseline attempts must share one frozen budget/policy')
    return local.register_json(dict(schema_version=1,kind='finite_baseline_campaign',created_at=time.time(),
        attempts=frozen,attempts_per_operator=1,per_operator_seconds=budgets[0],archive_performed=False,
        **({'collection_stop_policy':policies[0]} if policies[0] is not None else {})))


def dispatch_five(reader, *, campaign_ref):
    """Each original operator gets one attempt; unrelated failures do not stop peers."""
    campaign=_read(reader,campaign_ref);attempts=campaign['attempts']
    require(campaign['kind']=='finite_baseline_campaign' and campaign['attempts_per_operator']==1
        and positive(campaign['per_operator_seconds'])>0
        and [item['operator'] for item in attempts]==list(baseline.OPERATORS), 'finite campaign must cover all five originals')
    results=[]
    for item in attempts:
        try:
            require(file_hash(item['local_index'])==item['local_index_ref'], 'prepared local handoff changed')
            reader.verify_artifact(item['local_index_ref'])
            local=LocalEvidence.from_index(item['local_index'])
            attempt,plan,_=_checked(local,item['attempt_ref'])
            require(attempt['operator']==item['operator'] and budget_seconds(plan)==campaign['per_operator_seconds']
                and collection_policy(plan)==campaign.get('collection_stop_policy'), 'campaign operator/budget/policy differs')
            result=dispatch(local,attempt_ref=item['attempt_ref'])
        except Exception as error:
            result=dict(status='not_run',operator=item['operator'],error=dict(type=type(error).__name__,message=str(error)),
                        qualification_passed=False,archive_performed=False)
        results.append(result)
    return reader.register_json(dict(campaign_ref=campaign_ref,results=results,qualification_passed=False,archive_performed=False))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--local-index',type=Path,required=True)
    args=parser.parse_args();result=run_child(args.attempt,args.local_index)
    raise SystemExit(0 if result['status']=='components_completed' else 1)


if __name__=='__main__':main()
