#!/usr/bin/env python3
"""Explicit one-shot DQ quota continuation. Archived producer code is never executed.

The certificate authorizes a physical replacement for exactly one failed slot;
source, request design, original attempt and timing charge stay unchanged.
"""
from __future__ import annotations
from aprof_layout import skill_lib
import hashlib,json,re,sys
from pathlib import Path
sys.path.insert(0,str(skill_lib()/"runtime/src"))
from level2_stage_recovery import (canonical,digest,load,pointer,require,sha,ledger_events,task_events)

VERSION='level2_partial_cohort_continuation_v1'
OPERATOR='dynamic_quant';CANDIDATE='dynamic_quant001';STAGE=CANDIDATE+'-search'
SOURCE='sha256:a80a045dc0e5c9714441af4cf54e92a75f718035083db6055f907c6f56fdc232'
ARGS={'workload','stage_id','source_hash','plan_hash','qualification','reason'}
KEYS={'version','run','operator','candidate_id','stage_id','source','stage_plan','cohort_plan','terminal_receipt','preservation','old_engineering','consumer_engineering','producers','ledger_prefix','task_prefix','original_metadata','original_absent','reuse_sessions','failed_session','replacement_name','failed_costs','scope'}
LIMITATIONS=['The cohort crosses an explicitly retained infrastructure interruption; elapsed-time/environment drift is not independently controlled.', 'The failed process is excluded from the six formal rows but retained in actual cost and provenance.', 'Native-output retirement and output deduplication are unsupported for this continued cohort.', 'The original native exit is 1 and the owner tool exit is 1; the missing original msprof execution receipt leaves the profiler exit unknown.']
REQUIRED_PRODUCERS={'level2_cohort_continuation.py','msprof_exploration_campaign.py','msprof_exploration_report.py','msprof_exploration_provenance.py','level2_iteration.py','msprof_exploration_archive.py','run_msprof_exploration_stage.py','msprof_exploration_execute.py','cannbench_msprof_timing.py','level2_failed_capture_preservation.py','level2_stage_recovery.py','level2_prestart_recovery.py'}
COST_KEYS=('native_processes_started','native_processes_completed','role_samples','timed_complete_calls','warmup_complete_calls','formal_target_kernel_launches','unconfirmed_warmup_blocks')


def validate_qualification(stage,candidate,a):
    require(set(a)==ARGS and a['workload']==OPERATOR and a['stage_id']==STAGE,'unsupported continuation operation')
    require(stage is not None and candidate is not None and stage['stage_id']==STAGE and stage['candidate_id']==CANDIDATE and stage['kind']=='timing','foreign continuation stage')
    require(candidate.get('feedback_closed') is False and candidate.get('observation_ids')==[],'only the original unclosed source observation may qualify')
    require(candidate['source_hash']==a['source_hash']==SOURCE and digest(stage['plan'])==a['plan_hash'],'continuation source/plan changed')
    require(stage['plan']['purpose']=='search' and stage['plan']['case_ids']==[1,8,14,20,6,16] and len(stage['plan']['cohorts'])==1 and stage['plan']['cohorts'][0]['relation']=='direct_parent','only original DQ search design supported')
    require(len(stage['attempts'])==1 and stage['attempts'][0]['outcome'] is None and stage['attempts'][0]['charged']=='timing_groups' and stage['recoveries']==0 and 'prestart_recovery' not in stage,'continuation requires original active charged attempt')
    require('continuation' not in stage and isinstance(a['reason'],str) and a['reason'].strip(),'continuation already qualified or reason absent')
    pointer(a['qualification'])


