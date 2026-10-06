"""Tiny orchestration using the real ledger but a fake native collector."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import level2_prestart_recovery as recovery
import run_msprof_exploration_stage as stage
import msprof_exploration_execute as execution
import msprof_exploration_campaign as campaign
from test_level2_prestart_campaign import failed_final


@pytest.fixture
def native(tmp_path,monkeypatch,failed_final):
 ledger,plan,args=failed_final
 # This fixture starts with a synthetic old failure and freezes a matching plan
 # before the first stage; only collection itself is replaced below.
 root=Path(args['failed_result']['path']).parent;root.mkdir(parents=True)
 old={'status':'failed','kind':'timing','stage_id':args['stage_id'],'candidate_id':'group_norm002','error':recovery.FAILURE,'native_started':False,'actual_costs':ledger.state['tasks']['group_norm']['stages'][args['stage_id']]['attempts'][0]['actual_costs']}
 recovery.save(root/'result.json',old);recovery.save(root/'stage-plan.json',plan)
 cert=root/'prestart-recovery/qualification.json';cert.parent.mkdir();recovery.save(cert,{'tiny':'fixture certificate; full certificate validation tested separately'})
 # Use a separate real fresh ledger whose original failure binds the tiny file.
 # Reconstructing fixture events is deliberate test setup, not product recovery.
 rows=ledger.events
 directory=tmp_path/'bound-ledger'
 bound=campaign.create_fresh(directory,campaign_id='tiny',workloads={'group_norm':{'baseline_source_hash':campaign._read_json(ledger.directory/'config.json')['tasks']['group_norm']['baseline_source_hash'],'source_split':'validation','repeat_by_case':{str(c):10 for c in campaign.ALL_CASES},'pilot_ref':'sha256:'+f'{2:064x}'}})
 for e in rows[1:]:
  a=deepcopy(e['arguments'])
  if e['event_id']=='first-finish':a['evidence']['result']=recovery.pointer(root/'result.json')
  bound._commit(e['operation'],event_id=e['event_id'],**a)
 args=deepcopy(args);args['failed_result']=recovery.pointer(root/'result.json');args['qualification']=recovery.pointer(cert)
 bound.qualify_prestart(event_id='qualification',**args)
 task=root.parents[3]
 # The small plan has no real cohort. Supply one only to the execution fixture;
 # keep the actual ledger immutable plan unchanged and intercept its start call.
 cal=tmp_path/'cal.json';recovery.save(cal,{'tiny':True});cohort=tmp_path/'cohort.json';recovery.save(cohort,{'tiny':True})
 runplan={**plan,'calibration_report':recovery.pointer(cal),'cohorts':[{'relation':'direct_parent','plan':recovery.pointer(cohort)}]}
 state=SimpleNamespace(ledger=bound,args=args,root=root,cert=cert,task=task,plan=plan,runplan=runplan,collect_calls=0,fail=False,preflight_fail=False,mutate_old=False)
 def audit(*a):
  bound._load();record=bound.state['tasks']['group_norm']['stages'][args['stage_id']]
  if len(record['attempts'])!=1 or (cert.parent/'execution-started.json').exists():raise ValueError('already invoked')
  return {'stage':root,'directory':cert.parent,'plan':runplan,'task':task,'ledger':state.proxy,'qualification':args['qualification'],'python_import_paths':['/fixture/scripts','/fixture/src']}
 class Proxy:
  def start(self,**kw):kw['plan']=plan;return bound.start(**kw)
  def finish(self,**kw):return bound.finish(**kw)
 state.proxy=Proxy()
 monkeypatch.setattr(recovery,'execution_audit',audit)
 monkeypatch.setattr(recovery,'check_execution_identity',lambda *a:None)
 monkeypatch.setattr(stage,'validate_calibration_storage',lambda *a:None)
 def preflight(*a):
  if state.preflight_fail:raise ValueError('preflight failed')
 monkeypatch.setattr(execution,'preflight_cohort',preflight)
 def collect(frozen,out,selected):
  state.collect_calls+=1;out.mkdir()
  if state.mutate_old:(root/'result.json').write_bytes(b'changed old failure')
  if state.fail:raise RuntimeError('native fixture failed')
 monkeypatch.setattr(stage,'collect_cohort',collect)
 monkeypatch.setattr(stage,'native_started_in',lambda out:bool(state.collect_calls))
 def costs(out):
  v={k:0 for k in old['actual_costs']};v['native_processes_started']=6 if state.collect_calls else 0;v['native_processes_completed']=0 if state.fail else v['native_processes_started'];v['role_samples']=0 if state.fail else campaign.expected_samples(plan);return v
 monkeypatch.setattr(stage,'actual_costs',costs)
 # Execution checks the frozen plan after native; fixture read delegates exactly
 # the synthetic execution plan at that slot without altering on-disk bytes.
 real_load=stage.load
 monkeypatch.setattr(stage,'load',lambda p:runplan if Path(p)==root/'stage-plan.json' else real_load(p))
 state.invoke=lambda:stage.run_qualified_timing_recovery(tmp_path,cert,args['qualification']['sha256'])
 return state


def test_second_success_new_result_preserves_old_and_charge(native):
 old=(native.root/'result.json').read_bytes();plan=(native.root/'stage-plan.json').read_bytes();used=deepcopy(native.ledger.state['tasks']['group_norm']['used'])
 result=native.invoke();assert result['status']=='passed' and result['native_started'] is True
 assert (native.root/'result.json').read_bytes()==old and (native.root/'stage-plan.json').read_bytes()==plan
 assert native.ledger.state['tasks']['group_norm']['used']==used
 attempts=native.ledger.state['tasks']['group_norm']['stages'][recovery.STAGE]['attempts']
 assert len(attempts)==2 and attempts[0]['outcome']=='failed' and attempts[1]['outcome']=='success'
 assert attempts[1]['evidence']['result']==recovery.pointer(native.root/'result.recovery-01.json')
 with pytest.raises(ValueError,match='already invoked'):native.invoke()
 assert native.collect_calls==1


def test_new_native_failure_is_retained_no_retry(native):
 native.fail=True;result=native.invoke();assert result['status']=='failed' and result['error']['type']=='RuntimeError'
 assert native.ledger.state['tasks']['group_norm']['stages'][recovery.STAGE]['attempts'][-1]['outcome']=='failed'
 with pytest.raises(ValueError):native.invoke()
 assert native.collect_calls==1


def test_preflight_failure_cannot_start_second_attempt(native):
 native.preflight_fail=True
 with pytest.raises(ValueError,match='before second start'):native.invoke()
 assert len(native.ledger.state['tasks']['group_norm']['stages'][recovery.STAGE]['attempts'])==1
 assert not (native.root/'result.recovery-01.json').exists()
 assert recovery.load(native.cert.parent/'execution-failure.json')['status']=='failed_before_second_start'
 with pytest.raises(ValueError):native.invoke()
 assert native.collect_calls==0


def test_old_result_mutation_prevents_finish(native):
 native.mutate_old=True
 with pytest.raises(ValueError,match='original failed stage changed'):native.invoke()
 assert not (native.root/'result.recovery-01.json').exists()
 assert native.ledger.state['tasks']['group_norm']['stages'][recovery.STAGE]['attempts'][-1]['outcome'] is None
