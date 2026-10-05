#!/usr/bin/env python3
"""Local host-exclusive continuation of an immutable Level1 candidate roster."""
from __future__ import annotations
import argparse
import contextlib
import datetime as dt
import difflib
import fcntl
import hashlib
import fnmatch
import json
import math
import os
from pathlib import Path
import shutil
import signal
import socket
import statistics
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from cannbench_device_timing import summarize_multicase

PYTHON = '/usr/local/python3.11.15/bin/python3'
CASES = [1, 8, 14, 20]
DEFER_INTERRUPTS = False
PENDING_SIGNAL = None

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')

def read(path):
    return json.loads(Path(path).read_text())

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1048576), b''):
            h.update(chunk)
    return 'sha256:' + h.hexdigest()

def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if path.exists():
        if path.read_text() != text:
            raise ValueError(f'immutable evidence differs: {path}')
        return
    temp = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temp.write_text(text)
    os.replace(temp, path)

@contextlib.contextmanager
def exclusive_host(lock_root='/tmp/aprof-device-locks'):
    """Also excludes legacy jobs which know only their individual chip lock."""
    root = Path(lock_root)
    root.mkdir(parents=True, exist_ok=True)
    locks = []
    try:
        for name in ['host-serial.lock'] + [f'device-{i}.lock' for i in range(16)]:
            f = (root / name).open('a+')
            locks.append(f)
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise RuntimeError(f'host is not exclusive: {name} is occupied') from e
        yield
    finally:
        for f in reversed(locks):
            fcntl.flock(f, fcntl.LOCK_UN)
            f.close()

def health(out):
    out = Path(out)
    if out.exists():
        out = out.with_name(out.stem + f'-resume-{time.time_ns()}' + out.suffix)
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = '/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/driver:/usr/local/Ascend/driver/lib64/common'
    started = now()
    argv = ['/usr/local/sbin/npu-smi', 'info']
    p = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=30)
    record = dict(argv=argv, cwd=str(ROOT), host=socket.gethostname(), started_at=started,
                  finished_at=now(), exit_status=p.returncode, stdout=p.stdout, stderr=p.stderr)
    # The standard eight-card report explicitly enumerates empty process tables.
    record['no_device_processes'] = p.returncode == 0 and p.stdout.count('No running processes found in NPU') == 8
    save(out, record)
    if not record['no_device_processes']:
        raise RuntimeError('device process inventory is not empty; see health evidence')
    return record

def prepare_measurement_tree(source, destination, op):
    from collect_level1_traces import candidate_source_files
    from prepare_trace_pilot import create_source_snapshot, DEFAULT_EXCLUDES
    from run_aprof_job import run as execute_job
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    for rel,path in candidate_source_files(Path(source)).items():
        target=destination/rel
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,target)
    timer=destination/'op_host/aprof_device_timer.h'
    original=timer.read_text()
    updated=(ROOT/'benchmarks/cannbench/harness/device_timer.h').read_text()
    timer.write_text(updated)
    patch=destination.parent/(destination.name+'-harness.patch')
    patch.write_text(''.join(difflib.unified_diff(original.splitlines(True),updated.splitlines(True),
        fromfile='a/op_host/aprof_device_timer.h',tofile='b/op_host/aprof_device_timer.h')))
    for phase,argv in [('configure',['cmake','-S',str(destination),'-B',str(destination/'build'),'-DCMAKE_BUILD_TYPE=Release']),
                       ('build',['cmake','--build',str(destination/'build'),'-j4'])]:
        report=execute_job(dict(job_id=op+'-'+destination.name+'-'+phase,
            argv=['taskset','-c','40-43',*argv],cwd=str(destination),output_dir=str(destination.parent/(destination.name+'-'+phase)),
            timeout_seconds=1200,environment={'OMP_NUM_THREADS':'2','MKL_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'}))
        if report['status']!='passed':
            raise RuntimeError(f'measurement harness build failed: {destination}/{phase}')
    snapshot=destination.parent/(destination.name+'-source.tar')
    create_source_snapshot(destination,snapshot,root_label=f'{op}/source',
        excludes=DEFAULT_EXCLUDES+('results.json','harness.patch','harness_manifest.json'))
    return dict(source_snapshot_path=str(snapshot),source_snapshot_sha256=sha(snapshot),
        harness_patch_path=str(patch),harness_patch_sha256=sha(patch))

