#!/usr/bin/env python3
"""Explicit, one-shot GN002 final pre-native import-failure recovery.

Qualification is not execution success. Old failed result, events, frozen request,
plan and charge remain intact. No collector is called by audit/authorize.
"""
from __future__ import annotations

from aprof_layout import skill_lib
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys

sys.dont_write_bytecode = True
VERSION = 'level2_final_prestart_qualification_v1'
OPERATOR = 'group_norm'
CANDIDATE = 'group_norm002'
STAGE = CANDIDATE + '-final'
PRESERVATION_NAME = 'group-norm002-final-zero-native-022-20261006'
PRESERVATION_SHA = 'sha256:7ca0dec037ca73fed4a90662e1d9fb27d78c4b72e8422e2d2b4570d1aaddefd3'
OLD_ENGINEERING_NAME = 'frozen-engineering-022.json'
OLD_ENGINEERING_SHA = 'sha256:072f1209af216e755059d6424d700f5fb1f19e1bab8dd609ff2264cd0bf8ade4'
FAILURE = {'type':'ModuleNotFoundError', 'message':"No module named 'aprof_runtime'"}
REASON = 'Explicit qualification of the retained GN002 final pre-native import failure; owner-reported environment correction, no invented traceback or native evidence.'
PRODUCERS = ('level2_prestart_recovery.py', 'level2_stage_recovery.py',
             'msprof_exploration_campaign.py', 'run_msprof_exploration_stage.py',
             'level2_iteration.py', 'level2_finalize.py')


def require(ok, message):
    if not ok: raise ValueError(message)


def safe(path):
    p = Path(path)
    require(p.is_absolute() and '..' not in p.parts and all(not x.is_symlink() for x in (p,*p.parents)), 'noncanonical recovery path')
    return p


def data(path):
    p=safe(path);require(p.is_file() and p.stat().st_size <= 16*1024*1024,'bounded regular recovery metadata required')
    return p.read_bytes()


def sha(path): return 'sha256:'+hashlib.sha256(data(path)).hexdigest()
def pointer(path): return {'path':str(safe(path)), 'sha256':sha(path)}
def load(path): return json.loads(data(path))
def canonical(value): return (json.dumps(value,sort_keys=True,allow_nan=False,ensure_ascii=False)+'\n').encode()


def check(ref):
    require(isinstance(ref,dict) and set(ref)=={'path','sha256'} and pointer(ref['path'])==ref,'recovery pointer changed')
    return load(ref['path'])


