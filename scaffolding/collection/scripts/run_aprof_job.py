#!/usr/bin/env python3
"""Execute one recorded AProf job under a host-local, process-shared device lock."""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
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


def _children(pid):
    children = set()
    for task in Path(f'/proc/{pid}/task').glob('*'):
        try:
            children.update(map(int, (task / 'children').read_text().split()))
        except FileNotFoundError:
            pass
    return children


def _stopped_descendants():
    """Freeze the supervisor's own tree; pidfds prevent PID-reuse signalling."""
    handles = {}
    pending = list(_children(os.getpid()))
    while pending:
        pid = pending.pop()
        if pid in handles:
            continue
        try:
            descriptor = os.pidfd_open(pid)
        except ProcessLookupError:
            continue
        handles[pid] = descriptor
        try:
            signal.pidfd_send_signal(descriptor, signal.SIGSTOP)
        except ProcessLookupError:
            pending.extend(_children(os.getpid()) - handles.keys())
            continue
        while True:
            try:
                state = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
            except FileNotFoundError:
                break
            if state in ('T', 't', 'Z', 'X'):
                break
            time.sleep(.001)
        pending.extend(_children(pid))
        # Exiting intermediate parents may already have reparented children.
        pending.extend(_children(os.getpid()) - handles.keys())
    return handles


def _signal_handles(handles, signum):
    for descriptor in handles.values():
        try:
            signal.pidfd_send_signal(descriptor, signum)
        except ProcessLookupError:
            pass


def _reap_nonblocking():
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return True
        if pid == 0:
            return False


def _cleanup_descendants():
    handles = _stopped_descendants()
    try:
        _signal_handles(handles, signal.SIGTERM)
        _signal_handles(handles, signal.SIGCONT)
        deadline = time.monotonic() + 1
        while not _reap_nonblocking() and time.monotonic() < deadline:
            time.sleep(.01)
    finally:
        for descriptor in handles.values():
            os.close(descriptor)
    # A TERM handler can fork; collect the adopted tree again before KILL.
    handles = _stopped_descendants()
    try:
        _signal_handles(handles, signal.SIGKILL)
        while True:
            try:
                os.waitpid(-1, 0)
            except ChildProcessError:
                break
    finally:
        for descriptor in handles.values():
            os.close(descriptor)


def _supervise(argv):
    """A private Linux subreaper contains nested setsid/double-fork children."""
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'cannot enable job subreaper')

    def interrupted(signum, _frame):
        raise SystemExit(128 + signum)

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, interrupted)
    try:
        signal.pthread_sigmask(signal.SIG_UNBLOCK, {signal.SIGTERM, signal.SIGINT})
        process = subprocess.Popen(argv)
        code = process.wait()
        return code if code >= 0 else 128 - code
    finally:
        for signum in (signal.SIGTERM, signal.SIGINT):
            signal.signal(signum, signal.SIG_IGN)
        _cleanup_descendants()


def _stop_supervisor(process):
    if process is not None and process.poll() is None:
        process.send_signal(signal.SIGTERM)
        # Do not kill the subreaper before it has reaped its detached children.
        process.wait()


def run(job: dict) -> dict:
    required = {'job_id', 'argv', 'cwd', 'output_dir', 'timeout_seconds'}
    if not required <= job.keys():
        raise ValueError(f'missing job fields: {required - job.keys()}')
    if not isinstance(job['argv'], list) or not job['argv'] or not all(isinstance(x, str) and x for x in job['argv']):
        raise ValueError('argv must be a nonempty string array')
    deadline = job.get('deadline_monotonic')
    if 'deadline_monotonic' in job and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
        raise ValueError('deadline_monotonic must be a finite clock value')
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
    process, failure, exit_code = None, None, -1
    previous_handlers = {}
    command = ['bash', '-c',
               'source /usr/local/Ascend/cann-9.0.0/set_env.sh; '
               'export LD_LIBRARY_PATH=/usr/local/Ascend/driver/lib64/common:/usr/local/Ascend/driver/lib64/driver:${LD_LIBRARY_PATH:-}; '
               'exec "$@"', 'aprof-job', *job['argv']]
    try:
        with (out / 'stdout.log').open('wb') as stdout, (out / 'stderr.log').open('wb') as stderr:
            def interrupted(signum, _frame):
                raise SystemExit(128 + signum)
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous_handlers[signum] = signal.signal(signum, interrupted)
            try:
                if deadline is not None and time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(job['argv'], 0)
                blocked = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGTERM, signal.SIGINT})
                try:
                    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), '--supervise', *command],
                                               cwd=job['cwd'], env=environment,
                                               stdout=stdout, stderr=stderr, start_new_session=True)
                finally:
                    signal.pthread_sigmask(signal.SIG_SETMASK, blocked)
                timeout = job['timeout_seconds']
                if deadline is not None:
                    timeout = min(timeout, max(0, deadline - time.monotonic()))
                exit_code = process.wait(timeout=timeout)
                if deadline is not None and time.monotonic() > deadline:
                    timed_out = True
            except subprocess.TimeoutExpired:
                timed_out = True
                _stop_supervisor(process)
                exit_code = process.returncode if process is not None else -1
    except BaseException as error:
        failure = error
        # Repeated cancellation must not interrupt child cleanup or receipts.
        for signum in previous_handlers:
            signal.signal(signum, signal.SIG_IGN)
        _stop_supervisor(process)
        exit_code = process.returncode if process is not None else -1
    finally:
        result = {
            'schema_version': '1.0.0', 'kind': 'aprof_execution_report', 'job': job,
            'host': socket.gethostname(), 'physical_device': device,
            'started_at': started, 'finished_at': now(), 'duration_seconds': time.monotonic() - before,
            'exit_code': exit_code, 'status': 'timeout' if timed_out else ('passed' if exit_code == 0 and failure is None else 'failed'),
            'stdout': {'path': str(out / 'stdout.log'), 'sha256': sha(out / 'stdout.log')},
            'stderr': {'path': str(out / 'stderr.log'), 'sha256': sha(out / 'stderr.log')},
        }
        if failure is not None:
            result['error'] = {'type': type(failure).__name__, 'message': str(failure)}
        if deadline is not None:
            result['process_started'] = process is not None
        dump(report_path, result)
        for signum, previous in previous_handlers.items():
            signal.signal(signum, previous)
        if lock is not None:
            fcntl.flock(lock, fcntl.LOCK_UN)
            lock.close()
    if failure is not None:
        raise failure
    return result


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
    raise SystemExit(_supervise(sys.argv[2:]) if sys.argv[1:2] == ['--supervise'] else main())
