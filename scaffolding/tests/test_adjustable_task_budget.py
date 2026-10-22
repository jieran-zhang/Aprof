"""CPU checks of the current controller code; no model, compiler or device."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time
import datetime as dt
import math
import pytest

REPO=Path(__file__).resolve().parents[2]
S=REPO/'scaffolding/collection/scripts'
sys.path.insert(0,str(S))
from task_budget import budget_seconds, positive, evaluation_budget, teacher_budget, rule_execution_job
from run_aprof_job import run as run_job

def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,sort_keys=True,allow_nan=False)+'\n')
def pointer(path):return dict(path=str(path),sha256=sha(path))
def checked(p):
 assert sha(p['path'])==p['sha256'];return Path(p['path'])

def functions(name,names,extra=None):
 tree=ast.parse((S/name).read_text())
 body=[node for node in tree.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in names]
 assert {node.name for node in body}==set(names)
 ns=dict(Path=Path,json=json,time=time,dt=dt,math=math,sys=sys,sha=sha,load=lambda p:json.loads(Path(p).read_text()),
         dump=save,checked=checked,budget_seconds=budget_seconds,evaluation_budget=evaluation_budget,
         BUDGET_POLICY='time_only_v1',run_job=run_job,__file__=str(S/name))
 ns.update(extra or {});exec(compile(ast.Module(body=body,type_ignores=[]),str(S/name),'exec'),ns);return ns

@pytest.mark.parametrize('value',[True,False,0,-1,float('inf'),float('nan'),'7200'])
def test_bad_budget(value):
 with pytest.raises(ValueError):positive(value)

@pytest.mark.parametrize('value',[3600,7200])
def test_alias(value):
 assert budget_seconds({'wall_time_limit_seconds':value})==value
 assert budget_seconds({'wall_time_limit_seconds':value,'budget_seconds':value})==value
 with pytest.raises(ValueError):budget_seconds({'wall_time_limit_seconds':value,'budget_seconds':value+1})

CHILD='''import json,time,sys\nfrom pathlib import Path\np=Path(sys.argv[1]);l=json.loads((p/'dispatcher-launch.json').read_text());m=time.monotonic();r={'status':'passed','deployed_speedup':1,'time_to_target_seconds':None,'task_launch_ref':{'path':str(p/'dispatcher-launch.json'),'sha256':sys.argv[2]},'started_monotonic':l['started_monotonic'],'finished_monotonic':m,'deadline_monotonic':l['deadline_monotonic'],'duration_seconds':m-l['started_monotonic']}\n(p/'child-result.json').write_text(json.dumps(r));(p/'worker').mkdir();(p/'worker/worker.json').write_text(json.dumps({'usage':{'totalTokens':0}}))\n'''

def setup(tmp_path,B=7200):
 save(tmp_path/'plan.json',{'equal_budget_evaluation':{'budget_seconds':B}})
 manifest={'plan':pointer(tmp_path/'plan.json')}
 save(tmp_path/'freeze.json',manifest)
 rows=[dict(run_id='op-'+arm,operator='op',arm=arm,seed=4101) for arm in ('baseline','skill-only','skill-plus-wiki')]
 save(tmp_path/'matrix.json',{'freeze_sha256':sha(tmp_path/'freeze.json'),'runs':rows})
 ns=functions('evaluate_skill_release.py',['_pointer','_load_launch','_dispatch_result','dispatch','verify_dispatch'])
 def job(output,row,manifest):
  p=output/'runs'/row['run_id']
  # _load_launch adds the real launch digest as the final argv pair.
  code=CHILD.replace('sys.argv[2]','sys.argv[3]')
  return dict(job_id=row['run_id'],argv=[sys.executable,'-c',code,str(p)],cwd=str(tmp_path),
              output_dir=str(p/'supervisor'),timeout_seconds=evaluation_budget(manifest),environment={})
 ns['_trial_job']=job
 return ns,rows

@pytest.mark.parametrize('B',[3600,7200])
def test_real_short_dispatch_same_freeze(tmp_path,B):
 ns,rows=setup(tmp_path,B)
 for row in rows:
  result=ns['dispatch'](tmp_path,row['run_id'])
  assert result['status']=='passed',result
  verified=ns['verify_dispatch'](tmp_path,row,result)
  execution=json.loads(Path(verified['execution']['path']).read_text())
  launch=json.loads(Path(verified['launch']['path']).read_text())
  assert execution['exit_code']==0 and 0<execution['duration_seconds']<5
  assert launch['deadline_monotonic']==launch['started_monotonic']+B
  assert execution['job']['deadline_monotonic']==launch['deadline_monotonic']
  assert execution['job']['timeout_seconds']==launch['child_timeout_seconds']<=B

@pytest.mark.parametrize('change',['child_budget','cross_arm','renew_deadline','freeze_changed'])
def test_frozen_parent_cannot_be_overridden(tmp_path,change):
 ns,rows=setup(tmp_path)
 result=ns['dispatch'](tmp_path,rows[0]['run_id']);p=tmp_path/'runs'/rows[0]['run_id']
 if change=='freeze_changed':save(tmp_path/'plan.json',{'equal_budget_evaluation':{'budget_seconds':14400}})
 elif change in ('child_budget','cross_arm'):
  plan=json.loads((p/'dispatcher-plan.json').read_text());plan['budget_seconds']=14400
  if change=='cross_arm':plan['row']=rows[1]
  save(p/'dispatcher-plan.json',plan)
  attempt=json.loads((p/'attempt.json').read_text());attempt['plan_ref']=pointer(p/'dispatcher-plan.json');attempt['budget_seconds']=14400;save(p/'attempt.json',attempt)
  launch=json.loads((p/'dispatcher-launch.json').read_text());launch['attempt_ref']=pointer(p/'attempt.json');save(p/'dispatcher-launch.json',launch)
 else:
  launch=json.loads((p/'dispatcher-launch.json').read_text());launch['deadline_monotonic']+=1;launch['child_timeout_seconds']+=1;save(p/'dispatcher-launch.json',launch)
 with pytest.raises(ValueError):ns['_load_launch'](tmp_path,rows[0]['run_id'],p/'dispatcher-launch.json',sha(p/'dispatcher-launch.json'))

def test_expired_actual_job_does_not_start(tmp_path):
 marker=tmp_path/'forbidden'
 result=run_job(dict(job_id='expired',argv=[sys.executable,'-c',f"open({str(marker)!r},'w').write('bad')"],
  cwd=str(tmp_path),output_dir=str(tmp_path/'job'),timeout_seconds=7200,deadline_monotonic=time.monotonic()-1))
 assert result['status']=='timeout' and result['process_started'] is False and not marker.exists()

@pytest.mark.parametrize('B',[3600,7200])
def test_teacher_absolute_binding(B):
 objects={}
 def reg(value):
  ref='sha256:'+hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest();objects[ref]=value;return ref
 campaign=reg({'budget_seconds':B});job={'timeout_seconds':B};job_ref=reg(job)
 anchor={'budget_seconds':B,'campaign_ref':campaign,'job_ref':job_ref,'created_at':1};a=reg(anchor)
 launch=dict(schema_version=2,anchor_ref=a,job_ref=job_ref,started_at=2,started_monotonic=10,
  monotonic_deadline=10+B,issued_monotonic=12,child_timeout_seconds=B-2)
 actual=rule_execution_job(objects.__getitem__,anchor,job,launch)
 assert actual==dict(job,timeout_seconds=B-2,deadline_monotonic=10+B)
 for changed in [dict(anchor,budget_seconds=B+1),dict(anchor,campaign_ref=reg({'budget_seconds':B+1}))]:
  with pytest.raises(ValueError):rule_execution_job(objects.__getitem__,changed,job,launch)
 with pytest.raises(ValueError):rule_execution_job(objects.__getitem__,anchor,job,dict(launch,monotonic_deadline=20+B))
 if B==7200:
  with pytest.raises(ValueError):rule_execution_job(objects.__getitem__,anchor,job,None)
 else:assert rule_execution_job(objects.__getitem__,anchor,job,None)==job

def test_worker_preserves_absolute_remaining(tmp_path):
 import asyncio,os,shutil
 calls=[]
 async def inner(*args,**kwargs): calls.append(args[5]);return {'status':'fixture'}
 ns=functions('isolated_eval_worker.py',['run'],dict(os=os,shutil=shutil,_run=inner))
 deadline=time.monotonic()+1
 result=asyncio.run(ns['run'](tmp_path,tmp_path/'worker','model','effort',None,7200,probe=True,deadline_monotonic=deadline))
 assert result=={'status':'fixture'} and len(calls)==1 and 0<calls[0]<=1
 with pytest.raises(TimeoutError):asyncio.run(ns['run'](tmp_path,tmp_path/'expired','model','effort',None,7200,probe=True,deadline_monotonic=time.monotonic()-1))
 assert not (tmp_path/'expired').exists() and len(calls)==1

from task_budget import collection_policy, collection_unit_deadline, CollectionBoundaryStop
POLICY=dict(kind='finish_started_unit_v1',reserve_seconds=500,task_unit_seconds=300,pmu_unit_seconds=200,terminal_seconds=20)

@pytest.mark.parametrize('change',[{'reserve_seconds':320-1},{'reserve_seconds':7200},{'terminal_seconds':False},{'task_unit_seconds':float('inf')},{'kind':'renew_lease'}])
def test_invalid_drain_reserve(change):
 with pytest.raises(ValueError):collection_policy(dict(budget_seconds=7200,collection_stop_policy={**POLICY,**change}))

def test_started_unit_finishes_after_cutoff_without_renewal():
 policy=collection_policy(dict(budget_seconds=7200,collection_stop_policy=POLICY))
 unit=collection_unit_deadline(1000,policy,'task',now=490)
 assert unit==790 and unit<1000
 # The unit can finish at 600 after S=500; no new collection gets a lease.
 with pytest.raises(CollectionBoundaryStop):collection_unit_deadline(1000,policy,'task',now=600)
 assert collection_unit_deadline(1000,None,'task',now=600)==1000

def test_full_pmu_boundary_retains_complete_first_slot(tmp_path,monkeypatch):
 from types import SimpleNamespace as NS
 from contextlib import nullcontext
 runtime=REPO/'skill-libs/graph-base/1.0.0/runtime/src'
 sys.path.insert(0,str(runtime))
 from aprof_runtime.local_evidence import LocalEvidence
 local=LocalEvidence(tmp_path/'records');clock=[400.0];calls=[]
 plan=dict(budget_seconds=7200,collection_stop_policy=POLICY,pmu_scope={'protocol':'CPU','case_id':1,'warmups':0,'captures':2},
  assembly_dir=str(tmp_path),physical_device=0,roles={'baseline':{'path':str(tmp_path)}},source_hashes={'baseline':'CPU'},
  toolchain_refs={'TOOL':'CPU'},cases=[{'metadata_path':str(tmp_path/'meta'),'metadata_ref':'CPU','input_files':{}}])
 build={'deadline_monotonic':1000,'finished_at':0,'binary':{'path':'CPU','sha256':'CPU'}}
 def remaining(d):
  if clock[0]>=d:raise TimeoutError('unit hang watchdog')
  return d-clock[0]
 def run(argv,cwd,prefix,timeout,*args,**kwargs):
  calls.append(argv[0]);prefix.parent.mkdir(parents=True,exist_ok=True)
  if argv[0]=='capture':
   (prefix.parent/'output.bin').write_bytes(b'complete output')
   (prefix.parent/'profile').mkdir();(prefix.parent/'profile/op_summary.csv').write_text('CPU fixture\n')
   clock[0]=510.0 # Complete capture crossed S; oracle still has the fixed unit allowance.
  elif argv[0]=='oracle':
   Path(argv[1]).write_text('{"passed":true}');clock[0]=511.0
  return {'log_hash':local.register_json({'argv':argv,'timeout_seconds':timeout})}
 def files(root,reader):return {p.name:reader.register_artifact(p) for p in root.iterdir()}
 fake=NS(remaining=remaining,save=save,profile_capture=NS(run=run),timing=NS(old=NS(
  select_mount=lambda *a:{'filesystem_type':'tmpfs'},LOCAL_PROFILE_FILESYSTEMS={'tmpfs'},profile_files=files),
  shared=NS(device_lock=lambda *a:nullcontext())))
 def commands(case,role,directory):return ['capture'],['oracle',str(directory/'result.json'),'--result',str(directory/'result.json')],[str(directory/'output.bin')]
 def need(test,msg):
  if not test:raise ValueError(msg)
 ns=functions('task_baseline_pmu.py',['_collect_pmu'],dict(bridge=fake,time=NS(time=lambda:clock[0],monotonic=lambda:clock[0]),
  os=__import__('os'),ROLES=['baseline'],TOOL='TOOL',NPU_SMI='SMI',require=need,collection_policy=collection_policy,
  collection_unit_deadline=lambda d,p,k,**kwargs:collection_unit_deadline(d,p,k,now=kwargs.get('now',clock[0])),CollectionBoundaryStop=CollectionBoundaryStop,
  _commands=commands,capture_argv=lambda c,d:c,_table=lambda f:next(iter(f)),partition_call=lambda *a,**k:None,
  _read=lambda l,r:json.loads(l.verify_artifact(r).read_text()),slot_receipt_value=lambda *a,**k:{'CPU_complete_slot':True}))
 monkeypatch.setenv('ASCEND_RT_VISIBLE_DEVICES','0')
 out=tmp_path/'pmu'
 with pytest.raises(CollectionBoundaryStop):
  ns['_collect_pmu'](local,plan_ref='CPU',build_receipt_ref='CPU',destination=out,deadline=1000,setup=lambda:(plan,build,{}))
 report=json.loads((out/'pmu-report.json').read_text());stop=json.loads((out/'budget-stop.json').read_text())
 assert report['status']=='failed' and report['deadline_monotonic']==1000 and len(report['captures'])==1
 assert 'slot_receipt_ref' in report['captures'][0] and report['captures'][0]['output_refs']
 assert calls.count('capture')==calls.count('oracle')==1
 assert stop['next_unit']=={'role':'baseline','mode':'capture','index':1} and stop['complete'] is False
 assert (out/'baseline/capture/0/completed-local-index.json').is_file() and (out/'partial-local-index.json').is_file()
 assert not (out/'baseline/capture/1').exists()

def test_single_kernel_whole_role_finishes_then_stops(tmp_path):
 from types import SimpleNamespace as NS
 from contextlib import nullcontext
 sys.path.insert(0,str(REPO/'skill-libs/graph-base/1.0.0/runtime/src'))
 from aprof_runtime.local_evidence import LocalEvidence
 local=LocalEvidence(tmp_path/'records');clock=[400.0];calls=[]
 case={'case_id':1,'workload':{},'command':['CPU_BINARY'],'output_files':{r:['{cycle_dir}/'+r+'.bin'] for r in ('baseline','candidate')},
       'verify_commands':{r:['oracle','--result','{cycle_dir}/'+r+'-result.json'] for r in ('baseline','candidate')}}
 config={'physical_device':0,'expected_case_ids':[1],'cases':[case]}
 proof={'operator':'exp','role_kernel_names':{r:[r+'_kernel'] for r in ('baseline','candidate')},
        'roles':{r:{'path':str(tmp_path),'files':{}} for r in ('baseline','candidate')}}
 def remaining(d):
  if clock[0]>=d:raise TimeoutError('unit deadline expired')
  return d-clock[0]
 def capture(cfg,directory,*,deadline_monotonic):
  assert deadline_monotonic==600 and cfg['warmups']==10 and cfg['repeats']==5
  calls.append('whole-role');directory.mkdir();reader=LocalEvidence(directory/'records')
  source=reader.register_json({'schema_version':'1.0.0','files':{}})
  hardware=reader.register_json({'hardware':'CPU fixture'})
  manifest={'role':cfg['role'],'kernel':cfg['kernel'],'case_id':1,'binary_hash':'CPU_HASH','source_hash':source,'hardware_hash':hardware}
  mref=reader.register_json(manifest);index=reader.write_index(directory/'local-index.json')
  (directory.parent/(cfg['role']+'.bin')).write_bytes(b'full role output');clock[0]=510
  return {'manifest_hash':mref,'local_index':str(index)}
 def run(argv,cwd,prefix,timeout,reader):
  calls.append('oracle');v={'passed':True,'case_id':1};Path(argv[-1]).write_text(json.dumps(v));clock[0]=511
  text=json.dumps(v);path=prefix.with_suffix('.stdout.log');path.write_text(text)
  return {'text':text,'stdout_hash':reader.register_artifact(path),'log_hash':reader.register_json({'CPU_oracle':True})}
 fake_time=NS(monotonic=lambda:clock[0],time=lambda:clock[0])
 # Execute the proposed helper with its real per-role structure; CPU effects are explicitly fixture-only.
 ns=functions('local_controller_bridge.py',['capture_mechanism','verify_mechanism_oracle'],dict(time=fake_time,
  checked_build=lambda *a:(proof,{'binary':{'path':'CPU_BINARY','sha256':'CPU_HASH'}}),ROLES=('baseline','candidate'),
  remaining=remaining,save=save,file_hash=sha,LocalEvidence=LocalEvidence,profile_capture=NS(capture=capture,run=run),
  timing=NS(replay_task_budget=lambda *a,**k:{'deadline_monotonic':1000,'collection_stop_policy':POLICY},
            shared=NS(device_lock=lambda *a:nullcontext())),
  load_capture_manifest=lambda r,ref:json.loads(r.verify_artifact(ref).read_text()),
  expand_specs=lambda *a:None,normalize_profile=lambda *a:{'CPU_normalized':True},
  merge_index=lambda r,p:[r.register_artifact(v) for v in json.loads(Path(p).read_text())['artifacts'].values()],
  adapter=NS(source_identity=lambda *a:proof)))
 # The imported common helper normally reads monotonic time; pin only that clock for this controlled crossing.
 import task_budget
 original=task_budget.collection_unit_deadline
 def deadline(d,p,k,**kwargs):return original(d,p,k,now=kwargs.get('now',clock[0]))
 task_budget.collection_unit_deadline=deadline
 try:
  with pytest.raises(CollectionBoundaryStop):ns['capture_mechanism'](tmp_path,'CPU',config,
   {'case_id':1,'kernel':'exp_kernel','metric':'metric','expected_direction':'decrease'}, {'metric':{}},tmp_path/'profile',local,
   deadline=1000,budget_binding={'kind':'teacher','launch_ref':'CPU'})
 finally:task_budget.collection_unit_deadline=original
 assert calls==['whole-role','oracle']
 assert (tmp_path/'profile/baseline-completed.json').is_file()
 assert not (tmp_path/'profile/candidate').exists()
 stop=json.loads((tmp_path/'profile/budget-stop.json').read_text())
 assert stop['next_unit']=={'role':'candidate'} and stop['scope']=='whole_role_10warmups_5captures_original_oracle'

def test_real_hanging_command_keeps_failed_receipt(tmp_path):
 result=run_job(dict(job_id='hang',argv=['/bin/sh','-c','printf started; sleep 3'],
  cwd=str(tmp_path),output_dir=str(tmp_path/'job'),timeout_seconds=.5,deadline_monotonic=time.monotonic()+.5))
 assert result['status']=='timeout' and result['process_started'] is True
 assert (tmp_path/'job/execution.json').is_file() and 'started' in (tmp_path/'job/stdout.log').read_text()

@pytest.mark.parametrize('B,new_launch',[(3600,False),(3600,True),(7200,True)])
def test_real_outer_roster_preserves_history_and_bound_budget(tmp_path,B,new_launch):
 from datetime import datetime,timezone
 sys.path.insert(0,str(REPO/'skill-libs/graph-base/1.0.0/runtime/src'))
 from aprof_runtime.local_evidence import LocalEvidence
 spec=importlib.util.spec_from_file_location('budget_outer',S/'task_rule_admission.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 text=(REPO/'scaffolding/tests/test_task_rule_admission.py').read_text()
 text=text.replace('timeout_seconds=3600','timeout_seconds=B').replace('budget_seconds=3600','budget_seconds=B')
 text=text.replace('    protocol = {**anchor,',"    if new_launch: anchor['campaign_ref']=save({'budget_seconds':B})\n    protocol = {**anchor,")
 text=text.replace('    values["protocol"]["anchor_ref"] = anchor_ref', '''    if new_launch:
        launch=dict(schema_version=2,anchor_ref=anchor_ref,job_ref=anchor['job_ref'],started_at=100,
            started_monotonic=10,monotonic_deadline=10+B,issued_monotonic=11,child_timeout_seconds=B-1)
        values['protocol']['dispatcher_launch_ref']=save(launch)
        values['execution']['job']=dict(job,timeout_seconds=B-1,deadline_monotonic=10+B)
    values["protocol"]["anchor_ref"] = anchor_ref''')
 body=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name in ('iso','fixture')]
 ns=dict(LocalEvidence=LocalEvidence,datetime=datetime,timezone=timezone,json=json,B=B,new_launch=new_launch,
         PROTOCOL=module.PROTOCOL,TASK_PROTOCOL=module.TASK_PROTOCOL,STAGES=module.STAGES)
 exec(compile(ast.Module(body=body,type_ignores=[]),'original-roster-fixture','exec'),ns)
 local,report,expected=ns['fixture'](tmp_path)
 result=module.verify_task_attempt_roster(local,local.register_json(report),expected=expected)
 assert result['valid'] is True and result['admission_authority'] is False
 assert result['actual_duration_seconds']==20

@pytest.mark.parametrize('renew',[False,True])
def test_recorder_binds_actual_original_launch(tmp_path,renew):
 from copy import deepcopy
 sys.path.insert(0,str(REPO/'skill-libs/graph-base/1.0.0/runtime/src'))
 from aprof_runtime.local_evidence import LocalEvidence
 from timing_admission import number,read,require
 import task_rule_admission as admission
 local=LocalEvidence(tmp_path/'records');ref=local.register_json({'CPU_fixture':True})
 mono=time.monotonic();wall=time.time();deadline=mono+7200
 jobref=local.register_json({'timeout_seconds':7200})
 planref=local.register_json({'launch_path':str(tmp_path/'dispatcher-launch.json')})
 anchor=dict(schema_version=1,protocol=admission.PROTOCOL,task_protocol=admission.TASK_PROTOCOL,purpose='promotion',
  operator='exp',run_id='CPU',candidate_id='CPU',source_hashes={'baseline':ref,'candidate':ref},created_at=wall-1,
  budget_seconds=7200,campaign_ref=local.register_json({'budget_seconds':7200}),controller_plan_ref=planref,
  job_ref=jobref,history_refs=[ref],**{k:ref for k in ('input_inventory_ref','boundary_plan_ref','screen_plan_ref','profile_plan_ref','source_review_ref')})
 aref=local.register_json(anchor)
 save(tmp_path/'dispatcher-launch.json',dict(schema_version=2,anchor_ref=aref,job_ref=jobref,started_at=wall,
  started_monotonic=mono,monotonic_deadline=deadline,issued_monotonic=mono+.01,child_timeout_seconds=deadline-(mono+.01)))
 tree=ast.parse((S/'task_rule_recorder.py').read_text())
 body=[n for n in tree.body if isinstance(n,ast.ClassDef) or isinstance(n,ast.Assign)]
 ns=dict(deepcopy=deepcopy,json=json,Path=Path,time=time,LocalEvidence=LocalEvidence,
  IDENTITY=admission.IDENTITY,PROTOCOL=admission.PROTOCOL,TASK_PROTOCOL=admission.TASK_PROTOCOL,STAGES=admission.STAGES,
  number=number,read=read,require=require,rule_execution_job=rule_execution_job)
 exec(compile(ast.Module(body=body,type_ignores=[]),str(S/'task_rule_recorder.py'),'exec'),ns)
 post=dict(binary_hashes={'baseline':ref,'candidate':ref},oracle_files={'CPU':ref},task_config_ref=ref,
           profile_configs={'baseline':ref,'candidate':ref})
 if renew:
  with pytest.raises(ValueError,match='deadline'):ns['TaskRuleRecorder'](local,tmp_path/'admission',anchor_ref=aref,post_build=post,deadline=deadline+1)
 else:
  recorder=ns['TaskRuleRecorder'](local,tmp_path/'admission',anchor_ref=aref,post_build=post,deadline=deadline)
  protocol=json.loads(local.verify_artifact(recorder.protocol_ref).read_text())
  assert protocol['dispatcher_launch_ref']==sha(tmp_path/'dispatcher-launch.json')
  assert protocol['budget_seconds']==7200 and recorder.deadline==deadline

@pytest.mark.parametrize('mutation',[None,'missing','renewed','after_soft_stop','before_unit','capture_timeout','oracle_late','wrong_profile'])
def test_whole_role_unit_independent_replay(tmp_path,monkeypatch,mutation):
 monkeypatch.setenv('APROF_SKILL_LIB',str(REPO/'skill-libs/graph-base/1.0.0'))
 from aprof_runtime.local_evidence import LocalEvidence
 from aprof_runtime import task_window_measurement_admission as runtime
 from timing_admission import number,read,require
 local=LocalEvidence(tmp_path/'records');stream=tmp_path/'stream';stream.write_text('{}')
 stream_ref=local.register_artifact(stream)
 source=REPO/'skill-libs/graph-base/1.0.0/runtime/src/aprof_runtime/task_window_measurement_admission.py'
 nodes=[n for n in ast.parse(source.read_text()).body if isinstance(n,ast.FunctionDef)
        and n.name in ('collection_unit_deadline','replay_collection_unit')]
 ns=dict(_load=lambda r,k:read(r,k),_need=require,_number=number,ContractError=ValueError)
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
 monkeypatch.setattr(runtime,'replay_collection_unit',ns['replay_collection_unit'],raising=False)
 def execution(at,argv):
  value=dict(argv=argv,exit_code=0,error=None,started_at=at,ended_at=at+.1,timeout_seconds=1,
             stdout_hash=stream_ref,stderr_hash=stream_ref)
  return dict(value,log_hash=local.register_json(value))
 refs=[];profiles={}
 for index,role in enumerate(('baseline','candidate')):
  start=100+index*30;mono=start
  unit=dict(schema_version=1,started_at=start,started_monotonic=mono,deadline_monotonic=mono+200)
  if role=='baseline' and mutation=='renewed':unit['deadline_monotonic']+=1
  if role=='baseline' and mutation=='after_soft_stop':unit.update(started_monotonic=501,deadline_monotonic=701)
  manifest=dict(role=role,policy=dict(warmups=10,repeats=5),warmup_runs=[],captures=[])
  for i in range(10):
   e=execution(start+1+i,['warmup'])
   if role=='baseline' and i==0 and mutation=='before_unit':e=execution(start-1,['warmup'])
   manifest['warmup_runs'].append(dict(argv=e['argv'],exit_code=0,log_hash=e['log_hash']))
  for i in range(5):
   e=execution(start+12+i,['capture'])
   if role=='baseline' and i==0 and mutation=='capture_timeout':
    e['timeout_seconds']=500;e['log_hash']=local.register_json({k:v for k,v in e.items() if k!='log_hash'})
   cap=local.register_json({'capture':e})
   manifest['captures'].append(dict(capture_id=f'capture-{i:03d}',argv=e['argv'],exit_code=0,log_hash=cap))
  pref=local.register_json({'capture_manifest_hash':local.register_json(manifest)})
  profiles[role]=pref
  oracle=execution(start+20 if mutation!='oracle_late' or role!='baseline' else start+201,['oracle'])
  oracle['timeout_seconds']=120
  oracle['log_hash']=local.register_json({k:v for k,v in oracle.items() if k!='log_hash'})
  sealed=dict(kind='complete_role_collection_v1',role=role,profile_ref=pref,oracle_ref=oracle['log_hash'],
              collection_unit_ref=local.register_json(unit),finished_at=oracle['ended_at'])
  if role=='baseline' and mutation=='wrong_profile':sealed['profile_ref']=stream_ref
  refs.append(local.register_json(sealed))
 mechanism=local.register_json({'metrics':[dict(baseline_profile_hash=profiles['baseline'],candidate_profile_hash=profiles['candidate'])]})
 evidence=[mechanism,stream_ref,*refs]
 if mutation=='missing':evidence.pop()
 ns=functions('task_rule_admission.py',['_verify_profile_units'],dict(require=require,read=read,number=number))
 args=(local,{'mechanism_report_ref':mechanism},evidence,[90,151],
       dict(schema_version=2,started_monotonic=0,monotonic_deadline=1000),POLICY)
 if mutation:
  expected={'missing':'receipts missing','renewed':'deadline','after_soft_stop':'soft budget',
    'before_unit':'outside its registered stage','capture_timeout':'timeout escaped',
    'oracle_late':'oracle escaped','wrong_profile':'profile differs'}[mutation]
  with pytest.raises(ValueError,match=expected):ns['_verify_profile_units'](*args)
 else:ns['_verify_profile_units'](*args)
