"""Controller joins with bounded CPU doubles, not baseline hardware acceptance."""
import contextlib
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import pytest
import task_baseline_controller as controller
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.errors import ContractError


def dump(local,path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value));return local.register_artifact(path)


def child_fixture(tmp_path,monkeypatch):
    local=LocalEvidence(tmp_path/'records');budget=7200
    plan=dict(operator='gelu',assembly_dir=str(tmp_path/'assembly'),physical_device=0,budget_seconds=budget)
    plan_ref=local.register_json(plan)
    attempt=dict(directory=str(tmp_path),plan_ref=plan_ref,budget_seconds=budget)
    attempt_ref=dump(local,tmp_path/'baseline-attempt.json',attempt)
    now=time.monotonic();deadline=now+120
    dump(local,tmp_path/'dispatcher-launch.json',dict(attempt_ref=attempt_ref,started_at=time.time()-(budget-120),
        started_monotonic=deadline-budget,deadline_monotonic=deadline,issued_monotonic=now-1,child_timeout_seconds=121))
    index=local.write_index(tmp_path/'prepared-local-index.json')
    monkeypatch.setattr(controller,'_checked',lambda *a:(attempt,plan,tmp_path))
    monkeypatch.setattr(controller.bridge.timing.shared,'device_lock',lambda *a:contextlib.nullcontext())
    return local,plan,attempt_ref,index,deadline


def test_job_selects_actual_runtime_without_nested_device_lock(tmp_path):
    job=controller.job(tmp_path,operator='gqa',physical_device=3)
    assert job['cwd']==str(controller.bridge.adapter.base.REPO)
    assert job['timeout_seconds']==3600 and 'physical_device' not in job
    assert job['environment']['ASCEND_RT_VISIBLE_DEVICES']=='3'
    assert job['environment']['APROF_SKILL_LIB'].endswith('/1.0.0')


@pytest.mark.parametrize('failed_stage',['build','correctness','Task','PMU','online'])
def test_one_deadline_and_failure_halts_later_stages(tmp_path,monkeypatch,failed_stage):
    local,plan,ref,index,deadline=child_fixture(tmp_path,monkeypatch);calls=[]
    def stage(name):
        calls.append(name)
        if name==failed_stage:raise RuntimeError('CPU fixture '+name+' failure')
    def build(local,*,plan_ref,commands):
        assert commands.deadline==deadline;stage('build');return local.register_json({'kind':'CPU build fixture'})
    def accuracy(local,*,plan_ref,build_receipt_ref,commands,destination):
        assert commands.deadline==deadline;stage('correctness');return local.register_json({'kind':'CPU accuracy fixture'})
    def task(config,output,local,*,deadline,budget_binding):
        assert deadline==child_deadline
        assert budget_binding=={'kind':'baseline','launch_ref':local.register_artifact(tmp_path/'dispatcher-launch.json')}
        stage('Task');return {'measurement_admission_ref':local.register_json({'kind':'CPU Task fixture'})}
    def pmu(local,*,plan_ref,build_receipt_ref,destination,deadline):
        assert deadline==child_deadline;stage('PMU');return local.register_json({'kind':'CPU PMU fixture'})
    def online(*a,**kw):stage('online');return {'valid':True,'CPU_fixture_only':True}
    child_deadline=deadline
    monkeypatch.setattr(controller.builder,'build_baseline_once',build)
    monkeypatch.setattr(controller.correctness,'collect_baseline_correctness',accuracy)
    monkeypatch.setattr(controller.baseline,'baseline_task_config',lambda *a,**kw:{})
    monkeypatch.setattr(controller.bridge,'collect_task',task)
    monkeypatch.setattr(controller.pmu,'collect_baseline_pmu',pmu)
    monkeypatch.setattr(controller,'replay_components',online)
    result=controller.run_child(tmp_path/'baseline-attempt.json',index)
    order=['build','correctness','Task','PMU','online']
    assert calls==order[:order.index(failed_stage)+1] and result['status']=='failed'
    assert not result['qualification_passed'] and not result['archive_performed']
    retained=LocalEvidence.from_index(tmp_path/'controller-local-index.json')
    assert retained.verify_artifact(retained.register_artifact(tmp_path/'controller-result.json')).is_file()
    assert not list(tmp_path.rglob('*.sqlite'))


