"""Level2 adapter contracts: source capture, output closure and measurement replay."""
import hashlib
import json
from pathlib import Path
import struct
import sys

import pytest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import level2_adapters as l2
from shared_context_build import generate_adapter, source_hash, validate_source_cmake
from cannbench_msprof_timing import instrument, parse_profile


@pytest.mark.parametrize('op',l2.OPERATORS)
def test_all_hosts_capture_source_tiling_and_defer_output(op):
    source=ROOT/'benchmarks/cannbench/operators'/op
    code,identity,original=generate_adapter(source,op,'A',source_hash(source))
    assert identity['operator_name']==op
    assert 's->kernel([=]()' in code
    assert 's->mapped(' in code
    assert 's->exporter=[=]' in code
    assert 's->mark_output(' in code
    assert 'level2::export_copy(' in code
    assert 'level2::write_output(""' in code
    assert (source/'op_host'/f'{op}.asc').read_text()==original
    assert validate_source_cmake(source,op,'dav-2201')['cmake_guard_version']=='level2_canonical_recipe_v1'
    if op=='softmax':
        export=code.split('s->exporter=[=]',1)[1]
        assert 'srcIndex' in export and 'dstIndex' in export
    if op=='scatter':assert 'level2::copy(' in code and 'ACL_MEMCPY_DEVICE_TO_DEVICE' in code
    if op=='unsorted_segment_sum':assert 'level2::zero(' in code


def test_bundle_roundtrip_is_named_and_readonly_replay_detects_corruption(tmp_path):
    path=tmp_path/'outputs.bin';chunks=[b'query-value',b'key-value']
    path.write_bytes(b''.join(struct.pack('<Q',len(v))+v for v in chunks))
    metadata={'query_out':'old-q','key_out':'old-k','shape':[1]}
    result=l2.output_metadata('apply_rotary_pos_emb',metadata,path)
    assert Path(result['query_out']).read_bytes()==chunks[0]
    before={p:p.read_bytes() for p in tmp_path.iterdir()}
    assert l2.verify_output_metadata('apply_rotary_pos_emb',metadata,path)==result
    assert before=={p:p.read_bytes() for p in tmp_path.iterdir()}
    Path(result['key_out']).write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='differs'):l2.verify_output_metadata('apply_rotary_pos_emb',metadata,path)


@pytest.mark.parametrize('payload',[b'',struct.pack('<Q',100)+b'bad',struct.pack('<Q',0)])
def test_malformed_bundle_fails(tmp_path,payload):
    p=tmp_path/'bad.bin';p.write_bytes(payload)
    with pytest.raises(ValueError):l2.output_metadata('cummin',{'values':'x','indices':'y'},p)


def test_launch_sequence_includes_real_branches_and_resets():
    root=ROOT/'benchmarks/cannbench/operators'
    for reduction,names in [('none',['cross_entropy_kernel']),('mean',['cross_entropy_reduce'])]:
        plan=l2.launch_contract('cross_entropy_loss',root/'cross_entropy_loss',{'reduction':reduction})
        assert plan['kernels']==names
    for dtype,reduce,count in [('float16','add',3),('float16','multiply',3),('float32','add',1),('float16',None,1)]:
        plan=l2.launch_contract('scatter',root/'scatter',{'data_dtype':dtype,'reduce':reduce})
        assert plan['launches_per_call']==count
        assert plan['required_auxiliary_tasks']==['device_to_device_copy']
    plan=l2.launch_contract('unsorted_segment_sum',root/'unsorted_segment_sum',{})
    assert plan['launches_per_call']==2 and plan['required_auxiliary_tasks']==['device_memset']


def test_long_case_repetition_is_frozen_without_changing_legacy_runner():
    text=(ROOT/'benchmarks/cannbench/harness/shared_context/runner.cpp').read_text()
    old=instrument(text,10)
    new=instrument(text,10,per_case=True)
    assert 'msprof_kernel_time_study_v1' in old and 'aprof_case_repeat' not in old
    assert 'msprof_kernel_time_study_v2' in new and 'aprof_case_repeat' in new
    assert 'double(ms)*1000000/aprof_case_repeat' in new
    assert l2.repeat_for_baseline_us(10_000)==10
    assert l2.repeat_for_baseline_us(10_001)==1
    with pytest.raises(ValueError):l2.repeat_for_baseline_us(float('nan'))


