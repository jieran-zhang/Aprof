#!/usr/bin/env python3
"""Draft calibrated Task Duration collection using native Task profiling.

Measurement and online validation use local files only. Optional trace archival
belongs to the task controller after this entry has finished.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import platform
import re
import shutil
import socket
import stat
import sys
import tempfile
import time

SCRIPTS = Path(__file__).resolve().parent
RELEASE = SCRIPTS.parents[2]
sys.path.insert(0, str(RELEASE / "runtime/src"))
sys.path.insert(0, str(SCRIPTS))

import device_shared_timing as shared
import device_task_timing as old
from persistent_oracle import PersistentOracle, validate_plan
from aprof_runtime.jsonio import file_hash
from aprof_runtime.measurement_admission import _phase_controls, _summarize_values
from aprof_runtime.profile_evidence import _json
from aprof_runtime.local_evidence import LocalEvidence
from aprof_runtime.task_timing import protocol_commands
from aprof_runtime.task_window_timing import case_task_config, partition_window_tasks, choose_task_repeat
from aprof_runtime.task_window_measurement_admission import replay_task_budget, collection_unit_deadline
from aprof_runtime.traces import register_json_artifact


PROTOCOL = "shared_buffer_msprof_task_window_v5"
METRIC = "msprof.op_summary.Task_Duration"
HEADER_ASSET = RELEASE / "skills/ascendc-aprof-profiling/assets/device_task_profile.h"
SUMMARY_ENTRY = Path("/usr/local/Ascend/cann-9.0.0/tools/profiler/profiler_tool/analysis/msprof/msprof.py")
SUMMARY_PYTHON = Path("/usr/local/python3.11.15/bin/python3.11")
PRODUCER_FILES = (*old.PRODUCER_FILES,
    "skills/ascendc-aprof-profiling/scripts/device_task_window_timing.py",
    "runtime/src/aprof_runtime/task_window_timing.py",
    "runtime/src/aprof_runtime/local_evidence.py",
    "runtime/src/aprof_runtime/task_window_measurement_admission.py",
    "runtime/src/aprof_runtime/measurement_entry.py",
    "runtime/src/aprof_runtime/exploration.py",
    "runtime/src/aprof_runtime/full_call_pmu.py",
    "runtime/src/aprof_runtime/episodes.py",
    "skills/ascendc-aprof-profiling/assets/device_task_profile.h")
ROLES, PHASES = shared.ROLES, shared.PHASES
PILOT_COMMANDS = ("prime 0 pilot", "sample 1 pilot 0", "sample 2 pilot 1",
                  "sample 3 pilot 2", "finish 4")
COLLECTION_LOG = re.compile(r"PROF_[^/]+/mindstudio_profiler_log/collection_(?:host|device_[0-9]+)\.log")
_INVENTORY_PROOF_INTERVAL_NS = 1_000_000_000


def remaining(deadline):
    value = deadline - time.monotonic()
    if not math.isfinite(value) or value <= 0:
        raise TimeoutError("original Task timing deadline expired")
    return value


def _collection_budget(config, *, timeout_seconds, deadline_monotonic, budget_binding,
                       budget_reader, started_at, started_monotonic):
    if (type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0):
        raise ValueError("positive finite Task timeout required")
    parent = None
    if budget_binding is not None:
        if budget_reader is None or deadline_monotonic is None:
            raise ValueError("Task budget requires original parent reader and deadline")
        parent = replay_task_budget(budget_reader, budget_binding, expected=config)
        if (deadline_monotonic != parent["deadline_monotonic"]
                or timeout_seconds > parent["budget_seconds"]
                or timeout_seconds < deadline_monotonic - started_monotonic
                or started_monotonic < parent["started_monotonic"]
                or not parent["started_at"] <= started_at < parent["wall_deadline"]):
            raise ValueError("Task collector changed the original parent allowance")
    elif timeout_seconds > 3600:
        raise ValueError("larger Task budget requires the original parent binding")
    if deadline_monotonic is None:
        deadline_monotonic = started_monotonic + timeout_seconds
    if (type(deadline_monotonic) not in (int, float) or not math.isfinite(deadline_monotonic)
            or deadline_monotonic <= started_monotonic
            or parent is None and deadline_monotonic > started_monotonic + 3600):
        raise ValueError("invalid original Task deadline")
    # Parent-to-child handoff/setup consumes the original window too.
    timeout_seconds = min(timeout_seconds, deadline_monotonic - started_monotonic)
    return deadline_monotonic, timeout_seconds, parent


class _InventoryProof:
    """One collection's full-file hashes; every use rechecks path and identity."""
    def __init__(self):
        self.files = {}

    @staticmethod
    def identity(path):
        path = old.canonical_path(path)
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode):
            raise ValueError("inventory dependency must be a regular file")
        return path, (info.st_dev, info.st_ino, info.st_mode, info.st_size,
                      info.st_mtime_ns, info.st_ctime_ns)

    def digest(self, path):
        path, before = self.identity(path)
        previous = self.files.get(path)
        if previous is not None:
            if previous[0] != before:
                raise ValueError("frozen inventory dependency changed")
            if previous[2]:
                return previous[1]
        hash_started_ns = time.monotonic_ns()
        digest = file_hash(path)
        _, after = self.identity(path)
        if before != after:
            raise ValueError("inventory dependency changed during hashing")
        if previous is not None and digest != previous[1]:
            raise ValueError("inventory dependency bytes changed without a new identity")
        # Same-size rewrites can share a filesystem timestamp tick. On the
        # supported Linux overlay/JuiceFS hosts, observe an unchanged identity
        # across one local monotonic second, then require another full matching
        # read before permitting reuse. Never infer age from remote wall time.
        # This is a bounded timestamp safeguard, not an arbitrary-FS guarantee.
        reusable = previous is not None and hash_started_ns - previous[3] >= _INVENTORY_PROOF_INTERVAL_NS
        first_completed_ns = time.monotonic_ns() if previous is None else previous[3]
        self.files[path] = (after, digest, reusable, first_completed_ns)
        return digest

    # source_inventory already has a narrow hash-registration hook. It still
    # walks the complete source roster and rejects links on every boundary.
    register_artifact = digest

    def source(self, root):
        return shared.source_inventory(old.canonical_path(root), store=self)


