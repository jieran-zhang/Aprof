"""CPU-only inherited-prefix CAS, producer epoch and no-repeat continuation tests."""
import fcntl
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_level2_r1_queue import queued
import level2_r1_queue as q


def tree_bytes(path):
    return {str(p.relative_to(path)):p.read_bytes() for p in path.rglob('*') if p.is_file() and p.name != 'queue.lock'}


@pytest.fixture
def blocked_prefix(queued, monkeypatch):
    previous,calls,order,schedule,engineering=queued
    run=previous.parents[1]
    order=['apply_adam_w','group_norm','rms_norm']+[op for op in order if op not in ('apply_adam_w','group_norm','rms_norm')]
    scheduled=q.load(schedule);scheduled['scheduling']['after_current_recommended_new_operator_order']=order;q.atomic(schedule,scheduled)
    request=q.load(previous/'request.json');byop={e['operator']:e for e in request['entries']}
    request['entries']=[byop[op] for op in order];request['schedule']=q.pointer(schedule)
    gn=byop['group_norm'];task=Path(gn['task']);parent=task/'candidates'/gn['candidate_id']
    old={'status':'infrastructure_blocked','source_hash':'sha256:'+'a'*64,
         'source_parent':{'candidate_id':None,'source_hash':'sha256:'+'b'*64},'stages':[],
         'semantic_guards':None,'measurement_error':None}
    old_path=task/'feedback/group_norm001.json';q.atomic(old_path,old)
    old_ref=q.pointer(old_path);old_id='group_norm001-feedback-01';oid='group_norm001-numeric-01'
    old_summary={'operator':'group_norm','candidate_id':'group_norm001','status':'infrastructure_blocked',
                 'observation_id':old_id,'feedback':old_ref}
    child=q.ROOT/'scripts/level2_iteration.py'
    child.write_text('import json,sys\nfrom pathlib import Path\na=sys.argv[1:]\n'
        +f'with Path({str(calls)!r}).open("a") as f:f.write(json.dumps(a)+"\\n")\n'
        +'bad=a[0]=="candidate" and a[a.index("--operator")+1]=="group_norm"\n'
        +f'if bad:print(json.dumps({old_summary!r}))\n'
        +'raise SystemExit(1 if bad else 0)\n')
    # Historical frozen snapshots are separate files; changing live producers
    # must never rewrite the old engineering epoch.
    snapshots=run/'bootstrap/old-producer-snapshots';snapshots.mkdir()
    files=[]
    for path in (q.ROOT/'scripts').iterdir():
        snapshot=snapshots/path.name;snapshot.write_bytes(path.read_bytes())
        files.append({**q.pointer(path),'snapshot':str(snapshot)})
    q.atomic(engineering,{'version':'level2_frozen_engineering_v1','files':files})
    request['engineering']=q.pointer(engineering);request['producers']=[q.pointer(Path(r['path'])) for r in request['producers']]
    q.atomic(previous/'request.json',request)
    state=q.load(previous/'state.json');state['request']=q.pointer(previous/'request.json');q.atomic(previous/'state.json',state)
    mode={'recovered':False}
    classification={'status':'source_attempt_failed','rule':'guard_numeric','reason':'CPU fixture proof','evidence':[]}
    recovery_request=parent/'feedback-recovery/numeric-01/request.json'
    q.atomic(recovery_request,{'operator':'group_norm','candidate_id':'group_norm001','new_observation_id':oid,
        'blocked_observation_id':old_id,'previous_feedback':old_ref,'classification':classification,
        'native_rerun':False,'source_attempt_added':False})
    feedback={**old,'status':'source_attempt_failed','reclassification':{'previous_feedback':old_ref,
        'previous_observation_id':old_id,'request':q.pointer(recovery_request),'recovery_id':'numeric-01',
        'native_reexecuted':False,'source_attempt_added':False}}
    feedback_path=task/'feedback/group_norm001-numeric-01.json';q.atomic(feedback_path,feedback)
    def candidate(request,entry,**kwargs):
        if entry['operator']=='group_norm':
            if not mode['recovered']:raise ValueError('GN has no closed source feedback')
            return {'status':'source_attempt_failed','observation_id':oid,'feedback':q.pointer(feedback_path),
                    'classification':classification,'source_rounds':1}
        return {'status':'measured','observation_id':entry['candidate_id']+'-feedback-01'}
    monkeypatch.setattr(q,'candidate_evidence',candidate)
    ledger=SimpleNamespace(state={'tasks':{'group_norm':{'observations':{old_id:{'candidate_id':'group_norm001',
        'close_feedback':False,'quality':{'infrastructure_blocked':True},'feedback':old,'report_ref':old_ref['sha256']}}}}})
    monkeypatch.setattr(q,'ledger_for',lambda entry:(ledger,task))
    assert q.execute(previous)['status']=='blocked'
    assert len(calls.read_text().splitlines())==4
    before=tree_bytes(previous)
    # New reviewed classifier/coordinator epoch; old snapshots stay untouched.
    (q.ROOT/'scripts/level2_r1_queue.py').write_text('# reviewed suffix coordinator epoch')
    new_engineering=run/'bootstrap/frozen-engineering-011.json'
    new_snapshots=run/'bootstrap/new-producer-snapshots';new_snapshots.mkdir()
    files=[]
    for path in (q.ROOT/'scripts').iterdir():
        snapshot=new_snapshots/path.name;snapshot.write_bytes(path.read_bytes())
        files.append({**q.pointer(path),'snapshot':str(snapshot)})
    q.atomic(new_engineering,{'version':'level2_frozen_engineering_v1','files':files})
    return SimpleNamespace(previous=previous,output=previous.with_name('r1-queue-02'),calls=calls,
        order=order,engineering=new_engineering,old_engineering=engineering,mode=mode,before=before,
        oid=oid,feedback_path=feedback_path,recovery_request=recovery_request,ledger=ledger)


