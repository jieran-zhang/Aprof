#!/usr/bin/env python3
"""Isolated prepared-input ACL-event timing and fail-closed multicase adapter.

No canonical operator is changed. Instrument first, then build the returned tree.
Interactive children allocate/copy inputs once, keeping paired AB/BA samples free
of process startup, file reads, allocation and H2D. Event intervals include all
operator launches and device-visible launch gaps, not pure kernel busy time.
"""
from __future__ import annotations
import argparse
import ast
import contextlib
import fcntl
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import queue
import random
import re
import shutil
import socket
import statistics
import subprocess
import sys
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / 'benchmarks/cannbench/harness'
OPERATORS = ('foreach_norm', 'exp', 'masked_scale', 'foreach_addcdiv_scalar', 'mish', 'sigmoid', 'gelu')
PREFIX = 'APROF_TIMING_JSON:'
SCHEMA_VERSION = '1.0.0'


def dump(value, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    temporary.replace(path)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b''): digest.update(chunk)
    return digest.hexdigest()


def operator_name(opdir):
    names = [name for name in OPERATORS if (Path(opdir)/'op_host'/f'{name}.asc').is_file()]
    if len(names) != 1:
        raise ValueError(f'expected exactly one supported host in {opdir}, found {names}')
    return names[0]


def instrument(source_op, dest_op):
    """Copy a pristine operator and inject harness; reject canonical destinations."""
    source_op, dest_op = Path(source_op).resolve(), Path(dest_op).resolve()
    canonical = (ROOT/'benchmarks/cannbench/operators').resolve()
    if dest_op == canonical or canonical in dest_op.parents or dest_op == source_op or source_op in dest_op.parents:
        raise ValueError('instrumentation requires a separate noncanonical destination')
    if dest_op.exists():
        raise FileExistsError(dest_op)
    name = operator_name(source_op)
    original = (source_op/'op_host'/f'{name}.asc').read_text()
    if 'aprof::Run(' in original or 'aprof_device_timer.h' in original:
        raise ValueError('source is already instrumented; copy this tree for candidates instead')
    shutil.copytree(source_op, dest_op, ignore=shutil.ignore_patterns('build', '.git', '__pycache__', 'PROF_*'))
    target = dest_op/'op_host'/f'{name}.asc'
    shutil.copyfile(HARNESS/'device_timer.h', target.parent/'aprof_device_timer.h')
    source = original.replace('#include "acl/acl.h"', '#include "acl/acl.h"\n#include "aprof_device_timer.h"', 1)
    if name.startswith('foreach_'):
        insertion = '        Check(aclrtCreateStream(&stream), "aclrtCreateStream");\n'
        if source.count(insertion) != 1:
            raise ValueError('unrecognized TensorList stream preparation')
        body = (HARNESS/f'{name}_prepared.inc').read_text()
        if name == 'foreach_addcdiv_scalar':
            chunk = re.search(r'constexpr uint64_t kChunkElements = ([^;]+);', source)
            if not chunk:
                raise ValueError('missing baseline chunk length')
            body = body.replace('@CHUNK_ELEMENTS@', chunk.group(1))
        source = source.replace(insertion, insertion + body, 1)
    else:
        launch = re.compile(r'        ' + name + r'_kernel<<<.*?;\n', re.S)
        matches = list(launch.finditer(source))
        if len(matches) != 1:
            raise ValueError('unrecognized scalar kernel launch')
        body = matches[0].group(0)
        wrapped = f'        aprof::Run(stream, device, "{name}", 1, [&]() {{\n' + body + '        });\n'
        source = source[:matches[0].start()] + wrapped + source[matches[0].end():]
    target.write_text(source)
    import difflib
    patch = ''.join(difflib.unified_diff(original.splitlines(True), source.splitlines(True),
                                        fromfile=f'a/op_host/{name}.asc', tofile=f'b/op_host/{name}.asc'))
    (dest_op/'harness.patch').write_text(patch)
    manifest = {'schema_version':SCHEMA_VERSION, 'operator':name, 'source_host_sha256':hashlib.sha256(original.encode()).hexdigest(),
                'instrumented_host_sha256':sha256(target), 'header_sha256':sha256(target.parent/'aprof_device_timer.h'),
                'harness_patch_sha256':sha256(dest_op/'harness.patch'), 'producer_sha256':sha256(__file__),
                'timing_scope':'complete_operator_device_event_interval', 'template_sha256':None}
    if name.startswith('foreach_'):
        manifest['template_sha256'] = sha256(HARNESS/f'{name}_prepared.inc')
    dump(manifest, dest_op/'harness_manifest.json')
    return manifest


def prepared_commands(opdir, case_id, device, input_root=None):
    """Return prepare/execute/verify argv plus metadata path (never executes)."""
    opdir = Path(opdir).resolve()
    name = operator_name(opdir)
    if not 1 <= int(case_id) <= 20:
        raise ValueError('case id must be 1..20')
    root = Path(input_root).resolve() if input_root else opdir/'build/prepared_cases'
    metadata_path = root/f'case_{int(case_id):02d}'/'metadata.json'
    result = {'operator':name, 'cwd':str(opdir), 'metadata':str(metadata_path),
              'prepare_argv':[sys.executable, str(opdir/'scripts/gen_data.py'), '--case',str(case_id), '--output',str(root)],
              'verify_argv':[sys.executable,str(opdir/'scripts/verify_result.py'),'--metadata',str(metadata_path)], 'argv':None}
    if metadata_path.exists():
        result['argv'] = command_from_metadata(opdir, json.loads(metadata_path.read_text()), device)
    return result


