"""CPU-only retained RMS oracle proof fixtures: no compiler or NPU calls."""
from pathlib import Path
import hashlib,io,json,shutil,sys,tarfile,copy
import pytest,torch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import level2_failure_classification as c
from level2_adapters import workload_metadata
from aprof_runtime.planning import select_dispatch
torch.set_num_threads(2)
F=Path(__file__).parent/'fixtures/rms_boundary'
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'sha256':sha(p)}
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True)+'\n');return p
def write(p,b):p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b if isinstance(b,bytes) else b.encode());return p
def load(p):return json.loads(p.read_text())
def raw(p,x):return write(p,x.contiguous().view(torch.uint8).numpy().tobytes())
def process(argv,cwd,task,code=0):
 argv=list(map(str,argv));setup=f'source {task}/sdk/set_env.sh || exit $?; export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:${{LD_LIBRARY_PATH:-}}; exec "$@"'
 return dict(argv=argv,cwd=str(cwd),environment_overrides={},started_at=1,finished_at=2,exit_status=code,status='passed' if code==0 else 'failed',error=None if code==0 else f'process failed ({code}): {argv[0]}',shell_argv=['taskset','-c','40-43' if '-B' in argv else '8','bash','-c',setup,'feedback-hardware',*argv])
def refresh(task,parent):
 root=parent/'boundary-validation';request=load(root/'request.json')
 for k in ('script','binary','dispatch_plan'):request[k]=ref(Path(request[k]['path']))
 save(root/'request.json',request);guard=load(root/'completion.json');guard['request']=ref(root/'request.json')
 for row in guard['cases']:row['execution']=ref(Path(row['execution']['path']))
 save(root/'completion.json',guard);previous=None;events=[]
 for i,(kind,value) in enumerate([('boundary_validation_started',{'candidate':parent.name,'request':ref(root/'request.json')}),('boundary_validation_completed',{'candidate':parent.name,'completion':ref(root/'completion.json')})]):
  row=dict(sequence=i,previous_hash=previous,kind=kind,value=value,recorded_at=str(i));row['hash']='sha256:'+hashlib.sha256((json.dumps(row,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()).hexdigest();previous=row['hash'];events.append(row)
 write(task/'events.jsonl',''.join(json.dumps(r)+'\n' for r in events));return guard
@pytest.fixture
def fixture(tmp_path):
 task=tmp_path/'run/train/tasks/rms_norm';parent=task/'candidates/rms_norm002';root=parent/'boundary-validation';source=parent/'op';agent=task/'agent';agent.mkdir(parents=True)
 for name in ('boundary_guard.py','boundary_cases.json'):shutil.copyfile(F/name,agent/name)
 (task/'baseline/scripts').mkdir(parents=True);shutil.copyfile(F/'verify_result.py',task/'baseline/scripts/verify_result.py')
 write(task/'sdk/set_env.sh','# CPU fixture only\n');host=write(source/'op_host/rms_norm.asc','#include "../op_kernel/rms_norm_kernel.asc"\n');kernel=write(source/'op_kernel/rms_norm_kernel.asc','// immutable original source fixture\n')
 h=hashlib.sha256()
 with tarfile.open(parent/'source.tar','w') as tar:
  for p in (host,kernel):
   name=str(p.relative_to(source));b=p.read_bytes();m=tarfile.TarInfo('source/'+name);m.size=len(b);tar.addfile(m,io.BytesIO(b));h.update(name.encode()+b'\0'+b+b'\0')
 binary=write(parent/'build/build/standalone','fixture-only executable bytes')
 save(parent/'build/build_manifest.json',{'operator':'rms_norm','standalone':ref(binary),'roles':{r:{'source_sha256':h.hexdigest(),'source_dir':str(source)} for r in 'AB'}})
 save(parent/'stages/build/result.json',{'status':'passed','candidate_id':parent.name,'kind':'build','error':None});save(parent/'stages/build/stage-plan.json',{'source_hash':sha(parent/'source.tar')})
 plan={'schema_version':'1.0.0','operator':'rms_norm','dispatch_id':'rms-proof','source_hash':sha(parent/'source.tar'),'architecture_profile_ref':'sha256:'+'1'*64,'parallel_plan_ref':'sha256:'+'2'*64,'entries':[],'fallback':{'group_id':'generic','tiling_key':0,'kernel_entry':'rms_norm_generic','conditions':[],'required_capabilities':[]}}
 for key,entry,conditions in [(10,'short_rows',[{'field':'attributes.hidden','op':'ne','value':2},{'field':'attributes.hidden','op':'le','value':128}]),(11,'full_row',[{'field':'attributes.hidden','op':'gt','value':128}]),(12,'pair_rows',[{'field':'attributes.hidden','op':'eq','value':2}])]:plan['entries'].append({'group_id':entry,'tiling_key':key,'kernel_entry':'rms_norm_'+entry,'conditions':conditions,'required_capabilities':['vector']})
 save(parent/'dispatch_plan.json',plan)
 save(root/'request.json',{'version':'level2_semantic_guards_v1','operator':'rms_norm','candidate':parent.name,'dispatch_logs_required':True,'script':ref(agent/'boundary_guard.py'),'binary':ref(binary),'dispatch_plan':ref(parent/'dispatch_plan.json')})
 for name in ('health-before.json','health-after.json'):save(root/name,{'status':'passed','exit_status':0,'error':None})
 rows=[];commands=[];prepared=[];verified=[]
 for case in load(agent/'boundary_cases.json')['cases']:
  name=case['name'];shape=case['shape'];dt=getattr(torch,case['dtype']);n=__import__('math').prod(shape);dest=root/'inputs'/name
  if 'values' in case:x=torch.tensor([{'nan':float('nan'),'inf':float('inf'),'-inf':-float('inf')}.get(v,v) if isinstance(v,str) else v for v in case['values']],dtype=dt).reshape(shape)
  else:x=(((torch.arange(n)*17%31)-15).float()/8).to(dt).reshape(shape)
  gamma=torch.linspace(.75,1.25,shape[-1]).to(dt);expected=(x.float()*torch.rsqrt((x.float()*x.float()).mean(-1,keepdim=True)+case['epsilon'])*gamma.float()).to(dt);actual=expected.clone();bad='special' in name
  if bad:actual[1,:]=float('nan')
  for filename,t in [('input.bin',x),('gamma.bin',gamma),('expected.bin',expected),('output.bin',actual)]:raw(dest/filename,t)
  selected=select_dispatch(plan,workload_metadata('rms_norm',{'shape':shape,'dtype':case['dtype']}));argv=['--shape',','.join(map(str,shape)),'--x',str(dest/'input.bin'),'--gamma',str(dest/'gamma.bin'),'--epsilon',str(case['epsilon']),'--dtype',case['dtype'],'--output',str(dest/'output.bin'),'--device','0']
  commands.append(dict(name=name,argv=argv,expected_key=selected['tiling_key'],reference=str(dest/'expected.bin')))
  before=dict(name=name,dispatch=selected,expected_shape=shape,status='cpu_reference_prepared_not_hardware_verified');prepared.append(before);verified.append({**before,'passed':not bad,'status':'hardware_output_failed' if bad else 'hardware_output_verified'})
  directory=root/'executions'/name;save(directory/'execution.json',process([binary,*argv],source,task));log={'tiling_key':selected['tiling_key'],'kernel_entry':selected['kernel_entry']};write(directory/'stdout.log','APROF_DISPATCH_JSON:'+json.dumps(log)+'\n');write(directory/'stderr.log','')
  rows.append(dict(name=name,execution=ref(directory/'execution.json'),expected_process_passed=True,dispatch_log_passed=True,dispatch_logs=[log],error=None))
 save(root/'inputs/coordinator_commands.json',commands)
 for filename,values in [('cpu_preparation.json',prepared),('verification.json',verified)]:save(root/'inputs'/filename,dict(operator='rms_norm',hardware_executed_by_this_script=False,results=values))
 for label,code in [('prepare',0),('verify',1)]:
  argv=['/usr/bin/python','-B',agent/'boundary_guard.py','--output',root/'inputs',*(['--verify'] if code else []),'--plan',parent/'dispatch_plan.json'];save(root/label/'execution.json',process(argv,task,task,code));write(root/label/'stderr.log','');write(root/label/'stdout.log',json.dumps(dict(operator='rms_norm',cases=10,mode='verify_existing_outputs' if code else 'cpu_only',passed=not bool(code)))+'\n')
 save(root/'completion.json',dict(version='level2_semantic_guards_v1',operator='rms_norm',candidate=parent.name,request=ref(root/'request.json'),status='failed',cases=rows,error=None,verification_error={'type':'RuntimeError','message':'process failed (1): /usr/bin/python'}))
 from msprof_exploration_campaign import create_fresh
 ledger=create_fresh(task.parents[1]/'ledger',campaign_id='rms-fixture',workloads={'rms_norm':{'baseline_source_hash':'sha256:'+'8'*64,'source_split':'train','repeat_by_case':{str(i):10 for i in range(1,21)},'pilot_ref':'sha256:'+'6'*64}},provenance={})
 for kind in ('build','correctness','runtime'):
  sid='baseline-'+kind;ledger.start(event_id=sid+'-start',workload='rms_norm',candidate_id=None,stage_id=sid,kind=kind,plan={'source_hash':'sha256:'+'8'*64,'case_ids':list(range(1,21))})
  ledger.finish(event_id=sid+'-finish',workload='rms_norm',stage_id=sid,outcome='success',native_started=kind!='build',evidence={'prepared_output_checked':kind=='correctness','fixture_only':True,'record_ref':'sha256:'+'5'*64})
 ledger.register(event_id='register',workload='rms_norm',candidate_id=parent.name,source_hash=sha(parent/'source.tar'),patch_hash='sha256:'+'7'*64,source_parent={'candidate_id':None,'source_hash':'sha256:'+'8'*64},decision_basis=[],artifacts={'source':ref(parent/'source.tar'),'dispatch_plan':ref(parent/'dispatch_plan.json')})
 ledger.start(event_id='start',workload='rms_norm',candidate_id=parent.name,stage_id=parent.name+'-build',kind='build',plan={'source_hash':sha(parent/'source.tar')})
 ledger.finish(event_id='finish',workload='rms_norm',stage_id=parent.name+'-build',outcome='success',native_started=False,evidence={'build':ref(parent/'build/build_manifest.json'),'result':ref(parent/'stages/build/result.json')})
 return task,parent,refresh(task,parent)

def test_bound_original_oracle_nonfinite_failure_is_positive(fixture):
 t,p,g=fixture;r=c.classify_failure(t,p,guard=g);assert r['status']=='source_attempt_failed',r;assert r['rule']=='original_rms_boundary_nonfinite_mismatch';assert len(r['event_bindings'])==2

@pytest.mark.parametrize('mutation',['source','archive','binary','build_status','health','missing_case','spec','script','verifier','input','gamma','reference','output_tail','output_missing','native_exit','native_stderr','cpu_stderr','verify_argv','prepare_env','dispatch','verify_json','verify_stdout','events','all_pass','finite_only'])
def test_unproven_or_tampered_rms_evidence_is_blocked(fixture,mutation):
 t,p,g=fixture;root=p/'boundary-validation';name='special_short_row';dest=root/'inputs'/name
 def change(path,key,value):v=load(path);v[key]=value;save(path,v)
 if mutation=='source':write(p/'op/op_kernel/rms_norm_kernel.asc','changed')
 elif mutation=='archive':write(p/'source.tar',b'bad tar')
 elif mutation=='binary':write(p/'build/build/standalone','changed')
 elif mutation=='build_status':change(p/'stages/build/result.json','status','failed')
 elif mutation=='health':change(root/'health-after.json','status','failed')
 elif mutation=='missing_case':g['cases']=g['cases'][:-1];save(root/'completion.json',g)
 elif mutation in ('spec','script','verifier'):
  path={'spec':t/'agent/boundary_cases.json','script':t/'agent/boundary_guard.py','verifier':t/'baseline/scripts/verify_result.py'}[mutation];write(path,path.read_bytes()+b'\n')
 elif mutation in ('input','gamma','reference'):
  path=dest/{'input':'input.bin','gamma':'gamma.bin','reference':'expected.bin'}[mutation];write(path,bytes(path.stat().st_size))
 elif mutation=='output_tail':write(dest/'output.bin',(dest/'output.bin').read_bytes()+b'!')
 elif mutation=='output_missing':(dest/'output.bin').unlink()
 elif mutation=='native_exit':change(root/'executions'/name/'execution.json','exit_status',-9)
 elif mutation=='native_stderr':write(root/'executions'/name/'stderr.log','ACL error')
 elif mutation=='cpu_stderr':write(root/'verify/stderr.log','Traceback\n')
 elif mutation=='verify_argv':change(root/'verify/execution.json','argv',['/usr/bin/python','wrong.py'])
 elif mutation=='prepare_env':change(root/'prepare/execution.json','environment_overrides',{'LD_PRELOAD':'bad'})
 elif mutation=='dispatch':write(root/'executions'/name/'stdout.log','APROF_DISPATCH_JSON:{"tiling_key":0,"kernel_entry":"wrong"}\n')
 elif mutation=='verify_json':change(root/'inputs/verification.json','hardware_executed_by_this_script',True)
 elif mutation=='verify_stdout':write(root/'verify/stdout.log','{"passed":true}\n')
 elif mutation=='events':write(t/'events.jsonl','{}\n')
 elif mutation in ('all_pass','finite_only'):
  results=load(root/'inputs/verification.json')
  for row in results['results']:
   d=root/'inputs'/row['name'];write(d/'output.bin',(d/'expected.bin').read_bytes());row.update(passed=True,status='hardware_output_verified')
  if mutation=='finite_only':
   d=root/'inputs/hidden_128';x=torch.ones(5,128);raw(d/'output.bin',x);results['results'][1].update(passed=False,status='hardware_output_failed')
  save(root/'inputs/verification.json',results)
 if mutation not in ('binary','events'):g=refresh(t,p)
 r=c.classify_failure(t,p,guard=g);assert r['status']=='infrastructure_blocked',r

@pytest.mark.parametrize('mutation',['self_rebound_binary','self_rebound_plan','ledger_bytes'])
def test_registered_identities_cannot_be_replaced_by_local_self_rehash(fixture,mutation):
 t,p,g=fixture;root=p/'boundary-validation'
 if mutation=='self_rebound_binary':
  binary=p/'build/build/standalone';write(binary,'different executable')
  build=load(p/'build/build_manifest.json');build['standalone']=ref(binary);save(p/'build/build_manifest.json',build)
  g=refresh(t,p)
 elif mutation=='self_rebound_plan':
  path=p/'dispatch_plan.json';plan=load(path);plan['dispatch_id']='changed';save(path,plan);g=refresh(t,p)
 else:write(t.parents[1]/'ledger/events.jsonl','{}\n')
 r=c.classify_failure(t,p,guard=g);assert r['status']=='infrastructure_blocked',r

def test_later_append_preserves_exact_closed_proof_identity(fixture):
 from msprof_exploration_campaign import Campaign
 t,p,g=fixture;before=c.classify_failure(t,p,guard=g);assert before['status']=='source_attempt_failed'
 ledger=Campaign(t.parents[1]/'ledger');ledger.observe(event_id='later-observation',workload='rms_norm',candidate_id=p.name,observation_id='later-observation',stage_ids=[p.name+'-build'],feedback={'fixture':'later unrelated observation'},close_feedback=False)
 assert c.classify_failure(t,p,guard=g)==before
