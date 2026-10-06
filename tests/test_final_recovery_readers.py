"""Reader propagation tests; certificate authenticity is tested by shared resolver.

These tiny fixtures isolate the consumer boundary. No real campaign or native IO.
"""
import contextlib,copy,importlib.util,json
from pathlib import Path
import pytest
import level2_stage_recovery as recovery
import level2_verification_storage as verification
import level2_native_output_storage as native
import msprof_exploration_archive as archive
import level2_final_report_authority as final_authority
from msprof_exploration_execute import event
from test_msprof_exploration_archive import run,stage,save,read_memory
from test_level2_native_output_storage import fixture as native_fixture
from test_level2_final_prestart_resolver import certified,put as cert_put,journal as cert_journal

@pytest.fixture(autouse=True)
def no_real_host_lock(monkeypatch):
    import level2_storage
    monkeypatch.setattr(level2_storage,'exclusive_host',contextlib.nullcontext)

def pointer(path):return {'path':str(path),'sha256':verification.digest(path.read_bytes())}

def session_fixture(tmp_path):
    task=tmp_path/'run/validation/tasks/group_norm'
    stage=task/'candidates/group_norm002/stages/final';cohort=stage/'direct_parent';session=cohort/'p01'
    artifacts={}
    for role in 'AB':
        for name in verification.NAMES:
            p=save(session/'verification'/f'1_normal_{role}'/name,{'passed':True})
            if name!='result.json':artifacts[str(p)]=pointer(p)['sha256']
    original=save(stage/'result.json',{'status':'failed','error':{'type':'ModuleNotFoundError'},'ended_at':1})
    current=save(stage/'result.recovery-01.json',{'status':'passed','error':None,'ended_at':2})
    qualification=save(stage/'prestart-recovery/qualification.json',{'stub':'already checked by shared resolver'})
    save(stage/'stage-plan.json',{'purpose':'final'})
    save(cohort/'plan.json',{'case_ids':[1]})
    save(cohort/'report.json',{'sessions':[{'directory':str(session),'artifacts':artifacts}]})
    save(cohort/'group-completion.json',{'status':'passed','error':None,'completed_sessions':[str(cohort/f'p{i:02d}') for i in range(1,7)]})
    save(session/'completion.json',{'status':'passed','error':None})
    save(session/'msprof.execution.json',{'exit_code':0,'error':None,'ended_at':2})
    save(session/'native/journal.jsonl',{'type':'session_end','exit_code':0})
    save(session/'bindings.json',{})
    save(session/'validation.json',{'scope':'final_call_of_final_sample_per_case_config_role','outputs':[
        {'case_id':'1','buffer_config':'normal','role':r,'passed':True} for r in 'AB']})
    event(task,'stage_completed',{'result':pointer(original)})
    event(task,'stage_completed',{'result':pointer(current)})
    resolved={'current_result':pointer(current),'original_failed_result':pointer(original),
        'qualification':pointer(qualification),'protected':[pointer(original),pointer(current),pointer(qualification)],
        'event_bindings':[{'path':str(task.parents[1]/'ledger/events.jsonl'),'sequence':4,'hash':'sha256:'+'a'*64}]}
    return task,stage,session,resolved

def test_verification_retains_failed_qualification_and_current_result(tmp_path,monkeypatch):
    task,stage,session,resolved=session_fixture(tmp_path);calls=[]
    def resolve(directory,read,*,require_success=False):
        assert directory==stage and require_success is True;calls.append(directory);return resolved
    monkeypatch.setattr(recovery,'resolve_from_reader',resolve)
    facts,expected=verification.closed_from_reader(session,Path.read_bytes)
    assert calls==[stage] and len(expected)==8
    assert all(ref in facts['protected'] for ref in resolved['protected'])
    assert facts['stage_recovery']=={k:v for k,v in resolved.items() if k!='protected'}
    assert facts['event_binding']['sequence']==1
    assert verification.event_bindings(facts)==[facts['event_binding'],*resolved['event_bindings']]

@pytest.mark.parametrize('failure',['denied_certificate','changed_current','missing_original'])
def test_verification_does_not_fallback_after_recovery_rejection(tmp_path,monkeypatch,failure):
    _,stage,session,resolved=session_fixture(tmp_path)
    def resolve(*args,**kwargs):
        if failure=='denied_certificate':raise ValueError('certificate rejected')
        if failure=='missing_original':resolved['original_failed_result']=None
        if failure=='changed_current':Path(resolved['current_result']['path']).write_text('{}')
        return resolved
    monkeypatch.setattr(recovery,'resolve_from_reader',resolve)
    with pytest.raises(ValueError):verification.closed_from_reader(session,Path.read_bytes)