def command_from_metadata(opdir, metadata, device, output=None):
    opdir = Path(opdir).resolve()
    name = operator_name(opdir)
    fields = {
        'exp': ('numel','dtype','input','base','scale','shift'),
        'mish': ('numel','dtype','input'), 'sigmoid': ('numel','dtype','input'),
        'gelu': ('numel','dtype','approximate','input'),
        'masked_scale': ('numel','x_dtype','mask_dtype','x','mask','scale'),
        'foreach_norm': ('lengths','dtype','scalar','input'),
        'foreach_addcdiv_scalar': ('lengths','dtype','scalar','x1','x2','x3'),
    }[name]
    argv = [str(opdir/'build'/name)]
    for field in fields:
        value = metadata[field]
        if field == 'lengths': value = ','.join(map(str,value))
        argv += ['--'+field.replace('_','-'), str(value)]
    return argv + ['--output',str(output or metadata['output']),'--device',str(device)]


@contextlib.contextmanager
def device_lock(device, lock_root='/tmp/aprof-device-locks'):
    """Host-local advisory lock shared by all cooperating hardware jobs."""
    root = Path(lock_root); root.mkdir(parents=True,exist_ok=True)
    with (root/f'device-{int(device)}.lock').open('a+') as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        try: yield
        finally: fcntl.flock(stream,fcntl.LOCK_UN)


class TimingChild:
    def __init__(self, argv, cwd, env, log_path, timeout=180):
        self.argv = argv; self.timeout=timeout; self.rows=queue.Queue()
        self.log = Path(log_path).open('w')
        self.process = subprocess.Popen(argv,cwd=cwd,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT,text=True,bufsize=1)
        def reader():
            try:
                for line in self.process.stdout:
                    self.log.write(line); self.log.flush(); self.rows.put(line.strip())
            finally: self.rows.put(None)
        self.reader = threading.Thread(target=reader,daemon=True); self.reader.start()
        try: self.read_until('APROF_TIMING_READY')
        except BaseException:
            self.close(abort=True)
            raise
    def read_until(self, prefix):
        deadline=time.monotonic()+self.timeout
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0: raise TimeoutError(f'timing child timeout: {self.argv[0]}')
            try: row=self.rows.get(timeout=remaining)
            except queue.Empty: raise TimeoutError(f'timing child timeout: {self.argv[0]}') from None
            if row is None: raise RuntimeError(f'timing child exited before {prefix}; see {self.log.name}')
            if row.startswith(prefix): return row[len(prefix):]
    def sample(self):
        self.process.stdin.write('sample\n'); self.process.stdin.flush()
        row=json.loads(self.read_until(PREFIX))
        duration=row.get('elapsed_ns')
        if row.get('unit')!='ns' or row.get('source')!='acl_event' or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<=0:
            raise ValueError('invalid ACL-event sample')
        return row
    def close(self, abort=False):
        if self.process.poll() is None:
            if abort: self.process.terminate()
            else:
                self.process.stdin.write('quit\n'); self.process.stdin.flush()
            try: self.process.wait(timeout=30)
            except subprocess.TimeoutExpired: self.process.kill(); self.process.wait()
        self.reader.join(timeout=5); self.log.close()
        if not abort and self.process.returncode != 0:
            raise RuntimeError(f'timing child failed after measurements: {self.process.returncode}')


class ReusedVerifier:
    """Sequential calls to an unchanged, import-safe verifier's complete main()."""
    def __init__(self, path):
        self.path=Path(path).resolve()
        source=self.path.read_bytes()
        self.source_hash='sha256:'+hashlib.sha256(source).hexdigest()
        tree=ast.parse(source,filename=str(self.path))
        main=[]; guards=0
        allowed_imports={'argparse','json','math','pathlib','numpy','torch'}
        for node in tree.body:
            safe=False
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                modules=[alias.name for alias in node.names] if isinstance(node,ast.Import) else [node.module]
                safe=all(name in allowed_imports for name in modules) and not getattr(node,'level',0)
            elif isinstance(node,ast.FunctionDef):
                arguments=[*node.args.posonlyargs,*node.args.args,*node.args.kwonlyargs]
                arguments += [arg for arg in (node.args.vararg,node.args.kwarg) if arg is not None]
                safe=(not node.decorator_list and not node.args.defaults and not node.args.kw_defaults
                      and node.returns is None and not any(isinstance(item,(ast.Global,ast.Nonlocal)) for item in ast.walk(node))
                      and not any(arg.annotation is not None for arg in arguments))
                if node.name=='main':
                    main.append(node)
                    safe &= not (node.args.posonlyargs or node.args.args or node.args.kwonlyargs or node.args.vararg or node.args.kwarg)
            elif isinstance(node,ast.Assign):
                safe=(all(isinstance(target,ast.Name) and target.id.isupper() for target in node.targets)
                      and isinstance(node.value,ast.Constant) and isinstance(node.value.value,(int,float,str,bool,type(None))))
            elif isinstance(node,ast.Expr):
                safe=isinstance(node.value,ast.Constant) and isinstance(node.value.value,str)
            elif isinstance(node,ast.If):
                guard=ast.parse("if __name__ == '__main__': main()").body[0]
                safe=ast.dump(node,include_attributes=False)==ast.dump(guard,include_attributes=False)
                guards+=int(safe)
            if not safe:
                raise ValueError(f'verifier reuse is not applicable to top-level {type(node).__name__}: {self.path}')
        if len(main)!=1 or guards!=1:
            raise ValueError(f'verifier reuse requires exactly one zero-argument main and standard main guard: {self.path}')
        spec=importlib.util.spec_from_file_location('_aprof_verifier_'+self.source_hash.split(':')[1],self.path)
        self.module=importlib.util.module_from_spec(spec)
        # Execute the exact source bytes without importlib's bytecode-cache
        # writes beside the immutable baseline. The main guard stays false.
        exec(compile(source,str(self.path),'exec'),self.module.__dict__)

    def run(self, metadata_path, *, cwd=None):
        if 'sha256:'+sha256(self.path)!=self.source_hash:
            raise ValueError('verifier source changed after preload')
        argv=[str(self.path),'--metadata',str(metadata_path)]
        previous_argv=sys.argv
        output=io.StringIO()
        returncode=0
        try:
            sys.argv=argv
            with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output), (contextlib.chdir(cwd) if cwd is not None else contextlib.nullcontext()):
                try:
                    self.module.main()
                except SystemExit as error:
                    if error.code is None: returncode=0
                    elif isinstance(error.code,int): returncode=error.code
                    else:
                        print(error.code,file=sys.stderr); returncode=1
                except Exception:
                    traceback.print_exc(); returncode=1
        finally:
            sys.argv=previous_argv
        return subprocess.CompletedProcess([sys.executable,*argv],returncode,stdout=output.getvalue())


