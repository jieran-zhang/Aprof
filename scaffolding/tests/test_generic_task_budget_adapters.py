import copy
import pytest
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.task_budget import prepare_task_launch,prepare_budget_plan
from aprof_runtime.stage_recovery import default_stage_plan
import task_budget as adapter
from test_generic_task_budget import job


POLICY=dict(kind='finish_started_unit_v1',reserve_seconds=600,task_unit_seconds=300,pmu_unit_seconds=540,terminal_seconds=60)


@pytest.mark.parametrize('kind',['teacher','baseline','validation'])
def test_three_parent_adapters_share_frozen_budget_and_policy(tmp_path,kind):
    local=LocalEvidence(tmp_path/'records')
    parent=dict(budget_seconds=5400,collection_stop_policy=POLICY)
    if kind=='validation':parent={'equal_budget_evaluation':parent}
    parent_ref=local.register_json(parent);source=local.register_json({'source':'actual'})
    scope=default_stage_plan(task_id='ordinary-task',source_ref=source,input_ref=source,toolchain_ref=source,protocol_ref=source)
    scope['stages'][0]['inputs']['parent_budget']=parent_ref
    scope_ref=local.register_json(scope)
    budget=adapter.freeze_generic_task_budget(local,kind=kind,parent_ref=parent_ref,task_id='ordinary-task',scope_ref=scope_ref)
    launch=prepare_task_launch(local,budget_ref=budget,job_ref=job(local,tmp_path,5400),
        started_at=1000,started_monotonic=100,issued_monotonic=101)
    binding={'kind':'task','launch_ref':local.register_json(launch)}
    assert adapter.replay_generic_task_budget(local,binding,kind=kind,parent_ref=parent_ref,task_id='ordinary-task')['collection_stop_policy']==POLICY
    for total,policy in ((7200,POLICY),(5400,dict(POLICY,reserve_seconds=700))):
        changed=local.register_json(prepare_budget_plan(task_id='ordinary-task',scope_ref=scope_ref,budget_seconds=total,collection_stop_policy=policy))
        alternate=prepare_task_launch(local,budget_ref=changed,job_ref=job(local,tmp_path,total),
            started_at=1000,started_monotonic=100,issued_monotonic=101)
        with pytest.raises(ValueError,match='changed its frozen comparison'):
            adapter.replay_generic_task_budget(local,{'kind':'task','launch_ref':local.register_json(alternate)},
                kind=kind,parent_ref=parent_ref,task_id='ordinary-task')
    with pytest.raises(ValueError,match='does not freeze'):
        adapter.freeze_generic_task_budget(local,kind=kind,parent_ref=local.register_json({'equal_budget_evaluation':{'budget_seconds':5400}} if kind=='validation' else {'budget_seconds':5400}),
            task_id='ordinary-task',scope_ref=scope_ref)


def test_existing_shared_helpers_call_generic_numeric_contract(monkeypatch):
    from aprof_runtime import task_budget
    actual=task_budget.validate_budget_values;calls=[]
    def checked(*args):calls.append(args);return actual(*args)
    monkeypatch.setattr(task_budget,'validate_budget_values',checked)
    assert adapter.budget_seconds({'wall_time_limit_seconds':5400})==5400
    assert adapter.collection_policy({'budget_seconds':5400,'collection_stop_policy':POLICY})==POLICY
    assert (5400,POLICY) in calls
    with pytest.raises(ValueError):adapter.collection_policy({'budget_seconds':5400,'collection_stop_policy':dict(POLICY,reserve_seconds=599)})
    monkeypatch.setattr(adapter,'_generic_runtime',lambda:None)
    assert adapter.budget_seconds({'wall_time_limit_seconds':3600})==3600
    assert adapter.collection_policy({'wall_time_limit_seconds':3600}) is None