def test_task_saved_passed_summary_cannot_replace_real_completion_replay(tmp_path,monkeypatch):
    local=LocalEvidence(tmp_path/'records')
    plan={k:'CPU' for k in ('operator','run_id','session_id','candidate_id')}
    plan['source_hashes']={r:local.register_json({'source':r}) for r in ('baseline','candidate')}
    references={key:local.register_json({'status':'passed','kind':key}) for key in controller.KINDS}
    monkeypatch.setattr(controller.baseline,'checked_plan',lambda *a:plan)
    monkeypatch.setattr(controller.builder,'checked_baseline_build',lambda *a,**kw:({},{}))
    monkeypatch.setattr(controller.correctness,'verify_baseline_correctness',lambda *a,**kw:{'valid':True})
    with pytest.raises(ContractError,match='completion'):
        controller.replay_components(local,plan_ref='CPU',references=references)


@pytest.mark.parametrize('budget',[3600,7200])
def test_dispatch_timeout_deducts_prelaunch_work_and_retains_actual_failure(tmp_path,monkeypatch,budget):
    local=LocalEvidence(tmp_path/'records');plan={'budget_seconds':budget,
        'job_ref':local.register_json(controller.job(tmp_path,operator='gelu',physical_device=0,budget_seconds=budget))}
    now=time.monotonic();clock=iter([now,now+7,now+8])
    monkeypatch.setattr(controller.time,'monotonic',lambda:next(clock))
    monkeypatch.setattr(controller,'_checked',lambda *a:({},plan,tmp_path))
    monkeypatch.setattr(controller.bridge,'remaining',lambda deadline:deadline-(now+7))
    calls=[]
    def failed(job):
        calls.append(job);folder=Path(job['output_dir']);folder.mkdir()
        log=folder/'stdout.log';log.write_text('explicit CPU dispatcher failure fixture')
        pointer={'path':str(log),'sha256':local.register_artifact(log)}
        record=dict(job=job,status='failed',exit_code=2,stdout=pointer,stderr=pointer)
        (folder/'execution.json').write_text(json.dumps(record));return record
    monkeypatch.setattr(controller,'run_job',failed)
    result=controller.dispatch(local,attempt_ref='CPU')
    assert calls[0]['timeout_seconds']==budget-7 and result['status']=='failed'
    assert calls[0]['deadline_monotonic']==now+budget
    assert 'execution_ref' in result and not result['qualification_passed']
    assert (tmp_path/'dispatcher-result.json').is_file()


def test_finite_campaign_keeps_other_independent_operators_after_failure(tmp_path,monkeypatch):
    reader=LocalEvidence(tmp_path/'records');attempts=[];calls=[]
    for op in controller.baseline.OPERATORS:
        folder=tmp_path/op;folder.mkdir();local=LocalEvidence(folder/'records')
        attempt_ref=local.register_json({'operator':op});index=local.write_index(folder/'prepared-local-index.json')
        attempts.append(dict(operator=op,attempt_ref=attempt_ref,local_index=str(index),local_index_ref=reader.register_artifact(index)))
    reference=reader.register_json(dict(kind='finite_baseline_campaign',attempts=attempts,
        attempts_per_operator=1,per_operator_seconds=3600))
    def check(local,ref):
        op=json.loads(local.verify_artifact(ref).read_text())['operator'];return {'operator':op},{'budget_seconds':3600},tmp_path/op
    def dispatch(local,*,attempt_ref):
        op=check(local,attempt_ref)[0]['operator'];calls.append(op)
        return {'status':'failed' if op=='gelu' else 'completed_child','qualification_passed':False}
    monkeypatch.setattr(controller,'_checked',check);monkeypatch.setattr(controller,'dispatch',dispatch)
    result_ref=controller.dispatch_five(reader,campaign_ref=reference)
    result=json.loads(reader.verify_artifact(result_ref).read_text())
    assert calls==list(controller.baseline.OPERATORS) and len(result['results'])==5
    assert result['results'][1]['status']=='failed' and result['results'][-1]['status']=='completed_child'


