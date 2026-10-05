#!/usr/bin/env python3
"""Independent msprof timing study; does not produce legacy gate inputs.

Every target launch (including warmup) must match the native journal in stream
order. Task duration sums exclude inter-task gaps; PMU core time is reported
separately and is not a complete-operator latency. No outliers are discarded.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal
import difflib
import json
import math
import os
from pathlib import Path
import shutil
import statistics as st
import sys
import time

from cannbench_device_timing import ReusedVerifier
from level2_adapters import dispatch_command as command_from_metadata, verification_metadata, OPERATORS as LEVEL2_OPERATORS, launch_contract, input_paths, reusable_verifier, verify_build_dispatch, native_kernel_sequence
from cannbench_shared_context import count_launches
from cannbench_shared_context_profile import run_logged, sha, save, read_metadata, save_metadata
from run_level1_serial import exclusive_host, health
from shared_context_build import source_hash

ROOT = Path(__file__).resolve().parents[1]
VERSION = 'msprof_kernel_time_study_v1'
VERSION_V2 = 'msprof_kernel_time_study_v2'
METRICS = ('task_us', 'core_us', 'event_us')


def load(path):
    return json.loads(Path(path).read_text())


def instrument(source, repeat, *, per_case=False):
    """A separate, hashed measurement variant; original runner is untouched."""
    if type(repeat) is not int or not 1 <= repeat <= 100:
        raise ValueError('repeat must be in [1,100]')
    replacements = [
        ('#include <cstring>', '#include <cstring>\n#include <cstdlib>'),
        # Profiling may retain module callbacks until ACL finalization. Keep
        # code mapped through teardown; RTLD_LOCAL still isolates both roles.
        ('RTLD_NOW|RTLD_LOCAL', 'RTLD_NOW|RTLD_LOCAL|RTLD_NODELETE'),
        ('check(aclrtRecordEvent(start,stream));for(int i=0;i<100;++i)r.call(r.api->launch(r.state));',
         'const char *delay_env=std::getenv(std::string(r.api->identity()->role)=="A"?'
         '"APROF_MSPROF_HOST_DELAY_A_US":"APROF_MSPROF_HOST_DELAY_B_US");'
         'unsigned delay=delay_env?std::stoul(delay_env):0;'
         f'check(aclrtRecordEvent(start,stream));for(int i=0;i<{repeat};++i)'
         '{if(delay)usleep(delay);r.call(r.api->launch(r.state));}'),
        (r'\"repeat\":100', rf'\"repeat\":{repeat}'),
        ('double(ms)*10000', f'double(ms)*1000000/{repeat}'),
        (r'\"complete_calls_since_prepare\":3010', rf'\"complete_calls_since_prepare\":{10+30*repeat}'),
    ]
    for before, after in replacements:
        expected = 2 if before == r'\"repeat\":100' else 1
        if source.count(before) != expected:
            raise ValueError('native template changed; review required: '+before)
        source = source.replace(before, after)
    # Distinguish every journal row from the old event-only protocol.
    before = r'journal<<"{\"session_id\":"'
    after = r'journal<<"{\"timing_protocol\":\"msprof_kernel_time_study_v1\",\"session_id\":"'
    if source.count(before) != 1:
        raise ValueError('journal template changed')
    source = source.replace(before, after)
    if per_case:
        source = source.replace(VERSION, VERSION_V2)
        # Only the new Level2 runner reads this frozen TSV field. Legacy generated
        # runners and their repeat constants remain byte-for-byte unchanged.
        source = source.replace('namespace {', 'namespace {\nint aprof_case_repeat='+str(repeat)+';', 1)
        source = source.replace(f'for(int i=0;i<{repeat};++i)', 'for(int i=0;i<aprof_case_repeat;++i)')
        source = source.replace(f'double(ms)*1000000/{repeat}', 'double(ms)*1000000/aprof_case_repeat')
        source = source.replace(r'\"repeat\":'+str(repeat), r'\"repeat\":'+ '\"+std::to_string(aprof_case_repeat)+\"', 1)
        source = source.replace(r'\"repeat\":'+str(repeat), r'\"repeat\":'+ '\"<<aprof_case_repeat<<\"', 1)
        source = source.replace(r'\"complete_calls_since_prepare\":'+str(10+30*repeat), r'\"complete_calls_since_prepare\":'+ '\"+std::to_string(10+30*aprof_case_repeat)+\"')
        anchor='for(size_t case_index=0;case_index<cases.size();++case_index){auto &c=cases[case_index];'
        if source.count(anchor)!=1: raise ValueError('case loop template changed')
        source = source.replace(anchor,anchor+'aprof_case_repeat='+str(repeat)+';for(size_t j=1;j+1<c.size();j+=2)if(c[j]=="--aprof-repeat"){aprof_case_repeat=std::stoi(c[j+1]);if(aprof_case_repeat!=1&&aprof_case_repeat!=10)throw std::runtime_error("invalid frozen case repeat");}')
    return source


def build_runner(out, repeat, *, per_case=False):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    original = ROOT/'benchmarks/cannbench/harness/shared_context/runner.cpp'
    abi = original.with_name('abi.h')
    text = original.read_text()
    generated = instrument(text, repeat, per_case=per_case)
    (out/'original-runner.cpp').write_text(text)
    (out/'runner.cpp').write_text(generated)
    (out/'harness.patch').write_text(''.join(difflib.unified_diff(
        text.splitlines(True), generated.splitlines(True), fromfile='original-runner.cpp', tofile='runner.cpp')))
    shutil.copyfile(abi, out/'abi.h')
    home = Path(os.environ['ASCEND_HOME_PATH'])
    argv = ['g++', '-std=c++17', '-O2', str(out/'runner.cpp'), '-I'+str(home/'include'),
            '-L'+str(home/'lib64'), '-Wl,-rpath,'+str(home/'lib64'), '-lascendcl', '-ldl', '-o', str(out/'runner')]
    with exclusive_host():
        run_logged(argv, out/'build', dict(os.environ), 120)
    result = dict(version=VERSION_V2 if per_case else VERSION, repeat=repeat, pairs=30, warmup=10,
                  runner=str(out/'runner'), runner_hash=sha(out/'runner'),
                  source_hash=sha(out/'runner.cpp'), original_hash=sha(original), abi_hash=sha(abi))
    if per_case: result['per_case_repeat'] = True
    save(out/'build.json', result)
    return result


def positive(value, field):
    v = float(value)
    if not math.isfinite(v) or v <= 0:
        raise ValueError('missing/nonpositive/nonfinite '+field)
    return v


def parse_profile(raw, journal, build, cases, repeat):
    """Reject missing/extra/wrong-role tasks, multi-stream capture, and overlap."""
    needs_auxiliary=any(any(c.get('required_auxiliary_tasks',{}).get(r,[]) for r in 'AB') for c in cases)
    files = sorted(Path(raw).rglob('op_summary*.csv'))
    if len(files) != 1:
        raise ValueError('expected exactly one op_summary CSV')
    path = files[0]
    records = [load_row for load_row in (json.loads(x) for x in Path(journal).read_text().splitlines())]
    if not records or records[-1].get('type') != 'session_end' or records[-1].get('exit_code') != 0:
        raise ValueError('native session did not finish')
    modules = {r['role']:r for r in records if r['type']=='module'}
    if set(modules) != {'A', 'B'}:
        raise ValueError('missing role identities')
    for role in 'AB':
        for field in ('source_sha256', 'kernel_symbols'):
            if modules[role][field] != build['roles'][role][field]:
                raise ValueError('native role identity mismatch')
    symbols = {r:build['roles'][r]['kernel_symbols'].split(',') for r in 'AB'}
    known = {s for names in symbols.values() for s in names}
    rows = []
    skipped = []
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        required = {'Op Name','Task Type','Task Start Time(us)','Task Duration(us)','Stream ID','Task ID','Device_id'}
        if not required.issubset(reader.fieldnames or []) or len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError('invalid msprof headers')
        for line, row in enumerate(reader, 2):
            if None in row or any(v is None for v in row.values()):
                raise ValueError('malformed CSV row')
            if row['Op Name'] not in known:
                if row['Task Type'] in ('AI_CORE','AI_VECTOR_CORE','MIX_AIC','MIX_AIV'):
                    raise ValueError('unrecognized compute task: '+row['Op Name'])
                skipped.append(dict(line=line, name=row['Op Name'], task_type=row['Task Type']))
                continue
            if row['Task Type'] != 'AI_VECTOR_CORE':
                raise ValueError('this study only supports verified vector kernels')
            start = Decimal(row['Task Start Time(us)'].strip())
            if not start.is_finite():
                raise ValueError('invalid start timestamp')
            core_text=(row.get('aiv_time(us)') or '').strip()
            core=0 if core_text in ('', 'N/A', 'NA') else float(core_text)
            if not math.isfinite(core) or core<0:
                raise ValueError('invalid aiv_time')
            rows.append(dict(line=line, name=row['Op Name'], task_us=positive(row['Task Duration(us)'],'Task Duration'),
                             core_us=core or None, start=start,
                             device=row['Device_id'], stream=row['Stream ID'], task=row['Task ID']))
    auxiliary_csv=None
    compute_count=len(rows)
    use_task_time=needs_auxiliary or records[0].get('timing_protocol')==VERSION_V2
    if use_task_time:
        task_files=sorted(Path(raw).rglob('task_time*.csv'))
        if len(task_files)!=1:raise ValueError('complete-call reset requires exactly one task_time CSV')
        auxiliary_csv=task_files[0]
        compute={(r['device'],r['stream'],r['task'],r['start']):r for r in rows}
        if len(compute)!=len(rows):raise ValueError('duplicate compute identity')
        matched=set();aux=[]
        with auxiliary_csv.open(newline='',encoding='utf-8-sig') as f:
            reader=csv.DictReader(f)
            required={'Device_id','kernel_name','kernel_type','stream_id','task_id','task_time(us)','task_start(us)','task_stop(us)'}
            if not required.issubset(reader.fieldnames or []) or len(set(reader.fieldnames))!=len(reader.fieldnames):raise ValueError('invalid task_time headers')
            for line,row in enumerate(reader,2):
                if None in row or any(v is None for v in row.values()):raise ValueError('malformed task_time row')
                kind=row['kernel_type']
                if kind in ('EVENT_RECORD','PROFILING_ENABLE','PROFILING_DISABLE','PLACE_HOLDER_SQE'):continue
                start=Decimal(row['task_start(us)'].strip());stop=Decimal(row['task_stop(us)'].strip())
                if not start.is_finite() or not stop.is_finite():raise ValueError('invalid auxiliary timestamp')
                duration=positive(row['task_time(us)'],'task_time duration')
                if abs(stop-start-Decimal(str(duration)))>Decimal('0.002'):raise ValueError('task_time stop/duration differs')
                key=(row['Device_id'],row['stream_id'],row['task_id'],start)
                if row['kernel_name'] in known:
                    if key not in compute or key in matched:raise ValueError('task_time compute identity differs')
                    expected=compute[key]
                    if kind!='AI_VECTOR_CORE' or row['kernel_name']!=expected['name'] or abs(duration-expected['task_us'])>.002:raise ValueError('task_time/op_summary compute differs')
                    matched.add(key)
                    continue
                if kind not in ('MEMCPY_ASYNC','MEMSET','MEMSET_ASYNC'):raise ValueError('unrecognized complete-call task: '+kind)
                aux.append(dict(line=None,auxiliary_line=line,name=kind,task_us=duration,core_us=None,start=start,
                                device=key[0],stream=key[1],task=key[2]))
        if matched!=set(compute):raise ValueError('missing task_time compute records')
        rows.extend(aux)
    rows.sort(key=lambda r:r['start'])
    if len({(r['device'],r['stream']) for r in rows}) != 1:
        raise ValueError('expected one device stream')
    identities = [(r['device'],r['stream'],r['task'],r['start']) for r in rows]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate task record')
    for a,b in zip(rows, rows[1:]):
        if b['start'] < a['start']+Decimal(str(a['task_us']))-Decimal('0.002'):
            raise ValueError('overlapping target tasks cannot be summed')
    metadata = {str(c['case_id']):c for c in cases}
    cursor = 0
    samples = []
    warmup_rows = 0

    def consume(case, role, calls):
        nonlocal cursor
        launch_count = case['launches_per_call'][role]
        if 'kernel_sequence' in case:
            sequence=case['kernel_sequence'][role]
            if len(sequence)!=launch_count or not set(sequence)<=set(symbols[role]): raise ValueError('case launch contract mismatch')
        else:
            if launch_count % len(symbols[role]): raise ValueError('incomplete kernel sequence')
            sequence=symbols[role]*(launch_count//len(symbols[role]))
        resets=case.get('required_auxiliary_tasks',{}).get(role,[])
        # Observed on CANN9/910C: both explicit stream D2D copy and memset are DMA tasks.
        mapping={'device_to_device_copy':'MEMCPY_ASYNC','device_memset':'MEMCPY_ASYNC'}
        if any(x not in mapping for x in resets):raise ValueError('unknown auxiliary launch contract')
        expected = ([mapping[x] for x in resets]+sequence)*calls
        result = rows[cursor:cursor+len(expected)]
        if [r['name'] for r in result] != expected:
            raise ValueError(f'launch sequence mismatch at {cursor}, case {case["case_id"]}, role {role}')
        cursor += len(expected)
        return result

    for record in records:
        if record['type'] == 'case_start':
            case = metadata[record['case_id']]
            case_repeat=case.get('repeat',repeat)
            if (record['repeat'],record['pairs'],record['warmup_per_role']) != (case_repeat,30,10):
                raise ValueError('native measurement parameters differ')
            for _ in range(10):
                for role in 'AB':
                    warmup_rows += len(consume(case,role,1))
        elif record['type'] == 'sample':
            case = metadata[record['case_id']]
            role = record['role']
            case_repeat=case.get('repeat',repeat)
            if record['repeat'] != case_repeat or record['launches_per_call'] != case['launches_per_call'][role]:
                raise ValueError('native complete-call contract differs')
            captured = consume(case,role,case_repeat)
            task_us = sum(r['task_us'] for r in captured)/case_repeat
            compute=[r for r in captured if r['line'] is not None]
            core_us = sum(r['core_us'] for r in compute)/case_repeat if all(r['core_us'] is not None for r in compute) else None
            span = float(captured[-1]['start']-captured[0]['start'])+captured[-1]['task_us']
            samples.append(dict(case_id=record['case_id'], buffer_config=record['buffer_config'],
                                pair_id=record['pair_id'], role=role, order=record['order'],
                                task_us=task_us, core_us=core_us, event_us=positive(record['ns_per_call'],'event')/1000,
                                task_span_us=span/case_repeat, inter_task_gap_us=(span-case_repeat*task_us)/case_repeat,
                                launches=len(compute), csv_rows=[r['line'] for r in compute]))
            if use_task_time:
                samples[-1].update(auxiliary_tasks=len(captured)-len(compute),auxiliary_csv_rows=[r['auxiliary_line'] for r in captured if r['line'] is None],
                                   auxiliary_task_us=sum(r['task_us'] for r in captured if r['line'] is None)/case_repeat)
            if role in case.get('expected_dispatch',{}):
                samples[-1]['verified_dispatch']=dict(case['expected_dispatch'][role],captured_kernel_sequence=case['kernel_sequence'][role])
    if cursor != len(rows):
        raise ValueError(f'extra target tasks: consumed {cursor}, captured {len(rows)}')
    if not samples:
        raise ValueError('no measured samples')
    producer=records[0].get('timing_protocol',VERSION)
    if producer not in (VERSION,VERSION_V2):raise ValueError('unknown native timing producer')
    result=dict(version=producer, csv=str(path), csv_hash=sha(path), target_tasks=len(rows),
                warmup_tasks_excluded=warmup_rows, other_tasks=skipped, samples=samples)
    if use_task_time:result.update(auxiliary_csv=str(auxiliary_csv),auxiliary_csv_hash=sha(auxiliary_csv),compute_tasks=compute_count,auxiliary_tasks=len(rows)-compute_count)
    return result


def profiler_arguments(mode, output):
    """Make PMU collection an explicit condition of the timing experiment."""
    if mode not in ('task_time_l1_pipe_utilization', 'task_time_l1_ai_core_off'):
        raise ValueError('unsupported profiler_mode: '+str(mode))
    pmu=mode=='task_time_l1_pipe_utilization'
    return ['msprof','--output='+str(output),'--task-time=l1',
            '--ai-core='+('on' if pmu else 'off'),
            *(['--aic-metrics=PipeUtilization'] if pmu else []),
            '--ascendcl=off','--runtime-api=off']


def collect(request_path, out):
    request = load(request_path)
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    save(out/'request.json',request)
    build = load(request['role_build'])
    runner = load(request['runner_build'])
    version=runner['version']
    if version not in (VERSION,VERSION_V2) or request.get('version',VERSION)!=version or sha(runner['runner']) != runner['runner_hash']:
        raise ValueError('runner identity differs')
    for role in 'AB':
        identity=build['roles'][role]
        if sha(identity['binary']) != 'sha256:'+identity['binary_sha256'] or source_hash(Path(identity['source_dir'])) != identity['source_sha256']:
            raise ValueError('source/binary identity differs')
    rows=[]; cases=[]; bindings={}
    if build['operator'] in LEVEL2_OPERATORS:
        for role in 'AB':
            for path in verify_build_dispatch(build['roles'][role]):bindings[str(path)]=sha(path)
        for filename in ('level2_adapters.py','shared_context_build.py','cannbench_shared_context.py','cannbench_shared_context_profile.py','cannbench_device_timing.py'):
            path=ROOT/'scripts'/filename;bindings[str(path)]=sha(path)
        path=ROOT/'src/aprof_runtime/planning.py';bindings[str(path)]=sha(path)
    opdir=Path(build['roles']['A']['source_dir'])
    for spec in request['cases']:
        meta=read_metadata(spec['metadata'])
        case=str(spec['case_id'])
        argv=command_from_metadata(opdir,meta,0,out/'unused.bin')[1:]
        if any('\t' in x or '\n' in x for x in argv):
            raise ValueError('invalid TSV argument')
        case_row=dict(case_id=case,launches_per_call={r:count_launches(build['operator'],build['roles'][r]['source_dir'],meta) for r in 'AB'})
        if build['operator'] in LEVEL2_OPERATORS:
            contracts={r:launch_contract(build['operator'],build['roles'][r]['source_dir'],meta) for r in 'AB'}
            case_row['kernel_sequence']={r:native_kernel_sequence(build['roles'][r],contracts[r]['kernels']) for r in 'AB'}
            case_row['required_auxiliary_tasks']={r:contracts[r]['required_auxiliary_tasks'] for r in 'AB'}
            expected_dispatch={r:contracts[r]['expected_dispatch'] for r in 'AB' if 'expected_dispatch' in contracts[r]}
            if expected_dispatch:case_row['expected_dispatch']=expected_dispatch
            case_repeat=spec.get('repeat',runner['repeat'])
            if type(case_repeat) is not int or case_repeat not in (1,10):raise ValueError('Level2 repeat must be 1 or 10')
            if case_repeat != runner['repeat'] and not runner.get('per_case_repeat'):raise ValueError('runner does not support per-case repeats')
            case_row['repeat']=case_repeat
            if runner.get('per_case_repeat'):argv+=['--aprof-repeat',str(case_repeat)]
        rows.append('\t'.join([case,*argv]))
        cases.append(case_row)
        for path in [spec['metadata'],spec['verifier'],*(input_paths(meta) if build['operator'] in LEVEL2_OPERATORS else [v for k,v in meta.items() if k!='output' and isinstance(v,str) and Path(v).is_file()])]:
            bindings[str(path)]=sha(path)
    if len({c['case_id'] for c in cases})!=len(cases):
        raise ValueError('duplicate case')
    if build['operator'] in LEVEL2_OPERATORS:
        for spec in request['cases']:
            for path in Path(spec['verifier']).parent.iterdir():
                if path.is_file() and path.suffix in ('.py','.csv','.yaml','.yml'): bindings[str(path)]=sha(path)
    for path in [request_path,request['role_build'],request['runner_build'],__file__,runner['runner']]:
        bindings[str(path)]=sha(path)
    save(out/'bindings.json',bindings)
    save(out/'cases.json',cases)
    (out/'cases.tsv').write_text('\n'.join(rows)+'\n')
    env=dict(os.environ,ASCEND_RT_VISIBLE_DEVICES=str(request.get('device',0)),OMP_NUM_THREADS='2',MKL_NUM_THREADS='2',OPENBLAS_NUM_THREADS='2')
    for role in 'AB':
        delay=request.get('host_delay_'+role.lower()+'_us',0)
        if type(delay) is not int or not 0<=delay<=10000:
            raise ValueError('invalid host delay')
        env['APROF_MSPROF_HOST_DELAY_'+role+'_US']=str(delay)
    native=[runner['runner'],
            '--role-a',build['roles']['A']['binary'],'--role-b',build['roles']['B']['binary'],
            '--cases',str(out/'cases.tsv'),'--output-dir',str(out/'native'), '--session-id',out.name,
            '--load-order',request.get('load_order','AB'),'--first-order',request.get('first_order','AB'),
            '--buffer-configs',request.get('buffer_configs','normal,swapped'),'--device','0']
    argv=['taskset','-c',str(request.get('cpu',8)),
          *profiler_arguments(request.get('profiler_mode','task_time_l1_pipe_utilization'),out/'raw'),*native]
    error=None
    with exclusive_host():
        try:
            health(out/'health-before.json')
            run_logged(argv,out/'msprof',env,request.get('timeout',300))
            validations=[];verifiers={}
            # The native process has exited: oracle CPU work cannot perturb timing.
            for spec in request['cases']:
                for config in request.get('buffer_configs','normal,swapped').split(','):
                    for role in 'AB':
                        stem=f'{spec["case_id"]}_{config}_{role}'
                        output=out/'native'/(stem+'.bin')
                        meta=verification_metadata(opdir,read_metadata(spec['metadata']),output)
                        vdir=out/'verification'/stem;vdir.mkdir(parents=True)
                        mpath=vdir/'metadata.json';save_metadata(mpath,meta)
                        if spec['verifier'] not in verifiers:
                            verifiers[spec['verifier']]=reusable_verifier(spec['verifier'])
                        started=time.time()
                        checked=verifiers[spec['verifier']].run(mpath)
                        (vdir/'stdout.log').write_text(checked.stdout)
                        save(vdir/'execution.json',dict(argv=checked.args,exit_code=checked.returncode,
                             started_at=started,ended_at=time.time(),mode='unchanged_import_safe_main',
                             **({'oracle_relocation':checked.oracle_relocation} if hasattr(checked,'oracle_relocation') else {})))
                        if checked.returncode:
                            raise ValueError('oracle failed: '+stem)
                        validations.append(dict(case_id=str(spec['case_id']),buffer_config=config,role=role,passed=True,output_hash=sha(output)))
            save(out/'validation.json',dict(scope='final_call_of_final_sample_per_case_config_role',outputs=validations))
            parsed=parse_profile(out/'raw',out/'native/journal.jsonl',build,cases,runner['repeat'])
            save(out/'samples.json',parsed)
            for path,digest in bindings.items():
                if sha(path)!=digest:
                    raise ValueError('bound evidence changed: '+path)
        except BaseException as exc:
            error=dict(type=type(exc).__name__,message=str(exc))
            raise
        finally:
            try:
                health(out/'health-after.json')
            except BaseException as exc:
                if error is None:
                    error=dict(type=type(exc).__name__,message=str(exc))
            save(out/'completion.json',dict(version=version,status='failed' if error else 'passed',error=error,formal_admission='not_evaluated'))
        if error:
            raise RuntimeError(str(error))
    return dict(output=str(out),target_tasks=parsed['target_tasks'],samples=len(parsed['samples']))


def describe(values):
    return dict(mean=st.mean(values),median=st.median(values),cv=st.stdev(values)/st.mean(values) if len(values)>1 else 0,
                minimum=min(values),maximum=max(values))


def summarize(directories):
    """Process is the replication unit. No pooled per-launch confidence interval."""
    from scipy.stats import t
    groups={};missing={};condition=None;seen_directories=set()
    for directory in directories:
        directory=Path(directory).resolve()
        if directory in seen_directories:
            raise ValueError('duplicate process directory')
        seen_directories.add(directory)
        if load(directory/'completion.json')['status']!='passed':
            raise ValueError('incomplete collection: '+str(directory))
        request=load(directory/'request.json')
        current={k:request.get(k) for k in ('role_build','runner_build','cases')}
        current.update(profiler_mode=request.get('profiler_mode','task_time_l1_pipe_utilization'),
                       device=request.get('device',0),cpu=request.get('cpu',8),
                       host_delay_a_us=request.get('host_delay_a_us',0),host_delay_b_us=request.get('host_delay_b_us',0))
        if condition is not None and current!=condition:
            raise ValueError('cannot pool different sources, cases, profiler modes or host-delay conditions')
        condition=current
        samples=load(directory/'samples.json')['samples']
        for case,config in sorted({(s['case_id'],s['buffer_config']) for s in samples}):
            rows=[s for s in samples if s['case_id']==case and s['buffer_config']==config]
            pairs={}
            for row in rows:
                slot=pairs.setdefault(row['pair_id'],{})
                if row['role'] in slot:
                    raise ValueError('duplicate role/pair')
                slot[row['role']]=row
            if set(pairs)!=set(range(30)) or any(set(p)!=set('AB') for p in pairs.values()):
                raise ValueError('incomplete pairing')
            for metric in METRICS:
                if any(p[r][metric] is None for p in pairs.values() for r in 'AB'):
                    missing.setdefault((case,config,metric),[]).append(directory.name)
                    continue
                logs=[math.log(p['A'][metric]/p['B'][metric]) for p in pairs.values()]
                role_stats={r:describe([p[r][metric] for p in pairs.values()]) for r in 'AB'}
                order_means={order:st.mean([math.log(p['A'][metric]/p['B'][metric]) for p in pairs.values() if p['A']['order']==order]) for order in ('AB','BA')}
                groups.setdefault((case,config,metric),[]).append(dict(session=directory.name,log_ratio=st.mean(logs),
                    speedup=math.exp(st.mean(logs)),roles=role_stats,order_log_effect=order_means['AB']-order_means['BA']))
    result=[]
    for (case,config,metric),sessions in sorted(groups.items()):
        if (case,config,metric) in missing:
            continue  # Never report a subset of processes as the full cohort.
        logs=[s['log_ratio'] for s in sessions];n=len(logs);mean=st.mean(logs)
        half=float(t.ppf(.975,n-1))*st.stdev(logs)/math.sqrt(n) if n>1 else None
        ci=[math.exp(mean-half),math.exp(mean+half)] if half is not None else None
        result.append(dict(case_id=case,buffer_config=config,metric=metric,n_processes=n,speedup=math.exp(mean),ci95=ci,
            aa_within_half_percent=bool(ci and ci[0]>=1/1.005 and ci[1]<=1.005),
            max_within_process_cv=max(s['roles'][r]['cv'] for s in sessions for r in 'AB'),
            sessions=sessions))
    return dict(version=VERSION,unit='us_per_complete_call',replication_unit='native_process',results=result,
                unavailable=[dict(case_id=k[0],buffer_config=k[1],metric=k[2],missing_in_sessions=v) for k,v in sorted(missing.items())])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('build');p.add_argument('--output',required=True);p.add_argument('--repeat',type=int,default=10)
    p=sub.add_parser('collect');p.add_argument('--request',required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('summarize');p.add_argument('directories',nargs='+');p.add_argument('--output',required=True)
    args=parser.parse_args()
    if args.command=='build':
        result=build_runner(args.output,args.repeat)
    elif args.command=='collect':
        result=collect(args.request,args.output)
    else:
        result=summarize(args.directories);save(Path(args.output),result)
    print(json.dumps(result,allow_nan=False))


if __name__=='__main__':
    main()
