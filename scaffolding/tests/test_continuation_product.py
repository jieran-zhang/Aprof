"""CPU-only actual ledger/certificate tests. No native collector, locks or payload."""
from pathlib import Path
import copy,hashlib,json,os,sys
import pytest
HERE=Path(__file__).resolve().parents[2]
LIVE=Path(os.environ.get('APROF_TEST_REPO',str(HERE)))
sys.path[:0]=[str(HERE/'scaffolding/collection/scripts'),str(LIVE/'scaffolding/collection/scripts'),str(LIVE/'src')]
import level2_cohort_continuation as c
import msprof_exploration_campaign as campaign
from msprof_exploration_execute import save,event,pointer


def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,sort_keys=True)+'\n');return pointer(path)
def h(n):return 'sha256:'+f'{n:064x}'
def journal(name,failed=False):
    rows=[{'type':'process_start','session_id':name}]
    for _ in range(6 if failed else 12):
        rows += [{'type':'case_start','session_id':name},{'type':'warmup_complete','session_id':name,'calls_per_role':10}]
        rows += [{'type':'sample','session_id':name,'repeat':10,'launches_per_call':2} for _ in range(60)]
    if failed:rows += [{'type':'failure','session_id':name,'error':'output open failed'}]
    rows += [{'type':'session_end','session_id':name,'exit_code':1 if failed else 0,'stream_destroyed':True,'context_destroyed':True}]
    return b''.join(json.dumps(r).encode()+b'\n' for r in rows)

