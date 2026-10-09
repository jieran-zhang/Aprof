"""CPU-only nested-prefix handoff. No live run or device is accessed."""
import fcntl
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_level2_r1_queue import queued
from test_level2_r1_continuation import blocked_prefix, tree_bytes
import level2_r1_queue as q


def freeze(run, name):
    snapshots = run / 'bootstrap' / (name + '-files'); snapshots.mkdir()
    rows = []
    for path in (q.ROOT / 'scaffolding/collection/scripts').iterdir():
        snapshot = snapshots / path.name; snapshot.write_bytes(path.read_bytes())
        rows.append({**q.pointer(path), 'snapshot':str(snapshot)})
    path = run / 'bootstrap' / (name + '.json')
    q.atomic(path, {'version':'level2_frozen_engineering_v1', 'files':rows})
    return path


@pytest.fixture
def rms_block(blocked_prefix, monkeypatch):
    f = blocked_prefix; f.mode['recovered'] = True
    queue01, queue02 = f.previous, f.output
    run = queue02.parents[1]
    request = q.load(queue01 / 'request.json')
    rms = next(e for e in request['entries'] if e['operator'] == 'rms_norm')
    task = Path(rms['task']); parent = task / 'candidates/rms_norm001'
    old_id, oid = 'rms_norm001-feedback-01', 'rms_norm001-reclassification-01'
    stage = {'stage_id':'rms_norm001-build', 'status':'failed', 'kind':'build',
             'error':'RuntimeError: process failed (2): cmake', 'native_started':False}
    old = {'status':'infrastructure_blocked', 'source_hash':'sha256:'+'c'*64,
           'source_parent':{'candidate_id':None, 'source_hash':'sha256:'+'d'*64},
           'stages':[stage], 'semantic_guards':None, 'measurement_error':None}
    old_path = task / 'feedback/rms_norm001.json'; q.atomic(old_path, old); old_ref = q.pointer(old_path)
    summary = {'operator':'rms_norm','candidate_id':'rms_norm001','status':'infrastructure_blocked',
               'observation_id':old_id,'feedback':old_ref}
    child = q.ROOT / 'scaffolding/collection/scripts/level2_iteration.py'
    child.write_text('import json,sys\nfrom pathlib import Path\na=sys.argv[1:]\n'
        + f'with Path({str(f.calls)!r}).open("a") as f:f.write(json.dumps(a)+"\\n")\n'
        + 'bad=a[0]=="candidate" and a[a.index("--operator")+1]=="rms_norm"\n'
        + f'if bad:print(json.dumps({summary!r}))\n'
        + 'raise SystemExit(1 if bad else 0)\n')
    engineering02 = freeze(run, 'frozen-engineering-q02')
    classification = {'status':'source_attempt_failed', 'rule':'original_source_adds_scalar_diagnostic',
                      'reason':'CPU fixture reviewed compiler proof', 'evidence':[]}
    recovery = parent / 'feedback-recovery/reclassification-01/request.json'
    q.atomic(recovery, {'operator':'rms_norm','candidate_id':'rms_norm001','new_observation_id':oid,
        'blocked_observation_id':old_id,'previous_feedback':old_ref,'classification':classification,
        'native_rerun':False,'source_attempt_added':False})
    feedback = {**old, 'status':'source_attempt_failed', 'reclassification':{'previous_feedback':old_ref,
        'previous_observation_id':old_id,'request':q.pointer(recovery),'recovery_id':'reclassification-01',
        'native_reexecuted':False,'source_attempt_added':False}}
    feedback_path = task / 'feedback/rms_norm001-reclassification-01.json'; q.atomic(feedback_path, feedback)
    mode = {'recovered':False}
    old_candidate = q.candidate_evidence
    def candidate(request, entry, **kwargs):
        if entry['operator'] != 'rms_norm':return old_candidate(request, entry, **kwargs)
        if not mode['recovered']:raise ValueError('RMS has no closed real source feedback')
        return {'status':'source_attempt_failed','observation_id':oid,'feedback':q.pointer(feedback_path),
                'classification':classification,'source_rounds':1}
    monkeypatch.setattr(q, 'candidate_evidence', candidate)
    f.ledger.state['tasks']['rms_norm'] = {'observations':{old_id:{'candidate_id':'rms_norm001',
        'close_feedback':False,'quality':{'infrastructure_blocked':True},'feedback':old,'report_ref':old_ref['sha256']}}}
    monkeypatch.setattr(q, 'ledger_for', lambda entry:(f.ledger,Path(entry['task'])))
    q.prepare_continuation(queue01, engineering02, queue02, f.oid)
    assert q.execute(queue02)['status'] == 'blocked'
    assert len(f.calls.read_text().splitlines()) == 6
    before01, before02 = tree_bytes(queue01), tree_bytes(queue02)
    (q.ROOT / 'scaffolding/collection/scripts/level2_r1_queue.py').write_text('# reviewed generic handoff and classifier V6 epoch')
    engineering03 = freeze(run, 'frozen-engineering-q03')
    return SimpleNamespace(queue01=queue01, previous=queue02, output=queue02.with_name('r1-queue-03'),
        engineering=engineering03, engineering02=engineering02, old=f, mode=mode, oid=oid,
        calls=f.calls, order=f.order, before01=before01, before02=before02, feedback=feedback_path,
        recovery=recovery, ledger=f.ledger, rms=rms)


