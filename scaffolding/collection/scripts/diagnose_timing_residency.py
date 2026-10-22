#!/usr/bin/env python3
"""Finite, research-only A/A experiments. Preparation never launches a kernel."""
from __future__ import annotations
import argparse
import contextlib
import csv
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import shlex
import signal
import statistics
import subprocess
import sys
import threading
import time

REPO = Path(__file__).resolve().parents[3]
WORKSPACE = REPO.parent
OLD = WORKSPACE / 'validation-graph-base-1.0.0-round2-20261014'
HEADER = REPO / 'scaffolding/benchmarks/cannbench/harness/device_timing_diagnostic.h'
PREFIX = 'APROF_DIAG_JSON:'
ROLES = ('A', 'B')
MODES = ('shared', 'split', 'residency')
FACTORS = ('row_logging', 'buffered')


def read(path): return json.loads(Path(path).read_text())
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024 * 1024), b''): h.update(block)
    return 'sha256:' + h.hexdigest()
def save(path, value):
    path=Path(path);temporary=path.with_name(path.name+'.tmp')
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')
    os.replace(temporary,path)


def cells():
    # Each allocation cycle rotates mode order and reverses logging-factor order.
    return [dict(operator=op, cycle=cycle, mode=MODES[(cycle + offset) % 3], logging=factor)
            for op in ('exp', 'sigmoid') for cycle in range(6) for offset in range(3)
            for factor in (FACTORS if cycle % 2 == 0 else FACTORS[::-1])]


def patch_host(text, op):
    old = f'''aprof::Run(stream, device, "{op}", 1, [&]() {{
        {op}_kernel<<<tiling.blockNum, nullptr, stream>>>(
            static_cast<uint8_t *>(devIn), static_cast<uint8_t *>(devOut), static_cast<uint8_t *>(devTiling));
        }});'''
    new = f'''aprof_diag::Run(stream, device, "{op}", devIn, devOut, devTiling, bytes, sizeof(tiling),
            [&](void *input, void *output, void *params) {{
        {op}_kernel<<<tiling.blockNum, nullptr, stream>>>(
            static_cast<uint8_t *>(input), static_cast<uint8_t *>(output), static_cast<uint8_t *>(params));
        }});'''
    if text.count(old) != 1 or text.count('#include "aprof_device_timer.h"') != 1:
        raise ValueError('unexpected frozen host; refuse heuristic rewriting')
    return text.replace(old, new).replace('#include "aprof_device_timer.h"', '#include "device_timing_diagnostic.h"')


