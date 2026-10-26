"""Behavioral checks for new tasks; no NPU or long wall-clock budgets."""
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from aprof_runtime.execution_policy import wait
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.local_archive import freeze_package_identity
from aprof_runtime.task_budget import prepare_budget_plan, run_task, replay_task_terminal
from aprof_runtime.task_workspace import create_workspace
from aprof_runtime.unified_timing import file_hash, evaluate_request, replay_capture
from test_original_oracle import original_config
from test_unified_capture import FakeRunner
from single_role_task import collect, collect_pair, SnapshotStore, inventory, reference, finish_case, collection_steps


def owned(tmp_path, monkeypatch):
    monkeypatch.setenv('APROF_TASK_ROOT', str(tmp_path))
    (tmp_path/'tmp').mkdir()
    return tmp_path


def test_soft_total_stage_and_continuation_keep_actual_errors(tmp_path):
    local=LocalEvidence(tmp_path/'records')
    identity=freeze_package_identity(local)
    budget=local.register_json(prepare_budget_plan(task_id='soft',scope_ref=local.register_json({}),budget_seconds=.01))
    prior=[]
    for i,code in enumerate(['import time; time.sleep(.05); print("done")','raise SystemExit(7)','print("continued")']):
        destination=tmp_path/f'run{i}'
        job=local.register_json({'argv':[sys.executable,'-c',code], 'cwd':str(tmp_path),
            'output_dir':str(destination),'environment':{},'timeout_seconds':.01,'package_identity_ref':identity})
        result=run_task(local,budget_ref=budget,job_ref=job,destination=destination,prior_terminal_refs=prior)
        prior.append(result['terminal_ref'])
        record=replay_task_terminal(local,result['terminal_ref'],task_id='soft',budget_ref=budget)
        assert record['status']==('failed' if i==1 else 'passed')
        assert record['execution']['exit_code']==(7 if i==1 else 0)
        assert record['execution']['budget_warnings']==['target_exceeded']
        if i==0:
            first=record['budget']['started_monotonic']
            assert (destination/'checkpoints.jsonl').exists()
        assert record['cumulative_seconds']==pytest.approx(record['finished_monotonic']-first)
        time.sleep(.01)  # continuation gap is charged too


def test_confirmed_local_hang_preserves_diagnostics_and_next_work(tmp_path):
    process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],start_new_session=True)
    with pytest.raises(RuntimeError,match='confirmed local hang'):
        wait(process,target_seconds=.01,checkpoint=tmp_path/'checkpoint.jsonl',
            confirm_hang=lambda sample:{'reason':'test injected confirmed deadlock','owner_pid':sample['pid']})
    assert process.returncode != 0
    assert 'confirmed_local_hang' in (tmp_path/'checkpoint.jsonl').read_text()
    process=subprocess.Popen([sys.executable,'-c','print("independent report")'],start_new_session=True)
    assert wait(process,target_seconds=.01,checkpoint=tmp_path/'next.jsonl')==0


def test_persistent_reuse_is_content_bound_and_unsigned_cache_cannot_pass(tmp_path,monkeypatch):
    owned(tmp_path,monkeypatch)
    config=original_config(tmp_path/'input')
    collect(config,tmp_path/'correctness',runner=FakeRunner(config),correctness_only=True,timeout_seconds=.001)
    path=tmp_path/'correctness/correctness.json'
    config['correctness']={'path':str(path),'sha256':file_hash(path)}
    collect(config,tmp_path/'capture',runner=FakeRunner(config),timeout_seconds=.001)
    env=dict(os.environ,PYTHONPATH=str(Path(__file__).resolve().parents[1]/'src'))
    code='from aprof_runtime.unified_timing import replay_capture; import sys; replay_capture(sys.argv[1])'
    subprocess.run([sys.executable,'-c',code,str(tmp_path/'capture/case_1/capture.json')],env=env,check=True)
    events=[json.loads(l) for l in (tmp_path/'validation-cache/events.jsonl').read_text().splitlines()]
    assert sum(e.get('oracle_executions',0) for e in events)==1
    assert sum(e['kind']=='validation_reuse' for e in events)>=3
    entries=list((tmp_path/'validation-cache').glob('*.json'))
    entry=json.loads(entries[0].read_text());entry['body']['validation']['pid']=0
    entries[0].write_text(json.dumps(entry))
    subprocess.run([sys.executable,'-c',code,str(tmp_path/'capture/case_1/capture.json')],env=env,check=True)
    events=[json.loads(l) for l in (tmp_path/'validation-cache/events.jsonl').read_text().splitlines()]
    assert sum(e.get('oracle_executions',0) for e in events)==2
    # A changed actual output is judged by the original oracle, not by equality alone.
    from aprof_runtime.original_oracle import execute, OracleFailure
    root=tmp_path/'capture/case_1';receipt=json.loads((root/'oracle_receipt.json').read_text())
    output=root/'outputs/output.bin';output.write_bytes(b'changed')
    receipt['checks'][0]['actual']=reference(root,output)
    with pytest.raises(OracleFailure,match='numerical_mismatch'):
        execute(root,receipt,config['cases'][0]['workload']['oracle_limits'])