def test_ordinary_passed_verification_never_imports_recovery_facts(tmp_path,monkeypatch):
    _,stage,session,_=session_fixture(tmp_path)
    save(stage/'result.json',{'status':'passed','error':None,'ended_at':2})
    task=stage.parents[3];(task/'events.jsonl').unlink();event(task,'stage_completed',{'result':pointer(stage/'result.json')})
    monkeypatch.setattr(recovery,'resolve_from_reader',lambda *a,**k:pytest.fail('ordinary path uses no recovery dependency'))
    facts,_=verification.closed_from_reader(session,Path.read_bytes)
    assert 'stage_recovery' not in facts
    assert set(facts)=={'protected','event_binding'}

def test_archive_keeps_both_attempt_statuses_without_duplicate_comparison(run,monkeypatch):
    old=stage(run,status='failed',kind='timing',name='final');cid='exp001'
    current=old.with_name('result.recovery-01.json');save(current,{**archive.load(old),'status':'passed','error':None})
    qualification=save(old.parent/'prestart-recovery/qualification.json',{'stub':'qualified'})
    row=run['state']['stages']['final'];row['prestart_recovery']={'qualification':pointer(qualification)}
    row['attempts'].append({'outcome':'success','evidence':{'result':pointer(current)}})
    resolved={'current_result':pointer(current),'original_failed_result':pointer(old),'qualification':pointer(qualification),
              'protected':[pointer(old),pointer(current),pointer(qualification)],'event_bindings':[]}
    monkeypatch.setattr(recovery,'resolve_result',lambda *a,**k:resolved)
    collector=archive.Archive(run['root'],'train');config=collector.prepare([]);collector.publish(config)
    rows,_=read_memory(run['root']);evaluations=rows[0]['body']['evaluations']
    assert len(evaluations)==1
    assert [r['status'] for r in evaluations[0]['stages']]==['failed','passed']
    assert archive.load(old)['status']=='failed'

def test_native_requires_recovery_refs_in_prior_dedup_inventory(tmp_path,monkeypatch):
    task,cohort,_,_=native_fixture(tmp_path)
    original=verification.closed_from_reader
    def projected(*args):
        facts,roster=original(*args)
        facts['stage_recovery']={'current_result':{'path':str(cohort.parent/'result.recovery-01.json'),'sha256':'sha256:'+'b'*64},
             'original_failed_result':pointer(cohort.parent/'result.json'),
             'qualification':{'path':str(cohort.parent/'prestart-recovery/qualification.json'),'sha256':'sha256:'+'c'*64},'event_bindings':[]}
        return facts,roster
    monkeypatch.setattr(verification,'closed_from_reader',projected)
    with pytest.raises(ValueError,match='dedup authority lacks original closed-state hashes'):
        native.closed_from_reader(cohort,Path.read_bytes)

def compose_certificate_session(certified,tmp_path):
    """Join the real small certificate resolver to retained oracle metadata."""
    f=certified;_,source,_,_=session_fixture(tmp_path/'oracle-donor')
    origin=source/'direct_parent';destination=f['stage']/'direct_parent'
    for p in origin.rglob('*'):
        if p.is_file():
            target=destination/p.relative_to(origin);target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(p.read_bytes().replace(str(origin).encode(),str(destination).encode()))
    current=Path(f['current']['path']);value=json.loads(current.read_bytes());value['ended_at']=2
    f['current']=cert_put(current,value)
    f['events'][-1][1]['evidence']['result']=f['current']
    f['rows']=cert_journal(f['ledger']/'events.jsonl',f['events'],f['config'])
    event(f['task'],'stage_completed',{'result':f['current']})
    return destination/'p01'

def test_real_certificate_resolver_feeds_successful_verification_closure(certified,tmp_path):
    session=compose_certificate_session(certified,tmp_path)
    facts,_=verification.closed_from_reader(session,Path.read_bytes)
    assert facts['stage_recovery']['current_result']==certified['current']
    assert facts['stage_recovery']['original_failed_result']==certified['original']
    assert certified['original'] in facts['protected']
    assert certified['args']['qualification'] in facts['protected']
    assert str(certified['ledger']/'events.jsonl') not in {p['path'] for p in facts['protected']}
    assert facts['event_binding']['sequence']==2
    assert any(p['path']==str(certified['task']/'events.jsonl') and p['sequence']==1
               for p in facts['stage_recovery']['event_bindings'])