def prepare(f):
    f.mode['recovered'] = True
    return q.prepare_handoff(f.previous, f.engineering, f.output, f.oid)


def test_open_rms_never_publishes_or_retries(rms_block):
    f = rms_block
    with pytest.raises(ValueError, match='no closed real source feedback'):
        q.prepare_handoff(f.previous, f.engineering, f.output, f.oid)
    assert not f.output.exists() and tree_bytes(f.previous) == f.before02
    assert tree_bytes(f.queue01) == f.before01 and len(f.calls.read_text().splitlines()) == 6


def test_queue03_binds_nested_prefix_and_only_launches_remaining12(rms_block):
    f = rms_block; before = f.calls.read_bytes(); result = prepare(f)
    assert result['operators'] == f.order[3:] and result['inherited_prefix'] == f.order[:3]
    assert result['no_child_executed'] and f.calls.read_bytes() == before
    request = q.load(f.output / 'request.json'); previous = q.load(f.previous / 'request.json')
    assert request['version'] == q.HANDOFF_VERSION and request['entries'] == previous['entries'][1:]
    inherited = request['handoff']
    assert inherited['previous_inheritance'] == previous['continuation']
    assert inherited['previous_state'] == q.pointer(f.previous / 'state.json')
    assert set(inherited['completed_children']) == {'rms_norm/baseline'}
    assert inherited['recovered_candidate']['audit']['observation_id'] == f.oid
    assert q.execute(f.output, max_new_operators=1)['status'] == 'operator_limit_reached'
    commands = [json.loads(line) for line in f.calls.read_text().splitlines()]
    assert len(commands) == 8 and all(c[c.index('--operator')+1] == f.order[3] for c in commands[6:])
    assert q.execute(f.output)['status'] == 'completed'
    before = f.calls.read_bytes(); assert q.execute(f.output)['status'] == 'completed'
    assert f.calls.read_bytes() == before and len(before.splitlines()) == 30
    assert tree_bytes(f.queue01) == f.before01 and tree_bytes(f.previous) == f.before02
    assert not any((f.output / op).exists() for op in f.order[:3])


@pytest.mark.parametrize('target', ['q01_state','q01_request','q01_log','q01_snapshot','gn_feedback','gn_recovery',
    'q02_state','q02_request','rms_baseline','rms_checkpoint','rms_log','rms_execution','rms_blocked',
    'q02_snapshot','rms_feedback','rms_recovery','q03_snapshot','producer'])
def test_any_ancestor_or_new_epoch_mutation_blocks_before_child(rms_block, target):
    f = rms_block; prepare(f); before = f.calls.read_bytes()
    paths = {'q01_state':f.queue01/'state.json','q01_request':f.queue01/'request.json',
        'q01_log':f.queue01/'apply_adam_w/candidate/stdout.log',
        'q01_snapshot':Path(q.load(f.old.old_engineering)['files'][0]['snapshot']),
        'gn_feedback':f.old.feedback_path,'gn_recovery':f.old.recovery_request,
        'q02_state':f.previous/'state.json','q02_request':f.previous/'request.json',
        'rms_baseline':f.previous/'rms_norm/baseline/finished.json',
        'rms_checkpoint':f.previous/'rms_norm/checkpoint.json','rms_log':f.previous/'rms_norm/candidate/stdout.log',
        'rms_execution':f.previous/'rms_norm/candidate/execution.json','rms_blocked':f.previous/'rms_norm/blocked.json',
        'q02_snapshot':Path(q.load(f.engineering02)['files'][0]['snapshot']),
        'rms_feedback':f.feedback,'rms_recovery':f.recovery,
        'q03_snapshot':Path(q.load(f.engineering)['files'][0]['snapshot']),
        'producer':q.ROOT/'scaffolding/collection/scripts/level2_r1_queue.py'}
    path = paths[target]; path.write_bytes(path.read_bytes() + b' ')
    with pytest.raises(ValueError):q.execute(f.output)
    assert f.calls.read_bytes() == before


@pytest.mark.parametrize('mutation', ['suffix_started','missing_execution','successful_exit','stdout_other_observation',
    'old_observation_closed','native_reexecuted','other_source','other_stages','wrong_queue_number','old_engineering',
    'cycle','skipped_entry','wrong_stage_kind'])
