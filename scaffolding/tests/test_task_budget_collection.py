"""CPU child processes and explicit native-unit stubs; no real profiler/device."""
import json
from pathlib import Path
import time as real_time
from types import SimpleNamespace

import pytest

from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.task_window_measurement_admission import collection_unit_deadline, replay_collection_unit
import device_task_window_timing as collector
import profile_capture
from test_task_budget_runtime import parent, POLICY


def executable(path, text):
    path.write_text('#!/usr/bin/env python3\n'+text);path.chmod(0o755);return path


def config(tmp_path, *, hang=False):
    source=tmp_path/'source';source.mkdir();(source/'kernel.cpp').write_text('original CPU fixture source')
    binary=executable(tmp_path/'operator', "print('complete callback')\n")
    tool=executable(tmp_path/'fake-msprof', '''import pathlib,sys,time
if '--help' in sys.argv:print('op profile fixture');raise SystemExit(0)
root=pathlib.Path(next(v.split('=',1)[1] for v in sys.argv if v.startswith('--output=')))
raw=root/'kernel';raw.mkdir(parents=True)
(raw/'OpBasicInfo.csv').write_text('Op Name,Current Freq,Rated Freq\\nkernel,1850,1850\\n')
(raw/'raw.bin').write_text('opened')
time.sleep(%r)
(raw/'raw.bin').write_text('closed-complete-raw')
''' % (1 if hang else .01))
    smi=executable(tmp_path/'fake-board', "print('Board ID: 9392')\n")
    return dict(backend='msprof',architecture='910C',device=0,role='baseline',case_id=1,kernel='kernel',
        command=[str(binary)],binary=str(binary),cwd=str(tmp_path),source_dir=str(source),
        tool_path=str(tool),npu_smi_path=str(smi),workload={'shape':[1]},warmups=0,repeats=2,
        timeout_seconds=.1 if hang else 2)


def test_started_capture_closes_past_soft_cutoff_then_partial_keeps_index(tmp_path, monkeypatch):
    cfg=config(tmp_path);clock=[699.0];calls=[]
    monkeypatch.setattr(profile_capture,'time',SimpleNamespace(time=real_time.time,monotonic=lambda:clock[0]))
    actual_run=profile_capture.run
    def run(*args,**kwargs):
        value=actual_run(*args,**kwargs)
        if '--output=' in ' '.join(args[0]):clock[0]=750  # Completed real CPU capture crosses S=700.
        return value
    monkeypatch.setattr(profile_capture,'run',run)
    def before(kind,index):
        calls.append((kind,index,clock[0]))
        return collection_unit_deadline(1000,POLICY,'pmu',now=clock[0])
    out=tmp_path/'result'
    with pytest.raises(TimeoutError,match='soft budget'):
        profile_capture.capture(cfg,out,deadline_monotonic=1000,before_unit=before)
    assert calls==[('capture',0,699),('capture',1,750)]
    assert (out/'capture-000/raw/kernel/raw.bin').read_text()=='closed-complete-raw'
    assert not (out/'capture-001').exists()
    partial=json.loads((out/'partial-manifest.json').read_text())
    assert len(partial['captures'])==1 and partial['policy']['repeats']==2
    reader=LocalEvidence.from_index(out/'local-index.json')
    assert reader.verify_artifact(partial['captures'][0]['log_hash']).is_file()
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='failed' and result['performance_gate'] is False
    assert result['failure']['next_or_active_unit']=={'kind':'capture','index':1}


def test_true_command_hang_remains_bounded_and_retains_failed_receipt(tmp_path):
    cfg=config(tmp_path,hang=True);out=tmp_path/'result';started=real_time.monotonic()
    with pytest.raises(RuntimeError,match='command failed'):
        profile_capture.capture(cfg,out,deadline_monotonic=started+10)
    assert real_time.monotonic()-started<3
    record=json.loads((out/'capture-000/capture.execution.json').read_text())
    assert record['error']['type']=='TimeoutExpired'
    assert json.loads((out/'partial-manifest.json').read_text())['captures']==[]
    assert LocalEvidence.from_index(out/'local-index.json').register_artifact(out/'capture-000/capture.execution.json')
    assert json.loads((out/'result.json').read_text())['status']=='failed'


def test_callback_cannot_extend_absolute_deadline(tmp_path):
    cfg=config(tmp_path);deadline=real_time.monotonic()+10
    with pytest.raises(ValueError,match='extend'):
        profile_capture.capture(cfg,tmp_path/'result',deadline_monotonic=deadline,
                                before_unit=lambda kind,index:deadline+1)