def prepare(destination, cpus):
    from run_aprof_job import run
    destination = destination.resolve(); destination.mkdir(exist_ok=False)
    if not cpus or not set(cpus) <= os.sched_getaffinity(0): raise ValueError('invalid frozen CPU affinity')
    operators = {}
    for op, cid in (('exp', 9), ('sigmoid', 4)):
        original = OLD/op/'baseline'; tree = destination/op/'source'; tree.mkdir(parents=True)
        for name in ('op_host', 'op_kernel', 'scripts'): shutil.copytree(original/name, tree/name)
        shutil.copyfile(original/'CMakeLists.txt', tree/'CMakeLists.txt')
        host = tree/f'op_host/{op}.asc'; host.write_text(patch_host(host.read_text(), op))
        shutil.copyfile(HEADER, tree/'op_host/device_timing_diagnostic.h')
        for p in (original/'op_kernel').iterdir():
            if p.is_file() and sha(p) != sha(tree/'op_kernel'/p.name): raise ValueError('kernel changed')
        for stage, argv in [('configure', ['cmake','-S','.','-B','build','-DCMAKE_BUILD_TYPE=Release']),
                            ('build', ['cmake','--build','build','-j2'])]:
            job = dict(job_id=f'timing-diagnostic-{op}-{stage}',argv=argv,cwd=str(tree),
                       output_dir=str(destination/op/stage),timeout_seconds=600,
                       environment={'PYTHONDONTWRITEBYTECODE':'1'})
            result = run(job)
            if result['exit_code']: raise RuntimeError(f'{op} {stage} failed; logs preserved')
        meta = OLD/op/'prepared'/f'case_{cid:02d}'/'metadata.json'; m = read(meta)
        source = {str(p.relative_to(tree)):sha(p) for p in sorted(tree.rglob('*'))
                  if p.is_file() and 'build' not in p.relative_to(tree).parts and '__pycache__' not in p.parts}
        inputs = {str(meta):sha(meta), str(Path(m['input'])):sha(m['input'])}
        operators[op] = dict(case_id=cid,source_dir=str(tree),source_files=source,
            original_kernel_files={str(p.relative_to(original)):sha(p) for p in sorted((original/'op_kernel').glob('*')) if p.is_file()},
            binary=str(tree/'build'/op),binary_hash=sha(tree/'build'/op),metadata=str(meta),input_files=inputs)
    profiler=Path(shutil.which('msprof') or '/usr/local/Ascend/cann-9.0.0/tools/profiler/bin/msprof').resolve(strict=True)
    plan = dict(schema_version=1,purpose='timing_method_diagnosis_no_skill_promotion',created_at=time.time(),
        producer={str(Path(__file__).resolve()):sha(__file__),str(HEADER):sha(HEADER)},operators=operators,
        cells=cells(),cpu_affinity=cpus,cycles=6,pairs_per_cycle=5,repeat=100,warmup=10,prime_repeat=100,
        conditions={'shared':['shared'],'split':['map_AB','map_BA'],
                    'residency':['solo_before','secondary_idle','dual_active_serial','solo_after']},
        logging={'row_logging':'reader write+flush before enqueue; full raw JSON saved after each pair',
                 'buffered':'reader retains all lines in memory; raw and child logs saved only after complete cycle or failure'},
        thresholds={'max_role_bias':.02,'max_sample_cv':.05,'max_solo_mean_shift':.02},
        statistics='abs(exp(mean(log(B/A)))-1); sample stdev/mean; evaluate each condition overall AND each fresh cycle. No gain threshold.',
        execution_policy='Exactly once per fixed cell. Preserve rejected controls and continue the diagnostic matrix; correctness or execution failure stops the experiment. No resampling.',
        decision_policy='If buffered dual-resident remains biased, logging-only repair is insufficient. Shared-buffer pass supports a separately implemented common-ABI two-callback collector only after independent full20 sigmoid+exp qualification. If both fail, stop this fixed experiment and propose a new investigation.',
        timeline={'separate_from_control_samples':True,'operators':['exp','sigmoid'],'cycles':1,
                  'tool':str(profiler),'tool_hash':sha(profiler),
                  'slots':1,'warmup':10,'prime_commands':4,'prime_repeat':100,'samples':1,'repeat':100,
                  'expected_kernel_tasks':510,'sample_task_range_zero_based':[410,510],
                  'metrics':['kernel_task_count','kernel_total_duration_ns','first_last_kernel_span_ns','acl_event_range_ns'],
                  'constraint':'Keep per-kernel timestamps; event interval may include gaps and need not equal summed kernel duration.'})
    save(destination/'plan.draft.json', plan)
    print(json.dumps({'draft':str(destination/'plan.draft.json'),'sha256':sha(destination/'plan.draft.json')}))