def certified(tmp_path):
    run=tmp_path/'run';task=run/'validation/tasks/dynamic_quant';child=task/'candidates/dynamic_quant001';stage=child/'stages/search';cohort=stage/'direct_parent';d=cohort/'continuation-01';d.mkdir(parents=True)
    manifest=put(task/'manifest.json',{'task_dir':str(task)});cm=put(run/'campaign-manifest.json',{'fixture':'no native'})
    ledger=campaign.create_fresh(run/'validation/ledger',campaign_id='fixture',workloads={'dynamic_quant':{'baseline_source_hash':h(1),'source_split':'validation','repeat_by_case':{str(i):10 for i in range(1,21)},'pilot_ref':h(2)}})
    def ready(cid,source):
        for kind in ('build','correctness','runtime'):
            sid=(cid or 'baseline')+'-'+kind
            ledger.start(event_id=sid+'-start',workload='dynamic_quant',stage_id=sid,candidate_id=cid,kind=kind,plan={'source_hash':source,'case_ids':list(range(1,21))})
            ledger.finish(event_id=sid+'-finish',workload='dynamic_quant',stage_id=sid,outcome='success',native_started=kind!='build',evidence={'result_ref':h(3),'prepared_output_checked':kind=='correctness'})
    ready(None,h(1))
    ledger.register(event_id='registered',workload='dynamic_quant',candidate_id=c.CANDIDATE,source_hash=c.SOURCE,patch_hash=h(4),source_parent={'candidate_id':None,'source_hash':h(1)},decision_basis=[],probes=[{'case_id':6,'reason':'declared int case'},{'case_id':16,'reason':'declared tail'}])
    ready(c.CANDIDATE,c.SOURCE)
    schedule=[{'name':f'dynamic_quant001-search-direct-parent-p{i:02d}','request':{'slot':i}} for i in range(1,7)]
    cp={'protocol':'msprof_task_time_exploration_v2','schedule':schedule,'case_ids':[1,8,14,20,6,16]};cpref=put(cohort/'plan.json',cp)
    frozen=put(child/'plans/search/direct_parent-cohort.json',cp)
    sp=ledger.timing_plan('dynamic_quant',c.CANDIDATE,purpose='search',manifest_ref=h(5),final_candidate_ids=[c.CANDIDATE],cohorts=[{'relation':'direct_parent','control_candidate_id':'baseline','plan':frozen}])
    sp['calibration_report']=put(task/'calibration.json',{'fixture':True})
    spr=put(stage/'stage-plan.json',sp)
    ledger.start(event_id='dynamic_quant-dynamic_quant001-search-start',workload='dynamic_quant',stage_id=c.STAGE,candidate_id=c.CANDIDATE,kind='timing',plan=sp)
    event(task,'stage_started',{'candidate_id':c.CANDIDATE,'stage':c.STAGE,'plan':spr})
    orig=[cohort/r['name'] for r in schedule];refs=[put(cohort/'identity-preflight.json',{'fixture':True})]
    scripts=tmp_path/'repo/scripts';scripts.mkdir(parents=True)
    producers=[];engfiles=[]
    for name in sorted(c.REQUIRED_PRODUCERS):
        p=scripts/name;p.write_text('# inert tiny producer '+name);r=pointer(p);producers.append(r);cas=run/'bootstrap/source-cas'/r['sha256'][7:];cas.parent.mkdir(parents=True,exist_ok=True);cas.write_bytes(p.read_bytes());engfiles.append({**r,'snapshot':str(cas)})
    scratch=tmp_path/'scratch/raw';scratch.mkdir(parents=True);(scratch/'fake-profiler.bin').write_bytes(b'private tiny capture')
    for i,p in enumerate(orig[:3]):
        refs.append(put(p/'request.json',schedule[i]['request']));refs.append(put(p/'bindings.json',{r['path']:r['sha256'] for r in producers}))
        (p/'native').mkdir();(p/'native/journal.jsonl').write_bytes(journal(p.name,failed=i==2));refs.append(pointer(p/'native/journal.jsonl'))
        if i<2:
            for name,value in [('completion.json',{'status':'passed','error':None}),('msprof.execution.json',{'exit_code':0,'error':None}),('samples.json',{}),('validation.json',{}),('cases.json',{}),('cases.tsv',{}),('health-before.json',{}),('health-after.json',{})]:refs.append(put(p/name,value))
        else:refs.append(put(p/'raw-storage.request.json',{'capture_root':str(scratch),'archive_root':str(p/'raw')}))
    eng={'version':'level2_frozen_engineering_v1','campaign_manifest':cm,'task_manifests':[manifest,{'path':str(run/'train/tasks/other/manifest.json'),'sha256':h(444)}],'files':engfiles}
    oldeng=put(run/'bootstrap/frozen-engineering-024.json',eng);neweng=put(run/'bootstrap/frozen-engineering-025.json',{**eng,'fixture_revision':2})
    forensic=put(tmp_path/'external/forensics.json',{'preserved_refs':[],'sessions':[]});owner=put(task/'original-owner-request.json',{});health=put(tmp_path/'external/health.json',{'status':'passed','no_device_processes':True,'processes':[]})
    terminal=put(tmp_path/'external/terminal.json',{'version':'dq001_terminal_infrastructure_owner_receipt_v1','source_hash':c.SOURCE,'writer_terminal':True,'source_feedback_closed':False,'tool_result':{'session_id':89943,'exit_code':1,'terminal':True,'evidence_origin':'actual root observation'},'allowed_open_stage':{'stage_id':c.STAGE,'plan':spr},'owner_request':owner,'forensics':forensic,'health_after':health})
    import importlib.util
    spec=importlib.util.spec_from_file_location('tiny_preservation_writer',HERE/'scaffolding/tests/preservation_writer_fixture.py')
    writer=importlib.util.module_from_spec(spec);spec.loader.exec_module(writer)
    writer.P03=orig[2];writer.SCRATCH=scratch;writer.OUTPUT=child/'failed-search-p03-preservation-01';writer.ALLOCATION=pointer(orig[2]/'raw-storage.request.json');writer.JOURNAL=pointer(orig[2]/'native/journal.jsonl');writer.TERMINAL=terminal
    preserved=writer.execute(pointer(HERE/'scaffolding/tests/preservation_writer_fixture.py')['sha256'])
    source={'path':str(child/'source.tar'),'sha256':c.SOURCE}
    lp=d/'ledger-prefix.jsonl';lp.write_bytes((run/'validation/ledger/events.jsonl').read_bytes());tp=d/'task-prefix.jsonl';tp.write_bytes((task/'events.jsonl').read_bytes())
    value={'version':c.VERSION,'run':str(run),'operator':c.OPERATOR,'candidate_id':c.CANDIDATE,'stage_id':c.STAGE,'source':source,'stage_plan':spr,'cohort_plan':cpref,'terminal_receipt':terminal,'preservation':preserved,'old_engineering':oldeng,'consumer_engineering':neweng,'producers':producers,'ledger_prefix':pointer(lp),'task_prefix':pointer(tp),'original_metadata':refs,'original_absent':[str(stage/'result.json'),str(cohort/'group-completion.json'),str(cohort/'identity-resolution.json'),str(cohort/'producer-summary.json'),str(cohort/'report.json')],'reuse_sessions':[str(p) for p in orig[:2]],'failed_session':str(orig[2]),'replacement_name':orig[2].name+'-continuation-01','failed_costs':c.journal_costs((orig[2]/'native/journal.jsonl').read_bytes(),failed=True),'scope':'one_original_active_attempt_no_new_source_start_or_charge'}
    cert=put(d/'qualification.json',value);proof=c.resolve(cohort,qualification_only=True)
    args={'workload':c.OPERATOR,'stage_id':c.STAGE,'source_hash':c.SOURCE,'plan_hash':c.digest(sp),'qualification':cert,'reason':'Explicit quota interruption continuation; original failed process retained.'}
    ledger.qualify_continuation(event_id='qualified',**args);event(task,'stage_continuation_qualified',{'candidate_id':c.CANDIDATE,'stage':c.STAGE,'qualification':cert})
    return {'cohort':cohort,'stage':stage,'task':task,'run':run,'child':child,'certificate':value,'cert':cert,'ledger':ledger,'original':orig,'args':args}

