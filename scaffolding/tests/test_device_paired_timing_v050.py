"""CPU fake children test protocol and cleanup, not NPU performance."""
import importlib.util
import contextlib
import json
import os
from pathlib import Path
import sys
import time

import pytest
from aprof_layout import skill_lib

SCRIPT = skill_lib() / 'skills/ascendc-aprof-profiling/scripts/device_paired_timing.py'
if not SCRIPT.is_file():
    pytest.skip('persistent device timing starts in graph-base 0.5.0', allow_module_level=True)
spec = importlib.util.spec_from_file_location('device_timing_v050', SCRIPT)
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)

CHILD = r'''
import json,os,sys,time,subprocess
from pathlib import Path
role,behavior,output,history,prepared,case=sys.argv[1:]
def event(kind,**extra):
 with Path(history).open('a') as f:f.write(json.dumps(dict(kind=kind,role=role,pid=os.getpid(),case=int(case),**extra))+'\n')
event('start')
if behavior=='startup_timeout':time.sleep(30)
if behavior=='leader_exits':
 subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
 sys.exit(0)
print('APROF_TIMING_READY',flush=True)
i=0
for line in sys.stdin:
 if line.strip()=='quit':
  event('quit')
  if behavior=='quit_failure':sys.exit(7)
  if behavior!='missing_output':Path(output).write_text(role)
  break
 if line.strip()!='sample':sys.exit(9)
 event('sample',index=i)
 if behavior=='sample_timeout':time.sleep(30)
 row=dict(schema_version='1.0.0',operator='exp',device=0,source='acl_event',unit='ns',sample_index=i,warmup=int(os.environ['APROF_WARMUP']),repeat=int(os.environ['APROF_REPEAT']),launches_per_operator=1,elapsed_ns=100.0 if role=='baseline' else 80.0)
 changes={'bad_unit':('unit','us'),'bad_index':('sample_index',i+1),'bad_device':('device',1),'bad_operator':('operator','other'),'bad_repeat':('repeat',1),'bad_launches':('launches_per_operator',2),'bad_source':('source','wall_clock'),'bool_elapsed':('elapsed_ns',True),'negative_elapsed':('elapsed_ns',-1)}
 if behavior in changes:row[changes[behavior][0]]=changes[behavior][1]
 if behavior=='mutate_prepared':Path(prepared).write_text('changed')
 if behavior=='mutate_binary':
  with open(sys.argv[0],'a') as f:f.write('\n#changed\n')
 if behavior=='mutate_source':Path(sys.argv[0]).with_name('kernel.asc').write_text('changed')
 print('APROF_TIMING_JSON:'+json.dumps(row),flush=True)
 i+=1
'''
VERIFY = r'''
import json,os,sys,time
from pathlib import Path
output,role,history,case,behavior=sys.argv[1:]
with Path(history).open('a') as f:f.write(json.dumps(dict(kind='verify',role=role,pid=os.getpid(),case=int(case)))+'\n')
if behavior=='verify_timeout':time.sleep(30)
assert Path(output).read_text()==role
if behavior=='verify_mutates':Path(output).write_text('changed by verifier')
'''

@pytest.fixture
def config(tmp_path,monkeypatch):
    # Fake CPU children must not contend with concurrent real NPU validation.
    # The actual lock implementation is exercised below in a private namespace.
    monkeypatch.setattr(timing,'device_lock',lambda *_:contextlib.nullcontext())
    for key in ('ASCEND_RT_VISIBLE_DEVICES','ASCEND_VISIBLE_DEVICES'):
        monkeypatch.delenv(key,raising=False)
    prepared=tmp_path/'cache/input.bin';prepared.parent.mkdir();prepared.write_text('prepared input')
    value=dict(schema_version='1.0.0',operator='exp',device=0,expected_case_ids=[1],cases=[],timeout_seconds=2)
    case=dict(case_id=1,workload={'shape':[1024],'dtype':'float16'},prepared_files=[str(prepared)])
    for role in timing.ROLES:
        root=tmp_path/role;root.mkdir()
        binary=root/'operator';binary.write_text('#!'+sys.executable+'\n'+CHILD);binary.chmod(0o755)
        (root/'kernel.asc').write_text('fixture kernel');(root/'verify.py').write_text(VERIFY)
        value[role]=dict(cwd=str(root),source_dir=str(root),binary=str(binary))
        output=tmp_path/'results'/f'case-1-{role}.bin';history=tmp_path/'history.jsonl'
        case[role]=dict(command=[str(binary),role,'normal',str(output),str(history),str(prepared),'1'],
            verify_command=[sys.executable,str(root/'verify.py'),str(output),role,str(history),'1','normal'],output_files=[str(output)])
    value['cases'].append(case)
    return value

