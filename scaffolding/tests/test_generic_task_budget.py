"""Candidate 1.0.1 budgets: actual CPU exits, no benchmark dispatcher dependency."""
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

from aprof_runtime.errors import ContractError
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.task_budget import (prepare_budget_plan, prepare_task_launch, replay_task_budget,
    replay_task_terminal, remaining_task_budget, run_task, _execution_job)


@pytest.fixture(autouse=True)
def stable_identity_files(monkeypatch):
    # Full producer-closure validation belongs to the archive suite; isolate the
    # process/deadline tests from concurrent candidate source edits.
    from aprof_runtime import local_archive
    monkeypatch.setattr(local_archive, 'identity_files', lambda: (
        '.codex-plugin/plugin.json','runtime/pyproject.toml','runtime/src/aprof_runtime/__init__.py'))


def setup_budget(tmp_path, total=7200, *, task_id='ordinary-task', scope=None):
    local = LocalEvidence(tmp_path / 'records')
    scope_ref = local.register_json(scope or {'task':'ordinary source optimization'})
    budget_ref = local.register_json(prepare_budget_plan(task_id=task_id, scope_ref=scope_ref, budget_seconds=total))
    return local, budget_ref


def job(local, tmp_path, timeout, code='print("CPU")', name='attempt', identity=False):
    from aprof_runtime.local_archive import freeze_package_identity
    extra={'package_identity_ref':freeze_package_identity(local)} if identity else {}
    return local.register_json(dict(**extra,job_id=name, argv=[sys.executable, '-c', code], cwd=str(tmp_path),
        output_dir=str(tmp_path / name), timeout_seconds=timeout, environment={}))


def segment(local, budget_ref, job_ref, *, prior=(), start=100, wall=1000, elapsed=2, status='failed', log_value=None):
    launch = prepare_task_launch(local, budget_ref=budget_ref, job_ref=job_ref, prior_terminal_refs=prior,
        started_at=wall, started_monotonic=start, issued_monotonic=start + .1)
    launch_ref = local.register_json(launch)
    parent = replay_task_budget(local, {'kind':'task','launch_ref':launch_ref}, task_id=launch['task_id'])
    log = local.register_json(log_value or {'log':'synthetic process report fixture'})
    execution = dict(schema_version='1.0.0', kind='aprof_execution_report',
        job=_execution_job(parent, launch_ref), status=status, exit_code=0 if status=='passed' else 2,
        started_at=wall + .1, finished_at=wall + elapsed, duration_seconds=elapsed - .1,
        stdout={'path':str(local.verify_artifact(log)), 'sha256':log},
        stderr={'path':str(local.verify_artifact(log)), 'sha256':log})
    execution_ref=local.register_json(execution)
    terminal=local.register_json(dict(schema_version=1, kind='task_terminal_v1', launch_ref=launch_ref,
        execution_ref=execution_ref, status='passed' if status=='passed' else 'failed',
        finished_at=wall+elapsed, finished_monotonic=start+elapsed))
    return terminal, launch_ref


def test_real_short_command_large_budget(tmp_path):
    local, budget = setup_budget(tmp_path)
    j = job(local, tmp_path, 7200, 'import os; print(os.environ["APROF_TASK_LAUNCH_REF"])', identity=True)
    result = run_task(local, budget_ref=budget, job_ref=j, destination=tmp_path / 'attempt')
    replay = replay_task_terminal(local, result['terminal_ref'], task_id='ordinary-task', budget_ref=budget)
    assert result['status']=='passed' and result['archive_performed'] is False
    assert 0 < replay['segment_seconds'] < 10
    assert replay['budget']['deadline_monotonic'] == replay['budget']['started_monotonic'] + 7200
    assert local.verify_artifact(replay['execution']['stdout']['sha256']).read_text().strip()==result['launch_ref']
    assert not list(tmp_path.rglob('*.sqlite*'))
    with pytest.raises(FileExistsError):
        run_task(local,budget_ref=budget,job_ref=j,destination=tmp_path/'attempt')


def test_real_timeout_retained_and_charged(tmp_path):
    local, budget=setup_budget(tmp_path, .12)
    j=job(local,tmp_path,.12,'import time; time.sleep(10)', identity=True)
    result=run_task(local,budget_ref=budget,job_ref=j,destination=tmp_path/'attempt')
    replay=replay_task_terminal(local,result['terminal_ref'],task_id='ordinary-task',budget_ref=budget)
    assert replay['status']=='failed' and replay['execution']['status']=='timeout'
    assert replay['segment_seconds'] >= .12
    state=remaining_task_budget(local,budget_ref=budget,prior_terminal_refs=[result['terminal_ref']])
    assert state['remaining_budget_seconds'] <= 0
    with pytest.raises(ContractError,match='exhausted'):
        prepare_task_launch(local,budget_ref=budget,job_ref=j,prior_terminal_refs=[result['terminal_ref']],
            started_at=time.time(),started_monotonic=time.monotonic(),issued_monotonic=time.monotonic())


