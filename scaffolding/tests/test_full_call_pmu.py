"""CPU evidence fixtures. Only the already-qualified Task boundary is stubbed."""
import csv
import importlib.util
import io
import json
from pathlib import Path
import statistics
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
from aprof_runtime import full_call_pmu as pmu, exploration, measurement_entry
from aprof_runtime.errors import ContractError, StoreError
from aprof_runtime.local_evidence import LocalEvidence


def csv_text(scope,role,capture=0,mutate=None):
    # Two QK occurrences deliberately differ: taking peak gives wrong result.
    values=[10,2,8,3,4,6,1] if role=='baseline' else [10,1,5,3,4,6,1]
    rows=[{'Op Name':name,'Task Start Time(us)':str(capture*100+i*3+1),
        'Task Duration(us)':'2','Task Type':'AI_CORE','Stream ID':'1','Task ID':str(i),
        'Device_id':'0','aicore_time(us)':str(values[i])}
        for i,name in enumerate(scope['role_kernel_names'][role])]
    if mutate:mutate(rows)
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    return stream.getvalue()


def basic_csv(scope,role):
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=['Op Name','Device Id','Current Freq','Rated Freq','Op Type'])
    writer.writeheader();writer.writerows({'Op Name':name,'Device Id':'0','Current Freq':'1000','Rated Freq':'1000','Op Type':'fixture'}
        for name in scope['role_kernel_names'][role])
    return stream.getvalue()