@pytest.mark.parametrize('mutation',[None,'actual_exit','job_timeout','build_deadline','online_result'])
def test_qualification_joins_actual_exit_original_deadline_and_online_result(tmp_path,monkeypatch,mutation):
    # Component readers have their own full raw/oracle tests; this isolates the final join.
    local=LocalEvidence(tmp_path/'records');wall=time.time();mono=time.monotonic()
    expected_job=controller.job(tmp_path,operator='gelu',physical_device=0)
    plan=dict(operator='gelu',job_ref=local.register_json(expected_job),budget_seconds=3600)
    attempt=dict(plan_ref='CPU plan',created_at=wall-1)
    monkeypatch.setattr(controller,'_checked',lambda *a:(attempt,plan,tmp_path))
    rebuilt=dict(valid=True,scope='explicit_CPU_component_double')
    monkeypatch.setattr(controller,'replay_components',lambda *a,**kw:rebuilt)
    launch=dict(attempt_ref='CPU attempt',started_at=wall,started_monotonic=mono,
        deadline_monotonic=mono+3600,issued_monotonic=mono+1,child_timeout_seconds=3599)
    dump(local,tmp_path/'dispatcher-launch.json',launch)
    build=local.register_json(dict(started_at=wall+2,started_monotonic=mono+2,
        deadline_monotonic=mono+3601 if mutation=='build_deadline' else mono+3600))
    child=dict(attempt_ref='CPU attempt',status='components_completed',error=None,
        started_at=wall+1.5,finished_at=wall+8,started_monotonic=mono+1.5,finished_monotonic=mono+8,
        deadline_monotonic=mono+3600,qualification_passed=False,archive_performed=False,
        references={'build_receipt_ref':build,'pmu_ref':local.register_json({'finished_at':wall+6})},
        online_replay_started_at=wall+7,online_replay_ref=local.register_json(
            {'tampered':True} if mutation=='online_result' else rebuilt))
    child_ref=dump(local,tmp_path/'controller-result.json',child)
    log=tmp_path/'job.log';log.write_text('CPU final-join fixture; no hardware')
    pointer=dict(path=str(log),sha256=local.register_artifact(log))
    execution=dict(schema_version='1.0.0',kind='aprof_execution_report',status='passed',error=None,
        exit_code=1 if mutation=='actual_exit' else 0,duration_seconds=8,
        job=dict(expected_job,timeout_seconds=3600 if mutation=='job_timeout' else 3599,deadline_monotonic=mono+3600),
        started_at=datetime.fromtimestamp(wall+1.1,timezone.utc).isoformat(),
        finished_at=datetime.fromtimestamp(wall+9.1,timezone.utc).isoformat(),stdout=pointer,stderr=pointer)
    execution_ref=dump(local,tmp_path/'job/execution.json',execution)
    result=dict(attempt_ref='CPU attempt',status='completed_child',error=None,started_at=wall,
        finished_at=wall+10,finished_monotonic=mono+10,execution_ref=execution_ref,
        controller_result_ref=child_ref,qualification_passed=False,archive_performed=False)
    result_ref=dump(local,tmp_path/'dispatcher-result.json',result)
    if mutation:
        with pytest.raises(ValueError):
            controller.verify_baseline_qualification(local,attempt_ref='CPU attempt',result_ref=result_ref)
    else:
        checked=controller.verify_baseline_qualification(local,attempt_ref='CPU attempt',result_ref=result_ref)
        assert checked['valid'] and checked['qualification_passed']
        assert not checked['graph_route_granted'] and not checked['archive_performed']
