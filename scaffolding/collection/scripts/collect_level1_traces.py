#!/usr/bin/env python3
"""Resumable local Level1 campaign jobs; agents propose, recorded tools execute."""
from __future__ import annotations

from aprof_layout import skill_lib

import argparse
import concurrent.futures
import difflib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import threading
import tarfile
import fnmatch
import socket
from functools import wraps

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(skill_lib() / 'runtime/src'))
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import TraceWriter, execution_record, register_json_artifact, utcnow
from cannbench_device_timing import command_from_metadata, summarize_multicase
from prepare_trace_pilot import create_source_snapshot, DEFAULT_EXCLUDES
from run_aprof_job import dump

DEFAULT_RUN = ROOT / '.aprof/runs/level1-20260907T152600Z'
THREAD_ENV = {'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2'}
WRITER_LOCK = threading.RLock()


def single_writer(function):
    @wraps(function)
    def call(*args, **kwargs):
        with WRITER_LOCK:
            return function(*args, **kwargs)
    return call


def text_items(values):
    """Project rich proposal notes to schema strings without losing their content."""
    return [value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
            for value in values]


def candidate_source_files(tree):
    excludes = DEFAULT_EXCLUDES + ('results.json', 'harness.patch', 'harness_manifest.json')
    return {path.relative_to(tree).as_posix(): path for path in tree.rglob('*') if path.is_file()
            and not any(fnmatch.fnmatchcase(path.relative_to(tree).as_posix(), pattern) for pattern in excludes)}