@pytest.fixture
def fixture(tmp_path,monkeypatch):
    local=LocalEvidence(tmp_path/'evidence'); counter=[0]
    def blob(value):
        counter[0]+=1;path=tmp_path/f'bytes-{counter[0]}'
        path.write_bytes(value if isinstance(value,bytes) else value.encode());return local.register_artifact(path)
    put=local.register_json
    sources={r:put({'schema_version':'1.0.0','files':{'op_kernel/kernel.asc':blob(r+' original kernel'),
        'scripts/verify_result.py':blob('original oracle')}}) for r in pmu.ROLES}
    source_dir='/task/assembly/source';binary='/task/assembly/build/gqa'
    binary_ref=blob('one combined binary');metadata_ref=put({'case_id':1,'shape':[2,2]});input_ref=blob('complete input')
    oracle_ref=blob('original adapted complete oracle')
    names={r:['aprof_'+r+'_'+n for n in ['gqa_reorder','gqa_qk_fp16','gqa_qk_fp16','gqa_softmax',
        'gqa_pv_fp16','gqa_pv_fp16','gqa_scatter']] for r in pmu.ROLES}
    outputs={r:['{cycle_dir}/'+r+'.bin'] for r in pmu.ROLES}
    case={'case_id':1,'workload':{'shape':[2,2],'dtype':'fp16'},'prepared_files':['/input/meta.json','/input/input.bin'],
        'command':[binary,'--input','/input/input.bin','--baseline-output',outputs['baseline'][0],
            '--candidate-output',outputs['candidate'][0]],'output_files':outputs,
        'verify_commands':{r:[pmu.SUMMARY_PYTHON,source_dir+'/oracle.py','--metadata','/input/meta.json',
            '--output',outputs[r][0],'--result','{cycle_dir}/'+r+'-result.json'] for r in pmu.ROLES}}
    config={'candidate_id':'candidate','operator':'gqa','run_id':'run','session_id':'session','device':0,'physical_device':0,
        'expected_case_ids':[1],'roles':{r:{'source_dir':'/task/'+r,'symbol':'launch_'+r,
            'launches_per_operator':{'1':7}} for r in pmu.ROLES},'cases':[case],
        'build':{'source_dir':source_dir,'binary':binary,'receipt_files':['/task/build.json']},
        'task_profile':{'profiler':pmu.TOOL,'scratch_root':'/task/profile',
            'role_kernel_names':{r:{'1':names[r]} for r in pmu.ROLES}}}
    job_ref=put({'timeout_seconds':3600})
    origin_ref=put({'job_ref':job_ref,'run_id':'run','source_hashes':sources,'deadline_monotonic':3700})
    attempt_ref=put({'plan_ref':origin_ref,'budget_seconds':3600,'created_at':-1})
    launch={'attempt_ref':attempt_ref,'started_at':0,'started_monotonic':100,'deadline_monotonic':3700,
        'issued_monotonic':100.1,'child_timeout_seconds':3599.9}
    # Compute the exact same subtraction as the actual dispatcher.
    launch['child_timeout_seconds']=launch['deadline_monotonic']-launch['issued_monotonic']
    launch_ref=put(launch)
    build_ref=put({'status':'passed','error':None,'binary':{'path':binary,'sha256':binary_ref}})
    build_window_ref=put({'schema_version':1,'kind':'reviewed_candidate_build','plan_ref':origin_ref,
        'receipt_ref':build_ref,'started_at':1,'finished_at':4,'started_monotonic':101,
        'finished_monotonic':104,'deadline_monotonic':3700})
    config_ref=put(config)
    tools={p:blob('frozen dependency '+p) for p in pmu.PROFILE_DEPENDENCY_PATHS}
    registration={'identity':{'source_hashes':sources,'build':{'binary_ref':binary_ref,
        'receipt_refs':{'/task/build.json':build_ref}},'cases':{'1':{'workload_ref':put(case['workload']),
        'prepared_files':{'/input/meta.json':metadata_ref,'/input/input.bin':input_ref},
        'verifier_files':{source_dir+'/oracle.py':oracle_ref}}}},
        'profile_dependency_refs':{p:tools[p] for p in pmu.TASK_DEPENDENCIES}}
    registration_ref=put(registration);measurement_ref=put({'stable':True})
    completion={'candidate_id':'candidate','source_hashes':sources,'measurement_report_ref':measurement_ref,
        'started_at':10,'finished_at':20}
    completion_ref=put(completion);calls=[]
    def task_boundary(reader,ref,*,expected):
        calls.append((ref,expected));assert ref==completion_ref
        saved=json.loads(reader.verify_artifact(ref).read_text())
        if any(saved.get(k)!=v for k,v in expected.items()):raise ContractError('Task expected identity differs')
        return {'valid':True,'config_ref':config_ref,'registration_ref':registration_ref,
            'hardware':{'npu_smi_ref':tools[pmu.NPU_SMI]}}
    monkeypatch.setattr(measurement_entry,'replay_current_measurement_admission',task_boundary)
    metrics={'aic_time':{'file':'op_summary*.csv','format':'csv','field':'aicore_time(us)',
        'unit':'us','row_aggregation':'median','aggregation':'median'}}
    scope=pmu._scope(config,1,metrics)
    plan={'schema_version':1,'kind':'full_call_pmu_plan','protocol':pmu.PROTOCOL,'candidate_id':'candidate',
        'config_ref':config_ref,'source_hashes':sources,'created_at':5,'deadline_monotonic':3700,
        'launch_ref':launch_ref,'build_window_ref':build_window_ref,'scope':scope,'selections':[{'name':'aic_time','kernel':'gqa_qk_fp16','unit':'us','expected_direction':'decrease'}],
        'toolchain_refs':tools}
    plan_ref=put(plan)
    capture={'schema_version':1,'protocol':pmu.PROTOCOL,'plan_ref':plan_ref,'measurement_admission_ref':completion_ref,
        'build_receipt_ref':build_ref,'scope':scope,'directory':'/task/pmu','started_at':21,'finished_at':100,
        'started_monotonic':121,'finished_monotonic':200,'deadline_monotonic':3700,
        'warmups':[],'captures':[],'status':'collected','error':None,'qualification_passed':False,
        'admission_authority':False,'archive_performed':False}
    wall=[21]
    def execution(argv,cwd,identity=None,stdout=''):
        wall[0]+=.1;start=wall[0];wall[0]+=.1
        value={'argv':argv,'cwd':cwd,'started_at':start,'ended_at':wall[0],'exit_code':0,'error':None,
            'environment':{},'pid':1000+int(wall[0]*10),'timeout_seconds':10,
            'stdout_hash':blob(stdout),'stderr_hash':blob('')}
        if identity:value['identity_checks']={'before':identity,'after':identity}
        return put(value)
    capture['capabilities_ref']=execution([pmu.TOOL,'--help'],'/task/assembly',stdout=' '.join(pmu.FLAGS))
    capture['hardware_ref']=execution([pmu.NPU_SMI,'info','-t','board','-i','0','-c','0'],'/task/assembly',stdout='9392')
    for role in pmu.ROLES:
        ident={'binary_hash':binary_ref,'tool_hash':tools[pmu.TOOL],'source_hash':sources[role]}
        for kind,count in [('warmups',10),('captures',5)]:
            for index in range(count):
                directory=Path('/task/pmu')/role/('warmup' if kind=='warmups' else 'capture')/str(index)
                expand=lambda values:[v.replace('{cycle_dir}',str(directory)) for v in values]
                command=expand(case['command'])+['--aprof-mechanism-role',role]
                item={'role':role,'index':index,'directory':str(directory),
                    'execution_ref':execution(command if kind=='warmups' else pmu.capture_argv(command,directory/'profile'),source_dir,ident)}
                if kind=='captures':
                    table_ref=blob(csv_text(scope,role,index))
                    item.update(table_ref=table_ref,profile_files_ref=put({'PROF_cpu/device_0/summary/op_summary_0.csv':table_ref,
                        'PROF_cpu/device_0/raw.data':blob('raw '+role+str(index)),
                        'PROF_cpu/device_0/summary/OpBasicInfo.csv':blob(basic_csv(scope,role))}),
                        output_refs={p:blob('complete output '+role+str(index)) for p in expand(case['output_files'][role])})
                    result={'case_id':1,'passed':True};result_ref=put(result)
                    item.update(oracle_result_ref=result_ref,oracle_execution_ref=execution(expand(case['verify_commands'][role]),source_dir,ident,json.dumps(result)))
                capture[kind].append(item)
    report={'schema_version':'1.0.0','kind':pmu.KIND,'protocol':pmu.PROTOCOL,'candidate_id':'candidate',
        'hypothesis_basis':'heuristic','plan_ref':plan_ref,'measurement_admission_ref':completion_ref,'capture_report_ref':put(capture)}
    evidence=SimpleNamespace(candidate_id='candidate',artifacts={'measurement_admission':completion_ref,
        'measurement_report':measurement_ref,'mechanism_plan':plan_ref,'task_launch':launch_ref,'build_window':build_window_ref})
    def seal(item):
        value=pmu.slot_receipt_value(local,item,plan_ref=report['plan_ref'],completion_ref=completion_ref,
            scope=scope,prepared_files=registration['identity']['cases']['1']['prepared_files'],
            outputs_before_oracle=item['output_refs'],outputs_after_oracle=item['output_refs'],
            finalized_at=json.loads(local.verify_artifact(item['oracle_execution_ref']).read_text())['ended_at'])
        item['slot_receipt_ref']=put(value)
    for item in capture['captures']:seal(item)
    def refresh():
        plan_ref=put(plan);report['plan_ref']=plan_ref;evidence.artifacts['mechanism_plan']=plan_ref;capture['plan_ref']=plan_ref
        report['capture_report_ref']=put(capture)
    def replay():refresh();return pmu.replay_full_call_mechanism(local,report,evidence=evidence,source_hashes=sources)
    def record(item,key,change):
        value=json.loads(local.verify_artifact(item[key]).read_text());change(value);item[key]=put(value)
    def csv_change(index,change):
        item=capture['captures'][index];item['table_ref']=blob(csv_text(scope,item['role'],item['index'],change))
        files=json.loads(local.verify_artifact(item['profile_files_ref']).read_text());files['PROF_cpu/device_0/summary/op_summary_0.csv']=item['table_ref']
        item['profile_files_ref']=put(files)
        seal(item)
    return SimpleNamespace(**locals())