def test_invalid_handoff_cannot_publish(rms_block, mutation):
    f = rms_block; f.mode['recovered'] = True; output = f.output; engineering = f.engineering
    if mutation == 'suffix_started':(f.previous / f.order[3]).mkdir()
    elif mutation == 'missing_execution':(f.previous/'rms_norm/candidate/execution.json').unlink()
    elif mutation == 'successful_exit':
        path = f.previous/'rms_norm/candidate/execution.json'; value = q.load(path);value['returncode']=0;q.atomic(path,value)
    elif mutation == 'stdout_other_observation':(f.previous/'rms_norm/candidate/stdout.log').write_text('{}\n')
    elif mutation == 'old_observation_closed':next(iter(f.ledger.state['tasks']['rms_norm']['observations'].values()))['close_feedback']=True
    elif mutation in ('native_reexecuted','other_source','other_stages'):
        value = q.load(f.feedback)
        if mutation == 'native_reexecuted':value['reclassification']['native_reexecuted']=True
        elif mutation == 'other_source':value['source_hash']='sha256:'+'f'*64
        else:value['stages']=[]
        q.atomic(f.feedback,value)
    elif mutation == 'wrong_queue_number':output=f.previous.with_name('r1-queue-04')
    elif mutation == 'old_engineering':engineering=f.engineering02
    elif mutation in ('cycle','skipped_entry'):
        path=f.previous/'request.json';value=q.load(path)
        if mutation=='cycle':value['continuation']['previous_queue']=str(f.previous)
        else:value['entries']=value['entries'][1:]
        q.atomic(path,value);state=q.load(f.previous/'state.json');state['request']=q.pointer(path);q.atomic(f.previous/'state.json',state)
    else:
        path=f.previous/'rms_norm/blocked.json';value=q.load(path);value['phase']='baseline';q.atomic(path,value)
        state=q.load(f.previous/'state.json');state['operators']['rms_norm']['blocked']=q.pointer(path);q.atomic(f.previous/'state.json',state)
    with pytest.raises((ValueError,FileNotFoundError,BlockingIOError)):
        q.prepare_handoff(f.previous,engineering,output,f.oid)
    assert not output.exists() and len(f.calls.read_text().splitlines())==6


