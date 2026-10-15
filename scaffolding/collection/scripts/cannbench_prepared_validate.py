#!/usr/bin/env python3
"""Validate all frozen cases with reusable inputs and private output files."""
from __future__ import annotations

import argparse
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

from cannbench_device_timing import dump, sha256
from level2_adapters import prepared_commands, dispatch_command as command_from_metadata, output_paths, is_level2, operator_name


def ensure_input(opdir, case, device, input_root):
    input_root = Path(input_root)
    input_root.mkdir(parents=True, exist_ok=True)
    with (input_root / f'.case-{case}.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        commands = prepared_commands(opdir, case, device, input_root)
        metadata = Path(commands['metadata'])
        if not metadata.exists():
            completed = subprocess.run(commands['prepare_argv'], cwd=opdir, capture_output=True, text=True)
            (input_root / f'case-{case}-prepare.log').write_text(completed.stdout + completed.stderr)
            completed.check_returncode()
        return metadata


def validate(opdir, input_root, output, cases, device):
    opdir, input_root, output = map(lambda p: Path(p).resolve(), (opdir, input_root, output))
    output.mkdir(parents=True, exist_ok=True)
    result = {'schema_version': '1.0.0', 'kind': 'aprof_full_correctness',
              'op_dir': str(opdir), 'case_ids': list(cases), 'case_count': len(cases),
              'passed_count': 0, 'status': 'running', 'oracle': 'unchanged_local_baseline_verifier', 'cases': []}
    if (output / 'correctness.json').exists():
        previous = json.loads((output / 'correctness.json').read_text())
        if previous['status'] in ('passed', 'failed'):
            return previous
        raise ValueError('interrupted correctness output must use a new execution directory')
    env = dict(os.environ, APROF_TIMING='1', APROF_WARMUP='0', APROF_REPEAT='1', APROF_SAMPLES='1',
               OMP_NUM_THREADS='2', OPENBLAS_NUM_THREADS='2', MKL_NUM_THREADS='2')
    for case in cases:
        row = {'case_id': case, 'status': 'failed'}
        directory = output / f'case-{case:02d}'
        directory.mkdir(exist_ok=True)
        try:
            metadata_path = ensure_input(opdir, case, device, input_root)
            metadata = json.loads(metadata_path.read_text())
            argv = command_from_metadata(opdir, metadata, device, directory / 'output.bin')
            kernel = subprocess.run(argv, cwd=opdir, env=env, capture_output=True, text=True, timeout=180)
            # Correctness feedback must not reveal nonsentinel performance.
            kernel_log = '\n'.join(line for line in (kernel.stdout + kernel.stderr).splitlines()
                                   if not line.startswith('APROF_TIMING_JSON:')) + '\n'
            (directory / 'kernel.log').write_text(kernel_log)
            row['kernel_exit_code'] = kernel.returncode
            row['kernel_log'] = str(directory / 'kernel.log')
            kernel.check_returncode()
            if is_level2(opdir): metadata.update(output_paths(operator_name(opdir), metadata, directory/'output.bin'))
            else: metadata['output'] = str(directory / 'output.bin')
            local_metadata = directory / 'metadata.json'
            # Original task metadata deliberately includes special IEEE values;
            # it is preserved as an opaque source artifact, not a JSONL record.
            local_metadata.write_text(json.dumps(metadata, indent=2, allow_nan=True) + '\n')
            verify_argv = [sys.executable, str(opdir / 'scripts/verify_result.py'), '--metadata', str(local_metadata)]
            verification = subprocess.run(verify_argv, cwd=directory, env=env, capture_output=True, text=True, timeout=240)
            (directory / 'verify.log').write_text(verification.stdout + verification.stderr)
            row.update(verify_exit_code=verification.returncode, verify_log=str(directory / 'verify.log'),
                       verifier_sha256='sha256:' + sha256(opdir / 'scripts/verify_result.py'),
                       metadata_sha256='sha256:' + sha256(local_metadata))
            verification.check_returncode()
            row['status'] = 'passed'
            result['passed_count'] += 1
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            row['error'] = {'type': type(error).__name__, 'message': str(error)}
        result['cases'].append(row)
        dump(result, output / 'correctness.json')
        if row['status'] != 'passed':
            break
    result['status'] = 'passed' if result['passed_count'] == len(cases) else 'failed'
    dump(result, output / 'correctness.json')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--opdir', required=True)
    parser.add_argument('--input-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--device', type=int, required=True)
    parser.add_argument('--cases', default=','.join(map(str, range(1, 21))))
    args = parser.parse_args()
    cases = [int(item) for item in args.cases.split(',')]
    if len(cases) != len(set(cases)) or not all(1 <= case <= 20 for case in cases):
        parser.error('cases must be unique IDs between 1 and 20')
    result = validate(args.opdir, args.input_root, args.output, cases, args.device)
    print(json.dumps({key: result[key] for key in ('status', 'case_count', 'passed_count')}))
    return 0 if result['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
