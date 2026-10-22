#!/usr/bin/env python3
"""Explicit diagnostic wrapper v2: one charged stage, bound source and producers."""
import argparse
import json
import sys
import time
from pathlib import Path
from cannbench_shared_context import load,save,sha
from feedback_hardware import run_process
from shared_context_campaign import Ledger,WORKLOADS
import shared_context_wrapper_evidence as evidence
ROOT=Path(__file__).resolve().parents[3]


def run(args):
    if args.operator not in WORKLOADS or args.stage not in ('profile','correctness'):raise ValueError('unknown diagnostic workload/stage')
    evidence.safe_token(args.candidate);evidence.safe_token(args.group)
    cases=evidence.cases_checked([int(x) for x in args.cases.split(',')])
    if args.stage=='correctness' and cases!=list(range(1,21)):raise ValueError('correctness requires all 20 cases')
    run_dir=Path(args.run).resolve();task=run_dir/'tasks'/args.operator;ledger=Ledger(run_dir/'ledger')
    cid=None if args.candidate=='baseline' else args.candidate;candidate=task if cid is None else task/'candidates'/cid
    build_path=task/'aa-build/build_manifest.json' if cid is None else candidate/'ab-build/build_manifest.json'
    role='A' if cid is None else 'B';stage_id=args.candidate+'-'+args.stage+'-'+args.group;out=candidate/(args.stage+'-'+args.group)
    if out.exists():raise FileExistsError(out)
    producer_refs=evidence.producers([__file__,evidence.__file__,ROOT/'scaffolding/collection/scripts/cannbench_shared_context_profile.py',ROOT/'scaffolding/collection/scripts/cannbench_shared_context.py',ROOT/'scaffolding/collection/scripts/feedback_hardware.py',*[ROOT/'scaffolding/collection/scripts'/name for name in ('shared_context_build.py','shared_context_report.py','cannbench_device_timing.py','run_level1_serial.py','shared_context_memory_plan.py')]])
    started=time.time();error=None;stage_started=False;plan=None;owned_output=False
    try:
        binding=load(task/'baseline-binding.json') if cid is None else {'path':str(candidate/'source.tar'),'sha256':sha(candidate/'source.tar')}
        build=load(build_path)
        if build.get('operator')!=args.operator:raise ValueError('role build operator mismatch')
        memory=evidence.memory_preflight(run_dir,task,args.candidate,build_path,cases)
        source_binding=evidence.archive_native_binding(binding,build,(role,))
        bindings_path=task/'input-bindings.json';bindings=load(bindings_path)
        metadata,input_refs=evidence.input_refs(bindings,cases,task/'baseline')
        runner_path=run_dir/'tools/diagnostic/profile-build.json';runner=load(runner_path)
        fixed_refs={str(build_path):sha(build_path),str(runner_path):sha(runner_path),str(bindings_path):sha(bindings_path),str(run_dir/'bootstrap/environment.json'):sha(run_dir/'bootstrap/environment.json'),
            runner['runner']:runner['runner_hash'],build['roles'][role]['binary']:'sha256:'+build['roles'][role]['binary_sha256'],**producer_refs,**memory['frozen_files']}
        commands=[]
        common=[sys.executable,ROOT/'scaffolding/collection/scripts/cannbench_shared_context_profile.py',args.stage,'--role-build',build_path,'--runner-build',runner_path,'--role',role,'--opdir',task/'baseline','--device','0','--cpu','8']
        if args.stage=='correctness':
            input_root=Path(metadata[1]).parent.parent
            if any(Path(metadata[c])!=input_root/f'case_{c:02d}/metadata.json' for c in cases):raise ValueError('20-case native input root does not match every bound metadata path')
            commands=[([*common,'--input-root',input_root,'--output',out/'evidence','--cases',args.cases],out/'execution',7200)]
        else:
            commands=[([*common,'--metadata',metadata[c],'--case-id',str(c),'--output',out/f'case_{c:02d}'],out/f'case_{c:02d}-execution',2400) for c in cases]
        plan=dict(source_hash=binding['sha256'],case_ids=cases,runner_build=str(runner_path),role_build=str(build_path),
            frozen_files=fixed_refs,input_refs=input_refs,source_native_binding=source_binding,memory_preflight=memory,producer_version=evidence.VERSION,physical_device=0,logical_device=0,cpu='8',
            commands=[[str(x) for x in command] for command,directory,timeout in commands])
        if args.stage=='profile':plan['capture_window']={'warmup_complete_calls':10,'measured_complete_calls':5,'full_operator':True,'profiler_replay_warmup':10}
        if stage_id in ledger.state['tasks'][args.operator]['stages']:raise ValueError('existing ledger stage cannot be implicitly re-executed')
        # Claim the artifact directory atomically before the idempotent ledger API.
        out.mkdir();owned_output=True
        snapshots=evidence.snapshot_producers(out,producer_refs)
        save(out/'group-started.json',dict(started_at=started,plan=plan,producer_snapshots=snapshots))
        save(out/'source-native-bindings.json',source_binding)
        save(out/'memory-plan-binding.json',memory)
        ledger.start_stage(event_id=stage_id+'-start',workload=args.operator,candidate_id=cid,stage_id=stage_id,kind=args.stage,plan=plan);stage_started=True
        evidence.verify_refs(input_refs)
        for command,directory,timeout in commands:
            evidence.verify_refs(fixed_refs)
            run_process(command,ROOT,directory,timeout=timeout)
            child_out=Path(command[command.index('--output')+1])
            child_completion=load(child_out/'completion.json')
            if child_completion.get('status')!='passed':raise ValueError('diagnostic command lacks a passing child completion')
    except BaseException as exc:
        if isinstance(exc,FileExistsError) and not owned_output:raise
        error={'type':type(exc).__name__,'message':str(exc)}
    costs,completed,cost_errors=evidence.diagnostic_costs(out,args.stage,cases)
    costs['wall_seconds']=int(time.time()-started)
    if error is None and (completed!=cases or cost_errors):error={'type':'IncompleteDiagnosticEvidence','message':'command success did not prove all declared cases'}
    result=dict(status='failed' if error else 'passed',stage=args.stage,candidate_id=cid,case_ids=cases,completed_cases=completed,error=error,
        started_at=started,ended_at=time.time(),performance_evaluated=args.stage=='profile',paired_performance_evaluated=False,
        actual_costs=costs,cost_errors=cost_errors,cost_scope='observed native calls and captured launches; profiler internal replay cost is not inferred',
        producer_version=evidence.VERSION,producers=producer_refs,ledger_stage_started=stage_started)
    if not owned_output:out.mkdir(parents=True,exist_ok=False)
    save(out/'group-result.json',result)
    paths=[out/'group-started.json',out/'group-result.json',out/'memory-plan-binding.json',out/'source-native-bindings.json',*out.rglob('*.execution.json'),*out.rglob('execution.json'),*out.rglob('completion.json'),*out.rglob('profile-summary.json'),*out.rglob('correctness.json')]
    refs=evidence.evidence_hashes(paths,cost_errors)
    if stage_started:
        # Infrastructure/interruption failures must not masquerade as an oracle mismatch.
        oracle_records=[evidence.inspect_json(p,[]) for p in out.rglob('verify.execution.json')]
        oracle_failed=any(r and type(r.get('exit_code')) is int and r['exit_code']>0 for r in oracle_records)
        outcome='correctness_failed' if error and args.stage=='correctness' and oracle_failed else 'failed' if error else 'success'
        try:ledger.finish_stage(event_id=stage_id+'-finish',workload=args.operator,stage_id=stage_id,outcome=outcome,formal_samples=0,
            evidence=refs,reason=json.dumps(error) if error else None,actual_costs=costs)
        except BaseException as exc:
            save(out/'ledger-finish-error.json',dict(type=type(exc).__name__,message=str(exc),stage_id=stage_id,producer_version=evidence.VERSION));raise
    print(json.dumps(result),flush=True);return result


if __name__=='__main__':
    evidence.install_termination_handler();parser=argparse.ArgumentParser(description=__doc__)
    for key in ('run','operator','candidate','group'):parser.add_argument('--'+key,required=True)
    parser.add_argument('--stage',choices=['correctness','profile'],required=True);parser.add_argument('--cases',default=','.join(map(str,range(1,21))))
    args=parser.parse_args();result=run(args);sys.exit(1 if result['status']=='failed' else 0)