def freeze(draft, output):
    if output.exists():raise FileExistsError(output)
    plan=read(draft);root=output.parent;payloads={}
    for op,phase,cid in [('exp','aa_before',9),('sigmoid','formal',4)]:
        original=OLD/op/'v2-diagnostic'/phase/'raw_measurements.json';value=read(original)
        value['records']=[r for r in value['records'] if r['case_id']<cid]
        value['case_executions']=[r for r in value['case_executions'] if r['case_id']<cid]
        payload=dict(authority='historical_logging_bytes_only_not_new_measurements',source_path=str(original),source_sha256=sha(original),selection=f'fixed identities and records/case_executions before case_id {cid}',historical_payload=value)
        path=root/op/'logging-reference-payload.json'
        if path.exists():raise FileExistsError(path)
        save(path,payload);payloads[op]={'path':str(path),'sha256':sha(path),'bytes':path.stat().st_size,'source':str(original),'source_hash':sha(original)}
    old_raw=read(OLD/'exp/v2-diagnostic/aa_before/raw_measurements.json')
    env={k:old_raw['environment'][k] for k in ('ASCEND_HOME_PATH','ASCEND_OPP_PATH','LD_LIBRARY_PATH','ASCEND_RT_VISIBLE_DEVICES')}
    env.update(OMP_NUM_THREADS='32',MKL_NUM_THREADS='32',OPENBLAS_NUM_THREADS='32')
    snapshot=root/'frozen';snapshot.mkdir(exist_ok=False)
    copied=snapshot/Path(__file__).name;shutil.copyfile(__file__,copied)
    host_tools={name:{'path':str(Path(path).resolve()),'sha256':sha(Path(path).resolve())}
                for name,path in {'python':sys.executable,'taskset':shutil.which('taskset'),'npu-smi':shutil.which('npu-smi')}.items()}
    snapshot_commands=[[host_tools['npu-smi']['path'],'info']]+[[host_tools['npu-smi']['path'],'info','-t',kind,'-i','0','-c','0'] for kind in ('usages','sensors')]
    plan.update(created_at=time.time(),draft_ref={'path':str(draft),'sha256':sha(draft)},
        producer={str(Path(__file__).resolve()):sha(__file__),str(copied):sha(copied),str(HEADER):sha(HEADER)},
        frozen_runner=str(copied),logging_reference_payloads=payloads,environment=env,
        host_tools=host_tools,device_state_commands=snapshot_commands,
        environment_source=str(OLD/'exp/v2-diagnostic/aa_before/raw_measurements.json'),
        cpu_affinity_policy='Exact complete inherited mask at preparation; unchanged for all worker roles. No narrower pinning factor.',
        control_samples_exclude='logging_reference_payload is immutable historical write-cost data and never included in new records/statistics.')
    save(output,plan);print(json.dumps({'plan':str(output),'sha256':sha(output),'runner':str(copied),'logging_payloads':payloads},indent=2))


class Child:
    def __init__(self, command, cwd, env, directory, logging, cpus, taskset='taskset'):
        self.directory=directory;self.logging=logging;self.lines=[];self.queue=queue.Queue();self.sequence=0
        self.log = (directory/'stdout.log').open('x') if logging=='row_logging' else None
        actual_command=[taskset,'-c',','.join(map(str,cpus)),*command]
        self.receipt=dict(argv=actual_command,application_argv=command,cwd=str(cwd),started_at=time.time(),environment={k:env.get(k) for k in ('ASCEND_HOME_PATH','ASCEND_OPP_PATH','LD_LIBRARY_PATH','ASCEND_RT_VISIBLE_DEVICES','APROF_DIAG_SLOTS','APROF_DIAG_REPEAT','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS')},cpu_affinity=cpus)
        self.process=subprocess.Popen(actual_command,cwd=cwd,env=env,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,start_new_session=True)
        self.receipt['wrapper_pid']=self.process.pid
        def reader():
            try:
                for line in self.process.stdout:
                    self.lines.append(line)
                    if self.log: self.log.write(line);self.log.flush()
                    self.queue.put(line)
            finally:self.queue.put(None)
        self.reader=threading.Thread(target=reader,daemon=True);self.reader.start()
        self.proc={}
        try:
            self.ready=self.until('ready');self.receipt['pid']=self.ready['pid']
            self.proc={name:Path(f'/proc/{self.ready["pid"]}/{name}').read_text() for name in ('status','stat','numa_maps','maps')}
        except BaseException:
            self.close(abort=True);self.persist();raise
    def until(self, kind):
        deadline=time.monotonic()+180
        while True:
            line=self.queue.get(timeout=max(.001,deadline-time.monotonic()))
            if line is None:raise RuntimeError('diagnostic child terminated before '+kind)
            if line.startswith(PREFIX):
                value=json.loads(line[len(PREFIX):])
                if value['type']!=kind:raise ValueError('unexpected child message '+value['type'])
                return value
            if time.monotonic()>deadline:raise TimeoutError('diagnostic child timeout')
    def command(self, verb, slot):
        begin=time.monotonic_ns();sequence=self.sequence;self.sequence+=1
        self.process.stdin.write(f'{verb} {slot} {sequence}\n');self.process.stdin.flush()
        value=self.until(verb)
        if value['sequence']!=sequence or value['slot']!=slot or value['pid']!=self.ready['pid']:
            raise ValueError('command identity mismatch')
        return dict(request_monotonic_ns=begin,response_monotonic_ns=time.monotonic_ns(),sample=value)
    def close(self, abort=False):
        if self.process.poll() is None:
            if abort:os.killpg(self.process.pid,signal.SIGTERM)
            else:self.process.stdin.write('quit\n');self.process.stdin.flush()
            try:self.process.wait(timeout=60)
            except subprocess.TimeoutExpired:os.killpg(self.process.pid,signal.SIGKILL);self.process.wait()
        self.reader.join(timeout=5)
        self.receipt.update(finished_at=time.time(),exit_status=self.process.returncode)
        if self.log:self.log.close();self.log=None
        if not abort and self.process.returncode:raise RuntimeError('diagnostic worker failed')
    def persist(self):
        if self.logging=='buffered':(self.directory/'stdout.log').write_text(''.join(self.lines))
        save(self.directory/'execution.json',self.receipt);save(self.directory/'proc.json',self.proc)