@pytest.mark.parametrize('which',['original','current','certificate','ledger_prefix','producer_cas'])
def test_real_certificate_mutation_prevents_verification_closure(certified,tmp_path,which):
    session=compose_certificate_session(certified,tmp_path);f=certified
    paths={'original':Path(f['original']['path']),'current':Path(f['current']['path']),
        'certificate':Path(f['args']['qualification']['path']),
        'ledger_prefix':f['stage']/'prestart-recovery/ledger-prefix.jsonl',
        'producer_cas':next((f['run']/'bootstrap/source-cas').iterdir())}
    paths[which].write_bytes(paths[which].read_bytes()+b' ')
    with pytest.raises((ValueError,json.JSONDecodeError)):
        verification.closed_from_reader(session,Path.read_bytes)

def projection_rows(f):
    rows=[{'operation':'prepare','arguments':{}}]
    cids=['group_norm001','group_norm002','group_norm003_exec']
    for cid in cids:
        rows.append({'operation':'register','arguments':{'workload':'group_norm','candidate_id':cid,
            'source_hash':f['candidate']['source_hash']}})
        rows.append({'operation':'start','arguments':{'workload':'group_norm','candidate_id':cid,
            'kind':'timing','stage_id':cid+'-search','plan':{'purpose':'search'}}})
        rows.append({'operation':'finish','arguments':{'workload':'group_norm','stage_id':cid+'-search',
            'outcome':'success','native_started':True}})
        rows.append({'operation':'observe','arguments':{'workload':'group_norm','candidate_id':cid,
            'close_feedback':True,'stage_ids':[cid+'-search']}})
    rows.append({'operation':'freeze','arguments':{'workload':'group_norm','candidate_ids':cids[1:]}})
    rows.extend(copy.deepcopy(f['rows'][2:]))
    return rows

def test_final_authority_projection_accepts_only_explicit_qualified_retry(certified):
    rows=projection_rows(certified)
    registered,starts,finishes,observed,freeze=final_authority.projection(rows,'group_norm')
    assert finishes['group_norm002-final']['evidence']['result']==certified['current']
    assert list(registered)==['group_norm001','group_norm002','group_norm003_exec']

@pytest.mark.parametrize('fault',['no_qualification','duplicate_qualification','native_first','nonzero_first','unfrozen_stage','changed_plan'])
def test_final_authority_projection_rejects_unqualified_or_nonzero_retries(certified,fault):
    rows=projection_rows(certified)
    qual=next(i for i,r in enumerate(rows) if r['operation']=='qualify_prestart')
    first=rows[qual-1]['arguments']
    if fault=='no_qualification':rows.pop(qual)
    elif fault=='duplicate_qualification':rows.insert(qual,copy.deepcopy(rows[qual]))
    elif fault=='native_first':first['native_started']=True
    elif fault=='nonzero_first':first['actual_costs']['native_processes_started']=1
    elif fault=='unfrozen_stage':rows=[r for r in rows if r['operation']!='freeze']
    else:rows[qual+1]['arguments']['plan']['case_ids']=[1]
    with pytest.raises(ValueError):final_authority.projection(rows,'group_norm')

@pytest.mark.parametrize('changed_certificate',[False,True])
def test_inventory_binds_both_results_and_qualification(tmp_path,monkeypatch,changed_certificate):
    import level2_storage
    task,cohort,_,_=native_fixture(tmp_path,'group_norm',candidate=True,
                                   candidate_id='group_norm002',stage_name='final')
    stage=cohort.parent;original=stage/'result.json'
    passed=json.loads(original.read_bytes());current=save(stage/'result.recovery-01.json',passed)
    save(original,{**passed,'status':'failed','error':{'type':'ModuleNotFoundError'}})
    certificate=save(stage/'prestart-recovery/qualification.json',{'stub':'checked upstream'})
    proof={'current_result':pointer(current),'original_failed_result':pointer(original),
        'qualification':pointer(certificate),'protected':[],'event_bindings':[]}
    monkeypatch.setattr(recovery,'resolve_from_reader',lambda *a,**k:proof)
    if changed_certificate:certificate.write_text('{}')
    if changed_certificate:
        with pytest.raises(ValueError):level2_storage.Inventory(task.parents[2],stage,'stage')
    else:
        inventory=level2_storage.Inventory(task.parents[2],stage,'stage')
        assert all(inventory.evidence[p['path']]==p['sha256'] for p in
                   (proof['original_failed_result'],proof['current_result'],proof['qualification']))
        assert len(inventory.files)==24 and json.loads(original.read_bytes())['status']=='failed'
