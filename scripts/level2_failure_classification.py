#!/usr/bin/env python3
"""Read-only, positive-evidence attribution of a terminal source attempt.

Unknown failures remain infrastructure_blocked. Exception names and nonzero exit
codes never establish source failure by themselves. The returned file hashes must
be frozen in feedback and replayed by the finalizer. Callers retain every actual
execution/cost record and do not close feedback for infrastructure_blocked.

This deliberately recognizes a small set of proofs; unsupported diagnostics,
crashes, missing outputs and arbitrary guard-script failures require investigation.
"""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import re

VERSION = 'level2_failure_classification_v1'
INFRA_TYPES = {'TimeoutExpired', 'TimeoutError', 'KeyboardInterrupt', 'OSError',
    'FileNotFoundError', 'PermissionError', 'ConnectionError', 'BrokenPipeError',
    'BlockingIOError', 'InterruptedError', 'IsADirectoryError', 'NotADirectoryError',
    'ProcessLookupError', 'ChildProcessError', 'MemoryError', 'EOFError'}
# Restrict compiler admission to semantic diagnostics at an original source file.
# Missing headers/libraries, tool crashes and resource errors are never admitted.
SEMANTIC_DIAGNOSTIC = re.compile(r'^(?:use of undeclared identifier\b|undeclared identifier\b|'
    r'no matching (?:function|member function|constructor)\b|no member named\b|'
    r'expected (?:expression|identifier|unqualified-id|type|parameter)\b|'
    r'invalid operands to binary expression\b|cannot initialize\b|'
    r'incompatible (?:pointer|integer|function)\b|redefinition of\b|'
    r'too (?:few|many) arguments\b)')
INFRA_LOG = re.compile(r'no such file|file not found|command not found|permission denied|'
    r'no space left|disk quota|cannot execute|cannot find -l|unable to (?:execute|load)|'
    r'error while loading|internal compiler error|segmentation fault|killed signal|'
    r'out of memory|\btimed? ?out\b|\bterminated\b', re.I)


