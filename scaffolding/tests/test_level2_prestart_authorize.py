"""Tiny real ledger + certificate admission; no source/native payload or device."""
from aprof_layout import skill_lib
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
import json,sys
from types import ModuleType
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
import level2_prestart_recovery as q
import msprof_exploration_campaign as campaign
import msprof_exploration_execute as execution
import run_level1_serial
from test_level2_prestart_campaign import failed_final


def put(p,value):
 p.parent.mkdir(parents=True,exist_ok=True);q.save(p,value);return q.pointer(p)


@pytest.fixture
def author(tmp_path,monkeypatch,failed_final):
 source,plan,_=failed_final;repo=tmp_path/'repository';run=repo/'.aprof/runs/tiny';task=run/'validation/tasks/group_norm';stage=task/'candidates/group_norm002/stages/final'
 monkeypatch.setattr(q,'__file__',str(repo/'scaffolding/collection/scripts/level2_prestart_recovery.py'))
 monkeypatch.setenv('PYTHONPATH',str(repo/'scaffolding/collection/scripts')+':'+str(skill_lib() / 'runtime/src'))
 manifest=put(run/'campaign-manifest.json',{'tiny':True});tm=put(task/'manifest.json',{'tiny':True})
 producers=[]
 for n in (22,23):
  refs=[];files=[]
  for name in q.PRODUCERS:
   p=repo/'scaffolding/collection/scripts'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(f'# inert fixture snapshot {n} {name}\n')
   r=q.pointer(p);snap=run/'bootstrap/source-cas'/r['sha256'][7:];snap.parent.mkdir(parents=True,exist_ok=True);snap.write_bytes(p.read_bytes());refs.append(r);files.append({**r,'snapshot':str(snap)})
  ref=put(run/f'bootstrap/frozen-engineering-{n:03}.json',{'version':'level2_frozen_engineering_v1','files':files,'campaign_manifest':manifest,'task_manifests':[tm]})
  producers.append((refs,ref))
 final=put(task/'finalization/request.json',{'operator':'group_norm','case_ids':list(range(1,21)),'evaluation_candidate_ids':['group_norm002'],'final_plans':{'group_norm002':put(stage/'stage-plan.json',plan)},'producers':producers[0][0]})
 costs=deepcopy(source.state['tasks']['group_norm']['stages'][q.STAGE]['attempts'][0]['actual_costs'])
 old=put(stage/'result.json',{'status':'failed','kind':'timing','stage_id':q.STAGE,'candidate_id':q.CANDIDATE,'native_started':False,'actual_costs':costs,'error':q.FAILURE})
 ledger=campaign.create_fresh(run/'validation/ledger',campaign_id='tiny',workloads={'group_norm':{'baseline_source_hash':'sha256:'+f'{1:064x}','source_split':'validation','repeat_by_case':{str(c):10 for c in campaign.ALL_CASES},'pilot_ref':'sha256:'+f'{2:064x}'}})
 for row in source.events[1:]:
  a=deepcopy(row['arguments'])
  if row['event_id']=='first-finish':a['evidence']['result']=old
  if row['operation']=='freeze':a['reason']='All safe candidates; no winner selected; finalization request '+final['sha256']
  ledger._commit(row['operation'],event_id=row['event_id'],**a)
 execution.event(task,'stage_started',{'candidate_id':q.CANDIDATE,'stage':q.STAGE,'kind':'timing','plan':q.pointer(stage/'stage-plan.json')})
 execution.event(task,'stage_completed',{'candidate_id':q.CANDIDATE,'stage':q.STAGE,'result':old})
 log=put(tmp_path/'invocation.json',{'error':q.FAILURE})
 keep=run/'storage/maintenance'/q.PRESERVATION_NAME;keep.mkdir(parents=True)
 entries=[]
 for p,name in [(stage/'result.json','stage-result.json'),(stage/'stage-plan.json','stage-plan.json'),(task/'finalization/request.json','finalization-request.json'),(Path(log['path']),'invocation.log'),(task/'events.jsonl','task-events-prefix.jsonl'),(ledger.directory/'events.jsonl','ledger-events-prefix.jsonl')]:
  retained=keep/name;retained.write_bytes(p.read_bytes());entries.append({'original':({'path':'/tmp/aprof-gn002-final-022-20261006.log','sha256':q.sha(p)} if name=='invocation.log' else q.pointer(p)),'retained':q.pointer(retained)})
 preserve=put(keep/'preservation.json',{'version':'level2_zero_native_failure_preservation_v1','stage':q.STAGE,'error':q.FAILURE,'native_processes_started':0,'role_samples':0,'observed_process_exit_code':1,'recovery_executed':False,'stage_directory_inventory':['result.json','stage-plan.json'],'files':entries,'request':final,'status':'infrastructure_blocked','original_stage_and_ledger_preserved':True,'source_attempt_count_unchanged':True,'recorded_at':'tiny fixture','invocation_environment_correction':'Owner-reported missing PYTHONPATH; no traceback claimed'})
 monkeypatch.setattr(q,'PRESERVATION_SHA',preserve['sha256']);monkeypatch.setattr(q,'OLD_ENGINEERING_SHA',producers[0][1]['sha256'])
 module=ModuleType('aprof_runtime');module.__file__=str(skill_lib() / 'runtime/src/aprof_runtime/__init__.py');monkeypatch.setitem(sys.modules,'aprof_runtime',module)
 @contextmanager
 def host():yield
 monkeypatch.setattr(run_level1_serial,'exclusive_host',host)
 eng=producers[1][1]
 return {'repo':repo,'run':run,'task':task,'stage':stage,'ledger':ledger,'engineering':eng,'old':old,'preserve':preserve,
         'invoke':lambda apply:q.authorize(run,Path(eng['path']),eng['sha256'],writers_closed=True,apply=apply)}


