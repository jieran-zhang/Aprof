"""Data-only certificate fixture; execution/campaign integration has separate tests."""
import copy,json
from pathlib import Path
import pytest
import level2_stage_recovery as r


def put(p,v):
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(r.canonical(v)+b'\n');return ref(p)
def ref(p):return {'path':str(p),'sha256':r.sha(p.read_bytes())}
def journal(p,events,config):
 rows=[];previous='sha256:'+'0'*64
 for n,(op,args) in enumerate(events):
  v={'sequence':n,'event_id':'genesis' if n==0 else f'e{n}','operation':op,'arguments':args,'recorded_at':'fixture','previous_hash':previous,'config_hash':r.digest(config)};v['hash']=r.digest(v);previous=v['hash'];rows.append(v)
 p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b''.join(r.canonical(v)+b'\n' for v in rows));return rows

@pytest.fixture
def certified(tmp_path):
 run=tmp_path/'run';task=run/'validation/tasks/group_norm';stage=task/'candidates/group_norm002/stages/final';ledger=run/'validation/ledger';directory=stage/'prestart-recovery'
 plan={'purpose':'final','case_ids':list(range(1,21)),'cohorts':[{'relation':'direct_parent'}]};planref=put(stage/'stage-plan.json',plan)
 costs={'native_processes_started':0,'native_processes_completed':0,'role_samples':0,'wall_seconds':0}
 original=put(stage/'result.json',{'status':'failed','kind':'timing','stage_id':'group_norm002-final','candidate_id':'group_norm002','error':r.FAILURE,'native_started':False,'actual_costs':costs})
 candidate={'candidate_id':'group_norm002','source_hash':'sha256:'+'a'*64};start={'workload':'group_norm','candidate_id':'group_norm002','stage_id':'group_norm002-final','kind':'timing','plan':plan};finish={'workload':'group_norm','stage_id':start['stage_id'],'outcome':'failed','evidence':{'result':original},'native_started':False,'formal_samples':0,'actual_costs':costs,'reason':'import failure'}
 config={'fixture':'explicit data-only'};put(ledger/'config.json',config);put(ledger/'config.sha256.json',{'sha256':r.digest(config)})
 events=[('prepare',{}),('register',{'workload':'group_norm',**candidate}),('start',start),('finish',finish)];rows=journal(ledger/'events.jsonl',events,config)
 directory.mkdir();(directory/'ledger-prefix.jsonl').write_bytes((ledger/'events.jsonl').read_bytes())
 task_event={'sequence':0,'recorded_at':'fixture','kind':'stage_completed','previous_hash':None,'value':{'result':original}}
 task_event['hash']=r.sha((json.dumps(task_event,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode());(task/'events.jsonl').write_bytes((json.dumps(task_event,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode());(directory/'task-events-prefix.jsonl').write_bytes((task/'events.jsonl').read_bytes())
 campaign_manifest=put(run/'campaign-manifest.json',{'run':'fixture'});task_manifest=put(task/'manifest.json',{'operator':'group_norm'})
 producer_sets=[];engrefs=[]
 for n in (22,23):
  files=[];refs=[]
  for name in sorted(r.REQUIRED_PRODUCERS):
   p=tmp_path/'repo/scripts'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(f'# inert code {n} {name}\n');v=ref(p);snap=run/'bootstrap/source-cas'/v['sha256'][7:];snap.parent.mkdir(parents=True,exist_ok=True);snap.write_bytes(p.read_bytes());refs.append(v);files.append({**v,'snapshot':str(snap)})
  engrefs.append(put(run/f'bootstrap/frozen-engineering-{n:03d}.json',{'version':'level2_frozen_engineering_v1','files':files,'campaign_manifest':campaign_manifest,'task_manifests':[task_manifest]}));producer_sets.append(refs)
 final=put(task/'finalization/request.json',{'operator':'group_norm','case_ids':list(range(1,21)),'evaluation_candidate_ids':['group_norm002'],'final_plans':{'group_norm002':planref},'producers':producer_sets[0]})
 kept_dir=run/'storage/maintenance/group-norm002-final-zero-native-022-20261006';kept_dir.mkdir(parents=True)
 kept_files=[]
 for name,origin in [('stage-result.json',original),('stage-plan.json',planref),('finalization-request.json',final),('invocation.log',{'path':'/tmp/aprof-gn002-final-022-20261006.log','sha256':r.sha(b'import failed\n')}),('task-events-prefix.jsonl',ref(task/'events.jsonl')),('ledger-events-prefix.jsonl',ref(ledger/'events.jsonl'))]:
  (kept_dir/name).write_bytes(b'import failed\n' if name=='invocation.log' else Path(origin['path']).read_bytes());kept_files.append({'original':origin,'retained':ref(kept_dir/name)})
 preservation=put(kept_dir/'preservation.json',{'version':'level2_zero_native_failure_preservation_v1','status':'infrastructure_blocked','stage':start['stage_id'],'error':r.FAILURE,'files':kept_files,'request':final,'stage_directory_inventory':['result.json','stage-plan.json'],'native_processes_started':0,'role_samples':0,'observed_process_exit_code':1,'recovery_executed':False,'original_stage_and_ledger_preserved':True,'source_attempt_count_unchanged':True,'recorded_at':'fixture','invocation_environment_correction':'explicit src bootstrap'})
 args={'workload':'group_norm','stage_id':start['stage_id'],'source_hash':candidate['source_hash'],'plan_hash':r.digest(plan),'failed_result':original,'reason':'explicit recovery of import path only'}
 cert={'version':r.VERSION,'arguments':args,'stage_plan':planref,'finalization_request':final,'preservation':preservation,'ledger_prefix':ref(directory/'ledger-prefix.jsonl'),'task_event_prefix':ref(directory/'task-events-prefix.jsonl'),'old_engineering':engrefs[0],'recovery_engineering':engrefs[1],'producers':producer_sets[1],'stage_files_before':sorted([original,planref],key=lambda x:x['path']),'native_started':False,'formal_samples':0,'actual_costs':costs,'failure':r.FAILURE,'authorizes':'one_same_stage_attempt_no_budget_reset'}
 qualification=put(directory/'qualification.json',cert);args={**args,'qualification':qualification}
 first=r.project_stage(rows,'group_norm',start['stage_id']);r.validate_certificate(stage,first,candidate,args)
 q={'sequence':1,'recorded_at':'fixture','kind':'stage_prestart_qualified','previous_hash':task_event['hash'],'value':{'candidate_id':'group_norm002','stage':start['stage_id'],'qualification':qualification,'failed_result':original}}
 q['hash']=r.sha((json.dumps(q,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode())
 with (task/'events.jsonl').open('ab') as stream:stream.write((json.dumps(q,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode())
 events.extend([('qualify_prestart',args),('start',start)])
 recovery_costs={'native_processes_started':6,'native_processes_completed':6,'role_samples':14400,'wall_seconds':12}
 new=put(stage/'result.recovery-01.json',{'status':'passed','kind':'timing','stage_id':start['stage_id'],'candidate_id':'group_norm002','error':None,'native_started':True,'actual_costs':recovery_costs,'prestart_recovery':{'qualification':qualification,'previous_result':original,'attempt':2}})
 events.append(('finish',{**finish,'outcome':'success','evidence':{'result':new,'qualification':qualification},'native_started':True,'formal_samples':14400,'actual_costs':recovery_costs,'reason':None}))
 rows=journal(ledger/'events.jsonl',events,config);projected=r.project_stage(rows,'group_norm',start['stage_id'])
 return {'stage':stage,'task':task,'run':run,'ledger':ledger,'config':config,'events':events,'rows':rows,'candidate':candidate,'state':projected,'args':args,'certificate':cert,'original':original,'current':new}


def test_ordinary_no_ledger_dependencies(tmp_path):
 stage=tmp_path/'stage';original=put(stage/'result.json',{'status':'passed','error':None})
 value=r.resolve_from_reader(stage,require_success=True);assert value=={'current_result':original,'original_failed_result':None,'qualification':None,'protected':[],'event_bindings':[]}

def test_certified_failed_then_real_success_and_immutable_prefix(certified):
 f=certified;v=r.resolve_from_reader(f['stage'],require_success=True)
 assert v['current_result']==f['current'] and v['original_failed_result']==f['original'] and v['qualification']==f['args']['qualification']
 assert len(v['event_bindings'])==2 and str(f['ledger']/'events.jsonl') not in {p['path'] for p in v['protected']}
 assert json.loads(Path(f['original']['path']).read_bytes())['status']=='failed'
 # Unrelated legitimate journal suffix never changes the qualified result.
 extra=[*f['events'],('checkpoint',{'checkpoint_id':'unrelated'})];journal(f['ledger']/'events.jsonl',extra,f['config'])
 assert r.resolve_from_reader(f['stage'],require_success=True)==v

@pytest.mark.parametrize('fault',['error','oldresult','prefix','qualification','newresult','sourcecas','missing_helper','bool_cost','bool_samples','bool_recoveries','wrong_new_path','missing_binding'])
def test_tamper_rejects(certified,fault):
 f=certified;stage=f['stage'];state=copy.deepcopy(f['state'])
 if fault=='error':v=json.loads(Path(f['original']['path']).read_bytes());v['error']={'type':'ValueError','message':'unknown'};put(Path(f['original']['path']),v)
 elif fault=='oldresult':Path(f['original']['path']).write_bytes(b'changed')
 elif fault=='prefix':(stage/'prestart-recovery/ledger-prefix.jsonl').write_bytes(b'changed')
 elif fault=='qualification':Path(f['args']['qualification']['path']).write_bytes(b'{}')
 elif fault=='newresult':Path(f['current']['path']).write_bytes(b'{}')
 elif fault=='sourcecas':next((f['run']/'bootstrap/source-cas').iterdir()).write_bytes(b'changed')
 elif fault=='missing_helper':state['prestart_recovery']=None
 elif fault=='bool_cost':state['attempts'][0]['actual_costs']['wall_seconds']=False
 elif fault=='bool_samples':state['attempts'][0]['formal_samples']=False
 elif fault=='bool_recoveries':state['recoveries']=True
 elif fault=='wrong_new_path':state['attempts'][1]['evidence']['result']['path']=str(stage/'forged.json')
 else:state['attempts'][1].pop('prestart_qualification')
 with pytest.raises((ValueError,KeyError,FileNotFoundError)):r.resolve_result(stage,state,require_success=True)

@pytest.mark.parametrize('counter,value',[('role_samples',0),('role_samples',14399),('native_processes_started',0),('native_processes_started',5),('native_processes_completed',5)])
def test_success_costs_match_actual_sample_and_process_roster(certified,counter,value):
 f=certified;events=copy.deepcopy(f['events']);events[-1][1]['actual_costs'][counter]=value
 result=json.loads(Path(f['current']['path']).read_bytes());result['actual_costs'][counter]=value
 events[-1][1]['evidence']['result']=put(Path(f['current']['path']),result)
 journal(f['ledger']/'events.jsonl',events,f['config'])
 with pytest.raises(ValueError,match='process/sample'):r.resolve_from_reader(f['stage'],require_success=True)

@pytest.mark.parametrize('name',['invocation.log','ledger-events-prefix.jsonl','task-events-prefix.jsonl'])
def test_preservation_payloads_are_protected(certified,name):
 f=certified;p=f['run']/'storage/maintenance/group-norm002-final-zero-native-022-20261006'/name
 assert str(p) in {v['path'] for v in r.resolve_from_reader(f['stage'])['protected']}
 p.write_bytes(b'tampered')
 with pytest.raises(ValueError):r.resolve_from_reader(f['stage'])

def test_public_qualification_event_is_required(certified):
 f=certified;(f['task']/'events.jsonl').write_bytes((f['stage']/'prestart-recovery/task-events-prefix.jsonl').read_bytes())
 with pytest.raises(ValueError,match='qualification event'):r.resolve_from_reader(f['stage'])


def test_frozen_producers_require_certified_same_request_and_new_engineering(certified):
 f=certified;final=json.loads((f['task']/'finalization/request.json').read_bytes());current=f['certificate']['producers']
 state={'stages':{'group_norm002-final':f['state']},'candidates':{'group_norm002':f['candidate']}}
 assert current!=final['producers']
 assert r.frozen_request_producers(f['task'],final,state,current)==final['producers']
 assert r.frozen_request_producers(f['task'],final,{},final['producers'])==final['producers']
 state['stages']['group_norm002-final']=copy.deepcopy(f['state']);state['stages']['group_norm002-final'].pop('prestart_recovery')
 with pytest.raises(ValueError,match='producer drift'):r.frozen_request_producers(f['task'],final,state,current)

@pytest.mark.parametrize('fault',['new_code','missing_new_snapshot','new_roles','request','missing_public_event'])
def test_frozen_producer_recovery_rejects_drift(certified,fault):
 f=certified;final=json.loads((f['task']/'finalization/request.json').read_bytes());current=copy.deepcopy(f['certificate']['producers'])
 state={'stages':{'group_norm002-final':f['state']},'candidates':{'group_norm002':f['candidate']}}
 if fault=='new_code':Path(current[0]['path']).write_bytes(b'changed')
 elif fault=='missing_new_snapshot':(f['run']/'bootstrap/source-cas'/current[0]['sha256'][7:]).unlink()
 elif fault=='new_roles':current.reverse()
 elif fault=='request':final['case_ids']=[1]
 else:(f['task']/'events.jsonl').write_bytes((f['stage']/'prestart-recovery/task-events-prefix.jsonl').read_bytes())
 with pytest.raises((ValueError,FileNotFoundError)):r.frozen_request_producers(f['task'],final,state,current)
