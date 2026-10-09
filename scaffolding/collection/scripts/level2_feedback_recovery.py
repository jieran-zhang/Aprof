#!/usr/bin/env python3
"""Explicit CPU-only reclassification of one immutable blocked source feedback.

Inspect is read-only. --apply appends one new observation only when the current
positive-evidence classifier proves source_attempt_failed for the same completed
attempt. Source, plans, prior feedback, execution records and costs never change.
No stage runner, process runner or hardware interface is called.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

import level2_failure_classification as classification
import msprof_exploration_campaign as campaign
import msprof_exploration_archive as archive
import msprof_exploration_execute as execute
import msprof_exploration_provenance as provenance
from msprof_exploration_archive import native_tar_hash
from msprof_exploration_execute import task_paths, canonical as event_canonical
from msprof_exploration_provenance import verify_pointer_tree

VERSION = 'level2_feedback_reclassification_v1'
EVENT_KIND = 'candidate_feedback_reclassified'
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]*')


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n').encode()


def digest(value):
    return 'sha256:'+hashlib.sha256(canonical(value)).hexdigest()


def path_checked(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and path == path.resolve(), 'noncanonical recovery path')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink recovery path')
    return path


def read(path):
    return json.loads(path_checked(path).read_bytes())


def pointer(path):
    path = path_checked(path)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b''):
            h.update(chunk)
    return {'path': str(path), 'sha256': 'sha256:'+h.hexdigest()}


def checked(ref, expected=None):
    require(isinstance(ref, dict) and set(ref) == {'path','sha256'}, 'recovery evidence pointer missing')
    if expected is not None:
        require(Path(ref['path']) == expected, 'recovery evidence location differs')
    require(pointer(ref['path']) == ref, 'recovery evidence bytes changed')
    return read(ref['path'])


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def publish(path, value):
    """Atomic immutable create, with byte-identical resumption and fsync barriers."""
    path = path_checked(path)
    data = canonical(value)
    if path.exists():
        require(path.read_bytes() == data, 'immutable recovery file differs: '+str(path))
        # A prior crash may have occurred after atomic link but before the parent
        # fsync. Reestablish durability before committing a ledger reference.
        with path.open('rb') as stream:
            os.fsync(stream.fileno())
        _fsync_dir(path.parent)
        return pointer(path)
    missing=[];directory=path.parent
    while not directory.exists():
        missing.append(directory);directory=directory.parent
    path.parent.mkdir(parents=True, exist_ok=True)
    for directory in reversed(missing):
        _fsync_dir(directory.parent)
    fd, temporary = tempfile.mkstemp(prefix='.'+path.name+'.', dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        try:
            os.link(temporary,path)
        except FileExistsError:
            require(path.read_bytes() == data, 'concurrent immutable recovery file differs')
        _fsync_dir(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return pointer(path)


def costs(state):
    return {key:deepcopy(state.get(key)) for key in ('used','new_source_attempts','new_rounds_started',
        'stage_starts','fixed_costs','actual_costs')}


def feedback_ref(task, cid, observation):
    expected=observation.get('report_ref')
    require(isinstance(expected,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',expected), 'old observation has no feedback hash')
    matches=[]
    for path in sorted((task/'feedback').glob('*.json')):
        ref=pointer(path)
        if ref['sha256']==expected:
            value=read(path)
            require(value==observation['feedback'] and value.get('operator')==task.name
                    and value.get('candidate_id')==cid, 'blocked feedback identity differs')
            matches.append(ref)
    require(len(matches)==1, 'old feedback must have exactly one immutable file')
    return matches[0]


def source_checked(path, expected, source):
    require(pointer(path)['sha256']==expected, 'source archive identity changed')
    native_tar_hash(path,source)
    return pointer(path)


def audit(run, operator, cid, blocked_id, recovery_id):
    """Pure readers only: validate old blocked observation and positive attribution."""
    require(TOKEN.fullmatch(cid) and TOKEN.fullmatch(recovery_id) and TOKEN.fullmatch(blocked_id), 'invalid recovery identity')
    run=path_checked(run)
    run,split,task,parent,source=task_paths(run,operator,cid)
    task,parent=path_checked(task),path_checked(parent)
    ledger=campaign.Campaign(run/split/'ledger')
    require(ledger.config['schema_version']==campaign.FRESH_SCHEMA, 'recovery requires a fresh campaign')
    state=ledger.state['tasks'][operator]
    item=state['candidates'][cid]
    require(not item['inherited'] and item['current_round_started'], 'recovery needs a real newly executed source attempt')
    old=state['observations'].get(blocked_id)
    require(old is not None and old.get('candidate_id')==cid and old.get('close_feedback') is False
            and old.get('quality',{}).get('infrastructure_blocked') is True,
            'recovery requires an explicit open infrastructure-blocked observation')
    old_ref=feedback_ref(task,cid,old);feedback=checked(old_ref)
    require(feedback.get('status')=='infrastructure_blocked' and feedback.get('source_hash')==item['source_hash']
            and feedback.get('source_parent')==item['source_parent'], 'old blocked feedback source lineage differs')
    require(not feedback.get('measurement_error'), 'measurement infrastructure is not a source failure')
    verify_pointer_tree(feedback,evidence_path=old_ref['path'])
    require(blocked_id in item['observation_ids'], 'old observation is not attached to candidate')
    oid=cid+'-'+recovery_id
    committed=state['observations'].get(oid)
    require(committed or not state['frozen'], 'frozen task cannot recover feedback')
    recovery_directory=parent/'feedback-recovery'/recovery_id
    stored_request=None
    if committed:
        stored_request=checked(committed.get('feedback',{}).get('reclassification',{}).get('request'),
                               recovery_directory/'request.json')
    expected_ids=item['observation_ids'][:item['observation_ids'].index(blocked_id)+1]
    require(item['observation_ids']==expected_ids+([oid] if committed else []), 'later observations require separate explicit review')
    require(item['feedback_closed'] is bool(committed), 'candidate feedback closure differs from recovery state')
    sources={'candidate':source_checked(parent/'source.tar',item['source_hash'],source),
        'original_baseline':source_checked(task/'baseline-source.tar',ledger.config['tasks'][operator]['baseline_source_hash'],task/'baseline')}
    prior=item['source_parent'];pid=prior['candidate_id']
    prior_parent=task if pid is None else task/'candidates'/pid
    sources['direct_parent']=source_checked(prior_parent/('baseline-source.tar' if pid is None else 'source.tar'),
        prior['source_hash'],prior_parent/('baseline' if pid is None else 'op'))
    artifacts=item.get('artifacts',{})
    require(isinstance(artifacts.get('proposal'),dict), 'registered proposal binding is missing')
    verify_pointer_tree(artifacts,evidence_path=parent/'proposal.json')
    proposal=checked(artifacts['proposal'],parent/'proposal.json')
    require(proposal.get('implementation_source_hash')==item['source_hash']
            and proposal.get('optimization_stage')==feedback.get('optimization_stage'), 'registered proposal source/stage differs')
    rows={sid:row for sid,row in state['stages'].items() if row['candidate_id']==cid}
    require(rows and old['stage_attempts']=={sid:len(row['attempts']) for sid,row in rows.items()},
            'source stage attempts changed since blocked feedback')
    declared=feedback.get('stages',[])
    require(len(declared)==len(rows) and {row['stage_id'] for row in declared}==set(rows), 'old feedback omits or duplicates executed stages')
    results=[];bindings=[]
    for observed in declared:
        sid=observed['stage_id'];recorded=rows[sid]
        require(sid.startswith(cid+'-') and TOKEN.fullmatch(sid[len(cid)+1:]), 'stage path is outside candidate')
        directory=parent/'stages'/sid[len(cid)+1:]
        attempt=recorded['attempts'][-1]
        require(attempt['outcome'] is not None, 'stage is still open')
        ref=attempt.get('evidence',{}).get('result')
        result=checked(ref,directory/'result.json')
        require(observed['result']==ref and all(observed.get(k)==result.get(k) for k in ('stage_id','kind','status','error'))
                and result.get('candidate_id')==cid and result['kind']==recorded['kind'], 'stage/feedback/ledger outcome differs')
        require(result['status'] in ('passed','failed') and (result['status']=='passed')==(attempt['outcome']=='success'), 'stage status differs from ledger outcome')
        plan=read(directory/'stage-plan.json')
        require(plan==recorded['plan'] and plan.get('source_hash')==item['source_hash'], 'frozen stage plan/source changed')
        verify_pointer_tree(attempt.get('evidence',{}),evidence_path=directory/'result.json')
        bindings.append({'stage_id':sid,'attempt_count':len(recorded['attempts']),'plan':pointer(directory/'stage-plan.json'),
                         'result':ref,'recorded_attempt':deepcopy(attempt)})
        results.append(result)
    failed=next((row for row in results if row['status']=='failed'),None)
    guard=checked(feedback['semantic_guards'],parent/'boundary-validation/completion.json') if feedback.get('semantic_guards') else None
    inferred=classification.classify_failure(task,parent,stage=failed,guard=guard)
    require(inferred['status']=='source_attempt_failed', 'current classifier does not positively prove source failure: '+inferred['reason'])
    request={'version':VERSION,'operator':operator,'candidate_id':cid,'recovery_id':recovery_id,
        'blocked_observation_id':blocked_id,'new_observation_id':oid,'previous_feedback':old_ref,
        'config_hash':ledger.config_hash,'sources':sources,'source_parent':deepcopy(prior),
        'registered_artifacts':deepcopy(artifacts),'stage_bindings':bindings,'classification':inferred,
        'producers':[pointer(module) for module in (__file__,classification.__file__,campaign.__file__,
                     archive.__file__,execute.__file__,provenance.__file__)],
        # A committed recovery keeps its historical snapshot even when later
        # candidates legitimately add costs. Every original evidence binding is
        # still rebuilt above and compared with the ledger-bound request below.
        'costs_before':deepcopy(stored_request['costs_before']) if stored_request else costs(state),
        'native_rerun':False,'source_attempt_added':False}
    if stored_request is not None:
        require(request==stored_request, 'committed recovery request/evidence differs')
    request_ref={'path':str(recovery_directory/'request.json'),'sha256':digest(request)}
    new=deepcopy(feedback)
    new.update(status='source_attempt_failed',failure_classification=inferred,
        next_action='Analyze this explicitly reclassified, closed source failure before authoring the next intervention.',
        reclassification={'request':request_ref,'previous_observation_id':blocked_id,'previous_feedback':old_ref,
                          'recovery_id':recovery_id,'native_reexecuted':False,'source_attempt_added':False})
    new_path=task/'feedback'/(cid+'-'+recovery_id+'.json')
    if committed:
        require(committed.get('close_feedback') is True and committed['feedback']==new
                and committed['report_ref']==digest(new), 'committed recovery observation differs')
        require(checked({'path':str(new_path),'sha256':committed['report_ref']},new_path)==new,
                'committed recovery feedback file differs')
    return {'ledger':ledger,'task':task,'parent':parent,'split':split,'state':state,'item':item,
            'old':old,'new':new,'request':request,'request_path':recovery_directory/'request.json',
            'feedback_path':new_path,'stage_ids':list(rows),'observation_id':oid,'committed':committed}


class GuardedCampaign(campaign.Campaign):
    """Reuse the ordinary ledger append, with a precondition under its write lock."""
    def __init__(self,directory,operator,expected,event_id):
        self.guard=None
        super().__init__(directory)
        self.guard=(operator,expected,event_id)

    def _load(self):
        super()._load()
        if self.guard is not None:
            operator,expected,event_id=self.guard
            if event_id not in self.event_ids:
                require(digest(self.state['tasks'][operator])==expected,
                        'task changed before atomic feedback recovery commit')


def append_event(task, value):
    """One idempotent public task event, using the existing recorder lock/chain."""
    with path_checked(task/'.recorder.lock').open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=path_checked(task/'events.jsonl')
        data=path.read_bytes() if path.exists() else b''
        require(not data or data.endswith(b'\n'), 'incomplete task event history needs separate recovery')
        rows=[json.loads(line) for line in data.splitlines()]
        matches=[];previous=None
        for i,row in enumerate(rows):
            payload={k:v for k,v in row.items() if k!='hash'}
            require(row['sequence']==i and row['previous_hash']==previous and 'sha256:'+hashlib.sha256(event_canonical(payload)).hexdigest()==row['hash'], 'task event chain differs')
            previous=row['hash']
            if row['kind']==EVENT_KIND and row['value'].get('observation_id')==value['observation_id']:
                require(row['value']==value, 'recovery task event differs');matches.append(row)
        require(len(matches)<=1, 'duplicate recovery task events')
        if matches:
            return matches[0]
        row={'sequence':len(rows),'recorded_at':datetime.now(timezone.utc).isoformat(),'kind':EVENT_KIND,
             'previous_hash':previous,'value':value}
        row['hash']='sha256:'+hashlib.sha256(event_canonical(row)).hexdigest()
        with path.open('ab') as stream:
            stream.write(event_canonical(row));stream.flush();os.fsync(stream.fileno())
        _fsync_dir(path.parent)
        return row


def recover(run,operator,candidate_id,*,blocked_observation_id,recovery_id,apply=False):
    run=path_checked(run)
    initial=audit(run,operator,candidate_id,blocked_observation_id,recovery_id)
    if not apply:
        return {'status':'eligible_source_reclassification','apply':False,'native_executed':False,
                'already_committed':bool(initial['committed']),'request':initial['request'],
                'proposed_feedback':initial['new'],'feedback_path':str(initial['feedback_path'])}
    lock_path=path_checked(initial['parent'] / '.feedback-recovery.lock')
    with lock_path.open('a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        bound=audit(run,operator,candidate_id,blocked_observation_id,recovery_id)
        request=bound['request'];directory=bound['request_path'].parent
        request_ref=publish(bound['request_path'],request)
        require(request_ref==bound['new']['reclassification']['request'], 'request publication identity differs')
        new_ref=publish(bound['feedback_path'],bound['new'])
        # Read all immutable inputs again immediately before commit. The guarded
        # ordinary Campaign append also checks task state inside the ledger lock.
        replay=audit(run,operator,candidate_id,blocked_observation_id,recovery_id)
        require(replay['request']==request and replay['new']==bound['new'], 'recovery evidence changed before commit')
        ledger=GuardedCampaign(run/bound['split']/'ledger',operator,digest(replay['state']),bound['observation_id'])
        committed=ledger.observe(event_id=bound['observation_id'],workload=operator,candidate_id=candidate_id,
            observation_id=bound['observation_id'],stage_ids=bound['stage_ids'],feedback=bound['new'],
            close_feedback=True,report_ref=new_ref['sha256'],quality={'formal_admission':'not_evaluated',
                'infrastructure_blocked':False,'complete_measurement':False,'explicit_reclassification':True})
        state=campaign.Campaign(run/bound['split']/'ledger').state['tasks'][operator]
        require(costs(state)==costs(replay['state']), 'reclassification changed execution costs or attempt counts')
        public=append_event(bound['task'],{'operator':operator,'candidate_id':candidate_id,
            'recovery_id':recovery_id,'observation_id':bound['observation_id'],'previous_observation_id':blocked_observation_id,
            'request':request_ref,'feedback':new_ref,'ledger_event_hash':committed['hash'],
            'native_reexecuted':False,'costs_reset':False,'source_attempt_added':False})
        event_ref=publish(directory/'event.json',public)
        completion={'version':VERSION,'status':'source_attempt_failed','request':request_ref,'feedback':new_ref,
            'event':event_ref,'observation_id':bound['observation_id'],'ledger_event_hash':committed['hash'],
            'old_feedback_preserved':request['previous_feedback'],'costs_unchanged':True,
            'stage_attempt_counts':{r['stage_id']:r['attempt_count'] for r in request['stage_bindings']},
            'native_executed':False,'source_attempt_added':False}
        completion_ref=publish(directory/'completion.json',completion)
        return {**completion,'completion':completion_ref,'apply':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('run','operator','candidate','blocked-observation','recovery-id'):
        parser.add_argument('--'+name,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    result=recover(Path(args.run).absolute(),args.operator,args.candidate,
        blocked_observation_id=args.blocked_observation,recovery_id=args.recovery_id,apply=args.apply)
    print(json.dumps(result,ensure_ascii=False,sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
