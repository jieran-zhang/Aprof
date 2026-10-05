#!/usr/bin/env python3
"""Export completed serial batches while the independent hardware collector runs.

This observer never launches device work. It holds a separate export lock, pins
itself and its children to a CPU, and records each export invocation. A stopped
collector leaves unfinished operators pending instead of inventing outcomes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def stamp():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return 'sha256:' + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def replace_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix='.export-observer-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream, sort_keys=True, allow_nan=False)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def process_identity(pid, proc_root=Path('/proc')):
    """Bind PID plus kernel start tick, treating zombies as stopped."""
    try:
        stat = (proc_root / str(pid) / 'stat').read_text()
        fields = stat[stat.rfind(')') + 2:].split()
        if fields[0] == 'Z':
            return None
        return {'pid': pid, 'start_ticks': int(fields[19])}
    except FileNotFoundError:
        return None


def closed_operators(run, operators):
    """A notification trigger; the exporter independently verifies full closure."""
    closed = []
    for op in operators:
        path = run / 'tasks' / op / 'calibration-decision.json'
        if path.exists():
            decision = read(path)
            if type(decision.get('accepted')) is not bool:
                raise ValueError(f'invalid terminal calibration decision: {op}')
            # The collector publishes its decision before its final health
            # probe. Do not seal a batch in that publication window.
            health_path = path.parent / 'health-after.json'
            if health_path.exists():
                health = read(health_path)
                if type(health.get('exit_status')) is int and health.get('finished_at'):
                    closed.append(op)
    return closed


class ExportObserver:
    def __init__(self, run, controller_pid, cpu=40):
        self.run = Path(run).resolve()
        self.directory = self.run / 'export-observer'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.operators = read(self.run / 'run-manifest.json')['operators']
        self.identity = process_identity(controller_pid)
        self.controller_pid = controller_pid
        self.cpu = cpu
        self.lock_fd = None
        self.exporter = ROOT / 'scripts/finalize_level1_serial.py'
        # Bind executable Python sources, including transitive local imports.
        paths = [*sorted((ROOT / 'src/aprof_runtime').rglob('*.py')),
                 *sorted((ROOT / 'scripts').glob('*.py'))]
        self.sources = {str(path): digest(path) for path in paths}
        self.sources[str(Path(__file__).resolve())] = digest(__file__)
        self.started_at = stamp()

    def alive(self):
        return self.identity is not None and process_identity(self.controller_pid) == self.identity

    def state(self, status, closed, **extra):
        value = dict(schema_version='1.0.0', run_id=self.run.name,
                     status=status, started_at=self.started_at, updated_at=stamp(),
                     observer_pid=os.getpid(), controller=self.identity,
                     controller_pid=self.controller_pid, cpu=self.cpu,
                     closed_operators=closed,
                     pending_operators=[op for op in self.operators if op not in closed],
                     hardware_commands_launched=0, **extra)
        replace_json(self.directory / 'state.json', value)
        print(json.dumps(value, sort_keys=True), flush=True)

    def command(self, flags):
        changed = [path for path, expected in self.sources.items() if digest(path) != expected]
        if changed:
            raise ValueError('export producer changed after observer start: ' + ', '.join(changed))
        destination = self.directory / ('command-' + str(time.time_ns()))
        destination.mkdir()
        argv = [sys.executable, str(self.exporter), '--run', str(self.run), *flags]
        execution = dict(schema_version='1.0.0', argv=argv, cwd=str(ROOT),
                         host=os.uname().nodename, cpu=self.cpu, started_at=stamp(),
                         source_hashes=self.sources, exit_status=None)
        replace_json(destination / 'execution.json', execution)
        with (destination / 'stdout.log').open('w') as out, (destination / 'stderr.log').open('w') as err:
            # The child shares the same flock open-file description. If this
            # observer is killed, it cannot release exclusivity while the CPU
            # exporter still writes; a restart must wait for that child to exit.
            inherited = () if self.lock_fd is None else (self.lock_fd,)
            result = subprocess.run(argv, cwd=ROOT, stdout=out, stderr=err, check=False,
                                    start_new_session=True, pass_fds=inherited)
        execution.update(finished_at=stamp(), exit_status=result.returncode,
                         stdout={'path': str(destination / 'stdout.log'), 'sha256': digest(destination / 'stdout.log')},
                         stderr={'path': str(destination / 'stderr.log'), 'sha256': digest(destination / 'stderr.log')})
        changed = [path for path, expected in self.sources.items()
                   if not Path(path).exists() or digest(path) != expected]
        execution['producer_changed_during_execution'] = changed
        replace_json(destination / 'execution.json', execution)
        if changed:
            raise ValueError('export producer changed during execution: ' + ', '.join(changed))
        if result.returncode:
            raise RuntimeError(f'export failed with exit {result.returncode}; see {destination}')

    def step(self, previous):
        closed = closed_operators(self.run, self.operators)
        if len(closed) == len(self.operators):
            self.state('finalizing', closed)
            self.command([])
            self.command(['--verify-only'])
            self.state('complete', closed, final_report=str(self.run / 'serial_report.md'),
                       verification=str(self.run / 'serial_verification.json'))
            return tuple(closed), True
        if previous != tuple(closed):
            self.state('exporting_closed_operators', closed)
            self.command(['--ready-only'])
        if not self.alive():
            self.state('collector_stopped_with_pending_operators', closed,
                       reason='Collector PID/start tick is no longer live; pending batches are not synthesized.')
            return tuple(closed), True
        self.state('waiting_for_operator_closure', closed)
        return tuple(closed), False

    def watch(self, interval=60):
        os.sched_setaffinity(0, {self.cpu})
        with (self.directory / 'observer.lock').open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.lock_fd = lock.fileno()
            snapshot = self.directory / ('producer-' + str(time.time_ns()) + '.json')
            replace_json(snapshot, dict(source_hashes=self.sources, controller=self.identity,
                                       started_at=self.started_at))
            previous = None
            try:
                while True:
                    previous, done = self.step(previous)
                    if done:
                        break
                    time.sleep(interval)
            except Exception as exc:
                self.state('export_observer_failed', list(previous or ()), error=str(exc))
                raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--controller-pid', required=True, type=int)
    parser.add_argument('--cpu', type=int, default=40)
    parser.add_argument('--interval', type=float, default=60)
    args = parser.parse_args()
    if not 1 <= args.interval <= 60:
        parser.error('--interval must be between 1 and 60 seconds')
    ExportObserver(args.run, args.controller_pid, args.cpu).watch(args.interval)


if __name__ == '__main__':
    main()
