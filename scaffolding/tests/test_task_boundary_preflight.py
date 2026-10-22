"""Original full boundaries and real Python oracle; native executor is CPU-only."""
from copy import deepcopy
import json
from pathlib import Path
import time

import pytest
import task_correctness_cpu_fixture as fixture
import task_rule_correctness as driver
from timing_admission import verify_boundary_report


@pytest.mark.parametrize('operator',['exp','sigmoid'])
def test_original_boundary_oracle_roster_and_missing_generator_fail_before_execution(tmp_path,monkeypatch,operator):
    args,protocol=fixture.fixture(tmp_path,operator)
    plan=driver.read(args['store'],protocol['boundary_plan_ref'])
    original=json.loads((driver.adapter.ROUND/operator/'candidate-qualification/protocol.json').read_text())
    oracles={path:ref for path,ref in original['oracle_files'].items()
             if ref in (plan['generator_ref'],plan['verifier_ref'])}
    for path,ref in oracles.items():assert args['store'].register_artifact(path)==ref
    checked=driver.preflight_boundary_plan(args['store'],operator=operator,source_hashes=args['expected']['source_hashes'],
        boundary_plan_ref=protocol['boundary_plan_ref'],oracle_files=oracles)
    assert len(checked['cases'])==(42 if operator=='exp' else 57)
    protocol['oracle_files']={p:r for p,r in oracles.items() if r!=plan['generator_ref']}
    args['protocol_ref']=args['store'].register_json(protocol)
    args['prepared']=driver.adapter.ROUND/operator/'boundary-inputs'
    executor=fixture.CPUExecutor(operator)
    monkeypatch.setattr(driver.bridge.profile_capture,'run',executor)
    with pytest.raises(driver.StageFailure,match='generator_ref') as error:
        driver.collect_correctness(**args,destination=tmp_path/'rejected',deadline=time.monotonic()+120,stage='boundary')
    assert executor.calls==[] and error.value.result['status']=='failed'


@pytest.fixture(scope='module',params=['exp','sigmoid'])
def completed(request,tmp_path_factory):
    root=tmp_path_factory.mktemp('boundary-contract-'+request.param)
    args,protocol=fixture.fixture(root,request.param)
    args['prepared']=driver.adapter.ROUND/request.param/'boundary-inputs'
    executor=fixture.CPUExecutor(request.param)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(driver.bridge.profile_capture,'run',executor)
        result=driver.collect_correctness(**args,destination=root/'complete',deadline=time.monotonic()+120,stage='boundary')
    assert len(executor.calls)==(42 if request.param=='exp' else 57)*4
    return args,result


def test_complete_original_boundary_collect_and_full_readonly_contract(completed):
    args,result=completed
    verdict=driver.verify_rule_correctness(args['store'],result['report_ref'],protocol_ref=args['protocol_ref'],
        expected=args['expected'],window=[result['started_at'],result['finished_at']])
    assert verdict['passed'] and verdict['case_count']==len(driver.read(args['store'],result['report_ref'])['case_ids'])


@pytest.mark.parametrize('fault',['time','source','output','oracle','execution'])
def test_full_boundary_replay_rejects_changed_real_evidence(completed,fault):
    args,result=completed;store=args['store'];report=deepcopy(driver.read(store,result['report_ref']))
    row=report['rows'][0]
    if fault=='time':
        value=driver.read(store,row['kernel_execution_ref']);value['started_at']=result['finished_at']+1
        row['kernel_execution_ref']=store.register_json(value)
    elif fault=='source':row['source_hash']=store.register_json({'CPU':'wrong source'})
    elif fault=='output':row['output_refs']=[store.register_json({'CPU':'wrong full output'})]
    elif fault=='oracle':
        value=driver.read(store,row['result_ref']);value['passed']=False
        row['result_ref']=store.register_json(value)
    else:
        value=driver.read(store,row['verifier_execution_ref']);value['argv']=['wrong-oracle']
        row['verifier_execution_ref']=store.register_json(value)
    with pytest.raises((ValueError,KeyError)):
        verify_boundary_report(store,store.register_json(report),protocol_ref=args['protocol_ref'],
            expected={**args['expected'],'boundary_window':[result['started_at'],result['finished_at']]})
