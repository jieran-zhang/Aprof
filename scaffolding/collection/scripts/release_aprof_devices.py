#!/usr/bin/env python3
"""Release authorized sglang trees under the AProf host lock and retain evidence."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import socket
import time

from msprof_exploration_safety import now, query_health
from run_level1_serial import exclusive_host


def process(pid):
    path = Path('/proc') / str(pid)
    fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
    if fields[0] == 'Z':
        return None
    raw = (path / 'cmdline').read_bytes()
    return dict(pid=int(pid), ppid=int(fields[1]), pgid=int(fields[2]), session_id=int(fields[3]),
                start_ticks=fields[19], name=(path / 'comm').read_text().strip(),
                command_hash=hashlib.sha256(raw).hexdigest(),
                is_server=b'sglang.launch_server' in raw.split(b'\0'))


def processes():
    """Read identities, never expose command lines or environment variables."""
    result = {}
    for path in Path('/proc').iterdir():
        if not path.name.isdigit():
            continue
        try:
            info = process(int(path.name))
            if info is not None:
                result[info['pid']] = info
        except (FileNotFoundError, ProcessLookupError):
            pass
        except (OSError, ValueError, IndexError) as exc:
            if path.exists():
                raise RuntimeError(f'cannot inventory process {path.name}') from exc
    return result


def identity(info):
    return info['pid'], str(info['start_ticks'])


def send_signal(info, sig):
    """Pin the kernel process object, then recheck identity before signalling."""
    if not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise RuntimeError('pidfd signalling is required for safe process release')
    try:
        fd = os.pidfd_open(info['pid'])
    except ProcessLookupError:
        return 'exited'
    try:
        try:
            current = process(info['pid'])
        except (FileNotFoundError, ProcessLookupError):
            return 'exited'
        if current is None:
            return 'exited'
        if identity(current) != identity(info):
            return 'identity_changed'
        try:
            signal.pidfd_send_signal(fd, sig)
        except ProcessLookupError:
            return 'exited'
        return 'sent'
    finally:
        os.close(fd)


class AuthorizedTree:
    def __init__(self, initial, root_pids=None):
        roots = {pid: row for pid, row in initial.items() if row['is_server']}
        if root_pids is not None:
            if not set(root_pids) <= roots.keys():
                raise ValueError('every authorized root PID must be a live sglang.launch_server')
            roots = {pid: roots[pid] for pid in root_pids}
        self.roots = roots
        self.known = dict(roots)
        self.groups = {}
        self.reused = set()
        self._descendants(initial)
        # An independent and initially uncontaminated session gives provenance
        # to children which become orphans between /proc snapshots.
        for pid, row in roots.items():
            if row['pgid'] == pid == row['session_id'] and all(
                    other['pid'] in self.known for other in initial.values() if other['pgid'] == pid):
                self.groups[pid] = row

    def _descendants(self, current):
        while True:
            parents = {pid for pid, row in self.known.items()
                       if pid in current and identity(row) == identity(current[pid])}
            added = False
            for pid, row in current.items():
                if row['ppid'] in parents and pid not in self.known:
                    self.known[pid] = row
                    added = True
            if not added:
                break

    def refresh(self, current):
        self._descendants(current)
        for group, root in self.groups.items():
            if group in current and identity(current[group]) != identity(root):
                continue  # Numerical group/session ID was reused.
            for pid, row in current.items():
                if row['pgid'] == group and row['session_id'] == group and pid not in self.known:
                    self.known[pid] = row
        self._descendants(current)
        alive = []
        for pid, original in self.known.items():
            if pid in current:
                if identity(original) == identity(current[pid]):
                    alive.append(current[pid])
                else:
                    self.reused.add(identity(current[pid]))
        known_ids = {identity(row) for row in alive}
        unresolved = [row for row in current.values() if identity(row) not in known_ids and (
            row['is_server'] or row['name'].startswith('sglang') or
            row['pgid'] in {root['pgid'] for root in self.roots.values()})]
        return sorted(alive, key=lambda row: row['pid']), sorted(unresolved, key=lambda row: row['pid'])


def _save(path, report):
    temporary = path.with_name(path.name + f'.{os.getpid()}.tmp')
    with temporary.open('x') as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def release_devices(output, *, authorized=False, root_pids=None, term_timeout=20,
                    kill_timeout=2, poll_interval=1, lock_root='/tmp/aprof-device-locks'):
    """Own one host lock. Collectors call health directly inside their own lock."""
    for value in (term_timeout, kill_timeout, poll_interval):
        if not math.isfinite(value) or value <= 0:
            raise ValueError('release timeouts and poll interval must be positive and finite')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    report = dict(schema_version='1.1.0', host=socket.gethostname(), started_at=now(),
                  authorized=authorized, targets=[], authorized_roots=[], signals=[],
                  remaining_targets=[], remaining_servers=[], unresolved_processes=[],
                  npu_smi=None, status='failed', exit_status=1, error=None)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    try:
        with exclusive_host(lock_root):
            initial = processes()
            tracker = AuthorizedTree(initial, root_pids)
            report['authorized_roots'] = list(tracker.roots.values())
            report['targets'] = list(tracker.known.values())
            _save(output, report)  # Freeze identities before any signal.
            term_sent = {}

            def refresh():
                snapshot = processes()
                alive, unresolved = tracker.refresh(snapshot)
                report['discovered_targets'] = list(tracker.known.values())
                report['remaining_targets'] = [row['pid'] for row in alive]
                report['remaining_servers'] = [row for row in snapshot.values() if row['is_server']]
                report['unresolved_processes'] = unresolved
                report['reused_identities'] = [dict(pid=pid, start_ticks=ticks) for pid, ticks in sorted(tracker.reused)]
                return alive

            def dispatch(rows, sig):
                for row in rows:
                    result = send_signal(row, sig)
                    report['signals'].append(dict(pid=row['pid'], start_ticks=row['start_ticks'],
                                                  signal=sig.name, result=result, timestamp=now()))
                    if sig == signal.SIGTERM:
                        term_sent[identity(row)] = time.monotonic()

            alive = refresh()
            if authorized:
                dispatch(alive, signal.SIGTERM)
                deadline = max(term_sent.values(), default=time.monotonic()) + term_timeout
                while alive:
                    dispatch([row for row in alive if identity(row) not in term_sent], signal.SIGTERM)
                    _save(output, report)
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
                    alive = refresh()
                # Late-born children get TERM, but never KILL without their own
                # full grace interval. Persistent late arrivals fail closed.
                alive = refresh()
                eligible = [row for row in alive if identity(row) in term_sent and
                            time.monotonic() - term_sent[identity(row)] >= term_timeout]
                dispatch(eligible, signal.SIGKILL)
                _save(output, report)
                deadline = time.monotonic() + kill_timeout
                while alive and time.monotonic() < deadline:
                    time.sleep(min(poll_interval, max(0, deadline - time.monotonic())))
                    alive = refresh()
            refresh()
            report['npu_smi'] = query_health()
            # A respawn during the health query invalidates the earlier clearance.
            refresh()
            clear = not (report['remaining_targets'] or report['remaining_servers'] or report['unresolved_processes'])
            if not clear:
                raise RuntimeError('authorized or unproven process residue remains; hardware is blocked')
            if report['npu_smi']['status'] != 'passed':
                raise RuntimeError('device health inventory failed; hardware is blocked')
            report.update(status='passed', exit_status=0)
    except BaseException as exc:
        report['error'] = dict(type=type(exc).__name__, message=str(exc))
        if not isinstance(exc, Exception):
            raise
    finally:
        report['finished_at'] = now()
        _save(output, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--release-authorized-sglang', action='store_true')
    parser.add_argument('--root-pid', action='append', type=int,
                        help='optional authorized launch_server root; defaults to all current servers')
    args = parser.parse_args(argv)
    report = release_devices(args.output, authorized=args.release_authorized_sglang, root_pids=args.root_pid)
    print(json.dumps(dict(host=report['host'], status=report['status'], target_count=len(report['targets']),
                         remaining_targets=report['remaining_targets'], remaining_server_count=len(report['remaining_servers']),
                         unresolved_count=len(report['unresolved_processes']), report=str(args.output))))
    return report['exit_status']


if __name__ == '__main__':
    raise SystemExit(main())