def pair_orders(cycle):return [list(ROLES if (cycle+i)%2==0 else ROLES[::-1]) for i in range(5)]


def sample_phase(raw, phase, mapping, cycle, directory, logging):
    # Always condition A/B/B/A in the current physical mapping, outside samples.
    primes=[]
    for role in ('A','B','B','A'):
        child,slot=mapping[role];primes.append(dict(role=role,**child.command('prime',slot)))
    raw['phases'].append(dict(name=phase,prime_receipts=primes,started_at=time.time()))
    for index,order in enumerate(pair_orders(cycle)):
        row=dict(condition=phase,cycle=cycle,pair=index,order=order,roles={});raw['records'].append(row)
        for role in order:
            child,slot=mapping[role];row['roles'][role]=child.command('sample',slot)
        if logging=='row_logging':
            begin=time.monotonic_ns();save(directory/'raw.json',raw);end=time.monotonic_ns()
            raw.setdefault('persistence_receipts',[]).append(dict(condition=phase,pair=index,
                started_monotonic_ns=begin,finished_monotonic_ns=end,bytes=(directory/'raw.json').stat().st_size))
    raw['phases'][-1]['finished_at']=time.time()


def worker(operator, plan, directory, slots, logging):
    directory.mkdir();info=plan['operators'][operator];m=read(info['metadata']);output=directory/'output0.bin'
    argv=worker_command(operator,info,m,output)
    env=dict(os.environ,**plan.get('environment',{}));env.update(ASCEND_RT_VISIBLE_DEVICES='0',APROF_DIAG_SLOTS=str(slots),APROF_DIAG_REPEAT=str(plan['repeat']),APROF_DIAG_OUTPUT1=str(directory/'output1.bin'))
    env.pop('APROF_DIAG_COMMANDS',None)
    return Child(argv,info['source_dir'],env,directory,logging,plan['cpu_affinity'],plan['host_tools']['taskset']['path'])


def worker_command(operator,info,metadata,output):
    argv=[info['binary'],'--numel',str(metadata['numel']),'--dtype',metadata['dtype'],
          '--input',metadata['input'],'--output',str(output),'--device','0']
    if operator=='exp':
        for key in ('base','scale','shift'):argv.extend(['--'+key,str(metadata[key])])
    return argv


