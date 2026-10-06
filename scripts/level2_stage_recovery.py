#!/usr/bin/env python3
"""Data-only, one-use GN002 final pre-native recovery contract.

Historical ordinary results do not acquire new ledger or producer dependencies.
No archived Python is executed. Consumers supply trusted bytes readers.
"""
from __future__ import annotations
import hashlib,json,re
from pathlib import Path

VERSION='level2_final_prestart_qualification_v1'
ARGUMENTS={'workload','stage_id','source_hash','plan_hash','failed_result','qualification','reason'}
CERTIFICATE={'version','arguments','stage_plan','finalization_request','preservation','ledger_prefix','task_event_prefix','old_engineering','recovery_engineering','producers','stage_files_before','native_started','formal_samples','actual_costs','failure','authorizes'}
FAILURE={'type':'ModuleNotFoundError','message':"No module named 'aprof_runtime'"}
REQUIRED_PRODUCERS={'level2_stage_recovery.py','msprof_exploration_campaign.py','run_msprof_exploration_stage.py','level2_prestart_recovery.py','level2_iteration.py','level2_finalize.py'}

def require(ok,message):
    if not ok:raise ValueError(message)
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()
def digest(v):return 'sha256:'+hashlib.sha256(canonical(v)).hexdigest()
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def load(b):
    def pairs(rows):
        out={}
        for k,v in rows:require(k not in out,'duplicate recovery JSON key');out[k]=v
        return out
    def bad(v):raise ValueError('nonfinite recovery JSON')
    return json.loads(b,object_pairs_hook=pairs,parse_constant=bad)
def path(v):
    require(isinstance(v,str),'recovery path must be text');p=Path(v)
    require(p.is_absolute() and '..' not in p.parts and str(p)==v,'noncanonical recovery path');return p
def pointer(v):
    require(isinstance(v,dict) and set(v)=={'path','sha256'} and isinstance(v['sha256'],str) and re.fullmatch(r'sha256:[0-9a-f]{64}',v['sha256']),'invalid recovery pointer');path(v['path']);return v
def zero_costs(v):return isinstance(v,dict) and bool(v) and all(type(n) is int and n==0 for n in v.values())

def validate_qualification(stage,candidate,args):
    """Pure Campaign transition gate; file/certificate proof is replayed separately."""
    require(isinstance(args,dict) and set(args)==ARGUMENTS,'unknown prestart qualification arguments')
    require(args['workload']=='group_norm' and args['stage_id']=='group_norm002-final' and stage['stage_id']==args['stage_id'] and stage['candidate_id']=='group_norm002','only exact GN002 final recovery is reviewed')
    require(stage['kind']=='timing' and stage['plan'].get('purpose')=='final' and stage['plan'].get('case_ids')==list(range(1,21)),'recovery requires original full20 final plan')
    require(candidate['candidate_id']=='group_norm002' and args['source_hash']==candidate['source_hash'] and args['plan_hash']==digest(stage['plan']),'recovery source/plan identity differs')
    require(isinstance(args['reason'],str) and bool(args['reason'].strip()),'recovery reason is required')
    pointer(args['failed_result']);pointer(args['qualification'])
    attempts=stage['attempts'];require(len(attempts) in (1,2),'exactly one original failed attempt and at most one recovery')
    first=attempts[0]
    require(first['outcome']=='failed' and first.get('native_started') is False and type(first.get('formal_samples')) is int and first['formal_samples']==0 and zero_costs(first.get('actual_costs')),'original stage is not a zero-native/zero-cost failed attempt')
    require(first.get('evidence',{}).get('result')==args['failed_result'],'qualification changes original failed result')
    require(stage.get('prestart_recovery') in (None,args),'another prestart qualification already exists')
    if len(attempts)==2:require(attempts[1].get('prestart_qualification')==args['qualification'],'second attempt lacks exact prestart qualification')
    return True


