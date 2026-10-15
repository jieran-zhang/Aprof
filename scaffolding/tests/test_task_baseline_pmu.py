"""Full occurrence replay with explicit CPU process doubles, never hardware proof."""
import contextlib
import copy
import csv
import io
import json
from pathlib import Path
import shlex
import statistics
import time

import pytest

import task_baseline_pmu as pmu
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.jsonio import content_hash


def test_sample_cv_preserves_frozen_five_capture_threshold():
    values=[93.5,96.75,100.,103.25,106.5]
    assert statistics.pstdev(values)/statistics.fmean(values)<.05
    result=pmu._capture_statistics(values)
    assert result['cv']==statistics.stdev(values)/abs(statistics.fmean(values))>.05
    assert not result['stable']


def test_zero_mean_with_variance_is_unknown_and_unstable():
    result=pmu._capture_statistics([-2.,-1.,0.,1.,2.])
    assert result['cv'] is None and result['status']=='unknown' and not result['stable']
    assert pmu._capture_statistics([0.]*pmu.MIN_CAPTURES)['cv']==0
    assert pmu._capture_statistics([0.]*pmu.MIN_CAPTURES)['stable']


def scope(operator='gqa'):
    stems = ['gqa_reorder', 'gqa_qk_fp16', 'gqa_qk_fp16', 'gqa_softmax',
             'gqa_pv_fp16', 'gqa_pv_fp16', 'gqa_scatter'] if operator=='gqa' else [operator+'_kernel']
    names = {r:['aprof_'+r+'_'+name for name in stems] for r in pmu.ROLES}
    return dict(protocol=pmu.PROTOCOL,case_id=1,device=0,role_kernel_names=names,
        launches_per_call={r:len(stems) for r in pmu.ROLES},warmups=10,captures=5,flags=list(pmu.FLAGS),
        metrics={'aic_time':{'field':'aicore_time(us)','unit':'us','file':'op_summary*.csv',
                            'format':'csv','row_aggregation':'median','aggregation':'median'}},
        occurrence_scope='all_ordered_tasks_in_one_complete_callback',within_kernel='median_of_all_occurrences',
        across_captures='median',maximum_cv=.05)


def table(scope,role='baseline',change=None):
    rows=[{'Op Name':name,'Task Start Time(us)':str(i*3+1),'Task Duration(us)':'2',
        'Task Type':'AI_CORE','Stream ID':'1','Task ID':str(i),'Device_id':'0','aicore_time(us)':str(i+1)}
        for i,name in enumerate(scope['role_kernel_names'][role])]
    if change:change(rows)
    stream=io.StringIO();writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows)
    return stream.getvalue()


def test_all_repeated_occurrences_and_row_identities_survive():
    expected=scope();result=pmu.partition_call(table(expected),scope=expected,role='baseline')
    assert result['task_count']==7 and result['pmu_complete']
    qk=result['kernels']['aprof_baseline_gqa_qk_fp16']
    assert qk['positions']==[1,2] and qk['count']==2
    assert qk['metrics']['aic_time']['median_decimal']=='2.5'
    assert [r['metrics']['aic_time']['value_decimal'] for r in result['occurrences']]==list(map(str,range(1,8)))


@pytest.mark.parametrize('mutation',[
    lambda r:r.pop(), lambda r:r.append(dict(r[-1])),
    lambda r:r[2].update(**{'Op Name':'aprof_baseline_gqa_softmax'}),
    lambda r:r[1].update(**{'Task Type':'MIX_AIC'}),
    lambda r:r[1].update(**{'Task Start Time(us)':'1.5'}),
    lambda r:r[1].update(**{'Stream ID':'2'}),
    lambda r:r[1].update(**{'Op Name':'aprof_candidate_gqa_qk_fp16'}),
])
def test_partial_duplicate_reordered_overlap_mix_or_wrong_role_rejected(mutation):
    expected=scope()
    with pytest.raises(ValueError):pmu.partition_call(table(expected,change=mutation),scope=expected,role='baseline')


@pytest.mark.parametrize('cell',[None,'','N/A','nan','Infinity','-1'])
def test_missing_pmu_is_unknown_never_task_duration(cell):
    expected=scope()
    def change(rows):
        for row in rows:
            if cell is None:row.pop('aicore_time(us)')
            else:row['aicore_time(us)']=cell
    result=pmu.partition_call(table(expected,change=change),scope=expected,role='baseline')
    assert not result['pmu_complete']
    assert all(row['metrics']['aic_time']['status']=='unknown' for row in result['occurrences'])


@pytest.mark.parametrize('forbidden',['Task Duration(us)','Block Num','Model ID','total_cycles'])
def test_whole_app_argv_has_no_task_truncation(forbidden):
    argv=pmu.capture_argv(['/binary','--aprof-mechanism-role','baseline'],Path('/tmp/raw'))
    assert 'op' not in argv and not any('launch-count' in item for item in argv)
    assert '--aic-mode=task-based' in argv and '--aic-metrics=PipeUtilization' in argv
    expected=scope();expected['metrics']['aic_time']['field']=forbidden
    with pytest.raises(ValueError,match='PMU columns'):
        pmu.scope_from_plan(dict(cases=[dict(case_id=1,**{k:expected[k] for k in ('role_kernel_names','launches_per_call')})],
            profile=dict(case_id=1,metrics=expected['metrics']),device=0))