def test_complete_roles_same_binary_all_occurrences(fixture):
    result=fixture.replay()
    assert result['valid'] and result['alignment'] is True
    assert result['metrics']['baseline']['aprof_baseline_gqa_qk_fp16']['aic_time']['median']==5
    assert result['metrics']['candidate']['aprof_candidate_gqa_qk_fp16']['aic_time']['median']==3
    assert result['partitions']['baseline'][0]['kernels']['aprof_baseline_gqa_qk_fp16']['positions']==[1,2]
    assert len(fixture.calls)==1
    assert fixture.sources['baseline']!=fixture.sources['candidate']


@pytest.mark.parametrize('mutation',[
    lambda r:r.pop(),lambda r:r.append(dict(r[-1])),
    lambda r:r[2].update(**{'Op Name':'aprof_baseline_gqa_softmax'}),
    lambda r:r[1].update(**{'Task Start Time(us)':'1.5'}),
    lambda r:r[1].update(**{'Stream ID':'2'}),
    lambda r:r[1].update(**{'Op Name':'aprof_candidate_gqa_qk_fp16'}),
    lambda r:r.__setitem__(slice(None),[row for row in r if 'qk' in row['Op Name']]),
])
def test_missing_extra_duplicate_reordered_overlap_wrong_role_or_only_selected_kernel_rejected(fixture,mutation):
    fixture.csv_change(0,mutation)
    with pytest.raises(ContractError):fixture.replay()


