import copy
import json
import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.stage_recovery import default_stage_plan, plan_stage_recovery, validate_stage_plan
from aprof_runtime.task_budget import prepare_budget_plan
from test_generic_task_budget import job, segment


NAMES=('prepare','review','build','correctness_boundary','exploratory_timing','formal_timing_control','pmu','online_admission')


def fixture(tmp_path, count=6, *, failed=None, policy='complete_only'):
    local=LocalEvidence(tmp_path/'records')
    inputs={name:local.register_json({'input':name}) for name in ('sources','input','protocol','toolchain')}
    stages=[]
    for i,name in enumerate(NAMES):
        bound=dict(inputs)
        if i>2:bound['binary']={'stage_id':'build','output':'binary'}
        stages.append(dict(id=name,dependencies=list(NAMES[:i]),inputs=bound,
            recovery_policy=policy if name==failed else 'complete_only',max_attempts=2 if name==failed else 1))
    plan=dict(schema_version=1,kind='task_stage_plan_v1',task_id='ordinary-task',stages=stages)
    plan_ref=local.register_json(plan)
    budget=local.register_json(prepare_budget_plan(task_id='ordinary-task',scope_ref=plan_ref,budget_seconds=100))
    terminal,launch=segment(local,budget,job(local,tmp_path,100),elapsed=40,status='failed',log_value={'stage_attempts':list(NAMES[:count])})
    refs=[];by_name={};binary=local.register_json({'cpu_binary':'complete build artifact'})
    for i,name in enumerate(NAMES[:count]):
        raw=local.register_json({'stage':name,'argument':i+1,'result':(i+1)**2})
        resolved=dict(inputs)
        if i>2:resolved['binary']=binary
        outputs={'binary':binary} if name=='build' else {}
        row=dict(schema_version=1,kind='task_stage_receipt_v1',plan_ref=plan_ref,stage_id=name,launch_ref=launch,
            status='failed' if name==failed else 'passed',failure_class='infrastructure' if name==failed else None,
            input_refs=resolved,dependency_refs=dict(by_name),artifact_refs=[raw,*outputs.values()],output_refs=outputs,
            started_at=1001+i*2,finished_at=1002+i*2)
        ref=local.register_json(row);refs.append(ref);by_name[name]=ref
    return local,plan,plan_ref,budget,terminal,refs


def trusted(local,stage,row,*,terminal_refs):
    if row is None:
        for terminal_ref in terminal_refs:
            terminal=json.loads(local.verify_artifact(terminal_ref).read_text())
            execution=json.loads(local.verify_artifact(terminal['execution_ref']).read_text())
            journal=json.loads(local.verify_artifact(execution['stdout']['sha256']).read_text())
            if stage['id'] in journal['stage_attempts']:
                return {'valid':False,'status':'unknown','failure_class':None}
        return {'valid':True,'status':'not_started','failure_class':None}
    raw=json.loads(local.verify_artifact(row['artifact_refs'][0]).read_text())
    return {'valid':raw['stage']==stage['id'] and raw['result']==raw['argument']**2,
            'status':row['status'],'failure_class':row['failure_class']}


def replay(values, **kwargs):
    local,plan,plan_ref,budget,terminal,refs=values
    return plan_stage_recovery(local,plan_ref,budget_ref=budget,terminal_refs=[terminal],receipt_refs=refs,
        current_inputs=kwargs.pop('current_inputs',{s['id']:s['inputs'] for s in plan['stages']}),
        verify_stage=kwargs.pop('verify_stage',trusted),**kwargs)


def test_eight_stages_reuse_only_complete_prefix(tmp_path):
    values=fixture(tmp_path)
    result=replay(values)
    assert list(result['reused_stages'])==list(NAMES[:6])
    assert result['remaining_stages']==['pmu','online_admission'] and result['ready_stages']==['pmu']
    assert result['remaining_budget_seconds']==60 and result['admission_authority'] is False
    assert result['execution_performed'] is result['archive_performed'] is False