class Unproven(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Unproven(reason)


def canonical_path(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'noncanonical evidence path is unsupported')
    require(not any(p.is_symlink() for p in (path, *path.parents)), 'symlink evidence is unsupported')
    require(path == path.resolve(), 'noncanonical evidence path is unsupported')
    return path


class Evidence:
    def __init__(self):
        self.refs = {}

    def path(self, path):
        path = canonical_path(path)
        require(path.is_file(), 'missing evidence: ' + str(path))
        return path

    def read(self, path, *, text=False):
        path = self.path(path)
        raw = path.read_bytes()
        self.refs[str(path)] = {'path': str(path), 'sha256': 'sha256:' + hashlib.sha256(raw).hexdigest()}
        return raw.decode() if text else json.loads(raw)

    def file(self, path):
        path = self.path(path)
        h = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                h.update(block)
        ref = {'path': str(path), 'sha256': 'sha256:' + h.hexdigest()}
        self.refs[str(path)] = ref
        return ref

    def bound(self, ref, expected=None, *, text=False, binary=False):
        require(isinstance(ref, dict) and set(ref) >= {'path', 'sha256'}, 'missing evidence pointer')
        path = self.path(ref['path'])
        if expected is not None:
            require(path == Path(expected).absolute(), 'evidence points outside expected location')
        actual = self.file(path)
        require(actual['sha256'] == ref['sha256'], 'evidence hash differs: ' + str(path))
        return actual if binary else self.read(path, text=text)


def infra_error(error):
    return isinstance(error, dict) and error.get('type') in INFRA_TYPES


def process(row, exit_code=0):
    code = row.get('exit_status', row.get('exit_code'))
    require(type(code) is int and code == exit_code, 'process exit does not establish the required outcome')
    require(row.get('finished_at', row.get('ended_at')) is not None and row.get('started_at') is not None,
            'process completion is not recorded')
    require(not row.get('timed_out') and not infra_error(row.get('error')), 'process timed out or failed infrastructure')
    if exit_code == 0:
        require(not row.get('error') and row.get('status', 'passed') == 'passed', 'process did not complete successfully')


def health(e, root):
    for name in ('health-before.json', 'health-after.json'):
        row = e.read(root / name)
        require(row.get('status') == 'passed' and not row.get('error')
                and row.get('exit_status', row.get('exit_code')) == 0,
                'healthy before/after records are required')


def stage_location(e, parent, stage):
    sid = stage.get('stage_id', '')
    prefix = parent.name + '-'
    require(sid.startswith(prefix) and re.fullmatch(r'[A-Za-z0-9_-]+', sid[len(prefix):]),
            'stage does not identify this candidate')
    directory = parent / 'stages' / sid[len(prefix):]
    require(e.read(directory / 'result.json') == stage, 'stage result differs from recorded evidence')
    require(stage.get('candidate_id') == parent.name, 'stage candidate differs')
    return directory


def compiler_failure(e, parent, stage):
    require(stage.get('error', {}).get('type') == 'RuntimeError', 'compiler failure is not positively identified')
    build = parent / 'build'
    configure = e.read(build / 'configure-execution/execution.json')
    process(configure)
    require(configure.get('argv') == ['cmake', '-S', str(build), '-B', str(build / 'build')],
            'configure argv differs')
    execution = e.read(build / 'build-execution/execution.json')
    require(execution.get('argv') == ['cmake', '--build', str(build / 'build'), '-j2'], 'build argv differs')
    code = execution.get('exit_status')
    require(type(code) is int and code in (1, 2), 'build exit is not a normal compiler failure')
    process(execution, code)
    require(stage['error']['message'] == f'process failed ({code}): cmake'
            and execution.get('error') == stage['error']['message'], 'compiler wrapper error differs')
    logs = '\n'.join(e.read(build / ('build-execution/' + f), text=True) for f in ('stdout.log', 'stderr.log'))
    require(not INFRA_LOG.search(logs), 'build logs contain an infrastructure/tool failure')
    for line in logs.splitlines():
        match = re.match(r'^(/[^\n]+?):([0-9]+):([0-9]+): error: (.+)$', line)
        if match is None or not SEMANTIC_DIAGNOSTIC.match(match[4]):
            continue
        path = Path(match[1])
        if not path.is_relative_to(parent / 'op') or path.suffix not in ('.asc', '.h', '.hpp', '.cpp'):
            continue
        lines = e.read(path, text=True).splitlines()
        require(1 <= int(match[2]) <= len(lines), 'diagnostic location exceeds original source')
        return 'original_source_compiler_diagnostic', 'Completed compiler reported a supported semantic error at original candidate source.'
    raise Unproven('no supported original-source compiler diagnostic; generated adapter or unknown errors require investigation')


def verifier_failure(e, task, parent, stage, directory):
    require(stage.get('native_started') is True, 'correctness failed before any confirmed native execution')
    build = e.read(parent / 'build/build_manifest.json')
    # Standalone may succeed before the prepared path fails. Only the failed
    # completion is eligible, never an unrelated earlier oracle result.
    roots = [directory / name for name in ('standalone', 'evidence') if (directory / name / 'completion.json').is_file()]
    failed = [(root, e.read(root / 'completion.json')) for root in roots]
    failed = [(root, row) for root, row in failed if row.get('status') == 'failed']
    require(len(failed) == 1, 'one failed correctness completion is required')
    root, completion = failed[0]
    require(not completion.get('health_error') and completion.get('error') == stage.get('error'),
            'correctness error is not the completed oracle failure')
    health(e, root)
    request = e.read(root / 'request.json')
    oracle = task / 'baseline/scripts/verify_result.py'
    oracle_ref = e.file(oracle)
    if root.name == 'standalone':
        require(request.get('verifier') == oracle_ref, 'standalone request does not bind original oracle')
        require(request.get('standalone') == build.get('standalone'), 'standalone request binary differs')
    else:
        require(request.get('verifier_hash') == oracle_ref['sha256'], 'prepared request does not bind original oracle')
        require(request.get('role_build_hash') == e.file(parent / 'build/build_manifest.json')['sha256'], 'prepared build differs')
    # Exact stdout/result agreement plus original-verifier identity distinguishes
    # a numeric failure from generic ImportError/OSError/RuntimeError in Python.
    for case in sorted(root.glob('case_[0-9][0-9]')):
        verify_path = case / 'verify.execution.json'
        if not verify_path.is_file():
            verify_path = case / 'verify/execution.json'
        if not verify_path.is_file():
            continue
        verify = e.read(verify_path)
        if verify.get('exit_status', verify.get('exit_code')) != 1:
            continue
        process(verify, 1)
        error = verify.get('error')
        require(isinstance(error, dict) and error.get('type') == 'RuntimeError'
                and error.get('message') in ('original oracle main exited 1', 'command exited 1'),
                'verifier exited without a known numeric-result termination')
        require(stage.get('error') == error, 'stage error differs from oracle termination')
        argv = verify.get('argv', [])
        require(str(oracle) in argv and '--metadata' in argv and argv.count('--metadata') == 1,
                'verifier argv does not invoke the original oracle')
        metadata_path = Path(argv[argv.index('--metadata') + 1])
        # Relocated oracle metadata needs its own reviewed proof. Until supported
        # here, keep it unfinished instead of inferring from a similarly named file.
        require(metadata_path == case / 'verification-metadata.json', 'oracle metadata relocation is not yet classified')
        metadata = e.read(metadata_path)
        require(int(metadata['case_id']) == int(case.name.removeprefix('case_')), 'oracle case identity differs')
        if 'verifier' in verify:
            require(verify['verifier'] == oracle_ref, 'executed original oracle differs')
            e.bound(verify['metadata'], metadata_path)
            for ref in verify.get('oracle_dependencies', []):
                e.bound(ref, binary=True)
        native_path = case / 'native/execution.json' if root.name == 'standalone' else case / 'native.execution.json'
        native = e.read(native_path)
        process(native)
        if root.name == 'standalone':
            binary = build['standalone']
            e.bound(binary, binary=True)
            require(native.get('argv', [None])[0] == binary['path'], 'native standalone binary differs')
        else:
            native_record = e.read(case / 'native.json')
            role = request.get('role')
            identity = build.get('roles', {}).get(role, {})
            require(identity and native_record.get('source_sha256') == identity.get('source_sha256')
                    and native_record.get('kernel_symbols') == identity.get('kernel_symbols')
                    and native_record.get('mode') == 'correctness' and native_record.get('exit_code') == 0
                    and all(native_record.get(k) is True for k in ('stream_destroyed', 'context_destroyed', 'finalized')),
                    'prepared native correctness/teardown/source proof is incomplete')
        result_name = 'precision.json' if (case / 'precision.json').is_file() else 'result.json'
        result = e.read(case / result_name)
        require(result.get('passed', result.get('precision_pass')) is False
                and result.get('case_id') == metadata['case_id'], 'original verifier has no explicit failed numeric result')
        stdout_path = Path(str(verify_path).removesuffix('.execution.json') + '.stdout.log') if verify_path.name != 'execution.json' else verify_path.parent / 'stdout.log'
        stdout = e.read(stdout_path, text=True)
        objects = []
        for line in stdout.splitlines():
            try:
                objects.append(json.loads(line))
            except (ValueError, TypeError):
                pass
        require(result in objects, 'oracle stdout does not corroborate its failed numeric result')
        # Include produced bytes in failure closure; no missing output counts as
        # numeric evidence, even when the verifier happened to write a result.
        outputs = [Path(v) for k, v in metadata.items() if isinstance(v, str)
                   and (k == 'output' or k.startswith('output_') or k.endswith('_out') or k.endswith('_output'))]
        require(outputs, 'oracle output binding is absent')
        for path in outputs:
            require(path.is_relative_to(case), 'oracle output is outside private correctness case')
            e.file(path)
        return 'original_oracle_numeric_mismatch', 'Healthy completed native execution failed the hash-bound original numeric oracle.'
    raise Unproven('no positively proven original-oracle numeric failure')


def dispatch_failure(e, task, parent, guard):
    root = parent / 'boundary-validation'
    require(e.read(root / 'completion.json') == guard, 'guard differs from recorded completion')
    require(not guard.get('error') and not guard.get('verification_error'),
            'guard preparation, health or verifier error is not positively attributed to source')
    request = e.bound(guard.get('request'), root / 'request.json')
    require(request.get('candidate') == parent.name and request.get('dispatch_logs_required') is True,
            'guard does not bind candidate dispatch')
    e.bound(request.get('script'), task / 'agent/boundary_guard.py', text=True)
    plan = e.bound(request.get('dispatch_plan'), parent / 'dispatch_plan.json')
    build = e.read(parent / 'build/build_manifest.json')
    require(request.get('binary') == build.get('standalone'), 'guard binary differs from build')
    e.bound(request['binary'], binary=True)
    health(e, root)
    for name in ('prepare', 'verify'):
        process(e.read(root / name / 'execution.json'))
    commands = e.read(root / 'inputs/coordinator_commands.json')
    rows = guard.get('cases', [])
    require(len(rows) == len(commands) and rows, 'guard coverage is incomplete')
    expected = {r['tiling_key']: r['kernel_entry'] for r in [*plan['entries'], plan['fallback']]}
    mismatch = False
    for row, command in zip(rows, commands):
        require(row.get('name') == command.get('name') and re.fullmatch(r'[A-Za-z0-9_-]+', row['name']),
                'guard command ordering or name differs')
        require(not row.get('error') and command.get('expected_exit') != 'nonzero',
                'native guard exit is not a successful dispatch check')
        directory = root / 'executions' / row['name']
        native = e.bound(row.get('execution'), directory / 'execution.json')
        process(native)
        require(native.get('argv') == [request['binary']['path'], *command['argv']], 'guard actual argv differs')
        require(row.get('expected_process_passed') is True, 'guard process check was not successful')
        key = command.get('expected_key')
        require(type(key) is int and key in expected and command.get('expected_entry', expected[key]) == expected[key],
                'guard expected entry is absent from the bound dispatch plan')
        logs = [json.loads(line.split('APROF_DISPATCH_JSON:', 1)[1])
                for line in e.read(directory / 'stdout.log', text=True).splitlines()
                if line.startswith('APROF_DISPATCH_JSON:')]
        require(logs == row.get('dispatch_logs'), 'recorded dispatch differs from actual stdout')
        passed = (len(logs) == 1 and type(logs[0].get('tiling_key')) is int
                  and logs[0]['tiling_key'] == key and logs[0].get('kernel_entry') == expected[key])
        require(row.get('dispatch_log_passed') is passed, 'guard dispatch outcome contradicts stdout')
        mismatch |= not passed
    require(mismatch, 'guard has no actual bound dispatch mismatch')
    return 'actual_dispatch_mismatch', 'Healthy successful guard processes emitted dispatch inconsistent with their bound plan.'


def classify_failure(task, parent, stage=None, guard=None):
    """Return a deterministic evidence-bound classification; never execute or write.

    ``stage`` is the first failed, already ledger-bound result, or None when only
    semantic guards failed. Callers must freeze/replay this result in feedback.
    """
    e = Evidence()
    status, rule, reason = 'infrastructure_blocked', 'unproven_failure', 'No positive source-failure proof.'
    try:
        task, parent = canonical_path(task), canonical_path(parent)
        require(parent.parent == task / 'candidates', 'candidate is outside the task')
        if stage is not None:
            require(stage.get('status') == 'failed', 'stage is not a failed terminal execution')
            directory = stage_location(e, parent, stage)
            require(not infra_error(stage.get('error')), 'stage records an infrastructure exception')
            if stage.get('kind') == 'build':
                rule, reason = compiler_failure(e, parent, stage)
            elif stage.get('kind') == 'correctness':
                rule, reason = verifier_failure(e, task, parent, stage, directory)
            else:
                raise Unproven('measurement/runtime/unsupported stage remains unfinished')
        else:
            require(guard is not None and guard.get('status') == 'failed', 'no failed stage or guard')
            rule, reason = dispatch_failure(e, task, parent, guard)
        status = 'source_attempt_failed'
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError, OverflowError) as exc:
        reason = str(exc)
    return {'version': VERSION, 'status': status, 'rule': rule, 'reason': reason,
            'evidence': [e.refs[k] for k in sorted(e.refs)]}