def journal_costs(data, *, failed=False):
    rows=[load(line) for line in data.splitlines()]
    require(rows and rows[0].get('type')=='process_start' and sum(r.get('type')=='process_start' for r in rows)==1,'journal process identity missing')
    end=rows[-1];require(end.get('type')=='session_end' and type(end.get('exit_code')) is int and end['exit_code']==(1 if failed else 0) and end.get('context_destroyed') is True and end.get('stream_destroyed') is True,'journal terminal result differs')
    require(all(r.get('session_id')==rows[0]['session_id'] for r in rows),'mixed native journal sessions')
    result=dict.fromkeys(COST_KEYS,0);result['native_processes_started']=1;result['native_processes_completed']=int(not failed)
    for r in rows:
        if r['type']=='case_start':result['unconfirmed_warmup_blocks']+=1
        elif r['type']=='warmup_complete':
            require(type(r['calls_per_role']) is int and r['calls_per_role']==10,'warmup count differs');result['warmup_complete_calls']+=2*r['calls_per_role'];result['unconfirmed_warmup_blocks']-=1
        elif r['type']=='sample':
            require(type(r['repeat']) is int and r['repeat']==10 and type(r['launches_per_call']) is int and r['launches_per_call']>0,'sample cost fields invalid')
            result['role_samples']+=1;result['timed_complete_calls']+=r['repeat'];result['formal_target_kernel_launches']+=r['repeat']*r['launches_per_call']
    if failed:
        require([r.get('error') for r in rows if r['type']=='failure']==['output open failed'],'unsupported original native failure')
        require(result['role_samples']==360 and result['warmup_complete_calls']==120 and result['unconfirmed_warmup_blocks']==0,'failed p03 cost coverage differs')
    else:require(result['role_samples']==720 and result['warmup_complete_calls']==240 and result['unconfirmed_warmup_blocks']==0,'accepted process cost coverage differs')
    return result


