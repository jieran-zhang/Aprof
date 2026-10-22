#!/usr/bin/env python3
"""Cache prepared inputs and reference outputs, never candidate correctness results.

Config: schema_version="1.0.0", workload={...}, dependencies={name:file},
commands=[["{dep:python}", "{dep:generator}", "--output", "{output_dir}"]],
outputs=["input.bin", "expected.bin"], optional environment={} and timeout_seconds=300.
Declare every generator/oracle/tool dependency and every semantic environment value.
Dependency locations may differ across candidates; their names and bytes must match.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import time
import uuid
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "runtime/src"))
from aprof_runtime.execution_policy import wait, local_path

VERSION = "prepared_workload_v1"
BASE_ENV = {"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def file_hash(path):
    if not Path(path).is_file():
        raise ValueError(f"dependency/output is not a regular file: {path}")
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return "sha256:" + value.hexdigest()


def no_links(path):
    path = Path(path).absolute()
    for item in (path, *path.parents):
        if item.is_symlink():
            raise ValueError(f"cache/output symlink refused: {item}")
    return path


def relative(value):
    if not isinstance(value, str):
        raise ValueError("output paths must be strings")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or str(path) != value or value == "." or "\\" in value:
        raise ValueError("outputs must be canonical relative file paths")
    return value


def save(path, value):
    path = no_links(path)
    with path.open("xb") as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())


def identity(config):
    allowed = {"schema_version", "workload", "dependencies", "commands", "outputs", "environment", "timeout_seconds"}
    required = {"schema_version", "workload", "dependencies", "commands", "outputs"}
    if not isinstance(config, dict) or not required.issubset(config) or set(config) - allowed:
        raise ValueError("config requires schema_version,workload,dependencies,commands,outputs; unknown fields refused")
    if config["schema_version"] != "1.0.0" or not isinstance(config["workload"], dict) or not config["workload"]:
        raise ValueError("schema_version must be 1.0.0 and workload a nonempty object")
    dependencies = config["dependencies"]
    if not isinstance(dependencies, dict) or not dependencies:
        raise ValueError("declare generator/oracle/tool dependency files")
    paths, hashes = {}, {}
    for name, value in dependencies.items():
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*", name) or not isinstance(value, str):
            raise ValueError("dependency names must be stable logical identifiers and paths strings")
        path = Path(value).resolve(strict=True)  # System interpreter symlinks are normal.
        paths[name], hashes[name] = str(path), file_hash(path)
    commands = config["commands"]
    if not isinstance(commands, list) or not commands:
        raise ValueError("commands must contain argv arrays")
    for command in commands:
        if not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in command):
            raise ValueError("commands must contain nonempty string argv arrays")
        match = re.fullmatch(r"\{dep:([^{}]+)\}", command[0])
        if not match or match.group(1) not in paths:
            raise ValueError("command executable must be an explicitly hashed {dep:name}")
        for arg in command:
            for token in re.findall(r"\{([^{}]+)\}", arg):
                if token != "output_dir" and (not token.startswith("dep:") or token[4:] not in paths):
                    raise ValueError(f"unknown command placeholder: {token}")
    outputs = config["outputs"]
    if not isinstance(outputs, list) or not outputs or len(set(outputs)) != len(outputs):
        raise ValueError("outputs must be a nonempty list of distinct file paths")
    outputs = sorted(relative(value) for value in outputs)
    environment = config.get("environment", {})
    if not isinstance(environment, dict) or any(not isinstance(key, str) or not key or "=" in key or "\0" in key or not isinstance(value, str) or "\0" in value for key, value in environment.items()):
        raise ValueError("environment must map valid names to strings")
    timeout = config.get("timeout_seconds", 300)
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout_seconds must be positive and finite")
    spec = dict(protocol_version=VERSION, producer_hash=file_hash(Path(__file__).resolve()),
                workload=config["workload"], dependencies=hashes, commands=commands, outputs=outputs,
                environment={**BASE_ENV, **environment}, timeout_seconds=timeout)
    # Serializing here also rejects NaN/Infinity in workload before any execution.
    return digest(canonical(spec)), spec, paths


def expand(command, paths, output_dir):
    def replace(match):
        token = match.group(1)
        return str(output_dir) if token == "output_dir" else paths[token[4:]]
    return [re.sub(r"\{([^{}]+)\}", replace, argument) for argument in command]


def output_inventory(output_dir):
    output_dir = no_links(output_dir)
    if not output_dir.is_dir():
        raise ValueError("prepared output directory is missing")
    files = {}
    for parent, directories, names in os.walk(output_dir, followlinks=False):
        for name in directories + names:
            no_links(Path(parent) / name)
        for name in names:
            path = Path(parent) / name
            files[str(path.relative_to(output_dir))] = file_hash(path)
    return dict(sorted(files.items()))


def checked_identity(config, expected):
    key, spec, paths = identity(config)
    if spec != expected:
        raise ValueError("preparation dependency/config/producer identity changed")
    return {"cache_key": key, "producer_hash": spec["producer_hash"], "dependencies": spec["dependencies"]}, paths


def run_command(command, config, spec, output_dir, attempt, index):
    started = time.monotonic()
    execution = {"command_template": command, "exit_code": None, "error": None}
    process = None
    stdout, stderr = b"", b""
    interrupted = None
    try:
        execution["identity_before"], paths = checked_identity(config, spec)
        argv = expand(command, paths, output_dir)
        execution.update(argv=argv, cwd=str(output_dir))
        process = subprocess.Popen(argv, cwd=output_dir, env=spec["environment"], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        stdout, stderr = wait(process, target_seconds=spec["timeout_seconds"], checkpoint=Path(output_dir)/"checkpoints.jsonl", communicate=True)
        execution["exit_code"] = process.returncode
        if process.returncode:
            raise RuntimeError(f"preparation command exited {process.returncode}")
    except BaseException as error:
        execution["error"] = {"type": type(error).__name__, "message": str(error)}
        if isinstance(error, (KeyboardInterrupt, SystemExit)):
            interrupted = error
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        if process is not None:
            execution["exit_code"] = process.returncode
    finally:
        try:
            execution["identity_after"], _ = checked_identity(config, spec)
        except Exception as error:
            execution["error"] = {"type": type(error).__name__, "message": str(error)}
        for name, data in (("stdout", stdout), ("stderr", stderr)):
            filename = f"command-{index:03d}.{name}.log"
            path = attempt / "logs" / filename
            with path.open("xb") as stream:
                stream.write(data)
            execution[name] = {"path": "logs/" + filename, "hash": file_hash(path)}
        execution["elapsed_seconds"] = time.monotonic() - started
        save(attempt / "logs" / f"command-{index:03d}.json", execution)
    if interrupted:
        raise interrupted
    if execution["error"]:
        raise RuntimeError(execution["error"]["message"])
    return execution


def verify_entry(entry, ready, spec):
    if set(ready) != {"protocol_version", "attempt", "entry_hash"} or ready["protocol_version"] != VERSION or not re.fullmatch(r"[0-9a-f]{32}", ready["attempt"]):
        raise ValueError("malformed preparation completion marker")
    attempt = no_links(entry / "attempts" / ready["attempt"])
    receipt = no_links(attempt / "entry.json")
    if file_hash(receipt) != ready["entry_hash"]:
        raise ValueError("preparation entry receipt was modified")
    record = json.loads(receipt.read_text())
    if record.get("identity") != spec or record.get("status") != "complete":
        raise ValueError("preparation entry identity/status mismatch")
    output_dir = no_links(attempt / "outputs")
    if record.get("output_dir") != str(output_dir):
        raise ValueError("prepared cache was relocated; embedded paths require a new cache entry")
    files = output_inventory(output_dir)
    if sorted(files) != spec["outputs"] or record.get("outputs") != files:
        raise ValueError("prepared output files are missing, unexpected or modified")
    expected_check = {"cache_key": digest(canonical(spec)), "producer_hash": spec["producer_hash"], "dependencies": spec["dependencies"]}
    executions = record.get("executions", [])
    if len(executions) != len(spec["commands"]):
        raise ValueError("preparation process receipts are incomplete")
    for index, execution in enumerate(executions):
        if execution.get("command_template") != spec["commands"][index] or execution.get("exit_code") != 0 or execution.get("error") is not None or execution.get("identity_before") != expected_check or execution.get("identity_after") != expected_check:
            raise ValueError("preparation process identity/status is invalid")
        raw_receipt = no_links(attempt / "logs" / f"command-{index:03d}.json")
        if json.loads(raw_receipt.read_text()) != execution:
            raise ValueError("preparation process receipt was modified")
        for name in ("stdout", "stderr"):
            log = execution[name]
            if file_hash(no_links(attempt / relative(log["path"]))) != log["hash"]:
                raise ValueError("preparation process log was modified")
    return record, output_dir, ready["entry_hash"]


def prepare(config, cache_dir, receipt_path):
    started = time.monotonic()
    key, spec, _ = identity(config)
    local_path(cache_dir); local_path(receipt_path)
    cache = no_links(cache_dir)
    receipt_path = no_links(receipt_path)
    if receipt_path.exists():
        raise FileExistsError(f"call receipt already exists: {receipt_path}")
    cache.mkdir(parents=True, exist_ok=True)
    entries, locks = cache / "entries", cache / "locks"
    for path in (entries, locks):
        no_links(path).mkdir(exist_ok=True)
    hexadecimal = key.removeprefix("sha256:")
    lock = no_links(locks / hexadecimal)
    try:
        lock.mkdir()
    except FileExistsError as error:
        raise RuntimeError(f"preparation entry is busy or has an interrupted owner; inspect lock: {lock}") from error
    attempt = None
    try:
        save(lock / "owner.json", {"pid": os.getpid(), "started_at": time.time(), "cache_key": key})
        entry = no_links(entries / hexadecimal)
        entry.mkdir(exist_ok=True)
        ready_path = no_links(entry / "ready.json")
        hit = ready_path.exists()
        if hit:
            record, output_dir, entry_hash = verify_entry(entry, json.loads(ready_path.read_text()), spec)
        else:
            attempts = no_links(entry / "attempts")
            attempts.mkdir(exist_ok=True)
            attempt = attempts / uuid.uuid4().hex
            attempt.mkdir()
            output_dir = attempt / "outputs"
            output_dir.mkdir()
            (attempt / "logs").mkdir()
            executions = [run_command(command, config, spec, output_dir, attempt, index)
                          for index, command in enumerate(spec["commands"])]
            files = output_inventory(output_dir)
            if sorted(files) != spec["outputs"]:
                raise ValueError("prepared files do not match declared outputs exactly")
            checked_identity(config, spec)
            record = dict(protocol_version=VERSION, status="complete", identity=spec,
                          output_dir=str(output_dir), outputs=files, executions=executions,
                          preparation_seconds=sum(item["elapsed_seconds"] for item in executions))
            entry_receipt = attempt / "entry.json"
            save(entry_receipt, record)
            entry_hash = file_hash(entry_receipt)
            marker = dict(protocol_version=VERSION, attempt=attempt.name, entry_hash=entry_hash)
            # Output paths are final from the start: generators may embed them in metadata.
            # Publish only this small marker atomically; never rename generated files.
            temporary = entry / (".ready-" + uuid.uuid4().hex)
            save(temporary, marker)
            os.link(temporary, ready_path)  # Atomic publication without overwriting another completion.
            temporary.unlink()
        checked_identity(config, spec)
        result = dict(protocol_version=VERSION, status="hit" if hit else "prepared", cache_key=key,
                      entry_receipt_hash=entry_hash, output_dir=str(output_dir), outputs=record["outputs"],
                      preparation_seconds=0.0 if hit else record["preparation_seconds"],
                      elapsed_seconds=time.monotonic() - started, candidate_correctness_cached=False)
        save(receipt_path, result)
        return result
    except BaseException as error:
        failure = dict(protocol_version=VERSION, status="failed", cache_key=key,
                       error={"type": type(error).__name__, "message": str(error)},
                       elapsed_seconds=time.monotonic() - started, candidate_correctness_cached=False)
        if attempt is not None and not (attempt / "failure.json").exists():
            save(attempt / "failure.json", failure)
        if not receipt_path.exists():
            save(receipt_path, failure)
        raise
    finally:
        # Only this owner creates/removes this lock; no timeout-based stale-lock deletion.
        owner = lock / "owner.json"
        if owner.exists():
            owner.unlink()
        lock.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, help="JSON preparation contract with explicit dependencies and argv")
    parser.add_argument("--cache-dir", required=True, help="shared local cache; candidates must treat prepared files as read-only")
    parser.add_argument("--receipt", required=True, help="new per-call JSON receipt, separate from immutable cache evidence")
    args = parser.parse_args()
    try:
        result = prepare(json.loads(Path(args.config).read_text()), args.cache_dir, args.receipt)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, RuntimeError, KeyError, TypeError) as error:
        parser.exit(2, f"prepare_workload: {error}\n")


if __name__ == "__main__":
    main()
