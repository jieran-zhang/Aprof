"""Real CPU child processes exercise v2 lifecycle; these are not NPU evidence."""
import contextlib
import json
import os
from pathlib import Path
import sys

import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'collection/scripts'
sys.path.insert(0,str(SCRIPTS))
import device_paired_timing_v2 as timing

CHILD=r'''
import json,os,sys
from pathlib import Path
role,behavior,output,history=sys.argv[1:]
def event(kind,**values):
 with Path(history).open('a') as f:f.write(json.dumps(dict(kind=kind,role=role,pid=os.getpid(),**values))+'\n')
event('start');print('APROF_TIMING_READY',flush=True)
i=p=0
for line in sys.stdin:
 c=line.strip()
 if c=='quit':
  event('quit');Path(output).write_text(role);break
 if c=='prime':
  event('prime',index=p)
  row=dict(schema_version='2.0.0',operator='exp',device=0,prime_index=p,repeat=100,launches_per_operator=1)
  if behavior=='bad_prime':row['repeat']=99
  print('APROF_PRIME_JSON:'+json.dumps(row),flush=True);p+=1;continue
 if c!='sample' or p!=2:sys.exit(9)
 event('sample',index=i)
 row=dict(schema_version='1.0.0',operator='exp',device=0,source='acl_event',unit='ns',sample_index=i,warmup=int(os.environ['APROF_WARMUP']),repeat=int(os.environ['APROF_REPEAT']),launches_per_operator=1,elapsed_ns=100.0 if role=='baseline' else 80.0)
 if behavior=='bad_sample_index':row['sample_index']+=1
 print('APROF_TIMING_JSON:'+json.dumps(row),flush=True);i+=1
'''
VERIFY="from pathlib import Path\nimport sys\nassert Path(sys.argv[1]).read_text()==sys.argv[2]\n"

@pytest.fixture
def config(tmp_path,monkeypatch):
 monkeypatch.setattr(timing.v1,'device_lock',lambda *_:contextlib.nullcontext())
 for key in ('ASCEND_RT_VISIBLE_DEVICES','ASCEND_VISIBLE_DEVICES'):monkeypatch.delenv(key,raising=False)
 prepared=tmp_path/'prepared/input';prepared.parent.mkdir();prepared.write_text('immutable')
 value=dict(schema_version='2.0.0',operator='exp',device=0,expected_case_ids=[1],cases=[],pairs=6,warmup=10,repeat=100,timeout_seconds=2)
 for role in timing.ROLES:
  d=tmp_path/role;d.mkdir();binary=d/'operator';binary.write_text('#!'+sys.executable+'\n'+CHILD);binary.chmod(0o755)
  (d/'kernel.asc').write_text('fixture');(d/'verify.py').write_text(VERIFY)
  value[role]=dict(cwd=str(d),source_dir=str(d),binary=str(binary))
 case=dict(case_id=1,workload=dict(numel=33),prepared_files=[str(prepared)],epochs=[])
 for epoch in range(2):
  row={}
  for role in timing.ROLES:
   d=tmp_path/role;out=tmp_path/'outputs'/f'{epoch}-{role}.bin'
   row[role]=dict(command=[str(d/'operator'),role,'normal',str(out),str(tmp_path/'history.jsonl')],verify_command=[sys.executable,str(d/'verify.py'),str(out),role],output_files=[str(out)],launches_per_operator=1)
  case['epochs'].append(row)
 value['cases'].append(case);return value

def history(tmp_path):
 p=tmp_path/'history.jsonl';return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

def test_true_new_processes_reversed_start_and_fixed_prime_order(config,tmp_path):
 report=timing.collect(config,tmp_path/'evidence');h=history(tmp_path)
 assert [x['role'] for x in h if x['kind']=='start']==['baseline','candidate','candidate','baseline']
 assert len({x['pid'] for x in h if x['kind']=='start'})==4
 assert [x['role'] for x in h if x['kind']=='prime']==['baseline','candidate','candidate','baseline','candidate','baseline','baseline','candidate']
 assert [x['role'] for x in h if x['kind']=='sample']==['baseline','candidate','candidate','baseline']*3
 raw=json.loads((tmp_path/'evidence/raw_measurements.json').read_text())
 assert raw['complete'] and [r['round'] for r in raw['records']]==list(range(6))
 assert [r['epoch'] for r in raw['records']]==[0]*3+[1]*3
 assert [r['baseline']['sample_index'] for r in raw['records']]==[0,1,2]*2
 for epoch in raw['case_executions'][0]['epochs']:
  assert epoch['identity_before']==epoch['identity_after'] and epoch['exit_status']==0
  assert min(p['request_monotonic_ns'] for p in epoch['prime_receipts'])>=max(v['ready_monotonic_ns'] for v in epoch['ready_receipts'].values())
  for role in timing.ROLES:assert epoch['verifications'][role]['exit_status']==0
 for record in raw['records']:
  for role in timing.ROLES:
   r=record['sample_receipts'][role];assert r['response_monotonic_ns']>=r['request_monotonic_ns']
 assert report['per_case'][0]['speedup']==pytest.approx(1.25) and not report['stable']
 for event in h:
  if event['kind']=='start':
   with pytest.raises(ProcessLookupError):os.kill(event['pid'],0)