def resolve(cohort,read_bytes=Path.read_bytes,*,require_closed=False,qualification_only=False):
    """Authenticate the fixed mapping and return its complete metadata closure.

    Tar bytes are retained as opaque evidence pointers; the preservation producer
    verifies their inventories. No archive code or historical producer is run.
    """
    cohort=Path(cohort);certpath=cohort/'continuation-01/qualification.json'
    try:data=read_bytes(certpath)
    except FileNotFoundError:return None
    stage=cohort.parent;child=stage.parent.parent;task=child.parent.parent;run=task.parents[2]
    require(cohort==run/'validation/tasks'/OPERATOR/'candidates'/CANDIDATE/'stages/search/direct_parent','unsupported continuation namespace')
    protected={};retained_inputs={}
    def read(p):return read_bytes(Path(p))
    def checked(ref):
        pointer(ref);actual=ref
        if not Path(ref['path']).is_relative_to(run) and ref['path'] in retained_inputs:
            pair=retained_inputs[ref['path']];require(pair['original']==ref,'retained origin differs');actual=pair['retained']
        b=read(actual['path']);require(sha(b)==ref['sha256'],'continuation evidence changed: '+ref['path']);protected[actual['path']]=actual;return b
    def ref(p):return {'path':str(p),'sha256':sha(read(p))}
    cr={'path':str(certpath),'sha256':sha(data)};protected[str(certpath)]=cr;c=load(data)
    require(set(c)==KEYS and c['version']==VERSION and c['run']==str(run) and c['operator']==OPERATOR and c['candidate_id']==CANDIDATE and c['stage_id']==STAGE,'unknown continuation certificate')
    require(c['scope']=='one_original_active_attempt_no_new_source_start_or_charge','unsupported continuation scope')
    from level2_failed_capture_preservation import completion_metadata
    require(c['preservation']['path']==str(child/'failed-search-p03-preservation-01/completion.json'),'preservation namespace differs')
    preserved=completion_metadata(c['preservation']['path'],c['preservation']['sha256'],read_bytes=read)
    retained_inputs={r['original']['path']:r for r in preserved['retained_inputs']}
    for r in preserved['protected']:protected[r['path']]=r
    preservation=load(checked(c['preservation']));preservation_request=load(checked(preservation['request']))
    require(c['source']=={'path':str(child/'source.tar'),'sha256':SOURCE},'continuation source differs')
    # Source bytes are streamed at execution; its registered hash is authenticated below.
    protected[c['source']['path']]=c['source']
    require(c['stage_plan']['path']==str(stage/'stage-plan.json') and c['cohort_plan']['path']==str(cohort/'plan.json'),'continuation changes frozen plan path')
    plan=load(checked(c['stage_plan']));cp=load(checked(c['cohort_plan']))
    require(plan['purpose']=='search' and plan['case_ids']==cp['case_ids']==[1,8,14,20,6,16] and len(plan['cohorts'])==1 and plan['cohorts'][0]['relation']=='direct_parent','continuation scope differs')
    require(load(checked(plan['cohorts'][0]['plan']))==cp,'original plan bytes/meaning differ')
    schedule=cp['schedule'];require(len(schedule)==6 and len({r['name'] for r in schedule})==6,'original schedule differs')
    original=[str(cohort/r['name']) for r in schedule]
    require(c['reuse_sessions']==original[:2] and c['failed_session']==original[2] and c['replacement_name']==schedule[2]['name']+'-continuation-01','continuation remaps an unapproved slot')
    paths=original[:];paths[2]=str(cohort/c['replacement_name'])
    absent=[str(stage/'result.json'),str(cohort/'group-completion.json'),str(cohort/'identity-resolution.json'),str(cohort/'producer-summary.json'),str(cohort/'report.json')]
    require(c['original_absent']==absent,'original absence declaration differs')
    oldrefs=c['original_metadata'];require(isinstance(oldrefs,list) and len({r['path'] for r in oldrefs})==len(oldrefs),'duplicate original metadata')
    originals={r['path']:r for r in oldrefs}
    needed={str(cohort/'identity-preflight.json')}
    for name in original[:2]:
        needed.update(str(Path(name)/n) for n in ('request.json','bindings.json','completion.json','msprof.execution.json','native/journal.jsonl','samples.json','validation.json','cases.json','cases.tsv','health-before.json','health-after.json'))
    needed.update(str(Path(original[2])/n) for n in ('request.json','bindings.json','native/journal.jsonl','raw-storage.request.json'))
    require(set(originals)==needed,'original observation metadata roster differs')
    for r in oldrefs:checked(r)
    for i in range(3):require(load(checked(originals[str(Path(original[i])/'request.json')]))==schedule[i]['request'],'original request differs from frozen slot')
    failed_costs=journal_costs(checked(originals[str(Path(original[2])/'native/journal.jsonl')]),failed=True)
    require(c['failed_costs']==failed_costs,'failed sample costs erased or changed')
    for name in original[:2]:
        d=Path(name);completion=load(checked(originals[str(d/'completion.json')]));execution=load(checked(originals[str(d/'msprof.execution.json')]))
        require(completion.get('status')=='passed' and completion.get('error') is None and type(execution.get('exit_code')) is int and execution['exit_code']==0 and execution.get('error') is None,'reused observation was not actually successful')
        journal_costs(checked(originals[str(d/'native/journal.jsonl')]))
    terminal=load(checked(c['terminal_receipt']))
    require(terminal.get('version')=='dq001_terminal_infrastructure_owner_receipt_v1' and terminal.get('source_hash')==SOURCE and terminal.get('writer_terminal') is True and terminal.get('source_feedback_closed') is False,'authentic terminal-infrastructure receipt required')
    tool=terminal['tool_result'];require(type(tool.get('session_id')) is int and tool['session_id']==89943 and type(tool.get('exit_code')) is int and tool['exit_code']==1 and tool.get('terminal') is True,'original tool exit must remain actual 1')
    require(terminal['allowed_open_stage']['stage_id']==STAGE and terminal['allowed_open_stage']['plan']==c['stage_plan'],'terminal stage binding differs')
    for key in ('owner_request','forensics','health_after'):checked(terminal[key])
    health=load(checked(terminal['health_after']));require(health.get('status')=='passed' and health.get('no_device_processes') is True and health.get('processes')==[],'terminal receipt lacks passed idle health')
    require(preservation_request['original_bindings']['terminal']==c['terminal_receipt'] and preservation_request['original_roots']['native']==str(Path(original[2])/'native'),'preservation belongs to another failed process')
    # Immutable copies anchor the prefix; lawful unrelated ledger suffixes remain allowed.
    ledgerdir=run/'validation/ledger';cfgref=ref(ledgerdir/'config.json');cfg=load(checked(cfgref));ch=digest(cfg)
    require(load(checked(ref(ledgerdir/'config.sha256.json')))=={'sha256':ch},'ledger config changed')
    for key,name,origin in (('ledger_prefix','ledger-prefix.jsonl',ledgerdir/'events.jsonl'),('task_prefix','task-prefix.jsonl',task/'events.jsonl')):
        require(c[key]['path']==str(certpath.parent/name),'prefix must be durable same-qualification copy')
        b=checked(c[key]);require(read(origin).startswith(b),'original event prefix changed')
    before=ledger_events(checked(c['ledger_prefix']),ch);rows=ledger_events(read(ledgerdir/'events.jsonl'),ch)
    import msprof_exploration_campaign as campaign
    def project(events):
        s=campaign._initial_state(cfg)
        for e in events[1:]:campaign._transition(s,cfg,e['operation'],e['arguments'])
        return s
    prior=project(before);current=project(rows);pt=prior['tasks'][OPERATOR];ct=current['tasks'][OPERATOR]
    prior_stage=pt['stages'][STAGE];args={'workload':OPERATOR,'stage_id':STAGE,'source_hash':SOURCE,'plan_hash':digest(plan),'qualification':cr,'reason':'Explicit quota interruption continuation; original failed process retained.'}
    validate_qualification(prior_stage,pt['candidates'][CANDIDATE],args)
    require(prior_stage['plan']==plan and pt['new_source_attempts']==1 and pt['new_rounds_started']==1,'prior active stage/source count differs')
    require(campaign._active(prior)==[(OPERATOR,STAGE)],'prior state contains other active stages')
    stage_state=ct['stages'][STAGE];require(len(stage_state['attempts'])==1 and stage_state['plan']==plan,'original active attempt was replaced')
    bindings=[]
    if not qualification_only:
        require(stage_state.get('continuation')==args,'ledger does not authorize exact continuation certificate')
        qe=[e for e in rows if e['operation']=='qualify_continuation' and e['arguments'].get('stage_id')==STAGE]
        require(len(qe)==1 and qe[0]['arguments']==args,'continuation qualification is not unique')
        at_qualification=project(rows[:qe[0]['sequence']+1])['tasks'][OPERATOR]
        require(all(at_qualification[k]==pt[k] for k in ('new_source_attempts','new_rounds_started','stage_starts','used')),'qualification changed original budget/start counters')
        bindings.append({'path':str(ledgerdir/'events.jsonl'),'sequence':qe[0]['sequence'],'hash':qe[0]['hash']})
        events=task_events(read(task/'events.jsonl'));te=[e for e in events if e['kind']=='stage_continuation_qualified' and e['value'].get('stage')==STAGE]
        require(len(te)==1 and te[0]['value']=={'candidate_id':CANDIDATE,'stage':STAGE,'qualification':cr},'task qualification event absent or changed')
        bindings.append({'path':str(task/'events.jsonl'),'sequence':te[0]['sequence'],'hash':te[0]['hash']})
    # Both engineering manifests are inert data. Execution separately verifies live origins.
    require(c['old_engineering']!=c['consumer_engineering'],'continuation must explicitly bind new engineering')
    oldbindings={}
    for name in original[:3]:oldbindings.update(load(checked(originals[str(Path(name)/'bindings.json')])))
    for label in ('old_engineering','consumer_engineering'):
        er=c[label];require(Path(er['path']).parent==run/'bootstrap','engineering must be canonical run evidence')
        eng=load(checked(er));require(eng.get('version')=='level2_frozen_engineering_v1','invalid frozen engineering')
        checked(eng['campaign_manifest']);manifests=eng['task_manifests']
        require(len({r['path'] for r in manifests})==len(manifests),'duplicate engineering task manifest')
        same_task=[r for r in manifests if r['path']==str(task/'manifest.json')]
        require(len(same_task)==1,'engineering lacks exact task');checked(same_task[0])
        files={r['path']:r for r in eng['files']};require(len(files)==len(eng['files']),'duplicate engineering producer')
        selected=c['producers'] if label=='consumer_engineering' else [{'path':p,'sha256':s} for p,s in oldbindings.items() if p in files]
        if label=='consumer_engineering':require(REQUIRED_PRODUCERS<={Path(r['path']).name for r in selected},'continuation producer closure incomplete')
        for r in selected:
            pointer(r);item=files.get(r['path']);require(item and item['sha256']==r['sha256'] and item['snapshot']==str(run/'bootstrap/source-cas'/r['sha256'][7:]),'producer lacks exact engineering CAS')
            checked({'path':item['snapshot'],'sha256':r['sha256']})
    proof={'qualification':cr,'cohort':str(cohort),'protected':[protected[k] for k in sorted(protected)],'event_bindings':bindings,'directories':paths,'failed_directory':original[2],'failed_costs':failed_costs,'interruption_limitations':LIMITATIONS}
    if require_closed:
        finishes=[e for e in rows if e['operation']=='finish' and e['arguments'].get('workload')==OPERATOR and e['arguments'].get('stage_id')==STAGE]
        require(len(finishes)==1,'continuation needs its unique historical finish')
        at_finish=project(rows[:finishes[0]['sequence']+1])['tasks'][OPERATOR]
        require(all(at_finish[k]==pt[k] for k in ('new_source_attempts','new_rounds_started','stage_starts','used')),'continuation finish changed source/start/budget counters')
        attempt=stage_state['attempts'][0];require(attempt['outcome']=='success' and attempt['native_started'] is True and attempt['formal_samples']==4320,'continuation has not closed six formal processes')
        bindings.append({'path':str(ledgerdir/'events.jsonl'),'sequence':finishes[0]['sequence'],'hash':finishes[0]['hash']})
        rr=attempt['evidence']['result'];require(rr['path']==str(stage/'result.json') and attempt['evidence'].get('continuation')==cr,'finish does not bind continuation')
        result=load(checked(rr));group=load(checked(ref(cohort/'group-completion.json')));report=load(checked(ref(cohort/'report.json')))
        require(result.get('status')=='passed' and result.get('error') is None and result.get('continuation')==cr and result.get('formal_samples')==4320 and result['actual_costs']==attempt['actual_costs'],'closed stage continuation differs')
        require(group.get('status')=='passed' and group['completed_sessions']==paths and group.get('continuation')==cr and report.get('continuation')==annotation(proof),'closed cohort mapping differs')
        require([r['directory'] for r in report['sessions']]==paths,'report contains unapproved session mapping')
        costs=dict(failed_costs)
        for name in paths:
            for key,n in journal_costs(read(Path(name)/'native/journal.jsonl')).items():costs[key]+=n
        require(all(result['actual_costs'].get(k)==v for k,v in costs.items()),'closed costs omit failed work or accepted processes')
        require(all(r.get('qualified_performance_eligible') is False for r in report['results']) and all(r.get('qualified_performance_eligible') is False for r in report['suite'].values()),'interrupted search cannot claim qualified performance')
        proof['protected']=[protected[k] for k in sorted(protected)]
    return proof