@pytest.mark.parametrize('cell',['N/A','nan','Infinity','-1'])
def test_nonfinite_or_unavailable_selected_occurrence_stays_unknown(fixture,cell):
    fixture.csv_change(0,lambda r:r[1].update(**{'aicore_time(us)':cell}))
    assert fixture.replay()['alignment'] is None


@pytest.mark.parametrize('mutation',[
    lambda f:f.capture['captures'].pop(),
    lambda f:f.capture['warmups'].pop(),
    lambda f:f.capture['captures'][1].update(execution_ref=f.capture['captures'][0]['execution_ref']),
    lambda f:f.capture['captures'][1].update(table_ref=f.capture['captures'][0]['table_ref'],profile_files_ref=f.capture['captures'][0]['profile_files_ref']),
    lambda f:f.capture.update(started_at=19),
    lambda f:f.plan.update(created_at=11),
    lambda f:f.capture.update(deadline_monotonic=3701),
    lambda f:f.capture['captures'][0].update(build_receipt_ref='unexpected'),
    lambda f:f.capture['captures'][0].update(output_refs={}),
    lambda f:f.plan['scope']['role_kernel_names']['baseline'].pop(),
    lambda f:f.plan['scope']['metrics']['aic_time'].update(field='Task Duration(us)'),
    lambda f:f.plan['scope']['metrics']['aic_time'].update(unit='ratio'),
    lambda f:f.plan['selections'][0].update(kernel='unknown'),
    lambda f:f.plan['toolchain_refs'].update({pmu.TOOL:f.blob('different SDK')}),
])
def test_binding_count_window_metric_and_reuse_fail_closed(fixture,mutation):
    mutation(fixture)
    with pytest.raises(ContractError):fixture.replay()


@pytest.mark.parametrize('mutation',[
    lambda r:r.update(exit_code=1),lambda r:r.update(started_at=19),lambda r:r.update(timeout_seconds=3600),
    lambda r:r['argv'].__setitem__(-1,r['argv'][-1].replace('baseline','candidate')),
    lambda r:r['identity_checks']['before'].update(source_hash='sha256:'+'f'*64),
    lambda r:r['identity_checks']['after'].update(binary_hash='sha256:'+'f'*64),
])
def test_actual_capture_execution_and_identity_not_summary_flags(fixture,mutation):
    fixture.record(fixture.capture['captures'][0],'execution_ref',mutation)
    with pytest.raises(ContractError):fixture.replay()


def test_all_raw_refs_and_source_files_are_required(fixture):
    reference=fixture.capture['captures'][0]['profile_files_ref']
    files=json.loads(fixture.local.verify_artifact(reference).read_text())
    files['PROF_cpu/device_0/raw.data']='sha256:'+'f'*64
    fixture.capture['captures'][0]['profile_files_ref']=fixture.put(files)
    with pytest.raises((ContractError,StoreError)):fixture.replay()


def test_source_bytes_tamper_rejected(fixture):
    bundle=json.loads(fixture.local.verify_artifact(fixture.sources['candidate']).read_text())
    fixture.local.verify_artifact(bundle['files']['op_kernel/kernel.asc']).write_text('changed')
    with pytest.raises((ContractError,StoreError)):fixture.replay()


def test_original_oracle_stdout_and_result_must_agree(fixture):
    fixture.capture['captures'][0]['oracle_result_ref']=fixture.put({'case_id':1,'passed':False})
    with pytest.raises(ContractError):fixture.replay()


