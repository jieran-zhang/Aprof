#!/usr/bin/env python3
"""Scoped reuse of one unchanged original oracle, outside native measurement.

The callable preserves run_logged's signature and evidence filenames. All other
commands are delegated unchanged. No old producer module is patched here.
"""
from __future__ import annotations

from contextlib import chdir, redirect_stderr, redirect_stdout, nullcontext
import hashlib
import io
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
import traceback

from level2_adapters import reusable_verifier as ReusedVerifier

MODE = "in_process_original_verifier_v1"
_CALL_LOCK = threading.RLock()


class _Deadline(BaseException):
    pass


def sha(path):
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _identity(value):
    value = value if str(value).startswith("sha256:") else "sha256:" + str(value)
    if len(value) != 71 or any(c not in "0123456789abcdef" for c in value[7:]):
        raise ValueError("expected oracle SHA-256")
    return value


def _save(path, value):
    with Path(path).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def _affinity(value):
    if value is None:
        return None
    result = set()
    for item in str(value).split(","):
        ends = item.split("-")
        if len(ends) == 1:
            result.add(int(ends[0]))
        elif len(ends) == 2 and int(ends[0]) <= int(ends[1]):
            result.update(range(int(ends[0]), int(ends[1]) + 1))
        else:
            raise ValueError("invalid oracle CPU affinity")
    if not result or min(result) < 0:
        raise ValueError("invalid oracle CPU affinity")
    return result