def prepare(f):
    f.mode['recovered']=True
    return q.prepare_continuation(f.previous,f.engineering,f.output,f.oid)


def test_open_gn_feedback_cannot_publish_or_relaunch(blocked_prefix):
    f=blocked_prefix
    with pytest.raises(ValueError,match='no closed source feedback'):
        q.prepare_continuation(f.previous,f.engineering,f.output,f.oid)
    assert not f.output.exists() and tree_bytes(f.previous)==f.before
    assert len(f.calls.read_text().splitlines())==4


def test_new_producer_suffix_request_is_bound_and_two_limit_runs_skip_prefix(blocked_prefix):
    f=blocked_prefix;before=f.calls.read_bytes();result=prepare(f)
    assert result['operators']==f.order[2:] and result['no_child_executed']
    assert f.calls.read_bytes()==before and tree_bytes(f.previous)==f.before
    req=q.load(f.output/'request.json');old=q.load(f.previous/'request.json')
    assert req['version']==q.CONTINUATION_VERSION and req['entries']==old['entries'][2:]
    assert req['settings']==old['settings'] and req['engineering']!=old['engineering']
    assert req['continuation']['previous_state']==q.pointer(f.previous/'state.json')
    assert req['continuation']['previous_blocked']==q.pointer(f.previous/'group_norm/blocked.json')
    assert q.execute(f.output,max_new_operators=1)['status']=='operator_limit_reached'
    commands=[json.loads(line) for line in f.calls.read_text().splitlines()]
    assert len(commands)==6 and all(c[c.index('--operator')+1]=='rms_norm' for c in commands[4:])
    assert q.execute(f.output,max_new_operators=1)['status']=='operator_limit_reached'
    commands=[json.loads(line) for line in f.calls.read_text().splitlines()]
    assert len(commands)==8 and all(c[c.index('--operator')+1]==f.order[3] for c in commands[6:])
    assert tree_bytes(f.previous)==f.before
    assert not (f.output/'apply_adam_w').exists() and not (f.output/'group_norm').exists()


def test_full_suffix_and_resume_execute_each_remaining_child_once(blocked_prefix):
    f=blocked_prefix;prepare(f)
    assert q.execute(f.output)['status']=='completed';before=f.calls.read_bytes()
    commands=[json.loads(line) for line in before.splitlines()]
    assert len(commands)==30
    assert [(c[c.index('--operator')+1],c[0]) for c in commands[4:]]==[(op,p) for op in f.order[2:] for p in ('baseline','candidate')]
    assert q.execute(f.output)['status']=='completed' and f.calls.read_bytes()==before
    assert tree_bytes(f.previous)==f.before


@pytest.mark.parametrize('mutation',['old_state','old_request','old_log','old_execution','old_receipt','old_snapshot',
                                      'old_checkpoint','new_snapshot','new_producer','gn_recovery','gn_feedback'])
def test_changed_inherited_or_new_proof_blocks_before_child(blocked_prefix,mutation):
    f=blocked_prefix;prepare(f);before=f.calls.read_bytes()
    if mutation=='old_state':path=f.previous/'state.json'
    elif mutation=='old_request':path=f.previous/'request.json'
    elif mutation=='old_log':path=f.previous/'apply_adam_w/candidate/stdout.log'
    elif mutation=='old_execution':path=f.previous/'group_norm/candidate/execution.json'
    elif mutation=='old_receipt':path=f.previous/'group_norm/baseline/finished.json'
    elif mutation=='old_checkpoint':path=f.previous/'group_norm/checkpoint.json'
    elif mutation=='old_snapshot':path=Path(q.load(f.old_engineering)['files'][0]['snapshot'])
    elif mutation=='new_snapshot':path=Path(q.load(f.engineering)['files'][0]['snapshot'])
    elif mutation=='new_producer':path=q.ROOT/'scripts/level2_r1_queue.py'
    elif mutation=='gn_recovery':path=f.recovery_request
    else:path=f.feedback_path
    path.write_bytes(path.read_bytes()+b' ')
    with pytest.raises(ValueError):q.execute(f.output)
    assert f.calls.read_bytes()==before


