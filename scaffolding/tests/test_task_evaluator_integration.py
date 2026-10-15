"""CPU wiring boundaries only; no fixture grants baseline/hardware qualification."""
from copy import deepcopy
import datetime as dt
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import evaluate_skill_release as e
import task_validation_trial as trial
import task_baseline_context as context
from aprof_runtime.local_evidence import LocalEvidence


def ptr(path):
    return {'path': str(path), 'sha256': e.sha(path)}


def record(path, value):
    e.dump(path, value)
    return ptr(path)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    local = LocalEvidence(tmp_path/'records')
    source = tmp_path/'baseline'; source.mkdir(); (source/'kernel.asc').write_text('CPU original complete call')
    original = dict(operator='gelu', task_protocol=trial.bridge.timing.PROTOCOL,
        case_ids=list(range(1,21)), budget_seconds=7200, physical_device=0,
        roles={'baseline':{'files':trial.bridge.profile_capture.source_inventory(source)}})
    plan_ref = local.register_json(original)
    qualification_ref = local.register_json({'status':'passed', 'CPU_fixture_only':'not an actual qualification'})
    derivation_ref = local.register_json({'plan_ref':plan_ref})
    registry_ref = local.register_json({'contexts':{'CPU':{'baseline_qualification':ptr(local.verify_artifact(qualification_ref))}}})
    task = dict(baseline={'path':str(source), 'sha256':e.tree_sha(source)},
        evaluation_plan=ptr(local.verify_artifact(plan_ref)),
        baseline_qualification=ptr(local.verify_artifact(qualification_ref)),
        context_derivation_ref=derivation_ref, route_registry=ptr(local.verify_artifact(registry_ref)))
    task['baseline_local_index'] = ptr(local.write_index(tmp_path/'index.json'))
    comparison = record(tmp_path/'comparison.json', {'equal_budget_evaluation':{'budget_seconds':7200}})
    release = tmp_path/'release'; release.mkdir(); (release/'version').write_text('CPU')
    manifest = dict(measurement_protocol=trial.bridge.timing.PROTOCOL, plan=comparison,
        libraries={'candidate':{'path':str(release), 'sha256':e.library_sha(release)}},
        evaluator={'physical_device':0,'task_local_root':str(tmp_path)}, tasks={'gelu':task})
    monkeypatch.setattr(e, '_task_api', lambda _:trial)
    calls=[]
    def replay(reader, **kwargs):
        calls.append(kwargs)
        assert isinstance(reader, LocalEvidence)
        for ref in kwargs.values(): reader.verify_artifact(ref)
        return {'valid':True, 'contexts':{str(i):{'workload':{'case_id':i}} for i in range(1,21)}, 'routes':{}}
    real_replay=context.replay_baseline_contexts
    monkeypatch.setattr(context, 'replay_baseline_contexts', replay)
    return SimpleNamespace(**locals())


def test_task_freeze_delegates_full_qualification_and_all_contexts(inputs):
    f=inputs
    original, trusted=e._task_inputs(f.manifest,'gelu')
    assert original==f.original and len(trusted['contexts'])==20
    assert f.calls==[dict(derivation_ref=f.derivation_ref, qualification_ref=f.qualification_ref, registry_ref=f.registry_ref)]
    assert not list(f.tmp_path.rglob('*.sqlite'))


@pytest.mark.parametrize('defect',['budget','device','protocol','source','missing_index','different_derivation'])
def test_task_freeze_rejects_changed_scope_before_controller(inputs, defect):
    f=inputs; task=f.manifest['tasks']['gelu']
    if defect=='budget': f.manifest['plan']=record(f.tmp_path/'other-comparison.json',{'equal_budget_evaluation':{'budget_seconds':3600}})
    elif defect=='device': f.manifest['evaluator']['physical_device']=1
    elif defect=='protocol': f.manifest['measurement_protocol']='old_event_protocol'
    elif defect=='source':
        (f.source/'kernel.asc').write_text('changed');task['baseline']['sha256']=e.tree_sha(f.source)
    elif defect=='missing_index': task['baseline_local_index']['sha256']='sha256:'+'0'*64
    else:
        ref=f.local.register_json({'plan_ref':'sha256:'+'0'*64})
        task['context_derivation_ref']=ref
        task['baseline_local_index']=ptr(f.local.write_index(f.tmp_path/'other-index.json'))
    with pytest.raises(ValueError): e._task_inputs(f.manifest,'gelu')
    assert f.calls==[]


