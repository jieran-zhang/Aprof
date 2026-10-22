"""Small local plan/config/exit joins; no device, input generator or claimed qualification."""
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
import task_baseline_qualification as baseline
from aprof_runtime.errors import ContractError
from aprof_runtime.local_evidence import LocalEvidence


@pytest.fixture
def planned(tmp_path,monkeypatch):
    def make(operator='gelu'):
        root=tmp_path/operator;root.mkdir()
        local=LocalEvidence(root/'records')
        source={}
        for role in baseline.ROLES:
            folder=root/role;(folder/'op_kernel').mkdir(parents=True)
            (folder/'op_kernel/kernel.asc').write_text('// CPU plan source; no kernel execution\n')
            source[role]=folder
        files=baseline.bridge.profile_capture.source_inventory(source['baseline'])
        preparation=local.register_json({'schema_version':1,'operator':operator,
            'state':'cpu_prepared_awaiting_baseline_qualification','source_files':files})
        prepared=root/'inputs';prepared.mkdir()
        for cid in baseline.CASE_IDS:
            folder=prepared/f'case_{cid:02d}';folder.mkdir()
            data=folder/'input.bin';data.write_bytes(b'CPU fixture only')
            m={'case_id':cid,'input':str(data),'output':str(folder/'output.bin'),'dtype':'float16',
               'numel':8,'approximate':'none','shape':[2,4], 'num_groups':2,'epsilon':0.00001,
               'x':str(data),'gamma':str(data),'beta':str(data),
               'query_shape':[2,4,8,16],'key_shape':[2,4,2,16],'scaleValue':0.25,'is_causal':False,
               'query':str(data),'key':str(data),'value':str(data)}
            if operator=='dynamic_quant':
                m.pop('output'); m.update(output_y=str(folder/'y.bin'),output_scale=str(folder/'scale.bin'))
            if operator=='weight_quant_batch_matmul':
                m.update(dtype=['float16'],m=2,k=4,n=8,paths={'x':str(data),'weight':str(data),'scale':str(data)})
            (folder/'metadata.json').write_text(json.dumps(m))
        assembly=root/'assembly';assembly.mkdir()
        (assembly/'source-review.json').write_text('{"CPU":"source proof fixture, not a real build"}')
        job=local.register_json({'timeout_seconds':3600,'output_dir':str(root/'job'),'argv':['CPU-never-executed']})
        tool=root/'tool';tool.write_text('CPU tool identity')
        producer=root/'producer';producer.write_text('CPU producer identity')
        monkeypatch.setattr(baseline,'PROFILE_DEPENDENCY_PATHS',(str(tool),))
        monkeypatch.setattr(baseline,'producer_paths',lambda:{str(producer)})
        scope=baseline.case_scope(operator,json.loads((prepared/'case_01/metadata.json').read_text()))
        profile={'case_id':1,'kernels':[scope['role_kernel_names']['baseline'][0].removeprefix('aprof_baseline_')],
            'metrics':{'aic_time':{'unit':'us','file':'op_summary*.csv','format':'csv','field':'aicore_time(us)',
                'row_aggregation':'median','aggregation':'median'}}}
        kwargs=dict(operator=operator,sources=source,assembly=assembly,prepared_inputs=prepared,
            scratch_root=root/'scratch',preparation_ref=preparation,profile=profile,job_ref=job,
            identity={'run_id':'CPU','session_id':'CPU','candidate_id':'CPU'},physical_device=0,created_at=1,
            toolchain_refs={str(tool):local.register_artifact(tool)},producer_refs={str(producer):local.register_artifact(producer)})
        ref=baseline.prepare_baseline_plan(local,**kwargs)
        return root,local,ref,kwargs
    return make