def history(config):
    p=Path(config['cases'][0]['baseline']['command'][4])
    return [json.loads(line) for line in p.read_text().splitlines()] if p.exists() else []

def stopped(config):
    for row in history(config):
        if row['kind']=='start':
            with pytest.raises(ProcessLookupError):os.kill(row['pid'],0)

def raw(tmp_path):return json.loads((tmp_path/'evidence/raw_measurements.json').read_text())

def test_six_pairs_reuse_two_children_then_verify(config,tmp_path):
    report=timing.collect(config,tmp_path/'evidence');rows=history(config)
    assert [r['role'] for r in rows if r['kind']=='start']==['baseline','candidate']
    assert [r['role'] for r in rows if r['kind']=='sample']==['baseline','candidate','candidate','baseline']*3
    assert max(i for i,r in enumerate(rows) if r['kind']=='quit')<min(i for i,r in enumerate(rows) if r['kind']=='verify')
    data=raw(tmp_path);assert data['complete'] and len(data['records'])==6
    dependencies=data['producer_dependencies']
    assert dependencies['runtime_source_hash']==timing.content_hash(dependencies['runtime_source_files'])
    assert dependencies['runtime_source_files']['gates.py']==timing.file_hash(timing.runtime_gates.__file__)
    assert dependencies['device_timer.h']==timing.file_hash(SCRIPT.parent.parent/'assets/device_timer.h')
    assert dependencies['profile_capture.py']==timing.file_hash(SCRIPT.parent/'profile_capture.py')
    assert data['case_executions'][0]['identity_before']==data['case_executions'][0]['identity_after']
    assert not report['stable'] and report['gate_projection']['baseline_samples_ns']==[]
    assert report['per_case'][0]['speedup']==pytest.approx(1.25)
    draft=json.loads((tmp_path/'evidence/timing_draft.json').read_text())
    assert not draft['production_minimum_met'] and draft['full_correctness_required']
    assert 'selected_as_best' not in draft and data['environment']['APROF_CAPTURE_REPLAY'] is None
    stopped(config)

def test_formal_projection_has_thirty_pairs_and_stays_draft(config,tmp_path):
    config['mode']='formal';report=timing.collect(config,tmp_path/'evidence')
    assert report['stable'] and len(report['gate_projection']['baseline_samples_ns'])==30
    assert report['speedup_lcb_95']==pytest.approx(1.25)
    assert 'performance_eligible' not in report and 'runtime candidate gate required' in report['authority']
    assert len([r for r in history(config) if r['kind']=='start'])==2

@pytest.mark.parametrize('field,value',[('pairs',29),('warmup',9)])
def test_formal_floors(config,tmp_path,field,value):
    config.update(mode='formal',**{field:value})
    with pytest.raises(ValueError,match='30 pairs and 10 warmups'):timing.collect(config,tmp_path/'evidence')
    assert history(config)==[]