def test_adamw_input_directory_is_closed_over_concrete_files(tmp_path):
    for name in ('var','grad','m','v'):(tmp_path/(name+'.bin')).write_bytes(name.encode())
    paths=l2.input_paths({'input_dir':str(tmp_path),'output':str(tmp_path/'var.bin')})
    assert len(paths)==4
    (tmp_path/'m.bin').unlink()
    with pytest.raises(ValueError,match='missing AdamW'):l2.input_paths({'input_dir':str(tmp_path)})


def test_case_kernel_sequence_can_choose_one_of_multiple_entries(tmp_path):
    from test_cannbench_msprof_timing import fixture
    journal,build,cases,_,_=fixture(tmp_path)
    for r in 'AB':build['roles'][r]['kernel_symbols']+=','+r+'_unused'
    # Keep native module identity bound to the complete compiled entry set.
    rows=[json.loads(x) for x in journal.read_text().splitlines()]
    for row in rows:
        if row['type']=='module':row['kernel_symbols']=build['roles'][row['role']]['kernel_symbols']
        row['timing_protocol']='msprof_kernel_time_study_v2'
    journal.write_text(''.join(json.dumps(x)+'\n' for x in rows))
    cases[0].update(repeat=1,kernel_sequence={r:[r+'_kernel'] for r in 'AB'})
    _task_time_fixture(tmp_path)
    result=parse_profile(tmp_path,journal,build,cases,10)
    assert result['version']=='msprof_kernel_time_study_v2'
    assert len(result['samples'])==60 and result['samples'][0]['task_us']==5


def _task_time_fixture(directory, reset=None):
    import csv
    from test_cannbench_msprof_timing import write_csv
    records=list(csv.DictReader((directory/'op_summary.csv').open()))
    rows=[]
    for i,r in enumerate(records):
        start=float(r['Task Start Time(us)']);duration=float(r['Task Duration(us)'])
        if reset:rows.append({'Device_id':r['Device_id'],'kernel_name':'N/A','kernel_type':reset,'stream_id':r['Stream ID'],
           'task_id':'reset-'+str(i),'task_time(us)':'2','task_start(us)':str(start-3),'task_stop(us)':str(start-1)})
        rows.append({'Device_id':r['Device_id'],'kernel_name':r['Op Name'],'kernel_type':r['Task Type'],'stream_id':r['Stream ID'],
           'task_id':r['Task ID'],'task_time(us)':str(duration),'task_start(us)':str(start),'task_stop(us)':str(start+duration)})
    write_csv(directory/'task_time.csv',rows)
    return rows


@pytest.mark.parametrize('corruption',[None,'drop_reset','drop_compute','wrong_duration','wrong_stream','extra_task','undeclared_reset'])
def test_complete_call_sum_binds_dma_and_compute_tables(tmp_path,corruption):
    from test_cannbench_msprof_timing import fixture,write_csv
    jp,build,cases,_,_=fixture(tmp_path)
    cases[0]['required_auxiliary_tasks']={r:['device_to_device_copy'] for r in 'AB'}
    rows=_task_time_fixture(tmp_path,'MEMCPY_ASYNC')
    if corruption=='drop_reset':rows.pop(0)
    elif corruption=='drop_compute':rows.pop(1)
    elif corruption=='wrong_duration':rows[1]['task_time(us)']='4'
    elif corruption=='wrong_stream':rows[0]['stream_id']='7'
    elif corruption=='extra_task':rows[0]['kernel_type']='AI_CPU'
    elif corruption=='undeclared_reset':cases[0]['required_auxiliary_tasks']['B']=[]
    write_csv(tmp_path/'task_time.csv',rows)
    if corruption:
        with pytest.raises(ValueError):parse_profile(tmp_path,jp,build,cases,1)
    else:
        result=parse_profile(tmp_path,jp,build,cases,1)
        assert result['compute_tasks']==80 and result['auxiliary_tasks']==80
        assert result['warmup_tasks_excluded']==40
        assert result['samples'][0]['task_us']==7
        assert result['samples'][0]['core_us']==3
        assert result['samples'][0]['auxiliary_task_us']==2
        assert len(result['samples'][0]['csv_rows'])==len(result['samples'][0]['auxiliary_csv_rows'])==1


