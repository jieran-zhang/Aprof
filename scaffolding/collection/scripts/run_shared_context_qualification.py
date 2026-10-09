#!/usr/bin/env python3
"""Explicit qualification wrapper v2: preserve failures and charge observed work."""
import argparse
import json
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from cannbench_shared_context import prepare,save,load,sha,verify_directory
from feedback_hardware import run_process
from shared_context_campaign import Ledger,WORKLOADS
import shared_context_wrapper_evidence as evidence
ROOT=Path(__file__).resolve().parents[3]


def run(run_dir,operator,cases):
    if operator not in (*WORKLOADS,'foreach_norm'):raise ValueError('unknown qualification workload')
    cases=evidence.cases_checked(cases);run_dir=Path(run_dir).resolve();method=operator=='foreach_norm'
    task=run_dir/('method' if method else 'tasks')/operator;out=task/'qualification'
    if out.exists():raise FileExistsError('Existing qualification is evidence; no implicit rerun: '+str(out))
    started=time.time();ledger=None;stage_started=False;error=None;report=None
    producer_refs=evidence.producers([__file__,evidence.__file__,ROOT/'scaffolding/collection/scripts/cannbench_shared_context.py',ROOT/'scaffolding/collection/scripts/feedback_hardware.py',*[ROOT/'scaffolding/collection/scripts'/name for name in ('shared_context_build.py','shared_context_report.py','cannbench_device_timing.py','run_level1_serial.py','shared_context_memory_plan.py')]])
    stage=operator+'-baseline-qualification'
    try:
        binding=load(task/'baseline-binding.json');build_path=task/'aa-build/build_manifest.json';build=load(build_path)
        if build.get('operator')!=operator:raise ValueError('AA build operator mismatch')
        memory=evidence.memory_preflight(run_dir,task,'baseline',build_path,cases,qualification=True)
        source_binding=evidence.archive_native_binding(binding,build,('A','B'))
        for role in ('A','B'):
            if Path(build['roles'][role]['source_dir']).resolve()!=(task/'baseline').resolve():raise ValueError('AA role does not use declared baseline tree')
        args=SimpleNamespace(output=str(out),build=str(build_path),control_build=None,input_bindings=str(task/'input-bindings.json'),
            environment=str(run_dir/'bootstrap/environment.json'),opdir=str(task/'baseline'),cases=','.join(map(str,cases)),phases='qualification',
            device=0,cpu='8',comparison_id=operator+'-aa-qualification',attempt_id='baseline-method',run_id=run_dir.name,comparison_kind='original',qualification_report=None)
        prepare(args)
        save(out/'source-native-bindings.json',source_binding)
        save(out/'memory-plan-binding.json',memory)
        snapshots=evidence.snapshot_producers(out,producer_refs)
        plan=dict(case_ids=cases,control_type='aa',source_hash=binding['sha256'],manifest_ref=sha(out/'manifest.json'),
            producer_version=evidence.VERSION,memory_preflight=memory,producers=snapshots,build_ref=sha(build_path),source_binding_ref=sha(out/'source-native-bindings.json'))
        save(out/'wrapper-started.json',dict(started_at=started,producer_version=evidence.VERSION,plan=plan))
        ledger=None if method else Ledger(run_dir/'ledger')
        if ledger:
            if stage in ledger.state['tasks'][operator]['stages']:raise ValueError('existing ledger stage cannot be implicitly re-executed')
            ledger.start_stage(event_id=stage+'-start',workload=operator,candidate_id=None,stage_id=stage,kind='qualification',plan=plan);stage_started=True
        evidence.verify_refs(producer_refs)
        evidence.verify_refs(memory['frozen_files'])
        run_process([sys.executable,ROOT/'scaffolding/collection/scripts/cannbench_shared_context.py','collect','--output',out],ROOT,task/'qualification-execution',timeout=21600)
        if not (out/'report.json').exists():raise ValueError('successful collect command did not produce a report')
        verify_directory(out);report=load(out/'report.json')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)}
    # Cost extraction is tolerant of truncated rows; invalid evidence never becomes success.
    costs,cost_errors=evidence.qualification_costs(out)
    costs['wall_seconds']=int(time.time()-started)
    if cost_errors and error is None:error={'type':'InvalidRawEvidence','message':'raw qualification evidence is incomplete or malformed'}
    status='execution_failed' if error else 'passed' if report['measurement_quality']['observed_checks_pass'] else 'quality_failed'
    failures=report['measurement_quality']['failures'] if report else []
    paths=[out/'manifest.json',out/'wrapper-started.json',out/'memory-plan-binding.json',out/'source-native-bindings.json',task/'qualification-execution/execution.json',out/'collection-completion.json',out/'report.json']
    refs=evidence.evidence_hashes(paths,cost_errors)
    result=dict(operator=operator,stage='baseline_method_qualification',status=status,started_at=started,ended_at=time.time(),
        formal_samples=costs['event_samples'],successful_sessions=costs['native_sessions_completed'],cases=cases,error=error,failures=failures,evidence=dict(refs),
        actual_costs=costs,cost_errors=cost_errors,cost_scope='observed lower bounds; partial failed calls and unreadable records remain unresolved',
        producer_version=evidence.VERSION,producers=producer_refs,ledger_stage_started=stage_started,candidate_attempts_created=0,production_gate='not_evaluated',
        next_action='baseline profile and candidate experiment' if status=='passed' else 'preserve evidence; do not retry stability failures or compare candidates under failed qualification')
    task.mkdir(parents=True,exist_ok=True)
    result_path=task/'qualification-result.json'
    if result_path.exists():result_path=task/f'qualification-preflight-result-{time.time_ns()}.json'
    save(result_path,result);refs[str(result_path)]=sha(result_path)
    if stage_started:
        try:ledger.finish_stage(event_id=stage+'-finish',workload=operator,stage_id=stage,
            outcome='failed' if error else 'success' if status=='passed' else 'quality_failed',formal_samples=costs['event_samples'],evidence=refs,
            reason=None if status=='passed' else json.dumps(error or failures),actual_costs=costs)
        except BaseException as exc:
            save(out/'ledger-finish-error.json',dict(type=type(exc).__name__,message=str(exc),stage_id=stage,producer_version=evidence.VERSION));raise
    print(json.dumps(result),flush=True);return result


if __name__=='__main__':
    evidence.install_termination_handler()
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run',required=True);parser.add_argument('--operator',required=True)
    parser.add_argument('--cases',default=','.join(map(str,range(1,21))))
    args=parser.parse_args();result=run(args.run,args.operator,[int(x) for x in args.cases.split(',')]);sys.exit(2 if result['status']=='execution_failed' else 0)