def sync(path):
    fd=os.open(path,os.O_RDONLY|os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def save_bytes(path, value):
    path=safe(path)
    require(not path.exists(),'recovery publication already exists')
    pending=path.with_name('.'+path.name+'.pending-'+os.urandom(8).hex())
    with pending.open('xb') as stream:
        stream.write(value);stream.flush();os.fsync(stream.fileno())
    os.link(pending,path);sync(path.parent);pending.unlink();sync(path.parent)


def save(path, value): save_bytes(path,canonical(value))


def engineering(path, expected, run, *, current):
    path=safe(path)
    require(path.parent==run/'bootstrap' and path.name.startswith('frozen-engineering-') and path.suffix=='.json'
            and sha(path)==expected,'engineering external binding differs')
    value=load(path)
    require(value.get('version')=='level2_frozen_engineering_v1','unknown engineering version')
    check(value['campaign_manifest'])
    require(value['campaign_manifest']['path']==str(run/'campaign-manifest.json'),'foreign campaign manifest')
    for ref in value['task_manifests']:check(ref)
    rows=value['files'];indexed={r['path']:r for r in rows}
    require(len(indexed)==len(rows),'duplicate engineering producer')
    repo=Path(__file__).resolve().parents[3]
    for name,row in indexed.items():
        source=safe(name)
        require(source.is_relative_to(repo) and set(row)=={'path','sha256','snapshot'},'foreign engineering producer')
        snapshot=run/'bootstrap/source-cas'/row['sha256'][7:]
        require(row['snapshot']==str(snapshot) and sha(snapshot)==row['sha256'],'engineering source CAS differs')
        if current:require(sha(source)==row['sha256'],'current producer differs from recovery engineering')
    return indexed


def old_scope(run):
    import msprof_exploration_campaign as campaign
    run=safe(run);repo=Path(__file__).resolve().parents[3]
    require(run.is_relative_to(repo/'.aprof/runs'),'run outside canonical repository')
    task=run/'validation/tasks'/OPERATOR;parent=task/'candidates'/CANDIDATE;stage=parent/'stages/final'
    preservation=run/'storage/maintenance'/PRESERVATION_NAME/'preservation.json'
    require(sha(preservation)==PRESERVATION_SHA,'external preserved failure differs')
    kept=load(preservation)
    require(kept['version']=='level2_zero_native_failure_preservation_v1' and kept['stage']==STAGE
            and kept['error']==FAILURE and kept['native_processes_started']==0 and kept['role_samples']==0
            and kept['observed_process_exit_code']==1 and kept['recovery_executed'] is False
            and kept['stage_directory_inventory']==['result.json','stage-plan.json'],'unknown preserved failure')
    for item in kept['files']:
        require(sha(item['retained']['path'])==item['retained']['sha256']==item['original']['sha256'],'retained old evidence differs')
        original=safe(item['original']['path'])
        if original.name=='events.jsonl':require(data(original).startswith(data(item['retained']['path'])),'original event prefix changed')
        elif Path(item['retained']['path']).name!='invocation.log':
            require(sha(original)==item['original']['sha256'],'original failed evidence changed')
    old_engineering=run/'bootstrap'/OLD_ENGINEERING_NAME
    old=engineering(old_engineering,OLD_ENGINEERING_SHA,run,current=False)
    final_request=task/'finalization/request.json';request=load(final_request)
    require(pointer(final_request)==kept['request'] and request['operator']==OPERATOR
            and request['case_ids']==list(range(1,21)) and CANDIDATE in request['evaluation_candidate_ids'],'original final request differs')
    for ref in request['producers']:
        require(old.get(ref['path'],{}).get('sha256')==ref['sha256'],'original finalizer producer not in old engineering')
    plan=load(stage/'stage-plan.json');failed=load(stage/'result.json')
    require(check(request['final_plans'][CANDIDATE])==plan and plan['purpose']=='final','original final plan differs')
    require(failed['status']=='failed' and failed['kind']=='timing' and failed['stage_id']==STAGE and failed['candidate_id']==CANDIDATE
            and failed['error']==FAILURE and failed['native_started'] is False,'not the retained pre-native failure')
    require(failed['actual_costs'] and all(type(v) is int and v==0 for v in failed['actual_costs'].values()),'nonzero or unknown failure cost')
    ledger=campaign.Campaign(run/'validation/ledger');state=ledger.state['tasks'][OPERATOR]
    record=state['stages'].get(STAGE);candidate=state['candidates'][CANDIDATE]
    require(ledger.state['status']=='active' and not campaign._active(ledger.state) and not ledger.unsealed_checkpoints,'campaign not quiescent')
    require(state['frozen'] and state['final_plans'][CANDIDATE]==plan and record['plan']==plan and record['candidate_id']==CANDIDATE,'frozen stage/source differs')
    first=record['attempts'][0]
    require(first['outcome']=='failed' and first['native_started'] is False and type(first['formal_samples']) is int and first['formal_samples']==0
            and first['evidence']['result']==pointer(stage/'result.json') and first['actual_costs']==failed['actual_costs'],'original ledger failed attempt differs')
    return {'run':run,'task':task,'parent':parent,'stage':stage,'ledger':ledger,'record':record,'candidate':candidate,
            'plan':plan,'failed':failed,'preservation':pointer(preservation),'old_engineering':pointer(old_engineering),
            'finalization_request':pointer(final_request),'directory':stage/'prestart-recovery'}


def qualification_arguments(facts, certificate):
    import msprof_exploration_campaign as campaign
    return {'workload':OPERATOR,'stage_id':STAGE,'source_hash':facts['candidate']['source_hash'],
            'plan_hash':campaign.digest(facts['plan']),'failed_result':pointer(facts['stage']/'result.json'),
            'qualification':pointer(certificate),'reason':REASON}


def audit_new(run, engineering_path, engineering_sha):
    facts=old_scope(run);stage=facts['stage'];record=facts['record']
    require(len(record['attempts'])==1 and record['recoveries']==0 and 'prestart_recovery' not in record,'recovery already qualified or attempted')
    require(sorted(p.name for p in stage.iterdir())==['result.json','stage-plan.json'],'nonempty/partial native stage namespace')
    indexed=engineering(engineering_path,engineering_sha,facts['run'],current=True)
    producers=[]
    for name in PRODUCERS:
        path=Path(__file__).resolve().parent/name
        require(indexed.get(str(path),{}).get('sha256')==sha(path),'recovery producer missing from engineering')
        producers.append(pointer(path))
    facts.update(recovery_engineering=pointer(engineering_path),producers=producers)
    return facts


def authorize(run, engineering_path, engineering_sha, *, writers_closed=False, apply=False):
    require(writers_closed is True,'explicit owner quiescence required')
    facts=audit_new(run,engineering_path,engineering_sha)
    if not apply:return {'status':'eligible_not_authorized','native_started':False,'source_attempt_added':False,'failed_result':pointer(facts['stage']/'result.json')}
    from run_level1_serial import exclusive_host
    with exclusive_host():
        facts=audit_new(run,engineering_path,engineering_sha);directory=facts['directory']
        directory.mkdir();sync(directory.parent)
        ledger_prefix=directory/'ledger-prefix.jsonl';task_prefix=directory/'task-events-prefix.jsonl'
        save_bytes(ledger_prefix,data(facts['ledger'].directory/'events.jsonl'))
        save_bytes(task_prefix,data(facts['task']/'events.jsonl'))
        cert_path=directory/'qualification.json'
        arguments={'workload':OPERATOR,'stage_id':STAGE,'source_hash':facts['candidate']['source_hash'],
                   'plan_hash':__import__('msprof_exploration_campaign').digest(facts['plan']),
                   'failed_result':pointer(facts['stage']/'result.json'),'reason':REASON}
        certificate={'version':VERSION,'arguments':arguments,'stage_plan':pointer(facts['stage']/'stage-plan.json'),
          'finalization_request':facts['finalization_request'],'preservation':facts['preservation'],
          'ledger_prefix':pointer(ledger_prefix),'task_event_prefix':pointer(task_prefix),
          'old_engineering':facts['old_engineering'],'recovery_engineering':facts['recovery_engineering'],
          'producers':facts['producers'],'stage_files_before':[pointer(facts['stage']/n) for n in ('result.json','stage-plan.json')],
          'native_started':False,'formal_samples':0,'actual_costs':facts['failed']['actual_costs'],'failure':FAILURE,
          'authorizes':'one_same_stage_attempt_no_budget_reset'}
        save(cert_path,certificate)
        from level2_stage_recovery import validate_certificate
        args=qualification_arguments(facts,cert_path)
        validate_certificate(facts['stage'],facts['record'],facts['candidate'],args,read_bytes=data)
        engineering(engineering_path,engineering_sha,facts['run'],current=True)
        # Append only after the certificate and immutable prefix copies are durable.
        facts['ledger'].qualify_prestart(event_id=OPERATOR+'-'+STAGE+'-qualify-prestart-01',**args)
        from msprof_exploration_execute import event
        event(facts['task'],'stage_prestart_qualified',{'candidate_id':CANDIDATE,'stage':STAGE,'qualification':pointer(cert_path),'failed_result':args['failed_result']})
        return {'status':'qualified_not_executed','qualification':pointer(cert_path),'native_started':False,'timing_group_charge_added':False}


def execution_audit(run, certificate_path, expected):
    facts=old_scope(run);certificate_path=safe(certificate_path)
    require(certificate_path==facts['directory']/'qualification.json' and sha(certificate_path)==expected,'external recovery certificate differs')
    cert=load(certificate_path);record=facts['record'];args=qualification_arguments(facts,certificate_path)
    require(cert['version']==VERSION and record.get('prestart_recovery')==args and len(record['attempts'])==1 and record['recoveries']==0,'no unused explicit qualification')
    from level2_stage_recovery import validate_certificate
    validate_certificate(facts['stage'],record,facts['candidate'],args,read_bytes=data)
    for key in ('preservation','old_engineering','recovery_engineering','stage_plan','finalization_request'):
        check(cert[key])
    for key in ('ledger_prefix','task_event_prefix'):
        require(pointer(cert[key]['path'])==cert[key],'qualified immutable prefix changed')
    require(cert['arguments']=={k:v for k,v in args.items() if k!='qualification'} and cert['failure']==FAILURE,'qualification certificate identity differs')
    require(data(facts['ledger'].directory/'events.jsonl').startswith(data(cert['ledger_prefix']['path']))
            and data(facts['task']/'events.jsonl').startswith(data(cert['task_event_prefix']['path'])),'qualified history prefix changed')
    rows=data(facts['task']/'events.jsonl').splitlines();previous=None;matches=[]
    for number,line in enumerate(rows):
        row=json.loads(line);body={k:v for k,v in row.items() if k!='hash'}
        require(type(row.get('sequence')) is int and row['sequence']==number and row.get('previous_hash')==previous
                and row.get('hash')=='sha256:'+hashlib.sha256(canonical(body)).hexdigest(),'task recovery event chain differs')
        previous=row['hash']
        if row.get('kind')=='stage_prestart_qualified' and row.get('value',{}).get('stage')==STAGE:matches.append(row['value'])
    require(matches==[{'candidate_id':CANDIDATE,'stage':STAGE,'qualification':args['qualification'],'failed_result':args['failed_result']}],
            'explicit task qualification event absent or differs')
    engineering(cert['recovery_engineering']['path'],cert['recovery_engineering']['sha256'],facts['run'],current=True)
    require(cert['producers']==[pointer(Path(__file__).resolve().parent/name) for name in PRODUCERS],'recovery producer set differs')
    require(sorted(p.name for p in facts['stage'].iterdir())==['prestart-recovery','result.json','stage-plan.json'],'cohort namespace already started')
    require(sorted(p.name for p in facts['directory'].iterdir() if p.name != '.execute.lock')==['ledger-prefix.jsonl','qualification.json','task-events-prefix.jsonl'], 'recovery was already invoked or is partial')
    safe(facts['directory']/'.execute.lock')
    if (facts['directory']/'.execute.lock').exists():
        require((facts['directory']/'.execute.lock').is_file() and (facts['directory']/'.execute.lock').stat().st_size==0,'unsafe execution lock')
    # Correct the Python search path explicitly before any ledger start/native call.
    repo=Path(__file__).resolve().parents[3]
    python_paths=[str(repo/'scaffolding/collection/scripts'),str(skill_lib() / 'runtime/src')]
    require(set(python_paths)<=set(os.environ.get('PYTHONPATH','').split(os.pathsep)),
            'explicit corrected PYTHONPATH must include canonical scripts and src before recovery')
    sys.path[:0]=python_paths
    module=importlib.import_module('aprof_runtime')
    require(Path(module.__file__).resolve().is_relative_to(skill_lib() / 'runtime/src/aprof_runtime'),'noncanonical runtime import')
    facts['qualification']=pointer(certificate_path)
    facts['python_import_paths']=python_paths
    return facts



def check_execution_identity(qualification):
    """Recheck immutable metadata/producers before publishing a native outcome."""
    cert=check(qualification)
    stage=Path(qualification['path']).parents[1];task=stage.parents[3];run=task.parents[2]
    engineering(cert['recovery_engineering']['path'],cert['recovery_engineering']['sha256'],run,current=True)
    for ref in cert['producers']:require(pointer(ref['path'])==ref,'recovery producer changed during execution')
    for ref in cert['stage_files_before']:require(pointer(ref['path'])==ref,'original failed stage changed during execution')
    check(cert['finalization_request'])


def execute(run, certificate_path, expected, *, writers_closed=False):
    require(writers_closed is True,'explicit owner quiescence required')
    from run_msprof_exploration_stage import run_qualified_timing_recovery
    return run_qualified_timing_recovery(run,certificate_path,expected)


def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='action',required=True)
    for action in ('audit','authorize'):
        s=subs.add_parser(action);s.add_argument('--run',type=Path,required=True);s.add_argument('--engineering',type=Path,required=True);s.add_argument('--engineering-sha256',required=True);s.add_argument('--writers-closed',action='store_true')
    s=subs.add_parser('execute');s.add_argument('--run',type=Path,required=True);s.add_argument('--qualification',type=Path,required=True);s.add_argument('--qualification-sha256',required=True);s.add_argument('--writers-closed',action='store_true')
    a=p.parse_args()
    value=(execute(a.run,a.qualification,a.qualification_sha256,writers_closed=a.writers_closed) if a.action=='execute'
           else authorize(a.run,a.engineering,a.engineering_sha256,writers_closed=a.writers_closed,apply=a.action=='authorize'))
    print(json.dumps(value,sort_keys=True))
    if a.action == 'execute' and value.get('status') != 'passed':
        raise SystemExit(1)

if __name__=='__main__':main()