class ScopedOracle:
    """One hash-pinned oracle module, lazy-loaded on the first matching call.

    Calls execute on the main thread with SIGALRM and restore argv/cwd/env/
    affinity/handler. Signals interrupt at Python checkpoints; a C extension can
    delay delivery. A timed-out scope is disabled rather than silently reused.
    Existing process timers and non-main-thread callers use the original runner.
    """
    def __init__(self, delegate, *, verifier, expected_hash, metadata_root=None, cpu_affinity=None):
        self.delegate = delegate
        self.path = Path(verifier).resolve()
        self.expected_hash = _identity(expected_hash)
        self.metadata_root = Path(metadata_root).resolve() if metadata_root is not None else None
        self.cpu_affinity = _affinity(cpu_affinity)
        self.verifier = None
        self.disabled = False

    def matches(self, argv):
        values = list(map(str, argv))
        if not values or Path(values[0]).resolve() != Path(sys.executable).resolve():
            return False
        args = values[1:]
        if args[:1] == ["-B"]:
            args = args[1:]
        return len(args) == 3 and Path(args[0]).resolve() == self.path and args[1] == "--metadata"

    def __call__(self, argv, out, env, timeout, cwd=None):
        if not self.matches(argv):
            return self.delegate(argv, out, env, timeout, cwd=cwd)
        if threading.current_thread() is not threading.main_thread() or any(signal.getitimer(signal.ITIMER_REAL)):
            return self.delegate(argv, out, env, timeout, cwd=cwd)
        argv = list(map(str, argv))
        cwd = Path(cwd).resolve() if cwd is not None else Path.cwd()
        metadata = Path(argv[-1])
        metadata = (cwd / metadata).resolve() if not metadata.is_absolute() else metadata.resolve()
        out = Path(out)
        paths = {name: Path(str(out) + suffix) for name, suffix in (
            ("stdout", ".stdout.log"), ("stderr", ".stderr.log"), ("execution", ".execution.json"), ("started", ".started.json"))}
        if any(path.exists() for path in paths.values()):
            raise FileExistsError("oracle evidence already exists: " + str(out))
        started, mono = time.time(), time.monotonic()
        stdout, stderr = io.StringIO(), io.StringIO()
        result, caught, error, exit_code = None, None, None, None
        invoked, import_seconds, timed_out = 0, 0.0, False
        record = {"argv": argv, "cwd": str(cwd), "host": socket.gethostname(), "physical_device": env.get("ASCEND_RT_VISIBLE_DEVICES"),
                  "logical_device": 0, "started_at": started, "mode": MODE, "new_process_started": False,
                  "verifier": {"path": str(self.path), "sha256": self.expected_hash}, "verifier_calls": 0,
                  "verifier_processes_started": 0, "timeout_seconds": timeout,
                  "timeout_policy": "SIGALRM; C extension delivery may wait for a Python checkpoint",
                  "producer": {"path": str(Path(__file__).resolve()), "sha256": sha(__file__)},
                  "requested_cpu_affinity": sorted(self.cpu_affinity) if self.cpu_affinity is not None else None,
                  "environment_scope": "provided oracle environment temporarily applied; restored before returning"}
        if not isinstance(timeout, (int, float)) or not math.isfinite(timeout):
            record["timeout_seconds"] = None
        _save(paths["started"], record)
        with _CALL_LOCK:
            previous_argv, previous_env = sys.argv, dict(os.environ)
            previous_affinity = os.sched_getaffinity(0)
            previous_handler = signal.getsignal(signal.SIGALRM)
            armed = False
            try:
                if self.disabled:
                    raise RuntimeError("oracle scope disabled after timeout or interruption")
                if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
                    raise ValueError("oracle timeout must be positive and finite")
                if self.metadata_root is not None and not metadata.is_relative_to(self.metadata_root):
                    raise ValueError("oracle metadata is outside its declared task scope")
                if sha(self.path) != self.expected_hash:
                    raise ValueError("original oracle hash differs from frozen identity")
                record["metadata"] = {"path": str(metadata), "sha256": sha(metadata)}
                if self.cpu_affinity is not None:
                    os.sched_setaffinity(0, self.cpu_affinity)
                record["actual_cpu_affinity"] = sorted(os.sched_getaffinity(0))
                os.environ.clear(); os.environ.update(env)
                def deadline(signum, frame):
                    raise _Deadline()
                signal.signal(signal.SIGALRM, deadline)
                signal.setitimer(signal.ITIMER_REAL, timeout)
                armed = True
                with chdir(cwd), redirect_stdout(stdout), redirect_stderr(stderr):
                    if self.verifier is None:
                        preload = time.monotonic()
                        self.verifier = ReusedVerifier(self.path)
                        import_seconds = time.monotonic() - preload
                        if self.verifier.source_hash != self.expected_hash:
                            raise ValueError("oracle bytes changed during preload")
                    if hasattr(self.verifier, 'dependencies'):
                        for dependency, expected in self.verifier.dependencies.items():
                            if sha(dependency)!=expected: raise ValueError('oracle dependency changed: '+str(dependency))
                        record['oracle_dependencies']=[{'path':str(p),'sha256':h} for p,h in self.verifier.dependencies.items()]
                    # Exactly the original audited main, with recorded local metadata
                    # relocation only for an oracle requiring writable mmap scratch.
                    context=(self.verifier.execution_metadata(metadata) if hasattr(self.verifier,'execution_metadata')
                             else nullcontext((metadata,None)))
                    with context as (actual_metadata,relocation):
                        if relocation is not None:
                            record['requested_argv']=list(argv)
                            record['argv']=[*argv[:-1],str(actual_metadata)]
                            record['oracle_relocation']=relocation
                        sys.argv = [str(self.path), "--metadata", str(actual_metadata)]
                        invoked = 1
                        try:
                            self.verifier.module.main()
                            exit_code = 0
                        except SystemExit as exc:
                            if exc.code is None:
                                exit_code = 0
                            elif isinstance(exc.code, int):
                                exit_code = exc.code
                            else:
                                print(exc.code, file=sys.stderr)
                                exit_code = 1
                signal.setitimer(signal.ITIMER_REAL, 0)
                armed = False
                if time.monotonic() - mono > timeout:
                    raise _Deadline()
                if hasattr(self.verifier, 'dependencies') and any(sha(p)!=h for p,h in self.verifier.dependencies.items()):
                    raise ValueError('oracle dependency changed during execution')
                if sha(self.path) != self.expected_hash or sha(metadata) != record["metadata"]["sha256"]:
                    raise ValueError("oracle or verification metadata changed during execution")
                if exit_code != 0:
                    raise RuntimeError("original oracle main exited " + str(exit_code))
                result = subprocess.CompletedProcess(record["argv"], exit_code, stdout.getvalue(), stderr.getvalue())
            except _Deadline:
                timed_out = True
                self.disabled = True
                exit_code = None
                caught = subprocess.TimeoutExpired(argv, timeout, output=stdout.getvalue(), stderr=stderr.getvalue())
                error = {"type": "TimeoutExpired", "message": str(caught)}
            except BaseException as exc:
                caught = exc
                error = {"type": type(exc).__name__, "message": str(exc)}
                traceback.print_exc(file=stderr)
                if not isinstance(exc, Exception):
                    self.disabled = True
                if invoked and exit_code is None and isinstance(exc, Exception):
                    exit_code = 1
            finally:
                if armed:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                signal.signal(signal.SIGALRM, previous_handler)
                sys.argv = previous_argv
                os.environ.clear(); os.environ.update(previous_env)
                if os.sched_getaffinity(0) != previous_affinity:
                    os.sched_setaffinity(0, previous_affinity)
                for name, content in (("stdout", stdout.getvalue()), ("stderr", stderr.getvalue())):
                    with paths[name].open("x") as stream:
                        stream.write(content)
                record.update(ended_at=time.time(), exit_code=exit_code, exit_status=exit_code,
                              status="failed" if caught is not None else "passed", error=error, timed_out=timed_out,
                              verifier_calls=invoked, preload_wall_seconds=import_seconds,
                              wall_seconds=time.monotonic() - mono, module_reused=invoked > 0 and import_seconds == 0)
                _save(paths["execution"], record)
        if caught is not None:
            raise caught
        return result


def make_run_logged(delegate, *, verifier, expected_hash, metadata_root=None, cpu_affinity=None):
    return ScopedOracle(delegate, verifier=verifier, expected_hash=expected_hash,
                        metadata_root=metadata_root, cpu_affinity=cpu_affinity)