def close(f):
    proof=c.resolve(f['cohort']);paths=proof['directories']
    for name in paths[2:]:
        p=Path(name)/'native/journal.jsonl';p.parent.mkdir(parents=True);p.write_bytes(journal(Path(name).name))
    costs=dict(proof['failed_costs'])
    for name in paths:
        for key,n in c.journal_costs((Path(name)/'native/journal.jsonl').read_bytes()).items():costs[key]+=n
    result={'status':'passed','error':None,'continuation':f['cert'],'formal_samples':4320,'actual_costs':costs}
    rr=put(f['stage']/'result.json',result)
    put(f['cohort']/'group-completion.json',{'status':'passed','completed_sessions':paths,'continuation':f['cert']})
    put(f['cohort']/'report.json',{'continuation':c.annotation(proof),'sessions':[{'directory':p} for p in paths],'results':[{'qualified_performance_eligible':False}],'suite':{'normal':{'qualified_performance_eligible':False},'swapped':{'qualified_performance_eligible':False}}})
    f['ledger'].finish(event_id='finished',workload=c.OPERATOR,stage_id=c.STAGE,outcome='success',evidence={'result':rr,'continuation':f['cert']},native_started=True,formal_samples=4320,actual_costs=costs)
    return costs

def test_real_qualification_keeps_one_attempt_charge_and_all_failed_costs(tmp_path):
    f=certified(tmp_path);p=c.resolve(f['cohort']);s=f['ledger'].state['tasks'][c.OPERATOR]
    assert len(s['stages'][c.STAGE]['attempts'])==1 and s['used']['timing_groups']==1 and s['stage_starts']['timing']==1
    assert p['directories'][2].endswith('p03-continuation-01') and p['failed_costs']['formal_target_kernel_launches']==7200
    costs=close(f);p=c.resolve(f['cohort'],require_closed=True)
    assert costs['role_samples']==4680 and costs['timed_complete_calls']==46800 and costs['warmup_complete_calls']==1560 and costs['formal_target_kernel_launches']==93600
    assert costs['native_processes_started']==7 and costs['native_processes_completed']==6