def test_formal30_and_nondefault_positive_repeat(config,tmp_path):
 config.update(mode='formal',pairs=30,repeat=7)
 report=timing.collect(config,tmp_path/'evidence')
 assert report['stable'] and len(report['gate_projection']['baseline_samples_ns'])==30
 raw=json.loads((tmp_path/'evidence/raw_measurements.json').read_text())
 assert [r['local_round'] for r in raw['records']]==list(range(15))*2
 assert all(p['acknowledgement']['repeat']==100 for e in raw['case_executions'][0]['epochs'] for p in e['prime_receipts'])

@pytest.mark.parametrize('behavior',['bad_prime','bad_sample_index'])
def test_failed_protocol_retains_real_logs_and_no_later_epoch(config,tmp_path,behavior):
 config['cases'][0]['epochs'][0]['candidate']['command'][2]=behavior
 with pytest.raises(ValueError):timing.collect(config,tmp_path/'evidence')
 raw=json.loads((tmp_path/'evidence/raw_measurements.json').read_text())
 assert not raw['complete'] and len(raw['case_executions'][0]['epochs'])==1
 for row in history(tmp_path):
  if row['kind']=='start':
   with pytest.raises(ProcessLookupError):os.kill(row['pid'],0)

@pytest.mark.parametrize('change',['reused_output','odd_pairs','prime_repeat'])
def test_config_fails_before_child_launch(config,tmp_path,change):
 if change=='reused_output':config['cases'][0]['epochs'][1]['baseline']['output_files']=config['cases'][0]['epochs'][0]['baseline']['output_files']
 elif change=='odd_pairs':config['pairs']=5
 else:config['prime_repeat']=99
 with pytest.raises(ValueError):timing.collect(config,tmp_path/'evidence')
 assert not history(tmp_path)

@pytest.fixture(scope='module')
def header_stub(tmp_path_factory):
 import shutil,subprocess
 from test_device_timer_capture import ACL_STUB,PROGRAM
 compiler=shutil.which('c++') or shutil.which('g++')
 if not compiler:pytest.skip('host C++ compiler unavailable')
 d=tmp_path_factory.mktemp('v2-acl-stub');(d/'acl').mkdir();(d/'acl/acl.h').write_text(ACL_STUB)
 (d/'stub.cpp').write_text(PROGRAM.replace('#include "device_timer.h"','#include "device_timer_v2.h"'))
 binary=d/'stub'
 subprocess.run([compiler,'-std=c++14','-Wall','-Wextra','-Werror','-I',str(d),'-I',str(timing.HEADER.parent),str(d/'stub.cpp'),'-o',str(binary)],check=True,capture_output=True,text=True,timeout=30)
 return binary

@pytest.mark.parametrize('commands,ok',[('prime\nprime\nsample\nquit\n',True),('sample\nquit\n',False),('prime\nprime\nprime\nquit\n',False)])
def test_actual_header_primes_complete_op_without_timing_or_capture(header_stub,commands,ok):
 import subprocess
 env={k:v for k,v in os.environ.items() if not k.startswith('APROF_')}
 env.update(APROF_TIMING_INTERACTIVE='1',APROF_TIMING_V2='1',APROF_WARMUP='10',APROF_REPEAT='7')
 r=subprocess.run([str(header_stub)],input=commands,env=env,capture_output=True,text=True,timeout=10)
 assert (r.returncode==0)==ok
 stats=next(json.loads(x.removeprefix('STUB_STATS:')) for x in r.stdout.splitlines() if x.startswith('STUB_STATS:'))
 assert stats['begins']==stats['replays']==0
 if ok:
  assert stats['launch_calls']==217 and stats['stream_syncs']==3
  primes=[json.loads(x.removeprefix('APROF_PRIME_JSON:')) for x in r.stdout.splitlines() if x.startswith('APROF_PRIME_JSON:')]
  assert [x['prime_index'] for x in primes]==[0,1] and all(x['repeat']==100 and x['launches_per_operator']==3 for x in primes)
  assert len([x for x in r.stdout.splitlines() if x.startswith('APROF_TIMING_JSON:')])==1