def test_local_capture_replay_and_full_raw_tamper(tmp_path,monkeypatch):
    local=LocalEvidence(tmp_path/'records');expected=scope()
    tool=tmp_path/'msprof';tool.write_text('CPU fixture tool')
    binary=tmp_path/'binary';binary.write_text('CPU fixture complete callback')
    source=tmp_path/'source';source.mkdir();(source/'kernel.asc').write_text('CPU source')
    source_ref=content_hash({'schema_version':'1.0.0','files':pmu.bridge.profile_capture.source_inventory(source)})
    metadata=tmp_path/'metadata.json';metadata.write_text(json.dumps({'case_id':1}))
    prepared=tmp_path/'input.bin';prepared.write_bytes(b'CPU input')
    plan=dict(assembly_dir=str(tmp_path),physical_device=0,pmu_scope=expected,
        cases=[dict(metadata_path=str(metadata),metadata_ref=local.register_artifact(metadata),
                    input_files={str(prepared):local.register_artifact(prepared)})],
        roles={r:{'path':str(source)} for r in pmu.ROLES},source_hashes={r:source_ref for r in pmu.ROLES},
        toolchain_refs={str(tool):local.register_artifact(tool)})
    deadline=time.monotonic()+120
    build=dict(binary={'path':str(binary),'sha256':local.register_artifact(binary)},
               finished_at=time.time(),deadline_monotonic=deadline)
    outputs={r:['{cycle_dir}/'+r+'.bin'] for r in pmu.ROLES}
    case=dict(command=[str(binary),'--baseline-output',outputs['baseline'][0],
        '--candidate-output',outputs['candidate'][0]],output_files=outputs,
        verify_commands={r:['cpu-oracle','--output',outputs[r][0],'--result','{cycle_dir}/result.json'] for r in pmu.ROLES})
    monkeypatch.setattr(pmu,'TOOL',str(tool))
    monkeypatch.setattr(pmu,'_setup',lambda *a:(plan,build,case))
    monkeypatch.setenv('ASCEND_RT_VISIBLE_DEVICES','0')
    monkeypatch.setattr(pmu.bridge.timing.shared,'device_lock',lambda *a:contextlib.nullcontext())
    calls=[]
    def run(argv,cwd,prefix,timeout,store,binding=None,*,environment):
        calls.append(argv);started=time.time();stdout='CPU fixture\n'
        if '--help' in argv:stdout=' '.join(flag.split('=')[0] for flag in pmu.FLAGS)
        elif argv[0]==pmu.NPU_SMI:stdout='Chip Name : Ascend910_9392\n'
        elif argv[0]=='cpu-oracle':
            assert Path(argv[argv.index('--output')+1]).read_bytes()==b'complete'
            value={'case_id':1,'passed':True}
            Path(argv[argv.index('--result')+1]).write_text(json.dumps(value));stdout=json.dumps(value)
        else:
            command=shlex.split(argv[-1].split('=',1)[1]) if argv[0]==str(tool) else argv
            role=command[command.index('--aprof-mechanism-role')+1]
            Path(command[command.index('--'+role+'-output')+1]).write_bytes(b'complete')
            if argv[0]==str(tool):
                folder=Path(argv[1].split('=',1)[1])/'PROF_cpu/device_0/summary';folder.mkdir(parents=True)
                (folder/'op_summary_0.csv').write_text(table(expected,role))
                (folder/'raw.data').write_bytes(b'complete raw retained')
        logs={}
        for label,text in [('stdout',stdout),('stderr','')]:
            path=Path(str(prefix)+'.'+label+'.log');path.write_text(text);logs[label+'_hash']=store.register_artifact(path)
        record=dict(argv=argv,cwd=str(cwd),started_at=started,ended_at=time.time(),exit_code=0,error=None,
                    environment=environment,timeout_seconds=timeout,pid=123,**logs)
        if binding is not None:record['identity_checks']={k:pmu.bridge.profile_capture.identity_state(binding) for k in ('before','after')}
        path=Path(str(prefix)+'.execution.json');path.write_text(json.dumps(record));record['log_hash']=store.register_artifact(path)
        return dict(record,text=stdout)
    monkeypatch.setattr(pmu.bridge.profile_capture,'run',run)
    with pytest.raises(ValueError,match='inherit'):
        pmu.collect_baseline_pmu(local,plan_ref='plan',build_receipt_ref='build',destination=tmp_path/'reset',deadline=deadline+1)
    ref=pmu.collect_baseline_pmu(local,plan_ref='plan',build_receipt_ref='build',destination=tmp_path/'pmu',deadline=deadline)
    result=pmu.verify_baseline_pmu(local,plan_ref='plan',build_receipt_ref='build',report_ref=ref)
    assert result['valid'] and result['pmu_complete'] and not result['qualification_passed']
    assert len(calls)==42 and len(result['partitions']['baseline'])==5
    receipts=list((tmp_path/'pmu').glob('*/capture/*/slot-receipt.json'))
    assert len(receipts)==10
    for path in receipts:
        slot=json.loads(path.read_text())
        assert slot['outputs_before_oracle']==slot['outputs_after_oracle']
        assert slot['capture_execution_ref'] and slot['oracle_execution_ref'] and slot['profile_files']
        assert slot['oracle']['ended_at']<=slot['finalized_at']
    report=json.loads(local.verify_artifact(ref).read_text())
    report['captures'][0]['output_refs']={name:local.register_artifact(prepared)
        for name in report['captures'][0]['output_refs']}
    with pytest.raises(ValueError,match='finalized slot'):
        pmu.verify_baseline_pmu(local,plan_ref='plan',build_receipt_ref='build',report_ref=local.register_json(report))
    assert not list(tmp_path.rglob('*.sqlite')) and not (tmp_path/'objects').exists()
    raw=tmp_path/'pmu/baseline/capture/0/profile/PROF_cpu/device_0/summary/raw.data';raw.write_bytes(b'changed')
    with pytest.raises(ValueError,match='raw file changed'):
        pmu.verify_baseline_pmu(local,plan_ref='plan',build_receipt_ref='build',report_ref=ref)