@pytest.mark.parametrize('attack',['foreign_source','erase_failed','replacement','old_plan','old_native','consumer_cas','certificate','old_prefix','extra_key'])
def test_tamper_rejected(tmp_path,attack):
    f=certified(tmp_path);cert=f['certificate']
    if attack=='old_plan':Path(cert['cohort_plan']['path']).write_text('{}')
    elif attack=='old_native':(f['original'][2]/'native/journal.jsonl').write_text('{}\n')
    elif attack=='consumer_cas':
        eng=json.loads(Path(cert['consumer_engineering']['path']).read_text());Path(eng['files'][0]['snapshot']).write_text('changed')
    elif attack=='old_prefix':Path(cert['ledger_prefix']['path']).write_text('{}\n')
    else:
        if attack=='foreign_source':cert['source']['sha256']=h(99)
        elif attack=='erase_failed':cert['failed_costs']['role_samples']=0
        elif attack=='replacement':cert['replacement_name']=f['original'][2].name
        elif attack=='extra_key':cert['unreviewed_option']=True
        else:cert['scope']='forged'
        put(Path(f['cert']['path']),cert)
    with pytest.raises((ValueError,KeyError)):c.resolve(f['cohort'])


def test_closed_replay_allows_later_legal_stage_start(tmp_path):
    f=certified(tmp_path);close(f)
    ledger=f['ledger'];ledger.start(event_id='later-control',workload=c.OPERATOR,stage_id='later-aa',candidate_id=None,kind='control',plan={'control_type':'aa','source_hash':c.SOURCE,'case_ids':list(range(1,21)),'manifest_ref':h(98)})
    assert c.resolve(f['cohort'],require_closed=True)['qualification']==f['cert']


def test_native_output_retirement_explicitly_remains_unsupported(tmp_path,monkeypatch):
    f=certified(tmp_path);close(f)
    import level2_native_output_storage as native
    monkeypatch.setattr(native,'cohort_location',lambda *a,**k:(f['task'],c.OPERATOR))
    report=json.loads((f['cohort']/'report.json').read_text());report.update(operator=c.OPERATOR,evidence_status='verified_complete');put(f['cohort']/'report.json',report)
    with pytest.raises(ValueError,match='scheduled output session coverage'):native.closed_from_reader(f['cohort'],Path.read_bytes)


def test_ordinary_no_certificate_has_no_added_requirements(tmp_path):
    assert c.resolve(tmp_path/'ordinary') is None


def execution_fixture(f,monkeypatch,fail_slot=None):
    from types import SimpleNamespace
    import msprof_exploration_execute as execution
    import msprof_exploration_report as report
    import run_msprof_exploration_stage as runner
    calls=[]
    monkeypatch.setattr(c,'_live_identity',lambda proof:f['certificate'])
    monkeypatch.setattr(execution,'preflight_cohort',lambda plan:{'producer_bindings':[]})
    monkeypatch.setattr(runner,'validate_calibration_storage',lambda *a:None)
    def collect(request,directory):
        calls.append(Path(directory).name);directory.mkdir()
        if fail_slot and len(calls)==fail_slot:raise ValueError('injected real continuation infrastructure failure')
        p=directory/'native/journal.jsonl';p.parent.mkdir();p.write_bytes(journal(directory.name))
        put(directory/'completion.json',{'status':'passed','error':None});put(directory/'samples.json',{})
    monkeypatch.setattr(execution,'execution_modules',lambda:(SimpleNamespace(collect=collect,summarize=lambda ds:{'accepted':len(ds)}),None,None))
    monkeypatch.setattr(report,'verify_observation',lambda *a,**kw:None)
    def analyze(ds,plan,**kw):
        proof=c.resolve(f['cohort'])
        return {'continuation':c.annotation(proof),'sessions':[{'directory':d} for d in ds],'results':[{'qualified_performance_eligible':False}],'suite':{'normal':{'qualified_performance_eligible':False},'swapped':{'qualified_performance_eligible':False}}}
    monkeypatch.setattr(report,'analyze_task_cohort',analyze)
    return calls


