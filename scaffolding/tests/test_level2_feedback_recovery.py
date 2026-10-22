"""Explicit append-only reclassification; real ledger, no hardware or fake reruns."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'scaffolding/collection/scripts'))
import level2_feedback_recovery as recovery
import msprof_exploration_campaign as campaign
from msprof_exploration_execute import save, pointer, sha, event
from test_level2_finalize import Fixture


@pytest.fixture
def existing(tmp_path,monkeypatch):
    real_register=campaign.Campaign.register
    real_observe=campaign.Campaign.observe
    def register(ledger,**args):
        parent=tmp_path/'train/tasks/maximum/candidates'/args['candidate_id']
        proposal={'candidate_id':args['candidate_id'],'implementation_source_hash':args['source_hash'],
                  'optimization_stage':'execution'}
        path=parent/'proposal.json';save(path,proposal)
        args['artifacts']={'proposal':pointer(path)}
        return real_register(ledger,**args)
    def blocked(ledger,**args):
        feedback=deepcopy(args['feedback']);feedback.update(status='infrastructure_blocked',optimization_stage='execution')
        feedback['failure_classification']['status']='infrastructure_blocked'
        feedback['failure_classification']['rule']='unproven_failure'
        feedback['failure_classification']['reason']='prior conservative compiler classifier'
        path=tmp_path/'train/tasks/maximum/feedback'/(args['candidate_id']+'.json')
        path.write_text(json.dumps(feedback))
        args.update(feedback=feedback,close_feedback=False,report_ref=sha(path),quality={'infrastructure_blocked':True})
        return real_observe(ledger,**args)
    monkeypatch.setattr(campaign.Campaign,'register',register)
    monkeypatch.setattr(campaign.Campaign,'observe',blocked)
    fixture=Fixture(tmp_path,monkeypatch,failed=(1,),blocked=(1,),count=1)
    monkeypatch.setattr(campaign.Campaign,'register',real_register)
    monkeypatch.setattr(campaign.Campaign,'observe',real_observe)
    # Include an existing Unicode public event, with the actual recorder format.
    event(fixture.task,'prior_event',{'text':'保留之前的事件'})
    monkeypatch.setattr('level2_iteration.stage',lambda *a,**k:pytest.fail('recovery called a stage runner'))
    monkeypatch.setattr('level2_iteration.run_stage',lambda *a,**k:pytest.fail('recovery called native execution'))
    return fixture


def call(f,apply=False):
    return recovery.recover(f.run,'maximum','maximum001',blocked_observation_id='maximum001-feedback',
                            recovery_id='reclassification-01',apply=apply)


def files(path):
    return {str(p):p.read_bytes() for p in path.rglob('*') if p.is_file()}


def state(f):
    return campaign.Campaign(f.run/'train/ledger').state['tasks']['maximum']


def test_inspect_is_completely_read_only(existing):
    before=files(existing.run)
    value=call(existing)
    assert value['status']=='eligible_source_reclassification' and value['apply'] is False
    assert value['proposed_feedback']['failure_classification']['status']=='source_attempt_failed'
    assert files(existing.run)==before


def test_apply_adds_only_one_closed_observation_and_preserves_costs_and_sources(existing):
    before=state(existing);parent=existing.task/'candidates/maximum001'
    protected={str(p):p.read_bytes() for p in [parent/'source.tar',parent/'proposal.json',
        parent/'stages/build/result.json',parent/'stages/build/stage-plan.json',existing.task/'feedback/maximum001.json']}
    result=call(existing,True);after=state(existing)
    assert result['status']=='source_attempt_failed' and result['costs_unchanged'] and not result['native_executed']
    assert after['candidates']['maximum001']['feedback_closed'] is True
    assert after['candidates']['maximum001']['observation_ids']==['maximum001-feedback','maximum001-reclassification-01']
    assert before['stages']==after['stages'] and recovery.costs(before)==recovery.costs(after)
    assert len(after['candidates'])==1 and after['new_source_attempts']==1
    assert all(Path(p).read_bytes()==raw for p,raw in protected.items())
    first=files(existing.run);again=call(existing,True)
    assert result==again and files(existing.run)==first
    assert call(existing)['already_committed'] is True


@pytest.mark.parametrize('fault',['source','stage_result','stage_plan','old_feedback','old_classifier_evidence','proposal'])
def test_changed_original_evidence_never_closes_feedback(existing,fault):
    parent=existing.task/'candidates/maximum001'
    path={'source':parent/'op/op_kernel/maximum.asc','stage_result':parent/'stages/build/result.json',
          'stage_plan':parent/'stages/build/stage-plan.json','old_feedback':existing.task/'feedback/maximum001.json',
          'old_classifier_evidence':parent/'build/build-execution/stderr.log','proposal':parent/'proposal.json'}[fault]
    path.write_text(path.read_text()+'\nchanged')
    before=files(existing.run)
    with pytest.raises((ValueError,json.JSONDecodeError)):
        call(existing,True)
    assert state(existing)['candidates']['maximum001']['feedback_closed'] is False
    assert files(existing.run)==before


def test_unknown_infrastructure_refuses_recovery_without_writing(existing,monkeypatch):
    monkeypatch.setattr(recovery.classification,'classify_failure',lambda *a,**k:{'status':'infrastructure_blocked','reason':'unknown SDK failure'})
    before=files(existing.run)
    with pytest.raises(ValueError,match='does not positively prove'):
        call(existing,True)
    assert files(existing.run)==before


def test_wrong_old_observation_never_creates_recovery(existing):
    before=files(existing.run)
    with pytest.raises(ValueError,match='explicit open'):
        recovery.recover(existing.run,'maximum','maximum001',blocked_observation_id='not-recorded',
                         recovery_id='reclassification-01',apply=True)
    assert files(existing.run)==before


@pytest.mark.parametrize('point',['after_request','after_feedback','after_commit','after_public_event','after_event_receipt','after_completion'])
def test_crash_safe_resume_never_reexecutes_or_duplicates_observation(existing,monkeypatch,point):
    real_publish=recovery.publish;real_observe=recovery.GuardedCampaign.observe;real_event=recovery.append_event
    fired=[False]
    def crash_once():
        if not fired[0]:fired[0]=True;raise OSError('injected crash')
    def publish(path,value):
        result=real_publish(path,value)
        if ((point=='after_request' and path.name=='request.json')
            or (point=='after_feedback' and path.parent.name=='feedback')
            or (point=='after_event_receipt' and path.name=='event.json')
            or (point=='after_completion' and path.name=='completion.json')):crash_once()
        return result
    def observe(ledger,**args):
        result=real_observe(ledger,**args)
        if point=='after_commit':crash_once()
        return result
    def append(task,value):
        result=real_event(task,value)
        if point=='after_public_event':crash_once()
        return result
    monkeypatch.setattr(recovery,'publish',publish)
    monkeypatch.setattr(recovery.GuardedCampaign,'observe',observe)
    monkeypatch.setattr(recovery,'append_event',append)
    before=state(existing)
    with pytest.raises(OSError,match='injected crash'):call(existing,True)
    result=call(existing,True);after=state(existing)
    assert result['status']=='source_attempt_failed'
    assert after['stages']==before['stages'] and recovery.costs(after)==recovery.costs(before)
    assert len(after['observations'])==2
    events=[json.loads(line) for line in (existing.task/'events.jsonl').read_text().splitlines()]
    assert sum(row['kind']==recovery.EVENT_KIND for row in events)==1


def test_concurrent_task_change_rejected_inside_ledger_commit(existing,monkeypatch):
    real=recovery.GuardedCampaign.observe
    def observe(ledger,**args):
        other=campaign.Campaign(existing.run/'train/ledger')
        original=other.state['tasks']['maximum']['observations']['maximum001-feedback']
        other.observe(event_id='concurrent-review',workload='maximum',candidate_id='maximum001',
            observation_id='concurrent-review',stage_ids=original['stage_ids'],feedback={'status':'still_blocked'},
            close_feedback=False,report_ref=original['report_ref'],quality={'infrastructure_blocked':True})
        return real(ledger,**args)
    monkeypatch.setattr(recovery.GuardedCampaign,'observe',observe)
    with pytest.raises(ValueError,match='task changed before atomic'):
        call(existing,True)
    assert state(existing)['candidates']['maximum001']['feedback_closed'] is False
    assert 'maximum001-reclassification-01' not in state(existing)['observations']


def test_existing_request_tamper_cannot_be_repaired_by_overwrite(existing,monkeypatch):
    real=recovery.publish
    def fail_after_request(path,value):
        result=real(path,value)
        if path.name=='request.json':raise OSError('stop after request')
        return result
    monkeypatch.setattr(recovery,'publish',fail_after_request)
    with pytest.raises(OSError):call(existing,True)
    monkeypatch.setattr(recovery,'publish',real)
    request=existing.task/'candidates/maximum001/feedback-recovery/reclassification-01/request.json'
    raw=json.loads(request.read_bytes());raw['source_attempt_added']=True;request.write_bytes(recovery.canonical(raw))
    with pytest.raises(ValueError,match='immutable recovery file differs'):
        call(existing,True)
    assert state(existing)['candidates']['maximum001']['feedback_closed'] is False


def test_existing_immutable_request_resyncs_after_directory_fsync_failure(existing,monkeypatch):
    real=recovery._fsync_dir;failed=[False]
    def fail(path):
        if path.name=='reclassification-01' and (path/'request.json').exists() and not failed[0]:
            failed[0]=True;raise OSError('directory fsync failed after publish')
        return real(path)
    monkeypatch.setattr(recovery,'_fsync_dir',fail)
    with pytest.raises(OSError,match='directory fsync'):
        call(existing,True)
    assert state(existing)['candidates']['maximum001']['feedback_closed'] is False
    assert len(state(existing)['observations'])==1
    calls=[]
    def track(path):calls.append(str(path));return real(path)
    monkeypatch.setattr(recovery,'_fsync_dir',track)
    assert call(existing,True)['status']=='source_attempt_failed'
    assert str(existing.task/'candidates/maximum001/feedback-recovery/reclassification-01') in calls


def test_symlink_public_recorder_lock_is_rejected(existing,tmp_path):
    lock=existing.task/'.recorder.lock';lock.unlink()
    victim=tmp_path/'external-lock';victim.write_bytes(b'unchanged')
    lock.symlink_to(victim)
    with pytest.raises(ValueError,match='recovery path'):
        call(existing,True)
    assert victim.read_bytes()==b'unchanged'
    # The ledger may already have durably recorded recovery; fix the unrelated
    # recorder problem explicitly, then replay emits exactly one event.
    lock.unlink()
    assert call(existing,True)['status']=='source_attempt_failed'


def later_source(f):
    """Real next registration/start/finish adds costs without touching original R1."""
    cid='maximum002';parent=f.task/'candidates'/cid
    f.make_source(parent,'op','source.tar',cid)
    ledger=campaign.Campaign(f.run/'train/ledger')
    ledger.register(event_id=cid+'-register',workload='maximum',candidate_id=cid,
        source_hash=sha(parent/'source.tar'),patch_hash='sha256:'+'b'*64,
        source_parent={'candidate_id':None,'source_hash':f.baseline},
        decision_basis=['maximum001-reclassification-01'])
    f.complete(cid,'build','build')


def test_committed_reentry_keeps_original_snapshot_after_later_source_costs(existing):
    result=call(existing,True)
    request_path=Path(result['request']['path'])
    original_request=request_path.read_bytes()
    original_costs=json.loads(original_request)['costs_before']
    later_source(existing)
    current_costs=recovery.costs(state(existing))
    assert current_costs!=original_costs
    before=files(existing.run)
    inspected=call(existing)
    assert inspected['already_committed']
    assert inspected['request']['costs_before']==original_costs
    assert call(existing,True)==result
    assert files(existing.run)==before and request_path.read_bytes()==original_request
    assert recovery.costs(state(existing))==current_costs
    assert state(existing)['new_source_attempts']==2


def test_committed_reentry_after_later_source_still_rejects_original_mutation(existing):
    call(existing,True);later_source(existing)
    path=existing.task/'candidates/maximum001/op/op_kernel/maximum.asc'
    path.write_text(path.read_text()+' changed')
    before=files(existing.run)
    with pytest.raises(ValueError):call(existing,True)
    assert files(existing.run)==before


def test_committed_reentry_verifies_original_request_and_feedback_bytes(existing):
    result=call(existing,True);later_source(existing)
    request=Path(result['request']['path']);original=request.read_bytes()
    value=json.loads(original);value['costs_before']=recovery.costs(state(existing))
    request.write_bytes(recovery.canonical(value))
    with pytest.raises(ValueError,match='evidence bytes changed'):call(existing)
    request.write_bytes(original)
    feedback=Path(result['feedback']['path']);feedback.write_bytes(feedback.read_bytes()+b' ')
    with pytest.raises(ValueError,match='evidence bytes changed'):call(existing)


def test_request_binds_every_actual_audit_producer(existing):
    value=call(existing)['request']
    expected={Path(module).name:recovery.pointer(module) for module in (
        recovery.__file__,recovery.classification.__file__,recovery.campaign.__file__,
        recovery.archive.__file__,recovery.execute.__file__,recovery.provenance.__file__)}
    assert len(value['producers'])==len(expected)==6
    assert {Path(ref['path']).name:ref for ref in value['producers']}==expected
