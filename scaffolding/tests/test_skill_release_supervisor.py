"""Real CPU subprocess supervision; fake workload never claims Task/PMU admission."""
import json
from pathlib import Path
import sys
import time

import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'collection/scripts'
sys.path.insert(0,str(SCRIPTS))
import evaluate_skill_release as evaluation

CHILD='''
import argparse,sys,time
from pathlib import Path
sys.path.insert(0,SCRIPTS)
import evaluate_skill_release as e
e.__file__=__file__
p=argparse.ArgumentParser();p.add_argument('command');p.add_argument('output',type=Path);p.add_argument('run_id');p.add_argument('--launch',type=Path);p.add_argument('--launch-sha256');a=p.parse_args()
manifest=e.load(a.output/'freeze.json');mode=manifest['CPU_mode']
e.validate_freeze=lambda _:manifest['CPU_plan']
def stage(*args):
    args[-1].mkdir()
    if mode=='stage_hang':time.sleep(120)
e.stage=stage
async def worker(work,output,*args,**kwargs):
    receipt=dict(status='completed',usage={'totalTokens':120000},CPU_fixture=True)
    e.dump(output/'worker.json',receipt)
    e.dump(output/'root/work/candidate_plan.json',{'transformation_id':'transformation.CPU'})
    return receipt
e.run_worker=worker
def review(manifest,row,directory,started,result):
    receipt=dict(status='completed',usage={'totalTokens':25000},CPU_fixture=True)
    e.dump(directory/'reviewer/worker.json',receipt)
    result.update(reviewer_started=True,reviewer=receipt)
e.review_candidate=review
def candidate(manifest,plan,row,directory,workspace,started,result):
    if mode=='replay_hang':time.sleep(120)
    result.update(status='passed',deployed_speedup=1.2,CPU_fixture_not_admission=True)
e.evaluate_candidate=candidate
answer=e.execute(a.output,a.run_id,launch_path=a.launch,launch_sha256=a.launch_sha256)
print(answer['status'])
raise SystemExit(0 if answer['status']=='passed' else 2)
'''


@pytest.fixture
def prepared(tmp_path,monkeypatch):
    def make(mode='pass',remaining=None):
        out=tmp_path/('run-'+str(len(list(tmp_path.iterdir()))));out.mkdir()
        script=out/'cpu_execute.py';script.write_text('SCRIPTS='+repr(str(SCRIPTS))+'\n'+CHILD)
        monkeypatch.setattr(evaluation,'__file__',str(script))
        release=evaluation.ROOT/'skill-libs/graph-base/1.0.0'
        plan=dict(seeds=[4101],operators=['gelu'],wall_time_limit_seconds=3600)
        evaluation.dump(out/'comparison-plan.json',{'equal_budget_evaluation':plan})
        manifest=dict(CPU_mode=mode,CPU_plan=plan,model={'name':'CPU fixture','reasoning_effort':'none'},
            plan=evaluation._pointer(out/'comparison-plan.json'),
            target_speedup=1.03,worker_qualification={},tasks={'gelu':{'route_registry':{}}},
            libraries={'candidate':{'path':str(release)}},evaluator={'physical_device':0})
        evaluation.dump(out/'freeze.json',manifest)
        roster=evaluation.matrix(plan)
        evaluation.dump(out/'matrix.json',{'freeze_sha256':evaluation.sha(out/'freeze.json'),'runs':roster})
        if remaining is not None:
            # Advance only the parent's first timestamp. Production still binds
            # exactly 3600 seconds; the real child gets the last two seconds.
            mono,wall=time.monotonic,time.time
            first_mono=[True];first_wall=[True]
            def clock(fn,first):
                value=fn()
                if first.pop() if first else False:return value-(3600-remaining)
                return value
            monkeypatch.setattr(evaluation.time,'monotonic',lambda:clock(mono,first_mono))
            monkeypatch.setattr(evaluation.time,'time',lambda:clock(wall,first_wall))
        return out,roster[0]
    return make


