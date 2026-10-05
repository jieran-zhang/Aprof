#!/usr/bin/env python3
"""Full correctness through the rebuilt original entry, using frozen baseline oracles.

No input generation, build, profiler, runtime gate or automatic retry occurs here.
The caller separately validates the prepared shared-context path afterwards.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import time

from cannbench_device_timing import operator_name as legacy_operator_name
from level2_adapters import dispatch_command as command_from_metadata, is_level2, output_paths, operator_name as level2_operator_name
from msprof_exploration_safety import health
from run_level1_serial import exclusive_host

VERSION = "msprof_exploration_standalone_correctness_v1"
ALL_CASES = list(range(1, 21))


def operator_name(opdir):
    """Resolve the same Level1/Level2 scope as the prepared command adapter."""
    return level2_operator_name(opdir) if is_level2(opdir) else legacy_operator_name(opdir)


def run_process(*args, **kwargs):
    # Hardware execution is reachable only through explicit correctness().
    from feedback_hardware import run_process as execute
    return execute(*args, **kwargs)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def _identity(value):
    if isinstance(value, str) and len(value) == 64:
        value = "sha256:" + value
    if not isinstance(value, str) or len(value) != 71 or not value.startswith("sha256:") or any(c not in "0123456789abcdef" for c in value[7:]):
        raise ValueError("SHA-256 evidence identity required")
    return value


def save(path, value, *, legacy_metadata=False):
    with Path(path).open("x") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=legacy_metadata)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())


def load(path):
    return json.loads(Path(path).read_text())


def pointer(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha(path)}


def _error(exc):
    return {"type": type(exc).__name__, "message": str(exc)}


def _check_binding(reference, seen):
    if not isinstance(reference, dict) or not {"path", "sha256"} <= set(reference):
        raise ValueError("frozen file needs path and SHA-256")
    path = Path(reference["path"]).resolve()
    expected = _identity(reference["sha256"])
    if path in seen and seen[path] != expected:
        raise ValueError("conflicting frozen input identity: " + str(path))
    if path not in seen:
        if sha(path) != expected:
            raise ValueError("frozen input, oracle or binary changed: " + str(path))
        seen[path] = expected
    return path


def _prepare(task, build_manifest, input_root, cases):
    baseline = task / "baseline"
    name = operator_name(baseline)
    build = load(build_manifest)
    if build.get("operator") != name:
        raise ValueError("standalone build operator differs from task baseline")
    seen = {}
    binary = _check_binding(build.get("standalone"), seen)
    verifier = (baseline / "scripts/verify_result.py").resolve()
    bindings_path = task / "input-bindings.json"
    bindings = load(bindings_path)
    rows = bindings.get("cases", [])
    if not isinstance(rows, list) or any(not isinstance(row, dict) or type(row.get("case_id")) is not int for row in rows):
        raise ValueError("invalid frozen case binding")
    by_case = {row["case_id"]: row for row in rows}
    if len(by_case) != len(rows) or set(by_case) != set(ALL_CASES):
        raise ValueError("frozen input bindings must cover exactly twenty cases")
    prepared = []
    for case in cases:
        row = by_case[case]
        metadata_path = (input_root / f"case_{case:02d}" / "metadata.json").resolve()
        if _check_binding(row.get("metadata"), seen) != metadata_path:
            raise ValueError("prepared metadata path differs from frozen input binding")
        if _check_binding(row.get("verifier"), seen) != verifier:
            raise ValueError("only the original task baseline verifier is allowed")
        inputs = row.get("inputs")
        if not isinstance(inputs, dict) or not inputs:
            raise ValueError("frozen input file identities required")
        for ref in inputs.values():
            _check_binding(ref, seen)
        if row.get("oracle_file"):
            _check_binding(row["oracle_file"], seen)
        metadata = load(metadata_path)  # Original oracle JSON may contain IEEE tags.
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        for key in ("input", "x", "mask", "x1", "x2", "x3", "golden"):
            if key in metadata and Path(metadata[key]).resolve() not in seen:
                raise ValueError("metadata references an unbound input/oracle: " + key)
        prepared.append((case, metadata_path, metadata))
    seen[build_manifest] = sha(build_manifest)
    seen[bindings_path] = sha(bindings_path)
    return baseline, name, binary, verifier, prepared, seen


def _process_cost(directory, costs, *, native):
    """Use execution.json, not pre-Popen started.json, to count launched processes."""
    record_path = _execution_path(directory)
    if not record_path.is_file():
        return None
    record = load(record_path)
    exit_status = record.get("exit_status", record.get("exit_code"))
    launched = record.get("new_process_started", exit_status is not None)
    prefix = "native" if native else "verifier"
    costs[prefix + "_processes_started"] += int(launched)
    costs[prefix + "_processes_completed"] += int(launched and exit_status == 0)
    if not native:
        costs["verifier_calls"] += record.get("verifier_calls", int(launched))
        if record.get("mode") != "in_process_original_verifier_v1" and directory.with_suffix(".execution.json").is_file():
            costs["verifier_processes_attempted"] += 1
    if native and launched and exit_status == 0:
        costs["standalone_complete_calls"] += 1
    return record


def _execution_path(directory):
    path = directory / "execution.json"
    return path if path.is_file() else Path(str(directory) + ".execution.json")


def correctness(task, build_manifest, input_root, output, cases=range(1, 21), *, device=0, cpu="8", timeout=1800, reuse_verifier=False):
    """Execute full standalone correctness or raise, always retaining new evidence.

    Returns completion.json's object on success. Failure (including post-health)
    raises after saving completion.json. Existing output is never overwritten.
    Native process counters describe launched standalone command processes; the
    executor's shell/environment preamble remains visible in execution.json.
    """
    task, build_manifest, input_root, output = (Path(p).resolve() for p in (task, build_manifest, input_root, output))
    cases = list(cases)
    if cases != ALL_CASES:
        raise ValueError("standalone correctness requires all twenty cases in frozen order")
    if type(device) is not int or device < 0 or not isinstance(cpu, str) or not cpu or not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf"):
        raise ValueError("invalid execution device/CPU/timeout")
    if type(reuse_verifier) is not bool:
        raise ValueError("reuse_verifier must be an explicit boolean")
    if output == task or output == input_root or output == build_manifest.parent:
        raise ValueError("standalone correctness needs a separate new output directory")
    costs = dict(native_processes_attempted=0, native_processes_started=0, native_processes_completed=0,
                 verifier_processes_attempted=0, verifier_processes_started=0, verifier_processes_completed=0,
                 verifier_call_attempts=0, verifier_calls=0, standalone_complete_calls=0)
    completed, failure, health_error, caught = [], None, None, None
    started = time.time()
    # Host lock also covers identity validation and both fresh health records.
    with exclusive_host():
        output.mkdir(parents=True, exist_ok=False)
        try:
            baseline, operator, binary, verifier, prepared, identities = _prepare(task, build_manifest, input_root, cases)
            oracle_runner = None
            oracle_mode = "independent_python_process"
            if reuse_verifier:
                from msprof_exploration_oracle import MODE, make_run_logged
                from cannbench_shared_context_profile import run_logged as process_logger
                oracle_runner = make_run_logged(process_logger, verifier=verifier, expected_hash=sha(verifier),
                                                metadata_root=output, cpu_affinity=cpu)
                oracle_mode = MODE
            request = {"schema_version": VERSION, "operator": operator, "task": str(task), "build_manifest": pointer(build_manifest),
                       "standalone": pointer(binary), "verifier": pointer(verifier), "input_bindings": pointer(task / "input-bindings.json"),
                       "case_ids": cases, "physical_device": device, "logical_device": 0, "cpu": cpu,
                       "host": socket.gethostname(), "producer": pointer(__file__),
                       "input_files": [{"path": str(path), "sha256": expected} for path, expected in identities.items()],
                       "oracle": "unchanged_original_baseline_verifier", "performance_evaluated": False,
                       "oracle_execution_mode": oracle_mode, "reuse_verifier_requested": reuse_verifier,
                       "prepared_path_validated_here": False, "formal_admission": "not_evaluated", "episode_ref": None}
            save(output / "request.json", request)
            health(output / "health-before.json")
            for case, metadata_path, metadata in prepared:
                directory = output / f"case_{case:02d}"
                directory.mkdir()
                result = {"case_id": case, "status": "failed", "metadata": pointer(metadata_path), "native": None, "verifier": None}
                try:
                    output_tensor = directory / "output.bin"
                    argv = command_from_metadata(baseline, metadata, 0, output_tensor)
                    argv[0] = str(binary)
                    save(directory / "command.json", {"argv": argv, "cwd": str(baseline), "standalone": request["standalone"]})
                    costs["native_processes_attempted"] += 1
                    try:
                        run_process(argv, baseline, directory / "native", device=device, cpu=cpu, timeout=timeout)
                    finally:
                        native = _process_cost(directory / "native", costs, native=True)
                        if native is not None:
                            result["native"] = pointer(directory / "native/execution.json")
                    if native is None or native.get("status") != "passed" or native.get("exit_status") != 0:
                        raise ValueError("standalone has no successful recorded execution")
                    named_outputs = (output_paths(operator, metadata, output_tensor) if is_level2(baseline)
                                     else {"output": str(output_tensor)})
                    if not all(Path(path).is_file() for path in named_outputs.values()):
                        raise ValueError("standalone did not produce every private named output")
                    verification = directory / "verification-metadata.json"
                    save(verification, {**metadata, **named_outputs}, legacy_metadata=True)
                    if sha(verifier) != request["verifier"]["sha256"]:
                        raise ValueError("original baseline verifier changed before validation")
                    costs["verifier_call_attempts"] += 1
                    costs["verifier_processes_attempted"] += int(not reuse_verifier)
                    verify_argv = [sys.executable, "-B", str(verifier), "--metadata", str(verification)]
                    try:
                        if oracle_runner is None:
                            run_process(verify_argv, directory, directory / "verify", device=device, cpu=cpu, timeout=timeout)
                        else:
                            env = dict(os.environ, ASCEND_RT_VISIBLE_DEVICES=str(device), OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", OPENBLAS_NUM_THREADS="2")
                            for key in list(env):
                                if key.startswith(("APROF_CALIBRATION_", "APROF_TIMING", "APROF_WARMUP", "APROF_REPEAT", "APROF_SAMPLES", "APROF_CAPTURE")):
                                    env.pop(key)
                            oracle_runner(verify_argv, directory / "verify", env, timeout, cwd=directory)
                    finally:
                        verified = _process_cost(directory / "verify", costs, native=False)
                        if verified is not None:
                            result["verifier"] = pointer(_execution_path(directory / "verify"))
                    if verified is None or verified.get("exit_status", verified.get("exit_code")) != 0 or verified.get("error"):
                        raise ValueError("original verifier has no successful recorded execution")
                    result.update(status="passed", output=(pointer(output_tensor) if output_tensor.is_file() else None),
                                  outputs={name: pointer(path) for name, path in named_outputs.items()}, verification_metadata=pointer(verification),
                                  verifier_source=request["verifier"], validation_scope="original standalone entry; one complete call")
                    completed.append(result)
                except BaseException as exc:
                    result["error"] = _error(exc)
                    raise
                finally:
                    save(directory / "correctness.json", result)
            # Run only after all native executions have ended; no concurrent IO.
            for path, expected in identities.items():
                if sha(path) != expected:
                    raise ValueError("frozen evidence changed during standalone correctness: " + str(path))
        except BaseException as exc:
            caught, failure = exc, _error(exc)
        finally:
            try:
                health(output / "health-after.json")
            except BaseException as exc:
                health_error = _error(exc)
                if caught is None:
                    caught, failure = exc, health_error
            costs["wall_seconds"] = int(time.time() - started)
            completion = {"schema_version": VERSION, "mode": "standalone_correctness", "status": "passed" if caught is None else "failed",
                          "planned_cases": cases, "completed": completed, "passed_count": len(completed), "error": failure,
                          "health_error": health_error, "actual_costs": costs, "native_started": costs["native_processes_started"] > 0,
                          "started_at": started, "ended_at": time.time(), "performance_evaluated": False,
                          "prepared_path_validated_here": False, "formal_admission": "not_evaluated", "graph_policy_eligible": False, "episode_ref": None}
            completion["reuse_verifier_requested"] = reuse_verifier
            save(output / "completion.json", completion)
        if caught is not None:
            raise caught
    return completion


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("task", "build-manifest", "input-root", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--cpu", default="8")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--reuse-verifier", action="store_true")
    args = parser.parse_args(argv)
    result = correctness(args.task, args.build_manifest, args.input_root, args.output, device=args.device, cpu=args.cpu, timeout=args.timeout,
                         reuse_verifier=args.reuse_verifier)
    print(json.dumps({"status": result["status"], "passed_count": result["passed_count"], "actual_costs": result["actual_costs"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
