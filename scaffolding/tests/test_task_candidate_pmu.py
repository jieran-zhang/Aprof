"""Candidate glue on CPU; Task qualification and process execution are explicit doubles."""
import contextlib
import json
from pathlib import Path
import shlex
from types import SimpleNamespace

import pytest

from aprof_runtime import full_call_pmu as runtime, measurement_entry
from aprof_runtime.errors import ContractError
from aprof_runtime.jsonio import file_hash
from aprof_runtime.local_evidence import LocalEvidence
import task_candidate_pmu as glue
from test_full_call_pmu import csv_text
from test_task_baseline_build import Clock


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    local = LocalEvidence(tmp_path/'records'); clock = Clock()
    for module in (glue, glue.collector, glue.bridge): monkeypatch.setattr(module, 'time', clock)
    monkeypatch.setenv('ASCEND_RT_VISIBLE_DEVICES', '0')
    monkeypatch.setattr(glue.bridge.timing.shared, 'device_lock', lambda *a:contextlib.nullcontext())
    def blob(name, data):
        path=tmp_path/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(data)
        return local.register_artifact(path)
    roles={r:{'path':str(tmp_path/r)} for r in runtime.ROLES}
    sources={}
    for role in roles:
        sources[role]=local.register_json({'schema_version':'1.0.0','files':{
            'kernel.asc':blob(role+'/kernel.asc',role+' original kernel')}})
    assembly=tmp_path/'assembly';(assembly/'source').mkdir(parents=True)
    binary=assembly/'build/gqa';binary_ref=blob('assembly/build/gqa','CPU combined binary')
    oracle=assembly/'source/oracle.py';oracle_ref=blob('assembly/source/oracle.py','CPU oracle boundary')
    metadata=tmp_path/'metadata.json';metadata_ref=blob('metadata.json','{"case_id":1}')
    input_path=tmp_path/'input.bin';input_ref=blob('input.bin','complete input')
    tools={p:blob('tools/'+str(i),'SDK '+p) for i,p in enumerate(runtime.PROFILE_DEPENDENCY_PATHS)}
    stems=['gqa_reorder','gqa_qk_fp16','gqa_qk_fp16','gqa_softmax','gqa_pv_fp16','gqa_pv_fp16','gqa_scatter']
    names={r:['aprof_'+r+'_'+s for s in stems] for r in roles}
    outputs={r:['{cycle_dir}/'+r+'.bin'] for r in roles}
    case=dict(case_id=1,workload={'shape':[2,2],'dtype':'fp16'},prepared_files=[str(metadata),str(input_path)],
        command=[str(binary),'--input',str(input_path),'--baseline-output',outputs['baseline'][0],
                 '--candidate-output',outputs['candidate'][0]],output_files=outputs,
        verify_commands={r:['cpu-oracle',str(oracle),'--metadata',str(metadata),'--output',outputs[r][0],
                           '--result','{cycle_dir}/'+r+'-result.json'] for r in roles})
    config=dict(operator='gqa',run_id='run',session_id='session',candidate_id='candidate',device=0,physical_device=0,
        expected_case_ids=[1],roles={r:dict(source_dir=roles[r]['path'],symbol='launch_'+r,
            launches_per_operator={'1':7}) for r in roles},cases=[case],
        build=dict(source_dir=str(assembly/'source'),binary=str(binary),receipt_files=[str(assembly/'build-receipt.json')]),
        task_profile=dict(profiler=runtime.TOOL,scratch_root=str(tmp_path/'profile'),
            role_kernel_names={r:{'1':names[r]} for r in roles}))
    launch=dict(attempt_ref=local.register_json(dict(plan_ref=local.register_json(dict(run_id='run',
        job_ref=local.register_json({'timeout_seconds':3600}))),budget_seconds=3600,created_at=clock.time())),
        started_at=clock.time(),started_monotonic=clock.monotonic(),deadline_monotonic=clock.monotonic()+3600,
        issued_monotonic=clock.monotonic(),child_timeout_seconds=3600)
    launch_ref=local.register_json(launch);clock.elapsed+=1
    metrics={'aic_time':dict(file='op_summary*.csv',format='csv',field='aicore_time(us)',unit='us',
                            row_aggregation='median',aggregation='median')}
    candidate_plan=dict(candidate_id='candidate',source_hashes=sources,assembly_dir=str(assembly),
        physical_device=0,roles=roles,toolchain_refs=tools,profile=dict(case_id=1,metrics=metrics),
        deadline_monotonic=launch['deadline_monotonic'],launch_ref=launch_ref,
        cases=[dict(metadata_path=str(metadata),metadata_ref=metadata_ref,input_files={str(input_path):input_ref})])
    candidate_plan_ref=local.register_json(candidate_plan)
    native_ref=local.register_json(dict(status='passed',error=None,binary={'path':str(binary),'sha256':binary_ref}))
    wrapper=dict(kind='reviewed_candidate_build',plan_ref=candidate_plan_ref,receipt_ref=native_ref,
        started_at=clock.time(),finished_at=clock.time()+1,started_monotonic=clock.monotonic(),
        finished_monotonic=clock.monotonic()+1,deadline_monotonic=launch['deadline_monotonic'])
    build_ref=local.register_json(wrapper);clock.elapsed+=2
    build=dict(binary={'path':str(binary),'sha256':binary_ref},finished_at=wrapper['finished_at'],
               deadline_monotonic=launch['deadline_monotonic'])
    def candidate_boundary(reader, plan_ref, receipt_ref):
        assert reader is local and plan_ref==candidate_plan_ref and receipt_ref==build_ref
        return candidate_plan,build,config,native_ref
    monkeypatch.setattr(glue,'_candidate',candidate_boundary)
    selections=[dict(name='aic_time',kernel='gqa_qk_fp16',unit='us',expected_direction='decrease')]
    plan_ref=glue.prepare_candidate_pmu_plan(local,candidate_plan_ref=candidate_plan_ref,
        build_receipt_ref=build_ref,selections=selections,destination=tmp_path/'pmu-plan')
    plan=json.loads(local.verify_artifact(plan_ref).read_text())
    registration=dict(identity=dict(source_hashes=sources,build=dict(binary_ref=binary_ref,
        receipt_refs={str(assembly/'build-receipt.json'):native_ref}),cases={'1':dict(workload_ref=local.register_json(case['workload']),
        prepared_files={str(metadata):metadata_ref,str(input_path):input_ref},verifier_files={str(oracle):oracle_ref})}),
        profile_dependency_refs={p:tools[p] for p in runtime.TASK_DEPENDENCIES})
    registration_ref=local.register_json(registration)
    clock.elapsed+=1;completion=dict(**{k:config[k] for k in ('operator','run_id','session_id','candidate_id')},
        source_hashes=sources,measurement_report_ref=local.register_json({'CPU':'formal Task boundary'}),
        started_at=clock.time(),finished_at=clock.time()+1)
    completion_ref=local.register_json(completion);clock.elapsed+=2
    task_calls=[]
    def task_boundary(reader, ref, *, expected):
        task_calls.append((ref,expected));assert reader is local and ref==completion_ref
        if any(completion.get(k)!=v for k,v in expected.items()):raise ContractError('Task expected identity differs')
        return dict(valid=True,config_ref=plan['config_ref'],registration_ref=registration_ref,
                    hardware={'npu_smi_ref':tools[runtime.NPU_SMI]})
    monkeypatch.setattr(glue,'replay_current_measurement_admission',task_boundary)
    monkeypatch.setattr(measurement_entry,'replay_current_measurement_admission',task_boundary)
    calls=[];mutations={}
    def run(argv,cwd,prefix,timeout,reader,binding=None,*,environment):
        calls.append(argv);started=clock.time();stdout='CPU\n'
        if '--help' in argv:stdout=' '.join(runtime.FLAGS)
        elif argv[0]==runtime.NPU_SMI:stdout='Ascend910_9392'
        elif argv[0]=='cpu-oracle':
            output=Path(argv[argv.index('--output')+1]);assert output.read_text()=='complete output'
            result=dict(case_id=1,passed=True,max_abs_error=float('nan'))
            Path(argv[argv.index('--result')+1]).write_text(json.dumps(result));stdout=json.dumps(result)
            if mutations.get('oracle_output'):output.write_text('changed by oracle')
        else:
            is_profile=argv[0]==runtime.TOOL
            command=shlex.split(argv[-1].split('=',1)[1]) if is_profile else argv
            role=command[-1];Path(command[command.index('--'+role+'-output')+1]).write_text('complete output')
            if is_profile:
                directory=Path(argv[1].split('=',1)[1])/'PROF_cpu/device_0/summary';directory.mkdir(parents=True)
                table=csv_text(plan['scope'],role,len(calls),lambda rows:rows.pop() if mutations.get('omit') else None)
                (directory/'op_summary_0.csv').write_text(table);(directory/'raw.data').write_text('raw '+str(len(calls)))
        clock.elapsed+=.01
        record=dict(argv=argv,cwd=str(cwd),started_at=started,ended_at=clock.time(),pid=100+len(calls),
            exit_code=0,error=None,environment=environment,timeout_seconds=timeout)
        for key,text in [('stdout',stdout),('stderr','')]:
            path=Path(str(prefix)+'.'+key+'.log');path.write_text(text);record[key+'_hash']=local.register_artifact(path)
        if binding is not None:record['identity_checks']={k:dict(binding['expected']) for k in ('before','after')}
        return {**record,'log_hash':local.register_json(record)}
    monkeypatch.setattr(glue.bridge.profile_capture,'run',run)
    def collect():
        return glue.collect_candidate_pmu(local,plan_ref=plan_ref,completion_ref=completion_ref,
            destination=tmp_path/'capture',deadline=launch['deadline_monotonic'])
    return SimpleNamespace(**locals())