def verify_outputs(child, operator, plan):
    info=plan['operators'][operator];m=read(info['metadata'])
    for slot in range(len(child.ready['buffers'])):
        d=child.directory/f'verify-slot{slot}';d.mkdir();metadata=dict(m,output=str(child.directory/f'output{slot}.bin'))
        save(d/'metadata.json',metadata)
        argv=[sys.executable,str(Path(info['source_dir'])/'scripts/verify_result.py'),'--metadata',str(d/'metadata.json')]
        begin=time.time();result=subprocess.run(argv,env=dict(os.environ,**plan.get('environment',{})),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (d/'stdout.log').write_text(result.stdout)
        save(d/'execution.json',dict(argv=argv,started_at=begin,finished_at=time.time(),exit_status=result.returncode,output_hash=sha(metadata['output'])))
        if result.returncode:raise RuntimeError('unchanged oracle rejected diagnostic output')


def device_snapshot(directory, label, plan):
    results=[]
    for argv in plan['device_state_commands']:
        before=time.time();result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
        results.append(dict(argv=argv,started_at=before,finished_at=time.time(),exit_status=result.returncode,stdout=result.stdout,stderr=result.stderr))
    host={name:Path('/proc',name).read_text() for name in ('stat','loadavg','meminfo')}
    save(directory/f'device-{label}.json',dict(commands=results,host=host))
    if results[0]['exit_status']:raise RuntimeError('device inventory failed')


def run_cell(cell, plan, directory):
    directory.mkdir();logging=cell['logging'];cycle=cell['cycle'];op=cell['operator'];mode=cell['mode']
    raw=dict(schema_version=1,cell=cell,started_at=time.time(),records=[],phases=[],workers=[],complete=False,
        logging_reference_payload=read(plan['logging_reference_payloads'][op]['path']))
    children=[]
    try:
        device_snapshot(directory,'before',plan)
        main=worker(op,plan,directory/'primary',2 if mode=='split' else 1,logging);children.append(main)
        shared={role:(main,0) for role in ROLES}
        if mode=='shared':sample_phase(raw,'shared',shared,cycle,directory,logging)
        elif mode=='split':
            for label in (('map_AB','map_BA') if cycle%2==0 else ('map_BA','map_AB')):
                slots=(0,1) if label=='map_AB' else (1,0)
                sample_phase(raw,label,dict(zip(ROLES,((main,s) for s in slots))),cycle,directory,logging)
        else:
            sample_phase(raw,'solo_before',shared,cycle,directory,logging)
            second=worker(op,plan,directory/'secondary',1,logging);children.append(second)
            sample_phase(raw,'secondary_idle',shared,cycle,directory,logging)
            mapping={'A':(main,0),'B':(second,0)} if cycle%2==0 else {'A':(second,0),'B':(main,0)}
            sample_phase(raw,'dual_active_serial',mapping,cycle,directory,logging)
            second.close();sample_phase(raw,'solo_after',shared,cycle,directory,logging)
        main.close()
        for child in children:verify_outputs(child,op,plan)
        raw['complete']=True
    except BaseException as exc:
        raw['error']=dict(type=type(exc).__name__,message=str(exc));raise
    finally:
        for child in children:
            child.close(abort=True);child.persist();raw['workers'].append(dict(ready=child.ready,execution=child.receipt))
        raw['finished_at']=time.time();save(directory/'raw.json',raw)
        device_snapshot(directory,'after',plan)


def summarize(root, plan):
    result=[]
    for op in plan['operators']:
        for mode,conditions in plan['conditions'].items():
            for logging in FACTORS:
                for condition in conditions:
                    rows=[r for p in root.glob(f'{op}-*-{mode}-{logging}/raw.json') for r in read(p)['records'] if r['condition']==condition]
                    for cycle in [None,*range(6)]:
                        selected=[r for r in rows if cycle is None or r['cycle']==cycle]
                        a,b=([r['roles'][role]['sample']['event_ns_per_operator'] for r in selected] for role in ROLES)
                        if len(a)!=(30 if cycle is None else 5):raise ValueError('missing preregistered pairs')
                        bias=abs(math.exp(statistics.fmean(math.log(y/x) for x,y in zip(a,b)))-1)
                        cvs=[statistics.stdev(x)/statistics.fmean(x) for x in (a,b)]
                        slots={}
                        if mode=='split':
                            for slot in (0,1):
                                physical=[r['roles'][role]['sample']['event_ns_per_operator'] for r in selected for role in ROLES if r['roles'][role]['sample']['slot']==slot]
                                slots[str(slot)]={'samples':len(physical),'mean_ns':statistics.fmean(physical)}
                        result.append(dict(operator=op,mode=mode,logging=logging,condition=condition,cycle=cycle,pairs=len(a),role_bias=bias,cv_A=cvs[0],cv_B=cvs[1],physical_slots=slots,passed=bias<=.02 and max(cvs)<=.05))
    shifts=[]
    for op in plan['operators']:
        for logging in FACTORS:
            records=[r for p in root.glob(f'{op}-*-residency-{logging}/raw.json') for r in read(p)['records']]
            for cycle in [None,*range(6)]:
                for role in ROLES:
                    means={phase:statistics.fmean(r['roles'][role]['sample']['event_ns_per_operator'] for r in records
                        if r['condition']==phase and (cycle is None or r['cycle']==cycle)) for phase in ('solo_before','solo_after')}
                    shift=abs(means['solo_after']/means['solo_before']-1)
                    shifts.append(dict(operator=op,logging=logging,cycle=cycle,role=role,shift=shift,passed=shift<=.02))
    return dict(schema_version=1,authority='diagnosis_only_no_promotion',rows=result,solo_shifts=shifts,
                all_controls_passed=all(x['passed'] for x in [*result,*shifts]))


@contextlib.contextmanager
def exclusive():
    with contextlib.ExitStack() as stack:
        root=Path('/tmp/aprof-device-locks');root.mkdir(exist_ok=True)
        for name in ['host-serial.lock',*[f'device-{i}.lock' for i in range(16)]]:
            stream=stack.enter_context((root/name).open('a+'));deadline=time.monotonic()+180
            while True:
                try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB);break
                except BlockingIOError:
                    if time.monotonic()>deadline:raise TimeoutError('hardware lock is held: '+name)
                    time.sleep(.2)
        yield