@pytest.mark.parametrize('operator',baseline.OPERATORS)
def test_all_twenty_cases_preserve_full_callback_and_local_readonly_plan(planned,operator):
    root,local,ref,_=planned(operator)
    count=local._sequence
    plan=baseline.checked_plan(local,ref)
    assert local._sequence==count
    assert plan['case_ids']==list(range(1,21)) and plan['budget_policy']=='time_only_v1'
    assert plan['source_hashes']['baseline']==plan['source_hashes']['candidate']
    expected=11 if operator=='gqa' else 3 if operator=='weight_quant_batch_matmul' else 1
    for case in plan['cases']:
        assert set(case['launches_per_call'].values())=={expected}
        assert all(len(names)==expected for names in case['role_kernel_names'].values())
    if operator=='gqa':
        names=plan['cases'][0]['role_kernel_names']['baseline']
        assert names.count('aprof_baseline_gqa_qk_fp16')==4
        assert names.count('aprof_baseline_gqa_pv_fp16')==4
    build={'binary':{'path':str(root/'assembly/build'/operator)},
           'attempt_ref':{'path':str(root/'assembly/build-attempt.json')}}
    config=baseline._task_config(local,plan,root/'assembly/build-receipt.json',build)
    assert len(config['cases'])==20 and config['expected_case_ids']==list(range(1,21))
    assert all(len(c['output_files']['baseline'])==(2 if operator=='dynamic_quant' else 1) for c in config['cases'])
    for case in config['cases']:
        for role,outputs in case['output_files'].items():
            assert all(path in case['command'] and path in case['verify_commands'][role] for path in outputs)
    assert not list(root.rglob('*.sqlite')) and not (root/'objects').exists()


@pytest.mark.parametrize('defect',['scope','role_names','source','input','producer','pmu','legacy','budget'])
def test_changed_plan_or_original_bytes_rejected(planned,defect):
    root,local,ref,kwargs=planned('gqa')
    plan=json.loads(local.verify_artifact(ref).read_text())
    if defect=='scope': plan['cases'][0]['launches_per_call']['baseline']=1
    elif defect=='role_names': plan['cases'][0]['role_kernel_names']['baseline']=plan['cases'][0]['role_kernel_names']['baseline'][:1]
    elif defect=='source': (root/'candidate/op_kernel/kernel.asc').write_text('changed source')
    elif defect=='input': (root/'inputs/case_01/input.bin').write_bytes(b'changed input')
    elif defect=='producer': (root/'producer').write_text('changed producer')
    elif defect=='pmu': plan['profile']['kernels']=['gqa_qk_bf16']
    elif defect=='legacy': plan['task_protocol']='shared_buffer_msprof_task_window_v4'
    elif defect=='budget': plan['budget_seconds']=3601
    ref=local.register_json(plan)
    with pytest.raises(Exception): baseline.checked_plan(local,ref)


def test_real_completion_replay_rejects_claimed_passed_without_task_raw(planned,monkeypatch):
    root,local,ref,_=planned()
    plan=baseline.checked_plan(local,ref)
    job=json.loads(local.verify_artifact(plan['job_ref']).read_text())
    folder=Path(job['output_dir']);folder.mkdir()
    log=folder/'stdout.log';log.write_text('CPU dispatcher fixture, no process executed')
    execution={'schema_version':'1.0.0','kind':'aprof_execution_report','job':job,
        'status':'passed','exit_code':0,'error':None,'duration_seconds':8,
        'started_at':'1970-01-01T00:00:02Z','finished_at':'1970-01-01T00:00:10Z',
        'stdout':{'path':str(log),'sha256':local.register_artifact(log)},
        'stderr':{'path':str(log),'sha256':local.register_artifact(log)}}
    path=folder/'execution.json';path.write_text(json.dumps(execution));execution_ref=local.register_artifact(path)
    build_ref=local.register_json({'CPU':'mocked build identity only'})
    monkeypatch.setitem(sys.modules,'task_baseline_build',SimpleNamespace(checked_baseline_build=
        lambda *a,**kw:({}, {'started_at':2.1,'finished_at':3})))
    completion=local.register_json({'status':'passed','started_at':4,'finished_at':9})
    # This is the real selected runtime completion verifier, not a mocked valid result.
    with pytest.raises(ContractError,match='completion'):
        baseline.replay_baseline_task(local,plan_ref=ref,build_receipt_ref=build_ref,
            completion_ref=completion,execution_ref=execution_ref)
    execution['exit_code']=143;path.write_text(json.dumps(execution));execution_ref=local.register_artifact(path)
    with pytest.raises(ValueError,match='dispatcher exit'):
        baseline.replay_baseline_task(local,plan_ref=ref,build_receipt_ref=build_ref,
            completion_ref=completion,execution_ref=execution_ref)