def test_failed_segment_recovery_uses_remaining_and_same_freeze(tmp_path):
    local,budget=setup_budget(tmp_path,7200); j=job(local,tmp_path,7200)
    first, _=segment(local,budget,j,elapsed=15)
    state=remaining_task_budget(local,budget_ref=budget,prior_terminal_refs=[first])
    assert state['remaining_budget_seconds']==7185
    second_job=job(local,tmp_path,7185,name='second')
    second, launch_ref=segment(local,budget,second_job,prior=[first],start=500,wall=2000,elapsed=7,status='passed')
    replay=replay_task_terminal(local,second,task_id='ordinary-task',budget_ref=budget)
    assert replay['cumulative_seconds']==22 and replay['budget']['deadline_monotonic']==500+7185
    assert replay['budget']['prior_launch_refs']
    wrong=local.register_json(dict(replay['budget']['job'],timeout_seconds=7200))
    with pytest.raises(ContractError):
        prepare_task_launch(local,budget_ref=budget,job_ref=wrong,prior_terminal_refs=[first],
            started_at=2000,started_monotonic=500,issued_monotonic=501)
    other=local.register_json(prepare_budget_plan(task_id='ordinary-task',scope_ref=replay['budget']['scope_ref'],budget_seconds=8000))
    with pytest.raises(ContractError,match='changed frozen budget'):
        remaining_task_budget(local,budget_ref=other,prior_terminal_refs=[first])
    with pytest.raises(ContractError,match='identity'):
        replay_task_budget(local,{'kind':'task','launch_ref':launch_ref},task_id='other-arm')


@pytest.mark.parametrize('mutation', ['deadline','child','budget','job','prior'])
def test_launch_mutations_rejected(tmp_path,mutation):
    local,budget=setup_budget(tmp_path);j=job(local,tmp_path,7200)
    launch=prepare_task_launch(local,budget_ref=budget,job_ref=j,started_at=1000,started_monotonic=100,issued_monotonic=101)
    if mutation=='deadline':launch['deadline_monotonic']+=1
    if mutation=='child':launch['child_timeout_seconds']+=1
    if mutation=='budget':launch['budget_ref']=local.register_json(prepare_budget_plan(task_id='ordinary-task',scope_ref=local.register_json({}),budget_seconds=8000))
    if mutation=='job':launch['job_ref']=job(local,tmp_path,9000,name='wrong')
    if mutation=='prior':launch['prior_terminal_refs']=[j,j]
    with pytest.raises(ContractError):
        replay_task_budget(local,{'kind':'task','launch_ref':local.register_json(launch)},task_id='ordinary-task')


def test_failed_overrun_valid_passed_overrun_rejected(tmp_path):
    local,budget=setup_budget(tmp_path,10);j=job(local,tmp_path,10)
    late,_=segment(local,budget,j,elapsed=12,status='timeout')
    assert replay_task_terminal(local,late,task_id='ordinary-task',budget_ref=budget)['cumulative_seconds']==12
    late,_=segment(local,budget,j,elapsed=12,status='passed')
    with pytest.raises(ContractError):replay_task_terminal(local,late,task_id='ordinary-task',budget_ref=budget)


