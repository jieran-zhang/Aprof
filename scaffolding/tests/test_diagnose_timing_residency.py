import csv
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

SCRIPT=Path(__file__).resolve().parents[1]/'collection/scripts/diagnose_timing_residency.py'
SPEC=importlib.util.spec_from_file_location('residency_diagnostic',SCRIPT)
diag=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(diag)


def test_fixed_matrix_has_six_cycles_and_balanced_orders():
    cells=diag.cells()
    assert len(cells)==72
    for op in ('exp','sigmoid'):
        for mode in diag.MODES:
            for factor in diag.FACTORS:
                assert sorted(c['cycle'] for c in cells if c['operator']==op and c['mode']==mode and c['logging']==factor)==list(range(6))
    orders=[order[0] for cycle in range(6) for order in diag.pair_orders(cycle)]
    assert orders.count('A')==orders.count('B')==15


def test_host_patch_refuses_unknown_kernel_layout():
    with pytest.raises(ValueError,match='frozen host'):diag.patch_host('aprof::Run()', 'exp')
    source=(diag.OLD/'exp/baseline/op_host/exp.asc').read_text()
    patched=diag.patch_host(source,'exp')
    assert 'aprof_diag::Run' in patched and 'static_cast<uint8_t *>(params)' in patched
    assert patched.count('exp_kernel<<<')==source.count('exp_kernel<<<')==1


@pytest.mark.parametrize('factor',['row_logging','buffered'])
def test_logging_factor_and_complete_reader_evidence(tmp_path,factor):
    program=tmp_path/'worker.py'
    program.write_text('''import json,os,sys
def emit(x):print('APROF_DIAG_JSON:'+json.dumps(x),flush=True)
emit(dict(type='ready',pid=os.getpid(),buffers=[dict(slot=0)]))
for line in sys.stdin:
 if line.strip()=='quit':break
 verb,slot,seq=line.split()
 emit(dict(type=verb,pid=os.getpid(),slot=int(slot),sequence=int(seq),event_ns_per_operator=100.,repeat=100))
emit(dict(type='completed',pid=os.getpid()))
''')
    directory=tmp_path/'child';directory.mkdir()
    child=diag.Child([sys.executable,str(program)],tmp_path,dict(os.environ),directory,factor,[min(os.sched_getaffinity(0))])
    raw={'phases':[],'records':[],'logging_reference_payload':{'historical_records':[{'not_a_new_sample':True}], 'fixed_padding':'x'*65536}}
    try:
        diag.sample_phase(raw,'shared',{r:(child,0) for r in diag.ROLES},0,tmp_path,factor)
        assert len(raw['records'])==5
        assert (tmp_path/'raw.json').exists()==(factor=='row_logging')
        assert (directory/'stdout.log').exists()==(factor=='row_logging')
        if factor=='row_logging':
            assert len(raw['persistence_receipts'])==5
            assert all(r['bytes']>65536 and r['finished_monotonic_ns']>=r['started_monotonic_ns'] for r in raw['persistence_receipts'])
        child.close();child.persist()
        lines=(directory/'stdout.log').read_text().splitlines()
        assert len(lines)==16  # READY + four primes + ten samples + completion.
        assert read_json(directory/'execution.json')['exit_status']==0
    finally:child.close(abort=True)


def read_json(path):return json.loads(path.read_text())


def test_per_cycle_failure_cannot_hide_in_overall_average(tmp_path):
    conditions={'shared':['shared'],'split':['map_AB','map_BA'],'residency':['solo_before','secondary_idle','dual_active_serial','solo_after']}
    for cell in diag.cells():
        if cell['operator']!='exp':continue
        out=tmp_path/f"exp-{cell['cycle']}-{cell['mode']}-{cell['logging']}";out.mkdir()
        rows=[]
        for condition in conditions[cell['mode']]:
            for pair in range(5):
                roles={r:{'sample':{'event_ns_per_operator':100.,'slot':slot}} for r,slot in zip(diag.ROLES,(0,1) if condition=='map_AB' else (1,0))}
                if cell['cycle']==0 and condition=='shared':roles['B']['sample']['event_ns_per_operator']=110.
                rows.append(dict(condition=condition,cycle=cell['cycle'],roles=roles))
        diag.save(out/'raw.json',{'records':rows})
    report=diag.summarize(tmp_path,{'operators':{'exp':{}},'conditions':conditions})
    assert not report['all_controls_passed']
    shared=[r for r in report['rows'] if r['condition']=='shared']
    assert all(r['passed'] for r in shared if r['cycle'] is None)
    assert not any(r['passed'] for r in shared if r['cycle']==0)


def test_independent_task_timeline_counts_full_launches_and_keeps_gaps(tmp_path):
    table=tmp_path/'op_summary.csv'
    with table.open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['Op Name','Task Start Time(us)','Task Duration(us)']);writer.writeheader()
        for index in range(510):writer.writerow({'Op Name':'exp_kernel','Task Start Time(us)':1000+index*.2,'Task Duration(us)':.1})
    stdout=tmp_path/'stdout.log'
    stdout.write_text(diag.PREFIX+json.dumps(dict(type='sample',repeat=100,sequence=4,event_ns_per_operator=250))+'\n')
    result=diag.timeline_summary(table,stdout,'exp')
    assert result['sample_task_count']==100 and result['kernel_total_duration_ns']==10000
    assert result['first_last_kernel_span_ns']==pytest.approx(19900)
    assert result['acl_event_range_ns']==25000
    table.write_text('\n'.join(table.read_text().splitlines()[:-1])+'\n')
    with pytest.raises(ValueError,match='510'):diag.timeline_summary(table,stdout,'exp')
