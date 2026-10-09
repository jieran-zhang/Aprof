import hashlib,json,sys
from pathlib import Path
from contextlib import contextmanager
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
import level2_verification_storage as store
import trace_v2_portable as portable
for module in (store,portable):
 assert Path(module.__file__).resolve().parent==Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'
from msprof_exploration_execute import event
import level2_storage

def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True)+'\n');return p
@pytest.fixture(autouse=True)
def locks(monkeypatch):
 @contextmanager
 def locked():yield
 monkeypatch.setattr(level2_storage,'exclusive_host',locked)

def fixture(tmp_path,operator='apply_adam_w',actual_result='precision.json'):
 task=tmp_path/'run/train/tasks'/operator;stage=task/'stages/aa';cohort=stage/'cohort';session=cohort/'p01';artifacts={}
 for role in 'AB':
  for name in ('metadata.json','execution.json','stdout.log',actual_result):
   p=save(session/'verification'/f'1_normal_{role}'/name,{'passed':True})
   if name in {'metadata.json','execution.json','stdout.log'}:artifacts[str(p)]=store.raw_ref(p)['sha256']
 save(stage/'result.json',{'status':'passed','error':None,'ended_at':2});save(stage/'stage-plan.json',{})
 save(cohort/'plan.json',{});save(cohort/'report.json',{'sessions':[{'directory':str(session),'artifacts':artifacts}]})
 save(cohort/'group-completion.json',{'status':'passed','error':None,'completed_sessions':[str(cohort/f'p{i:02d}') for i in range(1,7)]})
 save(session/'completion.json',{'status':'passed','error':None});save(session/'msprof.execution.json',{'exit_code':0,'error':None,'ended_at':1})
 save(session/'native/journal.jsonl',{'type':'session_end','exit_code':0});save(session/'bindings.json',{})
 save(session/'validation.json',{'scope':'final_call_of_final_sample_per_case_config_role','outputs':[{'case_id':'1','buffer_config':'normal','role':r,'passed':True} for r in 'AB']})
 event(task,'stage_completed',{'result':store.raw_ref(stage/'result.json')})
 from verification_authority_fixture import anchor
 anchor(task,cohort)
 return task,session

@pytest.mark.parametrize('operator,result',[('apply_adam_w','precision.json'),('maximum','result.json'),('arg_max','result.json'),('rms_norm','result.json'),('group_norm','result.json')])
def test_reviewed_names_and_repeat_retirement(tmp_path,operator,result):
 _,session=fixture(tmp_path,operator,result);old={p:p.read_bytes() for p in (session/'verification').rglob('*') if p.is_file()}
 first=store.prepare(session,writers_closed=True,retire=True)
 assert first['archived_files']==8
 assert store.prepare(session,writers_closed=True,retire=True)==first
 assert {p:store.read_bytes(p) for p in old}==old
 assert store.verified(session)['seal']['version']=='level2_closed_verification_storage_v2'

@pytest.mark.parametrize('operator,result',[('apply_adam_w','result.json'),('maximum','precision.json'),('apply_adam_w','random.json')])
def test_wrong_result_file_fails_before_any_unlink(tmp_path,operator,result):
 _,session=fixture(tmp_path,operator,result);original=[p for p in (session/'verification').rglob('*') if p.is_file()]
 with pytest.raises(ValueError):store.prepare(session,writers_closed=True,retire=True)
 assert all(p.is_file() for p in original)
 assert not (session/'verification-storage/seal.json').exists()

def test_adam_portable_full_roster_and_offline_reader(tmp_path):
 import trace_v2_dataset as v2
 from test_trace_v2_dataset import fixture_data
 task,session=fixture(tmp_path);origin=session/'verification/1_normal_A/precision.json'
 evidence,body=fixture_data(tmp_path);body['sources']['evidence_ids'].append(evidence.file(origin))
 dataset=tmp_path/'dataset';v2.publish(dataset,{'attempt':body},lambda _: {},evidence,{'hardware_executed':False})
 store.prepare(session,writers_closed=True,retire=True)
 bundle=tmp_path/'bundle';assert portable.export(dataset,bundle)['valid']
 import shutil,subprocess
 shutil.rmtree(task);shutil.rmtree(dataset)
 assert portable.verify(bundle)['valid']
 output=subprocess.run([sys.executable,str(bundle/'verifier/trace_v2_portable.py'),'verify','--bundle',str(bundle)],capture_output=True,text=True,cwd=tmp_path,check=True)
 assert json.loads(output.stdout)['valid']
