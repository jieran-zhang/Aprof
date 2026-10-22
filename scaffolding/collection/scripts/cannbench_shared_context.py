#!/usr/bin/env python3
"""Host-exclusive shared-context supervisor. Explicit collect is the only device action.

Prepare freezes the plan and file identities. Native samples remain in their original
journal; normalized sessions bind external oracle acknowledgements. Verify only reads.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import signal
import socket
import subprocess
import sys
import threading
import time

from level2_adapters import reusable_verifier as ReusedVerifier
from level2_adapters import dispatch_command as command_from_metadata, verification_metadata, OPERATORS as LEVEL2_OPERATORS, launch_contract
from run_level1_serial import exclusive_host, health
import shared_context_report as stats

ROOT = Path(__file__).resolve().parents[3]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(8*1024*1024), b''): h.update(data)
    return 'sha256:' + h.hexdigest()


def save(path, value, *, replace=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    data = stats.canonical(value)
    if not replace:
        with path.open('xb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
    else:
        tmp = path.with_suffix(path.suffix+'.tmp')
        with tmp.open('wb') as f: f.write(data); f.flush(); os.fsync(f.fileno())
        tmp.replace(path)


def load(path): return stats.strict_load(path)


def strict_line(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result:raise ValueError('duplicate journal JSON key: '+key)
            result[key]=value
        return result
    value=json.loads(text,object_pairs_hook=pairs)
    stats.finite(value)
    return value


def count_launches(operator, source, metadata):
    if operator in LEVEL2_OPERATORS: return launch_contract(operator, source, metadata)['launches_per_call']
    if operator == 'foreach_norm': return 2*len(metadata['lengths'])
    if operator != 'foreach_addcdiv_scalar': return 1
    import re
    host = (Path(source)/'op_host'/f'{operator}.asc').read_text()
    match = re.search(r'constexpr uint64_t kChunkElements\s*=\s*([^;]+);', host)
    if not match: raise ValueError('cannot attest actual source chunk expression')
    expr = re.sub(r'(?<=\d)(?:ULL|UL|LL|U|L)\b', '', match[1])
    tree = ast.parse(expr, mode='eval')
    allowed = (ast.Expression,ast.Constant,ast.BinOp,ast.Mult,ast.Add,ast.Sub,ast.LShift,ast.RShift,ast.FloorDiv)
    if any(not isinstance(n,allowed) for n in ast.walk(tree)): raise ValueError('unsupported chunk expression')
    chunk = eval(compile(tree,'<attested-source-chunk>','eval'), {'__builtins__':{}}, {})
    if type(chunk) is not int or chunk <= 0: raise ValueError('invalid chunk size')
    return sum((n+chunk-1)//chunk for n in metadata['lengths'])


def identities(build):
    return {r:dict(source_hash='sha256:'+v['source_sha256'],binary_hash='sha256:'+v['binary_sha256'],entry=v['kernel_symbols'])
            for r,v in build['roles'].items()}


def schedule(comparison_id, phases, cases):
    result=[]
    for phase in phases:
        for r in range(1,7):
            loads = (['AB','BA'] if r%2 else ['BA','AB']) if phase=='qualification' else ['AB' if r%2 else 'BA']
            for order in loads:
                buffers = (['normal','swapped'] if r%2 else ['swapped','normal']) if phase=='qualification' else ['swapped' if phase=='reverse' else 'normal']
                shift=(r-1)%len(cases)
                result.append(dict(session_id=f'{comparison_id}-{phase}-{r}-{order}',phase=phase,replicate_id=r,
                    block_id=r if phase=='qualification' else None,load_order=order,buffer_configs=buffers,
                    first_order='AB' if r%2 else 'BA',case_order=cases[shift:]+cases[:shift]))
    return result


def qualification_binding(manifest, input_bindings_hash, report_path=None, frozen=None):
    """Bind prior, fully replayed method qualification to this exact scope.

    This is baseline method qualification, not proof that a candidate's changed
    resource path has no candidate-specific interactions. No hardware is invoked.
    """
    if manifest['stages'] == ['qualification']:
        expected={'status':'qualification_requested','report':None,'input_bindings_hash':input_bindings_hash}
        if report_path or frozen is not None and frozen != expected:
            raise ValueError('qualification collection cannot borrow or alter a qualification binding')
        return expected
    if 'qualification' in manifest['stages']:
        raise ValueError('qualification must finish in a separate group before routine collection')
    if frozen is not None:
        if frozen.get('status') != 'externally_qualified':
            raise ValueError('routine collection lacks a frozen external qualification')
        report_path=frozen.get('report')
    if not report_path:
        raise ValueError('routine collection requires --qualification-report from a completed qualification bundle')
    path=Path(report_path).resolve()
    if path.name != 'report.json':
        raise ValueError('qualification report must be the report.json in its complete evidence bundle')
    directory=path.parent
    qualified=load(directory/'manifest.json')
    if qualified.get('stages') != ['qualification']:
        raise ValueError('external report is not a standalone method qualification')
    report=load(path)
    sessions=load(directory/'sessions.json')
    execution=load(directory/'execution-plan.json')
    bound_at=time.time() if frozen is None else frozen.get('bound_at')
    if not isinstance(bound_at,(int,float)) or isinstance(bound_at,bool) or not math.isfinite(bound_at) or bound_at<=0:
        raise ValueError('invalid qualification binding time')
    binding=dict(status='externally_qualified',report=str(path),input_bindings_hash=input_bindings_hash,
        report_hash=sha(path),manifest_hash=sha(directory/'manifest.json'),sessions_hash=sha(directory/'sessions.json'),
        execution_hash=sha(directory/'execution-plan.json'),bound_at=bound_at,
        scope='baseline_method_only_candidate_resource_changes_require_separate_controls')
    if frozen is not None and binding!=frozen:
        raise ValueError('frozen qualification evidence or binding changed')
    # Replay raw journals and all statistics; a claimed passing boolean is not enough.
    verify_directory(directory)
    quality=report['measurement_quality']
    if not quality['observed_checks_pass'] or not quality['structurally_complete'] or quality['method_qualification']!='evaluated_here':
        raise ValueError('external method qualification did not pass all declared checks')
    for key in ('protocol_version','analysis_version','task_id','hardware','harness_hash'):
        if qualified[key]!=manifest[key]:raise ValueError('qualification scope mismatch: '+key)
    if qualified['identities']!=manifest['control_identities'] or qualified['control_identities']!=manifest['control_identities']:
        raise ValueError('qualification A/A baseline identity mismatch')
    if execution['input_bindings_hash']!=input_bindings_hash or qualified['qualification_scope'].get('input_bindings_hash')!=input_bindings_hash:
        raise ValueError('qualification input binding differs from routine comparison')
    qcases={c['case_id']:c for c in qualified['cases']}
    for case in manifest['cases']:
        qcase=qcases.get(case['case_id'])
        if qcase is None or any(qcase[key]!=case[key] for key in ('attributes','input_hash','oracle_hash')):
            raise ValueError('qualification case/input/oracle scope mismatch: '+case['case_id'])
        if qcase['launches_per_call']['A']!=case['launches_per_call']['A'] or qcase['launches_per_call']['B']!=qcase['launches_per_call']['A']:
            raise ValueError('qualification baseline complete-operator scope mismatch')
    if not sessions or max(s['ended_at'] for s in sessions)>bound_at:
        raise ValueError('qualification was not completed before the routine plan was bound')
    return binding


def prepare(args):
    out=Path(args.output).resolve()
    if out.exists(): raise FileExistsError(out)
    build=load(args.build); control=load(args.control_build or args.build)
    bindings=load(args.input_bindings)
    rows={str(c['case_id']):c for c in bindings['cases']}
    case_ids=args.cases.split(',')
    if len(set(case_ids))!=len(case_ids) or not set(case_ids)<=set(rows): raise ValueError('unknown/duplicate cases')
    phases=args.phases.split(',')
    cases=[]; metadata={}
    for c in case_ids:
        row=rows[c]; raw=json.loads(Path(row['metadata']['path']).read_text())
        if sha(row['metadata']['path']) != row['metadata']['sha256']: raise ValueError('metadata identity changed')
        metadata[c]=row['metadata']['path']
        cases.append(dict(case_id=c,attributes=row['attributes'],input_hash=stats.digest(row['inputs']),
            oracle_hash=stats.digest({'verifier':row['verifier'],'oracle_file':row['oracle_file'],'attributes':row['attributes']}),
            launches_per_call={r:count_launches(build['operator'],v['source_dir'],raw) for r,v in build['roles'].items()}))
    hardware=dict(host=socket.gethostname(),physical_chip=str(args.device),logical_device=0,environment_hash=sha(args.environment))
    manifest=dict(protocol_version=stats.PROTOCOL,analysis_version=stats.ANALYSIS,comparison_id=args.comparison_id,
        run_id=args.run_id,task_id=build['operator'],attempt_id=args.attempt_id,comparison_kind=args.comparison_kind,
        cases=cases,identities=identities(build),control_identities=identities(control),
        harness_hash=stats.digest({'ab':build['harness'],'control':control['harness']}),hardware=hardware,
        qualification_scope={'status':'qualification_requested' if phases==['qualification'] else 'requires_external_qualification',
                             'report':args.qualification_report,'input_bindings_hash':sha(args.input_bindings)},
        seed=0,stages=phases,session_plan=schedule(args.comparison_id,phases,case_ids))
    manifest['qualification_scope']=qualification_binding(manifest,sha(args.input_bindings),args.qualification_report)
    stats.validate_plan(manifest)
    execution=dict(build=str(Path(args.build).resolve()),build_hash=sha(args.build),control_build=str(Path(args.control_build or args.build).resolve()),
        control_build_hash=sha(args.control_build or args.build),metadata=metadata,opdir=str(Path(args.opdir).resolve()),
        verifier_hash=sha(Path(args.opdir)/'scripts/verify_result.py'),physical_device=args.device,cpu=args.cpu,
        input_bindings=str(Path(args.input_bindings).resolve()),input_bindings_hash=sha(args.input_bindings),
        environment=str(Path(args.environment).resolve()),environment_hash=sha(args.environment),
        supervisor_hash=sha(__file__),native_hashes={label:{r:sha(v['binary']) for r,v in b['roles'].items()}
                                              for label,b in [('ab',build),('control',control)]})
    out.mkdir();(out/'supervisor-source.py').write_bytes(Path(__file__).read_bytes())
    execution['supervisor_snapshot']=str(out/'supervisor-source.py')
    save(out/'manifest.json',manifest);save(out/'execution-plan.json',execution)
    return manifest


def normalize(plan, directory, build, execution, argv, exit_code, validations):
    journal=[strict_line(x) for x in (directory/'journal.jsonl').read_text().splitlines()]
    allowed={'process_start','session_start','module','case_start','resources','warmup_complete','sample','output','outputs_verified','session_end'}
    if not journal or any(x.get('type') not in allowed or x.get('session_id')!=plan['session_id'] for x in journal):
        raise ValueError('failed, unknown, or foreign journal event')
    for kind in ('process_start','session_start','session_end'):
        if sum(x['type']==kind for x in journal)!=1:raise ValueError('duplicate or missing native lifecycle event')
    expected_types=['process_start','session_start','module','module']
    for c in plan['case_order']:
        for config in plan['buffer_configs']:
            expected_types+=['case_start','resources','resources','warmup_complete']+['sample']*60+['output','output','outputs_verified']
    expected_types+=['session_end']
    if [x['type'] for x in journal]!=expected_types:raise ValueError('native journal execution sequence mismatch')
    start=next(x for x in journal if x['type']=='session_start')
    end=next(x for x in journal if x['type']=='session_end')
    process=journal[0]
    if process['pid']!=start['pid'] or process['host']!=start['host'] or process['started_at']>start['started_at']:
        raise ValueError('native process identity/start mismatch')
    module_rows=[x for x in journal if x['type']=='module']
    if [x.get('role') for x in module_rows]!=list(plan['load_order']):raise ValueError('duplicate/missing/reordered module')
    modules={x['role']:x for x in journal if x['type']=='module'}
    ids=identities(build)
    for r,entry in ids.items():
        if modules[r]['source_sha256']!=entry['source_hash'][7:] or modules[r]['kernel_symbols']!=entry['entry']:
            raise ValueError('loaded module differs from build identity')
        if Path(modules[r]['path']).resolve()!=Path(build['roles'][r]['binary']).resolve() or modules[r]['operator_name']!=build['operator']:
            raise ValueError('module path/operator differs from frozen build')
        if not modules[r].get('entry_address') or modules[r]['entry_address'] in ('0','0x0','(nil)'):
            raise ValueError('missing module entry address')
    if modules['A']['entry_address']==modules['B']['entry_address']:raise ValueError('module entry collision')
    expected_outputs={(c,u,r) for c in plan['case_order'] for u in plan['buffer_configs'] for r in 'AB'}
    outputs=[x for x in journal if x['type']=='output']
    if len(outputs)!=len(expected_outputs) or {(x['case_id'],x['buffer_config'],x['role']) for x in outputs}!=expected_outputs:
        raise ValueError('native output journal incomplete')
    for x in outputs:
        expected=directory/f"{x['case_id']}_{x['buffer_config']}_{x['role']}.bin"
        if Path(x['path']).resolve()!=expected.resolve():raise ValueError('native output path mismatch')
        if x.get('complete_calls_since_prepare')!=3010 or x.get('validation_scope')!='final_call_of_final_formal_sample' or x.get('validation_status')!='pending_external_oracle':
            raise ValueError('native output coverage differs from protocol')
    if end['exit_code']!=exit_code or exit_code!=0:raise ValueError('unsuccessful native session')
    lifecycle={'session_start','session_end','case_start','warmup_complete','outputs_verified'}
    return dict(session_id=plan['session_id'],pid=start['pid'],host=start['host'],started_at=start['started_at'],ended_at=end['ended_at'],
        context_id=start['context_id'],stream_id=start['stream_id'],exit_code=exit_code,identities=ids,
        samples=[{k:v for k,v in x.items() if k!='type'} for x in journal if x['type']=='sample'],outputs=validations,
        resource_events=[{k:v for k,v in x.items() if k not in ('type','session_id')} for x in journal if x['type']=='resources'],
        lifecycle_events=[x for x in journal if x['type'] in lifecycle],argv=argv,cwd=execution['opdir'],log_hash=sha(directory/'journal.jsonl'))


def execute_session(plan, directory, build, execution, verifier, timeout):
    directory.mkdir()
    rows=[]
    for c in plan['case_order']:
        m=json.loads(Path(execution['metadata'][c]).read_text())
        argv=command_from_metadata(execution['opdir'],m,0,directory/'unused.bin')[1:]
        if any('\t' in v or '\n' in v for v in argv): raise ValueError('unsupported native argument separator')
        rows.append('\t'.join([c,*argv]))
    case_path=directory/'cases.tsv';case_path.write_text('\n'.join(rows)+'\n')
    argv=['taskset','-c',execution['cpu'],build['runner']['path'],'--role-a',build['roles']['A']['binary'],
        '--role-b',build['roles']['B']['binary'],'--cases',str(case_path),'--output-dir',str(directory),
        '--session-id',plan['session_id'],'--device','0','--load-order',plan['load_order'],'--first-order',plan['first_order'],
        '--buffer-configs',','.join(plan['buffer_configs']),'--verify-handshake','yes']
    env=dict(os.environ,ASCEND_RT_VISIBLE_DEVICES=str(execution['physical_device']),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    for k in list(env):
        if k.startswith(('APROF_TIMING','APROF_WARMUP','APROF_REPEAT','APROF_SAMPLES','APROF_CAPTURE')):env.pop(k)
    record=dict(argv=argv,cwd=execution['opdir'],started_at=time.time(),host=socket.gethostname(),phase=plan['phase'])
    save(directory/'started.json',record)
    validations=[]; process=None; error=None; messages=queue.Queue()
    try:
        process=subprocess.Popen(argv,cwd=execution['opdir'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
        def reader():
            for line in process.stdout:messages.put(line)
            messages.put(None)
        threading.Thread(target=reader,daemon=True).start()
        deadline=time.monotonic()+timeout
        with (directory/'stdout.log').open('w') as log:
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('native session deadline exceeded')
                line=messages.get(timeout=remaining)
                if line is None:break
                log.write(line);log.flush()
                try:request=json.loads(line)
                except ValueError:continue
                if request.get('type')!='validation_required':continue
                c=request['case_id'];config=request['buffer_config']
                if c not in plan['case_order'] or config not in plan['buffer_configs']:raise ValueError('unexpected output request')
                for role in 'AB':
                    m=json.loads(Path(execution['metadata'][c]).read_text());m['output']=request['outputs'][role]
                    expected=directory/f'{c}_{config}_{role}.bin'
                    if Path(m['output']).resolve()!=expected.resolve():raise ValueError('output path escape or role mismatch')
                    m=verification_metadata(execution['opdir'],m,expected)
                    local=directory/'validation'/f'{c}-{config}-{role}';local.mkdir(parents=True)
                    mp=local/'metadata.json';mp.write_text(json.dumps(m,allow_nan=True)+'\n')
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('session timeout before output verification')
                    previous_handler=signal.getsignal(signal.SIGALRM)
                    def alarm_handler(signum,frame):raise TimeoutError('output verification deadline exceeded')
                    signal.signal(signal.SIGALRM,alarm_handler);signal.setitimer(signal.ITIMER_REAL,remaining)
                    try:result=verifier.run(mp,cwd=local)
                    finally:signal.setitimer(signal.ITIMER_REAL,0);signal.signal(signal.SIGALRM,previous_handler)
                    (local/'verify.log').write_text(result.stdout)
                    row=dict(case_id=c,buffer_config=config,role=role,passed=result.returncode==0,
                        validation_scope='last_formal_sample_final_output',pair_id=29)
                    validations.append(row)
                    if result.returncode:raise RuntimeError(f'prepared correctness failed {c}/{config}/{role}')
                process.stdin.write('ok\n');process.stdin.flush()
        code=process.wait(timeout=max(.01,min(15,deadline-time.monotonic())))
        if code:raise RuntimeError(f'native runner exited {code}')
    except BaseException as exc:
        error={'type':type(exc).__name__,'message':str(exc)}
        if process is not None and process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
    finally:
        record.update(ended_at=time.time(),exit_code=process.returncode if process else None,error=error)
        save(directory/'completion.json',record);save(directory/'validations.json',validations)
    if error:raise RuntimeError(str(error))
    result=normalize(plan,directory,build,execution,argv,process.returncode,validations)
    save(directory/'normalized.json',result)
    return result


def attest_files(manifest, execution):
    stats.validate_plan(manifest)
    if manifest['hardware']['environment_hash']!=execution['environment_hash'] or manifest['hardware']['physical_chip']!=str(execution['physical_device']):
        raise ValueError('hardware/environment binding mismatch')
    for name in ('build','control_build','input_bindings','environment'):
        if sha(execution[name])!=execution[name+'_hash']:raise ValueError(name+' changed')
    build=load(execution['build']);control=load(execution['control_build'])
    if identities(build)!=manifest['identities'] or identities(control)!=manifest['control_identities']:
        raise ValueError('manifest identities differ from frozen binaries')
    if stats.digest({'ab':build['harness'],'control':control['harness']})!=manifest['harness_hash']:
        raise ValueError('harness identity mismatch')
    from shared_context_build import source_hash
    for label,b in [('ab',build),('control',control)]:
        build_root=Path(execution['build' if label=='ab' else 'control_build']).resolve().parent
        for role,v in b['roles'].items():
            source=Path(v['source_dir']).resolve()
            if source_hash(source)!=v['source_sha256']:raise ValueError('native source identity changed')
            if sha(source/'CMakeLists.txt')!='sha256:'+v['cmake_sha256']:raise ValueError('source CMake identity changed')
            generated=build_root/role
            adapter=generated/'op_host'/f"{b['operator']}.asc"
            if sha(adapter)!='sha256:'+v['adapter_sha256']:raise ValueError('generated adapter identity changed')
            if sha(build_root/f'{role}.harness.patch')!='sha256:'+v['patch_sha256']:raise ValueError('adapter patch identity changed')
            for sub in ('op_kernel','op_host'):
                expected={str(p.relative_to(source/sub)):sha(p) for p in (source/sub).rglob('*') if p.is_file()}
                actual={str(p.relative_to(generated/sub)):sha(p) for p in (generated/sub).rglob('*') if p.is_file()}
                if sub=='op_host':
                    expected.pop(f"{b['operator']}.asc",None);actual.pop(f"{b['operator']}.asc",None)
                if (not expected and sub=='op_kernel') or actual!=expected:
                    raise ValueError('generated '+sub+' differs from frozen source')
            if sha(v['binary'])!=execution['native_hashes'][label][role]:raise ValueError('binary changed')
        if sha(b['runner']['path'])!='sha256:'+b['runner']['sha256']:raise ValueError('runner changed')
    cached={}
    bindings=load(execution['input_bindings'])
    bound={str(x['case_id']):x for x in bindings['cases']}
    for c in manifest['cases']:
        row=bound[c['case_id']]
        if Path(row['verifier']['path']).resolve()!=(Path(execution['opdir'])/'scripts/verify_result.py').resolve():
            raise ValueError('oracle verifier is not the execution verifier')
        if execution['metadata'][c['case_id']]!=row['metadata']['path']:raise ValueError('metadata binding mismatch')
        for item in [row['metadata'],row['verifier'],*row['inputs'].values(),*([row['oracle_file']] if row['oracle_file'] else [])]:
            path=item['path']
            if path not in cached:cached[path]=sha(path)
            if cached[path]!=item['sha256']:raise ValueError('frozen input/oracle changed: '+path)
        m=json.loads(Path(row['metadata']['path']).read_text())
        for key,item in row['inputs'].items():
            if m[key]!=item['path']:raise ValueError('native input path differs from bound input')
        if row['oracle_file'] is not None and m.get('golden')!=row['oracle_file']['path']:
            raise ValueError('native oracle file differs from bound oracle')
        if stats.digest(row['inputs'])!=c['input_hash']:raise ValueError('input digest mismatch')
        if stats.digest({'verifier':row['verifier'],'oracle_file':row['oracle_file'],'attributes':row['attributes']})!=c['oracle_hash']:
            raise ValueError('oracle digest mismatch')
    qualification_binding(manifest,execution['input_bindings_hash'],frozen=manifest['qualification_scope'])
    return build,control


def verify_directory(out):
    out=Path(out).resolve();manifest=load(out/'manifest.json');execution=load(out/'execution-plan.json')
    build,control=attest_files(manifest,execution)
    if execution['supervisor_hash']!=sha(execution['supervisor_snapshot']):raise ValueError('frozen supervisor source changed')
    sessions=load(out/'sessions.json');replayed=[]
    scope=manifest['qualification_scope']
    if scope['status']=='externally_qualified' and any(s['started_at']<scope['bound_at'] for s in sessions):
        raise ValueError('routine native sessions precede the frozen qualification binding')
    for plan in manifest['session_plan']:
        directory=out/plan['session_id'];completed=load(directory/'completion.json')
        b=build if plan['phase']=='ab' else control
        actual=normalize(plan,directory,b,execution,completed['argv'],completed['exit_code'],load(directory/'validations.json'))
        if actual!=load(directory/'normalized.json'):raise ValueError('normalized session differs from native journal')
        replayed.append(actual)
    if sessions!=replayed:raise ValueError('sessions differ from native evidence')
    return stats.verify_report(manifest,sessions,load(out/'report.json'))


def collect(args):
    out=Path(args.output).resolve();manifest=load(out/'manifest.json');execution=load(out/'execution-plan.json')
    if (out/'collection-started.json').exists():raise FileExistsError('do not restart an attempted collection; use an explicitly budgeted new group')
    build,control=attest_files(manifest,execution)
    if execution['supervisor_hash']!=sha(__file__):raise ValueError('supervisor changed after plan freeze')
    if manifest['hardware']['host']!=socket.gethostname():raise ValueError('collection host differs from frozen local host')
    os.environ.update(OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    verifier=ReusedVerifier(Path(execution['opdir'])/'scripts/verify_result.py')
    if verifier.source_hash!=execution['verifier_hash']:raise ValueError('verifier changed')
    sessions=[];error=None
    with exclusive_host():
        health(out/'health-before.json')
        save(out/'collection-started.json',dict(started_at=time.time(),manifest_hash=stats.digest(manifest)))
        try:
            for p in manifest['session_plan']:
                b=build if p['phase']=='ab' else control
                s=execute_session(p,out/p['session_id'],b,execution,verifier,args.timeout)
                sessions.append(s);save(out/'sessions.partial.json',sessions,replace=True)
                print(json.dumps({'session_id':p['session_id'],'completed':len(sessions),'planned':len(manifest['session_plan'])}),flush=True)
            save(out/'sessions.json',sessions)
        except BaseException as exc:error={'type':type(exc).__name__,'message':str(exc)}
        finally:
            health_error=None
            try:health(out/'health-after.json')
            except BaseException as exc:
                health_error={'type':type(exc).__name__,'message':str(exc)}
                if error is None:error=health_error
            finally:save(out/'collection-completion.json',dict(ended_at=time.time(),completed_sessions=len(sessions),error=error,health_error=health_error))
    if error:raise RuntimeError(str(error))
    report=stats.analyze(manifest,sessions);save(out/'report.json',report)
    return report


def main():
    def terminate(signum, frame):raise KeyboardInterrupt('coordinator termination requested')
    signal.signal(signal.SIGTERM,terminate)
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('prepare')
    for flag in ('build','input-bindings','environment','opdir','output','run-id','attempt-id','comparison-id'):q.add_argument('--'+flag,required=True)
    q.add_argument('--control-build');q.add_argument('--qualification-report');q.add_argument('--comparison-kind',choices=['parent','original'],default='original')
    q.add_argument('--cases',default='1,8,14,20');q.add_argument('--phases',default='qualification');q.add_argument('--device',type=int,default=0);q.add_argument('--cpu',default='8')
    q=sub.add_parser('collect');q.add_argument('--output',required=True);q.add_argument('--timeout',type=float,default=7200)
    q=sub.add_parser('verify');q.add_argument('--output',required=True)
    args=p.parse_args()
    if args.command=='prepare':prepare(args)
    elif args.command=='collect':collect(args)
    else:
        verify_directory(args.output)
        print('verified read-only')


if __name__=='__main__':main()
