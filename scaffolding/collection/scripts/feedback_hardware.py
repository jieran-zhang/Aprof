#!/usr/bin/env python3
"""Generic, host-exclusive hardware executor for frozen feedback pilot trees.

Every invocation owns a new evidence directory; completed identical invocations
are verified and returned without executing. Incomplete/failed evidence is never
reused. Timing is delegated unchanged to cannbench_device_timing.py.
Profile protocol v2 skips all ten host warmup iterations before collecting five
complete operator iterations; profiler replay warmup remains ten.
"""
from __future__ import annotations

from aprof_layout import skill_lib
import argparse
import ast
import fnmatch
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scaffolding/collection/scripts'))
from cannbench_device_timing import command_from_metadata, operator_name
from prepare_trace_pilot import DEFAULT_EXCLUDES
from run_level1_serial import exclusive_host, health, now, sha

ENV_SCRIPT = '/usr/local/Ascend/cann-9.0.0/set_env.sh'
PYTHON = '/usr/local/python3.11.15/bin/python3'
PROTOCOL = dict(pairs=30, warmup=10, repeat=100, precondition_samples=1,
                single_live_context=True, reuse_verifier=True,
                capture_replay=False, checkpoint_every_pair=False)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')


def inventory(tree, source=False):
    excludes = DEFAULT_EXCLUDES + ('results.json', 'harness.patch', 'harness_manifest.json') if source else ()
    result = {}
    for path in sorted(Path(tree).rglob('*')):
        rel = path.relative_to(tree).as_posix()
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in excludes):
            continue
        if path.is_symlink():
            raise ValueError(f'symlink is not frozen evidence: {path}')
        if path.is_file():
            result[rel] = sha(path)
    return result


def request_binding(args):
    trees = {'opdir': args.opdir} if args.command in ('build', 'correctness', 'profile') else {
        'baseline': args.baseline, 'candidate': args.baseline if args.command == 'control' else args.candidate}
    binding = dict(command=args.command, cases=args.cases, device=args.device, reverse=args.reverse,
                   protocol=PROTOCOL, trees={}, controller_sha256=sha(__file__),
                   timing_producer_sha256=sha(ROOT / 'scaffolding/collection/scripts/cannbench_device_timing.py'),
                   validator_sha256=sha(ROOT / 'scaffolding/collection/scripts/cannbench_prepared_validate.py'))
    for label, tree in trees.items():
        if tree is None or not tree.is_dir():
            raise ValueError(f'{label} must be an existing frozen source tree')
        row = dict(path=str(tree), sources=inventory(tree, source=True), operator=operator_name(tree))
        if args.command != 'build':
            row['executable_sha256'] = sha(tree / 'build' / row['operator'])
        binding['trees'][label] = row
    if args.command != 'build':
        if args.input_root is None or not args.input_root.is_dir():
            raise ValueError('existing --input-root is required')
        for case in args.cases:
            if not (args.input_root / f'case_{case:02d}/metadata.json').is_file():
                raise ValueError(f'missing prepared metadata for case {case}')
        files = {}
        for case in args.cases:
            metadata_path = args.input_root / f'case_{case:02d}/metadata.json'
            files[str(metadata_path)] = sha(metadata_path)
            metadata = json.loads(metadata_path.read_text())
            for key in ('input', 'x', 'mask', 'x1', 'x2', 'x3', 'golden'):
                if key in metadata:
                    path = Path(metadata[key]).resolve()
                    files[str(path)] = sha(path)
        binding['inputs'] = dict(path=str(args.input_root), files=files)
        if args.command == 'profile':
            binding['profile_protocol'] = profile_protocol(args.opdir, metadata)
    return binding


def shell_command(argv, cpu):
    return ['taskset', '-c', cpu, 'bash', '-c',
            'source ' + ENV_SCRIPT + ' || exit $?; '
            'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:${LD_LIBRARY_PATH:-}; exec "$@"',
            'feedback-hardware', *map(str, argv)]