def profile_dependencies(*, _proof=None):
    """Hash the fixed native-build and CANN export dependencies, never config input."""
    from aprof_runtime.task_window_measurement_admission import PROFILE_DEPENDENCY_PATHS
    proof = _InventoryProof() if _proof is None else _proof
    return {path: proof.digest(path) for path in PROFILE_DEPENDENCY_PATHS}


def export_argv(config, profile_root):
    """The sole registered explicit export command for native Task capture."""
    profile_root = old.canonical_path(profile_root)
    python = old.canonical_path(SUMMARY_PYTHON)
    if Path(sys.executable).resolve(strict=True) != python:
        raise ValueError("summary export Python differs from the active canonical interpreter")
    entry = old.canonical_path(SUMMARY_ENTRY)
    return [str(python), str(entry), "export", "summary", "-dir", str(profile_root), "--format", "csv"]


def config_value(value, *, _proof=None):
    # Keep all legacy source/build/workload/path checks on a scalar view.
    config = old.config_value(case_task_config(value))
    for role in ROLES:
        config["roles"][role]["launches_per_operator"] = deepcopy(value["roles"][role]["launches_per_operator"])
    config["task_profile"]["role_kernel_names"] = deepcopy(value["task_profile"]["role_kernel_names"])
    if Path(sys.executable).resolve(strict=True) != SUMMARY_PYTHON:
        raise ValueError("active Python differs from fixed Task summary export interpreter")
    proof = _InventoryProof() if _proof is None else _proof
    built = proof.source(config["build"]["source_dir"])
    if built.get("op_host/device_task_profile.h") != proof.digest(HEADER_ASSET):
        raise ValueError("native Task binary source lacks the registered profiling header")
    return config


def inventory(config, selected_case=None, *, _proof=None):
    proof = _InventoryProof() if _proof is None else _proof
    files = set(config["build"]["receipt_files"] + [config["build"]["binary"]])
    for case in config["cases"] if selected_case is None else [selected_case]:
        files.update(case["prepared_files"])
        for command in case["verify_commands"].values():
            files.add(str(shared.regular(command[0])))
            for item in command[1:]:
                if "{cycle_dir}" not in item and Path(item).suffix in {".py", ".sh"}:
                    files.add(str(shared.regular(item)))
    files.add(config["task_profile"]["profiler"])
    values = {path: proof.digest(path) for path in sorted(files)}
    values.update(profile_dependencies(_proof=proof))
    return {"files": values,
        "sources": {role: proof.source(config["roles"][role]["source_dir"]) for role in ROLES},
        "build_sources": proof.source(config["build"]["source_dir"]),
        "producer_files": {name: proof.digest(RELEASE / name) for name in PRODUCER_FILES}}


def native_messages(stdout, mode):
    messages = []
    for line in Path(stdout).read_text(encoding="utf-8").splitlines():
        if line.startswith(shared.PREFIX):
            messages.append(_json(line[len(shared.PREFIX):]))
        elif "APROF_SHARED_TIMING" in line:
            raise ValueError("malformed native Task timing stdout")
    if len(messages) != (6 if mode == "pilot" else 20):
        raise ValueError("native Task message count differs")
    return messages