def test_actual_executor_reuses_two_and_finishes_same_attempt_once(tmp_path,monkeypatch):
    f=certified(tmp_path);calls=execution_fixture(f,monkeypatch)
    result=c.execute(f['cert']['path'],f['cert']['sha256'])
    assert result['status']=='passed' and result['formal_samples']==4320 and result['actual_costs']['role_samples']==4680
    assert calls==[f'dynamic_quant001-search-direct-parent-p{i:02d}'+('-continuation-01' if i==3 else '') for i in range(3,7)]
    l=campaign.Campaign(f['run']/'validation/ledger');s=l.state['tasks'][c.OPERATOR]
    assert s['stage_starts']['timing']==1 and s['used']['timing_groups']==1 and len(s['stages'][c.STAGE]['attempts'])==1
    with pytest.raises((ValueError,FileExistsError)):c.execute(f['cert']['path'],f['cert']['sha256'])
    assert len(calls)==4


def test_actual_executor_stops_and_preserves_second_infrastructure_failure(tmp_path,monkeypatch):
    f=certified(tmp_path);calls=execution_fixture(f,monkeypatch,fail_slot=1)
    result=c.execute(f['cert']['path'],f['cert']['sha256'])
    assert result['status']=='failed' and result['formal_samples']==1440 and result['actual_costs']['role_samples']==1800
    assert len(calls)==1 and json.loads((f['stage']/'result.json').read_text())['error']['type']=='ValueError'
    assert (f['original'][2]/'native/journal.jsonl').read_bytes()==journal(f['original'][2].name,failed=True)
    with pytest.raises((ValueError,FileExistsError)):c.execute(f['cert']['path'],f['cert']['sha256'])


def test_archival_certificate_never_reads_foreign_task_manifest(tmp_path):
    f=certified(tmp_path);foreign=f['run']/'train/tasks/other/manifest.json'
    def read(path):
        assert Path(path)!=foreign,'foreign manifest must remain opaque inside engineering identity'
        return Path(path).read_bytes()
    p=c.resolve(f['cohort'],read)
    assert str(foreign) not in {r['path'] for r in p['protected']}


def test_metadata_resolver_portable_after_original_tmp_inputs_removed(tmp_path):
    f=certified(tmp_path);close(f);expected=c.resolve(f['cohort'],require_closed=True)
    for p in (tmp_path/'external').iterdir():p.unlink()
    def read(p):
        assert not Path(p).is_relative_to(tmp_path/'external'),'original temporary metadata cannot be reopened'
        assert Path(p).suffix!='.tar','metadata resolution must not reread preserved payload'
        return Path(p).read_bytes()
    actual=c.resolve(f['cohort'],read,require_closed=True)
    assert actual==expected
    assert len([r for r in actual['protected'] if r['path'].endswith('.tar')])==3  # source plus native/scratch


def test_tampered_preserved_tar_rejected_before_any_native_continuation(tmp_path,monkeypatch):
    f=certified(tmp_path);calls=execution_fixture(f,monkeypatch)
    with (f['child']/'failed-search-p03-preservation-01/original-native.tar').open('r+b') as out:out.seek(2048);out.write(b'changed')
    with pytest.raises(ValueError):c.execute(f['cert']['path'],f['cert']['sha256'])
    assert not calls and not (f['cohort']/'continuation-01/execution-started.json').exists()


def test_historical_replay_after_feedback_and_registered_round_two(tmp_path):
    f=certified(tmp_path);close(f);ledger=f['ledger']
    ledger.observe(event_id='r1-feedback',workload=c.OPERATOR,observation_id='r1-closed',candidate_id=c.CANDIDATE,
                   stage_ids=[c.CANDIDATE+'-'+k for k in ('build','correctness','runtime','search')],feedback={'actual':'closed'})
    ledger.register(event_id='r2-registered',workload=c.OPERATOR,candidate_id='dynamic_quant002',source_hash=h(80),patch_hash=h(81),
                    source_parent={'candidate_id':c.CANDIDATE,'source_hash':c.SOURCE},decision_basis=['r1-closed'],probes=[{'case_id':6,'reason':'same declared case'},{'case_id':16,'reason':'same tail'}])
    assert ledger.state['tasks'][c.OPERATOR]['new_source_attempts']==2
    assert c.resolve(f['cohort'],require_closed=True)['qualification']==f['cert']


