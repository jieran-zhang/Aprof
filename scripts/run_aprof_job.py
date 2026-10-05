#!/usr/bin/env python3
"""Execute one recorded AProf job under a host-local, process-shared device lock."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def dump(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    os.replace(temporary, path)


def sha(path: Path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1048576), b''):
            h.update(part)
    return 'sha256:' + h.hexdigest()


def run(job: dict) -> dict:
    required = {'job_id', 'argv', 'cwd', 'output_dir', 'timeout_seconds'}
    if not required <= job.keys():
        raise ValueError(f'missing job fields: {required - job.keys()}')
    if not isinstance(job['argv'], list) or not job['argv'] or not all(isinstance(x, str) and x for x in job['argv']):
        raise ValueError('argv must be a nonempty string array')
    out = Path(job['output_dir']).resolve()
    out.mkdir(parents=True, exist_ok=True)
    report_path = out / 'execution.json'
    if report_path.exists():
        old = json.loads(report_path.read_text())
        if old['job'] != job:
            raise ValueError('refusing to reuse an output directory for a different job')
        return old
    environment = os.environ.copy()
    environment.update(job.get('environment', {}))
    device = job.get('physical_device')
    lock = None
    if device is not None:
        if type(device) is not int or not 0 <= device < 16:
            raise ValueError('physical_device must be an integer from 0 to 15')
        locks = Path('/tmp/aprof-device-locks')
        locks.mkdir(exist_ok=True)
        lock = (locks / f'device-{device}.lock').open('a+')
        fcntl.flock(lock, fcntl.LOCK_EX)
        environment['ASCEND_RT_VISIBLE_DEVICES'] = str(device)
        # Another idempotent dispatch may have completed while we waited for
        # this device. Never rerun its profiler into the same output tree.
        if report_path.exists():
            old = json.loads(report_path.read_text())
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
            if old['job'] != job:
                raise ValueError('output directory already belongs to a different job')
            return old
    started = now()
    before = time.monotonic()
    timed_out = False
    command = ['bash', '-c',
               'source /usr/local/Ascend/cann-9.0.0/set_env.sh; '
               'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:${LD_LIBRARY_PATH:-}; '
               'exec "$@"', 'aprof-job', *job['argv']]
    try:
        with (out / 'stdout.log').open('wb') as stdout, (out / 'stderr.log').open('wb') as stderr:
            process = subprocess.Popen(command, cwd=job['cwd'], env=environment,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            try:
                exit_code = process.wait(timeout=job['timeout_seconds'])
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                exit_code = process.returncode
        result = {
            'schema_version': '1.0.0', 'kind': 'aprof_execution_report', 'job': job,
            'host': socket.gethostname(), 'physical_device': device,
            'started_at': started, 'finished_at': now(), 'duration_seconds': time.monotonic() - before,
            'exit_code': exit_code, 'status': 'timeout' if timed_out else ('passed' if exit_code == 0 else 'failed'),
            'stdout': {'path': str(out / 'stdout.log'), 'sha256': sha(out / 'stdout.log')},
            'stderr': {'path': str(out / 'stderr.log'), 'sha256': sha(out / 'stderr.log')},
        }
        dump(report_path, result)
        return result
    finally:
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, type=Path)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    job = json.loads(args.job.read_text())
    if args.dry_run:
        print(json.dumps({'status': 'dry_run', 'job': job}, ensure_ascii=False))
        return 0
    result = run(job)
    print(json.dumps({'job_id': job['job_id'], 'status': result['status'], 'report': str(Path(job['output_dir']) / 'execution.json')}))
    return 0 if result['status'] == 'passed' else 2


if __name__ == '__main__':
    raise SystemExit(main())
