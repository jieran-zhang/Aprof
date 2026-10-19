"""Soft duration targets; measurement validity is enforced separately."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid

POLICY = "soft_targets_local_v1"


def local_path(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_relative_to(Path("/dev/shm")):
        raise ValueError("new execution artifacts must be canonical paths under /dev/shm")
    return path


def task_root(path):
    path = Path(path).resolve()
    for parent in (path, *path.parents):
        if (parent / ".aprof-workspace.json").is_file():
            return parent
    declared = os.environ.get("APROF_TASK_ROOT")
    if declared:
        root = local_path(declared)
        if path.is_relative_to(root):
            return root
    return None


def append(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def diagnostics(pid):
    result = {"pid": pid, "monotonic": time.monotonic()}
    for name in ("stat", "io", "wchan", "status"):
        try:
            result[name] = Path(f"/proc/{pid}/{name}").read_text()
        except OSError:
            result[name] = None
    return result


def wait(process, *, target_seconds, checkpoint, communicate=False, confirm_hang=None):
    """A threshold collects diagnostics. Only explicit diagnostic confirmation kills.

    confirm_hang must return evidence/reason, never a duration-only predicate.
    Cancellation is propagated after cleaning only the owned process group.
    """
    started = time.monotonic()
    target_at = started + max(0, target_seconds)
    warned = False
    def stop():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
    try:
        while True:
            try:
                interval = min(1.0, max(.01, target_at-time.monotonic())) if not warned else 1.0
                return (process.communicate(timeout=interval) if communicate else process.wait(timeout=interval))
            except subprocess.TimeoutExpired:
                sample = None
                if not warned and time.monotonic() >= target_at:
                    sample = diagnostics(process.pid)
                    append(checkpoint, {"event": "budget_warning", "policy": POLICY,
                        "target_seconds": target_seconds, "elapsed_seconds": time.monotonic()-started,
                        "diagnostics": sample, "action": "continue"})
                    warned = True
                if confirm_hang is not None:
                    evidence = confirm_hang(sample or diagnostics(process.pid))
                    if evidence:
                        append(checkpoint, {"event": "confirmed_local_hang", "evidence": evidence,
                            "diagnostics": diagnostics(process.pid)})
                        stop()
                        raise RuntimeError("confirmed local hang; diagnostics preserved")
    except BaseException:
        stop()
        raise


@contextmanager
def operation(root, stage, category, *, target=None, case=None, implementation=None, parent=None):
    started = time.monotonic()
    row = {"operation_id": uuid.uuid4().hex, "parent_operation": parent, "workflow_stage": stage,
           "operation_type": category, "case_id": case, "implementation": implementation,
           "pid": os.getpid(), "started_monotonic": started, "target_seconds": target}
    try:
        yield row
        row["execution_status"] = "completed"
    except BaseException as exc:
        row.update(execution_status="failed", error=type(exc).__name__, message=str(exc))
        raise
    finally:
        row["finished_monotonic"] = time.monotonic()
        row["elapsed_seconds"] = row["finished_monotonic"]-started
        row["overrun_seconds"] = max(0, row["elapsed_seconds"]-target) if target is not None else None
        row["budget_warnings"] = ["target_exceeded"] if row["overrun_seconds"] else []
        append(Path(root)/"operations.jsonl", row)
        if row["budget_warnings"]:
            append(Path(root)/"checkpoints.jsonl", {**row, "action": "continue"})