def annotation(proof):
    return {k:proof[k] for k in ('qualification','failed_directory','failed_costs','interruption_limitations')} | {'accepted_processes':6,'actual_processes_including_failed':7,'native_output_retirement':'unsupported','output_deduplication':'unsupported'}


def _live_identity(proof, certificate=None):
    """Execution-only checks; archives use inert producer CAS via resolve()."""
    from msprof_exploration_execute import load as readjson,sha as file_sha
    from run_msprof_exploration_stage import verify_source_snapshot
    c=certificate if certificate is not None else readjson(proof['qualification']['path']);child=Path(proof['cohort']).parent.parent.parent
    from level2_prestart_recovery import engineering
    run=Path(c['run'])
    engineering(Path(c['consumer_engineering']['path']),c['consumer_engineering']['sha256'],run,current=True)
    require(file_sha(child/'source.tar')==SOURCE,'source archive changed')
    verify_source_snapshot(child/'source.tar',child/'op')
    for ref in c['producers']:require(file_sha(ref['path'])==ref['sha256'],'current consumer differs from frozen engineering')
    return c


def _absent(c):
    for p in c['original_absent']:require(not Path(p).exists() and not Path(p).is_symlink(),'canonical output was already published; explicit inspection required')
    failed=Path(c['failed_session'])
    for n in ('msprof.execution.json','completion.json'):
        require(not (failed/n).exists() and not (failed/n).is_symlink(),'original unknown profiler outcome or failed collection was rewritten')