def test_native_pilot_finishes_then_next_unit_stops_with_truthful_partial(tmp_path, monkeypatch):
    # Exercise the actual collector orchestration and partial writers. The
    # already-covered native capture/parser/oracle unit is one explicit stub.
    original=LocalEvidence(tmp_path/'parent-records');p=parent(original)
    clock=[6999.0]
    monkeypatch.setattr(collector,'time',SimpleNamespace(time=lambda:clock[0]-100,
        monotonic=lambda:clock[0],monotonic_ns=lambda:int(clock[0]*1e9)))
    roots={name:tmp_path/name for name in ('baseline','candidate','build')}
    for path in roots.values():path.mkdir()
    profiler=executable(tmp_path/'fake-profiler',"print('not executed')\n")
    cfg={**p.expected,'physical_device':0,'device':0,'expected_case_ids':[1],
        'roles':{r:{'source_dir':str(roots[r])} for r in ('baseline','candidate')},
        'build':{'source_dir':str(roots['build'])},'cases':[{'case_id':1}],
        'task_profile':{'scratch_root':str(tmp_path/'scratch'),'profiler':str(profiler)}}
    monkeypatch.setattr(collector,'config_value',lambda value,**kw:value)
    snapshot={'files':{},'producer_files':{}}
    monkeypatch.setattr(collector,'inventory',lambda *a,**kw:snapshot)
    monkeypatch.setattr(collector.shared,'bind_identity',lambda cfg,snap,store:{'source_hashes':{
        'baseline':store.register_json('baseline'),'candidate':store.register_json('candidate')}})
    requests=[dict(stage='calibration',case_id=1,cycle=None,role=r,request_index=i)
              for i,r in enumerate(('baseline','candidate'))]
    requests += [dict(stage='confirmation',case_id=1,cycle=c,role=r,request_index=2+c*2+i)
                 for c in range(6) for i,r in enumerate(('baseline','candidate'))]
    monkeypatch.setattr(collector.shared,'oracle_plan',lambda *a:{'requests':requests})
    monkeypatch.setattr(collector,'validate_plan',lambda v:v)
    class Oracle:
        def __init__(self,plan,*,directory,store,deadline):
            self.directory=directory;self.store=store;self.report={'status':'aborted'}
        def start(self):
            self.directory.mkdir();self.report['request_plan_ref']=self.store.register_artifact(
                self.directory.parent/'verifier-request-plan.json')
        def finish(self,**kwargs):return self.store.register_json({'status':'aborted'})
    monkeypatch.setattr(collector,'PersistentOracle',Oracle)
    monkeypatch.setattr(collector,'profile_dependencies',lambda **kw:{})
    monkeypatch.setattr(collector.shutil,'which',lambda name:str(profiler))
    monkeypatch.setattr(collector.old,'run_process',lambda *a,**kw:{'text':'CPU fixture'})
    monkeypatch.setattr(collector,'choose_task_repeat',lambda p:{'repeat':100,'median_100_calls_ns_decimal':'1000'})
    completed=[]
    def session(cfg,case,value,snapshot,env,worker,slots,store,deadline,**kw):
        assert value['mode']=='pilot' and deadline==7199
        directory=Path(value['cycle_dir']);directory.mkdir()
        (directory/'raw-closed.bin').write_text('complete unit')
        clock[0]=7050  # S=7000 crossed inside the unit; unitD7199 still respected.
        value['finished_at']=clock[0]-100;completed.append(value['mode'])
        return {'CPU_fixture':True}
    monkeypatch.setattr(collector,'run_session',session)
    # The device lock itself is replaced, so this test never touches a real NPU lock.
    from contextlib import nullcontext
    monkeypatch.setattr(collector.old,'device_lock',lambda *a:nullcontext())
    out=tmp_path/'measurement'
    result=collector.collect_local(cfg,out,timeout_seconds=301,deadline_monotonic=7300,
                                   budget_binding=p.binding,budget_reader=original)
    assert completed==['pilot'] and result['status']=='failed'
    partial=json.loads((out/'collection-partial.json').read_text())
    assert partial['next_or_active_unit']==dict(mode='confirmation',case_id=1,cycle=0)
    assert len(partial['completed_pilots'])==1 and not partial['admission_authority']
    assert not json.loads((out/'raw_measurements.json').read_text())['complete']
    assert LocalEvidence.from_index(result['local_index']).verify_artifact(result['measurement_admission_ref']).is_file()
    assert not result['report']['stable']
    reader=LocalEvidence.from_index(result['local_index'])
    pilot=partial['completed_pilots'][0]['pilot']
    unit=replay_collection_unit(reader,pilot['collection_unit_ref'],parent_deadline=7300,policy=POLICY,kind='task')
    assert unit['started_at']==pilot['started_at'] and unit['started_monotonic']==6999
    assert unit['deadline_monotonic']==7199 and pilot['finished_at']<=unit['wall_deadline']


def test_final_identity_cost_expiry_writes_only_failed_terminal(tmp_path,monkeypatch):
    cfg=config(tmp_path);cfg['repeats']=1;clock=[10.0];calls=[0]
    monkeypatch.setattr(profile_capture,'time',SimpleNamespace(time=real_time.time,monotonic=lambda:clock[0]))
    original=profile_capture.identity_state
    def identity(binding):
        value=original(binding);calls[0]+=1
        if calls[0]==3:clock[0]=1001.0  # Two capture checks, then final identity check.
        return value
    monkeypatch.setattr(profile_capture,'identity_state',identity)
    out=tmp_path/'result'
    with pytest.raises(TimeoutError,match='deadline expired'):
        profile_capture.capture(cfg,out,deadline_monotonic=1000)
    assert calls[0]==3 and not (out/'capture-manifest.json').exists()
    result=json.loads((out/'result.json').read_text())
    assert result['status']=='failed' and result['failure']['error']=='TimeoutError'
    assert len(json.loads((out/'partial-manifest.json').read_text())['captures'])==1
    assert LocalEvidence.from_index(out/'local-index.json').verify_artifact(result['failure']['partial_manifest_ref']).is_file()