def unchanged_captured_profile(captured, exported, profile, store):
    """Export may append collection logs; every other captured byte stays fixed."""
    for relative, before_ref in captured.items():
        if relative not in exported:
            raise ValueError("export removed a captured profile file")
        if exported[relative] == before_ref:
            continue
        if COLLECTION_LOG.fullmatch(relative) is None:
            raise ValueError("export modified a captured non-log profile file")
        with store.verify_artifact(before_ref).open("rb") as before, (profile / relative).open("rb") as after:
            for chunk in iter(lambda: before.read(1024 * 1024), b""):
                if after.read(len(chunk)) != chunk:
                    raise ValueError("export rewrote original collection log bytes")


def profile_inventory(directory, *, deadline):
    """Read every file completely; preserve ordered results and each scan boundary."""
    directory = old.canonical_path(directory)
    if not directory.is_dir():
        raise ValueError("missing regular Task profile directory")
    paths = old.safe_files(directory)
    if not paths:
        raise ValueError("empty Task profile tree")

    def digest(path):
        remaining(deadline)
        if path.is_symlink() or not path.is_file():
            raise ValueError("Task profile contains a nonregular file")
        return file_hash(path)

    # The context joins every worker before returning or propagating failure.
    with ThreadPoolExecutor(max_workers=4) as executor:
        hashes = list(executor.map(digest, paths))
    old.canonical_path(directory)
    if old.safe_files(directory) != paths:
        raise ValueError("Task profile file roster changed during inventory")
    remaining(deadline)
    return {path.relative_to(directory).as_posix(): value
            for path, value in zip(paths, hashes, strict=True)}


def copy_profile_tree(source, destination, inventory, *, deadline):
    """Complete checks/durability; four threads copy and hash independent files."""
    source, destination = old.canonical_path(source), old.canonical_path(destination)
    partial = destination.with_name(destination.name + ".partial")
    if (destination.exists() or destination.is_symlink() or partial.exists() or partial.is_symlink()
            or source.is_relative_to(destination) or destination.is_relative_to(source)):
        raise ValueError("Task profile destination/partial must be fresh and outside source")
    started = time.time()
    before = profile_inventory(source, deadline=deadline)
    if before != inventory:
        raise ValueError("Task profile changed before persistence")

    def copy_file(src, dst):
        with open(src, "rb") as reader, open(dst, "xb") as writer:
            while data := reader.read(1024 * 1024):
                remaining(deadline)
                writer.write(data)
            writer.flush()
            os.fsync(writer.fileno())
        return dst

    # copytree still owns directory creation/copystat. Every submitted file is
    # finished (or its error propagated) before any hash or directory fsync.
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = []

        def submit_file(src, dst):
            futures.append(executor.submit(copy_file, src, dst))
            return dst

        shutil.copytree(source, partial, symlinks=True, copy_function=submit_file)
        for future in futures:
            future.result()
    persisted = profile_inventory(partial, deadline=deadline)
    after = profile_inventory(source, deadline=deadline)
    if persisted != before or after != before:
        raise ValueError("Task profile source/persisted inventory changed during copy")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Task profile destination appeared during copy")
    for folder, _, _ in os.walk(partial, topdown=False):
        descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        remaining(deadline)
    partial.rename(destination)
    descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    remaining(deadline)
    return {"source_dir": str(source), "destination_dir": str(destination),
            "started_at": started, "finished_at": time.time(), "source_inventory": before,
            "persisted_inventory": persisted, "source_after_inventory": after}


def profile_ref(directory, store, *, deadline, capture=False):
    """Index original local files; snapshot only collection logs export may append."""
    directory = old.canonical_path(directory)
    if not directory.is_dir():
        raise ValueError("missing regular Task profile directory")
    paths = old.safe_files(directory)
    if not paths or any(path.is_symlink() or not path.is_file() for path in paths):
        raise ValueError("Task profile must contain regular non-symlink files")
    values = {}
    for path in paths:
        remaining(deadline)
        name = path.relative_to(directory).as_posix()
        values[name] = (store.snapshot_file(path) if capture and COLLECTION_LOG.fullmatch(name)
                        else store.register_artifact(path))
    if old.safe_files(directory) != paths:
        raise ValueError("Task profile file roster changed during local indexing")
    remaining(deadline)
    return register_json_artifact(store, values), values


