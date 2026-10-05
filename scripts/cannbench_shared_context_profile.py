#!/usr/bin/env python3
"""Independent diagnostic profiling of one prepared shared-context role/case.

Only explicit build/profile subcommands execute tools. Raw profiler CSVs remain
untouched; this evidence is never paired timing or a runtime gate verdict.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import math
import socket
import subprocess
import sys
import time

from level2_adapters import dispatch_command as command_from_metadata, verification_metadata, OPERATORS as LEVEL2_OPERATORS, launch_contract, native_kernel_sequence, verify_build_dispatch
from cannbench_shared_context import count_launches
from run_level1_serial import exclusive_host, health
from shared_context_report import strict_load, canonical
from shared_context_build import source_hash

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'benchmarks/cannbench/harness/shared_context_profile/profile_runner.cpp'
ABI=ROOT/'benchmarks/cannbench/harness/shared_context/abi.h'
VERSION='shared_context_profile_v1'


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):digest.update(data)
    return 'sha256:'+digest.hexdigest()


def save(path,value):
    with Path(path).open('xb') as stream:stream.write(canonical(value))


def read_metadata(path):
    """Legacy oracle input is opaque JSON and may contain NaN/Infinity."""
    value=json.loads(Path(path).read_text())
    if not isinstance(value,dict):raise ValueError('legacy metadata must be an object')
    return value


def save_metadata(path,value):
    # Only the unchanged oracle consumes this file. Contracts stay finite JSON.
    with Path(path).open('x') as stream:stream.write(json.dumps(value,allow_nan=True)+'\n')


def protocol(build,role,metadata,mode="profile"):
    identity=build['roles'][role]
    launches=count_launches(build['operator'],identity['source_dir'],metadata)
    if mode not in ('profile','correctness'):raise ValueError('invalid diagnostic mode')
    if type(launches) is not int or launches<1 or mode=='profile' and launches>100:
        raise ValueError('invalid complete call count or exceeded msprof skip/count limits')
    kernels=identity['kernel_symbols'].split(',')
    if not kernels or len(set(kernels))!=len(kernels) or any(not re.fullmatch(r'[A-Za-z_]\w*',k) for k in kernels):
        raise ValueError('invalid native kernel identities')
    if build['operator'] in LEVEL2_OPERATORS:
        verify_build_dispatch(identity)
        actual=launch_contract(build['operator'],identity['source_dir'],metadata)['kernels']
        per_call={}
        for kernel in native_kernel_sequence(identity,actual):per_call[kernel]=per_call.get(kernel,0)+1
    elif build['operator']=='foreach_norm':
        if len(kernels)!=2 or launches!=2*len(metadata['lengths']):raise ValueError('norm requires both partial and finalize for every member')
        per_call={k:len(metadata['lengths']) for k in kernels}
    else:
        if len(kernels)!=1:raise ValueError('unrecognized complete-operator kernel contract')
        per_call={kernels[0]:launches}
    return dict(version=VERSION,mode=mode,role=role,operator=build['operator'],source_hash='sha256:'+identity['source_sha256'],
        binary_hash='sha256:'+identity['binary_sha256'],kernel_launches_per_complete_call=per_call,
        complete_operator_launches=launches,warmup_complete_calls=10 if mode=='profile' else 0,profile_complete_calls=5 if mode=='profile' else 1,
        profiler_replay_warmup=10 if mode=='profile' else 0,launch_skip_before_match=10*launches if mode=='profile' else 0,launch_count=(5 if mode=='profile' else 1)*launches,
        scope='five complete prepared operator calls after ten complete host warmups' if mode=='profile' else 'one complete prepared correctness call without device timing',gate=False)


def summarize_csv(raw,contract):
    """Count launch records once using OpBasicInfo, never sum metric tables."""
    raw=Path(raw);files=sorted(raw.rglob('*.csv'))
    artifacts=[dict(path=str(p.relative_to(raw)),sha256=sha(p)) for p in files]
    launches=[]
    for path in files:
        if not re.fullmatch(r'opbasicinfo(?:_\d{14,20})?\.csv',path.name.lower()):continue
        with path.open(newline='',encoding='utf-8-sig') as stream:
            reader=csv.DictReader(stream)
            if not reader.fieldnames or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('missing/duplicate CSV header')
            for index,row in enumerate(reader,2):
                if None in row or any(v is None for v in row.values()):raise ValueError('malformed profiler CSV row')
                names={value.strip() for key,value in row.items() if re.sub(r'[ _]','',key).lower() in ('opname','kernelname') and value.strip()}
                path_name=path.parent.parent.name if path.parent.name.isdecimal() and any(p.startswith('OPPROF_') for p in path.parts) else None
                if len(names)>1:raise ValueError('conflicting CSV kernel identities')
                kernel=next(iter(names)) if names else path_name
                if path_name and kernel!=path_name:raise ValueError('CSV/path kernel identity mismatch')
                if kernel not in contract['kernel_launches_per_complete_call']:
                    raise ValueError('unexpected/missing profiled kernel identity: '+str(kernel))
                launches.append(dict(csv=str(path.relative_to(raw)),row=index,kernel=kernel,kernel_identity_source='csv' if names else 'OPPROF_kernel_directory',raw=row))
    expected={k:n*5 for k,n in contract['kernel_launches_per_complete_call'].items()}
    observed={k:sum(row['kernel']==k for row in launches) for k in expected}
    if len(launches)!=contract['launch_count'] or observed!=expected:
        raise ValueError('captured window is not five complete operators: '+json.dumps({'expected':expected,'observed':observed}))
    return dict(version=VERSION,artifacts=artifacts,kernel_launches=launches,expected_kernel_counts=expected,
        observed_kernel_counts=observed,complete_operator_calls=5,launch_count=len(launches),complete=True,gate=False)


def native_command(runner,build,role,contract,case_args,out):
    row=build['roles'][role]
    return [str(runner),'--mode',contract['mode'],'--role-library',row['binary'],'--role',role,'--expected-source',row['source_sha256'],
        '--expected-kernels',row['kernel_symbols'],'--launches-per-call',str(contract['complete_operator_launches']),
        '--case-args',str(case_args),'--output',str(out/'output.bin'),'--journal',str(out/'native.json'),'--device','0']


def msprof_command(runner,build,role,contract,case_args,out):
    if contract['mode']!='profile':raise ValueError('correctness cannot invoke msprof')
    return ['msprof','op','--warm-up=10',f"--launch-skip-before-match={contract['launch_skip_before_match']}",
        f"--launch-count={contract['launch_count']}",'--aic-metrics=Default','--output='+str(out/'raw'),
        *native_command(runner,build,role,contract,case_args,out)]


def run_logged(argv,out,env,timeout,cwd=None):
    """Bound and reap the entire profiler/native process group on failure."""
    started=time.time();error=None;process=None;stdout='';stderr=''
    try:
        if not math.isfinite(timeout) or timeout<=0:raise ValueError('invalid process timeout')
        pending=[]
        handlers={sig:signal.getsignal(sig) for sig in (signal.SIGINT,signal.SIGTERM)}
        try:
            for sig in handlers:signal.signal(sig,lambda signum,frame:pending.append(signum))
            process=subprocess.Popen([str(x) for x in argv],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
        finally:
            for sig,handler in handlers.items():signal.signal(sig,handler)
        if pending:raise KeyboardInterrupt('controller signal during native startup: '+str(pending[0]))
        stdout,stderr=process.communicate(timeout=timeout)
        if process.returncode:raise RuntimeError('command exited '+str(process.returncode))
        return subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)}
        if process is not None:
            previous=signal.pthread_sigmask(signal.SIG_BLOCK,{signal.SIGINT,signal.SIGTERM})
            try:
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:stdout,stderr=process.communicate(timeout=10)
                except subprocess.TimeoutExpired:
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                    stdout,stderr=process.communicate()
            finally:signal.pthread_sigmask(signal.SIG_SETMASK,previous)
        raise
    finally:
        for suffix,value in [('stdout',stdout),('stderr',stderr)]:
            with Path(str(out)+'.'+suffix+'.log').open('xb') as f:f.write(value.encode() if isinstance(value,str) else value)
        save(Path(str(out)+'.execution.json'),dict(argv=[str(x) for x in argv],cwd=str(cwd) if cwd else None,
            host=socket.gethostname(),physical_device=env.get('ASCEND_RT_VISIBLE_DEVICES'),logical_device=0,
            started_at=started,ended_at=time.time(),exit_code=process.returncode if process else None,error=error))


def build_runner(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError(out)
    home=Path(args.ascend_home).resolve()
    with exclusive_host():
        out.mkdir(parents=True)
        (out/'profile_runner.cpp').write_bytes(SOURCE.read_bytes());(out/'abi.h').write_bytes(ABI.read_bytes())
        binary=out/'shared_context_profile_runner'
        command=['g++','-std=c++17','-O2',str(out/'profile_runner.cpp'),'-I'+str(out),'-I'+str(home/'include'),
            '-L'+str(home/'lib64'),'-Wl,-rpath,'+str(home/'lib64'),'-lascendcl','-ldl','-o',str(binary)]
        run_logged(command,out/'build',dict(os.environ),args.timeout)
        manifest=dict(version=VERSION,runner=str(binary),runner_hash=sha(binary),source_hash=sha(out/'profile_runner.cpp'),
            abi_hash=sha(out/'abi.h'),source_snapshot=str(out/'profile_runner.cpp'),abi_snapshot=str(out/'abi.h'),command=command)
        save(out/'profile-build.json',manifest)
    return manifest


def profile(args):
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError(out)
    build=strict_load(args.role_build);runner=strict_load(args.runner_build);metadata=read_metadata(args.metadata)
    contract=protocol(build,args.role,metadata);identity=build['roles'][args.role]
    if source_hash(Path(identity['source_dir']))!=identity['source_sha256'] or sha(identity['binary'])!=contract['binary_hash']:
        raise ValueError('role source/binary differs from build identity')
    if sha(runner['runner'])!=runner['runner_hash'] or sha(runner['source_snapshot'])!=runner['source_hash'] or sha(runner['abi_snapshot'])!=runner['abi_hash']:
        raise ValueError('profiling runner identity changed')
    opdir=Path(args.opdir).resolve();verifier=opdir/'scripts/verify_result.py'
    if not re.fullmatch(r'[A-Za-z0-9_-]+',args.case_id):raise ValueError('invalid case ID')
    if not math.isfinite(args.timeout) or not args.timeout>0:raise ValueError('timeout must be positive')
    command=command_from_metadata(opdir,metadata,0,out/'unused.bin')[1:]
    if any('\t' in str(v) or '\n' in str(v) for v in command):raise ValueError('unsupported case argument separator')
    inputs={k:dict(path=str(Path(v).resolve()),sha256=sha(v)) for k,v in metadata.items()
            if k!='output' and isinstance(v,str) and Path(v).is_file()}
    binding=dict(version=VERSION,case_id=args.case_id,metadata_path=str(Path(args.metadata).resolve()),metadata_hash=sha(args.metadata),
        inputs=inputs,verifier=dict(path=str(verifier),sha256=sha(verifier)),role_build_hash=sha(args.role_build),
        runner_build_hash=sha(args.runner_build),host=socket.gethostname(),physical_device=args.device,logical_device=0,cpu=args.cpu,protocol=contract)
    env=dict(os.environ,ASCEND_RT_VISIBLE_DEVICES=str(args.device),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    for key in list(env):
        if key.startswith(('APROF_TIMING','APROF_WARMUP','APROF_REPEAT','APROF_SAMPLES','APROF_CAPTURE')):env.pop(key)
    error=None
    with exclusive_host():
        out.mkdir(parents=True);save(out/'request.json',binding)
        try:
            health(out/'health-before.json')
            case_args=out/'case.tsv';case_args.write_text('\t'.join([args.case_id,*map(str,command)])+'\n')
            argv=msprof_command(runner['runner'],build,args.role,contract,case_args,out)
            run_logged(['taskset','-c',args.cpu,*argv],out/'profile',env,args.timeout,cwd=opdir)
            native=strict_load(out/'native.json')
            expected={'version':'shared_context_profile_native_v1','host':socket.gethostname(),'physical_device':str(args.device),'logical_device':'0','mode':'profile','exit_code':0,'role':args.role,'source_sha256':identity['source_sha256'],
                'kernel_symbols':identity['kernel_symbols'],'warmup_complete_calls':10,'profile_complete_calls':5,
                'launches_per_call':contract['complete_operator_launches'],'stream_destroyed':True,'context_destroyed':True,'finalized':True,
                'output':str(out/'output.bin'),'validation_scope':'final_call_of_five_profile_iterations'}
            if any(native.get(k)!=v for k,v in expected.items()) or not native.get('context_id') or not native.get('stream_id'):
                raise ValueError('native profile did not complete declared one-context/operator contract')
            checked=verification_metadata(opdir,metadata,out/'output.bin');save_metadata(out/'verification-metadata.json',checked)
            if sha(verifier)!=binding['verifier']['sha256']:raise ValueError('oracle changed during profile')
            run_logged([sys.executable,str(verifier),'--metadata',str(out/'verification-metadata.json')],out/'verify',env,args.timeout,cwd=opdir)
            save(out/'output-validation.json',dict(passed=True,scope='final_call_of_five_profile_iterations',output_hash=sha(out/'output.bin'),verifier_hash=sha(verifier)))
            summary=summarize_csv(out/'raw',contract);save(out/'profile-summary.json',summary)
        except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)};raise
        finally:
            health_error=None
            try:health(out/'health-after.json')
            except BaseException as exc:
                health_error={'type':type(exc).__name__,'message':str(exc)}
                if error is None:error=health_error
            save(out/'completion.json',dict(version=VERSION,status='failed' if error else 'passed',error=error,health_error=health_error,gate=False))
        if error:raise RuntimeError(str(error))
    return summary


def correctness(args):
    """Sequential independent cases; exports correctness only, no device timings."""
    out=Path(args.output).resolve()
    if out.exists():raise FileExistsError(out)
    if not math.isfinite(args.timeout) or args.timeout<=0:raise ValueError('timeout must be finite and positive')
    cases=args.cases.split(',')
    if len(set(cases))!=len(cases) or not cases or any(not re.fullmatch(r'(?:[1-9]|1[0-9]|20)',c) for c in cases):
        raise ValueError('correctness cases must be unique IDs from 1..20')
    build=strict_load(args.role_build);runner=strict_load(args.runner_build);identity=build['roles'][args.role]
    if source_hash(Path(identity['source_dir']))!=identity['source_sha256'] or sha(identity['binary'])!='sha256:'+identity['binary_sha256']:
        raise ValueError('role source/binary differs from frozen build')
    for path,hash_key in [('runner','runner_hash'),('source_snapshot','source_hash'),('abi_snapshot','abi_hash')]:
        if sha(runner[path])!=runner[hash_key]:raise ValueError('diagnostic runner identity changed')
    opdir=Path(args.opdir).resolve();verifier=opdir/'scripts/verify_result.py';verifier_hash=sha(verifier)
    prepared=[]
    for case in cases:
        path=Path(args.input_root).resolve()/f'case_{int(case):02d}'/'metadata.json'
        metadata=read_metadata(path);contract=protocol(build,args.role,metadata,mode='correctness')
        inputs={k:dict(path=str(Path(v).resolve()),sha256=sha(v)) for k,v in metadata.items()
            if k!='output' and isinstance(v,str) and Path(v).is_file()}
        prepared.append((case,path,metadata,contract,inputs))
    env=dict(os.environ,ASCEND_RT_VISIBLE_DEVICES=str(args.device),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    for key in list(env):
        if key.startswith(('APROF_TIMING','APROF_WARMUP','APROF_REPEAT','APROF_SAMPLES','APROF_CAPTURE')):env.pop(key)
    completed=[];error=None
    with exclusive_host():
        out.mkdir(parents=True)
        save(out/'request.json',dict(version=VERSION,mode='correctness',role=args.role,role_build_hash=sha(args.role_build),
            runner_build_hash=sha(args.runner_build),verifier_hash=verifier_hash,host=socket.gethostname(),physical_device=args.device,logical_device=0,cpu=args.cpu,
            cases=[dict(case_id=c,metadata_path=str(p),metadata_hash=sha(p),inputs=i,contract=t) for c,p,m,t,i in prepared],gate=False))
        try:
            health(out/'health-before.json')
            for case,path,metadata,contract,inputs in prepared:
                directory=out/f'case_{int(case):02d}';directory.mkdir()
                output=directory/'output.bin'
                command=command_from_metadata(opdir,metadata,0,output)[1:]
                if any('\t' in str(v) or '\n' in str(v) for v in command):raise ValueError('unsupported native case argument')
                case_args=directory/'case.tsv';case_args.write_text('\t'.join([case,*map(str,command)])+'\n')
                native_argv=native_command(runner['runner'],build,args.role,contract,case_args,directory)
                run_logged(['taskset','-c',args.cpu,*native_argv],directory/'native',env,args.timeout,cwd=opdir)
                native=strict_load(directory/'native.json')
                expected=dict(version='shared_context_profile_native_v1',host=socket.gethostname(),physical_device=str(args.device),logical_device='0',mode='correctness',exit_code=0,role=args.role,source_sha256=identity['source_sha256'],kernel_symbols=identity['kernel_symbols'],
                    warmup_complete_calls=0,profile_complete_calls=1,launches_per_call=contract['complete_operator_launches'],
                    output=str(output),validation_scope='single_complete_correctness_call',stream_destroyed=True,context_destroyed=True,finalized=True)
                if any(native.get(k)!=v for k,v in expected.items()) or not native.get('context_id') or not native.get('stream_id'):
                    raise ValueError('native correctness contract incomplete')
                verification=directory/'verification-metadata.json';save_metadata(verification,verification_metadata(opdir,metadata,output))
                if sha(verifier)!=verifier_hash:raise ValueError('original verifier changed')
                run_logged([sys.executable,str(verifier),'--metadata',str(verification)],directory/'verify',env,args.timeout,cwd=opdir)
                result=dict(case_id=case,passed=True,scope='one complete prepared call, no device timing',output_hash=sha(output),native_hash=sha(directory/'native.json'))
                save(directory/'correctness.json',result);completed.append(result)
        except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)};raise
        finally:
            health_error=None
            try:health(out/'health-after.json')
            except BaseException as exc:
                health_error={'type':type(exc).__name__,'message':str(exc)}
                if error is None:error=health_error
            save(out/'completion.json',dict(version=VERSION,mode='correctness',status='failed' if error else 'passed',completed=completed,
                planned_cases=cases,error=error,health_error=health_error,performance_evaluated=False,gate=False))
        if error:raise RuntimeError(str(error))
    return dict(passed=len(completed),planned=len(cases),performance_evaluated=False,gate=False)


def main():
    def terminate(signum,frame):raise KeyboardInterrupt('controller received SIGTERM')
    signal.signal(signal.SIGTERM,terminate)
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    build=commands.add_parser('build');build.add_argument('--output',required=True);build.add_argument('--ascend-home',default=os.environ.get('ASCEND_HOME_PATH','/usr/local/Ascend/ascend-toolkit/latest'));build.add_argument('--timeout',type=float,default=120)
    collect=commands.add_parser('profile')
    for flag in ('role-build','runner-build','metadata','opdir','case-id','output'):collect.add_argument('--'+flag,required=True)
    collect.add_argument('--role',choices=['A','B'],required=True);collect.add_argument('--device',type=int,default=0);collect.add_argument('--cpu',default='8');collect.add_argument('--timeout',type=float,default=1800)
    check=commands.add_parser('correctness')
    for flag in ('role-build','runner-build','input-root','opdir','output'):check.add_argument('--'+flag,required=True)
    check.add_argument('--cases',default=','.join(map(str,range(1,21))));check.add_argument('--role',choices=['A','B'],required=True)
    check.add_argument('--device',type=int,default=0);check.add_argument('--cpu',default='8');check.add_argument('--timeout',type=float,default=180)
    args=parser.parse_args();result={'build':build_runner,'profile':profile,'correctness':correctness}[args.command](args);print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