def test_passed_summary_cannot_replace_baseline_replay(inputs, monkeypatch):
    f=inputs;monkeypatch.setattr(context,'replay_baseline_contexts',f.real_replay)
    with pytest.raises((ValueError,KeyError)):
        e._task_inputs(f.manifest,'gelu')


@pytest.fixture
def exit_chain(tmp_path):
    output=tmp_path/'evaluation';directory=output/'runs/gelu-skill-only-4101';directory.mkdir(parents=True)
    row={'run_id':directory.name,'operator':'gelu','arm':'skill-only','seed':4101}
    comparison=record(output/'comparison.json',{'equal_budget_evaluation':{'budget_seconds':7200}})
    manifest={'measurement_protocol':trial.bridge.timing.PROTOCOL,'plan':comparison,
        'libraries':{'candidate':{'path':str(trial.bridge.RELEASE)}},
        'evaluator':{'physical_device':0,'argv':e._task_argv(),'environment':{},'task_local_root':str(tmp_path)}}
    freeze=record(output/'freeze.json',manifest)
    matrix=record(output/'matrix.json',{'freeze_sha256':freeze['sha256'],'runs':[row]})
    job=record(directory/'job.json',e._trial_job(output,row,manifest))
    plan=record(directory/'dispatcher-plan.json',dict(schema_version=1,kind='skill_release_trial_plan',
        run_id=row['run_id'],row=row,freeze_ref=freeze,matrix_ref=matrix,job_ref=job,budget_seconds=7200))
    attempt=record(directory/'attempt.json',dict(plan_ref=plan,budget_seconds=7200,created_at=1000))
    launch=dict(attempt_ref=attempt,started_at=1000,started_monotonic=100,deadline_monotonic=7300,
                issued_monotonic=101,child_timeout_seconds=7199)
    launch_ref=record(directory/'dispatcher-launch.json',launch)
    substitutions=dict(evaluation_output=str(output),run_id=row['run_id'],workspace=str(directory/'controller-workspace'),
        result=str(directory/'evaluation.json'),task_launch=launch_ref['path'],task_launch_ref=launch_ref['sha256'])
    env=dict(APROF_TASK_LAUNCH_PATH=launch_ref['path'],APROF_TASK_LAUNCH_SHA256=launch_ref['sha256'],
        APROF_TASK_DEADLINE_MONOTONIC='7300',APROF_SKILL_LIB=str(trial.bridge.RELEASE),
        PYTHONPATH=str(trial.bridge.RELEASE/'runtime/src'),PYTHONDONTWRITEBYTECODE='1',APROF_EVALUATION_SEED='4101',
        ASCEND_RT_VISIBLE_DEVICES='0',APROF_PHYSICAL_DEVICE='0',APROF_LOGICAL_DEVICE='0')
    logs={}
    for name in ('stdout','stderr'):
        path=directory/(name+'.txt');path.write_text('CPU execution schema fixture only');logs[name]=ptr(path)
    timestamp=lambda t:dt.datetime.fromtimestamp(t,dt.timezone.utc).isoformat()
    execution=dict(schema_version='1.0.0',kind='aprof_execution_report',status='passed',exit_code=0,error=None,
        started_at=timestamp(1010),finished_at=timestamp(1020),duration_seconds=10,**logs,
        job=dict(job_id=row['run_id'],argv=[x.format_map(substitutions) for x in e._task_argv()],cwd=str(e.ROOT),
            output_dir=str(directory/'controller'),timeout_seconds=7180,deadline_monotonic=7300,environment=env))
    receipt=dict(task_root=str(tmp_path/'local-task'),measurement_protocol=trial.bridge.timing.PROTOCOL,row=row,status='completed',task_launch_ref=launch_ref,
        deadline_monotonic=7300,started_at=1011,finished_at=1019,started_monotonic=111,finished_monotonic=119)
    return SimpleNamespace(**locals())


def test_task_actual_exit_join_keeps_original_7200_budget(exit_chain):
    f=exit_chain;e._verify_task_controller(f.manifest,f.row,f.directory,f.receipt,f.execution,f.launch_ref)