def create_profile_storage(scratch, output, store, *, started_at, timeout_seconds,
                           budget_binding=None, started_monotonic=None, deadline_monotonic=None):
    scratch, output = old.canonical_path(scratch), old.canonical_path(output)
    if scratch.is_relative_to(output) or output.is_relative_to(scratch):
        raise ValueError("Task scratch and persistent roots overlap")
    scratch.mkdir(mode=0o700, exist_ok=False)
    if scratch.stat().st_mode & 0o777 != 0o700:
        raise ValueError("Task scratch directory is not private mode 0700")
    mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    if any(old.select_mount(mountinfo, path)["filesystem_type"] not in old.LOCAL_PROFILE_FILESYSTEMS
           for path in (scratch, output)):
        raise ValueError("Task scratch and work roots must use supported local filesystems")
    if output.stat().st_mode & 0o777 != 0o700:
        raise ValueError("Task work directory is not private mode 0700")
    mount_path = output / "profile-mountinfo.txt"
    with mount_path.open("x", encoding="utf-8") as target:
        target.write(mountinfo)
    storage = {"schema_version": 1, "mode": "local_profile_only", "scratch_root": str(scratch),
        "work_root": str(output), "created_at": time.time(), "host": socket.gethostname(),
        "directory_mode": 0o700, "mountinfo_ref": store.register_artifact(mount_path),
        "scratch_mount": old.select_mount(mountinfo, scratch), "persistent_mount": old.select_mount(mountinfo, output),
        "collection_started_at": started_at, "timeout_seconds": timeout_seconds}
    if budget_binding is not None:
        storage.update(budget_binding=deepcopy(budget_binding), collection_started_monotonic=started_monotonic,
                       deadline_monotonic=deadline_monotonic)
    old.save(output / "profile-storage.json", storage)
    return store.register_artifact(output / "profile-storage.json")


def _remove_redundant_output(application, directory, output_hashes, store, *, deadline):
    """Remove only the unindexed third output after both role oracles passed."""
    if application.count("--output") != 1 or any(arg.startswith("--output=") for arg in application):
        return False
    position = application.index("--output") + 1
    registered = getattr(store, "_paths", None)
    if position == len(application) or not isinstance(registered, dict):
        return False
    remaining(deadline)
    try:
        root = old.canonical_path(str(directory))
        path = old.canonical_path(application[position])
        if (not path.is_relative_to(root) or path == root or str(path) in output_hashes
                or path in registered.values() or not stat.S_ISREG(path.lstat().st_mode)):
            return False
        _, before = _InventoryProof.identity(path)
        digest = file_hash(path)
        if digest not in output_hashes.values() or _InventoryProof.identity(path)[1] != before:
            return False
    except (OSError, ValueError):
        return False
    remaining(deadline)
    try:
        path.unlink()
    except OSError:
        return False
    return True