@pytest.mark.parametrize('mutation',['suffix_started','old_returncode','old_stdout','old_closed_observation',
                                      'gn_new_native','gn_other_source','gn_other_stages','wrong_output','old_epoch'])
def test_prepare_rejects_invalid_transfer_without_publishing(blocked_prefix,mutation):
    f=blocked_prefix;f.mode['recovered']=True;output=f.output;engineering=f.engineering
    if mutation=='suffix_started':(f.previous/'rms_norm').mkdir()
    elif mutation=='old_returncode':
        p=f.previous/'group_norm/candidate/execution.json';v=q.load(p);v['returncode']=0;q.atomic(p,v)
    elif mutation=='old_stdout':(f.previous/'group_norm/candidate/stdout.log').write_text('{}\n')
    elif mutation=='old_closed_observation':next(iter(f.ledger.state['tasks']['group_norm']['observations'].values()))['close_feedback']=True
    elif mutation.startswith('gn_'):
        v=q.load(f.feedback_path)
        if mutation=='gn_new_native':v['reclassification']['native_reexecuted']=True
        elif mutation=='gn_other_source':v['source_hash']='sha256:'+'f'*64
        else:v['stages']=[{'forged':'stage'}]
        q.atomic(f.feedback_path,v)
    elif mutation=='wrong_output':output=f.previous.with_name('r1-queue-03')
    else:engineering=f.old_engineering
    with pytest.raises(ValueError):q.prepare_continuation(f.previous,engineering,output,f.oid)
    assert not output.exists() and len(f.calls.read_text().splitlines())==4


def test_active_predecessor_lock_prevents_prepare_and_resume(blocked_prefix):
    f=blocked_prefix;f.mode['recovered']=True
    with (f.previous/'queue.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):q.prepare_continuation(f.previous,f.engineering,f.output,f.oid)
    prepare(f);before=f.calls.read_bytes()
    with (f.previous/'queue.lock').open('rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):q.execute(f.output)
    assert f.calls.read_bytes()==before


def test_legacy_request_cannot_smuggle_continuation_marker(blocked_prefix):
    f=blocked_prefix
    req=q.load(f.previous/'request.json');req['continuation']={};q.atomic(f.previous/'request.json',req)
    state=q.load(f.previous/'state.json');state['request']=q.pointer(f.previous/'request.json');q.atomic(f.previous/'state.json',state)
    with pytest.raises(ValueError,match='legacy queue'):prepare(f)


def test_continuation_cli_is_prepare_only_and_keeps_old_tree(blocked_prefix,monkeypatch,capsys):
    f=blocked_prefix;f.mode['recovered']=True
    monkeypatch.setattr(q.sys,'argv',['level2_r1_queue.py','prepare-continuation','--previous-queue',str(f.previous),
        '--engineering',str(f.engineering),'--output',str(f.output),'--observation-id',f.oid])
    assert q.main()==0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['no_child_executed']
    assert tree_bytes(f.previous)==f.before and len(f.calls.read_text().splitlines())==4


@pytest.mark.parametrize('failure',['state_write','staging_sync','rename'])
def test_failed_prepare_does_not_publish_partial_queue_and_can_retry(blocked_prefix,monkeypatch,failure):
    f=blocked_prefix;f.mode['recovered']=True;real_atomic=q.atomic;real_sync=q.sync_dir;real_rename=q.os.rename
    def atomic(path,*args,**kwargs):
        if failure=='state_write' and Path(path).name=='state.json':raise OSError('injected state write')
        return real_atomic(path,*args,**kwargs)
    def sync(path):
        if failure=='staging_sync' and Path(path).name.startswith('.r1-queue-02-staging-'):
            raise OSError('injected staging fsync')
        return real_sync(path)
    def rename(*args):raise OSError('injected rename')
    monkeypatch.setattr(q,'atomic',atomic);monkeypatch.setattr(q,'sync_dir',sync)
    if failure=='rename':monkeypatch.setattr(q.os,'rename',rename)
    with pytest.raises(OSError):q.prepare_continuation(f.previous,f.engineering,f.output,f.oid)
    assert not f.output.exists() and tree_bytes(f.previous)==f.before
    assert not list(f.output.parent.glob('.r1-queue-02-staging-*'))
    assert len(f.calls.read_text().splitlines())==4
    monkeypatch.setattr(q,'atomic',real_atomic);monkeypatch.setattr(q,'sync_dir',real_sync);monkeypatch.setattr(q.os,'rename',real_rename)
    assert prepare(f)['status']=='prepared'
    state=q.load(f.output/'state.json');assert state['request']==q.pointer(f.output/'request.json')
    assert q.request_state(f.output)[1]['version']==q.CONTINUATION_VERSION