def init_run(run, parent, capture_replay=False, reuse_verifier=False, method_parent=None,single_live_context=False):
    from collect_level1_traces import Campaign
    campaign = Campaign(parent)
    if run.exists():
        raise FileExistsError(run)
    run.mkdir(parents=True)
    roster = {}
    for op in campaign.manifest['operators']:
        entries = []
        measurement_baseline=None
        if capture_replay:
            measurement_baseline=prepare_measurement_tree(campaign.task(op)/'baseline',run/'tasks'/op/'measurement-source/baseline',op)
        for directory in sorted((campaign.task(op) / 'candidates').iterdir()):
            if not directory.is_dir() or not (directory / 'registration.json').exists():
                continue
            identifier = directory.name
            registration = read(directory / 'registration.json')
            campaign.verify_candidate_boundary(op, identifier)
            # Read immutable source CAS directly; never open the parent SQLite
            # through its writable EpisodeStore constructor during continuation.
            for label, tree in [('baseline',campaign.task(op)/'baseline'), ('candidate',directory/'op')]:
                digest = registration['source_hashes'][label]
                hexadecimal = digest.removeprefix('sha256:')
                obj = parent/campaign.split(op)/'episodes.sqlite.objects'/'sha256'/hexadecimal[:2]/hexadecimal[2:]
                if sha(obj) != digest:
                    raise ValueError('parent source CAS digest mismatch')
                with tarfile.open(obj) as archive:
                    frozen = json.load(archive.extractfile('APROF_SOURCE_SNAPSHOT.json'))
                expected = {f['path']:f for f in frozen['files']}
                actual = {p.relative_to(tree).as_posix():p for p in tree.rglob('*') if p.is_file()
                    and not any(fnmatch.fnmatchcase(p.relative_to(tree).as_posix(),pattern) for pattern in frozen['excludes'])}
                if set(actual) != set(expected):
                    raise ValueError('frozen source file set changed')
                for rel,p in actual.items():
                    if p.is_symlink() or sha(p)!=expected[rel]['sha256'] or p.stat().st_mode&0o777!=expected[rel]['mode']:
                        raise ValueError(f'frozen source changed: {op}/{identifier}/{rel}')
            entries.append(dict(identifier=identifier, candidate_id=registration['candidate_id'],
                source_hashes=registration['source_hashes'], registration_path=str(directory / 'registration.json'),
                registration_sha256=sha(directory / 'registration.json'), baseline=str(campaign.task(op) / 'baseline'),
                candidate=str(directory / 'op'), prepared_root=str(campaign.prepared(op)),
                baseline_executable_sha256=sha(campaign.task(op) / 'baseline' / 'build' / op),
                candidate_executable_sha256=sha(directory / 'op' / 'build' / op)))
            if capture_replay:
                entry=entries[-1]
                measured_candidate=run/'tasks'/op/'measurement-source'/identifier
                candidate_binding=prepare_measurement_tree(directory/'op',measured_candidate,op)
                entry['baseline']=str(run/'tasks'/op/'measurement-source/baseline')
                entry['candidate']=str(measured_candidate)
                for label in ('baseline','candidate'):
                    entry[label+'_executable_sha256']=sha(Path(entry[label])/'build'/op)
                entry['measurement_source_binding']=dict(kind='harness_only_measurement_continuation',
                    allowed_changed_paths=['op_host/aprof_device_timer.h'],baseline=measurement_baseline,candidate=candidate_binding)
        roster[op] = entries
    manifest = dict(schema_version='1.0.0', run_id=run.name, parent_run=str(parent),
        parent_delivery_sha256=sha(parent / 'delivery_manifest.json'), created_at=now(),
        host=socket.gethostname(), physical_device=0, logical_device=0, cpu_affinity=[8],
        operators=campaign.manifest['operators'], train_operators=campaign.manifest['train_operators'],
        validation_operators=campaign.manifest['validation_operators'], candidates=roster,
        purpose='measurement_continuation_of_frozen_roster', max_device_jobs=1, hosts=['local'],
        source_changes_allowed=False, graph_policy_updates=False,
        capture_replay=capture_replay,reuse_verifier=reuse_verifier,
        single_live_context=single_live_context,
        calibration_scope='per_operator_before_and_after' if single_live_context else 'global_pilot_then_per_operator',
        method_parent_run=None if method_parent is None else str(Path(method_parent).resolve()),
        acceptance=dict(max_cv=.05, min_speedup_lcb=1.03, max_case_regression=.03,
                        max_aa_role_bias=.02, max_aa_session_shift=.02),
        pilot=dict(cases=CASES, cells=[dict(precondition_samples=p, reverse_startup=r)
                   for p, r in [(0, False), (1, False), (1, True), (0, True)]],
                   selection='precondition=1 requires both startup orders and their session comparison to pass; no candidate feedback'),
        measurement=dict(pairs=30, warmup=10, repeat=100, checkpoint_every_pair=False,
                         case_ids=list(range(1,21)), output_storage='local scratch then immutable shared archive',
                         precondition_samples=1,
                         concurrency=('all 16 local chip locks held; one live ACL process per role sample; wait for exit before next role'
                            if single_live_context else 'all 16 local chip locks held; only one active timing request; two idle/resident ACL contexts alternate samples')))
    save(run / 'run-manifest.json', manifest)
    (run / 'setup').mkdir(exist_ok=True)
    for name in ['run_level1_serial.py', 'cannbench_device_timing.py']:
        shutil.copyfile(ROOT / 'scripts' / name, run / 'setup' / name)
    save(run / 'setup' / 'producers.json', {name:sha(run / 'setup' / name)
          for name in ['run_level1_serial.py', 'cannbench_device_timing.py']})
    return manifest