def test_actual_shared_collector_real_runtime_unknown_and_complete_slots(fixture):
    f=fixture;result=f.collect()
    assert result['replay']['valid'] and result['replay']['alignment'] is None
    assert len(f.calls)==42 and len(f.task_calls)==2
    assert not result['admission_authority'] and not result['archive_performed']
    assert result['replay']['partitions']['baseline'][0]['kernels']['aprof_baseline_gqa_qk_fp16']['positions']==[1,2]
    assert len(list((f.tmp_path/'capture').glob('*/capture/*/slot-receipt.json')))==10
    raw=f.tmp_path/'capture/baseline/capture/0/profile/PROF_cpu/device_0/summary/raw.data'
    assert raw.is_file() and not list(f.tmp_path.rglob('*.sqlite'))
    for role in runtime.ROLES:
        captures=[x for x in f.calls if x[0]==runtime.TOOL and '--application=' in x[-1] and x[-1].endswith(role)]
        assert len(captures)==5 and all('launch-count' not in ' '.join(x) for x in captures)


@pytest.mark.parametrize('mutation',['omit','oracle_output'])
def test_bad_full_callback_or_mutating_oracle_stops_capture(fixture,mutation):
    f=fixture;f.mutations[mutation]=True
    with pytest.raises(ValueError):f.collect()
    report=json.loads((f.tmp_path/'capture/pmu-report.json').read_text())
    assert report['status']=='failed' and report['error'] and len(report['captures'])==1
    assert not (f.tmp_path/'capture/mechanism-report.json').exists()


