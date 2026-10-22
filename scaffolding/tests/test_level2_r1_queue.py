"""CPU-only queue identity, crash boundaries and source-failure attribution."""
import json
import fcntl
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scaffolding/collection/scripts'))
import level2_r1_queue as q
from test_level2_failure_classification import compiler, save


@pytest.fixture
def queued(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'; scripts = repo / 'scaffolding/collection/scripts'; scripts.mkdir(parents=True)
    calls = tmp_path / 'calls.jsonl'
    child = scripts / 'level2_iteration.py'
    child.write_text('import json,sys\nfrom pathlib import Path\n'
        + 'args=sys.argv[1:]\n'
        + f'with Path({str(calls)!r}).open("a") as f:f.write(json.dumps(args)+"\\n")\n'
        + 'op=args[args.index("--operator")+1]\n'
        + 'raise SystemExit(1 if op=="apply_adam_w" and args[0]=="candidate" else 0)\n')
    (scripts / 'level2_r1_queue.py').write_text('# immutable coordinator fixture')
    (scripts / 'run_msprof_exploration_stage.py').write_text('# immutable stage fixture')
    (scripts / 'prepare_trace_pilot.py').write_text('# immutable snapshot fixture')
    monkeypatch.setattr(q, 'ROOT', repo)
    monkeypatch.setattr(q, 'FRESH_PRODUCERS', {'level2_iteration.py'})
    run = tmp_path / 'run'; (run / 'bootstrap').mkdir(parents=True)
    order = [op for op in q.iteration.OPERATORS if op != 'maximum']
    rows = []
    for op in order:
        cid = op + ('001v2' if op in ('scatter','unsorted_segment_sum','cross_entropy_loss') else '001')
        task = run / 'train/tasks' / op; parent = task / 'candidates' / cid; parent.mkdir(parents=True)
        for filename in ('pre-registration-source.tar','proposal.json'):
            (parent / filename).write_text('{}')
        for filename in ('measurement-policy.json','manifest.json','baseline-source.tar'):
            (task / filename).write_text('{}')
        rows.append({'operator':op,'split':'train','r1_candidate':cid,
            'input_bindings':{'proposal':q.pointer(parent/'proposal.json'),
                              'policy':q.pointer(task/'measurement-policy.json')}})
    schedule = save(run/'schedule.json', {'scheduling':{'after_current_recommended_new_operator_order':order},'operators':rows})
    engineering = save(run/'bootstrap/frozen-engineering-008.json', {
        'version':'level2_frozen_engineering_v1',
        'files':[dict(q.pointer(p), snapshot=str(p)) for p in scripts.iterdir()]})
    monkeypatch.setattr(q, 'check_entry', lambda entry, **kwargs: None)
    monkeypatch.setattr(q, 'baseline_evidence', lambda request,entry,**kwargs: {'status':'baseline_validated_and_calibrated'})
    monkeypatch.setattr(q, 'candidate_evidence', lambda request,entry,**kwargs: {
        'status':'source_attempt_failed' if entry['operator']=='apply_adam_w' else 'measured'})
    out=run/'preflight/r1-queue-01'
    q.prepare(run,schedule,engineering,out)
    return out,calls,order,schedule,engineering


def test_serial_r1_only_source_failure_continues_and_clean_resume_never_relaunches(queued):
    out,calls,order,*_=queued
    assert q.execute(out)['status']=='completed'
    commands=[json.loads(line) for line in calls.read_text().splitlines()]
    assert len(commands)==30
    assert [(c[c.index('--operator')+1],c[0]) for c in commands]==[(op,phase) for op in order for phase in ('baseline','candidate')]
    assert all('--deduplicate-outputs' in c and c[c.index('--epoch')+1]=='local-raw-01'
        and c[c.index('--calibration-group')+1]=='aa-local-01' for c in commands)
    assert all('002' not in ' '.join(c) and '003' not in ' '.join(c) for c in commands)
    original=calls.read_bytes()
    assert q.execute(out)['status']=='completed'
    assert calls.read_bytes()==original


def test_infrastructure_block_stops_global_queue_without_next_child(queued,monkeypatch):
    out,calls,order,*_=queued
    def blocked(*args):raise ValueError('unknown infrastructure failure')
    monkeypatch.setattr(q,'candidate_evidence',blocked)
    result=q.execute(out)
    assert result['status']=='blocked' and result['operator']==order[0]
    assert len(calls.read_text().splitlines())==2
    with pytest.raises(ValueError,match='explicit evidence recovery'):q.execute(out)
    assert len(calls.read_text().splitlines())==2


def test_lost_child_exit_receipt_never_retries_native(queued,monkeypatch):
    out,calls,order,*_=queued
    real=q.run_command
    def interrupted(*args):
        real(*args)
        raise KeyboardInterrupt('coordinator interrupted after child exited')
    monkeypatch.setattr(q,'run_command',interrupted)
    with pytest.raises(KeyboardInterrupt):q.execute(out)
    monkeypatch.setattr(q,'run_command',real)
    assert q.execute(out)['status']=='blocked'
    assert len(calls.read_text().splitlines())==1
    assert not (out/order[0]/'baseline/finished.json').exists()


@pytest.mark.parametrize('mutation',['schedule','producer','settings','source_order','finished_log','finished_exit'])
def test_resume_identity_changes_never_launch_new_child(queued,mutation):
    out,calls,order,schedule,_=queued
    if mutation.startswith('finished'):
        q.execute(out);before=calls.read_bytes()
        directory=out/order[0]/'baseline'
        if mutation=='finished_log':(directory/'stdout.log').write_text('changed')
        else:
            data=q.load(directory/'finished.json');data['execution']['returncode']=9
            q.atomic(directory/'finished.json',data)
        assert q.execute(out)['status']=='blocked'
        assert calls.read_bytes()==before
        return
    if mutation=='schedule':schedule.write_text('{}')
    elif mutation=='producer':(q.ROOT/'scaffolding/collection/scripts/level2_iteration.py').write_text('#changed')
    else:
        request=q.load(out/'request.json')
        if mutation=='settings':request['settings']['epoch']='other'
        else:request['entries'].reverse()
        q.atomic(out/'request.json',request)
        state=q.load(out/'state.json');state['request']=q.pointer(out/'request.json');q.atomic(out/'state.json',state)
    with pytest.raises(ValueError):q.execute(out)
    assert not calls.exists()


def test_prepare_cannot_replace_an_existing_queue(queued):
    out,_,_,schedule,engineering=queued
    with pytest.raises(ValueError,match='fresh queue'):
        q.prepare(out.parents[1],schedule,engineering,out)


def test_second_coordinator_cannot_launch_while_first_holds_queue_lock(queued):
    out,calls,*_=queued
    with (out/'queue.lock').open('a') as first:
        fcntl.flock(first,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):q.execute(out)
    assert not calls.exists()


def test_positive_source_failure_requires_real_classification_and_closed_observation(tmp_path,monkeypatch):
    task,parent,failed=compiler(tmp_path);cid=parent.name;op=task.name
    classification=q.classify_failure(task,parent,stage=failed)
    assert classification['status']=='source_attempt_failed'
    stage_ref=q.pointer(parent/'stages/build/result.json')
    item={'source_hash':'sha256:'+'a'*64,'source_parent':{'candidate_id':None,'source_hash':'sha256:'+'b'*64},
        'feedback_closed':True,'observation_ids':['o1']}
    feedback={'operator':op,'candidate_id':cid,'source_hash':item['source_hash'],'source_parent':item['source_parent'],
        'status':'source_attempt_failed','measurement_error':None,'semantic_guards':None,'failure_classification':classification,
        'stages':[{'stage_id':failed['stage_id'],'kind':'build','status':'failed','error':failed['error'],'result':stage_ref}]}
    feedback_path=save(task/'feedback/one.json',feedback)
    observation={'close_feedback':True,'report_ref':q.sha(feedback_path),'feedback':feedback,'stage_attempts':{failed['stage_id']:1}}
    state={'new_source_attempts':1,'new_rounds_started':1,'candidates':{cid:item},'observations':{'o1':observation},
        'stages':{failed['stage_id']:{'candidate_id':cid,'kind':'build','attempts':[{'outcome':'failed'}]}}}
    ledger=SimpleNamespace(state={'tasks':{op:state}},config={})
    monkeypatch.setattr(q,'check_entry',lambda entry,**kwargs:(ledger,task))
    monkeypatch.setattr(q.finalizer,'recorded_stage',lambda *args:(failed,stage_ref))
    monkeypatch.setattr(q,'verify_pointer_tree',lambda *a,**k:None)
    entry={'operator':op,'candidate_id':cid}
    assert q.candidate_evidence({'run':str(tmp_path)},entry)['status']=='source_attempt_failed'
    (parent/'build/build-execution/stderr.log').write_text('No space left on device')
    with pytest.raises(ValueError,match='positive evidence'):q.candidate_evidence({'run':str(tmp_path)},entry)
    observation['close_feedback']=False
    with pytest.raises(ValueError,match='infrastructure block'):q.candidate_evidence({'run':str(tmp_path)},entry)


def test_atomic_failure_does_not_replace_previous_checkpoint(tmp_path,monkeypatch):
    path=tmp_path/'checkpoint.json';q.atomic(path,{'status':'old'});before=path.read_bytes()
    def fail(*args):raise OSError('persistence failure')
    monkeypatch.setattr(q.os,'fsync',fail)
    with pytest.raises(OSError):q.atomic(path,{'status':'new'})
    assert path.read_bytes()==before


def test_completed_r1_reaudit_allows_later_registered_sources_but_pending_does_not(queued,monkeypatch):
    out,calls,order,*_=queued
    assert q.execute(out)['status']=='completed';before=calls.read_bytes()
    seen=[]
    def check(entry, *, allow_later=False):
        seen.append((entry['operator'],allow_later))
        if not allow_later:raise ValueError('later R2 was registered')
    monkeypatch.setattr(q,'check_entry',check)
    assert q.execute(out)['status']=='completed'
    assert all(flag for _,flag in seen) and calls.read_bytes()==before


def test_recovery_reconciles_unchanged_executed_child_without_relaunch(queued,monkeypatch):
    out,calls,order,*_=queued;auditor=q.candidate_evidence
    def blocked(*args,**kwargs):raise ValueError('positive proof not yet available')
    monkeypatch.setattr(q,'candidate_evidence',blocked)
    assert q.execute(out)['status']=='blocked'
    op=order[0];before=calls.read_bytes();blocked_bytes=(out/op/'blocked.json').read_bytes()
    monkeypatch.setattr(q,'candidate_evidence',auditor)
    result=q.recover(out,op,'Reviewed immutable feedback recovery now supplies positive classification')
    assert result['status']=='reconciled' and result['no_child_executed']
    assert calls.read_bytes()==before and (out/op/'blocked.json').read_bytes()==blocked_bytes
    assert q.execute(out)['status']=='completed'
    commands=[json.loads(line) for line in calls.read_text().splitlines()]
    assert len(commands)==30
    assert sum(c[0]=='candidate' and c[c.index('--operator')+1]==op for c in commands)==1


@pytest.mark.parametrize('mutation',['log','exit','missing_exit','still_blocked'])
def test_recovery_requires_unchanged_complete_evidence_and_positive_audit(queued,monkeypatch,mutation):
    out,calls,order,*_=queued;auditor=q.candidate_evidence
    def blocked(*args,**kwargs):raise ValueError('still infrastructure blocked')
    monkeypatch.setattr(q,'candidate_evidence',blocked);q.execute(out)
    op=order[0];directory=out/op/'candidate';before=calls.read_bytes()
    if mutation!='still_blocked':monkeypatch.setattr(q,'candidate_evidence',auditor)
    if mutation=='log':(directory/'stderr.log').write_text('changed')
    elif mutation=='exit':
        value=q.load(directory/'execution.json');value['returncode']=8;q.atomic(directory/'execution.json',value)
    elif mutation=='missing_exit':(directory/'execution.json').unlink()
    with pytest.raises((ValueError,FileNotFoundError)):
        q.recover(out,op,'Explicit recovery request')
    assert calls.read_bytes()==before and q.load(out/'state.json')['status']=='blocked'
    assert not (directory/'finished.json').exists()


def test_measured_completed_r1_replays_pinned_observation_after_final_starts(tmp_path,monkeypatch):
    task=tmp_path/'train/tasks/maximum';cid='maximum001';parent=task/'candidates'/cid
    source='sha256:'+'a'*64;baseline='sha256:'+'b'*64
    item={'source_hash':source,'source_parent':{'candidate_id':None,'source_hash':baseline},
        'feedback_closed':False,'observation_ids':['r1-observation']}
    results={};rows={};facts=[]
    for kind in ('build','correctness','runtime','timing'):
        group='search' if kind=='timing' else kind;sid=cid+'-'+group
        value={'stage_id':sid,'kind':kind,'status':'passed','error':None}
        path=save(parent/'stages'/group/'result.json',value)
        results[sid]=(value,q.pointer(path))
        rows[sid]={'candidate_id':cid,'kind':kind,'plan':{'purpose':'search'},'attempts':[{'outcome':'success'}]}
        facts.append({**value,'result':q.pointer(path)})
    search_stage_ids=set(rows)
    rows[cid+'-final']={'candidate_id':cid,'kind':'timing','plan':{'purpose':'final'},'attempts':[{'outcome':None}]}
    guard={'status':'passed','cases':[{'expected_process_passed':True,'dispatch_log_passed':True}]}
    guard_path=save(parent/'boundary-validation/completion.json',guard)
    save(parent/'plans/search/stage-plan.json',{})
    feedback={'operator':'maximum','candidate_id':cid,'source_hash':source,'source_parent':item['source_parent'],
        'status':'measured','measurement_error':None,'semantic_guards':q.pointer(guard_path),
        'failure_classification':None,'stages':facts,'comparisons':[{'verified':'original R1 comparison'}]}
    feedback_path=save(task/'feedback/original-r1.json',feedback)
    observation={'close_feedback':True,'report_ref':q.sha(feedback_path),'feedback':feedback,
        'stage_attempts':dict.fromkeys(search_stage_ids,1)}
    state={'new_source_attempts':3,'new_rounds_started':3,'frozen':True,'candidates':{cid:item},
        'observations':{'r1-observation':observation},'stages':rows}
    ledger=SimpleNamespace(state={'tasks':{'maximum':state}},config={'tasks':{'maximum':{'baseline_source_hash':baseline}}})
    monkeypatch.setattr(q,'check_entry',lambda entry,**kwargs:(ledger,task))
    monkeypatch.setattr(q.finalizer,'recorded_stage',lambda run,op,candidate,sid,row:results[sid])
    monkeypatch.setattr(q.finalizer,'runtime_evidence',lambda *a:None)
    monkeypatch.setattr(q.iteration,'boundary_result',lambda *a:guard)
    monkeypatch.setattr(q.iteration,'check_timing_settings',lambda *a:None)
    monkeypatch.setattr(q.iteration,'comparison_reports',lambda *a,**k:feedback['comparisons'])
    monkeypatch.setattr(q,'verify_pointer_tree',lambda *a,**k:None)
    entry={'operator':'maximum','candidate_id':cid};request={'run':str(tmp_path)}
    audited=q.candidate_evidence(request,entry,allow_later=True,observation_id='r1-observation')
    assert audited['status']=='measured' and audited['observation_id']=='r1-observation'
    with pytest.raises(ValueError,match='closed real source feedback'):q.candidate_evidence(request,entry)
    state['frozen']=False
    with pytest.raises(ValueError,match='closed real source feedback'):
        q.candidate_evidence(request,entry,allow_later=True,observation_id='r1-observation')
    state['frozen']=True;observation['close_feedback']=False
    with pytest.raises(ValueError,match='infrastructure block'):
        q.candidate_evidence(request,entry,allow_later=True,observation_id='r1-observation')


# Preserve the production validator before the broad subprocess fixture replaces
# it. These tests use genuine deterministic tar files and an append-only ledger.
_REAL_CHECK_ENTRY = q.check_entry
_REAL_CANDIDATE_EVIDENCE = q.candidate_evidence


@pytest.fixture
def materialized_queue(queued, monkeypatch):
    old_queue, calls, order, schedule, engineering = queued
    run=old_queue.parents[1];document=q.load(schedule);workloads={}
    for row in document['operators']:
        op=row['operator'];cid=row['r1_candidate'];task=run/'train/tasks'/op;parent=task/'candidates'/cid
        for base,label,content,target in ((task/'baseline',op,'baseline',task/'baseline-source.tar'),
            (parent/'op',cid,'candidate',parent/'pre-registration-source.tar')):
            for folder in ('op_host','op_kernel'):
                path=base/folder/(op+'.asc');path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(content+' '+folder+'\n')
            (base/'CMakeLists.txt').write_text('protected build metadata\n')
            target.unlink()
            q.create_source_snapshot(base,target,root_label=label)
        save(parent/'proposal.json',{'operator':op,'candidate_id':cid,'source_parent':'baseline',
            'implementation_source_hash':q.sha(parent/'pre-registration-source.tar'),
            'source_dir':str(parent/'op'),'decision_basis':[]})
        row['input_bindings']['proposal']=q.pointer(parent/'proposal.json')
        workloads[op]={'baseline_source_hash':q.sha(task/'baseline-source.tar'),'source_split':'train',
            'repeat_by_case':{str(c):1 for c in q.campaign.ALL_CASES},'pilot_ref':'sha256:'+'a'*64}
    save(schedule,document)
    ledger=q.campaign.create_fresh(run/'train/ledger',campaign_id='materialized-preview-test',workloads=workloads)
    monkeypatch.setattr(q,'check_entry',_REAL_CHECK_ENTRY)
    output=run/'preflight/r1-real-preview-01'
    q.prepare(run,schedule,engineering,output)
    request=q.load(output/'request.json')
    return SimpleNamespace(queue=output,run=run,entries=request['entries'],request=request,ledger=ledger,calls=calls)


def register_materialized(f, entry, *, source_ref_override=None, proposal_ref_override=None):
    """CPU-only registration fixture; no stage runner or native process."""
    op=entry['operator'];cid=entry['candidate_id'];task=Path(entry['task']);parent=task/'candidates'/cid
    ledger=q.campaign.Campaign(f.run/'train/ledger')
    baseline=ledger.config['tasks'][op]['baseline_source_hash']
    for kind in ('build','correctness','runtime'):
        sid='baseline-'+kind
        plan={'case_ids':q.campaign.ALL_CASES,'source_hash':baseline}
        ledger.start(event_id=op+'-'+sid+'-start',workload=op,stage_id=sid,kind=kind,plan=plan)
        result=save(task/'stages'/kind/'result.json',{'status':'passed','fixture':'synthetic closed prerequisite'})
        ledger.finish(event_id=op+'-'+sid+'-finish',workload=op,stage_id=sid,outcome='success',
            evidence={'result':q.pointer(result),'prepared_output_checked':True},
            native_started=kind!='build')
    q.create_source_snapshot(parent/'op',parent/'source.tar',root_label=cid)
    ledger.register(event_id=cid+'-register',workload=op,candidate_id=cid,
        source_hash=q.sha(parent/'source.tar'),patch_hash='sha256:'+'b'*64,
        source_parent={'candidate_id':None,'source_hash':baseline},decision_basis=[],
        artifacts={'source':source_ref_override or q.pointer(parent/'source.tar'),
                   'proposal':proposal_ref_override or q.pointer(parent/'proposal.json')})
    return parent


def test_prepare_binds_real_materialized_previews_without_registering_sources(materialized_queue):
    f=materialized_queue
    assert len(f.entries)==15
    assert not f.calls.exists()
    for entry in f.entries:
        task=Path(entry['task']);parent=task/'candidates'/entry['candidate_id']
        assert entry['bindings']['source_preview']==q.pointer(parent/'pre-registration-source.tar')
        assert not (parent/'source.tar').exists()
        ledger,_=q.check_entry(entry)
        assert not ledger.state['tasks'][entry['operator']]['candidates']
        with pytest.raises(ValueError,match='no formal registration'):
            q.check_entry(entry,require_registered=True)


def test_registration_must_reproduce_fixed_preview_and_complete_tree(materialized_queue):
    f=materialized_queue;entry=f.entries[0];preview=dict(entry['bindings']['source_preview'])
    parent=register_materialized(f,entry)
    ledger,_=q.check_entry(entry,require_registered=True)
    assert q.sha(parent/'source.tar')==preview['sha256']
    assert entry['bindings']['source_preview']==preview
    assert ledger.state['tasks'][entry['operator']]['candidates'][entry['candidate_id']]['artifacts']['source']==q.pointer(parent/'source.tar')
    # A second read cannot replace the bound preview with the new formal file.
    q.check_entry(entry,require_registered=True)
    assert q.load(f.queue/'request.json')['entries'][0]['bindings']['source_preview']==preview
    assert not f.calls.exists()


@pytest.mark.parametrize('mutation',['preview','native_tree','protected_tree','file_mode','formal','formal_only',
    'ledger_source_artifact','ledger_proposal_artifact','preview_path_alias','formal_symlink'])
def test_preview_and_formal_identity_drift_is_never_silently_substituted(materialized_queue,mutation):
    f=materialized_queue;entry=f.entries[0];parent=Path(entry['task'])/'candidates'/entry['candidate_id']
    if mutation=='preview':
        path=parent/'pre-registration-source.tar';path.write_bytes(path.read_bytes()+b'changed')
    elif mutation in ('native_tree','protected_tree'):
        path=parent/'op'/('op_kernel/'+entry['operator']+'.asc' if mutation=='native_tree' else 'CMakeLists.txt')
        path.write_text(path.read_text()+'changed')
    elif mutation=='file_mode':
        path=parent/'op/CMakeLists.txt';path.chmod(path.stat().st_mode ^ 0o100)
    elif mutation=='formal_symlink':
        (parent/'source.tar').symlink_to(parent/'missing-outside-archive.tar')
    elif mutation=='formal_only':
        q.create_source_snapshot(parent/'op',parent/'source.tar',root_label=entry['candidate_id'])
    elif mutation=='ledger_source_artifact':
        register_materialized(f,entry,source_ref_override=entry['bindings']['source_preview'])
    elif mutation=='ledger_proposal_artifact':
        register_materialized(f,entry,proposal_ref_override={'path':str(parent/'proposal.json'),'sha256':'sha256:'+'c'*64})
    elif mutation=='preview_path_alias':
        alias=parent/'another-preview.tar';alias.write_bytes((parent/'pre-registration-source.tar').read_bytes())
        entry['bindings']['source_preview']=q.pointer(alias)
    else:
        register_materialized(f,entry)
        path=parent/'source.tar';path.write_bytes(path.read_bytes()+b'changed')
    with pytest.raises(ValueError):q.check_entry(entry)
    assert not f.calls.exists()


def test_candidate_evidence_demands_registered_preview_equivalence(materialized_queue,monkeypatch):
    entry=materialized_queue.entries[0]
    # Use the real candidate auditor while its stage work has not started.
    with pytest.raises(ValueError,match='no formal registration'):
        _REAL_CANDIDATE_EVIDENCE(materialized_queue.request,entry)


def test_candidate_controller_registers_preview_before_any_stage(materialized_queue,monkeypatch):
    f=materialized_queue;entry=f.entries[0];cid=entry['candidate_id'];calls=[]
    parent=Path(entry['task'])/'candidates'/cid;preview=q.pointer(parent/'pre-registration-source.tar')
    def register(run,operator,candidate,proposal):
        assert Path(run)==f.run and operator==entry['operator'] and candidate==cid
        assert Path(proposal)==parent/'proposal.json'
        calls.append('register')
        register_materialized(f,entry)
    def no_native(*args,**kwargs):
        q.check_entry(entry,require_registered=True)
        calls.append('stage')
        raise RuntimeError('CPU fixture stops before first native/build stage')
    monkeypatch.setattr(q.iteration,'register_proposal',register)
    monkeypatch.setattr(q.iteration,'stage',no_native)
    with pytest.raises(RuntimeError,match='CPU fixture stops'):
        q.iteration.candidate(f.run,entry['operator'],cid)
    assert calls==['register','stage']
    assert q.pointer(parent/'pre-registration-source.tar')==preview
    assert q.sha(parent/'source.tar')==preview['sha256']


def test_operator_limit_yields_only_complete_checkpoint_and_resumes_without_relaunch(queued):
    out,calls,order,*_=queued;request=(out/'request.json').read_bytes()
    first=q.execute(out,max_new_operators=1)
    assert first['status']=='operator_limit_reached' and first['after_operator']==order[0]
    assert first['new_operators_completed']==1
    assert len(calls.read_text().splitlines())==2
    first_finished=(out/order[0]/'candidate/finished.json').read_bytes()
    assert q.load(out/'state.json')['operators'][order[0]]['checkpoint']==first['checkpoint']
    second=q.execute(out,max_new_operators=1)
    assert second['status']=='operator_limit_reached' and second['after_operator']==order[1]
    assert len(calls.read_text().splitlines())==4
    assert (out/order[0]/'candidate/finished.json').read_bytes()==first_finished
    assert (out/'request.json').read_bytes()==request
    assert q.execute(out)['status']=='completed'
    assert len(calls.read_text().splitlines())==30
    assert q.execute(out,max_new_operators=1)['status']=='completed'
    assert len(calls.read_text().splitlines())==30


def test_operator_limit_reaudits_old_receipts_before_starting_next_operator(queued):
    out,calls,order,*_=queued
    assert q.execute(out,max_new_operators=1)['status']=='operator_limit_reached'
    before=calls.read_bytes()
    (out/order[0]/'candidate/stdout.log').write_text('changed retained child log')
    assert q.execute(out,max_new_operators=1)['status']=='blocked'
    assert calls.read_bytes()==before
    assert not (out/order[1]).exists()


def test_operator_limit_never_returns_success_before_checkpoint_is_durable(queued,monkeypatch):
    out,calls,order,*_=queued;real=q.atomic
    def interrupted(path,value,**kwargs):
        if path.name=='checkpoint.json' and value.get('phase')=='candidate' and value.get('finished'):
            raise OSError('operator checkpoint persistence failed')
        return real(path,value,**kwargs)
    monkeypatch.setattr(q,'atomic',interrupted)
    value=q.execute(out,max_new_operators=1)
    assert value['status']=='blocked' and q.load(out/'state.json')['status']=='blocked'
    assert len(calls.read_text().splitlines())==2
    assert not (out/order[1]).exists()


@pytest.mark.parametrize('limit',[0,-1,True,1.0,'1'])
def test_invalid_operator_limit_never_launches_or_changes_queue(queued,limit):
    out,calls,*_=queued;before=(out/'state.json').read_bytes()
    with pytest.raises(ValueError,match='positive integer'):q.execute(out,max_new_operators=limit)
    assert not calls.exists() and (out/'state.json').read_bytes()==before


def test_operator_limit_cli_returns_success_for_checkpoint_yield(queued,monkeypatch):
    out,calls,order,*_=queued
    monkeypatch.setattr(sys,'argv',['level2_r1_queue.py','run','--queue',str(out),'--max-new-operators','1'])
    assert q.main()==0
    assert q.load(out/'state.json')['status']=='operator_limit_reached'
    assert len(calls.read_text().splitlines())==2