def collect_pair_suite(baseline, candidate, cases, device, output_dir, pairs=30, warmup=10, repeat=100,
                       input_root=None, lock_root='/tmp/aprof-device-locks', timeout=180, external_lock=False,
                       precondition_samples=0, reverse_startup=False, checkpoint_every_pair=True,reuse_verifier=False,
                       capture_replay=False, single_live_context=False):
    if type(precondition_samples) is not int or precondition_samples < 0:
        raise ValueError('precondition_samples must be a nonnegative integer')
    if type(reverse_startup) is not bool or type(checkpoint_every_pair) is not bool:
        raise ValueError('startup/checkpoint controls must be booleans')
    if type(reuse_verifier) is not bool: raise ValueError('reuse_verifier must be a boolean')
    if type(capture_replay) is not bool: raise ValueError('capture_replay must be a boolean')
    if type(single_live_context) is not bool: raise ValueError('single_live_context must be a boolean')
    extended_protocol = precondition_samples != 0 or reverse_startup or not checkpoint_every_pair or single_live_context
    baseline,candidate=Path(baseline).resolve(),Path(candidate).resolve()
    cases=list(cases)
    if not cases or len(set(cases))!=len(cases): raise ValueError('cases must be nonempty and unique')
    if pairs<30 or warmup<0 or repeat<1: raise ValueError('require >=30 pairs, warmup>=0, repeat>=1')
    if operator_name(baseline)!=operator_name(candidate): raise ValueError('operator mismatch')
    out=Path(output_dir).resolve(); out.mkdir(parents=True,exist_ok=True)
    if (out/'raw_measurements.json').exists(): raise FileExistsError(out/'raw_measurements.json')
    data_root=Path(input_root).resolve() if input_root else out/'inputs'
    records=[]
    raw={'schema_version':SCHEMA_VERSION,'operator':operator_name(baseline),'host':socket.gethostname(),
         'device':int(device),'unit':'ns','source':'acl_event','timing_scope':'complete_operator_device_event_interval',
         'case_ids':cases,'pairs':pairs,'warmup':warmup,'repeat':repeat,'records':records,'complete':False,
         'baseline_executable_sha256':sha256(baseline/'build'/operator_name(baseline)),
         'candidate_executable_sha256':sha256(candidate/'build'/operator_name(candidate)),
         'producer_sha256':sha256(__file__), 'case_executions':[]}
    if extended_protocol:
        raw.update(precondition_samples=precondition_samples, reverse_startup=reverse_startup,
                   checkpoint_every_pair=checkpoint_every_pair)
    if single_live_context:
        raw.update(single_live_context=True,context_lifecycle='one_process_per_role_sample',
                   verification_output_scope='last_process_output_per_role')
    if capture_replay:
        raw.update(capture_replay=True,execution_mode='acl_graph_replay',captured_operator_calls=repeat,
                   timing_scope='complete_operator_device_graph_event_interval')
    verifier_path=baseline/'scripts/verify_result.py'
    if reuse_verifier:
        raw.update(verification_protocol='in_process_reuse_v1',verifier_source_hash='sha256:'+sha256(verifier_path))
    env=dict(os.environ,APROF_TIMING_INTERACTIVE='1',APROF_WARMUP=str(warmup),APROF_REPEAT=str(repeat))
    if capture_replay: env['APROF_CAPTURE_REPLAY']='1'
    else: env.pop('APROF_CAPTURE_REPLAY',None)
    for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        env[key] = '2'
    lock = contextlib.nullcontext() if external_lock else device_lock(device,lock_root)
    with lock:
        try:
            verifier=None
            if reuse_verifier:
                raw['verifier_preload']={'started_at':time.time()}
                try:
                    verifier=ReusedVerifier(verifier_path)
                    if verifier.source_hash!=raw['verifier_source_hash']:
                        raise ValueError('verifier source changed during preload')
                finally: raw['verifier_preload']['finished_at']=time.time()
            for case_id in cases:
                commands=prepared_commands(baseline,case_id,device,data_root)
                metadata_path=Path(commands['metadata'])
                if not metadata_path.exists():
                    completed=subprocess.run(commands['prepare_argv'],cwd=baseline,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                    (out/f'case-{case_id:02d}-prepare.log').write_text(completed.stdout)
                    completed.check_returncode()
                metadata=json.loads(metadata_path.read_text())
                execution={'case_id':case_id,'metadata_path':str(metadata_path),'metadata_sha256':sha256(metadata_path),
                           'input_hashes':{key:sha256(metadata[key]) for key in ('input','x','mask','x1','x2','x3') if key in metadata},
                           'commands':{}, 'started_at':time.time(), 'finished_at':None, 'exit_status':None}
                raw['case_executions'].append(execution)
                if single_live_context:
                    execution.update(context_lifecycle='one_process_per_role_sample',context_sessions=[])
                    for label,tree in (('baseline',baseline),('candidate',candidate)):
                        execution['commands'][label]={'argv':command_from_metadata(tree,metadata,device,
                            out/f'case-{case_id:02d}-{label}.bin'),'cwd':str(tree)}
                elif extended_protocol: execution['startup_order']=[]
                children={}
                try:
                    startup=[('baseline',baseline),('candidate',candidate)]
                    if reverse_startup: startup.reverse()
                    for label,tree in ([] if single_live_context else startup):
                        argv=command_from_metadata(tree,metadata,device,out/f'case-{case_id:02d}-{label}.bin')
                        execution['commands'][label]={'argv':argv,'cwd':str(tree)}
                        children[label]=TimingChild(argv,tree,env,out/f'case-{case_id:02d}-{label}.log',timeout)
                        if extended_protocol: execution['startup_order'].append(label)
                    # Calibration barrier is outside every device event interval.
                    # Each participant holds its physical device lock throughout.
                    if os.environ.get('APROF_CALIBRATION_BARRIER'):
                        barrier=Path(os.environ['APROF_CALIBRATION_BARRIER'])/str(case_id)
                        barrier.mkdir(parents=True,exist_ok=True)
                        participant=os.environ['APROF_CALIBRATION_PARTICIPANT']
                        (barrier/participant).write_text(str(time.time()))
                        deadline=time.monotonic()+300
                        count=int(os.environ['APROF_CALIBRATION_COUNT'])
                        while len(list(barrier.iterdir()))<count:
                            if time.monotonic()>deadline: raise TimeoutError('calibration participant barrier timed out')
                            time.sleep(.1)
                    for round_id in range(pairs):
                        reverse_order=bool(round_id%2) ^ (single_live_context and reverse_startup)
                        order=('candidate','baseline') if reverse_order else ('baseline','candidate')
                        record={'case_id':case_id,'round':round_id,'order':list(order),'host':raw['host'],'device':int(device),'baseline':None,'candidate':None}
                        if single_live_context: record['context_lifecycle']='one_process_per_role_sample'
                        if extended_protocol:
                            record['preconditioning']={'baseline':[], 'candidate':[]}
                            # Keep each successful native sample even if a later
                            # precondition/formal sample interrupts this pair.
                            records.append(record)
                        for label in order:
                            if single_live_context:
                                command=execution['commands'][label]
                                log_path=out/f'case-{case_id:02d}-round-{round_id:03d}-{label}.log'
                                session={'round':round_id,'label':label,**command,'log_path':str(log_path),
                                         'started_at':time.time(),'finished_at':None,
                                         'started_monotonic_ns':time.monotonic_ns(),'finished_monotonic_ns':None,
                                         'exit_status':None,'pid':None,'preconditioning_sample_indices':[],
                                         'formal_sample_index':None}
                                execution['context_sessions'].append(session)
                                child=None
                                try:
                                    child=TimingChild(command['argv'],command['cwd'],env,log_path,timeout)
                                    session['pid']=child.process.pid
                                    for _ in range(precondition_samples):
                                        sample=child.sample()
                                        record['preconditioning'][label].append(sample)
                                        session['preconditioning_sample_indices'].append(sample.get('sample_index'))
                                    record[label]=child.sample()
                                    session['formal_sample_index']=record[label].get('sample_index')
                                    # close waits for the native process to exit;
                                    # no next role/context starts before this returns.
                                    child.close()
                                except BaseException as error:
                                    session['error']={'type':type(error).__name__,'message':str(error)}
                                    if child is not None and not child.log.closed: child.close(abort=True)
                                    raise
                                finally:
                                    if child is not None: session['exit_status']=child.process.returncode
                                    session.update(finished_at=time.time(),finished_monotonic_ns=time.monotonic_ns())
                            else:
                                for _ in range(precondition_samples):
                                    record['preconditioning'][label].append(children[label].sample())
                                record[label]=children[label].sample()
                        if not extended_protocol: records.append(record)
                        if checkpoint_every_pair: dump(raw,out/'raw_measurements.json')
                except BaseException:
                    for child in children.values(): child.close(abort=True)
                    raise
                else:
                    try:
                        for child in children.values(): child.close()
                    except BaseException:
                        for child in children.values():
                            if not child.log.closed: child.close(abort=True)
                        raise
                # Verify each prepared path as well, independently of legacy correctness.
                for label in ('baseline','candidate'):
                    verified_metadata=dict(metadata,output=str(out/f'case-{case_id:02d}-{label}.bin'))
                    # Upstream workload metadata uses NaN/Infinity for intentional special values.
                    mp=out/f'case-{case_id:02d}-{label}-verification'/'metadata.json'
                    mp.parent.mkdir(parents=True,exist_ok=True)
                    mp.write_text(json.dumps(verified_metadata,allow_nan=True))
                    if verifier is not None or single_live_context:
                        verification={'started_at':time.time(),'finished_at':None,'exit_status':None}
                        execution.setdefault('verifications',{})[label]=verification
                    if verifier is not None:
                        check=verifier.run(mp,cwd=out)
                    else:
                        check=subprocess.run([sys.executable,str(verifier_path),'--metadata',str(mp)],
                                             cwd=out,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                    if verifier is not None or single_live_context:
                        verification.update(finished_at=time.time(),exit_status=check.returncode)
                    (out/f'case-{case_id:02d}-{label}-verify.log').write_text(check.stdout)
                    check.check_returncode()
                execution['exit_status']=0; execution['finished_at']=time.time()
                if not checkpoint_every_pair: dump(raw,out/'raw_measurements.json')
            raw['complete']=True
        except BaseException as error:
            raw['error']={'type':type(error).__name__,'message':str(error)}
            raise
        finally: dump(raw,out/'raw_measurements.json')
    report=summarize_multicase(raw,cases)
    dump(report,out/'measurement_report.json')
    return report


def _cv(samples):
    return statistics.stdev(samples)/statistics.fmean(samples) if len(samples)>1 else 0.0


def _geomean(values):
    return math.exp(statistics.fmean(math.log(x) for x in values))


def _capture_sample_matches(sample, capture_replay, repeat):
    if not isinstance(sample,dict): return False
    if not capture_replay:
        return not any(field in sample for field in ('execution_mode','captured_operator_calls'))
    return (sample.get('execution_mode')=='acl_graph_replay'
            and type(sample.get('captured_operator_calls')) is int
            and sample['captured_operator_calls']==repeat)


def _single_context_reasons(raw, expected, precondition_samples):
    """Validate recorded process lifetimes without reading files or changing evidence."""
    reasons=[]
    lifecycle='one_process_per_role_sample'
    if (raw.get('context_lifecycle')!=lifecycle
            or raw.get('verification_output_scope')!='last_process_output_per_role'):
        reasons.append('invalid single-context lifecycle/output scope')
    pairs=raw.get('pairs')
    if type(pairs) is not int or pairs<30:
        reasons.append('invalid single-context pair count');pairs=0
    executions=raw.get('case_executions')
    if not isinstance(executions,list) or [entry.get('case_id') if isinstance(entry,dict) else None for entry in executions]!=expected:
        return reasons+['single-context case executions differ from expected cases']
    previous_end=previous_monotonic_end=None
    logs=set()
    def number(value):
        return type(value) in (int,float) and math.isfinite(value)
    for case,execution in zip(expected,executions):
        prefix=f'case {case}: '
        if execution.get('context_lifecycle')!=lifecycle or 'startup_order' in execution:
            reasons.append(prefix+'invalid single-context lifecycle/startup evidence')
        if type(execution.get('exit_status')) is not int or execution['exit_status']!=0:
            reasons.append(prefix+'single-context case did not exit successfully')
        commands=execution.get('commands')
        if not isinstance(commands,dict) or set(commands)!={'baseline','candidate'}:
            reasons.append(prefix+'missing single-context commands');commands={}
        sessions=execution.get('context_sessions')
        if not isinstance(sessions,list):
            reasons.append(prefix+'missing context sessions');sessions=[]
        if len(sessions)!=2*pairs:
            reasons.append(prefix+'incomplete context sessions')
        for position,session in enumerate(sessions):
            if not isinstance(session,dict):
                reasons.append(prefix+'invalid context session');continue
            round_id=position//2
            reversed_order=bool(round_id%2) ^ (raw.get('reverse_startup') is True)
            order=('candidate','baseline') if reversed_order else ('baseline','candidate')
            label=order[position%2]
            if type(session.get('round')) is not int or session['round']!=round_id or session.get('label')!=label:
                reasons.append(prefix+'context session order/round mismatch')
            command=commands.get(label)
            if (not isinstance(command,dict) or not isinstance(command.get('argv'),list) or not command['argv']
                    or not all(isinstance(arg,str) and arg for arg in command['argv'])
                    or not isinstance(command.get('cwd'),str) or not Path(command['cwd']).is_absolute()
                    or session.get('argv')!=command['argv'] or session.get('cwd')!=command['cwd']):
                reasons.append(prefix+'context session command mismatch')
            log=session.get('log_path')
            if (not isinstance(log,str) or not Path(log).is_absolute()
                    or Path(log).name!=f'case-{case:02d}-round-{round_id:03d}-{label}.log' or log in logs):
                reasons.append(prefix+'context session log missing/duplicate/mismatched')
            if isinstance(log,str): logs.add(log)
            if (type(session.get('pid')) is not int or session['pid']<=0
                    or type(session.get('exit_status')) is not int or session['exit_status']!=0 or 'error' in session):
                reasons.append(prefix+'context session missing successful process exit')
            start,end=session.get('started_at'),session.get('finished_at')
            mono_start,mono_end=session.get('started_monotonic_ns'),session.get('finished_monotonic_ns')
            if not (number(start) and number(end) and start<=end):
                reasons.append(prefix+'invalid context session timestamps')
            else:
                if previous_end is not None and start<previous_end:
                    reasons.append(prefix+'overlapping context session timestamps')
                previous_end=end
                if (not number(execution.get('started_at')) or not number(execution.get('finished_at'))
                        or start<execution['started_at'] or end>execution['finished_at']):
                    reasons.append(prefix+'context session outside case interval')
            if not (type(mono_start) is int and type(mono_end) is int and 0<=mono_start<=mono_end):
                reasons.append(prefix+'invalid context session monotonic timestamps')
            else:
                if previous_monotonic_end is not None and mono_start<previous_monotonic_end:
                    reasons.append(prefix+'overlapping context session monotonic timestamps')
                previous_monotonic_end=mono_end
            indices=session.get('preconditioning_sample_indices')
            if (not isinstance(indices,list) or not all(type(index) is int for index in indices)
                    or indices!=list(range(precondition_samples))
                    or type(session.get('formal_sample_index')) is not int
                    or session['formal_sample_index']!=precondition_samples):
                reasons.append(prefix+'context session native sample indices mismatch')
        verifications=execution.get('verifications')
        if not isinstance(verifications,dict) or set(verifications)!={'baseline','candidate'}:
            reasons.append(prefix+'missing final per-role output verification')
        else:
            for check in verifications.values():
                if (not isinstance(check,dict) or type(check.get('exit_status')) is not int or check['exit_status']!=0
                        or not number(check.get('started_at')) or not number(check.get('finished_at'))
                        or check['started_at']>check['finished_at']
                        or previous_end is None or check['started_at']<previous_end
                        or not number(execution.get('finished_at')) or check['finished_at']>execution['finished_at']):
                    reasons.append(prefix+'invalid final per-role output verification')
    return reasons


def summarize_multicase(raw, expected_cases=None, min_pairs=30, max_cv=.05, seed=0):
    """Keep raw samples; never expose unstable/incomplete arrays to the v1 gate."""
    expected=list(expected_cases or range(1,21))
    if len(set(expected))!=len(expected) or not expected: raise ValueError('invalid expected cases')
    if min_pairs <30 or max_cv > .05 or max_cv <=0: raise ValueError('production measurement floors cannot be weakened')
    reasons=[]; indexed={case:{} for case in expected}
    if raw.get('unit')!='ns' or raw.get('source')!='acl_event': reasons.append('invalid measurement unit or source')
    if not raw.get('complete'): reasons.append('measurement collection incomplete')
    if raw.get('case_ids')!=expected: reasons.append('declared case set differs from expected cases')
    capture_replay=raw.get('capture_replay') is True
    if any(field in raw for field in ('capture_replay','execution_mode','captured_operator_calls')):
        if (not capture_replay or raw.get('execution_mode')!='acl_graph_replay'
                or type(raw.get('captured_operator_calls')) is not int
                or type(raw.get('repeat')) is not int or raw['repeat']<1
                or raw['captured_operator_calls']!=raw['repeat']
                or raw.get('timing_scope')!='complete_operator_device_graph_event_interval'):
            reasons.append('invalid graph capture/replay protocol')
    elif raw.get('timing_scope')=='complete_operator_device_graph_event_interval':
        reasons.append('undeclared graph capture/replay protocol')
    protocol_fields=('precondition_samples','reverse_startup','checkpoint_every_pair')
    single_live_context=raw.get('single_live_context') is True
    if 'single_live_context' in raw and not single_live_context:
        reasons.append('invalid single-live-context protocol flag')
    lifecycle_executions=raw.get('case_executions')
    if not isinstance(lifecycle_executions,list): lifecycle_executions=[]
    if not single_live_context and (any(field in raw for field in ('context_lifecycle','verification_output_scope'))
            or any(isinstance(entry,dict) and ('context_sessions' in entry or 'context_lifecycle' in entry)
                   for entry in lifecycle_executions)):
        reasons.append('undeclared single-context lifecycle evidence')
    extended_protocol=single_live_context or any(field in raw for field in protocol_fields)
    precondition_samples=raw.get('precondition_samples',0)
    if extended_protocol:
        if (not all(field in raw for field in protocol_fields)
                or type(precondition_samples) is not int or precondition_samples < 0
                or type(raw.get('reverse_startup')) is not bool
                or type(raw.get('checkpoint_every_pair')) is not bool):
            reasons.append('invalid sampling protocol configuration')
            precondition_samples=0
        if (type(raw.get('warmup')) is not int or raw['warmup'] < 0
                or type(raw.get('repeat')) is not int or raw['repeat'] < 1):
            reasons.append('invalid sampling protocol warmup/repeat')
        startup=['candidate','baseline'] if raw.get('reverse_startup') is True else ['baseline','candidate']
        executions=raw.get('case_executions',[])
        if not isinstance(executions,list): executions=[]
        for case in ([] if single_live_context else expected):
            entries=[entry for entry in executions if isinstance(entry,dict) and entry.get('case_id')==case]
            if len(entries)!=1 or entries[0].get('startup_order')!=startup:
                reasons.append(f'case {case}: missing or mismatched startup order')
    if single_live_context:
        reasons.extend(_single_context_reasons(raw,expected,precondition_samples))
    for row in raw.get('records',[]):
        case=row.get('case_id'); round_id=row.get('round')
        if case not in indexed: reasons.append(f'unexpected case {case}'); continue
        if not isinstance(round_id,int) or round_id<0 or round_id in indexed[case]: reasons.append(f'case {case}: duplicate/invalid round'); continue
        reversed_order=bool(round_id%2) ^ (single_live_context and raw.get('reverse_startup') is True)
        desired=['candidate','baseline'] if reversed_order else ['baseline','candidate']
        if row.get('order')!=desired: reasons.append(f'case {case}: invalid AB/BA order')
        valid=True
        if single_live_context:
            if (row.get('context_lifecycle')!='one_process_per_role_sample'
                    or type(round_id) is not int or type(row.get('device')) is not int
                    or row['device']!=raw.get('device') or row.get('host')!=raw.get('host')):
                reasons.append(f'case {case}: invalid single-context record identity');valid=False
        elif 'context_lifecycle' in row:
            reasons.append(f'case {case}: undeclared context lifecycle');valid=False
        index_base=0 if single_live_context else round_id*(1+precondition_samples)
        preconditioning=row.get('preconditioning')
        if extended_protocol:
            if not isinstance(preconditioning,dict) or set(preconditioning)!={'baseline','candidate'}:
                reasons.append(f'case {case}: missing or invalid preconditioning evidence'); valid=False
                preconditioning={}
            for label in ('baseline','candidate'):
                samples=preconditioning.get(label)
                if not isinstance(samples,list) or len(samples)!=precondition_samples:
                    reasons.append(f'case {case}: incomplete {label} preconditioning evidence'); valid=False
                    continue
                for offset,sample in enumerate(samples):
                    value=sample.get('elapsed_ns') if isinstance(sample,dict) else None
                    good=(isinstance(sample,dict) and sample.get('unit')=='ns' and sample.get('source')=='acl_event'
                          and isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>0
                          and type(sample.get('device')) is int
                          and sample.get('device')==row.get('device',raw.get('device'))
                          and ('operator' not in raw or sample.get('operator')==raw['operator'])
                          and _capture_sample_matches(sample,capture_replay,raw.get('repeat'))
                          and type(sample.get('sample_index')) is int
                          and sample['sample_index']==index_base+offset
                          and all(field in raw and type(sample.get(field)) is int and sample[field]==raw[field]
                                  for field in ('warmup','repeat')))
                    if not good:
                        reasons.append(f'case {case}: invalid {label} preconditioning sample'); valid=False
        elif preconditioning is not None:
            reasons.append(f'case {case}: undeclared preconditioning evidence'); valid=False
        for label in ('baseline','candidate'):
            sample=row.get(label) or {}; value=sample.get('elapsed_ns')
            if not _capture_sample_matches(sample,capture_replay,raw.get('repeat')):
                reasons.append(f'case {case}: mismatched {label} execution mode/captured calls'); valid=False
            if sample.get('unit')!='ns' or sample.get('source')!='acl_event' or not isinstance(value,(float,int)) or isinstance(value,bool) or not math.isfinite(value) or value<=0:
                reasons.append(f'case {case}: invalid {label} sample'); valid=False
            if sample.get('device')!=row.get('device',raw.get('device')): reasons.append(f'case {case}: mismatched device'); valid=False
            if extended_protocol and (type(sample.get('device')) is not int
                    or ('operator' in raw and sample.get('operator')!=raw['operator'])):
                reasons.append(f'case {case}: invalid sample identity'); valid=False
            for field in ('warmup','repeat'):
                if field in raw and (sample.get(field)!=raw[field]
                        or (extended_protocol and type(sample.get(field)) is not int)):
                    reasons.append(f'case {case}: mismatched {field}'); valid=False
            expected_index=index_base+precondition_samples
            if ((extended_protocol and type(sample.get('sample_index')) is not int)
                    or ('sample_index' in sample and sample['sample_index']!=expected_index)):
                reasons.append(f'case {case}: mismatched sample index'); valid=False
        if valid: indexed[case][round_id]=row
    per_case=[]; shared_count=None
    for case in expected:
        rows=indexed[case]; indices=sorted(rows)
        if indices!=list(range(len(rows))) or len(rows)<min_pairs: reasons.append(f'case {case}: missing paired samples')
        if single_live_context and len(rows)!=raw.get('pairs'):
            reasons.append(f'case {case}: single-context declared pair count mismatch')
        if shared_count is None: shared_count=len(rows)
        if len(rows)!=shared_count: reasons.append(f'case {case}: unequal round count')
        a=[rows[i]['baseline']['elapsed_ns'] for i in indices]; b=[rows[i]['candidate']['elapsed_ns'] for i in indices]
        cv_a,cv_b=(_cv(a),_cv(b)) if a else (None,None)
        if a and max(cv_a,cv_b)>max_cv: reasons.append(f'case {case}: CV exceeds {max_cv}')
        per_case.append({'case_id':case,'pair_count':len(rows),'baseline_samples_ns':a,'candidate_samples_ns':b,
                         'baseline_cv':cv_a,'candidate_cv':cv_b,'baseline_median_ns':statistics.median(a) if a else None,
                         'candidate_median_ns':statistics.median(b) if b else None,
                         'regression':_geomean([y/x for x,y in zip(a,b)])-1 if a else None,
                         'speedup':_geomean([x/y for x,y in zip(a,b)]) if a else None})
    stable=not reasons; suite_a=[]; suite_b=[]
    if stable:
        for i in range(shared_count):
            suite_a.append(_geomean([indexed[c][i]['baseline']['elapsed_ns'] for c in expected]))
            suite_b.append(_geomean([indexed[c][i]['candidate']['elapsed_ns'] for c in expected]))
        if max(_cv(suite_a),_cv(suite_b))>max_cv: reasons.append('suite CV exceeds threshold'); stable=False
    speedup=lcb=None
    if stable:
        logs=[math.log(a/b) for a,b in zip(suite_a,suite_b)]; generator=random.Random(seed)
        bootstrap=sorted(statistics.fmean(logs[generator.randrange(len(logs))] for _ in logs) for _ in range(2000))
        speedup=math.exp(statistics.fmean(logs)); lcb=math.exp(bootstrap[int(.05*len(bootstrap))])
    max_regression=max((x['regression'] for x in per_case if x['regression'] is not None),default=None)
    report={'schema_version':SCHEMA_VERSION,'unit':'ns','aggregation':'equal_case_geometric_mean_per_round',
            'case_ids':expected,'stable':stable,'reasons':sorted(set(reasons)),'per_case':per_case,
            'speedup':speedup,'speedup_lcb_95':lcb,'max_case_regression':max_regression,
            'performance_eligible':bool(stable and lcb>=1.03 and max_regression<=.03),
            'gate_projection':{'baseline_samples_ns':suite_a if stable else [],'candidate_samples_ns':suite_b if stable else [],
                               'heldout_regressions':[x['regression'] for x in per_case if x['regression'] is not None]}}
    if capture_replay:
        count=raw.get('repeat') if type(raw.get('repeat')) is int and raw['repeat']>=1 else None
        report.update(execution_mode='acl_graph_replay',captured_operator_calls=count,
                      timing_scope='complete_operator_device_graph_event_interval')
    if single_live_context:
        report.update(single_live_context=True,context_lifecycle='one_process_per_role_sample',
                      verification_output_scope='last_process_output_per_role')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('instrument'); q.add_argument('--source',required=True); q.add_argument('--dest',required=True)
    q=sub.add_parser('prepare'); q.add_argument('--opdir',required=True); q.add_argument('--case',type=int,required=True); q.add_argument('--device',type=int,default=0); q.add_argument('--input-root'); q.add_argument('--execute',action='store_true')
    q=sub.add_parser('measure'); q.add_argument('--baseline',required=True); q.add_argument('--candidate',required=True); q.add_argument('--cases',default=','.join(map(str,range(1,21)))); q.add_argument('--device',type=int,required=True); q.add_argument('--output',required=True); q.add_argument('--input-root'); q.add_argument('--pairs',type=int,default=30); q.add_argument('--warmup',type=int,default=10); q.add_argument('--repeat',type=int,default=100); q.add_argument('--lock-root',default='/tmp/aprof-device-locks'); q.add_argument('--external-lock',action='store_true',help='caller holds physical-device lock for entire measurement')
    q.add_argument('--precondition-samples',type=int,default=0,help='native samples before each role formal sample; retain every sample as evidence')
    q.add_argument('--reverse-startup',action='store_true',help='create candidate first in persistent mode; start with BA in single-live-context mode')
    q.add_argument('--case-checkpoints-only',action='store_true',help='checkpoint after each verified case and on failure instead of after each pair')
    q.add_argument('--reuse-verifier',action='store_true',help='preload the unchanged import-safe verifier once, then fully verify every output after timing children exit')
    q.add_argument('--capture-replay',action='store_true',help='measure a replay of repeat complete operator calls captured by the compatible device timer')
    q.add_argument('--single-live-context',action='store_true',help='start and fully exit one process per role sample, alternating AB/BA; retain every process session')
    q=sub.add_parser('report'); q.add_argument('--raw',required=True); q.add_argument('--output',required=True); q.add_argument('--cases',default=','.join(map(str,range(1,21))))
    args=p.parse_args()
    if args.command=='instrument': result=instrument(args.source,args.dest)
    elif args.command=='prepare':
        result=prepared_commands(args.opdir,args.case,args.device,args.input_root)
        if args.execute:
            subprocess.run(result['prepare_argv'],cwd=result['cwd'],check=True)
            result=prepared_commands(args.opdir,args.case,args.device,args.input_root)
    elif args.command=='measure': result=collect_pair_suite(args.baseline,args.candidate,[int(c) for c in args.cases.split(',')],args.device,args.output,args.pairs,args.warmup,args.repeat,args.input_root,args.lock_root,external_lock=args.external_lock,
        precondition_samples=args.precondition_samples,reverse_startup=args.reverse_startup,checkpoint_every_pair=not args.case_checkpoints_only,reuse_verifier=args.reuse_verifier,capture_replay=args.capture_replay,single_live_context=args.single_live_context)
    else:
        result=summarize_multicase(json.loads(Path(args.raw).read_text()),[int(c) for c in args.cases.split(',')]); dump(result,args.output)
    print(json.dumps(result,sort_keys=True,allow_nan=False))

if __name__=='__main__': main()