def test_historical_producer_origin_can_change_but_inert_cas_remains_bound(tmp_path):
    f=certified(tmp_path);close(f);expected=c.resolve(f['cohort'],require_closed=True)
    origin=Path(f['certificate']['producers'][0]['path']);origin.write_text('later engineering origin')
    assert c.resolve(f['cohort'],require_closed=True)==expected


@pytest.mark.parametrize('invalid',[False,True])
def test_authorize_prevalidates_overlay_before_namespace_claim(tmp_path,monkeypatch,invalid):
    f=certified(tmp_path);cert=f['certificate'];directory=f['cohort']/'continuation-01'
    # Restore only private tiny journals to the original active, unqualified state.
    for key,origin in [('ledger_prefix',f['run']/'validation/ledger/events.jsonl'),('task_prefix',f['task']/'events.jsonl')]:
        origin.write_bytes(Path(cert[key]['path']).read_bytes())
    for p in directory.iterdir():p.unlink()
    directory.rmdir()
    import msprof_exploration_execute as ex
    original_pointer=ex.pointer;original_sha=ex.sha
    monkeypatch.setattr(c,'__file__',cert['producers'][0]['path'])
    monkeypatch.setattr(ex,'pointer',lambda p:cert['source'] if Path(p)==f['child']/'source.tar' else cert['old_engineering'] if Path(p)==Path(cert['old_engineering']['path']) else original_pointer(p))
    monkeypatch.setattr(ex,'sha',lambda p:'sha256:3716fb07a9f937f9c7ec6ab1003f8e3d112089e89dc769dba80b48299197495b' if Path(p)==Path(cert['old_engineering']['path']) else original_sha(p))
    monkeypatch.setattr(c,'_live_identity',lambda proof,certificate=None:certificate or json.loads(Path(proof['qualification']['path']).read_text()))
    original_resolve=c.resolve;calls=[]
    def resolving(cohort,read_bytes=Path.read_bytes,**kw):
        if kw.get('qualification_only') and not directory.exists():
            calls.append('prepublication')
            if invalid:raise ValueError('actual metadata preflight rejected')
        return original_resolve(cohort,read_bytes,**kw)
    monkeypatch.setattr(c,'resolve',resolving)
    args=[f['run'],cert['terminal_receipt']['path'],cert['terminal_receipt']['sha256'],cert['preservation']['path'],cert['preservation']['sha256'],cert['consumer_engineering']['path'],cert['consumer_engineering']['sha256']]
    if invalid:
        with pytest.raises(ValueError,match='preflight rejected'):c.authorize(*args)
        assert not directory.exists()
    else:
        proof=c.authorize(*args);assert original_resolve(f['cohort'])==proof
    assert calls==['prepublication']


def test_ordinary_report_without_new_helpers_keeps_existing_offline_dependencies(tmp_path,monkeypatch):
    import builtins
    import msprof_exploration_provenance as provenance
    import msprof_exploration_report as report
    original_import=builtins.__import__
    def guarded(name,*args,**kwargs):
        if name in ('level2_cohort_continuation','level2_failed_capture_preservation'):
            raise AssertionError('ordinary cohort attempted to import an unavailable optional helper')
        return original_import(name,*args,**kwargs)
    monkeypatch.setattr(builtins,'__import__',guarded)
    assert provenance.resolve_continuation(tmp_path/'ordinary') is None
    def deny_original(path):raise AssertionError('ordinary offline cohort opened an unexported optional certificate')
    assert provenance.resolve_continuation(tmp_path/'group_norm/candidates/group_norm002/stages/final/direct_parent',deny_original) is None
    monkeypatch.setattr(report,'validate_plan',lambda p:p)
    monkeypatch.setattr(report,'_verify_pointer_tree',lambda *a,**kw:[])
    reached=[]
    class Reached(Exception):pass
    def verify(*args,**kwargs):reached.append(True);raise Reached()
    monkeypatch.setattr(report,'verify_observation',verify)
    plan={'protocol':report.PROTOCOL,'calibration_scope':{},'schedule':[{'name':f'p{i}','request':{}} for i in range(6)]}
    with pytest.raises(Reached):report.analyze_task_cohort.__wrapped__([tmp_path/'ordinary'/f'p{i}' for i in range(6)],plan)
    assert reached==[True]