def run_process(argv, cwd, out, device=0, cpu='8', extra_env=None, timeout=3600):
    """Record each process and kill only its owned process group on interruption."""
    out.mkdir(parents=True, exist_ok=False)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('APROF_CALIBRATION_', 'APROF_TIMING', 'APROF_WARMUP', 'APROF_REPEAT', 'APROF_SAMPLES', 'APROF_CAPTURE'))}
    env.update(ASCEND_RT_VISIBLE_DEVICES=str(device), OMP_NUM_THREADS='2', MKL_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2')
    env.update(extra_env or {})
    command = shell_command(argv, cpu)
    record = dict(argv=list(map(str, argv)), shell_argv=command, cwd=str(cwd), host=socket.gethostname(),
                  physical_device=device, logical_device=0, started_at=now(), environment_overrides=extra_env or {})
    save(out / 'started.json', record)
    process = None
    error = None
    try:
        with (out / 'stdout.log').open('xb') as stdout, (out / 'stderr.log').open('xb') as stderr:
            # Defer controller signals until Popen exposes the owned handle.
            # Do not block them with pthread_sigmask: children inherit that mask.
            pending = []
            handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
            try:
                for sig in handlers:
                    signal.signal(sig, lambda signum, frame: pending.append(signum))
                process = subprocess.Popen(command, cwd=cwd, env=env, stdout=stdout, stderr=stderr, start_new_session=True)
            finally:
                for sig, handler in handlers.items():
                    signal.signal(sig, handler)
            if pending:
                raise KeyboardInterrupt(f'controller received signal {pending[0]} during process startup')
            code = process.wait(timeout=timeout)
            if code:
                raise RuntimeError(f'process failed ({code}): {argv[0]}')
    except BaseException as exc:
        error = str(exc)
        if process is not None:
            previous = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})
            try:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            finally:
                signal.pthread_sigmask(signal.SIG_SETMASK, previous)
        raise
    finally:
        record.update(finished_at=now(), exit_status=None if process is None else process.returncode,
                      status='passed' if error is None and process is not None and process.returncode == 0 else 'failed', error=error)
        save(out / 'execution.json', record)


def launch_count(tree, metadata):
    name = operator_name(tree)
    if name == 'foreach_norm':
        return len(metadata['lengths']) * 2
    if name == 'foreach_addcdiv_scalar':
        source = (tree / 'op_host/foreach_addcdiv_scalar.asc').read_text()
        match = re.search(r'constexpr uint64_t kChunkElements = ([^;]+);', source)
        if match is None:
            raise ValueError('unknown TensorList chunk launch contract')
        def integer(node):
            if isinstance(node, ast.Constant) and type(node.value) is int:
                return node.value
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
                return integer(node.left) * integer(node.right)
            raise ValueError('unsupported chunk expression')
        chunk = integer(ast.parse(re.sub(r'(?<=\d)[uUlL]+\b', '', match.group(1)), mode='eval').body)
        return sum(math.ceil(n / chunk) for n in metadata['lengths'])
    return 1


def profile_kernels(tree):
    """Bind compression to native launch names, including renamed candidates."""
    name = operator_name(tree)
    source = (tree / 'op_host' / (name + '.asc')).read_text()
    kernels = list(dict.fromkeys(re.findall(r'\b([A-Za-z_]\w*)\s*<<<', source)))
    if not kernels:
        raise ValueError('cannot identify native kernel launch names for profile compression')
    return kernels


def profile_protocol(tree, metadata):
    count = launch_count(tree, metadata)
    skip, collect = 10 * count, 5 * count
    if not 0 <= skip <= 1000 or not 1 <= collect <= 5000:
        raise ValueError(f'profile launch budget exceeds installed msprof limits: skip={skip} (0..1000), count={collect} (1..5000)')
    return dict(version='2.0.0', complete_operator_launches=count, warmup=10, repeat=5,
                profiler_replay_warmup=10, launch_skip_before_match=skip, launch_count=collect,
                captured_window='five complete operator iterations after ten host warmup iterations',
                startup='one native prepared-input process; host warmup precedes profiled iterations',
                native_kernel_names=profile_kernels(tree), gate=False)


