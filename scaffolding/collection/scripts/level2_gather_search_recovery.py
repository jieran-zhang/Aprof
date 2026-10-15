#!/usr/bin/env python3
"""One certified, same-stage recovery of Gather003's zero-native search failure."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from level2_prestart_recovery import safe, data, sha, pointer, load, save, save_bytes, check, sync, require
from level2_stage_recovery import ledger_events, task_events, digest, sha as bytes_sha, pointer as validate_pointer
from msprof_search_protocol import LITE_PROTOCOL

VERSION = 'level2_gather_search_prestart_qualification_v1'
OPERATOR = 'gather'
CANDIDATE = 'gather003'
STAGE = CANDIDATE + '-search'
FAILURE = {'type':'ValueError','message':'component role/harness identity differs'}
REASON = 'The historical and new harness READMEs have distinct hashes; the fixed role binaries and compiled harness inputs agree. Preserve the first seven-second zero-native failure and recover the same charged search stage.'
PRODUCERS = ('level2_gather_search_recovery.py','level2_stage_recovery.py',
             'msprof_exploration_campaign.py','run_msprof_exploration_stage.py',
             'level2_iteration.py','msprof_exploration_report.py',
             'msprof_exploration_provenance.py','level2_verification_storage.py')
CERTIFICATE = {'version','arguments','stage_plan','failed_result','blocked_feedback',
               'ledger_prefix','task_event_prefix','old_engineering','recovery_engineering',
               'handoff','producers','stage_files_before','actual_costs','authorizes'}


def locations(run):
    run=safe(run)
    require(run.name=='level2-skill-graph-base-20261005-experiment' and not (run/'skill-lib.json').exists(),
            'recovery is restricted to the unbound historical Level2 campaign')
    task=run/'train/tasks/gather';parent=task/'candidates/gather003';stage=parent/'stages/search'
    return run,task,parent,stage


def validate_qualification(stage,candidate,args):
    require(set(args)=={'workload','stage_id','source_hash','plan_hash','failed_result','qualification','reason'},
            'unknown Gather recovery qualification fields')
    require(args['workload']==OPERATOR and args['stage_id']==STAGE and stage['stage_id']==STAGE
            and stage['candidate_id']==CANDIDATE and candidate['candidate_id']==CANDIDATE,
            'recovery source/stage differs')
    plan=stage['plan']
    require(stage['kind']=='timing' and plan.get('purpose')=='search'
            and plan.get('protocol')==LITE_PROTOCOL and plan.get('processes')==2
            and plan.get('pairs_per_case')==6 and plan.get('case_ids')==[1,8,14,20,13,15]
            and len(plan.get('cohorts',[]))==1 and plan['cohorts'][0].get('relation')=='direct_parent',
            'recovery changes the frozen lite search')
    require(candidate['source_parent']['candidate_id']=='gather002'
            and args['source_hash']==candidate['source_hash'] and args['plan_hash']==digest(plan)
            and args['reason']==REASON,'recovery source, parent or reason differs')
    validate_pointer(args['failed_result']);validate_pointer(args['qualification'])
    attempts=stage['attempts'];require(len(attempts) in (1,2),'only one additional stage attempt is allowed')
    first=attempts[0];cost=first.get('actual_costs',{})
    require(first['outcome']=='failed' and first.get('native_started') is False
            and first.get('formal_samples')==0 and type(cost.get('wall_seconds')) is int
            and cost['wall_seconds']>=0 and all(type(v) is int and v>=0 for v in cost.values())
            and all(v==0 for k,v in cost.items() if k!='wall_seconds')
            and first.get('evidence',{}).get('result')==args['failed_result'],
            'original failure/cost/result differs')
    require(stage.get('prestart_recovery') in (None,args),'another recovery qualification exists')
    if len(attempts)==2:require(attempts[1].get('prestart_qualification')==args['qualification'],
                                'second attempt lacks qualification')
    return True


def _project(events):
    stage=None;candidate=None;observations=[]
    for row in events:
        a=row['arguments'];op=row['operation']
        if a.get('workload')!=OPERATOR:continue
        if op=='register' and a.get('candidate_id')==CANDIDATE:candidate=a
        if op=='observe' and a.get('candidate_id')==CANDIDATE:observations.append(a)
        if a.get('stage_id')!=STAGE:continue
        if op=='start':
            if stage is None:stage={'stage_id':STAGE,'candidate_id':CANDIDATE,'kind':a['kind'],
                                    'plan':a['plan'],'attempts':[],'recoveries':0}
            else:
                require(a['plan']==stage['plan'] and len(stage['attempts'])==1 and stage.get('prestart_recovery'),
                        'second start differs from qualified frozen plan')
                stage['recoveries']=1
            attempt={'outcome':None,'native_started':None,'formal_samples':0}
            if stage.get('prestart_recovery'):attempt['prestart_qualification']=stage['prestart_recovery']['qualification']
            stage['attempts'].append(attempt)
        elif op=='finish':
            require(stage is not None and stage['attempts'][-1]['outcome'] is None,'finish has no active search attempt')
            stage['attempts'][-1].update({k:v for k,v in a.items() if k not in ('workload','stage_id')})
        elif op=='qualify_prestart':
            require(stage is not None and 'prestart_recovery' not in stage,'duplicate/early Gather qualification')
            stage['prestart_recovery']=a
    require(stage is not None and candidate is not None,'Gather source/stage missing')
    return stage,candidate,observations


def resolve_result(stage_dir,stage_record,read_bytes=Path.read_bytes,*,require_success=False,qualification_only=False):
    stage_dir=Path(stage_dir);run,task,parent,expected=locations(stage_dir.parents[3].parents[2])
    require(stage_dir==expected,'foreign Gather recovery stage')
    protected={}
    def read(p):return read_bytes(Path(p))
    def ref(p):return {'path':str(p),'sha256':bytes_sha(read(p))}
    def checked(r):
        require(isinstance(r,dict) and set(r)=={'path','sha256'} and ref(r['path'])==r,
                'recovery dependency pointer changed')
        protected[r['path']]=r;return json.loads(read(r['path'])) if str(r['path']).endswith('.json') else read(r['path'])
    original=ref(stage_dir/'result.json');args=stage_record.get('prestart_recovery')
    if args is None:
        if require_success:raise ValueError('Gather search is not recovered')
        return {'current_result':original,'original_failed_result':None,'qualification':None,'protected':[],'event_bindings':[]}
    validate_qualification(stage_record,{'candidate_id':CANDIDATE,'source_hash':args['source_hash'],
                                         'source_parent':{'candidate_id':'gather002'}},args)
    cert_ref=args['qualification'];require(cert_ref['path']==str(stage_dir/'prestart-recovery/qualification.json'),
                                         'qualification path differs')
    cert=checked(cert_ref);require(set(cert)==CERTIFICATE and cert['version']==VERSION
            and cert['arguments']=={k:v for k,v in args.items() if k!='qualification'}
            and cert['authorizes']=='one_same_stage_attempt_no_budget_reset','Gather certificate differs')
    old=checked(original)
    require(original==args['failed_result']==cert['failed_result'] and old.get('status')=='failed'
            and old.get('error')==FAILURE and old.get('native_started') is False
            and old.get('actual_costs')==cert['actual_costs']==stage_record['attempts'][0]['actual_costs'],
            'original failed execution/cost differs')
    plan=checked(cert['stage_plan'])
    require(cert['stage_plan']==ref(stage_dir/'stage-plan.json') and plan==stage_record['plan']
            and digest(plan)==args['plan_hash'] and cert['stage_files_before']==[original,cert['stage_plan']],
            'frozen stage plan or original files differ')
    feedback=checked(cert['blocked_feedback'])
    require(cert['blocked_feedback']==ref(task/'feedback/gather003.json')
            and feedback.get('status')=='infrastructure_blocked' and feedback.get('source_hash')==args['source_hash'],
            'original blocked feedback differs')
    handoff=checked(cert['handoff']);require(handoff.get('epoch')=='graph-base-050-search-lite-01'
            and handoff.get('run')==str(run),'recovery handoff differs')
    for name in ('old_engineering','recovery_engineering'):
        eng=checked(cert[name]);require(eng.get('version')=='level2_frozen_engineering_v1'
                and Path(cert[name]['path']).parent==run/'bootstrap','foreign engineering epoch')
        files={r['path']:r for r in eng['files']}
        if name=='recovery_engineering':
            require(eng.get('skill_library')==handoff['skill_library'],'recovery skill release differs')
            for producer in cert['producers']:
                row=files.get(producer['path'])
                require(row is not None and row['sha256']==producer['sha256'],'producer absent from new engineering')
                checked({'path':row['snapshot'],'sha256':row['sha256']})
    prior=checked(cert['ledger_prefix']);current=read(run/'train/ledger/events.jsonl')
    require(current.startswith(prior),'original ledger prefix changed')
    config=checked(ref(run/'train/ledger/config.json'));events=ledger_events(prior,digest(config))
    projected,candidate,observations=_project(events)
    require(candidate['source_hash']==args['source_hash'] and len(projected['attempts'])==1
            and projected['attempts'][0]['evidence']['result']==original
            and any(o.get('observation_id')=='gather003-feedback-01' and o.get('close_feedback') is False
                    and o.get('report_ref')==cert['blocked_feedback']['sha256'] for o in observations),
            'preserved original ledger source/failure/feedback differs')
    task_prefix=checked(cert['task_event_prefix'])
    require(read(task/'events.jsonl').startswith(task_prefix)
            and any(r['kind']=='stage_completed' and r['value'].get('result')==original for r in task_events(task_prefix)),
            'original task event prefix differs')
    if qualification_only:
        return {'current_result':original,'original_failed_result':original,'qualification':cert_ref,
                'protected':[protected[k] for k in sorted(protected)],'event_bindings':[]}
    rows=ledger_events(current,digest(config));live,_,_=_project(rows)
    require(live.get('prestart_recovery')==args and len(live['attempts'])==len(stage_record['attempts'])==2
            and live['attempts'][0]['evidence']['result']==original,
            'qualified second Gather attempt absent from ledger')
    current_ref=stage_record['attempts'][1]['evidence']['result']
    require(current_ref==ref(stage_dir/'result.recovery-01.json') and live['attempts'][1]['evidence']['result']==current_ref
            and live['attempts'][1]['evidence']['qualification']==cert_ref,
            'recovery result/qualification differs from ledger')
    result=checked(current_ref)
    require(result.get('stage_id')==STAGE and result.get('candidate_id')==CANDIDATE
            and result.get('status') in ('passed','failed')
            and (result['status']=='passed')==(stage_record['attempts'][1]['outcome']=='success')
            and result.get('actual_costs')==stage_record['attempts'][1]['actual_costs']
            and result.get('prestart_recovery')=={'qualification':cert_ref,'previous_result':original,'attempt':2},
            'recovery result/status/cost differs')
    if result['status']=='passed':
        from msprof_exploration_campaign import expected_samples
        cost=result['actual_costs'];count=expected_samples(plan)
        require(stage_record['attempts'][1]['formal_samples']==cost.get('role_samples')==count
                and cost.get('native_processes_started')==cost.get('native_processes_completed')==2,
                'recovered lite sample/process coverage differs')
    if require_success:require(result['status']=='passed' and result.get('error') is None,
                               'recovered Gather search did not pass')
    task_rows=task_events(read(task/'events.jsonl'))
    bound=[r for r in task_rows if r['kind']=='stage_prestart_qualified' and r['value'].get('stage')==STAGE]
    require(len(bound)==1 and bound[0]['value']=={'candidate_id':CANDIDATE,'stage':STAGE,
            'qualification':cert_ref,'failed_result':original},'public qualification event differs')
    event_bindings=[{'path':str(task/'events.jsonl'),'sequence':bound[0]['sequence'],'hash':bound[0]['hash']}]
    return {'current_result':current_ref,'original_failed_result':original,'qualification':cert_ref,
            'protected':[protected[k] for k in sorted(protected)],'event_bindings':event_bindings}


def resolve_from_reader(stage_dir,read_bytes=Path.read_bytes,*,require_success=False):
    stage_dir=Path(stage_dir);run,_,_,expected=locations(stage_dir.parents[3].parents[2]);require(stage_dir==expected,'foreign stage')
    config=json.loads(read_bytes(run/'train/ledger/config.json'))
    events=ledger_events(read_bytes(run/'train/ledger/events.jsonl'),digest(config))
    stage,_,_=_project(events)
    return resolve_result(stage_dir,stage,read_bytes,require_success=require_success)


def audit(run,engineering,handoff):
    from msprof_exploration_campaign import Campaign, _active
    from level2_legacy_epoch import check as check_handoff
    run,task,parent,stage=locations(run)
    handoff=Path(handoff);h=check_handoff(handoff)
    require(h['run']==str(run) and h['new_engineering']==pointer(engineering),'new engineering handoff differs')
    ledger=Campaign(run/'train/ledger');state=ledger.state['tasks'][OPERATOR]
    require(not _active(ledger.state) and not state['frozen'] and state['new_source_attempts']==3
            and state['used']['timing_groups']==3
            and state['reserved_final_candidate_ids']==['gather001','gather002','gather003'],
            'invalid Gather source state')
    candidate=state['candidates'][CANDIDATE];record=state['stages'][STAGE]
    require(not candidate['feedback_closed'] and candidate['observation_ids']==['gather003-feedback-01']
            and len(record['attempts'])==1 and record.get('prestart_recovery') is None
            and sorted(p.name for p in stage.iterdir())==['result.json','stage-plan.json'],
            'recovery stage is already used or partially written')
    args={'workload':OPERATOR,'stage_id':STAGE,'source_hash':candidate['source_hash'],
          'plan_hash':digest(record['plan']),'failed_result':pointer(stage/'result.json'),
          'qualification':{'path':str(stage/'prestart-recovery/qualification.json'),'sha256':'sha256:'+'0'*64},
          'reason':REASON}
    validate_qualification(record,candidate,args)
    require(load(stage/'result.json')['error']==FAILURE and pointer(stage/'stage-plan.json')['sha256'],
            'original failed stage differs')
    return {'run':run,'task':task,'parent':parent,'stage':stage,'ledger':ledger,'candidate':candidate,
            'record':record,'plan':record['plan'],'handoff':pointer(handoff),
            'old_engineering':load(run/'preflight/resume-epoch-033/request.json')['new_engineering'],
            'recovery_engineering':pointer(engineering),'directory':stage/'prestart-recovery'}


def authorize(run,engineering,handoff,*,apply=False,writers_closed=False):
    require(writers_closed is True,'explicit closed-writer attestation required')
    facts=audit(run,engineering,handoff)
    if not apply:return {'status':'eligible_not_authorized','failed_result':pointer(facts['stage']/'result.json')}
    from run_level1_serial import exclusive_host
    from msprof_exploration_execute import event
    with exclusive_host():
        facts=audit(run,engineering,handoff);directory=facts['directory'];directory.mkdir();sync(directory.parent)
        save_bytes(directory/'ledger-prefix.jsonl',data(facts['ledger'].directory/'events.jsonl'))
        save_bytes(directory/'task-events-prefix.jsonl',data(facts['task']/'events.jsonl'))
        args={'workload':OPERATOR,'stage_id':STAGE,'source_hash':facts['candidate']['source_hash'],
              'plan_hash':digest(facts['plan']),'failed_result':pointer(facts['stage']/'result.json'),'reason':REASON}
        eng=load(engineering);files={r['path']:r for r in eng['files']};scripts=Path(__file__).resolve().parent
        producers=[pointer(scripts/name) for name in PRODUCERS]
        require(all(files.get(r['path'],{}).get('sha256')==r['sha256'] for r in producers),
                'recovery producer differs from frozen engineering')
        cert={'version':VERSION,'arguments':args,'stage_plan':pointer(facts['stage']/'stage-plan.json'),
              'failed_result':args['failed_result'],'blocked_feedback':pointer(facts['task']/'feedback/gather003.json'),
              'ledger_prefix':pointer(directory/'ledger-prefix.jsonl'),
              'task_event_prefix':pointer(directory/'task-events-prefix.jsonl'),
              'old_engineering':facts['old_engineering'],'recovery_engineering':facts['recovery_engineering'],
              'handoff':facts['handoff'],'producers':producers,
              'stage_files_before':[args['failed_result'],pointer(facts['stage']/'stage-plan.json')],
              'actual_costs':facts['record']['attempts'][0]['actual_costs'],
              'authorizes':'one_same_stage_attempt_no_budget_reset'}
        save(directory/'qualification.json',cert)
        args['qualification']=pointer(directory/'qualification.json')
        resolve_result(facts['stage'],{**facts['record'],'prestart_recovery':args},qualification_only=True)
        facts['ledger'].qualify_prestart(event_id=OPERATOR+'-'+STAGE+'-qualify-prestart-01',**args)
        event(facts['task'],'stage_prestart_qualified',{'candidate_id':CANDIDATE,'stage':STAGE,
              'qualification':args['qualification'],'failed_result':args['failed_result']})
        return {'status':'qualified_not_executed','qualification':args['qualification'],
                'timing_group_charge_added':False}


def execution_audit(run,qualification_path,expected_sha):
    from msprof_exploration_campaign import Campaign
    run,task,parent,stage=locations(run);qualification_path=Path(qualification_path)
    require(qualification_path==stage/'prestart-recovery/qualification.json' and sha(qualification_path)==expected_sha,
            'foreign/changed Gather recovery qualification')
    cert=load(qualification_path);facts=audit_qualified(run,cert)
    from aprof_layout import skill_lib
    return {**facts,'qualification':pointer(qualification_path),
            'python_import_paths':[str(Path(__file__).resolve().parent),str(skill_lib()/'runtime/src')]}


def audit_qualified(run,cert):
    from msprof_exploration_campaign import Campaign, _active
    from level2_legacy_epoch import check as check_handoff
    run,task,parent,stage=locations(run);ledger=Campaign(run/'train/ledger');record=ledger.state['tasks'][OPERATOR]['stages'][STAGE]
    require(not _active(ledger.state) and len(record['attempts'])==1 and record.get('prestart_recovery'),
            'qualified recovery was already used')
    args=record['prestart_recovery'];resolve_result(stage,record,qualification_only=True)
    require(cert==load(args['qualification']['path']) and cert['handoff']==pointer(cert['handoff']['path'])
            and check_handoff(cert['handoff']['path'])['new_engineering']==cert['recovery_engineering'],
            'recovery handoff or certificate changed')
    require(sorted(p.name for p in stage.iterdir())==['prestart-recovery','result.json','stage-plan.json']
            and not any((stage/r).exists() for r in ('direct_parent','original_baseline','result.recovery-01.json')),
            'recovery output namespace is not fresh')
    return {'run':run,'task':task,'parent':parent,'stage':stage,'plan':record['plan'],
            'ledger':ledger,'directory':stage/'prestart-recovery'}


def check_execution_identity(qualification):
    cert=check(qualification)
    from level2_legacy_epoch import check as check_handoff
    require(check_handoff(cert['handoff']['path'])['new_engineering']==cert['recovery_engineering'],
            'recovery engineering changed during execution')
    for r in cert['producers']:require(pointer(r['path'])==r,'recovery producer changed during execution')
    for r in cert['stage_files_before']:require(pointer(r['path'])==r,'original stage changed during execution')


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='action',required=True)
    for action in ('audit','authorize'):
        p=sub.add_parser(action);p.add_argument('--run',type=Path,required=True)
        p.add_argument('--engineering',type=Path,required=True);p.add_argument('--handoff',type=Path,required=True)
        p.add_argument('--writers-closed',action='store_true')
    p=sub.add_parser('execute');p.add_argument('--run',type=Path,required=True)
    p.add_argument('--qualification',type=Path,required=True);p.add_argument('--qualification-sha256',required=True)
    p.add_argument('--writers-closed',action='store_true')
    a=parser.parse_args()
    if a.action=='execute':
        require(a.writers_closed is True,'explicit closed-writer attestation required')
        from run_msprof_exploration_stage import run_qualified_timing_recovery
        result=run_qualified_timing_recovery(a.run,a.qualification,a.qualification_sha256)
    else:result=authorize(a.run,a.engineering,a.handoff,apply=a.action=='authorize',writers_closed=a.writers_closed)
    print(json.dumps(result,sort_keys=True))
    if a.action=='execute' and result.get('status')!='passed':raise SystemExit(1)


if __name__=='__main__':main()