def test_sample_cv_exact_frozen_rule():
    values=[93.5,96.75,100.,103.25,106.5]
    assert statistics.pstdev(values)/statistics.fmean(values)<.05
    assert not pmu._capture_statistics(values)['stable']
    assert pmu._capture_statistics([0.]*5)['stable']
    assert pmu._capture_statistics([-2.,-1.,0.,1.,2.])['status']=='unknown'




def test_applied_runtime_dispatch_calls_full_replay(fixture):
    fixture.refresh();fixture.evidence.artifacts['mechanism_report']=fixture.put(fixture.report)
    assert exploration.mechanism_alignment_from_artifacts(fixture.evidence,fixture.local,
        source_hashes=fixture.sources,require_v11=True) is True


def test_unstable_selected_five_capture_metric_stays_unknown(fixture):
    for i,value in enumerate([1,2,3,4,5]):
        fixture.csv_change(i,lambda rows,value=value:[r.update(**{'aicore_time(us)':str(value)}) for r in rows if 'qk' in r['Op Name']])
    assert fixture.replay()['alignment'] is None


def test_unknown_unselected_metric_is_retained_without_invented_support(fixture):
    fixture.csv_change(0,lambda rows:rows[0].update(**{'aicore_time(us)':'N/A'}))
    result=fixture.replay()
    assert result['alignment'] is True
    assert result['metrics']['baseline']['aprof_baseline_gqa_reorder']['aic_time']=={'status':'unknown'}


def test_direction_preserved_and_no_authority_from_collector_summary(fixture):
    fixture.plan['selections'][0]['expected_direction']='increase'
    fixture.refresh()
    for item in fixture.capture['captures']:fixture.seal(item)
    assert fixture.replay()['alignment'] is False
    fixture.capture['admission_authority']=True
    with pytest.raises(ContractError):fixture.replay()


def test_original_oracle_command_cannot_be_replaced_by_passed_result(fixture):
    fixture.record(fixture.capture['captures'][0],'oracle_execution_ref',lambda r:r['argv'].__setitem__(1,'/fake/oracle.py'))
    with pytest.raises(ContractError):fixture.replay()


def test_task_expected_role_identity_is_not_a_passed_boolean(fixture):
    wrong=dict(fixture.sources);wrong['candidate']=wrong['baseline']
    with pytest.raises(ContractError,match='Task expected identity'):
        pmu.replay_full_call_mechanism(fixture.local,fixture.report,evidence=fixture.evidence,source_hashes=wrong)


def test_expired_profile_window_and_execution_timeout_rejected(fixture):
    fixture.capture['finished_at']=4000
    with pytest.raises(ContractError):fixture.replay()
    fixture.capture['finished_at']=100
    fixture.record(fixture.capture['captures'][0],'execution_ref',lambda r:r.update(timeout_seconds=.01))
    with pytest.raises(ContractError):fixture.replay()




def test_raw_map_and_output_swap_rejected_by_finalized_slot(fixture):
    item=fixture.capture['captures'][0]
    before=item['output_refs']
    item['output_refs']={name:fixture.blob('different bytes, same passed oracle') for name in before}
    with pytest.raises(ContractError,match='finalized capture'):fixture.replay()
    item['output_refs']=before
    files=json.loads(fixture.local.verify_artifact(item['profile_files_ref']).read_text())
    files['PROF_cpu/device_0/raw.data']=fixture.blob('different raw export')
    item['profile_files_ref']=fixture.put(files)
    with pytest.raises(ContractError,match='finalized capture'):fixture.replay()


def test_oracle_actual_input_before_and_output_after_must_match(fixture):
    item=fixture.capture['captures'][0]
    sealed=json.loads(fixture.local.verify_artifact(item['slot_receipt_ref']).read_text())
    sealed['outputs_before_oracle']={name:fixture.blob('different bytes consumed') for name in item['output_refs']}
    item['slot_receipt_ref']=fixture.put(sealed)
    with pytest.raises(ContractError,match='finalized capture'):fixture.replay()


def test_resetting_both_pmu_plan_and_report_deadline_cannot_reset_dispatcher(fixture):
    fixture.plan['deadline_monotonic']+=3600;fixture.capture['deadline_monotonic']+=3600
    with pytest.raises(ContractError,match='original registered dispatcher'):fixture.replay()