@pytest.mark.parametrize('defect',['nonzero_exit','fresh_deadline','foreign_argv','late_terminal','different_row','changed_environment'])
def test_task_completed_cannot_replace_actual_exit_or_parent(exit_chain, defect):
    f=exit_chain
    if defect=='nonzero_exit':f.execution['exit_code']=2
    elif defect=='fresh_deadline':f.execution['job']['deadline_monotonic']+=20
    elif defect=='foreign_argv':f.execution['job']['argv']=['untrusted-controller']
    elif defect=='late_terminal':f.receipt['finished_monotonic']=7301
    elif defect=='different_row':f.receipt['row']={**f.row,'arm':'baseline'}
    else:f.execution['job']['environment']['APROF_SKILL_LIB']='other-release'
    with pytest.raises(ValueError,match='actual exit'):
        e._verify_task_controller(f.manifest,f.row,f.directory,f.receipt,f.execution,f.launch_ref)


def test_task_score_does_not_trust_completed_or_self_reported_gain(tmp_path):
    receipt=dict(kind='task_validation_evaluation',status='completed',error=None,row={},
        measurement_protocol=trial.bridge.timing.PROTOCOL,archive_performed=False,
        admission_authority=False,eligible_for_publication=False,local_index={'path':str(tmp_path/'missing-index'),'sha256':'sha256:'+'0'*64},
        formal_outcome='production_safe_gain',deployed_speedup=100)
    with pytest.raises(FileNotFoundError):
        e.replay_evaluation(receipt,trial.bridge.RELEASE,{},tmp_path)


def test_task_stage_uses_qualified_description_and_never_copies_profiles(tmp_path):
    source=tmp_path/'original';source.mkdir();(source/'kernel.asc').write_text('original')
    library=tmp_path/'library';library.mkdir();(library/'skill.txt').write_text('frozen skill')
    profile={'case_id':1,'kernels':['gelu_kernel'],'metrics':{'aicore':{'unit':'us'}}}
    cases=[dict(case_id=i,workload={'dtype':'float32'},launches_per_call={'baseline':1,'candidate':1},
        role_kernel_names={'baseline':['aprof_baseline_gelu_kernel'],'candidate':['aprof_candidate_gelu_kernel']}) for i in range(1,21)]
    original=record(tmp_path/'plan.json',dict(profile=profile,case_ids=list(range(1,21)),cases=cases))
    context_ref=record(tmp_path/'qualified-context.json',{'workload':{'case_id':1},'evidence':{'predicate_states':{'x':'unknown'}}})
    registry=record(tmp_path/'registry.json',{'contexts':{'gelu-case-1':{'context':context_ref}}})
    task=dict(baseline={'path':str(source),'sha256':e.tree_sha(source)},evaluation_plan=original,
        route_registry=registry,context_derivation_ref='sha256:'+'1'*64,baseline_qualification={'CPU':'not executed'})
    manifest=dict(measurement_protocol=trial.bridge.timing.PROTOCOL,tasks={'gelu':task},
        libraries={key:{'path':str(library),'sha256':e.library_sha(library)} for key in ('baseline','candidate')})
    row=dict(operator='gelu',arm='skill-only',seed=4101,run_id='cpu')
    target=tmp_path/'work';assert e.stage(manifest,row,target) is None
    description=e.load(target/'context.json')
    assert description['kind']=='qualified_task_description' and description['profile']==profile
    assert description['original_workloads']==cases and description['graph_context_ids']==['gelu-case-1']
    assert 'parallel_plan and dispatch_plan' in (target/'prompt.txt').read_text()
    assert not (target/'profiles').exists()
    task['profiles']={'path':str(source),'sha256':e.tree_sha(source)}
    with pytest.raises(ValueError,match='copy baseline profile'):
        e.stage(manifest,row,tmp_path/'forbidden')
    assert not (tmp_path/'forbidden').exists()


def test_task_child_command_is_fixed_and_keeps_deadline_after_staging(tmp_path,monkeypatch):
    directory=tmp_path/'evaluation/runs/cpu';work=directory/'worker/root/work'
    for role in ('baseline','candidate'):
        (work/role).mkdir(parents=True);(work/role/'kernel.asc').write_text(role)
    (work/'candidate_plan.json').write_text('{}')
    clock=[100.0];jobs=[]
    monkeypatch.setattr(e.time,'monotonic',lambda:clock[0])
    real_copy=e.shutil.copytree
    def copy(*args,**kwargs):
        result=real_copy(*args,**kwargs)
        if Path(args[0])==work: clock[0]+=7
        return result
    monkeypatch.setattr(e.shutil,'copytree',copy)
    monkeypatch.setattr(e,'run_job',lambda job:jobs.append(job) or {'status':'failed','exit_code':2})
    manifest=dict(measurement_protocol=trial.bridge.timing.PROTOCOL,evaluator={'argv':e._task_argv(),'physical_device':2},
        libraries={'candidate':{'path':str(trial.bridge.RELEASE)}})
    result={'worker':{'status':'completed'},'task_launch_ref':{'path':str(directory/'dispatcher-launch.json'),'sha256':'sha256:'+'a'*64}}
    e.evaluate_candidate(manifest,{'budget_seconds':7200},dict(run_id='cpu',operator='gelu',seed=4101),directory,work,100,result)
    assert len(jobs)==1 and jobs[0]['deadline_monotonic']==7300
    assert jobs[0]['timeout_seconds']==7200-7
    assert jobs[0]['argv'][2]=='_evaluate_task' and str(directory/'controller-workspace') in jobs[0]['argv']
    assert jobs[0]['environment']['APROF_TASK_DEADLINE_MONOTONIC']=='7300'
    assert 'physical_device' not in jobs[0]


