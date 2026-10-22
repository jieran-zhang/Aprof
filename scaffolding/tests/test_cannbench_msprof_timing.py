import csv
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
from cannbench_msprof_timing import instrument, parse_profile, summarize, profiler_arguments


def fixture(tmp_path, multi=False):
    symbols={r:[r+'_partial',r+'_final'] if multi else [r+'_kernel'] for r in 'AB'}
    build={'roles':{r:{'source_sha256':'same','kernel_symbols':','.join(symbols[r])} for r in 'AB'}}
    launches=4 if multi else 1
    cases=[{'case_id':'1','launches_per_call':{'A':launches,'B':launches}}]
    journal=[{'type':'module','role':r,**build['roles'][r]} for r in 'AB']
    journal.append({'type':'case_start','case_id':'1','repeat':1,'pairs':30,'warmup_per_role':10})
    names=[]
    for _ in range(10):
        for r in 'AB':names.extend(symbols[r]*(launches//len(symbols[r])))
    for pair in range(30):
        order='AB' if pair%2==0 else 'BA'
        for r in order:
            names.extend(symbols[r]*(launches//len(symbols[r])))
            journal.append(dict(type='sample',case_id='1',repeat=1,launches_per_call=launches,
                                role=r,buffer_config='normal',pair_id=pair,order=order,ns_per_call=100000))
    journal.append({'type':'session_end','exit_code':0})
    jp=tmp_path/'journal.jsonl';jp.write_text(''.join(json.dumps(r)+'\n' for r in journal))
    rows=[{'Op Name':name,'Task Type':'AI_VECTOR_CORE','Task Start Time(us)':str(10000+i*20),
           'Task Duration(us)':'5','aiv_time(us)':'3','Stream ID':'4','Task ID':str(i),'Device_id':'0'} for i,name in enumerate(names)]
    path=tmp_path/'op_summary.csv'
    write_csv(path,rows)
    return jp,build,cases,path,rows


def write_csv(path, rows):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


@pytest.mark.parametrize('multi',[False,True])
def test_complete_calls_exclude_warmup_and_gaps(tmp_path,multi):
    jp,build,cases,path,rows=fixture(tmp_path,multi)
    result=parse_profile(tmp_path,jp,build,cases,1)
    k=4 if multi else 1
    assert result['warmup_tasks_excluded']==20*k
    assert len(result['samples'])==60
    s=result['samples'][0]
    assert s['task_us']==5*k
    assert s['core_us']==3*k
    assert s['event_us']==100
    assert s['inter_task_gap_us']==15*(k-1)


@pytest.mark.parametrize('corruption',['drop','extra','wrong_role','duplicate','nan','overlap','stream','incomplete_native'])
def test_capture_corruption_fails_closed(tmp_path,corruption):
    jp,build,cases,path,rows=fixture(tmp_path)
    if corruption=='drop':rows.pop(25)
    elif corruption=='extra':rows.append(dict(rows[-1],**{'Task ID':'extra','Task Start Time(us)':'99999'}))
    elif corruption=='wrong_role':rows[25]['Op Name']='A_kernel' if rows[25]['Op Name']=='B_kernel' else 'B_kernel'
    elif corruption=='duplicate':rows.insert(25,dict(rows[25]))
    elif corruption=='nan':rows[25]['Task Duration(us)']='nan'
    elif corruption=='overlap':rows[25]['Task Start Time(us)']=str(int(rows[24]['Task Start Time(us)'])+1)
    elif corruption=='stream':rows[25]['Stream ID']='7'
    elif corruption=='incomplete_native':jp.write_text(jp.read_text().replace('"exit_code": 0','"exit_code": 1'))
    write_csv(path,rows)
    with pytest.raises(ValueError):parse_profile(tmp_path,jp,build,cases,1)


def test_native_template_keeps_correct_event_conversion():
    p=Path(__file__).resolve().parents[2]/'scaffolding/benchmarks/cannbench/harness/shared_context/runner.cpp'
    result=instrument(p.read_text(),10)
    assert 'double(ms)*1000000/10' in result
    assert result.count(r'\"repeat\":10')==2
    assert r'\"complete_calls_since_prepare\":310' in result
    assert 'APROF_MSPROF_HOST_DELAY_A_US' in result
    assert 'RTLD_NODELETE' in result


@pytest.mark.parametrize('missing',['0.0','N/A',''])
def test_missing_pmu_is_not_a_zero_time_measurement(tmp_path,missing):
    jp,build,cases,path,rows=fixture(tmp_path)
    rows[0]['aiv_time(us)']='0.0'  # Warmup must still be excluded by sequence.
    rows[21]['aiv_time(us)']=missing
    write_csv(path,rows)
    result=parse_profile(tmp_path,jp,build,cases,1)
    assert result['samples'][0]['core_us']==3
    assert result['samples'][1]['core_us'] is None
    assert result['samples'][1]['task_us']==5


def test_process_replication_does_not_pool_launches(tmp_path):
    dirs=[]
    for n,ratio in enumerate([.8,1.2]):
        d=tmp_path/str(n);d.mkdir();dirs.append(d)
        rows=[]
        for pair in range(30):
            for role in 'AB':
                value=ratio if role=='A' else 1
                rows.append(dict(case_id='1',buffer_config='normal',pair_id=pair,role=role,
                                 order='AB' if pair%2==0 else 'BA',task_us=value,core_us=value,event_us=value))
        (d/'completion.json').write_text('{"status":"passed"}')
        (d/'request.json').write_text('{}')
        (d/'samples.json').write_text(json.dumps({'samples':rows}))
    result=summarize(dirs)['results'][0]
    assert result['n_processes']==2
    assert result['speedup']==pytest.approx((.8*1.2)**.5)
    assert result['ci95'][0]<.8 and result['ci95'][1]>1.2
    assert not result['aa_within_half_percent']
    with pytest.raises(ValueError,match='duplicate process'):
        summarize([dirs[0],dirs[0]])
    (dirs[1]/'request.json').write_text('{"profiler_mode":"task_time_l1_ai_core_off"}')
    with pytest.raises(ValueError,match='cannot pool'):
        summarize(dirs)


def test_task_only_mode_does_not_enable_pmu_or_msprof_op(tmp_path):
    command=profiler_arguments('task_time_l1_ai_core_off',tmp_path)
    assert command[0]=='msprof' and 'op' not in command
    assert '--ai-core=off' in command and '--task-time=l1' in command
    assert not any(x.startswith('--aic-metrics') for x in command)
    assert '--ai-core=on' in profiler_arguments('task_time_l1_pipe_utilization',tmp_path)
    with pytest.raises(ValueError):profiler_arguments('unknown',tmp_path)