def execute_stages(args, scratch):
    if args.command == 'build':
        run_process(['cmake', '-S', args.opdir, '-B', args.opdir / 'build', '-DCMAKE_BUILD_TYPE=Release'],
                    args.opdir, scratch / 'configure', cpu='40-43', timeout=1200)
        run_process(['cmake', '--build', args.opdir / 'build', '-j4'], args.opdir, scratch / 'build', cpu='40-43', timeout=1200)
        save(scratch / 'binary.json', dict(path=str(args.opdir / 'build' / operator_name(args.opdir)),
                                         sha256=sha(args.opdir / 'build' / operator_name(args.opdir))))
    elif args.command == 'correctness':
        run_process([PYTHON, ROOT / 'scaffolding/collection/scripts/cannbench_prepared_validate.py', '--opdir', args.opdir,
                     '--input-root', args.input_root, '--output', scratch / 'correctness', '--device', '0',
                     '--cases', ','.join(map(str, args.cases))], args.opdir, scratch / 'process')
    elif args.command in ('measure', 'control'):
        argv = [PYTHON, ROOT / 'scaffolding/collection/scripts/cannbench_device_timing.py', 'measure', '--baseline', args.baseline,
                '--candidate', args.baseline if args.command == 'control' else args.candidate,
                '--input-root', args.input_root, '--output', scratch / 'measurement', '--device', '0',
                '--cases', ','.join(map(str, args.cases)), '--pairs', '30', '--warmup', '10', '--repeat', '100',
                '--external-lock', '--precondition-samples', '1', '--case-checkpoints-only', '--reuse-verifier', '--single-live-context']
        if args.reverse:
            argv.append('--reverse-startup')
        run_process(argv, ROOT, scratch / 'process')
    else:
        metadata = json.loads((args.input_root / f'case_{args.cases[0]:02d}/metadata.json').read_text())
        argv = command_from_metadata(args.opdir, metadata, 0, scratch / 'output.bin')
        protocol = profile_protocol(args.opdir, metadata)
        save(scratch / 'profile-protocol.json', dict(protocol, artifact_path_mapping={
            'scratch_root': str(scratch), 'archive_root': str(args.output),
            'mapping': 'replace scratch_root prefix with archive_root; relative paths preserved; scratch retained'}))
        run_process(['msprof', 'op', '--warm-up=10',
                     f"--launch-skip-before-match={protocol['launch_skip_before_match']}",
                     f"--launch-count={protocol['launch_count']}", '--aic-metrics=Default',
                     '--output=' + str(scratch / 'raw'), *argv], args.opdir, scratch / 'process', timeout=1800,
                    extra_env={'APROF_TIMING': '1', 'APROF_WARMUP': '10', 'APROF_REPEAT': '5', 'APROF_SAMPLES': '1'})
        for kernel in protocol['native_kernel_names']:
            run_process([PYTHON, skill_lib() / 'skills/ascendc-aprof-profiling/scripts/compress_msprof.py', '--input', scratch / 'raw',
                         '--op-name', kernel, '--output', scratch / (kernel + '-symptoms.json')], ROOT, scratch / ('compress-' + kernel))


def run(args):
    with exclusive_host():
        binding = request_binding(args)
        if args.output.exists():
            complete = args.output / 'completion.json'
            if complete.is_file():
                old = json.loads(complete.read_text())
                files = inventory(args.output)
                files.pop('completion.json', None)
                if old['status'] == 'passed' and old['request'] == binding and old['artifacts'] == files:
                    if args.command == 'build':
                        binary = json.loads((args.output / 'binary.json').read_text())
                        if sha(binary['path']) != binary['sha256']:
                            raise ValueError('completed build binary changed')
                    return old
            raise FileExistsError(f'output is not an identical verified completed invocation: {args.output}')
        scratch = Path(tempfile.mkdtemp(prefix='aprof-feedback-', dir='/tmp'))
        save(scratch / 'request.json', binding)
        started = now()
        status, error = 'failed', None
        try:
            health(scratch / 'health-before.json')
            execute_stages(args, scratch)
            if request_binding(args) != binding:
                raise ValueError('frozen source, executable, producer or input changed during execution')
            health(scratch / 'health-after.json')
            status = 'passed'
        except BaseException as exc:
            error = f'{type(exc).__name__}: {exc}'
            raise
        finally:
            result = dict(status=status, error=error, request=binding, started_at=started, finished_at=now(),
                          host=socket.gethostname(), physical_device=0, scratch=str(scratch), artifacts=inventory(scratch))
            save(scratch / 'completion.json', result)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            staging = args.output.with_name(args.output.name + '.partial')
            shutil.copytree(scratch, staging)
            if args.output.exists():
                raise FileExistsError(args.output)
            os.rename(staging, args.output)
        return result


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'correctness', 'profile', 'measure', 'control'])
    for key in ('opdir', 'baseline', 'candidate', 'input-root', 'output'):
        parser.add_argument('--' + key, type=lambda p: Path(p).resolve(), required=key == 'output')
    parser.add_argument('--device', type=int, choices=[0], default=0)
    parser.add_argument('--cases', default=','.join(map(str, range(1, 21))))
    parser.add_argument('--reverse', action='store_true')
    args = parser.parse_args(argv)
    args.cases = [int(item) for item in args.cases.split(',')]
    if not args.cases or len(args.cases) != len(set(args.cases)) or not all(1 <= c <= 20 for c in args.cases):
        parser.error('cases must be unique IDs in 1..20')
    if args.command == 'profile' and len(args.cases) != 1:
        parser.error('profile requires exactly one selected --cases ID')
    return args


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'controller received signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    result = run(parse_args())
    print(json.dumps({'status': result['status'], 'finished_at': result['finished_at']}))


if __name__ == '__main__':
    main()