def test_dry_audit_no_writes_or_native(author,monkeypatch):
 old={str(p):p.read_bytes() for p in author['run'].rglob('*') if p.is_file()}
 monkeypatch.setattr(execution,'collect_cohort',lambda *a:pytest.fail('audit called collector'))
 result=author['invoke'](False);assert result['status']=='eligible_not_authorized'
 assert old=={str(p):p.read_bytes() for p in author['run'].rglob('*') if p.is_file()}


def test_authorize_binds_durable_certificate_without_success(author):
 old=(author['stage']/'result.json').read_bytes();prefix=(author['ledger'].directory/'events.jsonl').read_bytes()
 done=author['invoke'](True);assert done['status']=='qualified_not_executed'
 assert (author['stage']/'result.json').read_bytes()==old and not (author['stage']/'result.recovery-01.json').exists()
 ledger=campaign.Campaign(author['ledger'].directory);assert len(ledger.state['tasks']['group_norm']['stages'][q.STAGE]['attempts'])==1
 assert (ledger.directory/'events.jsonl').read_bytes().startswith(prefix)
 f=q.execution_audit(author['run'],Path(done['qualification']['path']),done['qualification']['sha256'])
 assert f['qualification']==done['qualification']
 with pytest.raises(ValueError):author['invoke'](True)


@pytest.mark.parametrize('fault',['extra_cohort','old_result','preservation','current_producer','wrong_engineering','native_cost'])
def test_qualification_rejects_before_publication(author,fault):
 if fault=='extra_cohort':(author['stage']/'direct_parent').mkdir()
 elif fault=='old_result':(author['stage']/'result.json').write_bytes(b'{}')
 elif fault=='preservation':Path(author['preserve']['path']).write_bytes(b'{}')
 elif fault=='current_producer':(author['repo']/'scaffolding/collection/scripts/level2_prestart_recovery.py').write_bytes(b'changed')
 elif fault=='wrong_engineering':author['engineering']['sha256']='sha256:'+'0'*64
 else:
  p=author['stage']/'result.json';value=json.loads(p.read_bytes());value['actual_costs']['native_processes_started']=1;p.write_text(json.dumps(value))
 with pytest.raises(ValueError):author['invoke'](True)
 assert not (author['stage']/'prestart-recovery/qualification.json').exists()


def test_certificate_before_append_failure_stays_blocked(author,monkeypatch):
 def fail(*a,**kw):raise RuntimeError('injected append failure')
 monkeypatch.setattr(campaign.Campaign,'qualify_prestart',fail)
 with pytest.raises(RuntimeError):author['invoke'](True)
 cert=author['stage']/'prestart-recovery/qualification.json';assert cert.is_file()
 with pytest.raises(ValueError):q.execution_audit(author['run'],cert,q.sha(cert))
 assert not (author['stage']/'result.recovery-01.json').exists()


def test_post_execution_producer_recheck_rejects_drift(author):
 done=author['invoke'](True);q.check_execution_identity(done['qualification'])
 (author['repo']/'scaffolding/collection/scripts/msprof_exploration_campaign.py').write_bytes(b'changed after native')
 with pytest.raises(ValueError,match='current producer'):q.check_execution_identity(done['qualification'])


def test_missing_public_qualification_event_blocks_execute(author,monkeypatch):
 monkeypatch.setattr(execution,'event',lambda *a:None)
 done=author['invoke'](True)
 with pytest.raises(ValueError,match='qualification event'):
  q.execution_audit(author['run'],Path(done['qualification']['path']),done['qualification']['sha256'])


def test_execution_requires_explicit_corrected_environment(author,monkeypatch):
 done=author['invoke'](True);monkeypatch.delenv('PYTHONPATH',raising=False)
 with pytest.raises(ValueError,match='explicit corrected PYTHONPATH'):
  q.execution_audit(author['run'],Path(done['qualification']['path']),done['qualification']['sha256'])
 assert not (author['stage']/'prestart-recovery/execution-started.json').exists()


def test_dangling_execution_lock_cannot_escape(author):
 done=author['invoke'](True);outside=author['repo']/'forbidden-created-file'
 (author['stage']/'prestart-recovery/.execute.lock').symlink_to(outside)
 with pytest.raises(ValueError,match='noncanonical recovery path'):
  q.execution_audit(author['run'],Path(done['qualification']['path']),done['qualification']['sha256'])
 assert not outside.exists()


def test_execute_cli_failed_result_has_nonzero_exit(monkeypatch,capsys):
 monkeypatch.setattr(q,'execute',lambda *a,**k:{'status':'failed','native_started':False})
 monkeypatch.setattr(sys,'argv',['level2_prestart_recovery.py','execute','--run','/unused',
  '--qualification','/unused/qualification.json','--qualification-sha256','sha256:'+'a'*64,'--writers-closed'])
 with pytest.raises(SystemExit) as caught:q.main()
 assert caught.value.code==1
 assert json.loads(capsys.readouterr().out)['status']=='failed'