def authorize(run,terminal_receipt,terminal_sha,preservation,preservation_sha,consumer_engineering,consumer_sha):
    """Create a concrete certificate, then explicitly qualify the active attempt.

    Caller supplies external hashes of actual terminal, full preservation and
    new engineering records. No native operation occurs in this function.
    """
    from msprof_exploration_execute import pointer as file_ref,load as readjson,save,event,sha as file_sha
    from msprof_exploration_campaign import Campaign
    run=Path(run).resolve();task=run/'validation/tasks'/OPERATOR;child=task/'candidates'/CANDIDATE;stage=child/'stages/search';cohort=stage/'direct_parent';directory=cohort/'continuation-01'
    def external(path,expected):
        r=file_ref(path);require(r['sha256']==expected,'external certificate input SHA differs');return r
    tr=external(terminal_receipt,terminal_sha);pr=external(preservation,preservation_sha);er=external(consumer_engineering,consumer_sha)
    from level2_failed_capture_preservation import verify_completion
    verify_completion(pr['path'],pr['sha256'])
    require(Path(er['path']).parent==run/'bootstrap' and Path(er['path']).name!='frozen-engineering-024.json','actual new canonical engineering required')
    eng=readjson(er['path']);scripts=Path(__file__).resolve().parent
    producers=[file_ref(scripts/name) for name in sorted(REQUIRED_PRODUCERS)]
    files={r['path']:r for r in eng['files']}
    for r in producers:require(r['path'] in files and files[r['path']]['sha256']==r['sha256'],'new frozen engineering does not bind actual continuation producer')
    plan=readjson(cohort/'plan.json');original=[cohort/r['name'] for r in plan['schedule']]
    require(len(original)==6,'six original schedule rows required')
    metadata=[cohort/'identity-preflight.json']
    for d in original[:2]:metadata += [d/n for n in ('request.json','bindings.json','completion.json','msprof.execution.json','native/journal.jsonl','samples.json','validation.json','cases.json','cases.tsv','health-before.json','health-after.json')]
    metadata += [original[2]/n for n in ('request.json','bindings.json','native/journal.jsonl','raw-storage.request.json')]
    oldeng=run/'bootstrap/frozen-engineering-024.json'
    require(file_sha(oldeng)=='sha256:3716fb07a9f937f9c7ec6ab1003f8e3d112089e89dc769dba80b48299197495b','original actual024 engineering differs')
    c={'version':VERSION,'run':str(run),'operator':OPERATOR,'candidate_id':CANDIDATE,'stage_id':STAGE,'source':file_ref(child/'source.tar'),
       'stage_plan':file_ref(stage/'stage-plan.json'),'cohort_plan':file_ref(cohort/'plan.json'),'terminal_receipt':tr,'preservation':pr,
       'old_engineering':file_ref(oldeng),'consumer_engineering':er,'producers':producers,
       'ledger_prefix':None,'task_prefix':None,'original_metadata':[file_ref(p) for p in sorted(metadata)],
       'original_absent':[str(stage/'result.json'),str(cohort/'group-completion.json'),str(cohort/'identity-resolution.json'),str(cohort/'producer-summary.json'),str(cohort/'report.json')],
       'reuse_sessions':[str(p) for p in original[:2]],'failed_session':str(original[2]),'replacement_name':original[2].name+'-continuation-01',
       'failed_costs':journal_costs((original[2]/'native/journal.jsonl').read_bytes(),failed=True),'scope':'one_original_active_attempt_no_new_source_start_or_charge'}
    _absent(c)
    for p in [cohort/c['replacement_name'],*original[3:]]:require(not p.exists(),'remaining physical session namespace already exists')
    ledger=Campaign(run/'validation/ledger');state=ledger.state['tasks'][OPERATOR];args={'workload':OPERATOR,'stage_id':STAGE,'source_hash':SOURCE,'plan_hash':digest(readjson(stage/'stage-plan.json')),'qualification':{'path':str(directory/'qualification.json'),'sha256':'sha256:'+'0'*64},'reason':'Explicit quota interruption continuation; original failed process retained.'}
    validate_qualification(state['stages'][STAGE],state['candidates'][CANDIDATE],args)
    # Validate the exact prospective bytes before claiming the one-shot namespace.
    overlay={}
    for key,name,origin in (('ledger_prefix','ledger-prefix.jsonl',run/'validation/ledger/events.jsonl'),('task_prefix','task-prefix.jsonl',task/'events.jsonl')):
        p=directory/name;overlay[p]=origin.read_bytes();c[key]={'path':str(p),'sha256':sha(overlay[p])}
    overlay[directory/'qualification.json']=canonical(c)+b'\n'
    def prospective(p):
        p=Path(p);return overlay[p] if p in overlay else p.read_bytes()
    proof=resolve(cohort,prospective,qualification_only=True);_live_identity(proof,c);_absent(c)
    directory.mkdir(exist_ok=False)
    for p,b in overlay.items():
        with p.open('xb') as f:f.write(b);f.flush();__import__('os').fsync(f.fileno())
    require(resolve(cohort,qualification_only=True)==proof,'qualification inputs changed during publication')
    _live_identity(proof);_absent(c)
    args['qualification']=proof['qualification']
    ledger.qualify_continuation(event_id=OPERATOR+'-'+STAGE+'-continuation-01-qualified',**args)
    event(task,'stage_continuation_qualified',{'candidate_id':CANDIDATE,'stage':STAGE,'qualification':args['qualification']})
    return resolve(cohort)