def run_session(config, case, session, snapshot, base_environment, worker, slots, store, deadline,
                *, _inventory_proof=None):
    directory = Path(session["cycle_dir"])
    directory.mkdir()
    mode, repeat = session["mode"], session["repeat"]
    try:
        remaining(deadline)
        session["identity_before"] = inventory(config, case, _proof=_inventory_proof)
        expected = dict(snapshot, files={path: snapshot["files"].get(path)
                                         for path in session["identity_before"]["files"]})
        if session["identity_before"] != expected:
            raise ValueError("frozen source/input/profiler dependency changed before capture")
        if {key: os.environ.get(key) for key in base_environment} != base_environment:
            raise ValueError("base process environment changed before capture")
        outputs = {role: shared.expanded(case["output_files"][role], directory) for role in ROLES}
        paths = [Path(path) for items in outputs.values() for path in items]
        if (len(set(paths)) != len(paths) or any(path.exists() or path.is_symlink()
                or not path.resolve().is_relative_to(directory) for path in paths)):
            raise ValueError("callback outputs must be fresh and isolated")
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        command_path = directory / "commands.txt"
        commands = PILOT_COMMANDS if mode == "pilot" else protocol_commands()
        command_path.write_text("\n".join(commands) + "\n", encoding="utf-8")
        session["commands_ref"] = store.register_artifact(command_path)
        scratch = old.canonical_path(config["task_profile"]["scratch_root"])
        if not scratch.is_dir() or scratch.stat().st_mode & 0o777 != 0o700:
            raise ValueError("Task scratch root changed during collection")
        local = scratch / directory.name
        local.mkdir(mode=0o700, exist_ok=False)
        profile = local / "profile"
        profile.mkdir(mode=0o700, exist_ok=False)
        environment = {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(session["cycle"]),
                       "APROF_SHARED_MODE": mode, "APROF_SHARED_REPEAT": str(repeat),
                       "APROF_SHARED_COMMANDS": str(command_path),
                       "APROF_TASK_PROFILE_DIR": str(profile)}
        application = shared.expanded(case["command"], directory)
        if application[0] != config["build"]["binary"]:
            raise ValueError("native binary differs from registered build")
        old._execution(application, config["build"]["source_dir"], directory / "capture",
                       remaining(deadline), store, environment, session, "capture")
        if file_hash(command_path) != session["commands_ref"]:
            raise ValueError("native command file changed during capture")
        session["capture_files_ref"], captured = profile_ref(profile, store, deadline=deadline, capture=True)
        if any(Path(name).name.startswith("op_summary") and name.endswith(".csv") for name in captured):
            raise ValueError("native Task capture unexpectedly contains an exported Task table")
        messages = native_messages(directory / "capture.stdout.log", mode)
        session["native_messages_ref"] = register_json_artifact(store, messages)
        roots = [path for path in profile.glob("PROF_*") if path.is_dir() and not path.is_symlink()]
        if len(roots) != 1:
            raise ValueError("native Task capture requires exactly one PROF directory")
        old._execution(export_argv(config, roots[0]), config["build"]["source_dir"],
                       directory / "export", remaining(deadline), store, {}, session, "export")
        session["profile_files_ref"], final_files = profile_ref(profile, store, deadline=deadline)
        unchanged_captured_profile(captured, final_files, profile, store)
        tables = [name for name in final_files if Path(name).name.startswith("op_summary") and name.endswith(".csv")]
        if len(tables) != 1:
            raise ValueError("export requires exactly one complete Task CSV")
        session["task_table_ref"] = final_files[tables[0]]
        table = profile / tables[0]
        if table.is_symlink() or not table.is_file() or file_hash(table) != session["task_table_ref"]:
            raise ValueError("local Task CSV differs before parsing")
        selected_config = case_task_config(config, case["case_id"])
        partition = partition_window_tasks(table_path=table, messages=messages, config=selected_config,
            mode=mode, cycle=session["cycle"], repeat=repeat,
            role_kernel_names=selected_config["task_profile"]["role_kernel_names"])
        if file_hash(table) != session["task_table_ref"]:
            raise ValueError("Task CSV changed during parsing")
        session["partition_ref"] = register_json_artifact(store, partition)
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise ValueError("native callback did not export an isolated output")
            session["output_hashes"][str(path)] = store.register_artifact(path)
        for role in ROLES:
            try:
                receipt = worker.verify(slots[role], deadline=deadline)
            except BaseException:
                if worker.last_receipt is not None:
                    session["verifications"][role] = worker.last_receipt
                raise
            session["verifications"][role] = receipt
        if any(file_hash(path) != reference for path, reference in session["output_hashes"].items()):
            raise ValueError("oracle modified a native callback output")
        _remove_redundant_output(application, directory, session["output_hashes"], store, deadline=deadline)
        session["control_summary"] = _phase_controls(partition["values_ns_per_call"]) if mode == "confirmation" else None
        session["identity_after"] = inventory(config, case, _proof=_inventory_proof)
        if session["identity_after"] != expected:
            raise ValueError("frozen source/input/profiler dependency changed during session")
        if (file_hash(command_path) != session["commands_ref"]
                or {key: os.environ.get(key) for key in base_environment} != base_environment):
            raise ValueError("native command file or base environment changed during session")
        remaining(deadline)
        return partition
    finally:
        session["finished_at"] = time.time()


def _session(output, case_id, mode, cycle, repeat):
    directory = shared.session_directory(output, case_id, mode, cycle)
    return {"case_id": case_id, "cycle": cycle, "mode": mode, "repeat": repeat,
            "cycle_dir": str(directory), "started_at": time.time(), "finished_at": None,
            "capture": None, "export": None, "capture_files_ref": None,
            "profile_files_ref": None,
            "verifications": {}, "output_hashes": {}, "control_summary": None}



def _begin_session(output, case_id, mode, cycle, repeat, store, deadline, policy):
    mono, wall = time.monotonic(), time.time()
    unit_deadline = collection_unit_deadline(deadline, policy, "task", now=mono)
    session = _session(output, case_id, mode, cycle, repeat)
    if policy is not None:
        session["started_at"] = wall
        session["collection_unit_ref"] = register_json_artifact(store, {
            "schema_version": 1, "started_at": wall, "started_monotonic": mono,
            "deadline_monotonic": unit_deadline})
    return session, unit_deadline


def _controls(partition, case_id, cycle, same_source):
    quality = _phase_controls(partition["values_ns_per_call"])
    phases = PHASES if same_source else ("aa_before", "aa_after")
    if (any(quality[phase]["role_bias"] > .02 for phase in phases)
            or any(quality[phase][role + "_cv"] > .05 for phase in PHASES for role in ROLES)
            or any(value > .02 for value in quality["drift"].values())):
        raise ValueError(f"case {case_id} cycle {cycle}: Task control failed")


