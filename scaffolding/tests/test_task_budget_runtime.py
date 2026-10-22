"""Original parent budget and bounded collection CPU fixtures; no NPU calls."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.task_window_measurement_admission import replay_task_budget, storage_budget, collection_unit_deadline
from aprof_runtime import task_measurement_admission as old_admission, measurement_entry, full_call_pmu
import device_task_window_timing as collector
from persistent_oracle import PersistentOracle

REPO = Path(__file__).resolve().parents[2]
POLICY = dict(kind='finish_started_unit_v1', reserve_seconds=300, task_unit_seconds=200,
              pmu_unit_seconds=100, terminal_seconds=50)


def parent(local, kind='validation', *, total=7200, policy=POLICY, mutate=None):
    put = local.register_json
    expected = dict(run_id='run', operator='gqa', candidate_id='candidate', session_id='session')
    pointer = lambda ref: dict(path=str(local.verify_artifact(ref)), sha256=ref)
    job = dict(timeout_seconds=total)
    source = dict(**expected, budget_seconds=total, created_at=-1, source_hashes={})
    if policy is not None:
        source['collection_stop_policy'] = deepcopy(policy)
    if kind == 'teacher':
        campaign = dict(kind='teacher_task_rule_campaign', budget_seconds=total,
                        attempts=[{key:source[key] for key in ('run_id','candidate_id','operator','source_hashes')}])
        if policy is not None: campaign['collection_stop_policy'] = deepcopy(policy)
        if mutate: mutate('campaign', campaign)
        source['campaign_ref'] = put(campaign)
        source['job_ref'] = put(job)
        if mutate: mutate('origin', source)
        anchor_ref = put(source)
        launch = dict(schema_version=2, anchor_ref=anchor_ref, job_ref=source['job_ref'], started_at=0,
                      started_monotonic=100, monotonic_deadline=100+total, issued_monotonic=100.1,
                      child_timeout_seconds=100+total-100.1)
    else:
        source.update(kind='skill_release_trial_plan' if kind == 'validation' else 'task_baseline_qualification_plan',
                      job_ref=pointer(put(job)) if kind == 'validation' else put(job))
        if kind == 'validation':
            budget_plan = dict(budget_seconds=total)
            if policy is not None: budget_plan['collection_stop_policy'] = deepcopy(policy)
            if mutate: mutate('budget_plan', budget_plan)
            freeze = dict(plan=pointer(put(dict(equal_budget_evaluation=budget_plan))))
            source.update(row=dict(run_id='run', operator='gqa'), freeze_ref=pointer(put(freeze)),
                          matrix_ref=pointer(put(dict(runs=[dict(run_id='run', operator='gqa')]))))
        if mutate: mutate('origin', source)
        source_ref = put(source)
        attempt = dict(plan_ref=pointer(source_ref) if kind == 'validation' else source_ref,
                       budget_seconds=total, created_at=-1)
        if kind == 'baseline': attempt.update(kind='baseline_task_attempt', operator='gqa')
        if mutate: mutate('attempt', attempt)
        attempt_ref = put(attempt)
        launch = dict(attempt_ref=pointer(attempt_ref) if kind == 'validation' else attempt_ref, started_at=0,
                      started_monotonic=100, deadline_monotonic=100+total, issued_monotonic=100.1,
                      child_timeout_seconds=100+total-100.1)
    if mutate: mutate('launch', launch)
    binding = dict(kind=kind, launch_ref=put(launch))
    return SimpleNamespace(**locals())


@pytest.fixture
def local(tmp_path):
    return LocalEvidence(tmp_path/'records')


@pytest.mark.parametrize('kind', ['teacher', 'baseline', 'validation'])
@pytest.mark.parametrize('total', [3600, 7200])
def test_parent_budget_is_read_from_all_real_launch_shapes(local, kind, total):
    p = parent(local, kind, total=total)
    result = replay_task_budget(local, p.binding, expected=p.expected)
    assert result['budget_seconds'] == total
    assert result['deadline_monotonic'] == 100 + total
    assert result['collection_stop_policy'] == POLICY
    assert p.binding['launch_ref'] in result['references']
    for ref, path in result['references'].items(): assert local.verify_artifact(ref) == Path(path)


@pytest.mark.parametrize('site,key,value', [
    ('attempt','budget_seconds',7300), ('origin','budget_seconds',7300),
    ('budget_plan','budget_seconds',7300), ('budget_plan','wall_time_limit_seconds',3600),
    ('budget_plan','budget_seconds',True), ('budget_plan','budget_seconds',0),
    ('launch','deadline_monotonic',7400), ('launch','child_timeout_seconds',7300),
    ('origin','operator','exp'), ('origin','run_id','other'),
])
def test_changed_parent_alias_identity_or_renewal_rejected(local, site, key, value):
    p = parent(local, mutate=lambda label,obj: obj.update({key:value}) if label==site else None)
    with pytest.raises(ContractError): replay_task_budget(local,p.binding,expected=p.expected)


@pytest.mark.parametrize('mutation', [lambda p:p.update(reserve_seconds=7200),
    lambda p:p.update(task_unit_seconds=300),lambda p:p.update(terminal_seconds=-1),
    lambda p:p.update(pmu_unit_seconds=True),lambda p:p.update(kind='unlimited')])
def test_invalid_drain_policy_rejected(local, mutation):
    policy=deepcopy(POLICY);mutation(policy);p=parent(local,policy=policy)
    with pytest.raises(ContractError):replay_task_budget(local,p.binding,expected=p.expected)


def test_parent_refs_tamper_and_unindexed_chain_rejected(local, tmp_path):
    p=parent(local)
    local.verify_artifact(p.binding['launch_ref']).write_text('{}')
    with pytest.raises(StoreError):replay_task_budget(local,p.binding,expected=p.expected)
    other=LocalEvidence(tmp_path/'other')
    with pytest.raises(StoreError):replay_task_budget(other,p.binding,expected=p.expected)


def test_collector_entry_charges_handoff_and_cannot_renew(local):
    p=parent(local)
    args=dict(timeout_seconds=7199.9,deadline_monotonic=7300,budget_binding=p.binding,
              budget_reader=local,started_at=10,started_monotonic=110)
    deadline,timeout,_=collector._collection_budget(p.expected,**args)
    assert (deadline,timeout)==(7300,7190)
    with pytest.raises(ValueError):collector._collection_budget(p.expected,**{**args,'deadline_monotonic':7310})
    with pytest.raises(ValueError):collector._collection_budget(p.expected,**{**args,'budget_binding':None})
    with pytest.raises(ValueError):collector._collection_budget(p.expected,**{**args,'budget_reader':None})
    old=collector._collection_budget(p.expected,timeout_seconds=3600,deadline_monotonic=None,
        budget_binding=None,budget_reader=None,started_at=10,started_monotonic=110)
    assert old==(3710,3600,None)


def test_storage_replays_original_budget_and_rejects_fresh_child_window(local):
    p=parent(local)
    storage=dict(budget_binding=p.binding,collection_started_at=10,collection_started_monotonic=110,
                 timeout_seconds=7190,deadline_monotonic=7300)
    assert storage_budget(local,storage,p.expected)['budget_seconds']==7200
    with pytest.raises(ContractError):storage_budget(local,{**storage,'deadline_monotonic':7310},p.expected)
    with pytest.raises(ContractError):storage_budget(local,{**storage,'timeout_seconds':7200},p.expected)
    with pytest.raises(ContractError):storage_budget(local,dict(collection_started_at=10,timeout_seconds=7200),p.expected)


def test_task_command_optional_ceiling_preserves_legacy_default(local):
    raw=dict(argv=['fake'],cwd='/tmp',environment={},started_at=10,ended_at=20,exit_code=0,error=None,
             stdout_hash=local.register_json('out'),stderr_hash=local.register_json('err'),timeout_seconds=5000,pid=1)
    record={**raw,'log_hash':local.register_json(raw)}
    args=dict(argv=['fake'],cwd='/tmp',environment={},earliest=10,latest=20)
    with pytest.raises(ContractError):old_admission._execution(local,record,**args)
    assert old_admission._execution(local,record,**args,timeout_cap=7200,deadline=7200)==20
    with pytest.raises(ContractError):old_admission._execution(local,record,**args,timeout_cap=7200,deadline=100)


def test_unit_crosses_soft_cutoff_but_cannot_start_next_or_extend_D():
    unit=collection_unit_deadline(1000,POLICY,'task',now=699)
    assert unit==899 and unit<=1000-POLICY['terminal_seconds']
    # This unit can finish at850 (past S=700); no new unit can start there.
    with pytest.raises(TimeoutError,match='soft budget'):collection_unit_deadline(1000,POLICY,'task',now=850)
    assert collection_unit_deadline(1000,None,'task',now=999)==1000


def test_oracle_request_can_only_shorten_original_deadline(monkeypatch):
    oracle=object.__new__(PersistentOracle);oracle.deadline=1000
    monkeypatch.setattr('persistent_oracle.time.monotonic',lambda:100)
    assert oracle.remaining(200)==100 and oracle.remaining()==900
    with pytest.raises(ValueError):oracle.remaining(1001)
    with pytest.raises(TimeoutError):oracle.remaining(99)


spec=importlib.util.spec_from_file_location('budget_legacy_full_pmu',REPO/'scaffolding/tests/test_full_call_pmu.py')
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)
fixture=legacy.fixture


def test_legacy_full_pmu_keeps_existing_gate_and_occurrence_math(fixture):
    legacy.test_complete_roles_same_binary_all_occurrences(fixture)
    legacy.test_applied_runtime_dispatch_calls_full_replay(fixture)


def test_large_full_pmu_uses_same_bound_Task_launch(fixture, monkeypatch):
    f=fixture;p=parent(f.local,policy=None)
    # Complete Task replay itself is the existing explicit CPU fixture stub.
    storage_ref=f.put(dict(budget_binding=p.binding))
    registration={**f.registration,'profile_storage_ref':storage_ref};registration_ref=f.put(registration)
    def task_boundary(reader,ref,*,expected):
        assert ref==f.completion_ref
        assert expected['source_hashes']==f.sources
        return dict(valid=True,config_ref=f.config_ref,registration_ref=registration_ref,
                    hardware={'npu_smi_ref':f.tools[full_call_pmu.NPU_SMI]})
    monkeypatch.setattr(measurement_entry,'replay_current_measurement_admission',task_boundary)
    # Actual reviewed build window points at the same immutable original source plan.
    source={**p.source,'source_hashes':f.sources,'deadline_monotonic':7300}
    source_ref=f.put(source)
    build=json.loads(f.local.verify_artifact(f.build_window_ref).read_text())
    build.update(plan_ref=source_ref,deadline_monotonic=7300)
    build_ref=f.put(build)
    f.plan.update(launch_ref=p.binding['launch_ref'],build_window_ref=build_ref,deadline_monotonic=7300)
    f.evidence.artifacts.update(task_launch=p.binding['launch_ref'],build_window=build_ref)
    f.capture['deadline_monotonic']=7300
    f.refresh()
    for item in f.capture['captures']:f.seal(item)
    assert f.replay()['alignment'] is True
    f.capture['deadline_monotonic']=7400
    with pytest.raises(ContractError):f.replay()


@pytest.mark.parametrize('mutation', [
    lambda u:u.update(started_monotonic=700, deadline_monotonic=900),
    lambda u:u.update(deadline_monotonic=1000),
    lambda u:u.update(started_monotonic=True),
    lambda u:u.update(schema_version=True),
    lambda u:u.update(extra='unbound'),
])
def test_unit_receipt_replays_soft_start_and_exact_shortened_deadline(local, mutation):
    from aprof_runtime.task_window_measurement_admission import replay_collection_unit
    unit=dict(schema_version=1,started_at=599,started_monotonic=699,deadline_monotonic=899)
    args=dict(parent_deadline=1000,policy=POLICY,kind='task')
    assert replay_collection_unit(local,local.register_json(unit),**args)['wall_deadline']==799
    mutation(unit)
    with pytest.raises(ContractError):replay_collection_unit(local,local.register_json(unit),**args)


@pytest.mark.parametrize('mutation', ['none','missing','extend','after_soft','swapped_receipt','capture_window','oracle_window'])
def test_full_pmu_new_policy_checks_all_actual_unit_windows(fixture, monkeypatch, mutation):
    f=fixture;p=parent(f.local)
    registration={**f.registration,'profile_storage_ref':f.put(dict(budget_binding=p.binding))}
    registration_ref=f.put(registration)
    monkeypatch.setattr(measurement_entry,'replay_current_measurement_admission',lambda *a,**kw:
        dict(valid=True,config_ref=f.config_ref,registration_ref=registration_ref,
             hardware={'npu_smi_ref':f.tools[full_call_pmu.NPU_SMI]}))
    build=json.loads(f.local.verify_artifact(f.build_window_ref).read_text())
    build.update(plan_ref=f.put({**p.source,'source_hashes':f.sources,'deadline_monotonic':7300}),
                 deadline_monotonic=7300)
    build_ref=f.put(build)
    f.plan.update(launch_ref=p.binding['launch_ref'],build_window_ref=build_ref,deadline_monotonic=7300)
    f.evidence.artifacts.update(task_launch=p.binding['launch_ref'],build_window=build_ref)
    f.capture['deadline_monotonic']=7300
    for item in f.capture['warmups']+f.capture['captures']:
        actual=json.loads(f.local.verify_artifact(item['execution_ref']).read_text())
        start=actual['started_at']-.01
        item['collection_unit_ref']=f.put(dict(schema_version=1,started_at=start,
            started_monotonic=start+100,deadline_monotonic=collection_unit_deadline(7300,POLICY,"pmu",now=start+100)))
    f.refresh()
    for item in f.capture['captures']:f.seal(item)
    first=f.capture['captures'][0]
    if mutation=='missing':del first['collection_unit_ref']
    elif mutation in ('extend','after_soft','swapped_receipt'):
        unit=json.loads(f.local.verify_artifact(first['collection_unit_ref']).read_text())
        if mutation=='extend':unit['deadline_monotonic']+=1
        elif mutation=='after_soft':unit.update(started_monotonic=7000,deadline_monotonic=7100)
        else:unit['started_at']-=.001  # Valid arithmetic, but immutable capture receipt binds old ref.
        first['collection_unit_ref']=f.put(unit)
        if mutation!='swapped_receipt':f.seal(first)
    elif mutation in ('capture_window','oracle_window'):
        key='execution_ref' if mutation=='capture_window' else 'oracle_execution_ref'
        f.record(first,key,lambda v:v.update(timeout_seconds=101));f.seal(first)
    if mutation=='none':assert f.replay()['alignment'] is True
    else:
        with pytest.raises(ContractError):f.replay()
