#!/usr/bin/env python3
"""Prepared one-call pilot for selecting a frozen Level2 repeat schedule.

This is a method/runtime probe, never paired optimization evidence. Inputs and
allocations are outside the interval; each launch includes its required resets.
"""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import time

from cannbench_shared_context_profile import (SOURCE, ABI, run_logged, sha, save,
    read_metadata, save_metadata, protocol, native_command)
from level2_adapters import dispatch_command, verification_metadata, reusable_verifier, launch_contract, input_paths, repeat_for_baseline_us
from run_level1_serial import exclusive_host
from msprof_exploration_safety import health
from shared_context_build import source_hash

VERSION='level2_prepared_pilot_v1'


def instrument(source):
    replacements=[
      ('RTLD_NOW|RTLD_LOCAL','RTLD_NOW|RTLD_LOCAL|RTLD_NODELETE'),
      ('int status=1;unsigned warmups=0,profile_calls=0;', 'int status=1;double pilot_us=0;unsigned warmups=0,profile_calls=0;'),
      ('if(args["--mode"]!="profile"&&args["--mode"]!="correctness")', 'if(args["--mode"]!="pilot")'),
      ('const unsigned warmup_target=args["--mode"]=="profile"?10:0;', 'const unsigned warmup_target=1;'),
      ('const unsigned call_target=args["--mode"]=="profile"?5:1;', 'const unsigned call_target=1;'),
      ('for(unsigned i=0;i<call_target;++i){call(api->launch(state));++profile_calls;}check(aclrtSynchronizeStream(stream));',
       'aclrtEvent start=nullptr,end=nullptr;check(aclrtCreateEvent(&start));check(aclrtCreateEvent(&end));'
       'try{check(aclrtRecordEvent(start,stream));for(unsigned i=0;i<call_target;++i){call(api->launch(state));++profile_calls;}'
       'check(aclrtRecordEvent(end,stream));check(aclrtSynchronizeEvent(end));float ms=0;check(aclrtEventElapsedTime(&ms,start,end));pilot_us=double(ms)*1000;}'
       'catch(...){aclrtDestroyEvent(end);aclrtDestroyEvent(start);throw;}check(aclrtDestroyEvent(end));check(aclrtDestroyEvent(start));'),
      ('shared_context_profile_native_v1','level2_prepared_pilot_native_v1'),
      (r'<<",\"output\":"', r'<<",\"complete_call_us\":"<<std::setprecision(17)<<pilot_us<<",\"output\":"'),
    ]
    for before,after in replacements:
        if source.count(before)!=1:raise ValueError('pilot template changed: '+before)
        source=source.replace(before,after)
    return source


def build_runner(output, ascend_home='/usr/local/Ascend/cann-9.0.0'):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=False)
    original=SOURCE.read_text();generated=instrument(original)
    (out/'original.cpp').write_text(original);(out/'pilot.cpp').write_text(generated);(out/'abi.h').write_bytes(ABI.read_bytes())
    home=Path(ascend_home).resolve();binary=out/'pilot_runner'
    argv=['g++','-std=c++17','-O2',str(out/'pilot.cpp'),'-I'+str(out),'-I'+str(home/'include'),
          '-L'+str(home/'lib64'),'-Wl,-rpath,'+str(home/'lib64'),'-lascendcl','-ldl','-o',str(binary)]
    run_logged(argv,out/'build',dict(os.environ),120)
    result={'version':VERSION,'runner':str(binary),'runner_hash':sha(binary),'source_hash':sha(out/'pilot.cpp'),
            'original_hash':sha(out/'original.cpp'),'abi_hash':sha(out/'abi.h'),'warmup':1,'measured_calls':1}
    save(out/'build.json',result);return result