def checked_plan(plan_path, expected_hash):
    if sha(plan_path)!=expected_hash:raise ValueError('preregistered plan hash differs')
    plan=read(plan_path)
    for path,digest in plan['producer'].items():
        if sha(path)!=digest:raise ValueError('producer changed after registration')
    for payload in plan['logging_reference_payloads'].values():
        if sha(payload['path'])!=payload['sha256'] or Path(payload['path']).stat().st_size!=payload['bytes']:
            raise ValueError('logging payload changed after registration')
    for tool in plan['host_tools'].values():
        if sha(tool['path'])!=tool['sha256']:raise ValueError('host tool changed after registration')
    if sha(sys.executable)!=plan['host_tools']['python']['sha256']:raise ValueError('Python interpreter differs from registration')
    for info in plan['operators'].values():
        for path,digest in info['input_files'].items():
            if sha(path)!=digest:raise ValueError('frozen input changed')
        for path,digest in info['source_files'].items():
            if sha(Path(info['source_dir'])/path)!=digest:raise ValueError('frozen diagnostic source changed')
        if sha(info['binary'])!=info['binary_hash']:raise ValueError('diagnostic binary changed')
    return plan


def run(plan_path, expected_hash, output):
    plan=checked_plan(plan_path,expected_hash)
    output.mkdir(exist_ok=False)
    with exclusive():
        for cell in plan['cells']:
            name=f"{cell['operator']}-{cell['cycle']}-{cell['mode']}-{cell['logging']}"
            run_cell(cell,plan,output/name);print(json.dumps(dict(cell=cell,status='completed')),flush=True)
        save(output/'controls.json',summarize(output,plan))


def timeline_summary(csv_path, stdout_path, operator):
    with Path(csv_path).open(newline='') as stream:
        reader=csv.DictReader(stream)
        required={'Op Name','Task Start Time(us)','Task Duration(us)'}
        if not required<=set(reader.fieldnames or []):raise ValueError('unrecognized msprof task-time columns')
        tasks=[r for r in reader if operator+'_kernel' in r['Op Name']]
    if len(tasks)!=510:raise ValueError(f'expected exactly 510 complete kernel tasks, got {len(tasks)}')
    ordered=sorted(tasks,key=lambda r:float(r['Task Start Time(us)']))
    selected=ordered[410:510]
    starts=[float(r['Task Start Time(us)'])*1000 for r in selected]
    durations=[float(r['Task Duration(us)'])*1000 for r in selected]
    if any(not math.isfinite(x) or x<=0 for x in [*starts,*durations]):raise ValueError('invalid profiler task duration/time')
    records=[json.loads(line[len(PREFIX):]) for line in Path(stdout_path).read_text().splitlines() if line.startswith(PREFIX)]
    samples=[r for r in records if r['type']=='sample']
    if len(samples)!=1 or samples[0]['repeat']!=100 or samples[0]['sequence']!=4:raise ValueError('profile sample identity differs')
    return dict(schema_version=1,authority='independent_profile_not_control_samples',operator=operator,
        profiler_csv_hash=sha(csv_path),stdout_hash=sha(stdout_path),complete_kernel_tasks=len(tasks),
        warmup_tasks=10,prime_tasks=400,sample_task_count=100,sample_kernel_tasks=selected,
        kernel_total_duration_ns=math.fsum(durations),first_last_kernel_span_ns=max(s+d for s,d in zip(starts,durations))-min(starts),
        acl_event_range_ns=samples[0]['event_ns_per_operator']*100,acl_sample=samples[0],
        interpretation='Event range includes queue gaps; equality with summed kernel durations is not required.')


