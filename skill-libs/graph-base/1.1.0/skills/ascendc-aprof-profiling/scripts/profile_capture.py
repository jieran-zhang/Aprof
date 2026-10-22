#!/usr/bin/env python3
"""Collect independent hardware profiles in the task workspace without archiving.

The command never builds, generates data, verifies outputs or changes a driver.
Use it only after those stages have passed. Run ``capture --help`` for inputs.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import shlex
import signal
import socket
import platform
import subprocess
import sys
import time
import tempfile

RELEASE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RELEASE / "runtime" / "src"))
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.jsonio import canonical_json
from aprof_runtime.task_measurement_admission import LOCAL_PROFILE_FILESYSTEMS, select_mount

BASIC = ["Pipeline", "PipeUtilization", "Memory", "MemoryL0", "MemoryUB", "L2Cache", "ArithmeticUtilization"]
SECTIONS = [*BASIC, "ResourceConflictRatio"]
RECOGNIZED = {"summary.jsonl", "HardwareInfo.jsonl", "PipeTrace.json", *[name + ".csv" for name in SECTIONS]}


def save(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def select_backend(backend, architecture, soc=""):
    label = re.sub(r"[^a-z0-9]", "", architecture.lower())
    chip = re.sub(r"[^a-z0-9]", "", str(soc).lower())
    is_950 = label in {"ascend950", "950", "dav3510"} or label.startswith("ascend950pr")
    is_a3 = label in {"ascend910c", "910c", "a3"}
    if not (is_950 or is_a3):
        raise ValueError("unverified architecture: support is Ascend950/dav-3510 or Ascend910C/A3")
    if is_950 and chip and not ("950" in chip or chip in {"3510", "dav3510", "9599"}):
        raise ValueError("architecture and SoC disagree")
    if is_a3 and chip and not ("910" in chip or chip in {"9392", "a3", "dav2201", "2201"}):
        raise ValueError("architecture and SoC disagree")
    if backend not in {"auto", "npu-compute", "msprof"}:
        raise ValueError("unknown profiler backend")
    if backend == "npu-compute" and not is_950:
        raise ValueError("npu-compute supports Ascend950/dav-3510; Ascend910C/A3 must use msprof")
    return ("npu-compute" if is_950 else "msprof") if backend == "auto" else backend


def regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"expected non-symlink regular file: {path}")
    return path


def contained(path, parent):
    path, parent = Path(path), Path(parent).resolve()
    if path.is_symlink():
        raise ValueError(f"symlink result refused: {path}")
    resolved = path.resolve()
    if not resolved.is_relative_to(parent):
        raise ValueError(f"result escaped output directory: {path}")
    for ancestor in path.absolute().parents:
        if ancestor == parent:
            break
        if ancestor.is_symlink():
            raise ValueError(f"symlink ancestor refused: {ancestor}")
    return resolved


def file_hash(path):
    digest = hashlib.sha256()
    with regular(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def identity_state(binding):
    source = {"schema_version": "1.0.0", "files": source_inventory(binding["source_dir"])}
    source_bytes = canonical_json(source).encode("utf-8")
    return {"binary_hash": file_hash(binding["binary"]), "tool_hash": file_hash(binding["tool"]),
            "source_hash": "sha256:" + hashlib.sha256(source_bytes).hexdigest()}


def run(argv, cwd, output, timeout, store, binding=None, *, environment=None):
    """Run one process group, retain failure receipts, and terminate timed-out children."""
    argv = [str(value) for value in argv]
    if environment is not None:
        if not isinstance(environment, dict) or any(
                not isinstance(key, str) or not key or "\0" in key or "=" in key
                or not isinstance(value, str) or "\0" in value
                for key, value in environment.items()):
            raise ValueError("environment overrides must be a string mapping")
        launch_environment = {key: value for key, value in os.environ.items()
                              if not key.startswith("APROF_")}
        launch_environment.update(environment)
    else:
        launch_environment = None
    started = time.time()
    process = None
    stdout, stderr, error = b"", b"", None
    checks = {}
    try:
        if binding is not None:
            checks["before"] = identity_state(binding)
            if checks["before"] != binding["expected"]:
                raise ValueError("binary/tool/source identity changed before launch")
        process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   start_new_session=True, env=launch_environment)
        stdout, stderr = process.communicate(timeout=timeout)
    except BaseException as exc:
        error = {"type": type(exc).__name__, "message": str(exc)}
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
    finally:
        if binding is not None:
            try:
                checks["after"] = identity_state(binding)
                if checks["after"] != binding["expected"]:
                    raise ValueError("binary/tool/source identity changed during launch")
            except Exception as exc:
                error = {"type": type(exc).__name__, "message": str(exc)}
        logs = {}
        for name, data in (("stdout", stdout), ("stderr", stderr)):
            path = Path(str(output) + f".{name}.log")
            with path.open("xb") as stream:
                stream.write(data)
            logs[name + "_hash"] = store.register_artifact(path)
        record = dict(argv=argv, cwd=str(cwd), started_at=started, ended_at=time.time(),
                      exit_code=process.returncode if process else -1, error=error, **logs)
        if environment is not None:
            record.update(environment=environment, timeout_seconds=timeout,
                          pid=process.pid if process else None)
        if binding is not None:
            record["identity_checks"] = checks
        receipt = Path(str(output) + ".execution.json")
        save(receipt, record)
        record["log_hash"] = store.register_artifact(receipt)
    record["text"] = (stdout + b"\n" + stderr).decode("utf-8", errors="replace")
    if record["exit_code"] != 0 or error:
        raise RuntimeError(f"command failed; retained receipt: {receipt}")
    return record


def terminal_path(text, key, cwd, output, directory=False):
    matches = re.findall(r"^npu-compute:\s*" + key + r"=\s*(.+?)\s*$", text, re.MULTILINE)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one npu-compute {key}= terminal receipt")
    path = Path(matches[0])
    if not path.is_absolute():
        path = Path(cwd) / path
    path = contained(path, output)
    if directory:
        if not path.is_dir():
            raise ValueError("reported unpacked directory does not exist")
    elif not regular(path).name.endswith(".npu-rep"):
        raise ValueError("reported capture is not an existing .npu-rep file")
    return path


def safe_files(root):
    """Bound traversal to one explicitly selected output tree, refusing links."""
    result = []
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            candidate = Path(directory) / name
            if candidate.is_symlink():
                raise ValueError(f"symlink result refused: {candidate}")
        result.extend(Path(directory) / name for name in files)
    return sorted(result)


def collection_directory(root, backend, kernel, selected=None):
    root = Path(root)
    files = safe_files(root)
    if selected is not None:
        if Path(selected).is_absolute() or ".." in Path(selected).parts:
            raise ValueError("collection must be a safe relative path")
        chosen = contained(root / selected, root)
    else:
        if backend == "npu-compute":
            choices = {path.parent for path in files if path.name in RECOGNIZED and path.name != "HardwareInfo.jsonl"}
        else:
            choices = {path.parent for path in files if re.fullmatch(r"OpBasicInfo(?:_\d+)?\.csv", path.name)}
            matching = {path for path in choices if kernel in path.relative_to(root).parts}
            if matching:
                choices = matching
        if len(choices) != 1:
            raise ValueError("select exactly one collection; found: " + ", ".join(str(path.relative_to(root)) for path in sorted(choices)))
        chosen = next(iter(choices))
    if not chosen.is_dir():
        raise ValueError("selected collection is not a directory")
    direct = [path for path in files if path.parent == chosen]
    if backend == "npu-compute":
        if not any(path.name in RECOGNIZED - {"HardwareInfo.jsonl"} for path in direct):
            raise ValueError("selected collection has no recognizable npu-compute results")
    else:
        basic = [path for path in direct if re.fullmatch(r"OpBasicInfo(?:_\d+)?\.csv", path.name)]
        if len(basic) != 1:
            raise ValueError("selected msprof collection requires exactly one OpBasicInfo CSV")
        with basic[0].open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames):
                raise ValueError("invalid OpBasicInfo header")
            rows = list(reader)
        if not rows:
            raise ValueError("empty OpBasicInfo")
        for row in rows:
            names = {value.strip() for key, value in row.items() if key and re.sub(r"[ _]", "", key).lower() in {"opname", "kernelname"} and value}
            if names and names != {kernel}:
                raise ValueError("OpBasicInfo kernel disagrees with selected kernel")
            if not names and kernel not in chosen.relative_to(root).parts:
                raise ValueError("msprof CSV and directory do not identify selected kernel")
    return chosen


def source_inventory(source_dir, store=None):
    root = Path(source_dir).resolve()
    if not root.is_dir():
        raise ValueError("source_dir must be a complete operator project")
    excluded = {".git", ".aprof", "build", "__pycache__", ".pytest_cache"}
    files = {}
    for directory, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in excluded)
        for name in dirs + names:
            if (Path(directory) / name).is_symlink():
                raise ValueError("source snapshots cannot contain symlinks")
        for name in sorted(names):
            path = Path(directory) / name
            if path.stat().st_size > 100 * 1024 * 1024:
                raise ValueError("source file exceeds 100 MiB; use a clean operator source project")
            files[str(path.relative_to(root))] = store.register_artifact(path) if store is not None else file_hash(path)
    if not files:
        raise ValueError("source snapshot cannot be empty")
    return files


def source_bundle(source_dir, output, store):
    files = source_inventory(source_dir, store)
    path = output / "source-bundle.json"
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical_json({"schema_version": "1.0.0", "files": files}))
    return store.register_artifact(path)


def sections_for(config, backend):
    if backend == "msprof":
        if config.get("sections") or config.get("set"):
            raise ValueError("npu-compute sections/set cannot be applied to msprof")
        return ["Default"]
    sections = []
    if config.get("set"):
        if config["set"] not in {"basic", "full"}:
            raise ValueError("npu-compute set must be basic or full")
        sections.extend(BASIC if config["set"] == "basic" else SECTIONS)
    sections.extend(config.get("sections", []))
    if not sections:
        sections = BASIC.copy()
    if any(section not in SECTIONS for section in sections):
        raise ValueError("unknown npu-compute section")
    return list(dict.fromkeys(sections))


def capture(config, output=None, *, deadline_monotonic=None, before_unit=None):
    if deadline_monotonic is not None and (type(deadline_monotonic) not in (int, float)
            or not math.isfinite(deadline_monotonic)):
        raise ValueError("invalid absolute profiling deadline")
    if before_unit is not None and (not callable(before_unit) or deadline_monotonic is None):
        raise ValueError("trusted profiling unit callback requires an absolute deadline")

    def allowance(unit_deadline=None):
        end = deadline_monotonic if unit_deadline is None else unit_deadline
        if end is None:
            return timeout
        left = end - time.monotonic()
        if left <= 0:
            raise TimeoutError("original profiling unit deadline expired")
        return min(timeout, left)

    def begin(kind, index):
        end = deadline_monotonic if before_unit is None else before_unit(kind, index)
        if before_unit is not None and end is None:
            raise ValueError("trusted profiling unit callback omitted its deadline")
        if end is not None and (type(end) not in (int, float) or not math.isfinite(end)
                or deadline_monotonic is not None and end > deadline_monotonic):
            raise ValueError("profiling unit cannot extend the original deadline")
        allowance(end)
        return end

    backend = select_backend(config.get("backend", "auto"), config["architecture"], config.get("soc", ""))
    command = config["command"]
    if not isinstance(command, list) or not command or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in command):
        raise ValueError("command must be a non-empty JSON string array")
    if str(config["device"]) != "0" and not {"physical_device", "chip"}.issubset(config):
        raise ValueError("nonzero logical device requires explicit physical_device and chip mapping")
    if "--device" in command:
        index = command.index("--device")
        if index + 1 >= len(command) or command[index + 1] != str(config["device"]):
            raise ValueError("workload command device disagrees with capture device")
    cwd = Path(config["cwd"]).resolve()
    binary = regular(Path(config["binary"]).resolve())
    program = Path(command[0])
    program = (cwd / program).resolve() if not program.is_absolute() else program.resolve()
    if program != binary:
        raise ValueError("command must directly execute the declared operator binary")
    command = [str(binary), *command[1:]]
    for name, default, minimum in (("warmups", 10, 0), ("repeats", 5, 1), ("case_id", None, 1)):
        value = config.get(name, default)
        if type(value) is not int or value < minimum:
            raise ValueError(f"invalid {name}")
    if config["role"] not in {"baseline", "candidate"} or not isinstance(config["kernel"], str) or not config["kernel"].strip() or config["kernel"] == "*" or any(ord(char) < 32 for char in config["kernel"]):
        raise ValueError("role/kernel must identify exactly one operator kernel")
    timeout = float(config.get("timeout_seconds", 120))
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid timeout_seconds")
    if not isinstance(config["workload"], dict) or not config["workload"]:
        raise ValueError("workload must explicitly describe the case")
    tool = Path(config.get("tool_path") or shutil.which(backend) or "")
    if not tool.is_file():
        raise ValueError(f"{backend} executable not found; system installation is unchanged")
    tool = tool.resolve()
    sections = sections_for(config, backend)
    output = Path(output).absolute() if output is not None else Path(tempfile.mkdtemp(prefix="aprof-profile-")) / "capture"
    if output.resolve() != output:
        raise ValueError("profile work directory must be canonical")
    if select_mount(Path("/proc/self/mountinfo").read_text(), output)["filesystem_type"] not in LOCAL_PROFILE_FILESYSTEMS:
        raise ValueError("profile work directory must use a supported local filesystem")
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    if output.stat().st_mode & 0o777 != 0o700:
        raise ValueError("profile work directory must be private mode 0700")
    store = LocalEvidence(output / "records")
    manifest, active_unit = None, None
    try:
        probe = run([config.get("npu_smi_path", "npu-smi"), "info", "-t", "board", "-i", str(config.get("physical_device", config["device"])), "-c", str(config.get("chip", 0))], cwd, output / "hardware", allowance(), store)
        expected = "950" if backend == "npu-compute" or "950" in config["architecture"] or "3510" in config["architecture"] else "9392"
        if expected not in probe["text"] and (expected != "950" or "3510" not in probe["text"]):
            raise ValueError("actual npu-smi board identity does not verify the requested architecture")
        board = {key.strip(): value.strip() for line in probe["text"].splitlines() if ":" in line for key, value in [line.split(":", 1)]}
        stable_board = {key: board[key] for key in ("NPU Name", "Chip Name", "Chip Version", "Board ID", "Firmware Version", "PCIe Bus Info") if key in board}
        cann_home = Path(os.environ.get("ASCEND_HOME_PATH", "/usr/local/Ascend/ascend-toolkit/latest")).resolve()
        install_info = cann_home / (platform.machine() + "-linux") / "ascend_toolkit_install.info"
        cann_version = {}
        if install_info.is_file():
            cann_version = {key: value for line in install_info.read_text().splitlines() if "=" in line for key, value in [line.split("=", 1)] if "version" in key.lower()}
        hardware = dict(architecture=config["architecture"], soc=str(config.get("soc", "")), device=str(config["device"]), physical_device=str(config.get("physical_device", config["device"])), chip=str(config.get("chip", 0)), host=socket.gethostname(), board=stable_board, cann_home=str(cann_home), cann_version=cann_version, visible_devices={key: os.environ.get(key, "") for key in ("ASCEND_RT_VISIBLE_DEVICES", "ASCEND_VISIBLE_DEVICES")})
        hardware_path = output / "hardware.json"
        save(hardware_path, hardware)
        workload_path = output / "workload.json"
        save(workload_path, config["workload"])
        capability_args = [str(tool), "--list-sections"] if backend == "npu-compute" else [str(tool), "op", "--help"]
        capability = run(capability_args, cwd, output / "tool-capabilities", allowance(), store)
        if backend == "npu-compute" and any(section not in capability["text"] for section in sections):
            raise ValueError("installed npu-compute does not advertise requested sections")
        tool_hash = store.register_artifact(tool)
        manifest = dict(schema_version="1.0.0", collector_hash=store.register_artifact(Path(__file__).resolve()), protocol_version="independent_capture_v1", backend=backend, role=config["role"], case_id=config["case_id"], kernel=config["kernel"], workload_hash=store.register_artifact(workload_path), source_hash=source_bundle(config["source_dir"], output, store), binary_hash=store.register_artifact(binary), hardware_hash=store.register_artifact(hardware_path), tool={"executable_hash": tool_hash, "version": "content-addressed:" + tool_hash + ";capabilities:" + capability["stdout_hash"]}, policy={"warmups": config.get("warmups", 10), "repeats": config.get("repeats", 5), "sections": sections}, warmup_runs=[], captures=[])
        binding = {"binary": binary, "tool": tool, "source_dir": config["source_dir"],
                   "expected": {"binary_hash": manifest["binary_hash"], "tool_hash": tool_hash, "source_hash": manifest["source_hash"]}}
        for index in range(manifest["policy"]["warmups"]):
            active_unit = {"kind": "warmup", "index": index}
            unit_deadline = begin("warmup", index)
            record = run(command, cwd, output / f"warmup-{index:03d}", allowance(unit_deadline), store, binding)
            manifest["warmup_runs"].append({key: record[key] for key in ("argv", "exit_code", "log_hash")})
            allowance(unit_deadline)
        for index in range(manifest["policy"]["repeats"]):
            active_unit = {"kind": "capture", "index": index}
            unit_deadline = begin("capture", index)
            capture_id = f"capture-{index:03d}"
            directory = output / capture_id
            directory.mkdir()
            if backend == "npu-compute":
                argv = [str(tool)]
                for section in sections:
                    argv.extend(["--section", section])
                argv.extend(["--export", str(directory / "capture.npu-rep"), "--", *command])
            else:
                argv = [str(tool), "op", "--warm-up=0", "--launch-count=1", "--aic-metrics=Default", "--output=" + str(directory / "raw"), "--application=" + shlex.join(command)]
            execution = run(argv, cwd, directory / "capture", allowance(unit_deadline), store, binding)
            receipt = {"capture": {key: value for key, value in execution.items() if key != "text"}, "hardware_probe_hash": probe["log_hash"], "capabilities_hash": capability["log_hash"]}
            binary_reports = []
            if backend == "npu-compute":
                report = terminal_path(execution["text"], "report", cwd, directory)
                binary_reports.append(report)
                unpack_parent = directory / "unpacked"
                unpack_parent.mkdir()
                imported = run([str(tool), "--import", str(report), "--export", str(unpack_parent)], cwd, directory / "import", allowance(unit_deadline), store, binding)
                raw = terminal_path(imported["text"], "unpacked", cwd, unpack_parent, directory=True)
                receipt["import"] = {key: value for key, value in imported.items() if key != "text"}
                receipt.update(report=str(report), unpacked=str(raw))
            else:
                raw = directory / "raw"
            chosen = collection_directory(raw, backend, config["kernel"], config.get("collection"))
            selected = sorted(path for path in chosen.iterdir() if path.is_file())
            if backend == "npu-compute":
                hardware_files = [path for path in safe_files(raw) if path.name == "HardwareInfo.jsonl"]
                if len(hardware_files) != 1:
                    raise ValueError("npu-compute report must identify one HardwareInfo.jsonl")
                info = [json.loads(line) for line in hardware_files[0].read_text().splitlines() if line.strip()]
                device_rows = [row for row in info if row.get("category") == "Device Info"]
                if len(device_rows) != 1 or str(device_rows[0].get("arch info")) != "3510":
                    raise ValueError("npu-compute HardwareInfo does not verify dav-3510")
                summary = chosen / "summary.jsonl"
                if not summary.is_file():
                    raise ValueError("npu-compute exact kernel identity requires summary.jsonl OpInfoSummary")
                summary_rows = [json.loads(line) for line in summary.read_text().splitlines() if line.strip()]
                op_rows = [row for row in summary_rows if row.get("category") == "OpInfoSummary"]
                if len(op_rows) != 1 or op_rows[0].get("Op Name") != config["kernel"] or str(op_rows[0].get("Device Id")) != str(config["device"]):
                    raise ValueError("npu-compute OpInfoSummary kernel/device differs from requested scope")
                report_identity = {row["category"]: row for row in info if row.get("category") in {"Device Info", "AI Core Information", "CPU Information"}}
                report_identity["frequencies"] = {key: op_rows[0].get(key) for key in ("Current Freq", "Rated Freq")}
                if index == 0:
                    hardware["report_identity"] = report_identity
                    hardware_profile_path = output / "hardware-profile.json"
                    save(hardware_profile_path, hardware)
                    manifest["hardware_hash"] = store.register_artifact(hardware_profile_path)
                elif hardware["report_identity"] != report_identity:
                    raise ValueError("npu-compute chip/core/frequency identity changed across independent captures")
                selected.extend(path for path in hardware_files if path not in selected)
            files = []
            for path in sorted(set(selected + binary_reports)):
                contained(path, directory)
                suffix = path.suffix.lower().lstrip(".")
                files.append(dict(path=str(path.relative_to(output)), artifact_hash=store.register_artifact(regular(path)), format=suffix if suffix in {"csv", "jsonl", "json"} else "binary", kernel=config["kernel"]))
            receipt.update(collection=str(chosen.relative_to(output)), kernel=config["kernel"], files=files)
            receipt["capture_scope"] = {key: manifest[key] for key in ("backend", "role", "case_id", "kernel", "workload_hash", "source_hash", "binary_hash", "hardware_hash", "tool", "policy", "collector_hash", "protocol_version")}
            receipt["capture_scope"].update(capture_id=capture_id, collection=str(chosen.relative_to(output)), files=files)
            receipt_path = directory / "receipt.json"
            save(receipt_path, receipt)
            manifest["captures"].append(dict(capture_id=capture_id, collection=str(chosen.relative_to(output)), argv=argv, exit_code=0, log_hash=store.register_artifact(receipt_path), files=files))
            allowance(unit_deadline)
        active_unit = None
        if identity_state(binding) != binding["expected"]:
            raise ValueError("binary/tool/source identity changed before manifest publication")
        allowance()
        manifest_path = output / "capture-manifest.json"
        save(manifest_path, manifest)
        digest = store.register_artifact(manifest_path)
        result = dict(manifest=str(manifest_path), manifest_hash=digest, local_index=str(store.write_index(output / "local-index.json")), backend=backend, independent_captures=len(manifest["captures"]), performance_gate=False)
        save(output / "result.json", result)
        return result
    except BaseException as exc:
        failure = {"error": type(exc).__name__, "message": str(exc), "backend": backend,
                   "next_or_active_unit": active_unit, "performance_gate": False}
        if manifest is not None:
            save(output / "partial-manifest.json", manifest)
            failure["partial_manifest_ref"] = store.register_artifact(output / "partial-manifest.json")
        save(output / "failure.json", failure)
        store.register_artifact(output / "failure.json")
        store.write_index(output / "local-index.json")
        save(output / "result.json", {"status": "failed", "failure": failure,
             "local_index": str(output / "local-index.json"), "performance_gate": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    select = sub.add_parser("select", help="resolve declared support; capture additionally verifies actual hardware")
    select.add_argument("--backend", choices=["auto", "npu-compute", "msprof"], default="auto")
    select.add_argument("--architecture", required=True)
    select.add_argument("--soc", default="")
    collect = sub.add_parser("capture", help="collect after build/full correctness; config is a JSON object")
    collect.add_argument("--config", required=True, help="backend,architecture,soc,device,case_id,kernel,role,source_dir,binary,workload,command,cwd; optional warmups,repeats,timeout_seconds,sections,set,collection,tool_path")
    collect.add_argument("--output", help="new task-local directory; defaults to a temporary workspace")
    args = parser.parse_args()
    try:
        if args.action == "select":
            result = {"backend": select_backend(args.backend, args.architecture, args.soc), "architecture": args.architecture, "hardware_verified": False}
        else:
            result = capture(json.loads(Path(args.config).read_text()), args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        parser.exit(2, f"profile_capture: {exc}\n")


if __name__ == "__main__":
    main()