def test_metadata_dispatch_descriptor_has_semantics_not_case_identity():
    m={'case_id':17,'input_shapes':[[3,16],[16]],'dtype':'float16','seed':999,'numel':999999,'output_shape':[3,16]}
    d=l2.workload_metadata('maximum',m)
    assert d['attributes']['rhs_last_axis'] is True and d['attributes']['output_numel']==48
    assert 'case_id' not in d['attributes'] and 'seed' not in d['attributes'] and 'numel' not in d['attributes']
    d=l2.workload_metadata('cummin',{'shape':[3,16],'dtype':'float16','dim':-1})
    assert d['attributes']['dim']==1 and d['attributes']['inner']==1 and d['attributes']['aligned_rows']


def test_source_sibling_dispatch_is_bound_to_compiled_role(tmp_path):
    source=tmp_path/'source';source.mkdir()
    identity={'source_dir':str(source)}
    assert l2.verify_build_dispatch(identity)==[]
    path=tmp_path/'dispatch-launch.json';path.write_text('{}')
    with pytest.raises(ValueError,match='unbound'):l2.verify_build_dispatch(identity)
    identity['dispatch_contract']={'path':str(path),'sha256':'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()}
    assert l2.verify_build_dispatch(identity)==[path]
    path.write_text('{"changed":true}')
    with pytest.raises(ValueError,match='identity differs'):l2.verify_build_dispatch(identity)


def test_pilot_template_is_one_complete_call_with_event_and_reset_inside():
    import level2_pilot as pilot
    source=pilot.SOURCE.read_text()
    result=pilot.instrument(source)
    assert 'const unsigned warmup_target=1' in result and 'const unsigned call_target=1' in result
    assert result.index('aclrtRecordEvent(start,stream)')<result.index('call(api->launch(state));++profile_calls')<result.index('aclrtRecordEvent(end,stream)')
    assert 'level2_prepared_pilot_native_v1' in result


def test_dispatch_uses_metadata_and_requires_real_selected_entry(tmp_path):
    import shutil
    from test_planning import context_example
    source=tmp_path/'source';shutil.copytree(ROOT/'benchmarks/cannbench/operators/maximum',source)
    plan=context_example()['evidence']['dispatch_plan'];plan['operator']='maximum'
    plan['entries'][0]['kernel_entry']='maximum_kernel';plan['entries'][0]['required_capabilities']=[]
    plan['fallback']['kernel_entry']='maximum_kernel'
    data={'version':'level2_dispatch_launch_v1','source_sha256':source_hash(source),'dispatch_plan':plan,
          'sequences':{'1':{'kernels':['maximum_kernel']},'0':{'kernels':['maximum_kernel']}}}
    path=tmp_path/'dispatch-launch.json';path.write_text(json.dumps(data))
    small=l2.launch_contract('maximum',source,{'input_shapes':[[128],[128]],'dtype':'float32'})
    large=l2.launch_contract('maximum',source,{'input_shapes':[[129],[129]],'dtype':'float32'})
    assert small['expected_dispatch']['tiling_key']==1 and large['expected_dispatch']['tiling_key']==0
    data['sequences']['1']['kernels']=['missing_entry'];path.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='entry absent'):l2.launch_contract('maximum',source,{'input_shapes':[[128],[128]],'dtype':'float32'})


def test_native_dispatch_evidence_only_after_exact_csv_sequence(tmp_path):
    from test_cannbench_msprof_timing import fixture,write_csv
    jp,build,cases,path,rows=fixture(tmp_path)
    cases[0]['expected_dispatch']={r:{'tiling_key':8,'kernel_entry':r+'_kernel','group_id':'semantic','fallback':False} for r in 'AB'}
    cases[0]['kernel_sequence']={r:[r+'_kernel'] for r in 'AB'}
    result=parse_profile(tmp_path,jp,build,cases,1)
    assert result['samples'][0]['verified_dispatch']['captured_kernel_sequence']==['A_kernel']
    rows[20]['Op Name']='B_kernel';write_csv(path,rows)
    with pytest.raises(ValueError,match='sequence mismatch'):parse_profile(tmp_path,jp,build,cases,1)