def timeline(plan_path, expected_hash, output):
    plan=checked_plan(plan_path,expected_hash);output.mkdir(exist_ok=False)
    tool=plan['timeline']['tool']
    if sha(tool)!=plan['timeline']['tool_hash']:raise RuntimeError('preregistered profiler changed')
    with exclusive():
        for op in plan['timeline']['operators']:
            directory=output/op;directory.mkdir();info=plan['operators'][op];metadata=read(info['metadata'])
            command_file=directory/'commands.txt';command_file.write_text(''.join(f'prime 0 {i}\n' for i in range(4))+'sample 0 4\nquit\n')
            app=[plan['host_tools']['taskset']['path'],'-c',','.join(map(str,plan['cpu_affinity'])),*worker_command(op,info,metadata,directory/'output0.bin')]
            argv=[tool,'--output='+str(directory/'profile'),'--task-time=on','--runtime-api=on','--ascendcl=on','--ai-core=off','--type=text','--application='+shlex.join(app)]
            env=dict(os.environ,**plan.get('environment',{}));env.update(ASCEND_RT_VISIBLE_DEVICES='0',APROF_DIAG_COMMANDS=str(command_file),APROF_DIAG_SLOTS='1',APROF_DIAG_REPEAT='100')
            start=time.time();result=subprocess.run(argv,env=env,cwd=info['source_dir'],capture_output=True,text=True,timeout=600)
            (directory/'stdout.log').write_text(result.stdout);(directory/'stderr.log').write_text(result.stderr)
            save(directory/'execution.json',dict(argv=argv,started_at=start,finished_at=time.time(),exit_status=result.returncode,tool_hash=sha(tool)))
            if result.returncode:raise RuntimeError('independent task timeline collection failed')
            tables=list((directory/'profile').rglob('op_summary*.csv'))
            if not tables:
                profiles=list((directory/'profile').glob('PROF_*'))
                if len(profiles)!=1:raise RuntimeError('ambiguous profiler output directory')
                export=[tool,'--export=on','--type=text','--output='+str(profiles[0])]
                start=time.time();exported=subprocess.run(export,capture_output=True,text=True,timeout=600)
                (directory/'export.stdout.log').write_text(exported.stdout);(directory/'export.stderr.log').write_text(exported.stderr)
                save(directory/'export.execution.json',dict(argv=export,started_at=start,finished_at=time.time(),exit_status=exported.returncode))
                if exported.returncode:raise RuntimeError('independent task timeline export failed')
                tables=list((directory/'profile').rglob('op_summary*.csv'))
            if len(tables)!=1:raise RuntimeError('expected exactly one independent task table')
            save(directory/'timeline-summary.json',timeline_summary(tables[0],directory/'stdout.log',op))
            # The profile is a separate execution and retains its own correctness check.
            metadata['output']=str(directory/'output0.bin');save(directory/'metadata.json',metadata)
            verify=[sys.executable,str(Path(info['source_dir'])/'scripts/verify_result.py'),'--metadata',str(directory/'metadata.json')]
            start=time.time();verified=subprocess.run(verify,env=env,capture_output=True,text=True,timeout=180)
            (directory/'verify.stdout.log').write_text(verified.stdout);(directory/'verify.stderr.log').write_text(verified.stderr)
            save(directory/'verify.execution.json',dict(argv=verify,started_at=start,finished_at=time.time(),exit_status=verified.returncode,output_hash=sha(directory/'output0.bin')))
            if verified.returncode:raise RuntimeError('independent profile output failed correctness')


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--destination',type=Path,required=True);prep.add_argument('--cpus',default=','.join(map(str,sorted(os.sched_getaffinity(0)))))
    registration=sub.add_parser('freeze');registration.add_argument('--draft',type=Path,required=True);registration.add_argument('--output',type=Path,required=True)
    for name in ('run','timeline'):
        execute=sub.add_parser(name);execute.add_argument('--plan',type=Path,required=True);execute.add_argument('--expected-sha256',required=True);execute.add_argument('--output',type=Path,required=True)
    args=p.parse_args(argv)
    if args.action=='prepare':prepare(args.destination,[int(x) for x in args.cpus.split(',')])
    elif args.action=='freeze':freeze(args.draft,args.output)
    elif args.action=='run':run(args.plan,args.expected_sha256,args.output)
    else:timeline(args.plan,args.expected_sha256,args.output)


if __name__=='__main__':main()