def test_source_invalidation_blocks_whole_downstream_not_new_build(tmp_path):
    values=fixture(tmp_path);local,plan,*_=values
    current={s['id']:copy.deepcopy(s['inputs']) for s in plan['stages']}
    current['prepare']['sources']=local.register_json({'changed_source':True})
    result=replay(values,current_inputs=current)
    assert result['invalidated_stages']==list(NAMES)
    assert not result['reused_stages'] and not result['ready_stages']
    assert set(result['blocked_stages'])==set(NAMES)


def test_passed_json_without_trusted_replay_is_not_reusable(tmp_path):
    result=replay(fixture(tmp_path),verify_stage=None)
    assert not result['reused_stages'] and not result['ready_stages']
    assert 'trusted stage replay' in result['blocked_stages']['prepare']


@pytest.mark.parametrize('failure_class',['control','semantic','infrastructure'])
def test_partial_formal_is_never_resampled(tmp_path,failure_class):
    values=fixture(tmp_path,failed='formal_timing_control')
    local,_,_,_,_,refs=values
    row=json.loads(local.verify_artifact(refs[-1]).read_text());row['failure_class']=failure_class
    refs[-1]=local.register_json(row)
    result=replay(values)
    assert not result['ready_stages']
    assert 'formal_timing_control' in result['blocked_stages'] and 'pmu' in result['blocked_stages']


def test_only_frozen_repeat_safe_infrastructure_stage_can_retry(tmp_path):
    values=fixture(tmp_path,count=8,failed='online_admission',policy='repeat_safe')
    result=replay(values)
    assert result['ready_stages']==['online_admission']
    local,_,_,_,_,refs=values
    row=json.loads(local.verify_artifact(refs[-1]).read_text());row.update(status='passed',failure_class=None,started_at=1020,finished_at=1021)
    refs.append(local.register_json(row))
    assert 'online_admission' in replay(values)['reused_stages']
    row.update(started_at=1022,finished_at=1023);refs.append(local.register_json(row))
    with pytest.raises(ContractError,match='repeated after success'):
        replay(values)


@pytest.mark.parametrize('mutation',['source','dependency','output','window','raw'])
def test_receipt_binding_mutations_rejected(tmp_path,mutation):
    values=fixture(tmp_path);local,_,_,_,_,refs=values
    row=json.loads(local.verify_artifact(refs[-1]).read_text())
    if mutation=='source':row['input_refs']['sources']=local.register_json({'wrong':1})
    if mutation=='dependency':row['dependency_refs']['build']=refs[0]
    if mutation=='output':row['input_refs']['binary']=local.register_json({'other binary':1})
    if mutation=='window':row['finished_at']=2000
    if mutation=='raw':row['artifact_refs'][0]=local.register_json({'stage':row['stage_id'],'argument':2,'result':8})
    refs[-1]=local.register_json(row)
    with pytest.raises(ContractError):replay(values)


def test_seven_stage_template_has_real_refs_and_late_binary(tmp_path):
    local=LocalEvidence(tmp_path/'records');ref=local.register_json({'bytes':'frozen'})
    plan=default_stage_plan(task_id='ordinary',source_ref=ref,input_ref=ref,toolchain_ref=ref,protocol_ref=ref)
    assert len(plan['stages'])==7
    assert all({'sources','input','toolchain','protocol'} <= set(s['inputs']) for s in plan['stages'])
    assert plan['stages'][2]['inputs']['binary']=={'stage_id':'build','output':'binary'}
    assert plan['stages'][-1]['recovery_policy']=='repeat_safe'
    plan['stages'][0]['dependencies']=['build']
    with pytest.raises(ContractError):validate_stage_plan(plan)


def test_missing_receipt_is_not_a_free_second_attempt(tmp_path):
    values=fixture(tmp_path,count=7)
    values[-1].pop()  # PMU actually began, but its receipt is absent.
    result=replay(values)
    assert 'pmu' in result['remaining_stages'] and 'pmu' in result['blocked_stages']
    assert not result['ready_stages']