def execute(qualification_path,external_sha):
    """Continue the same attempt once; collector and its host locks are unchanged."""
    import fcntl,os,time
    from msprof_exploration_execute import (pointer as file_ref,load as readjson,save,event,preflight_cohort,execution_modules)
    from msprof_exploration_report import verify_observation,analyze_task_cohort
    from msprof_exploration_campaign import Campaign
    from run_msprof_exploration_stage import actual_costs,validate_calibration_storage
    path=Path(qualification_path).resolve();require(file_ref(path)['sha256']==external_sha,'external continuation SHA differs')
    cohort=path.parent.parent;stage=cohort.parent;child=stage.parent.parent;task=child.parent.parent;run=task.parents[2]
    proof=resolve(cohort);require(proof is not None and proof['qualification']==file_ref(path),'explicit qualified certificate missing')
    c=_live_identity(proof);_absent(c)
    from level2_failed_capture_preservation import verify_completion
    verify_completion(c['preservation']['path'],c['preservation']['sha256'])
    with (path.parent/'execute.lock').open('xb') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        proof=resolve(cohort);c=_live_identity(proof);_absent(c)
        for name in proof['directories'][2:]:require(not Path(name).exists(),'continuation cannot retry previously entered slot')
        plan=readjson(cohort/'plan.json');stageplan=readjson(stage/'stage-plan.json')
        calref=stageplan['cohorts'][0].get('calibration_report') or stageplan['calibration_report']
        require(file_ref(calref['path'])==calref,'frozen calibration changed');calibration=readjson(calref['path']);validate_calibration_storage(plan,calibration)
        preflight=preflight_cohort(plan);timing,_,_=execution_modules();provenance=list(preflight['producer_bindings'])
        # Verify old p01/p02 before the one-shot native continuation claim.
        for i in range(2):verify_observation(proof['directories'][i],plan['schedule'][i]['request'],provenance_out=provenance)
        require(resolve(cohort)==proof,'continuation inputs changed before claim');_absent(c)
        save(path.parent/'execution-started.json',{'qualification':proof['qualification'],'accepted_prefix':proof['directories'][:2],'new_sessions':proof['directories'][2:],'automatic_retry':False,'started_at':time.time()})
        started=time.time();completed=proof['directories'][:2];error=None
        try:
            for i in range(2,6):
                require(resolve(cohort)==proof,'continuation metadata changed before native');_live_identity(proof)
                provenance.extend(preflight_cohort(plan)['producer_bindings'])
                rp=path.parent/(f'p{i+1:02d}-request.json');save(rp,plan['schedule'][i]['request']);directory=Path(proof['directories'][i])
                print(json.dumps({'phase':'native_process_start','session':directory.name,'continuation':proof['qualification'],'time':time.time()}),flush=True)
                timing.collect(rp,directory)
                verify_observation(directory,plan['schedule'][i]['request'],provenance_out=provenance);completed.append(str(directory))
                print(json.dumps({'phase':'native_process_verified','session':directory.name,'time':time.time()}),flush=True)
            report=analyze_task_cohort(completed,plan,calibration=calibration,provenance_out=provenance)
            require(resolve(cohort)==proof,'continuation changed after report');_live_identity(proof);_absent(c)
            verify_completion(c['preservation']['path'],c['preservation']['sha256'])
            save(cohort/'report.json',report);save(cohort/'producer-summary.json',timing.summarize(completed))
        except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)}
        # A second interruption is retained once and is never implicitly retried.
        require(resolve(cohort)==proof,'continuation authority changed before finish');_live_identity(proof)
        unique={canonical(r):r for r in provenance}
        save(cohort/'identity-resolution.json',{'read_only_resolution':True,'producer_bindings':list(unique.values()),'continuation':proof['qualification']})
        save(cohort/'group-completion.json',{'status':'failed' if error else 'passed','error':error,'completed_sessions':completed,'sessions':[{'directory':d,'completion':file_ref(Path(d)/'completion.json'),'samples':file_ref(Path(d)/'samples.json'),'journal':file_ref(Path(d)/'native/journal.jsonl')} for d in completed], 'ended_at':time.time(),'protocol':plan['protocol'],'continuation':proof['qualification']})
        costs=actual_costs(stage);costs['wall_seconds']=int(time.time()-started)
        formal=sum(journal_costs((Path(d)/'native/journal.jsonl').read_bytes())['role_samples'] for d in completed)
        if error is None:require(formal==4320 and costs['role_samples']==4680 and costs['native_processes_started']==7 and costs['native_processes_completed']==6,'actual continuation cost coverage differs')
        from datetime import datetime
        prior_rows=[load(line) for line in Path(c['ledger_prefix']['path']).read_bytes().splitlines()]
        original_start=next(r for r in prior_rows if r['operation']=='start' and r['arguments'].get('workload')==OPERATOR and r['arguments'].get('stage_id')==STAGE)
        original_start_binding={'path':str(run/'validation/ledger/events.jsonl'),'sequence':original_start['sequence'],'hash':original_start['hash'],'recorded_at':original_start['recorded_at']}
        result={'status':'failed' if error else 'passed','kind':'timing','stage_id':STAGE,'candidate_id':CANDIDATE,'started_at':datetime.fromisoformat(original_start['recorded_at']).timestamp(),'original_stage_start':original_start_binding,'start_time_scope':'Original ledger start timestamp, not a reconstructed collector wall interval.','continuation_started_at':started,'ended_at':time.time(),'error':error,'native_started':True,'actual_costs':costs,'formal_samples':formal,'cost_scope':'Native counters include original p01/p02, failed p03 and every new process. Formal samples include only accepted complete sessions. wall_seconds covers only this continuation invocation; original collection wall duration and the infrastructure gap are not charged or inferred as zero.','formal_admission':'not_evaluated','graph_policy_eligible':False,'episode_ref':None,'continuation':proof['qualification']}
        save(stage/'result.json',result)
        ledger=Campaign(run/'validation/ledger');ledger.finish(event_id=OPERATOR+'-'+STAGE+'-finish',workload=OPERATOR,stage_id=STAGE,outcome='failed' if error else 'success',evidence={'result':file_ref(stage/'result.json'),'continuation':proof['qualification']},native_started=True,formal_samples=formal,actual_costs=costs,reason=json.dumps(error) if error else None)
        event(task,'stage_completed',{'candidate_id':CANDIDATE,'stage':STAGE,'result':file_ref(stage/'result.json'),'continuation':proof['qualification']})
        if error is None:resolve(cohort,require_closed=True)
        save(path.parent/'execution-completion.json',{'status':result['status'],'qualification':proof['qualification'],'result':file_ref(stage/'result.json'),'automatic_retry':False,'native_processes_added':costs['native_processes_started']-3,'error':error})
        return result


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('authorize');a.add_argument('--run',required=True)
    for n in ('terminal-receipt','preservation','consumer-engineering'):
        a.add_argument('--'+n,required=True);a.add_argument('--'+n+'-sha',required=True)
    e=sub.add_parser('execute');e.add_argument('--qualification',required=True);e.add_argument('--qualification-sha',required=True)
    args=p.parse_args()
    if args.command=='authorize':result=authorize(args.run,args.terminal_receipt,args.terminal_receipt_sha,args.preservation,args.preservation_sha,args.consumer_engineering,args.consumer_engineering_sha)
    else:result=execute(args.qualification,args.qualification_sha)
    print(json.dumps(result,sort_keys=True));return 1 if result.get('status')=='failed' else 0

if __name__=='__main__':raise SystemExit(main())