def measure(run, op, identifier, relative, cases, precondition=1, reverse=False):
    global DEFER_INTERRUPTS
    manifest = read(run / 'run-manifest.json')
    entry = next(x for x in manifest['candidates'][op] if x['identifier'] == identifier)
    bindings = read(run/'setup/input-bindings.json')
    if sha(run/'setup/cannbench_device_timing.py') != read(run/'setup/producers.json')['cannbench_device_timing.py']:
        raise ValueError('frozen timing producer changed')
    if sha(entry['registration_path']) != entry['registration_sha256']:
        raise ValueError('frozen registration changed')
    for case in cases:
        for path,digest in bindings['inputs'][op][str(case)].items():
            if not Path(path).is_file() or sha(path)!=digest:
                raise ValueError(f'frozen prepared input changed or missing: {path}')
    output = run / relative
    if (output / 'execution.json').exists():
        previous = read(output / 'execution.json')
        if previous['status'] == 'passed':
            raw = read(output / 'raw_measurements.json')
            if summarize_multicase(raw, cases) != read(output / 'measurement_report.json'):
                raise ValueError('archived measurements changed')
            for label in ('stdout','stderr'):
                if sha(output / (label+'.log')) != previous[label]['sha256']:
                    raise ValueError('archived execution logs changed')
        return previous
    if output.exists():
        raise FileExistsError(f'incomplete archive must be recovered explicitly: {output}')
    scratch = Path('/tmp/aprof-serial') / run.name / relative
    if scratch.exists():
        raise FileExistsError(f'unfinished scratch must be preserved/recovered: {scratch}')
    scratch.mkdir(parents=True)
    candidate = entry['baseline'] if 'calibration' in relative.parts else entry['candidate']
    argv = [PYTHON, str(run / 'setup/cannbench_device_timing.py'), 'measure', '--baseline', entry['baseline'],
        '--candidate', candidate, '--cases', ','.join(map(str,cases)), '--device', '0', '--output', str(scratch),
        '--input-root', entry['prepared_root'], '--external-lock', '--precondition-samples', str(precondition),
        '--case-checkpoints-only']
    if reverse:
        argv.append('--reverse-startup')
    if manifest.get('reuse_verifier'):
        argv.append('--reuse-verifier')
    if manifest.get('capture_replay'):
        argv.append('--capture-replay')
    if manifest.get('single_live_context'):
        argv.append('--single-live-context')
    env = dict(os.environ, ASCEND_RT_VISIBLE_DEVICES=str(manifest['physical_device']),
        OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
    for key in list(env):
        if key.startswith('APROF_CALIBRATION_'):
            del env[key]
    shell_argv = ['taskset', '-c', ','.join(map(str,manifest['cpu_affinity'])), 'bash', '-c',
        'source /usr/local/Ascend/cann-9.0.0/set_env.sh; export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:${LD_LIBRARY_PATH:-}; exec "$@"',
        'aprof-serial', *argv]
    source_binding = dict(entry)
    source_binding['actual_candidate'] = candidate
    source_binding['actual_candidate_source_hash'] = entry['source_hashes']['baseline' if candidate==entry['baseline'] else 'candidate']
    source_binding['input_bindings_sha256'] = sha(run/'setup/input-bindings.json')
    for label, path in [('baseline', entry['baseline']), ('candidate', candidate)]:
        actual = sha(Path(path) / 'build' / op)
        expected = entry[('baseline' if candidate == entry['baseline'] else label) + '_executable_sha256']
        if actual != expected:
            raise ValueError('frozen executable changed')
    started = now()
    save(scratch / 'started.json', dict(argv=argv, shell_argv=shell_argv, cwd=str(ROOT), host=socket.gethostname(),
        physical_device=manifest['physical_device'], started_at=started, source_binding=source_binding))
    print(json.dumps(dict(stage='started', op=op, candidate=identifier, path=str(relative), timestamp=started)), flush=True)
    with (scratch / 'stdout.log').open('w') as stdout, (scratch / 'stderr.log').open('w') as stderr:
        # Defer signals until Popen has returned a handle which cleanup can
        # terminate. Repeated termination signals cannot interrupt that cleanup.
        DEFER_INTERRUPTS = True
        try:
            p = subprocess.Popen(shell_argv, cwd=ROOT, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
        except BaseException:
            DEFER_INTERRUPTS = False
            raise
        try:
            DEFER_INTERRUPTS = False
            if PENDING_SIGNAL is not None:
                raise KeyboardInterrupt(f'controller received signal {PENDING_SIGNAL} during process startup')
            code = p.wait(timeout=3600)
        except BaseException:
            DEFER_INTERRUPTS = True
            os.killpg(p.pid, signal.SIGTERM)
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(p.pid, signal.SIGKILL)
                p.wait()
            code = p.returncode
            raise
        finally:
            execution = dict(schema_version='1.0.0', argv=argv, shell_argv=shell_argv, cwd=str(ROOT),
                host=socket.gethostname(), physical_device=manifest['physical_device'], logical_device=0,
                started_at=started, finished_at=now(), exit_status=p.returncode,
                status='passed' if p.returncode == 0 else 'failed', source_binding=source_binding,
                timing_producer_sha256=sha(run / 'setup/cannbench_device_timing.py'),
                controller_sha256=sha(__file__),
                stdout=dict(path=str(scratch / 'stdout.log'), sha256=sha(scratch / 'stdout.log')),
                stderr=dict(path=str(scratch / 'stderr.log'), sha256=sha(scratch / 'stderr.log')))
            save(scratch / 'execution.json', execution)
            output.parent.mkdir(parents=True, exist_ok=True)
            staging = output.with_name(output.name+'.partial')
            shutil.copytree(scratch, staging)
            os.replace(staging, output)
            DEFER_INTERRUPTS = False
    print(json.dumps(dict(stage='finished', op=op, candidate=identifier, path=str(relative), exit_status=code)), flush=True)
    return execution

def probe_capture(run, parent, method_parent=None, *, single_live_context=False,probe_cases=None):
    """Bounded A/A capability experiment before rebuilding the frozen roster."""
    with exclusive_host():
        run.mkdir(parents=True,exist_ok=False)
        health(run/'health-before.json')
        source=parent/'tasks/exp/baseline'
        tree=source if single_live_context else run/'exp'
        binding=None if single_live_context else prepare_measurement_tree(source,tree,'exp')
        old=read(parent/'tasks/exp/candidates/001/registration.json')
        registration=dict(kind='baseline_measurement_method_control',candidate_id='exp-aa',
            source_hashes={label:old['source_hashes']['baseline'] for label in ('baseline','candidate')})
        save(run/'registration.json',registration)
        entry=dict(identifier='baseline',candidate_id='exp-aa',source_hashes=registration['source_hashes'],
            registration_path=str(run/'registration.json'),registration_sha256=sha(run/'registration.json'),
            baseline=str(tree),candidate=str(tree),prepared_root=str(parent/'tasks/exp/prepared'),
            baseline_executable_sha256=sha(tree/'build/exp'),candidate_executable_sha256=sha(tree/'build/exp'))
        if binding:
            entry['measurement_source_binding']=dict(kind='harness_only_measurement_continuation',
                allowed_changed_paths=['op_host/aprof_device_timer.h'],baseline=binding,candidate=binding)
        selected_cases=probe_cases or CASES
        manifest=dict(schema_version='1.0.0',run_id=run.name,parent_run=str(parent),operators=['exp'],
            candidates={'exp':[entry]},physical_device=0,cpu_affinity=[8],capture_replay=not single_live_context,reuse_verifier=True,
            single_live_context=single_live_context,probe_cases=selected_cases,
            method_parent_run=None if method_parent is None else str(Path(method_parent).resolve()),
            kind='measurement_method_AA_probe',candidate_optimization_feedback=False)
        save(run/'run-manifest.json',manifest)
        (run/'setup').mkdir()
        for name in ['run_level1_serial.py','cannbench_device_timing.py']:
            shutil.copyfile(ROOT/'scripts'/name,run/'setup'/name)
        save(run/'setup/producers.json',{name:sha(run/'setup'/name) for name in ['run_level1_serial.py','cannbench_device_timing.py']})
        inputs={}
        for case in selected_cases:
            path=Path(entry['prepared_root'])/f'case_{case:02d}'/'metadata.json'
            metadata=read(path)
            inputs[str(case)]={str(p):sha(p) for p in [path,Path(metadata['input'])]}
        save(run/'setup/input-bindings.json',dict(inputs={'exp':inputs}))
        reports=[]
        for label,reverse in [('normal',False),('reverse',True)]:
            rel=Path('calibration')/label
            execution=measure(run,'exp','baseline',rel,selected_cases,1,reverse)
            if execution['exit_status']!=0:
                save(run/'selection.json',dict(accepted=False,reason='Measurement capability or correctness failed',execution=str(run/rel/'execution.json')))
                return
            reports.append(read(run/rel/'measurement_report.json'))
        decision=compare_controls(*reports,expected_cases=selected_cases)
        decision['artifact_paths']=[str(run/'calibration'/label/'measurement_report.json') for label in ('normal','reverse')]
        save(run/'selection.json',decision)
        health(run/'health-after.json')
        print(json.dumps(decision),flush=True)

def seal_inputs(run):
    """Freeze all prepared inputs before allowing the collector near old paths."""
    manifest=read(run/'run-manifest.json')
    parent=Path(manifest['parent_run'])
    inputs={}
    rosters={}
    for op,entries in manifest['candidates'].items():
        roster_path=parent/'tasks'/op/'frozen-roster.json'
        roster=read(roster_path)
        old={c['candidate_id']:c for c in roster['candidates']}
        if set(old)!={c['candidate_id'] for c in entries}:
            raise ValueError('continuation candidate roster differs from frozen parent')
        for entry in entries:
            if old[entry['candidate_id']]['source_hashes']!=entry['source_hashes']:
                raise ValueError('continuation source identity differs from frozen parent')
        rosters[op]=dict(path=str(roster_path),sha256=sha(roster_path))
        inputs[op]={}
        for case in range(1,21):
            path=Path(entries[0]['prepared_root'])/f'case_{case:02d}'/'metadata.json'
            metadata=read(path)
            files=[path]+[Path(metadata[key]) for key in ('input','x','mask','x1','x2','x3','golden') if key in metadata]
            # Oracle references may be named expected/output_ref in adapters;
            # existing timing verification remains authoritative for all outputs.
            inputs[op][str(case)]={str(p):sha(p) for p in files}
    save(run/'setup/input-bindings.json',dict(schema_version='1.0.0',inputs=inputs,parent_rosters=rosters))
    source=Path(__file__).resolve()
    target=run/'setup'/('controller-'+sha(source).removeprefix('sha256:')+'.py')
    if not target.exists(): shutil.copyfile(source,target)
    save(run/'setup/active-controller.json',dict(path=str(target),sha256=sha(target)))

def compare_controls(before, after, expected_cases=None):
    expected_cases=CASES if expected_cases is None else expected_cases
    reasons = []
    rows = []
    if not before['stable'] or not after['stable']:
        reasons.append('A/A has missing samples, incorrect units, or CV above 5%')
    a = {c['case_id']:c for c in before['per_case']}
    b = {c['case_id']:c for c in after['per_case']}
    if (not expected_cases or len(set(expected_cases))!=len(expected_cases)
            or set(a) != set(expected_cases) or set(b) != set(expected_cases)
            or len(before['per_case']) != len(expected_cases) or len(after['per_case']) != len(expected_cases)
            or before.get('case_ids') != expected_cases or after.get('case_ids') != expected_cases):
        reasons.append('control case sets differ from the complete frozen sentinel set')
    for case in sorted(set(a) & set(b)):
        x, y = a[case], b[case]
        scalars = [v.get(key) for v in (x,y) for key in ('baseline_median_ns','candidate_median_ns','speedup')]
        arrays = [v.get(key) for v in (x,y) for key in ('baseline_samples_ns','candidate_samples_ns')]
        if (any(type(v) not in (int,float) or not math.isfinite(v) or v<=0 for v in scalars)
                or any(not isinstance(v,list) or len(v)<30 or any(type(n) not in (int,float)
                    or not math.isfinite(n) or n<=0 for n in v) for v in arrays)):
            reasons.append(f'case {case}: invalid or missing control data')
            rows.append(dict(case_id=case, passed=False, reason='invalid or missing control data'))
            continue
        shifts = {label:abs(y[label+'_median_ns']/x[label+'_median_ns']-1)
                  for label in ('baseline', 'candidate')}
        shifts['pooled'] = abs(statistics.median(y['baseline_samples_ns']+y['candidate_samples_ns']) /
                               statistics.median(x['baseline_samples_ns']+x['candidate_samples_ns']) - 1)
        biases = [abs(x['speedup']-1), abs(y['speedup']-1)]
        passed = max([*shifts.values(), *biases]) <= .02
        if not passed:
            reasons.append(f'case {case}: session drift or A/A role bias exceeds 2%')
        rows.append(dict(case_id=case, shifts=shifts, role_bias=biases, passed=passed))
    return dict(accepted=not reasons, reason='; '.join(reasons) if reasons else 'All cases pass CV, A/A bias and session reproducibility thresholds', per_case=rows)

def pilot(run):
    with exclusive_host():
        health(run / 'calibration/health-before.json')
        results = []
        for i, cell in enumerate(read(run/'run-manifest.json')['pilot']['cells']):
            rel = Path('calibration') / f'cell-{i}'
            measure(run, 'exp', '001', rel, CASES, cell['precondition_samples'], cell['reverse_startup'])
            results.append(read(run / rel / 'measurement_report.json'))
        decision = compare_controls(results[1], results[2])
        decision.update(schema_version='1.0.0', precondition_samples=1, reverse_startup=False,
            artifact_paths=[str(run/'calibration'/f'cell-{i}'/'measurement_report.json') for i in range(4)],
            diagnostic_unconditioned=compare_controls(results[0], results[3]),
            candidate_results_observed=False)
        save(run / 'calibration/selection.json', decision)
        health(run / 'calibration/health-after.json')
        print(json.dumps(decision), flush=True)

def collect(run, operators=None):
    manifest = read(run/'run-manifest.json')
    if manifest.get('calibration_scope')=='per_operator_before_and_after':
        selection=dict(precondition_samples=manifest['measurement']['precondition_samples'])
    else:
        selection = read(run/'calibration/selection.json')
        if not selection['accepted']:
            raise ValueError('serial pilot did not qualify; candidate performance remains sealed')
    with exclusive_host():
        for op in operators or manifest['operators']:
            if op not in manifest['operators']:
                raise ValueError('operator is outside frozen roster')
            task = run/'tasks'/op
            if (task/'calibration-decision.json').exists():
                continue
            health(task/'health-before.json')
            control_paths = []
            # Two independently started A/A sessions precede each frozen batch.
            for label, reverse in [('before',False), ('startup-reversed',True)]:
                rel = Path('tasks')/op/'calibration'/label
                measure(run,op,'001',rel,CASES,selection['precondition_samples'],reverse)
                control_paths.append(str(run/rel/'measurement_report.json'))
            decision = compare_controls(*[read(p) for p in control_paths])
            if decision['accepted']:
                for candidate in manifest['candidates'][op]:
                    measure(run,op,candidate['identifier'],Path('tasks')/op/'measurements'/candidate['identifier'],
                            list(range(1,21)),selection['precondition_samples'])
                rel = Path('tasks')/op/'calibration'/'after'
                measure(run,op,'001',rel,CASES,selection['precondition_samples'])
                control_paths.append(str(run/rel/'measurement_report.json'))
                final = compare_controls(read(control_paths[0]), read(control_paths[-1]))
                decision['post_batch_control'] = final
                if not final['accepted']:
                    decision['accepted'] = False
                    decision['reason'] = 'Post-batch control failed: ' + final['reason']
            decision['artifact_paths'] = control_paths
            save(task/'calibration-decision.json',decision)
            health(task/'health-after.json')
            print(json.dumps(dict(op=op,calibration=decision)),flush=True)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['init','seal-inputs','pilot','collect','probe-capture','probe-single'])
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--parent',type=Path,default=ROOT/'.aprof/runs/level1-20260907T152600Z')
    p.add_argument('--operators')
    p.add_argument('--capture-replay',action='store_true')
    p.add_argument('--reuse-verifier',action='store_true')
    p.add_argument('--single-live-context',action='store_true')
    p.add_argument('--probe-cases')
    p.add_argument('--method-parent',type=Path)
    args=p.parse_args()
    run=args.run.resolve()
    if args.command=='init':
        with exclusive_host():
            init_run(run,args.parent.resolve(),args.capture_replay,args.reuse_verifier,args.method_parent,args.single_live_context)
    elif args.command=='probe-capture':
        probe_capture(run,args.parent.resolve(),args.method_parent)
    elif args.command=='probe-single':
        probe_capture(run,args.parent.resolve(),args.method_parent,single_live_context=True,
            probe_cases=[int(c) for c in args.probe_cases.split(',')] if args.probe_cases else None)
    elif args.command=='seal-inputs':
        seal_inputs(run)
    elif args.command=='pilot':
        pilot(run)
    else:
        collect(run,args.operators.split(',') if args.operators else None)

if __name__=='__main__':
    def interrupted(signum, frame):
        global PENDING_SIGNAL
        if DEFER_INTERRUPTS:
            PENDING_SIGNAL=signum
            return
        raise KeyboardInterrupt(f'controller received signal {signum}')
    signal.signal(signal.SIGTERM,interrupted)
    signal.signal(signal.SIGINT,interrupted)
    main()