@pytest.mark.parametrize('defect',[None,'missing_role','missing_case'])
def test_task_projection_uses_full_roster_and_runtime_verdict(tmp_path,monkeypatch,defect):
    # Only the already-tested component replay is doubled here. A real NOOP
    # runtime episode ensures this projection cannot invent production gain.
    from aprof_runtime.jsonio import to_primitive
    from test_store_integrity import _noop_episode
    local=LocalEvidence(tmp_path/'records');ref=local.register_json
    materialized=tmp_path/'work';materialized.mkdir()
    hashes={}
    for role in ('baseline','candidate'):
        root=materialized/role;root.mkdir();(root/'kernel.asc').write_text('same CPU source')
        hashes[role]=ref({'schema_version':'1.0.0','files':{'kernel.asc':local.register_artifact(root/'kernel.asc')}})
    row=dict(run_id='cpu',operator='gelu',arm='skill-only',seed=4101)
    launch=ref({'CPU':'supervisor replay is a separate tested boundary'})
    plan=ref(dict(run_id='cpu',operator='gelu',source_hashes=hashes,launch_ref=launch,deadline_monotonic=7200))
    draft=ref({'CPU':'draft leaf boundary'});binding=ref(dict(candidate_plan_ref=plan,draft_ref=draft))
    rows=[dict(case_id=i,role=role,correct=True) for i in range(1,21) for role in ('baseline','candidate')]
    per_case=[dict(case_id=i,baseline_median_ns=2000,candidate_median_ns=1000) for i in range(1,21)]
    if defect=='missing_role': rows.pop()
    if defect=='missing_case': per_case.pop()
    accuracy=ref(dict(case_ids=list(range(1,21)),rows=rows));measurement=ref(dict(per_case=per_case))
    episode=_noop_episode(hashes['baseline'])
    finalization=ref({'episodes':[to_primitive(episode)]})
    result=ref({'stages':[ref({'artifacts':v}) for v in ({'accuracy_report':accuracy},{'measurement_report':measurement},{},{'finalization':finalization})]})
    replay={'valid':True,'CPU_fixture_only':'component boundary, not actual qualification'}
    monkeypatch.setattr(trial,'replay_trial',lambda *a,**kw:replay)
    pointer=lambda digest:ptr(local.verify_artifact(digest))
    receipt=dict(kind='task_validation_evaluation',status='completed',error=None,row=row,
        measurement_protocol=trial.bridge.timing.PROTOCOL,archive_performed=False,admission_authority=False,
        eligible_for_publication=False,task_root=str(tmp_path),deadline_monotonic=7200,
        candidate_tree_sha256=e.tree_sha(materialized/'candidate'),candidate_plan_ref=pointer(plan),
        draft_ref=pointer(draft),trial_ref=pointer(binding),result_ref=pointer(result),task_launch_ref=pointer(launch),
        online_replay_ref=pointer(ref(replay)),formal_outcome='production_safe_gain',deployed_speedup=100)
    receipt['local_index']=ptr(local.write_index(tmp_path/'index.json'))
    if defect:
        with pytest.raises(ValueError,match='omitted original cases or a correctness role'):
            e.replay_evaluation(receipt,trial.bridge.RELEASE,row,materialized)
    else:
        outcome,speedup=e.replay_evaluation(receipt,trial.bridge.RELEASE,row,materialized)
        assert outcome['score']['geomean_speedup']==pytest.approx(2)
        assert outcome['result']['verdict']==episode.outcome.verdict.value!='production_safe_gain'
        assert speedup==episode.outcome.speedup and len(outcome['cases'])==20