class Campaign:
    def __init__(self, run=DEFAULT_RUN):
        self.run = Path(run).resolve()
        self.manifest = json.loads((self.run / 'run-manifest.json').read_text())

    def task(self, op):
        if op not in self.manifest['operators']:
            raise ValueError('operator is outside this frozen campaign')
        return self.run / 'tasks' / op

    def split(self, op):
        return 'validation' if op in self.manifest['validation_operators'] else 'train'

    def store(self, op):
        return EpisodeStore(self.run / self.split(op) / 'episodes.sqlite')

    def prepared(self, op):
        policy = self.task(op) / 'input-policy.json'
        return Path(json.loads(policy.read_text())['prepared_root']) if policy.exists() else self.task(op) / 'prepared'

    def accuracy_report(self, op, identifier):
        index = self.task(op) / 'correctness-index.json'
        if index.exists() and identifier in json.loads(index.read_text()):
            return Path(json.loads(index.read_text())[identifier])
        return self.task(op) / 'correctness' / identifier / 'correctness.json'

    def writer(self, op, store):
        return TraceWriter(self.task(op) / 'trace_events.jsonl', run_id=self.run.name,
                           task_id=op, session_id=op + '-campaign', store=store,
                           verify_history_artifacts=False)

    def job(self, op, stage, argv, *, cwd=None, device=None, host='local', timeout=1200, environment=None):
        task = self.task(op)
        argv = [str(v) for v in argv]
        if argv[0] == 'python3':
            argv[0] = '/usr/local/python3.11.15/bin/python3'
        job = {'job_id': op + '-' + stage.replace('/', '-'), 'argv': [str(v) for v in argv],
               'cwd': str(cwd or task / 'baseline'), 'output_dir': str(task / 'executions' / stage),
               'timeout_seconds': timeout, 'environment': {**THREAD_ENV, **(environment or {})}}
        if device is not None:
            job['physical_device'] = device
        path = task / 'jobs' / (stage.replace('/', '-') + '.json')
        if path.exists() and json.loads(path.read_text()) != job:
            previous = json.loads(path.read_text())
            differing = {key for key in previous.keys() | job.keys() if previous.get(key) != job.get(key)}
            completed_path = Path(previous['output_dir']) / 'execution.json'
            if differing <= {'physical_device'} and completed_path.exists():
                completed = json.loads(completed_path.read_text())
                if completed['job'] == previous:
                    return completed
            raise ValueError(f'immutable job configuration differs: {path}')
        if not path.exists():
            dump(path, job)
        cmd = ['/usr/local/python3.11.15/bin/python3', str(ROOT / 'scaffolding/collection/scripts/run_aprof_job.py'), '--job', str(path)]
        if host != 'local':
            cmd = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                   '-o', 'ConnectTimeout=10', host, shlex.join(cmd)]
        started = utcnow()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 180)
        except subprocess.TimeoutExpired as error:
            result = subprocess.CompletedProcess(cmd, 124, '', str(error))
        report_path = Path(job['output_dir']) / 'execution.json'
        if not report_path.exists():
            failure = {'kind': 'transport_failure', 'job': job, 'host': host,
                       'exit_code': result.returncode, 'stdout': result.stdout, 'stderr': result.stderr,
                       'observed_at': utcnow()}
            dump(task / 'executions' / stage / 'transport-failure.json', failure)
            with WRITER_LOCK:
                store = self.store(op)
                ref = register_json_artifact(store, failure)
                identifier = stage.split('/')[0]
                candidate_id = op + '-' + identifier if (task / 'candidates' / identifier).exists() else None
                self.writer(op, store).append('execution_interrupted', {
                    'stage': stage, 'reason': 'Remote execution state is unknown after coordinator transport failure',
                    'execution': execution_record(argv=cmd, cwd=Path.cwd(), host=socket.gethostname(),
                        started_at=started, finished_at=utcnow(), exit_status=result.returncode,
                        log_ref=ref, reason='Transport exit status; not a remote kernel verdict')},
                    candidate_id=candidate_id, attempt_id=candidate_id, artifact_refs=[ref])
            raise RuntimeError(f'job transport failed: {stage}: {result.stderr[-500:]}')
        return json.loads(report_path.read_text())

    @single_writer
    def record(self, op, report, *, candidate=None, stage=None):
        store = self.store(op)
        refs = [store.register_artifact(report[key]['path']) for key in ('stdout', 'stderr')]
        report_ref = register_json_artifact(store, report)
        refs.append(report_ref)
        status = report['status'] if report['status'] in ('passed', 'failed') else 'interrupted'
        candidate_id = None if candidate is None else (candidate if candidate.startswith(op + '-') else op + '-' + candidate)
        self.writer(op, store).append('stage_completed', {
            'stage': stage or report['job']['job_id'], 'status': status,
            'execution': execution_record(argv=report['job']['argv'], cwd=report['job']['cwd'],
                host=report['host'], device=report['physical_device'], started_at=report['started_at'],
                finished_at=report['finished_at'], exit_status=report['exit_code'], log_ref=refs[0]),
            'reason': None if status == 'passed' else 'See recorded command and logs', 'artifact_refs': list(dict.fromkeys(refs))},
            attempt_id=candidate_id, candidate_id=candidate_id,
            event_id=report['job']['job_id'] + '-completed')
        return report_ref

    @single_writer
    def source_snapshot(self, op, tree, name):
        path = self.task(op) / 'artifacts' / f'{name}.tar'
        if not path.exists():
            create_source_snapshot(Path(tree), path, root_label=f'{op}/source',
                                   excludes=DEFAULT_EXCLUDES + ('results.json', 'harness.patch', 'harness_manifest.json'))
        return self.store(op).register_artifact(path)

    def verify_source_identity(self, op, identifier):
        """Reject source changes after registration, including added/deleted files."""
        directory = self.task(op) / 'candidates' / identifier
        self.verify_candidate_boundary(op, identifier)
        registration = json.loads((directory / 'registration.json').read_text())
        store = self.store(op)
        for label, tree in [('baseline', self.task(op) / 'baseline'), ('candidate', directory / 'op')]:
            digest = registration['source_hashes'][label]
            store.verify_artifact(digest)
            with tarfile.open(store.object_path(digest)) as archive:
                manifest = json.load(archive.extractfile('APROF_SOURCE_SNAPSHOT.json'))
            expected = {item['path']: item for item in manifest['files']}
            actual = {}
            for path in tree.rglob('*'):
                rel = path.relative_to(tree).as_posix()
                if any(fnmatch.fnmatchcase(rel, pattern) for pattern in manifest['excludes']):
                    continue
                if path.is_symlink(): raise ValueError('registered source became a symlink')
                if path.is_file(): actual[rel] = path
            if set(expected) != set(actual): raise ValueError('registered source file set changed')
            for rel, path in actual.items():
                item = expected[rel]
                value = 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
                if value != item['sha256'] or path.stat().st_mode & 0o777 != item['mode']:
                    raise ValueError('registered source changed: ' + rel)
        return registration

    def verify_candidate_boundary(self, op, identifier):
        baseline = candidate_source_files(self.task(op) / 'baseline')
        candidate = candidate_source_files(self.task(op) / 'candidates' / identifier / 'op')
        for rel in baseline.keys() | candidate.keys():
            path = Path(rel)
            editable = (path.suffix in ('.asc', '.h', '.cpp') or path.name == 'CMakeLists.txt')
            editable &= path.parts[0] != 'scripts' and path.name != 'aprof_device_timer.h'
            if not editable and (rel not in baseline or rel not in candidate or baseline[rel].read_bytes() != candidate[rel].read_bytes()):
                raise ValueError('candidate changed a protected oracle/harness/support file: ' + rel)

    @single_writer
    def register_candidate(self, op, identifier):
        task = self.task(op)
        if (task / 'frozen-roster.json').exists():
            raise ValueError('candidate registration is closed after final acceptance starts')
        directory = task / 'candidates' / identifier
        plan = json.loads((directory / 'candidate_plan.json').read_text())
        candidate_id = op + '-' + identifier
        if plan['candidate_id'] != candidate_id:
            raise ValueError('candidate ID and directory differ')
        plans = list((task / 'candidates').glob('*/candidate_plan.json'))
        if len(plans) > self.manifest['budget']['candidate_limit']:
            raise ValueError('task candidate budget exceeded')
        baseline, tree = task / 'baseline', directory / 'op'
        self.verify_candidate_boundary(op, identifier)
        patch = []
        old_files, new_files = candidate_source_files(baseline), candidate_source_files(tree)
        for name in sorted(old_files.keys() | new_files.keys()):
            rel = Path(name)
            if not (rel.suffix in ('.asc', '.h', '.cpp') or rel.name == 'CMakeLists.txt'):
                continue
            old = baseline / rel
            path = tree / rel
            before = old.read_text() if old.is_file() else ''
            after = path.read_text() if path.is_file() else ''
            if before != after:
                if rel.name == 'aprof_device_timer.h' or rel.parts[0] == 'scripts':
                    raise ValueError('candidate changed the timing harness or oracle')
                patch.extend(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                fromfile='a/' + str(rel), tofile='b/' + str(rel)))
        patch_path = directory / 'optimization.patch'
        if not patch:
            raise ValueError('non-NOOP candidate has no source intervention')
        patch_path.write_text(''.join(patch))
        store = self.store(op)
        base_hash = self.source_snapshot(op, baseline, 'baseline-instrumented-source')
        candidate_hash = self.source_snapshot(op, tree, identifier + '-source')
        patch_hash = store.register_artifact(patch_path)
        refs = [base_hash, candidate_hash, patch_hash, store.register_artifact(directory / 'candidate_plan.json')]
        mode = plan.get('mode', 'exploration')
        self.writer(op, store).append('candidate_proposed', {
            'mode': mode, 'hypothesis': plan['intent'], 'source_parent_hash': base_hash,
            'patch_hash': patch_hash, 'handler_id': plan['handler_id'],
            'handler_version': plan.get('handler_version', '1.0.0'), 'parameters': plan['parameters'],
            'expected_effects': text_items(plan['expected_effects']), 'alternatives': text_items(plan.get('alternatives', [])),
            'coverage_gap': plan.get('coverage_gap') if mode == 'exploration' else None},
            attempt_id=candidate_id, candidate_id=candidate_id, artifact_refs=refs,
            event_id=op + '-' + identifier + '-proposed')
        registration = {'candidate_id': candidate_id, 'mode': mode,
                        'source_hashes': {'baseline': base_hash, 'candidate': candidate_hash},
                        'patch_artifact_hash': patch_hash, 'plan_hash': refs[-1]}
        dump(directory / 'registration.json', registration)
        return registration

    def build_candidate(self, op, identifier):
        task = self.task(op)
        if (task / 'frozen-roster.json').exists():
            raise ValueError('builds are closed after roster freeze')
        directory = task / 'candidates' / identifier
        if not (directory / 'registration.json').exists():
            self.register_candidate(op, identifier)
        self.verify_source_identity(op, identifier)
        tree = directory / 'op'
        for step, argv in (('configure', ['cmake', '-S', tree, '-B', tree / 'build', '-DCMAKE_BUILD_TYPE=Release']),
                           ('build', ['cmake', '--build', tree / 'build', '-j4'])):
            report = self.job(op, identifier + '/' + step, argv, cwd=tree)
            self.record(op, report, candidate=identifier, stage=step)
            if report['status'] != 'passed':
                return report
        return report

    def correctness(self, op, identifier='baseline', *, host='local', device=0):
        task = self.task(op)
        tree = task / 'baseline' if identifier == 'baseline' else task / 'candidates' / identifier / 'op'
        argv = ['python3', ROOT / 'scaffolding/collection/scripts/cannbench_prepared_validate.py', '--opdir', tree,
                '--input-root', self.prepared(op), '--output', task / 'correctness' / identifier,
                '--device', '0']
        report = self.job(op, identifier + '/correctness', argv, cwd=tree, host=host, device=device, timeout=3600)
        self.record(op, report, candidate=None if identifier == 'baseline' else identifier, stage='correctness')
        return report

    def profile_case(self, op, identifier='baseline', *, case=1, host='local', device=0):
        task = self.task(op)
        if identifier != 'baseline':
            profiled = {path.name for path in (task / 'profiles').iterdir() if path.is_dir() and path.name != 'baseline'} if (task / 'profiles').exists() else set()
            if identifier not in profiled and len(profiled) >= self.manifest['budget']['full_profile_limit']:
                raise ValueError('candidate full-profile budget exceeded')
        correctness = json.loads(self.accuracy_report(op, identifier).read_text())
        if correctness['status'] != 'passed' or correctness['passed_count'] != 20:
            raise ValueError('full correctness must pass before profiling')
        tree = task / 'baseline' if identifier == 'baseline' else task / 'candidates' / identifier / 'op'
        out = task / 'profiles' / identifier / f'case-{case:02d}'
        meta = json.loads((self.prepared(op) / f'case_{case:02d}/metadata.json').read_text())
        command = command_from_metadata(tree, meta, 0, out / 'output.bin')
        # Five complete operator iterations; profiler launch cap preserves all
        # TensorList partial/finalize or chunk launches instead of only one kernel.
        launches = 1
        if op == 'foreach_norm':
            launches = len(meta['lengths']) * 2
        elif op == 'foreach_addcdiv_scalar':
            import re, math
            source = (tree / 'op_host/foreach_addcdiv_scalar.asc').read_text()
            match = re.search(r'constexpr uint64_t kChunkElements = ([^;]+);', source)
            if match is None:
                raise ValueError('unknown TensorList chunk launch contract')
            # The baseline literal is an integer multiplication only.
            import ast
            expression = ast.parse(re.sub(r'(?<=\d)[uUlL]+\b', '', match.group(1)), mode='eval')
            def integer(node):
                if isinstance(node, ast.Constant) and type(node.value) is int: return node.value
                if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult): return integer(node.left)*integer(node.right)
                raise ValueError('unsupported chunk expression')
            chunk = integer(expression.body)
            launches = sum(math.ceil(n / chunk) for n in meta['lengths'])
        argv = ['msprof', 'op', '--warm-up=10', f'--launch-count={launches * 5}',
                '--aic-metrics=Default', '--output=' + str(out / 'raw'), *command]
        out.mkdir(parents=True, exist_ok=True)
        report = self.job(op, identifier + f'/profile-{case:02d}', argv, cwd=tree, host=host, device=device,
                          timeout=1800, environment={'APROF_TIMING': '1', 'APROF_WARMUP': '10', 'APROF_REPEAT': '5', 'APROF_SAMPLES': '1'})
        self.record(op, report, candidate=None if identifier == 'baseline' else identifier, stage='profile')
        if report['status'] == 'passed':
            for kernel in ([op + '_partial_kernel', op + '_finalize_kernel'] if op == 'foreach_norm' else [op + '_kernel']):
                subprocess.run(['python3', str(skill_lib() / 'skills/ascendc-aprof-profiling/scripts/compress_msprof.py'),
                                '--input', str(out / 'raw'), '--op-name', kernel,
                                '--output', str(out / (kernel + '-symptoms.json'))], check=True, capture_output=True)
        return report

    def measure_case(self, op, identifier, *, case, phase='search', host='local', device=0, repeat=100):
        task = self.task(op)
        if phase == 'search' and case not in self.manifest['sentinel_case_ids']:
            raise ValueError('search cannot access nonsentinel timing')
        if phase == 'final' and not (task / 'frozen-roster.json').exists():
            raise ValueError('final timing requires the frozen candidate roster')
        correctness = json.loads(self.accuracy_report(op, identifier).read_text())
        if correctness['status'] != 'passed' or correctness['passed_count'] != 20:
            raise ValueError('timing requires full correctness')
        tree = task / 'baseline' if identifier == 'baseline' else task / 'candidates' / identifier / 'op'
        out = task / 'timing' / phase / identifier / f'case-{case:02d}'
        argv = ['python3', ROOT / 'scaffolding/collection/scripts/cannbench_device_timing.py', 'measure', '--baseline', task / 'baseline',
                '--candidate', tree, '--cases', str(case), '--device', '0', '--output', out,
                '--input-root', self.prepared(op), '--pairs', '30', '--warmup', '10', '--repeat', str(repeat), '--external-lock']
        qualification = self.run / 'calibration/selection.json'
        if not qualification.exists():
            raise ValueError('timing requires a qualified concurrency protocol')
        selection = json.loads(qualification.read_text())
        if not selection['accepted'] or device not in selection['physical_devices_by_host'].get(host, []):
            raise ValueError('physical device is outside the qualified timing topology')
        cpus = selection.get('cpu_affinity_by_host', {}).get(host, {}).get(str(device))
        if cpus:
            argv[0] = '/usr/local/python3.11.15/bin/python3'
            argv = ['/usr/bin/taskset', '--cpu-list', ','.join(map(str, cpus)), *argv]
        report = self.job(op, identifier + f'/{phase}-timing-{case:02d}', argv, cwd=tree, host=host, device=device, timeout=1800)
        self.record(op, report, candidate=None if identifier == 'baseline' else identifier, stage=phase + '_timing')
        return report

    def aggregate(self, op, identifier, phase):
        task = self.task(op)
        cases = self.manifest['sentinel_case_ids'] if phase == 'search' else self.manifest['acceptance_case_ids']
        base = task / 'timing' / phase / identifier
        raw = {'schema_version': '1.0.0', 'operator': op, 'case_ids': cases, 'unit': 'ns',
               'source': 'acl_event', 'pairs': 30, 'warmup': 10, 'repeat': 100,
               'timing_scope': 'complete_operator_device_event_interval', 'complete': True, 'records': [], 'case_sources': []}
        for case in cases:
            path = base / f'case-{case:02d}/raw_measurements.json'
            if not path.exists():
                raw['complete'] = False
                continue
            part = json.loads(path.read_text())
            raw['complete'] &= part['complete']
            for row in part['records']:
                row = dict(row, device=part['device'], host=part['host'])
                raw['records'].append(row)
            raw['case_sources'].append({'case_id': case, 'path': str(path),
                                        'sha256': 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()})
        dump(base / 'raw_measurements.json', raw)
        report = summarize_multicase(raw, cases)
        dump(base / 'measurement_report.json', report)
        return report

    def freeze(self, op):
        task = self.task(op)
        target = task / 'frozen-roster.json'
        if target.exists():
            return json.loads(target.read_text())
        candidates = []
        for path in sorted((task / 'candidates').glob('*/registration.json')):
            self.verify_source_identity(op, path.parent.name)
            item = json.loads(path.read_text())
            item['frozen_plan_sha256'] = 'sha256:' + hashlib.sha256((path.parent / 'candidate_plan.json').read_bytes()).hexdigest()
            candidates.append(item)
        if not candidates or len(candidates) > 6:
            raise ValueError('expected 1..6 frozen candidates')
        value = {'schema_version': '1.0.0', 'run_id': self.run.name, 'operator': op,
                 'split': self.split(op), 'frozen_at': utcnow(), 'candidates': candidates,
                 'sentinel_case_ids': self.manifest['sentinel_case_ids'], 'final_case_ids': list(range(1, 21))}
        dump(target, value)
        self.store(op).register_artifact(target)
        return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, default=DEFAULT_RUN)
    p.add_argument('--operator', required=True)
    p.add_argument('--candidate', default='baseline')
    p.add_argument('--host', default='local', choices=['local', 'decode'])
    p.add_argument('--device', type=int, default=0)
    p.add_argument('--case', type=int, default=1)
    p.add_argument('--phase', default='search', choices=['search', 'final'])
    p.add_argument('action', choices=['register', 'build', 'correctness', 'profile', 'measure', 'aggregate', 'freeze'])
    a = p.parse_args(); campaign = Campaign(a.run)
    if a.action == 'register': value = campaign.register_candidate(a.operator, a.candidate)
    elif a.action == 'build': value = campaign.build_candidate(a.operator, a.candidate)
    elif a.action == 'correctness': value = campaign.correctness(a.operator, a.candidate, host=a.host, device=a.device)
    elif a.action == 'profile': value = campaign.profile_case(a.operator, a.candidate, case=a.case, host=a.host, device=a.device)
    elif a.action == 'measure': value = campaign.measure_case(a.operator, a.candidate, case=a.case, phase=a.phase, host=a.host, device=a.device)
    elif a.action == 'aggregate': value = campaign.aggregate(a.operator, a.candidate, a.phase)
    else: value = campaign.freeze(a.operator)
    print(json.dumps(value, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