def test_whole_task_real_child_and_immutable_launch(prepared):
    out,row=prepared();result=evaluation.dispatch(out,row['run_id'])
    assert result['status']=='passed' and result['total_model_tokens']==145000
    directory=out/'runs'/row['run_id'];child=evaluation.load(directory/'child-result.json')
    assert child['task_launch_ref']==result['task_launch_ref']
    assert child['started_monotonic']==result['started_monotonic']
    assert child['duration_seconds']<=result['duration_seconds']
    assert evaluation.verify_dispatch(out,row,result)['execution']==result['execution_ref']
    assert 'physical_device' not in evaluation.load(directory/'job.json')
    before=evaluation.sha(directory/'supervisor/execution.json')
    with pytest.raises(FileExistsError):evaluation.dispatch(out,row['run_id'])
    assert evaluation.sha(directory/'supervisor/execution.json')==before


@pytest.mark.parametrize('mode,expected_tokens',[('stage_hang',None),('replay_hang',145000)])
def test_real_whole_task_timeout_preserves_authoritative_cost(prepared,mode,expected_tokens):
    out,row=prepared(mode,remaining=2)
    result=evaluation.dispatch(out,row['run_id'])
    directory=out/'runs'/row['run_id'];execution=evaluation.load(directory/'supervisor/execution.json')
    assert execution['status']=='timeout' and execution['exit_code']!=0
    assert result['status']=='over_wall_time_budget' and result['deployed_speedup']==1
    assert result['time_to_target_seconds'] is result['tokens_to_target'] is None
    assert result['total_model_tokens']==expected_tokens
    assert not (directory/'child-result.json').exists()
    if expected_tokens is None:assert result['model_usage_status'].startswith('unavailable')
    evaluation.verify_dispatch(out,row,result)


@pytest.mark.parametrize('defect',['fresh_outer_deadline','fresh_child_deadline','fresh_job_budget','fresh_job_deadline','failed_exit','late_gate'])
def test_outer_receipt_and_deadline_tampering_reject(prepared,defect):
    out,row=prepared();result=evaluation.dispatch(out,row['run_id']);directory=out/'runs'/row['run_id']
    if defect=='fresh_outer_deadline':
        path=directory/'dispatcher-launch.json';value=evaluation.load(path);value['deadline_monotonic']+=3600
        evaluation.dump(path,value);result['task_launch_ref']=evaluation._pointer(path)
    elif defect=='fresh_child_deadline':
        path=directory/'child-result.json';value=evaluation.load(path);value['started_monotonic']+=1;value['deadline_monotonic']+=1
        evaluation.dump(path,value);result['child_result_ref']=evaluation._pointer(path)
    elif defect in ('fresh_job_budget','fresh_job_deadline','failed_exit'):
        path=directory/'supervisor/execution.json';value=evaluation.load(path)
        if defect=='fresh_job_budget':value['job']['timeout_seconds']=3600
        elif defect=='fresh_job_deadline':value['job']['deadline_monotonic']+=3600
        else:value.update(status='failed',exit_code=2)
        evaluation.dump(path,value);result['execution_ref']=evaluation._pointer(path)
    else:
        result.update(finished_monotonic=result['deadline_monotonic']+.1,duration_seconds=3600.1,
                      finished_at=result['started_at']+3600.1)
    evaluation.dump(directory/'dispatcher-result.json',result)
    with pytest.raises(ValueError):evaluation.verify_dispatch(out,row,result)