def _uss_oracle_input(tmp_path):
    import numpy as np
    m={'case_id':1,'shape':[3,2],'dtype':'float32','id_dtype':'int32','num_segments':2}
    for name,array in [('data',np.array([1,2,3,4,5,6],np.float32)),('ids',np.array([0,1,0],np.int32)),('output',np.array([6,8,3,4],np.float32))]:
        path=tmp_path/(name+'.bin');array.tofile(path);m[name]=str(path)
    metadata=tmp_path/'metadata.json';metadata.write_text(json.dumps(m));return metadata


def test_uss_original_oracle_uses_recorded_identical_local_metadata(tmp_path):
    metadata=_uss_oracle_input(tmp_path)
    verifier=ROOT/'benchmarks/cannbench/operators/unsorted_segment_sum/scripts/verify_result.py'
    result=l2.reusable_verifier(verifier).run(metadata)
    assert result.returncode==0 and result.args[-1]!=str(metadata)
    info=result.oracle_relocation
    assert result.args[-1]==info['execution_metadata_path']
    assert not Path(info['execution_metadata_path']).exists()
    assert len(l2.verify_oracle_relocation(info,metadata,verifier))==2
    assert not (tmp_path/'expected.tmp').exists()
    (tmp_path/'executed-metadata.json').write_text('{}')
    with pytest.raises(ValueError,match='executed oracle metadata'):l2.verify_oracle_relocation(info,metadata,verifier)


def test_scoped_oracle_also_records_local_execution_argv(tmp_path):
    import os
    from msprof_exploration_oracle import ScopedOracle
    metadata=_uss_oracle_input(tmp_path);verifier=ROOT/'benchmarks/cannbench/operators/unsorted_segment_sum/scripts/verify_result.py'
    def delegate(*args,**kwargs):raise AssertionError('unchanged oracle should execute in the scoped loader')
    scope=ScopedOracle(delegate,verifier=verifier,expected_hash='sha256:'+hashlib.sha256(verifier.read_bytes()).hexdigest(),metadata_root=tmp_path)
    argv=[sys.executable,'-B',str(verifier),'--metadata',str(metadata)]
    result=scope(argv,tmp_path/'verify',dict(os.environ),10,cwd=tmp_path)
    record=json.loads((tmp_path/'verify.execution.json').read_text())
    assert result.returncode==0 and record['requested_argv']==argv
    assert record['argv'][-1]==record['oracle_relocation']['execution_metadata_path']!=str(metadata)
    l2.verify_oracle_relocation(record['oracle_relocation'],metadata,verifier)


def test_workflow_family_attributes_are_derived():
    q=l2.workload_metadata('dynamic_quant',{'shape':[2,3,17],'dtype':'float16'})['attributes']
    assert (q['row_length'],q['token_count'])==(17,6)
    g=l2.workload_metadata('group_norm',{'shape':[2,12,3,4],'dtype':'float32','num_groups':3})['attributes']
    assert (g['group_count'],g['group_elements'],g['channels_per_group'],g['spatial'])==(6,48,4,12)
    c=l2.workload_metadata('cross_entropy_loss',{'shape':[2,7,3,4],'dtype':'float32'})['attributes']
    assert (c['C'],c['positions'],c['inner'],c['gather_safe'])==(7,24,12,True)
    with pytest.raises(ValueError,match='divide groups'):l2.workload_metadata('group_norm',{'shape':[2,13,3,4],'dtype':'float32','num_groups':3})


def test_half_softmax_ub_reserves_float_reinterpret_scratch():
    a=l2.workload_metadata('softmax',{'shape':[2,12288],'dtype':'float16','dim':-1})['attributes']
    assert a['ub_bytes']==12*12288+16384+4096+32+1536+8192