def test_assumed_baseline_zero_oracles_and_pair_export_after_native(tmp_path,monkeypatch):
    owned(tmp_path,monkeypatch)
    a=original_config(tmp_path/'input');b=deepcopy(a)
    bsource=tmp_path/'candidate.cpp';bsource.write_text('changed source')
    b['source_files']=[str(bsource)]
    trust_root=tmp_path/'trust';trust_root.mkdir();store=SnapshotStore(trust_root)
    source=inventory(trust_root,'source',a['source_files'],store)
    decl_path=Path(a['declaration']['path']);decl=json.loads(decl_path.read_text())
    decl.update(schema_version=2,baseline_trust={'status':'assumed','basis':'user_provided_baseline',
        'source_sha256':source['sha256'],'binary_sha256':file_hash(a['binary'])})
    decl_path.write_text(json.dumps(decl));a['declaration']['sha256']=file_hash(decl_path);b['declaration']=a['declaration']
    a['baseline_status']='assumed'
    collect(b,tmp_path/'correctness',runner=FakeRunner(b),correctness_only=True)
    correct=tmp_path/'correctness/correctness.json';b['correctness']={'path':str(correct),'sha256':file_hash(correct)}
    runner=FakeRunner(a)
    collect_pair(a,b,tmp_path/'pair',runner=runner,timeout_seconds=.001)
    names=[Path(argv[1]).name for argv in runner.calls]
    assert names.index('msprof.py')>max(i for i,n in enumerate(names) if n=='profile')
    ar=tmp_path/'pair/A/case_1';br=tmp_path/'pair/B/case_1'
    assert json.loads((ar/'oracle_receipt.json').read_text())['status']=='assumed'
    assert json.loads((ar/'execution_receipt.json').read_text())['stages']['oracle']['oracle_executions']==0
    request={'schema_version':1,'protocol':a['protocol'],'operator':'test','candidate_id':'r1',
        'baseline_source_sha256':json.loads((ar/'capture.json').read_text())['identity']['source_sha256'],
        'candidate_source_sha256':json.loads((br/'capture.json').read_text())['identity']['source_sha256'],
        'declaration':reference(tmp_path,decl_path),'baseline_captures':[reference(tmp_path,ar/'capture.json')],
        'candidate_captures':[reference(tmp_path,br/'capture.json')],'baseline_correctness':None,
        'candidate_correctness':reference(tmp_path,correct)}
    p=tmp_path/'comparison.json';p.write_text(json.dumps(request))
    assert evaluate_request(p)['baseline_correctness_status']=='assumed'
    assert sum(json.loads(l).get('oracle_executions',0) for l in (tmp_path/'validation-cache/events.jsonl').read_text().splitlines())==1
    # Changing baseline identity cannot borrow the assumption.
    a['source_files']=[str(bsource)]
    with pytest.raises(ValueError,match='cannot inherit'):
        collect(a,tmp_path/'wrong',runner=FakeRunner(a))


def test_local_paths_and_missing_workspace(tmp_path):
    with pytest.raises(ValueError,match='/dev/shm'):
        create_workspace('bad',parent='/tmp')
    from aprof_runtime.execution_policy import task_root
    assert task_root(tmp_path/'missing') is None


