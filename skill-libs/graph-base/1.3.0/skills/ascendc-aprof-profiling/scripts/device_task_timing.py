#!/usr/bin/env python3
"""Collect fixed-repeat msprof Task Duration on the existing shared native wire.

This is a measurement draft.  Runtime replay, correctness, and the candidate
gate decide admission; the v2 ACL Event collector remains historical evidence.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import platform
import shlex
import shutil
import socket
import sys
import time

SCRIPTS = Path(__file__).resolve().parent
RELEASE = SCRIPTS.parents[2]
sys.path.insert(0, str(RELEASE / "runtime/src"))
sys.path.insert(0, str(SCRIPTS))

import device_shared_timing as shared
from device_paired_timing import device_lock, regular, save
from persistent_oracle import PersistentOracle, validate_plan
from profile_capture import run as run_process, safe_files
from aprof_runtime.jsonio import file_hash
from aprof_runtime.measurement_admission import PRODUCER_FILES as SHARED_PRODUCERS, _phase_controls, _summarize_values
from aprof_runtime.profile_evidence import _json
from aprof_runtime.store import EpisodeStore
from aprof_runtime.task_timing import partition_task_samples, protocol_commands
from aprof_runtime.traces import register_json_artifact
from aprof_runtime.task_measurement_admission import LOCAL_PROFILE_FILESYSTEMS, select_mount


PROTOCOL = "shared_buffer_msprof_task_v2"
METRIC = "msprof.op_summary.Task_Duration"
PROFILE_FLAGS = ("--task-time=l1", "--ai-core=off", "--ascendcl=off", "--runtime-api=off",
                 "--ge-api=off", "--aicpu=off", "--type=text")
PRODUCER_FILES = (*SHARED_PRODUCERS,
    "skills/ascendc-aprof-profiling/scripts/device_task_timing.py",
    "runtime/src/aprof_runtime/task_timing.py",
    "runtime/src/aprof_runtime/task_measurement_admission.py",
    "runtime/src/aprof_runtime/store.py")
ROLES, PHASES = shared.ROLES, shared.PHASES
PREFIX = shared.PREFIX


def config_value(value):
    if not isinstance(value, dict) or set(value) != {
            "schema_version", "operator", "run_id", "session_id", "candidate_id",
            "device", "physical_device", "expected_case_ids", "roles", "build", "cases", "task_profile"}:
        raise ValueError("Task timing config fields differ")
    profile = deepcopy(value["task_profile"])
    config = shared.config_value({key: item for key, item in value.items() if key != "task_profile"})
    if not isinstance(profile, dict) or set(profile) != {"profiler", "role_kernel_names", "scratch_root"}:
        raise ValueError("Task timing profiler and kernel sequences required")
    scratch = canonical_path(profile["scratch_root"])
    if scratch.exists() or scratch.is_symlink() or not scratch.parent.is_dir():
        raise ValueError("Task scratch root must not exist and its parent must be a real directory")
    if select_mount(Path("/proc/self/mountinfo").read_text(), scratch)["filesystem_type"] not in LOCAL_PROFILE_FILESYSTEMS:
        raise ValueError("Task scratch filesystem is not a supported local filesystem")
    for source in [config["build"]["source_dir"], *(config["roles"][role]["source_dir"] for role in ROLES)]:
        if scratch.is_relative_to(source) or Path(source).is_relative_to(scratch):
            raise ValueError("Task scratch root overlaps frozen sources")
    profiler = Path(profile["profiler"])
    if not profiler.is_absolute():
        raise ValueError("profiler must be an absolute file")
    profile["profiler"] = str(regular(profiler))
    names = profile["role_kernel_names"]
    if not isinstance(names, dict) or set(names) != set(ROLES):
        raise ValueError("Task kernel roles differ")
    for role in ROLES:
        sequence = names[role]
        if (not isinstance(sequence, list) or not sequence
                or any(not isinstance(name, str) or not name or name.strip() != name for name in sequence)
                or len(sequence) != config["roles"][role]["launches_per_operator"]):
            raise ValueError("registered serial Task kernel sequence differs from callback launches")
    config["task_profile"] = profile
    return config


def canonical_path(value):
    path = Path(value)
    if (not path.is_absolute() or str(path) != str(value) or ".." in path.parts
            or path.resolve() != path or path.is_symlink()):
        raise ValueError("Task profile path must be canonical absolute without symlinks")
    return path


def profile_inventory(directory, *, deadline):
    """Hash every regular file, including files not used by the Task parser."""
    directory = canonical_path(directory)
    if not directory.is_dir():
        raise ValueError("missing regular Task profile directory")
    files = {}
    for path in safe_files(directory):
        remaining(deadline)
        if not path.is_file() or path.is_symlink():
            raise ValueError("Task profile contains a nonregular file")
        files[path.relative_to(directory).as_posix()] = file_hash(path)
    remaining(deadline)
    if not files:
        raise ValueError("empty Task profile tree")
    return files


def copy_profile_tree(source, destination, inventory, *, deadline):
    """Persist a complete profile atomically; keep partial output on any failure."""
    source, destination = canonical_path(source), canonical_path(destination)
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

    shutil.copytree(source, partial, symlinks=True, copy_function=copy_file)
    persisted = profile_inventory(partial, deadline=deadline)
    after = profile_inventory(source, deadline=deadline)
    if persisted != before or after != before:
        raise ValueError("Task profile source/persisted inventory changed during copy")
    if destination.exists() or destination.is_symlink():
        raise ValueError("Task profile destination appeared during copy")
    # Flush directory entries before publishing the complete tree.
    for folder, _, _ in os.walk(partial, topdown=False):
        descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
        remaining(deadline)
    partial.rename(destination)
    descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
    remaining(deadline)
    return {"source_dir": str(source), "destination_dir": str(destination),
            "started_at": started, "finished_at": time.time(), "source_inventory": before,
            "persisted_inventory": persisted, "source_after_inventory": after}


def create_profile_storage(scratch, output, store, *, started_at, timeout_seconds):
    scratch, output = canonical_path(scratch), canonical_path(output)
    if scratch.is_relative_to(output) or output.is_relative_to(scratch):
        raise ValueError("Task scratch and persistent roots overlap")
    scratch.mkdir(mode=0o700, exist_ok=False)
    if scratch.stat().st_mode & 0o777 != 0o700:
        raise ValueError("Task scratch directory is not private mode 0700")
    mountinfo = Path("/proc/self/mountinfo").read_text(encoding="utf-8")
    if select_mount(mountinfo, scratch)["filesystem_type"] not in LOCAL_PROFILE_FILESYSTEMS:
        raise ValueError("Task scratch filesystem is not a supported local filesystem")
    mount_path = output / "profile-mountinfo.txt"
    with mount_path.open("x", encoding="utf-8") as target:
        target.write(mountinfo)
    storage = {"schema_version": 1, "mode": "local_profile_then_copy", "scratch_root": str(scratch),
        "persistent_root": str(output), "created_at": time.time(), "host": socket.gethostname(),
        "directory_mode": 0o700, "mountinfo_ref": store.register_artifact(mount_path),
        "scratch_mount": select_mount(mountinfo, scratch), "persistent_mount": select_mount(mountinfo, output),
        "collection_started_at": started_at, "timeout_seconds": timeout_seconds}
    save(output / "profile-storage.json", storage)
    return store.register_artifact(output / "profile-storage.json")


def inventory(config, selected_case=None):
    snapshot = shared.inventory(config, selected_case)
    profiler = config["task_profile"]["profiler"]
    snapshot["files"][profiler] = file_hash(profiler)
    snapshot["producer_files"] = {name: file_hash(RELEASE / name) for name in PRODUCER_FILES}
    return snapshot


def oracle_plan(config, output, identity):
    """Use the original oracle slots with only the fixed confirmation roster."""
    plan = shared.oracle_plan(config, output, identity)
    plan["requests"] = [item for item in plan["requests"] if item["stage"] == "confirmation"]
    for index, item in enumerate(plan["requests"]):
        item["request_index"] = index
    return validate_plan(plan)


def profile_files(directory, store):
    """Freeze every exported file and reject links anywhere under profile."""
    directory = Path(directory)
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("missing regular profile directory")
    paths = safe_files(directory)
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ValueError("profile contains a nonregular file")
    if not paths:
        raise ValueError("empty profile output")
    return {path.relative_to(directory).as_posix(): digest
            for path, digest in zip(paths, store.register_artifacts(paths), strict=True)}


def native_messages(stdout):
    rows = []
    for line in Path(stdout).read_text(encoding="utf-8").splitlines():
        if line.startswith(PREFIX):
            rows.append(_json(line[len(PREFIX):]))
        elif "APROF_SHARED_TIMING" in line:
            raise ValueError("malformed Task native stdout protocol")
    if len(rows) != 20:
        raise ValueError("Task capture requires READY and exactly 19 native messages")
    return rows


def remaining(deadline):
    amount = deadline - time.monotonic()
    if amount <= 0:
        raise TimeoutError("Task timing trial deadline exceeded")
    return min(3600, amount)


def _execution(argv, cwd, prefix, budget, store, environment, session, key):
    """Keep the process receipt even when the tool exits unsuccessfully."""
    receipt = Path(str(prefix) + ".execution.json")
    try:
        result = run_process(argv, cwd, prefix, budget, store, environment=environment)
        session[key] = {name: value for name, value in result.items() if name != "text"}
    except BaseException:
        if receipt.is_file():
            session[key] = _json(receipt.read_text(encoding="utf-8"))
            session[key]["log_hash"] = store.register_artifact(receipt)
        raise


def _profile_ref(directory, store):
    values = profile_files(directory, store)
    return register_json_artifact(store, values), values


def run_session(config, case, session, snapshot, base_environment, worker, slots, store, deadline):
    directory = Path(session["cycle_dir"])
    directory.mkdir()
    try:
        remaining(deadline)
        session["identity_before"] = inventory(config, case)
        expected = dict(snapshot, files={path: snapshot["files"].get(path)
                                         for path in session["identity_before"]["files"]})
        if session["identity_before"] != expected:
            raise ValueError("frozen source/input/profiler identity changed before capture")
        if {key: os.environ.get(key) for key in base_environment} != base_environment:
            raise ValueError("Task base process environment changed before capture")
        outputs = {role: shared.expanded(case["output_files"][role], directory) for role in ROLES}
        paths = [Path(path) for items in outputs.values() for path in items]
        if (len(set(paths)) != len(paths) or any(path.exists() or path.is_symlink()
                or not path.resolve().is_relative_to(directory) for path in paths)):
            raise ValueError("Task callback outputs must be fresh and isolated")
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        command_path = directory / "commands.txt"
        command_path.write_text("\n".join(protocol_commands()) + "\n", encoding="utf-8")
        session["commands_ref"] = store.register_artifact(command_path)
        environment = {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(session["cycle"]),
                       "APROF_SHARED_MODE": "confirmation", "APROF_SHARED_REPEAT": "100",
                       "APROF_SHARED_COMMANDS": str(command_path)}
        application = shared.expanded(case["command"], directory)
        profiler = config["task_profile"]["profiler"]
        scratch = canonical_path(config["task_profile"]["scratch_root"])
        if not scratch.is_dir() or scratch.stat().st_mode & 0o777 != 0o700:
            raise ValueError("Task scratch root changed during collection")
        scratch_cycle = scratch / f"case-{case['case_id']:02d}-cycle-{session['cycle']}"
        scratch_cycle.mkdir(mode=0o700, exist_ok=False)
        profile_dir = scratch_cycle / "profile"
        capture_argv = [profiler, "--output=" + str(profile_dir), *PROFILE_FLAGS,
                        "--application=" + shlex.join(application)]
        _execution(capture_argv, config["build"]["source_dir"], directory / "capture",
                   remaining(deadline), store, environment, session, "capture")
        if file_hash(command_path) != session["commands_ref"]:
            raise ValueError("frozen Task command file changed during capture")
        session["capture_files_ref"], captured = _profile_ref(profile_dir, store)
        messages = native_messages(directory / "capture.stdout.log")
        session["native_messages_ref"] = register_json_artifact(store, messages)
        tables = [name for name in captured if Path(name).name.startswith("op_summary") and name.endswith(".csv")]
        session["export"] = None
        if not tables:
            roots = [path for path in profile_dir.glob("PROF_*") if path.is_dir() and not path.is_symlink()]
            if len(roots) != 1:
                raise ValueError("Task capture has no table and not exactly one PROF directory")
            export_argv = [profiler, "--export=on", "--type=text", "--output=" + str(roots[0])]
            _execution(export_argv, config["build"]["source_dir"], directory / "export",
                       remaining(deadline), store, environment, session, "export")
            session["profile_files_ref"], final_files = _profile_ref(profile_dir, store)
        else:
            session["profile_files_ref"], final_files = session["capture_files_ref"], captured
        transfer = copy_profile_tree(profile_dir, directory / "profile", final_files, deadline=deadline)
        for key in ("source_inventory", "persisted_inventory", "source_after_inventory"):
            transfer[key + "_ref"] = register_json_artifact(store, transfer.pop(key))
        session["profile_transfer_ref"] = register_json_artifact(store, transfer)
        save(directory / "profile-transfer.json", transfer)
        profile_dir = directory / "profile"
        tables = [name for name in final_files if Path(name).name.startswith("op_summary") and name.endswith(".csv")]
        if len(tables) != 1:
            raise ValueError("Task profile requires exactly one complete op_summary CSV")
        table_path = profile_dir / tables[0]
        session["task_table_ref"] = final_files[tables[0]]
        if table_path.is_symlink() or not table_path.is_file() or file_hash(table_path) != session["task_table_ref"]:
            raise ValueError("Task table changed after profile snapshot")
        partition = partition_task_samples(table_path, messages, operator=config["operator"],
            cycle=session["cycle"], repeat=100,
            role_kernel_names=config["task_profile"]["role_kernel_names"])
        if table_path.is_symlink() or not table_path.is_file() or file_hash(table_path) != session["task_table_ref"]:
            raise ValueError("Task table changed during parsing")
        session["partition_ref"] = register_json_artifact(store, partition)
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise ValueError("Task callback did not export an isolated output")
            session["output_hashes"][str(path)] = store.register_artifact(path)
        for role in ROLES:
            try:
                receipt = worker.verify(slots[role])
            except BaseException:
                if worker.last_receipt is not None:
                    session["verifications"][role] = worker.last_receipt
                raise
            session["verifications"][role] = receipt
        if any(file_hash(path) != digest for path, digest in session["output_hashes"].items()):
            raise ValueError("Task oracle modified a callback output")
        session["control_summary"] = _phase_controls(partition["values_ns_per_call"])
        session["identity_after"] = inventory(config, case)
        if session["identity_after"] != expected:
            raise ValueError("frozen source/input/profiler identity changed during capture")
        if (file_hash(command_path) != session["commands_ref"]
                or {key: os.environ.get(key) for key in base_environment} != base_environment):
            raise ValueError("Task command file or base environment changed during session")
        remaining(deadline)
        return partition["values_ns_per_call"]
    finally:
        session["finished_at"] = time.time()


def collect(value, output, store, *, timeout_seconds=3600):
    if (isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (float, int))
            or not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 3600):
        raise ValueError("positive finite Task trial timeout up to 3600 seconds required")
    collection_started_at = time.time()
    deadline = time.monotonic() + timeout_seconds
    config = config_value(value)
    output = Path(output).resolve()
    if any(output.is_relative_to(config["roles"][role]["source_dir"]) for role in ROLES) \
            or output.is_relative_to(config["build"]["source_dir"]):
        raise ValueError("Task evidence directory must be outside source trees")
    output.mkdir(parents=True, exist_ok=False)
    save(output / "config.json", config)
    storage_ref = create_profile_storage(config["task_profile"]["scratch_root"], output, store,
        started_at=collection_started_at, timeout_seconds=timeout_seconds)
    snapshot = inventory(config)
    identity = shared.bind_identity(config, snapshot, store)
    for name, digest in snapshot["producer_files"].items():
        if store.register_artifact(RELEASE / name) != digest:
            raise ValueError("Task producer changed during registration")
    config_ref = store.register_artifact(output / "config.json")
    plan = oracle_plan(config, output, identity)
    save(output / "verifier-request-plan.json", plan)
    plan_ref = store.register_artifact(output / "verifier-request-plan.json")
    slots = {(item["case_id"], item["cycle"], item["role"]): item["request_index"]
             for item in plan["requests"]}
    smi = regular(shutil.which("npu-smi") or "/usr/local/sbin/npu-smi")
    probe = run_process([str(smi), "info", "-t", "board", "-i", str(config["physical_device"]), "-c", "0"],
                        output, output / "hardware-probe", min(60, remaining(deadline)), store)
    cann_home = Path(os.environ.get("ASCEND_HOME_PATH", "/usr/local/Ascend/ascend-toolkit/latest")).resolve()
    install_info = regular(cann_home / (platform.machine() + "-linux/ascend_toolkit_install.info"))
    hardware = {"host": socket.gethostname(), "physical_device": config["physical_device"],
                "probe": {key: item for key, item in probe.items() if key != "text"},
                "npu_smi_ref": store.register_artifact(smi), "cann_home": str(cann_home),
                "cann_install_info_ref": store.register_artifact(install_info)}
    hardware_ref = register_json_artifact(store, hardware)
    registration = {"protocol": PROTOCOL, "created_at": time.time(), "config_ref": config_ref,
        "identity": identity, "inventory": snapshot, "producer_files": snapshot["producer_files"],
        "attempt_policy": "exactly_once_no_resume_no_resampling", "cycles": 6, "pairs_per_phase": 5,
        "warmup": 10, "prime_repeat": 100, "repeat": 100,
        "cpu_affinity": sorted(os.sched_getaffinity(0)), "hardware_ref": hardware_ref,
        "verifier_request_plan_ref": plan_ref, "profiler_ref": store.register_artifact(config["task_profile"]["profiler"]),
        "task_profile": deepcopy(config["task_profile"]), "profile_storage_ref": storage_ref}
    save(output / "registration.json", registration)
    registration_ref = store.register_artifact(output / "registration.json")
    raw = {"protocol": PROTOCOL, "registration_ref": registration_ref, "verifier_worker_ref": None,
           "started_at": time.time(), "finished_at": None, "complete": False,
           "sessions": [], "host": socket.gethostname()}
    environment = {key: value for key, value in os.environ.items() if not key.startswith("APROF_")}
    raw["environment"] = {key: environment.get(key) for key in (
        "ASCEND_HOME_PATH", "ASCEND_OPP_PATH", "LD_LIBRARY_PATH", "ASCEND_RT_VISIBLE_DEVICES",
        "ASCEND_VISIBLE_DEVICES", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
    worker = None
    try:
        worker = PersistentOracle(plan, directory=output / "oracle-worker", store=store, deadline=deadline)
        worker.start()
        if worker.report["request_plan_ref"] != plan_ref:
            raise ValueError("oracle worker changed the frozen Task request roster")
        with device_lock(config["physical_device"], remaining(deadline)):
            for case in config["cases"]:
                case_values = []
                for cycle in range(6):
                    directory = shared.session_directory(output, case["case_id"], "confirmation", cycle)
                    session = {"case_id": case["case_id"], "cycle": cycle, "mode": "confirmation",
                               "cycle_dir": str(directory), "started_at": time.time(), "finished_at": None,
                               "capture": None, "export": None, "capture_files_ref": None,
                               "profile_files_ref": None, "profile_transfer_ref": None,
                               "verifications": {}, "output_hashes": {}}
                    raw["sessions"].append(session)
                    case_values.append(run_session(config, case, session, snapshot, raw["environment"], worker,
                        {role: slots[(case["case_id"], cycle, role)] for role in ROLES}, store, deadline))
                    quality = session["control_summary"]
                    same_source = identity["source_hashes"]["baseline"] == identity["source_hashes"]["candidate"]
                    controls = PHASES if same_source else ("aa_before", "aa_after")
                    if (any(quality[phase]["role_bias"] > 0.02 for phase in controls)
                            or any(quality[phase][role + "_cv"] > 0.05 for phase in PHASES for role in ROLES)
                            or any(value > 0.02 for value in quality["drift"].values())):
                        raise ValueError(f"case {case['case_id']} cycle {cycle}: Task control failed")
                    save(output / "raw_measurements.json", raw)
                case_report = _summarize_values({case["case_id"]: case_values},
                    {**config, "expected_case_ids": [case["case_id"]]}, protocol=PROTOCOL)
                if not case_report["stable"]:
                    raise ValueError(f"case {case['case_id']}: Task measurement controls failed: "
                                     + "; ".join(case_report["reasons"]))
                if same_source and case_report["controls"][0]["overall"]["formal"]["role_bias"] > 0.02:
                    raise ValueError(f"case {case['case_id']}: same-source Task formal A/A role bias exceeds 2%")
            raw["complete"] = True
            from aprof_runtime.task_measurement_admission import summarize_task_raw
            report = summarize_task_raw(raw, config, store)
            if not report["stable"]:
                raw["complete"] = False
                raise ValueError("Task measurement controls failed: " + "; ".join(report["reasons"]))
            if identity["source_hashes"]["baseline"] == identity["source_hashes"]["candidate"]:
                if any(item["overall"]["formal"]["role_bias"] > 0.02 for item in report["controls"]):
                    raw["complete"] = False
                    raise ValueError("same-source Task formal A/A role bias exceeds 2%")
    except BaseException as error:
        raw["complete"] = False
        raw["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        if worker is not None and worker.directory.is_dir():
            raw["verifier_worker_ref"] = worker.finish(abort=not raw["complete"])
            if raw["complete"] and worker.report["status"] != "complete":
                raw["complete"] = False
                raw["error"] = {"type": "RuntimeError", "message": "persistent oracle did not complete"}
        raw["finished_at"] = time.time()
        if raw["complete"] and time.monotonic() > deadline:
            raw["complete"] = False
            raw["error"] = {"type": "TimeoutError", "message": "Task collection exceeded its total deadline"}
        save(output / "raw_measurements.json", raw)
        raw_ref = store.register_artifact(output / "raw_measurements.json")
        from aprof_runtime.task_measurement_admission import summarize_task_raw
        report = summarize_task_raw(raw, config, store)
        save(output / "measurement_report.json", report)
        report_ref = store.register_artifact(output / "measurement_report.json")
        receipt = {"schema_version": "1.0.0", "protocol": PROTOCOL,
                   **{key: config[key] for key in ("operator", "run_id", "session_id", "candidate_id")},
                   "source_hashes": identity["source_hashes"], "registration_ref": registration_ref,
                   "config_ref": config_ref, "raw_ref": raw_ref, "measurement_report_ref": report_ref}
        save(output / "measurement_admission.json", receipt)
        receipt_ref = store.register_artifact(output / "measurement_admission.json")
        save(output / "artifacts.json", {"measurement_report": report_ref,
                                         "measurement_admission": receipt_ref})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    args = parser.parse_args()
    with EpisodeStore(args.store) as store:
        report = collect(_json(args.config.read_text()), args.output, store,
                         timeout_seconds=args.timeout_seconds)
    print(json.dumps({"measurement_stable": report["stable"],
                      "authority": "measurement_only_no_performance_verdict"}))
    return 0 if report["stable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