def ledger_events(data,config_hash):
    rows=[];previous='sha256:'+'0'*64;ids=set()
    for n,line in enumerate(data.splitlines()):
        row=load(line)
        require(set(row)=={'sequence','event_id','operation','arguments','recorded_at','previous_hash','config_hash','hash'} and type(row['sequence']) is int and row['sequence']==n and canonical(row)==line,'ledger recovery prefix shape differs')
        require(row['previous_hash']==previous and row['config_hash']==config_hash and row['hash']==digest({k:v for k,v in row.items() if k!='hash'}) and row['event_id'] not in ids,'ledger recovery prefix hash differs')
        if n==0:require(row['operation']=='prepare' and row['event_id']=='genesis' and row['arguments']=={},'recovery ledger genesis differs')
        previous=row['hash'];ids.add(row['event_id']);rows.append(row)
    require(bool(rows),'empty recovery ledger');return rows


def project_stage(events,operator,stage_id):
    """Project one stage from already hash-checked ledger rows."""
    stage=None;candidate=None;qualified=None
    for event in events:
        args=event['arguments'];op=event['operation']
        if args.get('workload')!=operator:continue
        if op=='register' and args.get('candidate_id')=='group_norm002':candidate=args
        if args.get('stage_id')!=stage_id:continue
        if op=='qualify_prestart':
            require(stage is not None and candidate is not None and qualified is None,'qualification before original stage or repeated')
            validate_qualification(stage,candidate,args);qualified=dict(args);stage['prestart_recovery']=qualified
        elif op=='start':
            if stage is None:stage={'stage_id':stage_id,'candidate_id':args['candidate_id'],'kind':args['kind'],'plan':args['plan'],'recoveries':0,'attempts':[]}
            else:
                require(stage['candidate_id']==args['candidate_id'] and stage['kind']==args['kind'] and stage['plan']==args['plan'] and len(stage['attempts'])==1,'recovery changes frozen stage identity')
                previous=stage['attempts'][-1]
                if qualified:validate_qualification(stage,candidate,qualified)
                else:require(previous['outcome']=='prestart_failure' and previous['native_started'] is False and type(previous['formal_samples']) is int and previous['formal_samples']==0,'unsupported repeated stage')
                stage['recoveries']+=1
            current={'outcome':None,'native_started':None,'formal_samples':0}
            if qualified:current['prestart_qualification']=qualified['qualification']
            stage['attempts'].append(current)
        elif op=='finish':
            require(stage is not None and stage['attempts'][-1]['outcome'] is None,'finish without matching active recovery stage')
            stage['attempts'][-1].update({k:v for k,v in args.items() if k not in ('workload','stage_id')})
    require(stage is not None,'recovery stage absent');return stage