def test_publication_requires_outer_exit_even_for_a_cost_complete_failure(tmp_path,monkeypatch):
    from eval_tool_broker import CONFIG
    release=tmp_path/'release';release.mkdir()
    plan={'seeds':[4101,4102,4103],'operators':list(evaluation.VALIDATION_OPERATORS)}
    manifest={'libraries':{'candidate':{'path':str(release),'sha256':evaluation.library_sha(release)}},
              'model':{'name':'CPU fixture','reasoning_effort':'none'},'worker_qualification':{'CPU_fixture':True}}
    evaluation.dump(tmp_path/'freeze.json',manifest);rows=evaluation.matrix(plan)
    evaluation.dump(tmp_path/'matrix.json',{'freeze_sha256':evaluation.sha(tmp_path/'freeze.json'),'runs':rows})
    monkeypatch.setattr(evaluation,'validate_freeze',lambda _:plan)
    row=rows[0];directory=tmp_path/'runs'/row['run_id'];worker_dir=directory/'worker';worker_dir.mkdir(parents=True)
    (worker_dir/'broker.jsonl').write_text('')
    usage={'totalTokens':123456}
    (worker_dir/'events.jsonl').write_text(json.dumps({'method':'thread/tokenUsage/updated','params':{'tokenUsage':{'total':usage}}})+'\n')
    worker=dict(status='failed',usage=usage,model='CPU fixture',reasoning_effort='none',role='proposer',
                qualification_ref=manifest['worker_qualification'],config=CONFIG,worker_builds=0,
                budget_policy=evaluation.BUDGET_POLICY,broker_ref=evaluation._pointer(worker_dir/'broker.jsonl'))
    evaluation.dump(worker_dir/'worker.json',worker)
    evaluation.dump(directory/'result.json',dict(**row,status='worker_error',budget_policy=evaluation.BUDGET_POLICY,
        worker=worker,reviewer=None,reviewer_started=False,total_model_tokens=123456,duration_seconds=1))
    with pytest.raises(FileNotFoundError,match='dispatcher-launch'):
        evaluation.verify_publication(tmp_path,release=release)


def test_slow_prelaunch_does_not_grant_a_fresh_child_budget(prepared,monkeypatch):
    out,row=prepared(remaining=1)
    original=evaluation._load_launch
    def delayed(*args):
        value=original(*args)
        time.sleep(1.1)
        return value
    monkeypatch.setattr(evaluation,'_load_launch',delayed)
    result=evaluation.dispatch(out,row['run_id']);directory=out/'runs'/row['run_id']
    receipt=evaluation.load(directory/'supervisor/execution.json')
    assert receipt['status']=='timeout' and receipt['process_started'] is False
    assert receipt['exit_code']==-1 and not (directory/'workspace').exists()
    assert result['status']=='over_wall_time_budget' and result['total_model_tokens'] is None
    monkeypatch.setattr(evaluation,'_load_launch',original)
    evaluation.verify_dispatch(out,row,result)


@pytest.mark.parametrize('receipt_exists',[False,True])
def test_setup_failure_retains_one_failed_attempt_without_fabricated_exit(prepared,monkeypatch,receipt_exists):
    out,row=prepared();original=evaluation.run_job
    def broken(job):
        if receipt_exists:
            import run_aprof_job
            def fail_spawn(*args,**kwargs):raise OSError('CPU fixture spawn failed')
            with monkeypatch.context() as context:
                context.setattr(run_aprof_job.subprocess,'Popen',fail_spawn)
                return original(job)
        raise OSError('CPU fixture setup failed before execution')
    monkeypatch.setattr(evaluation,'run_job',broken)
    result=evaluation.dispatch(out,row['run_id']);directory=out/'runs'/row['run_id']
    assert result['status']=='dispatch_failed' and result['deployed_speedup']==1
    assert result['total_model_tokens'] is None and result['child_result_ref'] is None
    assert evaluation.load(directory/'result.json')==result
    assert evaluation.load(directory/'dispatcher-error.json')['type']=='OSError'
    if receipt_exists:
        receipt=evaluation.load(directory/'supervisor/execution.json')
        assert receipt['status']=='failed' and receipt['process_started'] is False and receipt['exit_code']==-1
        evaluation.verify_dispatch(out,row,result)
    else:
        assert result['execution_ref'] is None and not (directory/'supervisor/execution.json').exists()
        with pytest.raises(FileNotFoundError):evaluation.verify_dispatch(out,row,result)
    with pytest.raises(FileExistsError):evaluation.dispatch(out,row['run_id'])