@pytest.mark.parametrize('behavior',['bad_unit','bad_index','bad_device','bad_operator','bad_repeat','bad_launches','bad_source','bool_elapsed','negative_elapsed'])
def test_bad_sample_preserves_raw_and_cleans_children(config,tmp_path,behavior):
    config['cases'][0]['candidate']['command'][2]=behavior
    with pytest.raises(ValueError):timing.collect(config,tmp_path/'evidence')
    data=raw(tmp_path)
    assert not data['complete'] and data['records'][0]['baseline'] is not None and data['records'][0]['candidate'] is None
    assert json.loads((tmp_path/'evidence/measurement_report.json').read_text())['gate_projection']['baseline_samples_ns']==[]
    assert not [r for r in history(config) if r['kind']=='verify'];stopped(config)

@pytest.mark.parametrize('behavior',['mutate_prepared','mutate_binary','mutate_source'])
def test_identity_changes_rejected(config,tmp_path,behavior):
    config['cases'][0]['candidate']['command'][2]=behavior
    with pytest.raises(ValueError,match='identity changed'):timing.collect(config,tmp_path/'evidence')
    stopped(config);assert not raw(tmp_path)['complete']

@pytest.mark.parametrize('behavior',['startup_timeout','sample_timeout','leader_exits','quit_failure','missing_output'])
def test_timeout_exit_cleanup(config,tmp_path,behavior):
    config['timeout_seconds']=.2;config['cases'][0]['candidate']['command'][2]=behavior
    start=time.monotonic()
    with pytest.raises((RuntimeError,TimeoutError,ValueError)):timing.collect(config,tmp_path/'evidence')
    assert time.monotonic()-start<8;stopped(config)
    assert (tmp_path/'evidence/case-01-candidate.log').exists()
    data=raw(tmp_path);assert not data['complete']
    assert data['case_executions'][0]['commands']['candidate']['exit_status'] is not None

@pytest.mark.parametrize('behavior',['verify_timeout','verify_mutates'])
def test_verifier_failure_retains_receipt(config,tmp_path,behavior):
    config['timeout_seconds']=.2;config['cases'][0]['baseline']['verify_command'][-1]=behavior
    with pytest.raises((ValueError,TimeoutError,timing.subprocess.TimeoutExpired)):timing.collect(config,tmp_path/'evidence')
    data=raw(tmp_path);receipt=data['case_executions'][0]['verifications']['baseline']
    assert receipt['log_hash'] and receipt['finished_at'] is not None and not data['complete'];stopped(config)

@pytest.mark.parametrize('change',['duplicate_role_output','existing_output','prepared_output','case_mismatch'])
def test_output_isolation(config,tmp_path,change):
    case=config['cases'][0]
    if change=='duplicate_role_output':case['candidate']['output_files']=case['baseline']['output_files']
    elif change=='existing_output':
        p=Path(case['candidate']['output_files'][0]);p.parent.mkdir();p.write_text('stale')
    elif change=='prepared_output':case['candidate']['output_files']=[str(Path(case['prepared_files'][0]).with_name('unsafe.bin'))]
    else:config['expected_case_ids']=[2]
    with pytest.raises(ValueError):timing.collect(config,tmp_path/'evidence')
    assert history(config)==[]

def test_visibility_mapping(config,monkeypatch):
    monkeypatch.setenv('ASCEND_RT_VISIBLE_DEVICES','3,4')
    with pytest.raises(ValueError,match='explicit physical_device'):timing.config_value(config)
    config['physical_device']=4
    with pytest.raises(ValueError,match='disagrees'):timing.config_value(config)
    config['physical_device']=3;assert timing.config_value(config)['physical_device']==3

def test_device_lock_excludes_contenders_and_releases(tmp_path,monkeypatch):
    original_path=timing.Path
    monkeypatch.setattr(timing,'Path',lambda path:tmp_path/'locks' if str(path)=='/tmp/aprof-device-locks' else original_path(path))
    with timing.device_lock(0,.2):
        with pytest.raises(TimeoutError,match='advisory lock is held'):
            with timing.device_lock(0,.05):
                pytest.fail('contender acquired the same device')
        with timing.device_lock(1,.2):
            pass
    with timing.device_lock(0,.2):
        pass
