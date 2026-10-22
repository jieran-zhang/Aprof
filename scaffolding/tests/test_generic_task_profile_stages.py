import importlib.util
import json
from pathlib import Path
import sys
import time

import pytest

from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.task_budget import prepare_budget_plan,prepare_task_launch,replay_task_terminal,run_task
from aprof_runtime.stage_recovery import default_stage_plan
from test_generic_task_budget import job,stable_identity_files


PACKAGE=Path(__file__).resolve().parents[2]/'skill-libs/graph-base/1.0.1'
SCRIPT=PACKAGE/'skills/ascendc-aprof-profiling/scripts/run_profile_stages.py'
spec=importlib.util.spec_from_file_location('generic_profile_stages',SCRIPT)
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def setup(tmp_path,total=7200):
    local=LocalEvidence(tmp_path/'records')
    config=dict(schema_version='1.0.0',op_dir=str(tmp_path),output_dir=str(tmp_path/'stages'),
        stages=[dict(name='preflight',commands=[[sys.executable,'-c','print("preflight")']])])
    config_ref=local.register_json(config); ref=local.register_json({'source':'original'})
    scope=default_stage_plan(task_id='ordinary-task',source_ref=ref,input_ref=ref,toolchain_ref=ref,protocol_ref=ref)
    scope['stages'][0]['inputs']['command_config']=config_ref
    scope_ref=local.register_json(scope)
    budget=local.register_json(prepare_budget_plan(task_id='ordinary-task',scope_ref=scope_ref,budget_seconds=total))
    return local,config,budget


def bind(local,budget,tmp_path,total,monkeypatch):
    wall,mono=time.time(),time.monotonic()
    launch=prepare_task_launch(local,budget_ref=budget,job_ref=job(local,tmp_path,total),started_at=wall,
        started_monotonic=mono,issued_monotonic=mono)
    ref=local.register_json(launch);index=local.write_index(tmp_path/'parent-index.json')
    monkeypatch.setenv('APROF_TASK_LAUNCH_REF',ref)
    monkeypatch.setenv('APROF_TASK_LOCAL_INDEX',str(index))
    monkeypatch.setenv('APROF_TASK_DEADLINE_MONOTONIC',str(launch['deadline_monotonic']))
    return ref,launch


def test_package_supervisor_child_automatically_inherits_original_budget(tmp_path):
    local,config,budget=setup(tmp_path)
    config_path=tmp_path/'commands.json';config_path.write_text(json.dumps(config))
    from aprof_runtime.local_archive import freeze_package_identity
    j=local.register_json(dict(job_id='stages',argv=[sys.executable,str(SCRIPT),'--config',str(config_path),
        '--report',str(tmp_path/'stage-report.json')],cwd=str(tmp_path),output_dir=str(tmp_path/'attempt'),
        timeout_seconds=7200,environment={'PYTHONDONTWRITEBYTECODE':'1'},
        evidence_indices=[str(tmp_path/'stages/local-evidence-index.json')],package_identity_ref=freeze_package_identity(local)))
    result=run_task(local,budget_ref=budget,job_ref=j,destination=tmp_path/'attempt')
    terminal=replay_task_terminal(local,result['terminal_ref'],task_id='ordinary-task',budget_ref=budget)
    report=json.loads((tmp_path/'stage-report.json').read_text())
    assert terminal['status']==report['terminal_status']=='passed'
    assert report['deadline_monotonic']==terminal['budget']['deadline_monotonic']
    assert report['budget_binding']=={'kind':'task','launch_ref':result['launch_ref']}
    restored=LocalEvidence.from_index(result['local_index'])
    child=json.loads((tmp_path/'stages/local-evidence-index.json').read_text())
    assert all(restored.verify_artifact(ref).is_file() for ref in child['artifacts'])
    assert terminal['execution']['evidence_indices'][0]['status']=='merged'


def test_two_commands_share_one_deadline(tmp_path,monkeypatch):
    local,config,_=setup(tmp_path)
    config['stages'][0]['commands']=[[sys.executable,'-c','import time; time.sleep(.08)'],
                                    [sys.executable,'-c','import time; time.sleep(.3)']]
    config_ref=local.register_json(config);source=local.register_json({'source':'same'})
    scope=default_stage_plan(task_id='ordinary-task',source_ref=source,input_ref=source,toolchain_ref=source,protocol_ref=source)
    scope['stages'][0]['inputs']['command_config']=config_ref
    budget=local.register_json(prepare_budget_plan(task_id='ordinary-task',scope_ref=local.register_json(scope),budget_seconds=.2))
    _,launch=bind(local,budget,tmp_path,.2,monkeypatch)
    before=time.monotonic();report=runner.execute(config)
    assert report['terminal_status'] in ('preflight_failed','budget_exhausted')
    assert report['stages'][0]['commands'][1]['timed_out'] is True
    assert time.monotonic()-before < .4
    assert report['deadline_monotonic']==launch['deadline_monotonic']


def test_explicit_different_parent_or_config_rejected(tmp_path,monkeypatch):
    local,config,budget=setup(tmp_path);ref,_=bind(local,budget,tmp_path,7200,monkeypatch)
    with pytest.raises(ValueError,match='differs from inherited'):
        runner.execute(config,budget_binding={'kind':'task','launch_ref':'sha256:'+'0'*64},budget_reader=local)
    config['stages'][0]['commands']=[[sys.executable,'-c','print("different")']]
    with pytest.raises(ValueError,match='not frozen'):
        runner.execute(config)
    monkeypatch.setenv('APROF_TASK_DEADLINE_MONOTONIC','9000000000')
    with pytest.raises(ValueError,match='deadline differs'):
        runner.execute(config)


def test_expired_parent_cannot_start_first_command(tmp_path,monkeypatch):
    local,config,budget=setup(tmp_path,1);_,launch=bind(local,budget,tmp_path,1,monkeypatch)
    monkeypatch.setattr(runner.time,'monotonic',lambda:launch['deadline_monotonic']+1)
    monkeypatch.setattr(runner.subprocess,'run',lambda *a,**k:pytest.fail('expired child launched'))
    report=runner.execute(config)
    assert report['terminal_status'] in ('preflight_failed','budget_exhausted')