def test_multioutput_coverage_and_target_only_change_reuses(tmp_path,monkeypatch):
    owned(tmp_path,monkeypatch)
    from aprof_runtime.original_oracle import config_contract, execute
    from aprof_runtime.errors import ContractError
    config=original_config(tmp_path/'inputs')
    c=config['cases'][0]
    oracle=Path(c['oracle_source'])
    oracle.write_text("import json\nfrom pathlib import Path\np=Path('out.bin').read_bytes()==Path('golden.bin').read_bytes() and Path('other.bin').read_bytes()==Path('golden.bin').read_bytes()\nPath('result.json').write_text(json.dumps({'passed':p}))\n")
    c['oracle_replay']['outputs']['other.bin']={'actual':'outputs/other.bin','dtype':'bfloat16'}
    c['workload']['oracle_limits']['contract_sha256']=config_contract(c['oracle_replay'])
    base=FakeRunner(config)
    def runner(argv,**kwargs):
        v=base(argv,**kwargs)
        root=Path(kwargs['cwd'])
        if (root/'outputs/output.bin').exists():
            (root/'outputs/other.bin').write_bytes((root/'outputs/output.bin').read_bytes())
        return v
    collect(config,tmp_path/'correctness',runner=runner,correctness_only=True)
    root=tmp_path/'correctness/case_1'
    receipt=json.loads((root/'oracle_receipt.json').read_text())
    spec=receipt['replay'];spec['timeout_seconds']=.001
    from aprof_runtime.original_oracle import contract
    limits={'mode':'original_python_v1','contract_sha256':contract(spec)}
    workload=json.loads((root/'workload.json').read_text());workload['oracle_limits']=limits
    (root/'workload.json').write_text(json.dumps(workload));receipt['workload_ref']=file_hash(root/'workload.json')
    assert execute(root,receipt,limits)['kind']=='validation_reuse'
    receipt['checks'].pop()
    with pytest.raises(ContractError,match='覆盖'):
        execute(root,receipt,limits)


def test_changed_but_valid_output_is_revalidated_and_cached(tmp_path,monkeypatch):
    owned(tmp_path,monkeypatch)
    config=original_config(tmp_path/'input',program="import json\nfrom pathlib import Path\nPath('result.json').write_text(json.dumps({'passed':len(Path('out.bin').read_bytes())==8}))\n")
    collect(config,tmp_path/'correctness',runner=FakeRunner(config),correctness_only=True)
    correct=tmp_path/'correctness/correctness.json';config['correctness']={'path':str(correct),'sha256':file_hash(correct)}
    collect(config,tmp_path/'changed',runner=FakeRunner(config,wrong_output=True))
    replay_capture(tmp_path/'changed/case_1/capture.json')
    events=[json.loads(l) for l in (tmp_path/'validation-cache/events.jsonl').read_text().splitlines()]
    assert sum(e.get('oracle_executions',0) for e in events)==2


def test_reserve_exceeding_total_is_planning_only():
    value=prepare_budget_plan(task_id='reserve',scope_ref='sha256:'+'a'*64,budget_seconds=.01,
        collection_stop_policy={'kind':'finish_started_unit_v1','reserve_seconds':1200,
            'task_unit_seconds':60,'pmu_unit_seconds':60,'terminal_seconds':180})
    assert value['schema_version']==2


def test_pending_postprocessing_resumes_without_native(tmp_path,monkeypatch):
    owned(tmp_path,monkeypatch)
    config=original_config(tmp_path/'input')
    collect(config,tmp_path/'correctness',runner=FakeRunner(config),correctness_only=True)
    correct=tmp_path/'correctness/correctness.json';config['correctness']={'path':str(correct),'sha256':file_hash(correct)}
    runner=FakeRunner(config)
    steps=collection_steps(config,tmp_path/'capture',runner=runner)
    next(steps);pending=next(steps)['pending'][0];steps.close()
    calls=len(runner.calls)
    finish_case(pending,deadline=time.monotonic()-1,runner=runner)
    assert all(Path(argv[1]).name!='profile' for argv in runner.calls[calls:])
    assert replay_capture(tmp_path/'capture/case_1/capture.json')['median_us']==80