def collect(role_build, runner_build, input_root, opdir, output, case_ids=range(1,21), device=0, cpu='8', timeout=1800):
    out=Path(output).resolve();opdir=Path(opdir).resolve();input_root=Path(input_root).resolve()
    role_build=Path(role_build).resolve();runner_build=Path(runner_build).resolve()
    build=json.loads(role_build.read_text());runner=json.loads(runner_build.read_text());identity=build['roles']['A']
    if runner['version']!=VERSION or sha(runner['runner'])!=runner['runner_hash']:raise ValueError('pilot runner identity differs')
    if source_hash(Path(identity['source_dir']))!=identity['source_sha256'] or sha(identity['binary'])!='sha256:'+identity['binary_sha256']:
        raise ValueError('pilot source/binary identity differs')
    ids=list(case_ids)
    if not ids or len(set(ids))!=len(ids) or any(type(c)is not int or not 1<=c<=20 for c in ids):raise ValueError('invalid pilot cases')
    env=dict(os.environ,ASCEND_RT_VISIBLE_DEVICES=str(device),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    verifier=reusable_verifier(opdir/'scripts/verify_result.py')
    rows=[];error=None
    with exclusive_host():
        out.mkdir(parents=True,exist_ok=False)
        save(out/'request.json',{'version':VERSION,'role_build':{'path':str(role_build),'sha256':sha(role_build)},
             'runner_build':{'path':str(runner_build),'sha256':sha(runner_build)},'case_ids':ids,'device':device,'cpu':str(cpu),
             'metric':'complete_operator_acl_event_us','purpose':'freeze_repeat_schedule_only','performance_evaluated':False})
        try:
            health(out/'health-before.json')
            for case in ids:
                directory=out/f'case_{case:02d}';directory.mkdir()
                metadata_path=input_root/f'case_{case:02d}'/'metadata.json';metadata=read_metadata(metadata_path)
                bindings={p:sha(p) for p in [str(metadata_path),*input_paths(metadata)]}
                contract=protocol(build,'A',metadata,'correctness');contract['mode']='pilot'
                command=dispatch_command(opdir,metadata,0,directory/'unused.bin')[1:]
                if any('\t' in v or '\n' in v for v in command):raise ValueError('invalid TSV args')
                case_args=directory/'case.tsv';case_args.write_text('\t'.join([str(case),*command])+'\n')
                argv=native_command(runner['runner'],build,'A',contract,case_args,directory)
                run_logged(['taskset','-c',str(cpu),*argv],directory/'native',env,timeout,cwd=opdir)
                native=json.loads((directory/'native.json').read_text())
                expected={'version':'level2_prepared_pilot_native_v1','mode':'pilot','exit_code':0,'warmup_complete_calls':1,
                          'profile_complete_calls':1,'launches_per_call':contract['complete_operator_launches'],
                          'source_sha256':identity['source_sha256'],'stream_destroyed':True,'context_destroyed':True,'finalized':True}
                if any(native.get(k)!=v for k,v in expected.items()):raise ValueError('pilot native contract differs')
                repeat=repeat_for_baseline_us(native['complete_call_us'])
                checked=verification_metadata(opdir,metadata,directory/'output.bin');mp=directory/'metadata.json';save_metadata(mp,checked)
                started=time.time();result=verifier.run(mp,cwd=directory)
                (directory/'verify.stdout.log').write_text(result.stdout)
                save(directory/'verify.execution.json',{'argv':result.args,'exit_code':result.returncode,'started_at':started,'ended_at':time.time(),**({'oracle_relocation':result.oracle_relocation} if hasattr(result,'oracle_relocation') else {})})
                if result.returncode:raise ValueError('pilot output correctness failed')
                if any(sha(p)!=v for p,v in bindings.items()):raise ValueError('pilot inputs changed')
                row={'case_id':case,'complete_call_us':native['complete_call_us'],'recommended_repeat':repeat,
                     'launch_contract':launch_contract(build['operator'],identity['source_dir'],metadata),
                     'correctness':{'passed':True,'output_hash':sha(directory/'output.bin'),'verifier_hash':sha(verifier.path)},
                     'native':{'path':str(directory/'native.json'),'sha256':sha(directory/'native.json')},'inputs':bindings}
                save(directory/'pilot-case.json',row);rows.append(row)
        except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)};raise
        finally:
            try:health(out/'health-after.json')
            except BaseException as exc:
                if error is None:error={'type':type(exc).__name__,'message':str(exc)}
            save(out/'pilot.json',{'version':VERSION,'operator':build['operator'],'status':'failed' if error else 'passed',
                 'error':error,'cases':rows,'performance_evaluated':False,'metric':'complete_operator_acl_event_us',
                 'purpose':'freeze_repeat_schedule_only'})
        if error:raise RuntimeError(str(error))
    return json.loads((out/'pilot.json').read_text())