def test_reset_deadline_or_late_plan_rejected_before_capture(fixture):
    f=fixture
    with pytest.raises(ValueError,match='reset'):
        glue.collect_candidate_pmu(f.local,plan_ref=f.plan_ref,completion_ref=f.completion_ref,
            destination=f.tmp_path/'reset',deadline=f.launch['deadline_monotonic']+1)
    late=dict(f.plan,created_at=f.completion['finished_at'])
    with pytest.raises(ValueError,match='preregistered'):
        glue.collect_candidate_pmu(f.local,plan_ref=f.local.register_json(late),completion_ref=f.completion_ref,
            destination=f.tmp_path/'late',deadline=f.launch['deadline_monotonic'])
    assert not f.calls


def test_runtime_rejects_aggregate_output_swap(fixture):
    f=fixture;result=f.collect();report=json.loads(f.local.verify_artifact(result['mechanism_report_ref']).read_text())
    capture=json.loads(f.local.verify_artifact(result['capture_report_ref']).read_text())
    item=capture['captures'][0];item['output_refs']={path:f.input_ref for path in item['output_refs']}
    report['capture_report_ref']=f.local.register_json(capture)
    with pytest.raises(ContractError,match='finalized capture'):
        glue.verify_candidate_pmu(f.local,plan_ref=f.plan_ref,completion_ref=f.completion_ref,
                                 report_ref=f.local.register_json(report))


def test_real_reviewed_candidate_preparation_binds_same_formal_config(tmp_path,monkeypatch):
    from test_task_validation_controller import candidate_setup,build_candidate
    f=candidate_setup(tmp_path,monkeypatch,'gqa');built=build_candidate(f);local=f['local']
    monkeypatch.setattr(glue,'time',f['clock'])
    original=json.loads(local.verify_artifact(f['plan_ref']).read_text())
    # The existing build fixture uses two harmless toolchain placeholders.
    monkeypatch.setattr(glue,'PROFILE_DEPENDENCY_PATHS',tuple(original['toolchain_refs']))
    reference=glue.prepare_candidate_pmu_plan(local,candidate_plan_ref=f['plan_ref'],
        build_receipt_ref=built['build_receipt_ref'],destination=tmp_path/'pmu-plan',
        selections=[dict(name='aic_time',kernel='gqa_qk_fp16',unit='us',expected_direction='decrease')])
    value=json.loads(local.verify_artifact(reference).read_text())
    config=glue.candidate.candidate_task_config(local,plan_ref=f['plan_ref'],build_receipt_ref=built['build_receipt_ref'])
    glue.bridge.timing.old.save(tmp_path/'formal-config.json',config)
    assert file_hash(tmp_path/'formal-config.json')==value['config_ref']
    assert len(config['cases'])==20 and f['commands'].calls==['configure','build']
    assert value['source_hashes']['baseline']!=value['source_hashes']['candidate']
    assert str(Path(glue.__file__).resolve()) in original['producer_refs']
    assert str(Path(glue.collector.__file__).resolve()) in original['producer_refs']
    glue._checked_plan(local,reference)
    source=f['workspace']/'candidate/op_kernel/gqa_kernel.asc'
    source.write_bytes(source.read_bytes()+b'\n// changed after PMU registration\n')
    with pytest.raises((ValueError,RuntimeError)):
        glue._checked_plan(local,reference)