@pytest.mark.parametrize('ancestor',['queue01','previous'])
def test_live_ancestor_lock_prevents_publish_and_resume(rms_block, ancestor):
    f=rms_block;f.mode['recovered']=True;old=getattr(f,ancestor)
    with (old/'queue.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):q.prepare_handoff(f.previous,f.engineering,f.output,f.oid)
    prepare(f);before=f.calls.read_bytes()
    with (old/'queue.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):q.execute(f.output)
    assert f.calls.read_bytes()==before


@pytest.mark.parametrize('failure',['state_write','staging_sync','rename'])
def test_atomic_publication_failures_leave_no_official_queue(rms_block,monkeypatch,failure):
    f=rms_block;f.mode['recovered']=True;real_atomic=q.atomic;real_sync=q.sync_dir;real_rename=q.os.rename
    def atomic(path,*args,**kwargs):
        if failure=='state_write' and Path(path).name=='state.json':raise OSError('injected state write')
        return real_atomic(path,*args,**kwargs)
    def sync(path):
        if failure=='staging_sync' and Path(path).name.startswith('.r1-queue-03-staging-'):raise OSError('injected staging sync')
        return real_sync(path)
    def rename(*args):raise OSError('injected rename')
    monkeypatch.setattr(q,'atomic',atomic);monkeypatch.setattr(q,'sync_dir',sync)
    if failure=='rename':monkeypatch.setattr(q.os,'rename',rename)
    with pytest.raises(OSError):q.prepare_handoff(f.previous,f.engineering,f.output,f.oid)
    assert not f.output.exists() and not list(f.output.parent.glob('.r1-queue-03-staging-*'))
    assert tree_bytes(f.queue01)==f.before01 and tree_bytes(f.previous)==f.before02
    monkeypatch.setattr(q,'atomic',real_atomic);monkeypatch.setattr(q,'sync_dir',real_sync);monkeypatch.setattr(q.os,'rename',real_rename)
    assert prepare(f)['status']=='prepared'
    assert q.request_state(f.output)[0]['request']==q.pointer(f.output/'request.json')


def test_prepare_handoff_cli_does_not_execute_child(rms_block,monkeypatch,capsys):
    f=rms_block;f.mode['recovered']=True
    monkeypatch.setattr(q.sys,'argv',['level2_r1_queue.py','prepare-handoff','--previous-queue',str(f.previous),
        '--engineering',str(f.engineering),'--output',str(f.output),'--observation-id',f.oid])
    assert q.main()==0 and json.loads(capsys.readouterr().out.splitlines()[-1])['no_child_executed']
    assert len(f.calls.read_text().splitlines())==6


def test_another_producer_handoff_retains_all_ancestors_and_completed_prefix(rms_block, monkeypatch):
    f = rms_block; op = f.order[4]; run = f.output.parents[1]
    entry = next(e for e in q.load(f.previous/'request.json')['entries'] if e['operator']==op)
    cid=entry['candidate_id'];task=Path(entry['task']);parent=task/'candidates'/cid
    old_id=cid+'-feedback-01';oid=cid+'-reclassification-01'
    old={'status':'infrastructure_blocked','source_hash':'sha256:'+'e'*64,
         'source_parent':{'candidate_id':None,'source_hash':'sha256:'+'f'*64},
         'stages':[],'semantic_guards':None,'measurement_error':None}
    old_path=task/'feedback'/f'{cid}.json';q.atomic(old_path,old);old_ref=q.pointer(old_path)
    summary={'operator':op,'candidate_id':cid,'status':'infrastructure_blocked','observation_id':old_id,'feedback':old_ref}
    (q.ROOT/'scaffolding/collection/scripts/level2_iteration.py').write_text('import json,sys\nfrom pathlib import Path\na=sys.argv[1:]\n'
        +f'with Path({str(f.calls)!r}).open("a") as s:s.write(json.dumps(a)+"\\n")\n'
        +f'bad=a[0]=="candidate" and a[a.index("--operator")+1]=={op!r}\n'
        +f'if bad:print(json.dumps({summary!r}))\n'
        +'raise SystemExit(1 if bad else 0)\n')
    f.engineering=freeze(run,'frozen-engineering-q03-future-fixture')
    classification={'status':'source_attempt_failed','rule':'fixture_positive','reason':'CPU only','evidence':[]}
    recovery=parent/'feedback-recovery/reclassification-01/request.json'
    q.atomic(recovery,{'operator':op,'candidate_id':cid,'new_observation_id':oid,'blocked_observation_id':old_id,
        'previous_feedback':old_ref,'classification':classification,'native_rerun':False,'source_attempt_added':False})
    feedback={**old,'status':'source_attempt_failed','reclassification':{'previous_feedback':old_ref,
        'previous_observation_id':old_id,'request':q.pointer(recovery),'recovery_id':'reclassification-01',
        'native_reexecuted':False,'source_attempt_added':False}}
    feedback_path=task/'feedback'/f'{cid}-reclassification-01.json';q.atomic(feedback_path,feedback)
    mode={'recovered':False};old_candidate=q.candidate_evidence;seen=[]
    def candidate(request,entry,**kwargs):
        seen.append((entry['operator'],kwargs))
        if entry['operator']!=op:return old_candidate(request,entry,**kwargs)
        if not mode['recovered']:raise ValueError('future fixture open feedback')
        return {'status':'source_attempt_failed','observation_id':oid,'feedback':q.pointer(feedback_path),
                'classification':classification,'source_rounds':1}
    monkeypatch.setattr(q,'candidate_evidence',candidate)
    f.ledger.state['tasks'][op]={'observations':{old_id:{'candidate_id':cid,'close_feedback':False,
        'quality':{'infrastructure_blocked':True},'feedback':old,'report_ref':old_ref['sha256']}}}
    prepare(f);assert q.execute(f.output)['status']=='blocked'
    before03=tree_bytes(f.output);before=f.calls.read_bytes();mode['recovered']=True
    (q.ROOT/'scaffolding/collection/scripts/level2_r1_queue.py').write_text('# subsequent classifier epoch fixture')
    engineering04=freeze(run,'frozen-engineering-q04');queue04=f.output.with_name('r1-queue-04')
    result=q.prepare_handoff(f.output,engineering04,queue04,oid)
    assert result['inherited_prefix']==f.order[:5] and result['operators']==f.order[5:]
    request=q.load(queue04/'request.json');ancestor=request['handoff']['previous_inheritance']
    assert ancestor['previous_queue']==str(f.previous) and ancestor['previous_inheritance']['previous_queue']==str(f.queue01)
    assert set(request['handoff']['completed_children'])=={f.order[3]+'/baseline',f.order[3]+'/candidate',op+'/baseline'}
    assert f.calls.read_bytes()==before and tree_bytes(f.output)==before03
    assert tree_bytes(f.previous)==f.before02 and tree_bytes(f.queue01)==f.before01
    assert all(kwargs.get('allow_later') is True and kwargs.get('observation_id')
               for name,kwargs in seen[-8:] if name in f.order[:3])
    assert q.execute(queue04)['status']=='completed'
    assert len(f.calls.read_text().splitlines())==30