def task_events(data):
    rows=[];previous=None
    for n,line in enumerate(data.splitlines()):
        row=load(line)
        require(set(row)=={'sequence','recorded_at','kind','previous_hash','value','hash'} and type(row['sequence']) is int and row['sequence']==n,'task recovery event shape differs')
        encoded=(json.dumps({k:v for k,v in row.items() if k!='hash'},ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
        require(row['previous_hash']==previous and row['hash']==sha(encoded),'task recovery prefix hash differs')
        previous=row['hash'];rows.append(row)
    return rows


def resolve_result(stage_dir,stage_record,read_bytes=Path.read_bytes,*,require_success=False,qualification_only=False):
    """Return effective immutable result and every fixed recovery dependency."""
    stage_dir=path(str(stage_dir));protected={}
    def read(p):return read_bytes(Path(p))
    def ref(p):return {'path':str(p),'sha256':sha(read(p))}
    def checked(p):
        pointer(p);b=read(p['path']);require(sha(b)==p['sha256'],'recovery bound evidence changed: '+p['path']);protected[p['path']]=p;return b
    original=ref(stage_dir/'result.json');old=load(read(original['path']))
    args=stage_record.get('prestart_recovery')
    if args is None:
        if require_success:require(old.get('status')=='passed' and old.get('error') is None,'stage is not terminal passed')
        return {'current_result':original,'original_failed_result':None,'qualification':None,'protected':[],'event_bindings':[]}
    task=stage_dir.parents[3];run=task.parents[2]
    require(task.name=='group_norm' and stage_dir==task/'candidates/group_norm002/stages/final','unsupported recovery result scope')
    cert_ref=args['qualification'];require(cert_ref['path']==str(stage_dir/'prestart-recovery/qualification.json'),'qualification path differs')
    cert=load(checked(cert_ref));require(set(cert)==CERTIFICATE and cert['version']==VERSION,'unknown recovery certificate schema')
    require(cert['arguments']=={k:v for k,v in args.items() if k!='qualification'} and cert['authorizes']=='one_same_stage_attempt_no_budget_reset','recovery certificate/event differ')
    candidate={'candidate_id':'group_norm002','source_hash':args['source_hash']};validate_qualification(stage_record,candidate,args)
    require(original==args['failed_result'] and cert['failure']==old.get('error')==FAILURE and old.get('status')=='failed' and old.get('native_started') is False,'not the exact known pre-native import failure')
    require(cert['native_started'] is False and type(cert['formal_samples']) is int and cert['formal_samples']==0 and zero_costs(cert['actual_costs']) and cert['actual_costs']==old.get('actual_costs')==stage_record['attempts'][0]['actual_costs'],'certificate costs differ or are not strict zero')
    checked(original)
    require(cert['stage_plan']==ref(stage_dir/'stage-plan.json'),'original stage plan pointer differs')
    plan=load(checked(cert['stage_plan']));require(plan==stage_record['plan'] and digest(plan)==args['plan_hash'],'frozen recovery plan differs')
    require(cert['stage_files_before']==sorted([original,cert['stage_plan']],key=lambda r:r['path']),'original two-file stage inventory differs')
    final_ref=cert['finalization_request'];require(final_ref['path']==str(task/'finalization/request.json'),'foreign final request')
    final=load(checked(final_ref));require(final['operator']=='group_norm' and final['case_ids']==list(range(1,21)) and 'group_norm002' in final['evaluation_candidate_ids'] and load(checked(final['final_plans']['group_norm002']))==plan,'recovery changes final request/plan')
    preserved=load(checked(cert['preservation']))
    require(set(preserved)=={'version','status','stage','error','files','request','stage_directory_inventory','native_processes_started','role_samples','observed_process_exit_code','recovery_executed','original_stage_and_ledger_preserved','source_attempt_count_unchanged','recorded_at','invocation_environment_correction'}
            and preserved['version']=='level2_zero_native_failure_preservation_v1' and preserved['status']=='infrastructure_blocked'
            and preserved['stage']==args['stage_id'] and preserved['error']==FAILURE and preserved['request']==final_ref
            and preserved['stage_directory_inventory']==['result.json','stage-plan.json']
            and type(preserved['native_processes_started']) is int and preserved['native_processes_started']==0
            and type(preserved['role_samples']) is int and preserved['role_samples']==0
            and type(preserved['observed_process_exit_code']) is int and preserved['observed_process_exit_code']==1
            and preserved['recovery_executed'] is False and preserved['original_stage_and_ledger_preserved'] is True
            and preserved['source_attempt_count_unchanged'] is True,'preserved failure contract differs')
    retained_dir=path(cert['preservation']['path']).parent
    require(retained_dir==run/'storage/maintenance/group-norm002-final-zero-native-022-20261006','preservation namespace differs')
    expected_kept={'stage-result.json':original['path'],'stage-plan.json':cert['stage_plan']['path'],
      'finalization-request.json':final_ref['path'],'invocation.log':'/tmp/aprof-gn002-final-022-20261006.log',
      'task-events-prefix.jsonl':str(task/'events.jsonl'),'ledger-events-prefix.jsonl':str(run/'validation/ledger/events.jsonl')}
    require(isinstance(preserved['files'],list) and len(preserved['files'])==6,'preserved failure roster differs')
    seen=set()
    for entry in preserved['files']:
        require(set(entry)=={'original','retained'},'unknown preservation entry')
        oldref=pointer(entry['original']);kept=pointer(entry['retained']);name=path(kept['path']).name
        require(name not in seen and path(kept['path']).parent==retained_dir and expected_kept.get(name)==oldref['path'] and kept['sha256']==oldref['sha256'],'preservation pointer correlation differs');seen.add(name)
        data=checked(kept)
        if name.endswith('prefix.jsonl'):require(read(oldref['path']).startswith(data),'preserved original journal prefix changed')
        elif name!='invocation.log':checked(oldref)
    require(seen==set(expected_kept),'preservation roster incomplete')
    for key,name in (('ledger_prefix','ledger-prefix.jsonl'),('task_event_prefix','task-events-prefix.jsonl')):
        require(cert[key]['path']==str(stage_dir/'prestart-recovery'/name),'noncanonical recovery immutable prefix')
        checked(cert[key])
    configs=run/'validation/ledger';config=load(checked(ref(configs/'config.json')));confighash=digest(config)
    require(load(checked(ref(configs/'config.sha256.json')))=={'sha256':confighash},'recovery ledger config identity differs')
    prior=ledger_events(checked(cert['ledger_prefix']),confighash)
    old_projected=project_stage(prior,'group_norm','group_norm002-final')
    require(len(old_projected['attempts'])==1 and old_projected['attempts'][0]['evidence']['result']==original and old_projected.get('prestart_recovery') is None,'preserved prefix is not original failed stage')
    require(any(e['operation']=='register' and e['arguments'].get('candidate_id')=='group_norm002' and e['arguments'].get('source_hash')==args['source_hash'] for e in prior),'recovery source is not registered')
    require(read(configs/'events.jsonl').startswith(checked(cert['ledger_prefix'])) and read(task/'events.jsonl').startswith(checked(cert['task_event_prefix'])),'original journal prefix changed')
    current_rows=ledger_events(read(configs/'events.jsonl'),confighash)
    actual_stage=project_stage(current_rows,'group_norm','group_norm002-final')
    if not qualification_only:
        require(actual_stage.get('prestart_recovery')==args and len(actual_stage['attempts'])==len(stage_record['attempts']),'supplied stage differs from qualified actual ledger')
        for actual,declared in zip(actual_stage['attempts'],stage_record['attempts']):
            require(all(actual.get(k)==declared.get(k) for k in ('outcome','native_started','formal_samples','actual_costs','evidence','prestart_qualification')),'supplied attempt differs from actual ledger')
    old_task_rows=task_events(checked(cert['task_event_prefix']))
    require(any(row['kind']=='stage_completed' and row['value'].get('result')==original for row in old_task_rows),'original failed result missing task event authority')
    task_rows=task_events(read(task/'events.jsonl'));bindings=[]
    if not qualification_only:
        qualified_rows=[row for row in task_rows if row['kind']=='stage_prestart_qualified' and row['value'].get('stage')==args['stage_id']]
        require(len(qualified_rows)==1 and qualified_rows[0]['value']=={'candidate_id':'group_norm002','stage':args['stage_id'],'qualification':cert_ref,'failed_result':original},'explicit task qualification event absent or differs')
        q=qualified_rows[0];bindings.append({'path':str(task/'events.jsonl'),'sequence':q['sequence'],'hash':q['hash']})
        relevant=[row for row in current_rows if row['arguments'].get('workload')=='group_norm' and row['arguments'].get('stage_id')==args['stage_id']]
        tail=relevant[-1];bindings.append({'path':str(configs/'events.jsonl'),'sequence':tail['sequence'],'hash':tail['hash']})
    for key,producer_refs in (('old_engineering',final['producers']),('recovery_engineering',cert['producers'])):
        engref=cert[key];p=path(engref['path']);require(p.parent==run/'bootstrap' and re.fullmatch(r'frozen-engineering-[0-9]{3,}\.json',p.name),'noncanonical recovery engineering')
        eng=load(checked(engref));require(eng.get('version')=='level2_frozen_engineering_v1','invalid recovery engineering')
        require(eng['campaign_manifest']['path']==str(run/'campaign-manifest.json'),'foreign recovery campaign manifest');checked(eng['campaign_manifest'])
        manifests=eng['task_manifests'];require(isinstance(manifests,list) and len({r['path'] for r in manifests})==len(manifests),'duplicate recovery task manifests')
        require(any(r['path']==str(task/'manifest.json') for r in manifests),'recovery engineering misses task manifest')
        for m in manifests:
            require(path(m['path']).is_relative_to(run) and path(m['path']).name=='manifest.json','foreign recovery task manifest');checked(m)
        require(cert['old_engineering']['path']!=cert['recovery_engineering']['path'],'recovery must use distinct engineering snapshot')
        files={r['path']:r for r in eng['files']};require(len(files)==len(eng['files']),'duplicate engineering producer')
        require(isinstance(producer_refs,list) and len({r['path'] for r in producer_refs})==len(producer_refs),'duplicate recovery producers')
        if key=='recovery_engineering':require(REQUIRED_PRODUCERS<={Path(r['path']).name for r in producer_refs},'recovery producer closure missing')
        for r in producer_refs:
            pointer(r);item=files.get(r['path']);require(item is not None and item['sha256']==r['sha256'] and item['snapshot']==str(run/'bootstrap/source-cas'/r['sha256'][7:]),'producer lacks canonical engineering snapshot')
            checked({'path':item['snapshot'],'sha256':r['sha256']})
    if qualification_only:
        return {'current_result':original,'original_failed_result':original,'qualification':cert_ref,'protected':[protected[k] for k in sorted(protected)],'event_bindings':[]}
    attempts=stage_record['attempts'];require(len(attempts)==2 and type(stage_record.get('recoveries')) is int and stage_record['recoveries']==1,'recovery has not completed exactly one extra attempt')
    current=attempts[-1];require(current.get('outcome') is not None,'recovery attempt is still active')
    result_ref=current.get('evidence',{}).get('result');pointer(result_ref);require(result_ref['path']==str(stage_dir/'result.recovery-01.json'),'recovery result path differs')
    result=load(checked(result_ref));require(result.get('stage_id')==stage_record['stage_id'] and result.get('candidate_id')=='group_norm002' and result.get('kind')=='timing' and result.get('status') in ('passed','failed') and (result['status']=='passed')==(current['outcome']=='success'),'recovery result and latest ledger outcome differ')
    require(result.get('native_started') is current.get('native_started') and result.get('actual_costs')==current.get('actual_costs'),'actual recovery costs/lifecycle differ')
    require(type(current.get('formal_samples')) is int and current['formal_samples']>=0 and isinstance(current.get('actual_costs'),dict) and all(type(v) is int and v>=0 for v in current['actual_costs'].values()),'invalid recovered sample/cost types')
    require(result.get('prestart_recovery')=={'qualification':cert_ref,'previous_result':original,'attempt':2} and type(result['prestart_recovery']['attempt']) is int and current['evidence'].get('qualification')==cert_ref,'result lacks explicit attempt/qualification binding')
    if result['status']=='passed':
        expected_samples=len(plan['case_ids'])*6*2*2*30*len(plan['cohorts'])
        require(result.get('error') is None and result['native_started'] is True and current['formal_samples']==expected_samples,'success lacks actual full six-process sample closure')
        costs=current['actual_costs'];expected_processes=6*len(plan['cohorts'])
        require(costs.get('role_samples')==expected_samples and costs.get('native_processes_started')==costs.get('native_processes_completed')==expected_processes,'successful recovery process/sample costs differ from complete roster')
    if require_success:require(result['status']=='passed' and result.get('error') is None and result['native_started'] is True,'recovered stage is not actually successful')
    return {'current_result':result_ref,'original_failed_result':original,'qualification':cert_ref,'protected':[protected[k] for k in sorted(protected)],'event_bindings':bindings}


def resolve_from_reader(stage_dir,read_bytes=Path.read_bytes,*,require_success=False):
    stage_dir=path(str(stage_dir));original={'path':str(stage_dir/'result.json'),'sha256':sha(read_bytes(stage_dir/'result.json'))};value=load(read_bytes(stage_dir/'result.json'))
    if value.get('status')=='passed':return {'current_result':original,'original_failed_result':None,'qualification':None,'protected':[],'event_bindings':[]}
    if stage_dir.name!='final' or stage_dir.parent.name!='stages' or stage_dir.parent.parent.name!='group_norm002':
        if require_success:require(False,'stage is not terminal passed')
        return {'current_result':original,'original_failed_result':None,'qualification':None,'protected':[],'event_bindings':[]}
    task=stage_dir.parents[3];run=task.parents[2];ledger=run/'validation/ledger'
    config=load(read_bytes(ledger/'config.json'));rows=ledger_events(read_bytes(ledger/'events.jsonl'),digest(config));stage=project_stage(rows,'group_norm','group_norm002-final')
    proof=resolve_result(stage_dir,stage,read_bytes,require_success=require_success)
    return proof


def validate_certificate(stage_dir,stage,candidate,args,read_bytes=Path.read_bytes):
    validate_qualification(stage,candidate,args)
    return resolve_result(stage_dir,{**stage,'prestart_recovery':args},read_bytes,qualification_only=True)


def frozen_request_producers(task, frozen_request, task_state, current_producers, read_bytes=Path.read_bytes):
    """Retain the original request only under the explicit reviewed recovery.

    This authorizes replay of the old finalization plan, never an altered source,
    final plan, or producer snapshot. No old executable is loaded.
    """
    if frozen_request['producers']==current_producers:return current_producers
    task=path(str(task));stage=task/'candidates/group_norm002/stages/final'
    record=task_state['stages'].get('group_norm002-final')
    require(record is not None and record.get('prestart_recovery') is not None,'producer drift requires explicit certified final recovery')
    args=record['prestart_recovery'];proof=validate_certificate(stage,record,task_state['candidates']['group_norm002'],args,read_bytes)
    certificate=load(read_bytes(path(args['qualification']['path'])))
    require(certificate['finalization_request']=={'path':str(task/'finalization/request.json'),'sha256':sha(read_bytes(task/'finalization/request.json'))}
            and load(read_bytes(task/'finalization/request.json'))==frozen_request,'recovery does not bind exact original final request')
    require([p['path'] for p in current_producers]==[p['path'] for p in frozen_request['producers']],'final request producer roles changed')
    engineering=load(read_bytes(path(certificate['recovery_engineering']['path'])))
    files={p['path']:p for p in engineering['files']};run=task.parents[2]
    for producer in current_producers:
        pointer(producer);entry=files.get(producer['path'])
        require(entry is not None and entry['sha256']==producer['sha256']
                and entry['snapshot']==str(run/'bootstrap/source-cas'/producer['sha256'][7:])
                and sha(read_bytes(path(entry['snapshot'])))==producer['sha256']
                and sha(read_bytes(path(producer['path'])))==producer['sha256'],'current final producer lacks exact recovery engineering binding')
    # Revalidate the qualified journal projection, including the public task event,
    # while permitting the one approved attempt to be pending or unfinished.
    ledger=run/'validation/ledger';config=load(read_bytes(ledger/'config.json'))
    projected=project_stage(ledger_events(read_bytes(ledger/'events.jsonl'),digest(config)),'group_norm','group_norm002-final')
    require(projected.get('prestart_recovery')==args,'recovery qualification absent from actual ledger')
    matches=[r for r in task_events(read_bytes(task/'events.jsonl')) if r['kind']=='stage_prestart_qualified' and r['value'].get('stage')=='group_norm002-final']
    require(len(matches)==1 and matches[0]['value']=={'candidate_id':'group_norm002','stage':'group_norm002-final','qualification':args['qualification'],'failed_result':args['failed_result']},'public final recovery qualification missing')
    return frozen_request['producers']
