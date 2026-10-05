#!/usr/bin/env python3
"""Execute declared nonbenchmark semantic guards in private, immutable outputs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

from feedback_hardware import run_process
from msprof_exploration_execute import event, load, pointer, save, sha, task_paths
from msprof_exploration_safety import health
from run_level1_serial import exclusive_host


def collect(run, operator, candidate, output=None):
    run, split, task, parent, source = task_paths(run, operator, candidate)
    out = Path(output).resolve() if output else parent / "boundary-validation"
    script = task / "agent/boundary_guard.py"
    build = load(parent / "build/build_manifest.json")
    binary = build["standalone"]
    if sha(binary["path"]) != binary["sha256"]:
        raise ValueError("boundary binary changed")
    source_ref = pointer(script)
    plan_path = parent / "dispatch_plan.json" if candidate != "baseline" else None
    plan_ref = pointer(plan_path) if plan_path is not None else None
    dispatch = load(plan_path) if plan_path is not None else None
    entries = ({row["tiling_key"]: row["kernel_entry"] for row in [*dispatch["entries"], dispatch["fallback"]]}
               if dispatch is not None else {})
    guard_args = ["--plan", plan_path] if plan_path is not None else []
    started = time.time()
    with exclusive_host():
        out.mkdir(parents=True, exist_ok=False)
        save(out / "request.json", {"version": "level2_semantic_guards_v1", "operator": operator,
             "candidate": candidate, "script": source_ref, "binary": binary, "performance_evaluated": False,
             "dispatch_plan": plan_ref,
             "dispatch_logs_required": candidate != "baseline", "device": 0, "cpu": 8})
        event(task, "boundary_validation_started", {"candidate": candidate, "request": pointer(out / "request.json")})
        rows, error, verification_error = [], None, None
        try:
            run_process([sys.executable, "-B", script, "--output", out / "inputs", *guard_args], task,
                        out / "prepare", cpu="40-43", timeout=600)
            commands = load(out / "inputs/coordinator_commands.json")
            health(out / "health-before.json")
            for command in commands:
                directory = out / "executions" / command["name"]
                argv = [binary["path"], *command["argv"]]
                failure = None
                try:
                    run_process(argv, source, directory, device=0, cpu="8", timeout=300)
                except Exception as exc:
                    failure = {"type": type(exc).__name__, "message": str(exc)}
                execution = load(directory / "execution.json")
                stdout = (directory / "stdout.log").read_text(errors="replace")
                stderr = (directory / "stderr.log").read_text(errors="replace")
                if command.get("process_record"):
                    save(command["process_record"], {"returncode": execution["exit_status"], "stderr": stderr})
                logs = [json.loads(line.split("APROF_DISPATCH_JSON:", 1)[1]) for line in stdout.splitlines()
                        if line.startswith("APROF_DISPATCH_JSON:")]
                rejected = command.get("expected_exit") == "nonzero"
                # A signal/timeout is never evidence of a deliberate input rejection.
                expected_process = ((type(execution["exit_status"]) is int and execution["exit_status"] > 0
                                     and bool(command.get("expected_error"))
                                     and command["expected_error"] in stderr
                                     and (failure is None or failure["type"] == "RuntimeError")) if rejected
                                    else execution["exit_status"] == 0 and failure is None)
                expected_entry = entries.get(command.get("expected_key"))
                dispatch_passed = (candidate == "baseline" or rejected or
                                   (expected_entry is not None and len(logs) == 1
                                    and type(logs[0].get("tiling_key")) is int
                                    and logs[0]["tiling_key"] == command["expected_key"]
                                    and logs[0].get("kernel_entry") == expected_entry
                                    and ("expected_entry" not in command or expected_entry == command["expected_entry"])))
                rows.append({"name": command["name"], "execution": pointer(directory / "execution.json"),
                    "expected_process_passed": expected_process, "dispatch_log_passed": dispatch_passed,
                    "dispatch_logs": logs, "error": failure})
            try:
                run_process([sys.executable, "-B", script, "--output", out / "inputs", "--verify", *guard_args], task,
                            out / "verify", cpu="40-43", timeout=600)
            except Exception as exc:
                verification_error = {"type": type(exc).__name__, "message": str(exc)}
            if sha(script) != source_ref["sha256"] or sha(binary["path"]) != binary["sha256"]:
                raise ValueError("boundary source or executable changed during execution")
            if plan_ref is not None and sha(plan_path) != plan_ref["sha256"]:
                raise ValueError("boundary dispatch plan changed during execution")
        except BaseException as exc:
            error = {"type": type(exc).__name__, "message": str(exc)}
        finally:
            try:
                health(out / "health-after.json")
            except BaseException as exc:
                error = error or {"type": type(exc).__name__, "message": str(exc)}
            passed = not error and not verification_error and bool(rows) and all(
                r["expected_process_passed"] and r["dispatch_log_passed"] for r in rows)
            result = {"version": "level2_semantic_guards_v1", "operator": operator, "candidate": candidate,
                "request": pointer(out / "request.json"),
                "status": "passed" if passed else "failed", "cases": rows, "error": error,
                "verification_error": verification_error, "elapsed_seconds": time.time() - started,
                "performance_evaluated": False, "formal_admission": "not_evaluated"}
            save(out / "completion.json", result)
            event(task, "boundary_validation_completed", {"candidate": candidate, "completion": pointer(out / "completion.json")})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "operator", "candidate"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    result = collect(args.run, args.operator, args.candidate, args.output)
    print(json.dumps(result))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