def test_alternate_original_launch_cannot_replace_actual_build_window(fixture):
    newer=dict(fixture.launch,started_at=10,started_monotonic=110,deadline_monotonic=3710,issued_monotonic=110.1)
    newer['child_timeout_seconds']=newer['deadline_monotonic']-newer['issued_monotonic']
    ref=fixture.put(newer);fixture.plan['launch_ref']=ref;fixture.evidence.artifacts['task_launch']=ref
    fixture.plan['deadline_monotonic']=fixture.capture['deadline_monotonic']=3710
    with pytest.raises(ContractError,match='build did not use'):fixture.replay()


def test_no_raw_frequency_basis_means_unknown(fixture):
    item=fixture.capture['captures'][0]
    files=json.loads(fixture.local.verify_artifact(item['profile_files_ref']).read_text())
    del files['PROF_cpu/device_0/summary/OpBasicInfo.csv'];item['profile_files_ref']=fixture.put(files);fixture.seal(item)
    assert fixture.replay()['alignment'] is None


@pytest.mark.parametrize('frequency',['NaN','900'])
def test_present_raw_frequency_invalid_or_changed_is_not_ignored(fixture,frequency):
    item=fixture.capture['captures'][0]
    files=json.loads(fixture.local.verify_artifact(item['profile_files_ref']).read_text())
    raw=basic_csv(fixture.scope,'baseline').replace('1000,1000',frequency+',1000')
    files['PROF_cpu/device_0/summary/OpBasicInfo.csv']=fixture.blob(raw)
    item['profile_files_ref']=fixture.put(files);fixture.seal(item)
    with pytest.raises(ContractError,match='frequency'):fixture.replay()




def test_gate_evidence_artifact_map_accepts_bound_join_keys(fixture):
    from aprof_runtime.contracts import GateEvidence
    value={'candidate_id':'candidate',**{key:'passed' for key in ('static_review','build','accuracy','runtime','semantic','scope','portability')},
        'artifacts':fixture.evidence.artifacts}
    assert GateEvidence.from_dict(value).artifacts['task_launch']==fixture.launch_ref


def test_actual_supervisor_nested_path_hash_pointers(fixture):
    pointer=lambda ref:{'path':str(fixture.local.verify_artifact(ref)),'sha256':ref}
    origin=json.loads(fixture.local.verify_artifact(fixture.origin_ref).read_text())
    origin['job_ref']=pointer(origin['job_ref']);origin_ref=fixture.put(origin)
    attempt=json.loads(fixture.local.verify_artifact(fixture.attempt_ref).read_text())
    attempt['plan_ref']=pointer(origin_ref);attempt_ref=fixture.put(attempt)
    launch=dict(fixture.launch,attempt_ref=pointer(attempt_ref));launch_ref=fixture.put(launch)
    fixture.plan['launch_ref']=launch_ref;fixture.evidence.artifacts['task_launch']=launch_ref
    fixture.refresh()
    for item in fixture.capture['captures']:fixture.seal(item)
    assert fixture.replay()['alignment'] is True
    launch['attempt_ref']={'path':'../wrong','sha256':attempt_ref};launch_ref=fixture.put(launch)
    fixture.plan['launch_ref']=launch_ref;fixture.evidence.artifacts['task_launch']=launch_ref
    with pytest.raises(ContractError,match='pointer path'):fixture.replay()


def test_applied_collector_and_runtime_producer_closure_matches():
    from aprof_runtime import task_window_measurement_admission as runtime
    release=Path(pmu.__file__).resolve().parents[3]
    spec=importlib.util.spec_from_file_location('full_pmu_closure_collector',
        release/'skills/ascendc-aprof-profiling/scripts/device_task_window_timing.py')
    collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
    assert set(collector.PRODUCER_FILES)==set(runtime.PRODUCER_FILES)
    name='runtime/src/aprof_runtime/full_call_pmu.py'
    for files in (collector.PRODUCER_FILES,runtime.PRODUCER_FILES):
        assert files.count(name)==1
        assert files[files.index(name)-1]=='runtime/src/aprof_runtime/exploration.py'
        assert all((release/path).is_file() for path in files)
    import task_baseline_pmu
    assert task_baseline_pmu.partition_call is pmu.partition_call
    assert task_baseline_pmu._capture_statistics is pmu._capture_statistics
