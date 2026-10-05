"""One-process qualification uses real fixed-control ledger accounting, no NPU."""
from pathlib import Path
import json
import sys
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import level2_raw_method as method
from msprof_exploration_campaign import create_fresh, Campaign
from msprof_exploration_execute import load, pointer, save, sha


@pytest.fixture(params=[1,10])
def prepared(tmp_path,monkeypatch,request):
    repeat=request.param;task=tmp_path/'train/tasks/maximum';task.mkdir(parents=True)
    archive=task/'baseline-source.tar';archive.write_bytes(b'original frozen source')
    save(task/'manifest.json',{'version':'msprof_task_time_exploration_v2'})
    save(task/'measurement-policy.json',{'repeat_by_case':{str(c):repeat for c in range(1,21)},'timing_timeout_seconds':1800})
    save(task/'build/build_manifest.json',{'operator':'maximum'})
    save(tmp_path/'tools/timing/build.json',{'runner_hash':'sha256:'+'b'*64})
    metadata=task/'inputs/case_01/metadata.json';save(metadata,{'case_id':1})
    verifier=task/'baseline/scripts/verify_result.py';verifier.parent.mkdir(parents=True);verifier.write_text('# immutable oracle')
    save(task/'input-bindings.json',{'cases':[{'case_id':1,'metadata':pointer(metadata),'verifier':pointer(verifier)}]})
    create_fresh(tmp_path/'train/ledger',campaign_id='method-cpu-test',workloads={'maximum':{
        'baseline_source_hash':sha(archive),'source_split':'test','repeat_by_case':{str(c):repeat for c in range(1,21)},'pilot_ref':'sha256:'+'a'*64}})
    calls=[];fault={'when':None}
    monkeypatch.setattr(method,'verify_source_snapshot',lambda *a:None)
    monkeypatch.setattr(method,'preflight_cohort',lambda p:{'status':'passed','read_only':True})
    def collect(path,out):
        req=load(path);calls.append(req)
        if fault['when']=='before':raise RuntimeError('host occupied before native')
        journal=out/'native/journal.jsonl';journal.parent.mkdir(parents=True)
        rows=[{'type':'process_start'}]
        if fault['when']!='after':
            for config in ('normal','swapped'):
                rows += [{'type':'case_start','case_id':'1','buffer_config':config},
                         {'type':'warmup_complete','calls_per_role':10}]
                rows += [{'type':'sample','repeat':repeat,'launches_per_call':1} for _ in range(60)]
            rows += [{'type':'session_end','exit_code':0}]
        journal.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        if fault['when']=='after':raise RuntimeError('profiler teardown interrupted')
    monkeypatch.setattr(method,'execution_modules',lambda:(SimpleNamespace(collect=collect),None,None))
    def verify(directory,expected_request,provenance_out):
        assert expected_request==calls[0]
        return {'session_id':directory.name,'case_bindings':{'1':'identity'},'artifacts':{}}
    monkeypatch.setattr(method,'verify_observation',verify)
    return tmp_path,task,repeat,calls,fault


def test_one_process_is_fixed_method_cost_and_never_calibration(prepared):
    run,task,repeat,calls,_=prepared
    result=method.qualify(run,'maximum')
    assert result['status']=='passed' and len(calls)==1
    assert calls[0]['cases'][0]['repeat']==repeat
    assert calls[0]['buffer_configs']=='normal,swapped'
    state=Campaign(run/'train/ledger').state['tasks']['maximum']
    assert state['new_source_attempts']==state['new_rounds_started']==0
    assert all(value==0 for value in state['used'].values())
    row=state['stages']['baseline-raw-local-method-01']
    assert row['plan']['control_type']=='method' and row['plan']['declared_native_processes']==1
    assert row['plan']['calibration_eligible'] is False and row['candidate_id'] is None
    assert row['attempts'][-1]['formal_samples']==120
    assert state['fixed_costs']['native_processes_started']==1
    assert state['fixed_costs']['timed_complete_calls']==120*repeat
    assert not list((task/'stages/raw-local-method-01').rglob('report.json'))
    with pytest.raises(FileExistsError):method.qualify(run,'maximum')
    assert len(calls)==1


@pytest.mark.parametrize('when,native',[('before',False),('after',True)])
def test_failed_method_preserves_actual_cost_without_retry_or_round_charge(prepared,when,native):
    run,task,repeat,calls,fault=prepared;fault['when']=when
    result=method.qualify(run,'maximum')
    assert result['status']=='failed' and result['native_started'] is native
    state=Campaign(run/'train/ledger').state['tasks']['maximum']
    row=state['stages']['baseline-raw-local-method-01']['attempts'][-1]
    assert row['outcome']=='failed' and row['native_started'] is native
    assert row['actual_costs']['native_processes_started']==int(native)
    assert row['formal_samples']==0 and state['new_rounds_started']==0
    assert (task/'stages/raw-local-method-01/request.json').is_file()
    assert not (task/'stages/raw-local-method-01/method-qualification.json').exists()
    assert len(calls)==1