def collect_local(value, output, *, timeout_seconds=3600, deadline_monotonic=None,
                  budget_binding=None, budget_reader=None):
    collection_started_at = time.time()
    started_monotonic = time.monotonic()
    deadline, timeout_seconds, parent = _collection_budget(value, timeout_seconds=timeout_seconds,
        deadline_monotonic=deadline_monotonic, budget_binding=budget_binding, budget_reader=budget_reader,
        started_at=collection_started_at, started_monotonic=started_monotonic)
    stop_policy = parent.get("collection_stop_policy") if parent is not None else None
    proof = _InventoryProof()
    config = config_value(value, _proof=proof)
    output = old.canonical_path(output)
    if any(output.is_relative_to(config["roles"][role]["source_dir"]) for role in ROLES) \
            or output.is_relative_to(config["build"]["source_dir"]):
        raise ValueError("Task evidence directory must be outside frozen sources")
    if old.select_mount(Path("/proc/self/mountinfo").read_text(), output)["filesystem_type"] not in old.LOCAL_PROFILE_FILESYSTEMS:
        raise ValueError("Task work root must use a supported local filesystem")
    output.mkdir(mode=0o700, exist_ok=False)
    store = LocalEvidence(output / "records")
    if parent is not None:
        for reference, path in parent["references"].items():
            if store.register_artifact(path) != reference:
                raise ValueError("original parent budget changed during local indexing")
    old.save(output / "config.json", config)
    storage_ref = create_profile_storage(config["task_profile"]["scratch_root"], output, store,
        started_at=collection_started_at, timeout_seconds=timeout_seconds,
        budget_binding=budget_binding, started_monotonic=started_monotonic, deadline_monotonic=deadline)
    snapshot = inventory(config, _proof=proof)
    identity = shared.bind_identity(config, snapshot, store)
    for name, reference in snapshot["producer_files"].items():
        if store.register_artifact(RELEASE / name) != reference:
            raise ValueError("Task-window producer changed during registration")
    config_ref = store.register_artifact(output / "config.json")
    plan = validate_plan(shared.oracle_plan(config, output, identity))
    old.save(output / "verifier-request-plan.json", plan)
    plan_ref = store.register_artifact(output / "verifier-request-plan.json")
    slots = {(item["stage"], item["case_id"], item["cycle"], item["role"]): item["request_index"]
             for item in plan["requests"]}
    smi = old.regular(shutil.which("npu-smi") or "/usr/local/sbin/npu-smi")
    probe = old.run_process([str(smi), "info", "-t", "board", "-i", str(config["physical_device"]), "-c", "0"],
                            output, output / "hardware-probe", min(60, remaining(deadline)), store)
    cann_home = Path(os.environ.get("ASCEND_HOME_PATH", "/usr/local/Ascend/ascend-toolkit/latest")).resolve()
    install_info = old.regular(cann_home / (platform.machine() + "-linux/ascend_toolkit_install.info"))
    hardware = {"host": socket.gethostname(), "physical_device": config["physical_device"],
                "probe": {key: item for key, item in probe.items() if key != "text"},
                "npu_smi_ref": store.register_artifact(smi), "cann_home": str(cann_home),
                "cann_install_info_ref": store.register_artifact(install_info)}
    hardware_ref = register_json_artifact(store, hardware)
    calibration = {"schema_version": 1, "protocol": PROTOCOL, "config_ref": config_ref,
                   "started_at": None, "finished_at": None, "host": socket.gethostname(), "cases": []}
    raw = {"protocol": PROTOCOL, "registration_ref": None, "calibration_ref": None,
           "repeat_by_case": {}, "verifier_worker_ref": None, "started_at": None,
           "finished_at": None, "complete": False, "sessions": [], "host": socket.gethostname()}
    environment = {key: value for key, value in os.environ.items() if not key.startswith("APROF_")}
    raw["environment"] = {key: environment.get(key) for key in (
        "ASCEND_HOME_PATH", "ASCEND_OPP_PATH", "LD_LIBRARY_PATH", "ASCEND_RT_VISIBLE_DEVICES",
        "ASCEND_VISIBLE_DEVICES", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
    same_source = identity["source_hashes"]["baseline"] == identity["source_hashes"]["candidate"]
    worker = None
    next_unit, pending_pilot = None, None
    try:
        with old.device_lock(config["physical_device"], remaining(deadline)):
            calibration["started_at"] = time.time()
            worker = PersistentOracle(plan, directory=output / "oracle-worker", store=store, deadline=deadline)
            worker.start()
            if worker.report["request_plan_ref"] != plan_ref:
                raise ValueError("oracle worker changed the frozen Task request roster")
            for case in config["cases"]:
                cid = case["case_id"]
                next_unit = {"mode": "pilot", "case_id": cid, "cycle": 0}
                pilot, unit_deadline = _begin_session(output, cid, "pilot", 0, 100, store, deadline, stop_policy)
                pending_pilot = pilot
                partition = run_session(config, case, pilot, snapshot, raw["environment"], worker,
                    {role: slots[("calibration", cid, None, role)] for role in ROLES}, store, unit_deadline,
                    _inventory_proof=proof)
                chosen = choose_task_repeat(partition)
                frozen_case = {"case_id": cid, "repeat": chosen["repeat"],
                    "median_100_calls_ns_decimal": chosen["median_100_calls_ns_decimal"], "pilot": pilot}
                path = output / f"calibration-case-{cid:02d}.json"
                old.save(path, frozen_case)
                calibration["cases"].append(dict(frozen_case, case_ref=store.register_artifact(path)))
                pending_pilot = None
            calibration["finished_at"] = time.time()
            old.save(output / "calibration.json", calibration)
            calibration_ref = store.register_artifact(output / "calibration.json")
            repeat_by_case = {str(item["case_id"]): item["repeat"] for item in calibration["cases"]}
            dependencies = profile_dependencies(_proof=proof)
            if any(snapshot["files"].get(path) != reference for path, reference in dependencies.items()):
                raise ValueError("fixed Task profile dependency changed before registration")
            registration = {"protocol": PROTOCOL, "created_at": time.time(), "config_ref": config_ref,
                "identity": identity, "inventory": snapshot, "producer_files": snapshot["producer_files"],
                "attempt_policy": "exactly_once_no_resume_no_resampling", "cycles": 6, "pairs_per_phase": 5,
                "warmup": 10, "prime_repeat": 100, "calibration_ref": calibration_ref,
                "repeat_by_case": repeat_by_case, "cpu_affinity": sorted(os.sched_getaffinity(0)),
                "hardware_ref": hardware_ref, "verifier_request_plan_ref": plan_ref,
                "profiler_ref": store.register_artifact(config["task_profile"]["profiler"]),
                "task_profile": deepcopy(config["task_profile"]), "profile_storage_ref": storage_ref,
                "profile_dependency_refs": {path: store.register_artifact(path) for path in dependencies}}
            old.save(output / "registration.json", registration)
            registration_ref = store.register_artifact(output / "registration.json")
            raw.update(registration_ref=registration_ref, calibration_ref=calibration_ref,
                       repeat_by_case=repeat_by_case, started_at=time.time())
            for case in config["cases"]:
                cid, case_values = case["case_id"], []
                repeat = repeat_by_case[str(cid)]
                for cycle in range(6):
                    next_unit = {"mode": "confirmation", "case_id": cid, "cycle": cycle}
                    session, unit_deadline = _begin_session(output, cid, "confirmation", cycle, repeat,
                        store, deadline, stop_policy)
                    raw["sessions"].append(session)
                    partition = run_session(config, case, session, snapshot, raw["environment"], worker,
                        {role: slots[("confirmation", cid, cycle, role)] for role in ROLES}, store, unit_deadline,
                        _inventory_proof=proof)
                    case_values.append(partition["values_ns_per_call"])
                    _controls(partition, cid, cycle, same_source)
                    old.save(output / "raw_measurements.json", raw)
                case_report = _summarize_values({cid: case_values},
                    {**config, "expected_case_ids": [cid]}, protocol=PROTOCOL)
                if not case_report["stable"]:
                    raise ValueError(f"case {cid}: Task controls failed: " + "; ".join(case_report["reasons"]))
                if same_source and case_report["controls"][0]["overall"]["formal"]["role_bias"] > .02:
                    raise ValueError(f"case {cid}: same-source formal A/A role bias exceeds 2%")
            raw["complete"] = True
            next_unit = None
            from aprof_runtime.task_window_measurement_admission import summarize_task_window_raw
            report = summarize_task_window_raw(raw, config, store)
            if not report["stable"]:
                raw["complete"] = False
                raise ValueError("Task-window controls failed: " + "; ".join(report["reasons"]))
            if same_source and any(item["overall"]["formal"]["role_bias"] > .02 for item in report["controls"]):
                raw["complete"] = False
                raise ValueError("same-source formal A/A role bias exceeds 2%")
    except BaseException as error:
        raw["complete"] = False
        raw["error"] = {"type": type(error).__name__, "message": str(error)}
        # Separate diagnostic record: failed/partial evidence never expands the
        # strict successful raw schema or claims an unrun unit was completed.
        old.save(output / "collection-partial.json", {"error": raw["error"], "next_or_active_unit": next_unit,
            "active_pilot": pending_pilot, "completed_pilots": calibration["cases"],
            "completed_confirmation_count": sum(s.get("control_summary") is not None for s in raw["sessions"]),
            "budget_binding": budget_binding, "admission_authority": False})
        store.register_artifact(output / "collection-partial.json")
    finally:
        if worker is not None and worker.directory.is_dir():
            close_budget = ({"deadline": min(deadline, time.monotonic() + stop_policy["terminal_seconds"])}
                            if stop_policy is not None else {})
            raw["verifier_worker_ref"] = worker.finish(abort=not raw["complete"], **close_budget)
            if raw["complete"] and worker.report["status"] != "complete":
                raw["complete"] = False
                raw["error"] = {"type": "RuntimeError", "message": "persistent oracle did not complete"}
        raw["finished_at"] = time.time()
        if raw["complete"] and time.monotonic() > deadline:
            raw["complete"] = False
            raw["error"] = {"type": "TimeoutError", "message": "Task collection exceeded its deadline"}
        old.save(output / "raw_measurements.json", raw)
        raw_ref = store.register_artifact(output / "raw_measurements.json")
        from aprof_runtime.task_window_measurement_admission import summarize_task_window_raw
        report = summarize_task_window_raw(raw, config, store)
        old.save(output / "measurement_report.json", report)
        report_ref = store.register_artifact(output / "measurement_report.json")
        receipt = {"schema_version": "1.0.0", "protocol": PROTOCOL,
                   **{key: config[key] for key in ("operator", "run_id", "session_id", "candidate_id")},
                   "source_hashes": identity["source_hashes"], "registration_ref": raw["registration_ref"],
                   "config_ref": config_ref, "raw_ref": raw_ref, "measurement_report_ref": report_ref}
        old.save(output / "measurement-proof.json", receipt)
        proof_ref = store.register_artifact(output / "measurement-proof.json")
    terminal = {"schema_version": "1.0.0", "kind": "local_measurement_completion", "protocol": PROTOCOL,
                **{key: config[key] for key in ("operator", "run_id", "session_id", "candidate_id")},
                "source_hashes": identity["source_hashes"], "proof_ref": proof_ref,
                "measurement_report_ref": report_ref, "started_at": collection_started_at,
                "finished_at": None, "elapsed_seconds": None, "timeout_seconds": timeout_seconds,
                "status": "failed", "error": raw.get("error")}
    try:
        remaining(deadline)
        if not raw["complete"]:
            raise ValueError("local Task collection did not complete")
        from aprof_runtime.task_window_measurement_admission import replay_task_window_measurement_admission
        replay = replay_task_window_measurement_admission(store, proof_ref, expected={
            **{key: config[key] for key in ("operator", "run_id", "session_id", "candidate_id")},
            "source_hashes": identity["source_hashes"]})
        if replay["valid"] is not True:
            raise ValueError("local Task full replay failed")
        remaining(deadline)
        terminal["status"] = "passed"
    except BaseException as error:
        terminal["error"] = terminal["error"] or {"type": type(error).__name__, "message": str(error)}
    terminal.update(finished_at=time.time(), elapsed_seconds=time.monotonic() - started_monotonic)
    if terminal["elapsed_seconds"] >= timeout_seconds:
        terminal.update(status="failed", error={"type": "TimeoutError", "message": "local Task measurement and replay exceeded deadline"})
    if terminal["status"] != "passed":
        report = dict(report, stable=False, speedup=None, speedup_lcb_95=None,
                      gate_projection={"baseline_samples_ns": [], "candidate_samples_ns": [], "heldout_regressions": []},
                      reasons=[*report["reasons"], terminal["error"]["message"]])
    old.save(output / "local-result.json", terminal)
    completion_ref = store.register_artifact(output / "local-result.json")
    old.save(output / "artifacts.json", {"measurement_report": report_ref,
                                        "measurement_admission": completion_ref})
    store.write_index(output / "local-evidence-index.json")
    if terminal["status"] == "passed":
        try:
            remaining(deadline)
        except TimeoutError:
            # Invalidate the provisional completion hash; raw observations remain intact.
            terminal.update(status="failed", finished_at=time.time(),
                elapsed_seconds=time.monotonic() - started_monotonic,
                error={"type": "TimeoutError", "message": "local handoff exceeded deadline"})
            old.save(output / "local-result.json", terminal)
            raise
    return {"status": terminal["status"], "report": report, "measurement_admission_ref": completion_ref,
            "local_index": str(output / "local-evidence-index.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="fresh local work directory; defaults to a private temporary directory")
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    args = parser.parse_args()
    if args.output is None:
        args.output = Path(tempfile.mkdtemp(prefix="aprof-task-window-")) / "work"
    existed = args.output.exists()
    try:
        result = collect_local(_json(args.config.read_text()), args.output,
                               timeout_seconds=args.timeout_seconds)
    except Exception as error:
        # A failed process cannot be admitted from an earlier measurement summary.
        if not existed and args.output.is_dir():
            old.save(args.output / "local-failure.json", {
                "kind": "local_measurement_failure", "status": "failed", "finished_at": time.time(),
                "error": {"type": type(error).__name__, "message": str(error)}})
        print(json.dumps({"measurement_stable": False, "error": str(error)}))
        return 2
    print(json.dumps({"measurement_stable": result["status"] == "passed",
                      "authority": "local_online_measurement", "result": str(args.output / "local-result.json")}))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
