"""Real small fresh ledger; no native collection or source compilation."""
from copy import deepcopy
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
import msprof_exploration_campaign as campaign


def h(n):return 'sha256:'+f'{n:064x}'


@pytest.fixture
def failed_final(tmp_path):
 op='group_norm';cid='group_norm002';sid=cid+'-final'
 ledger=campaign.create_fresh(tmp_path/'ledger',campaign_id='tiny',workloads={op:{'baseline_source_hash':h(1),'source_split':'validation','repeat_by_case':{str(c):10 for c in campaign.ALL_CASES},'pilot_ref':h(2)}})
 def ready(who):
  ids=[]
  for kind in ('build','correctness','runtime'):
   stage=who+'-'+kind;plan={'case_ids':campaign.ALL_CASES,'source_hash':h(1 if who=='baseline' else 10+int(who[-3:]))}
   ledger.start(event_id=stage+'-start',workload=op,stage_id=stage,kind=kind,plan=plan,candidate_id=None if who=='baseline' else who)
   ledger.finish(event_id=stage+'-finish',workload=op,stage_id=stage,outcome='success',native_started=kind!='build',evidence={'result':{'path':str(tmp_path/stage/'result.json'),'sha256':h(50)},'prepared_output_checked':True})
   ids.append(stage)
  return ids
 ready('baseline');basis=[]
 for i in range(1,4):
  who=f'group_norm{i:03}'
  ledger.register(event_id=who+'-register',workload=op,candidate_id=who,source_hash=h(10+i),patch_hash=h(20+i),source_parent={'candidate_id':None,'source_hash':h(1)},decision_basis=basis)
  ids=ready(who);oid=who+'-closed'
  ledger.observe(event_id=oid,workload=op,candidate_id=who,observation_id=oid,stage_ids=ids,feedback={'status':'measured'})
  basis=[oid]
 plan=ledger.timing_plan(op,cid,purpose='final',manifest_ref=h(60))
 ledger.freeze(event_id='freeze',workload=op,candidate_ids=[cid],final_plans={cid:plan},reason='all safe')
 ledger.start(event_id='first-start',workload=op,stage_id=sid,kind='timing',candidate_id=cid,plan=plan)
 original={'path':str(tmp_path/'validation/tasks/group_norm/candidates'/cid/'stages/final/result.json'),'sha256':h(61)}
 costs={k:0 for k in ('native_processes_started','native_processes_completed','role_samples','timed_complete_calls','warmup_complete_calls','formal_target_kernel_launches','correctness_complete_calls','unconfirmed_warmup_blocks','wall_seconds')}
 ledger.finish(event_id='first-finish',workload=op,stage_id=sid,outcome='failed',evidence={'result':original},native_started=False,actual_costs=costs,reason='{"type":"ModuleNotFoundError","message":"No module named \'aprof_runtime\'"}')
 args={'workload':op,'stage_id':sid,'source_hash':h(12),'plan_hash':campaign.digest(plan),'failed_result':original,
       'qualification':{'path':str(Path(original['path']).parent/'prestart-recovery/qualification.json'),'sha256':h(62)},'reason':'Explicit retained pre-native import failure qualification'}
 return ledger,plan,args


def test_qualification_preserves_failed_attempt_and_charge(failed_final):
 ledger,plan,args=failed_final;state=ledger.state['tasks']['group_norm'];before=deepcopy(state);original_prefix=(ledger.directory/'events.jsonl').read_bytes()
 ledger.qualify_prestart(event_id='qualify',**args)
 state=ledger.state['tasks']['group_norm'];stage=state['stages'][args['stage_id']]
 assert stage['attempts']==before['stages'][args['stage_id']]['attempts']
 assert stage['attempts'][0]['outcome']=='failed' and state['used']==before['used']
 assert (ledger.directory/'events.jsonl').read_bytes().startswith(original_prefix)
 ledger.start(event_id='second-start',workload='group_norm',stage_id=args['stage_id'],kind='timing',candidate_id='group_norm002',plan=plan)
 stage=ledger.state['tasks']['group_norm']['stages'][args['stage_id']]
 assert len(stage['attempts'])==2 and stage['recoveries']==1
 assert stage['attempts'][1]['charged'] is None and stage['attempts'][1]['prestart_qualification']==args['qualification']
 assert ledger.state['tasks']['group_norm']['used']==before['used']
 assert ledger.state['tasks']['group_norm']['stage_starts']['timing']==before['stage_starts']['timing']+1


def test_failed_without_qualification_remains_unrecoverable(failed_final):
 ledger,plan,args=failed_final
 with pytest.raises(ValueError,match='native-not-started'):
  ledger.start(event_id='bad',workload='group_norm',stage_id=args['stage_id'],kind='timing',candidate_id='group_norm002',plan=plan)


@pytest.mark.parametrize('key,value',[('source_hash',h(99)),('plan_hash',h(99)),('stage_id','group_norm003-final'),('workload','maximum'),('reason','')])
def test_foreign_qualification_rejected(failed_final,key,value):
 ledger,plan,args=failed_final;args[key]=value
 with pytest.raises(ValueError):ledger.qualify_prestart(event_id='bad',**args)


def test_qualification_only_once_and_exact_plan(failed_final):
 ledger,plan,args=failed_final;ledger.qualify_prestart(event_id='qualify',**args)
 with pytest.raises(ValueError):ledger.qualify_prestart(event_id='qualify-again',**args)
 plan=deepcopy(plan);plan['manifest_ref']=h(99)
 with pytest.raises(ValueError,match='exact frozen|immutable'):
  ledger.start(event_id='wrong-plan',workload='group_norm',stage_id=args['stage_id'],kind='timing',candidate_id='group_norm002',plan=plan)


def test_recovered_finish_requires_new_result_and_qualification(failed_final):
 ledger,plan,args=failed_final;ledger.qualify_prestart(event_id='qualify',**args)
 ledger.start(event_id='second-start',workload='group_norm',stage_id=args['stage_id'],kind='timing',candidate_id='group_norm002',plan=plan)
 with pytest.raises(ValueError,match='distinct result'):
  ledger.finish(event_id='bad-finish',workload='group_norm',stage_id=args['stage_id'],outcome='failed',evidence={'result':args['failed_result'],'qualification':args['qualification']},native_started=False,reason='still failed')
 new={'path':str(Path(args['failed_result']['path']).with_name('result.recovery-01.json')),'sha256':h(64)}
 ledger.finish(event_id='second-finish',workload='group_norm',stage_id=args['stage_id'],outcome='failed',evidence={'result':new,'qualification':args['qualification']},native_started=False,reason='still failed')
 with pytest.raises(ValueError):ledger.start(event_id='third-start',workload='group_norm',stage_id=args['stage_id'],kind='timing',candidate_id='group_norm002',plan=plan)
 assert ledger.state['tasks']['group_norm']['used']['timing_groups']==1


def test_extra_qualification_fields_rejected(failed_final):
 ledger,plan,args=failed_final;args['retry_forever']=True
 with pytest.raises((ValueError,TypeError)):ledger.qualify_prestart(event_id='bad',**args)