def test_generic_task_window_dispatch_and_full_pmu_original_window(tmp_path):
    from aprof_runtime.task_window_measurement_admission import replay_task_budget as task_budget
    from aprof_runtime.full_call_pmu import _original_window
    local,budget=setup_budget(tmp_path,100);j=job(local,tmp_path,100)
    terminal,launch_ref=segment(local,budget,j,elapsed=40)
    binding={'kind':'task','launch_ref':launch_ref}
    assert task_budget(local,binding,expected={'run_id':'ordinary-task'})['budget_seconds']==100
    sources={'baseline':local.register_json({'files':{}}),'candidate':local.register_json({'files':{'a':'b'}})}
    binary=local.register_json({'binary':'fixture'})
    build_plan=local.register_json({'source_hashes':sources})
    build=dict(kind='reviewed_candidate_build',plan_ref=build_plan,deadline_monotonic=200,
        started_at=1001,finished_at=1002,started_monotonic=101,finished_monotonic=102,
        status='passed',error=None,binary={'sha256':binary})
    build_ref=local.register_json(build)
    plan=dict(launch_ref=launch_ref,build_window_ref=build_ref,deadline_monotonic=200,
        created_at=1003,source_hashes=sources)
    identity={'build':{'binary_ref':binary,'receipt_refs':{'build':build_ref}}}
    evidence=SimpleNamespace(artifacts={'task_launch':launch_ref,'build_window':build_ref})
    args=(local,plan,evidence,{'started_at':1004,'finished_at':1035},{'run_id':'ordinary-task'},identity)
    assert _original_window(*args,budget_binding=binding)[1]==1100
    j2=job(local,tmp_path,60,name='pmu')
    new=prepare_task_launch(local,budget_ref=budget,job_ref=j2,prior_terminal_refs=[terminal],
        started_at=1050,started_monotonic=150,issued_monotonic=151)
    new_ref=local.register_json(new)
    effective,wall,_=_original_window(*args,budget_binding=binding,
        capture_budget_binding={'kind':'task','launch_ref':new_ref})
    assert effective['deadline_monotonic']==210 and wall==1110
    other_launch=prepare_task_launch(local,budget_ref=budget,job_ref=j,started_at=1050,started_monotonic=150,issued_monotonic=151)
    with pytest.raises(ContractError,match='same task budget prefix'):
        _original_window(*args,budget_binding=binding,capture_budget_binding={'kind':'task','launch_ref':local.register_json(other_launch)})


def test_missing_declared_child_index_preserves_actual_exit_but_fails_task(tmp_path):
    local,budget=setup_budget(tmp_path)
    original=job(local,tmp_path,7200,identity=True)
    value=json.loads(local.verify_artifact(original).read_text())
    value['evidence_indices']=[str(tmp_path/'missing/index.json')]
    result=run_task(local,budget_ref=budget,job_ref=local.register_json(value),destination=tmp_path/'attempt')
    terminal=replay_task_terminal(local,result['terminal_ref'],task_id='ordinary-task',budget_ref=budget)
    assert terminal['status']=='failed' and terminal['execution']['exit_code']==0
    assert terminal['execution']['evidence_indices']==[{'path':value['evidence_indices'][0],'status':'missing'}]


def test_failed_child_merges_available_partial_index_without_copy(tmp_path):
    local,budget=setup_budget(tmp_path)
    code="""from pathlib import Path
from aprof_runtime.local_evidence import LocalEvidence
import sys
root=Path('child');root.mkdir()
local=LocalEvidence(root/'records')
raw=root/'raw.bin';raw.write_bytes(b'actual partial observation')
local.register_artifact(raw)
local.write_index(root/'index.json')
sys.exit(2)
"""
    original=job(local,tmp_path,7200,code,identity=True)
    value=json.loads(local.verify_artifact(original).read_text())
    value['environment']={'PYTHONPATH':str(Path(__file__).resolve().parents[2]/'skill-libs/graph-base/1.0.1/runtime/src'),
                          'PYTHONDONTWRITEBYTECODE':'1'}
    value['evidence_indices']=[str(tmp_path/'child/index.json'),str(tmp_path/'never-started/index.json')]
    result=run_task(local,budget_ref=budget,job_ref=local.register_json(value),destination=tmp_path/'attempt')
    terminal=replay_task_terminal(local,result['terminal_ref'],task_id='ordinary-task',budget_ref=budget)
    assert terminal['status']=='failed' and terminal['execution']['exit_code']==2
    assert [row['status'] for row in terminal['execution']['evidence_indices']]==['merged','missing']
    restored=LocalEvidence.from_index(result['local_index'])
    child=json.loads((tmp_path/'child/index.json').read_text())
    assert all(restored.verify_artifact(ref)==Path(path) for ref,path in child['artifacts'].items())
    assert not list(tmp_path.rglob('*.sqlite*'))


def test_stage_plan_requires_declared_child_handoff(tmp_path):
    from aprof_runtime.stage_recovery import default_stage_plan
    local=LocalEvidence(tmp_path/'records');source=local.register_json({'source':'fixed'})
    scope=default_stage_plan(task_id='ordinary-task',source_ref=source,input_ref=source,toolchain_ref=source,protocol_ref=source)
    budget=local.register_json(prepare_budget_plan(task_id='ordinary-task',scope_ref=local.register_json(scope),budget_seconds=7200))
    original=job(local,tmp_path,7200,identity=True)
    with pytest.raises(ContractError,match='child evidence indices'):
        run_task(local,budget_ref=budget,job_ref=original,destination=tmp_path/'attempt')
    assert not (tmp_path/'attempt').exists()
