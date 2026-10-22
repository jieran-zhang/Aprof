#!/usr/bin/env python3
"""Collect a predeclared same-buffer, two-callback timing session.

The host must integrate device_shared_timing.h. This collector does not rewrite
operator sources, build candidates, or accept a performance improvement.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
import statistics
import os
from pathlib import Path
import platform
import shutil
import socket
import sys
import time

SCRIPTS = Path(__file__).resolve().parent
RELEASE = SCRIPTS.parents[2]
sys.path.insert(0, str(RELEASE / "runtime/src"))
sys.path.insert(0, str(SCRIPTS))
from device_paired_timing import TimingChild, argv, device_lock, regular, save
from persistent_oracle import PersistentOracle, validate_plan
from profile_capture import source_inventory, run as capture_process
from aprof_runtime.jsonio import file_hash
from aprof_runtime.profile_evidence import _json
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact

PROTOCOL = "shared_buffer_acl_event_v2"
PREFIX = "APROF_SHARED_TIMING_JSON:"
ROLES = ("baseline", "candidate")
PHASES = ("aa_before", "formal", "aa_after")
PRODUCERS = (
    "skills/ascendc-aprof-profiling/scripts/device_shared_timing.py",
    "skills/ascendc-aprof-profiling/scripts/device_paired_timing.py",
    "skills/ascendc-aprof-profiling/scripts/persistent_oracle.py",
    "skills/ascendc-aprof-profiling/scripts/profile_capture.py",
    "skills/ascendc-aprof-profiling/assets/device_shared_timing.h",
    "runtime/src/aprof_runtime/jsonio.py",
    "runtime/src/aprof_runtime/profile_evidence.py",
    "runtime/src/aprof_runtime/measurement_admission.py",
    "runtime/src/aprof_runtime/gates.py",
    "runtime/src/aprof_runtime/contracts.py",
)


def config_value(value):
    config = deepcopy(value)
    fields = {"schema_version", "operator", "run_id", "session_id", "candidate_id",
              "device", "physical_device", "expected_case_ids", "roles", "build", "cases"}
    if not isinstance(config, dict) or set(config) != fields or config["schema_version"] != "1.0.0":
        raise ValueError("invalid shared timing config")
    for key in ("operator", "run_id", "session_id", "candidate_id"):
        if not isinstance(config[key], str) or not config[key].strip():
            raise ValueError(key + " must be a nonempty string")
    for key in ("device", "physical_device"):
        if type(config[key]) is not int or config[key] < 0:
            raise ValueError("invalid " + key)
    mapped = False
    for key in ("ASCEND_RT_VISIBLE_DEVICES", "ASCEND_VISIBLE_DEVICES"):
        if os.environ.get(key):
            mapped = True
            tokens = os.environ[key].split(",")
            if (not all(t.strip().isdigit() for t in tokens) or config["device"] >= len(tokens)
                    or int(tokens[config["device"]]) != config["physical_device"]):
                raise ValueError("physical device differs from visibility mapping")
    if not mapped and config["physical_device"] != config["device"]:
        raise ValueError("unmapped logical and physical device must agree")
    ids = config["expected_case_ids"]
    if (not isinstance(ids, list) or not ids or any(type(i) is not int or i < 1 for i in ids)
            or len(set(ids)) != len(ids)):
        raise ValueError("expected_case_ids must be unique positive integers")
    if not isinstance(config["roles"], dict) or set(config["roles"]) != set(ROLES):
        raise ValueError("both fixed source roles are required")
    for role in ROLES:
        item = config["roles"][role]
        if set(item) != {"source_dir", "symbol", "launches_per_operator"}:
            raise ValueError("role requires source_dir, symbol and launches_per_operator")
        item["source_dir"] = str(Path(item["source_dir"]).resolve(strict=True))
        if not Path(item["source_dir"]).is_dir() or not isinstance(item["symbol"], str) or not item["symbol"]:
            raise ValueError("invalid role source or symbol")
        if type(item["launches_per_operator"]) is not int or item["launches_per_operator"] < 1:
            raise ValueError("invalid launch count")
    if config["roles"]["baseline"]["symbol"] == config["roles"]["candidate"]["symbol"]:
        raise ValueError("formal callbacks must have distinct source symbols")
    build = config["build"]
    if set(build) != {"source_dir", "binary", "receipt_files"}:
        raise ValueError("build requires source_dir, binary and receipt_files")
    build["source_dir"] = str(Path(build["source_dir"]).resolve(strict=True))
    if not Path(build["source_dir"]).is_dir():
        raise ValueError("build source_dir must be a directory")
    build["binary"] = str(regular(build["binary"]))
    if not isinstance(build["receipt_files"], list) or not build["receipt_files"]:
        raise ValueError("immutable build receipts are required")
    build["receipt_files"] = [str(regular(p)) for p in build["receipt_files"]]
    if not isinstance(config["cases"], list) or [c.get("case_id") for c in config["cases"]] != ids:
        raise ValueError("cases must exactly match the declared workload order")
    for case in config["cases"]:
        if set(case) != {"case_id", "workload", "prepared_files", "command", "verify_commands", "output_files"}:
            raise ValueError("invalid shared timing case fields")
        if not isinstance(case["workload"], dict) or not case["workload"]:
            raise ValueError("nonempty workload required")
        if not isinstance(case["prepared_files"], list) or not case["prepared_files"]:
            raise ValueError("immutable inputs and oracle data are required")
        case["prepared_files"] = [str(regular(p)) for p in case["prepared_files"]]
        argv(case["command"], "command")
        if case["command"][0] != build["binary"]:
            raise ValueError("shared command must execute the bound binary directly")
        if "--device" in case["command"]:
            position = case["command"].index("--device")
            if position + 1 >= len(case["command"]) or case["command"][position + 1] != str(config["device"]):
                raise ValueError("command device differs from the locked device")
        if set(case["verify_commands"]) != set(ROLES) or set(case["output_files"]) != set(ROLES):
            raise ValueError("both callback output verifiers are required")
        for role in ROLES:
            argv(case["verify_commands"][role], "verify_command")
            for i, token in enumerate(case["verify_commands"][role]):
                if i == 0 or ("{cycle_dir}" not in token and Path(token).suffix in {".py", ".sh"}):
                    case["verify_commands"][role][i] = str(regular(token))
            outputs = case["output_files"][role]
            if (not isinstance(outputs, list) or not outputs or
                    any(not isinstance(p, str) or not p.startswith("{cycle_dir}/") for p in outputs)):
                raise ValueError("fresh role outputs must be under {cycle_dir}/")
    return config


def inventory(config, selected_case=None):
    """Identities are checked outside active sampling, before and after each cycle."""
    files = set(config["build"]["receipt_files"] + [config["build"]["binary"]])
    for case in config["cases"] if selected_case is None else [selected_case]:
        files.update(case["prepared_files"])
        for command in case["verify_commands"].values():
            files.add(str(regular(command[0])))
            for item in command[1:]:
                if "{cycle_dir}" not in item and Path(item).suffix in {".py", ".sh"}:
                    files.add(str(regular(item)))
    return {
        "files": {p: file_hash(p) for p in sorted(files)},
        "sources": {role: source_inventory(config["roles"][role]["source_dir"]) for role in ROLES},
        "build_sources": source_inventory(config["build"]["source_dir"]),
        "producer_files": {p: file_hash(RELEASE / p) for p in PRODUCERS},
    }


def bind_identity(config, snapshot, store):
    refs = {p: store.register_artifact(p) for p in snapshot["files"]}
    def source(path):
        return register_json_artifact(store, {"schema_version": "1.0.0", "files": source_inventory(path, store)})
    cases = {}
    for case in config["cases"]:
        verifiers = {}
        for command in case["verify_commands"].values():
            for i, token in enumerate(command):
                if i == 0 or ("{cycle_dir}" not in token and Path(token).suffix in {".py", ".sh"}):
                    verifiers[token] = refs[str(regular(token))]
        cases[str(case["case_id"])] = {
            "workload_ref": register_json_artifact(store, case["workload"]),
            "prepared_files": {p: refs[p] for p in case["prepared_files"]}, "verifier_files": verifiers,
        }
    return {
        "source_hashes": {role: source(config["roles"][role]["source_dir"]) for role in ROLES},
        "build": {"source_ref": source(config["build"]["source_dir"]),
                  "binary_ref": refs[config["build"]["binary"]],
                  "receipt_refs": {p: refs[p] for p in config["build"]["receipt_files"]}},
        "cases": cases,
    }


def command(child, text):
    begin = time.monotonic_ns()
    child.process.stdin.write(text + "\n")
    child.process.stdin.flush()
    value = _json(child.until(PREFIX))
    return {"request_monotonic_ns": begin, "response_monotonic_ns": time.monotonic_ns(), "message": value}


def check_message(message, ready, *, kind, index=None, phase=None, pair=None):
    if not isinstance(message, dict) or message.get("kind") != kind:
        raise ValueError("unexpected shared timing response")
    common = ("schema_version", "protocol", "operator", "cycle_index", "pid", "device",
              "context_address", "stream_address", "buffers", "warmup", "repeat",
              "prime_repeat", "launches_per_operator", "role_symbols", "execution_mode", "mode", "warmup_role_counts")
    if any(key not in ready or message.get(key) != ready[key] for key in common):
        raise ValueError("shared process/context/buffer/source identity changed")
    for key, value in (("command_index", index), ("phase", phase), ("pair_index", pair)):
        if value is not None and message.get(key) != value:
            raise ValueError("shared command index or phase differs")
    if kind == "prime":
        order = list(ROLES if ready["cycle_index"] % 2 == 0 else reversed(ROLES))
        if message.get("prime_order") != (["baseline"] * 4 if phase == "pilot" else [order[0], order[1], order[1], order[0]]):
            raise ValueError("shared prime order differs")
    if kind == "pair":
        order = list(ROLES if (ready["cycle_index"] + pair) % 2 == 0 else reversed(ROLES))
        if message.get("order") != order:
            raise ValueError("shared pair order differs")
        for role in ROLES:
            if message.get(role, {}).get("implementation") != (role if phase == "formal" else "baseline"):
                raise ValueError("shared callback mapping differs")


def expanded(tokens, directory):
    return [s.replace("{cycle_dir}", str(directory)) for s in tokens]


def session_directory(output, case_id, mode, cycle=0):
    return output / (f"case-{case_id:02d}-pilot" if mode == "pilot" else f"case-{case_id:02d}-cycle-{cycle}")


def oracle_plan(config, output, identity):
    """Freeze every output/verifier slot before starting any native process."""
    requests = []
    for stage in ("calibration", "confirmation"):
        for case in config["cases"]:
            for cycle in ([None] if stage == "calibration" else range(6)):
                directory = session_directory(output, case["case_id"], "pilot" if cycle is None else "confirmation", cycle or 0)
                for role in ROLES:
                    arguments = expanded(case["verify_commands"][role], directory)
                    if len(arguments) < 2 or arguments.count("--result") != 1:
                        raise ValueError("persistent Python oracle requires an explicit --result path")
                    position = arguments.index("--result")
                    if position + 1 == len(arguments):
                        raise ValueError("oracle --result path is missing")
                    result = Path(arguments[position + 1])
                    if not result.is_absolute() or not result.is_relative_to(directory) or ".." in result.parts:
                        raise ValueError("oracle result must be isolated in its session directory")
                    requests.append({
                        "request_index": len(requests), "stage": stage, "case_id": case["case_id"],
                        "cycle": cycle, "role": role, "argv": arguments, "cwd": config["build"]["source_dir"],
                        "script_ref": identity["cases"][str(case["case_id"])]["verifier_files"][arguments[1]],
                        "prepared_refs": identity["cases"][str(case["case_id"])]["prepared_files"],
                        "output_paths": expanded(case["output_files"][role], directory),
                        "result_path": str(result), "log_path": str(directory / f"{role}-verify.log"),
                        "stderr_path": str(directory / f"{role}-verify.stderr.log"),
                    })
    return validate_plan({"schema_version": 1, "protocol": "persistent_python_oracle_v1",
                          "run_id": config["run_id"], "session_id": config["session_id"], "requests": requests})


def remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError("shared timing trial deadline exceeded")
    return min(180, value)


def run_session(config, case, run, repeat, snapshot, env, worker, request_indices, store, deadline):
    """One fresh native process; all persistence and oracle calls follow its exit."""
    directory = Path(run["cycle_dir"])
    directory.mkdir()
    cycle, mode = run["cycle"], run["mode"]
    child = None
    try:
        remaining(deadline)
        run["identity_before"] = inventory(config, case)
        expected_snapshot = dict(snapshot, files={p: snapshot["files"].get(p) for p in run["identity_before"]["files"]})
        if run["identity_before"] != expected_snapshot:
            raise ValueError("frozen identity changed before session")
        outputs = {role: expanded(case["output_files"][role], directory) for role in ROLES}
        paths = [Path(p) for values in outputs.values() for p in values]
        if len(set(paths)) != len(paths) or any(p.exists() or p.is_symlink() or not p.resolve().is_relative_to(directory) for p in paths):
            raise ValueError("callback outputs must be fresh and isolated")
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
        timing_env = {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(cycle),
                      "APROF_SHARED_MODE": mode, "APROF_SHARED_REPEAT": str(repeat)}
        child = TimingChild(expanded(case["command"], directory), config["build"]["source_dir"],
                            dict(env, **timing_env), directory / "stdout.log", remaining(deadline))
        run["execution"] = child.receipt
        run["execution"]["environment"] = timing_env
        run["ready"] = _json(child.until(PREFIX))
        ready = run["ready"]
        expected_ready = {
            "kind": "ready", "schema_version": "1.0.0", "protocol": PROTOCOL,
            "operator": config["operator"], "cycle_index": cycle,
            "pid": child.process.pid, "device": config["device"],
            "warmup": 10, "repeat": repeat, "prime_repeat": 100, "mode": mode,
            "warmup_role_counts": {"baseline": 20, "candidate": 0} if mode == "pilot" else {"baseline": 10, "candidate": 10},
            "execution_mode": "direct_enqueue",
            "role_symbols": {r: config["roles"][r]["symbol"] for r in ROLES},
            "launches_per_operator": {r: config["roles"][r]["launches_per_operator"] for r in ROLES},
        }
        if any(ready.get(k) != v for k, v in expected_ready.items()):
            raise ValueError("shared READY differs from registered protocol")
        check_message(ready, ready, kind="ready")
        def exchange(text, **expected):
            child.timeout = remaining(deadline)
            event = command(child, text)
            run["events"].append(event)
            check_message(event["message"], ready, **expected)
            return event["message"]
        if mode == "pilot":
            exchange("prime 0 pilot", kind="prime", index=0, phase="pilot")
            for sample in range(3):
                message = exchange(f"sample {sample + 1} pilot {sample}", kind="pilot_sample", index=sample + 1, phase="pilot")
                if message.get("sample_index") != sample:
                    raise ValueError("pilot sample index differs")
            index = 4
        else:
            index = 0
            for phase in PHASES:
                exchange(f"prime {index} {phase}", kind="prime", index=index, phase=phase)
                index += 1
                for pair in range(5):
                    exchange(f"pair {index} {phase} {pair}", kind="pair", index=index, phase=phase, pair=pair)
                    index += 1
        exchange(f"finish {index}", kind="complete", index=index)
        child.process.wait(timeout=remaining(deadline))
        child.close()
        if run["execution"]["exit_status"] != 0:
            raise ValueError("shared native process failed")
        run["stdout_ref"] = store.register_artifact(directory / "stdout.log")
        for path in paths:
            if path.is_symlink() or not path.is_file():
                raise ValueError("callback did not export an isolated output")
            run["output_hashes"][str(path)] = store.register_artifact(path)
        for role in ROLES:
            try:
                receipt = worker.verify(request_indices[role])
            except BaseException:
                if worker.last_receipt is not None:
                    run["verifications"][role] = worker.last_receipt
                raise
            run["verifications"][role] = receipt
        if any(file_hash(p) != h for p, h in run["output_hashes"].items()):
            raise ValueError("verifier modified a callback output")
        run["identity_after"] = inventory(config, case)
        if run["identity_after"] != expected_snapshot:
            raise ValueError("frozen identity changed during session")
        remaining(deadline)
    finally:
        if child is not None:
            child.close(abort=True)
            run["stdout_ref"] = store.register_artifact(directory / "stdout.log")
        run["finished_at"] = time.time()


def collect(value, output, store, *, timeout_seconds=3600):
    if not isinstance(timeout_seconds, (float, int)) or isinstance(timeout_seconds, bool) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("positive finite trial timeout required")
    deadline = time.monotonic() + timeout_seconds
    config = config_value(value)
    output = Path(output).resolve()
    for source in [config["build"]["source_dir"], *(r["source_dir"] for r in config["roles"].values())]:
        if output.is_relative_to(source):
            raise ValueError("evidence directory must be outside source trees")
    output.mkdir(parents=True, exist_ok=False)
    save(output / "config.json", config)
    snapshot = inventory(config)
    identity = bind_identity(config, snapshot, store)
    same_source = identity["source_hashes"]["baseline"] == identity["source_hashes"]["candidate"]
    for name, digest in snapshot["producer_files"].items():
        if store.register_artifact(RELEASE / name) != digest:
            raise ValueError("producer changed during registration")
    config_ref = store.register_artifact(output / "config.json")
    plan = oracle_plan(config, output, identity)
    save(output / "verifier-request-plan.json", plan)
    plan_ref = store.register_artifact(output / "verifier-request-plan.json")
    slots = {(item["stage"], item["case_id"], item["cycle"], item["role"]): item["request_index"] for item in plan["requests"]}
    npu_smi = regular(shutil.which("npu-smi") or "/usr/local/sbin/npu-smi")
    probe = capture_process([str(npu_smi), "info", "-t", "board", "-i", str(config["physical_device"]), "-c", "0"],
                            output, output / "hardware-probe", min(60, remaining(deadline)), store)
    cann_home = Path(os.environ.get("ASCEND_HOME_PATH", "/usr/local/Ascend/ascend-toolkit/latest")).resolve()
    install_info = regular(cann_home / (platform.machine() + "-linux/ascend_toolkit_install.info"))
    hardware = {"host": socket.gethostname(), "physical_device": config["physical_device"],
                "probe": {k: v for k, v in probe.items() if k != "text"},
                "npu_smi_ref": store.register_artifact(npu_smi),
                "cann_home": str(cann_home), "cann_install_info_ref": store.register_artifact(install_info)}
    hardware_ref = register_json_artifact(store, hardware)
    calibration = {"schema_version": "1.0.0", "protocol": PROTOCOL, "config_ref": config_ref,
                   "started_at": time.time(), "finished_at": None, "host": socket.gethostname(), "cases": []}
    raw = {"protocol": PROTOCOL, "registration_ref": None, "calibration_ref": None, "repeat_by_case": {},
           "started_at": None, "finished_at": None, "complete": False, "sessions": [], "host": socket.gethostname()}
    env = {key: value for key, value in os.environ.items() if not key.startswith("APROF_")}
    raw["environment"] = {k: env.get(k) for k in (
        "ASCEND_HOME_PATH", "ASCEND_OPP_PATH", "LD_LIBRARY_PATH", "ASCEND_RT_VISIBLE_DEVICES",
        "ASCEND_VISIBLE_DEVICES", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}
    worker, registration_ref = None, None
    try:
        worker = PersistentOracle(plan, directory=output / "oracle-worker", store=store, deadline=deadline)
        worker.start()
        if worker.report["request_plan_ref"] != plan_ref:
            raise ValueError("worker changed the frozen oracle roster")
        with device_lock(config["physical_device"], remaining(deadline)):
            for case in config["cases"]:
                run = {"case_id": case["case_id"], "cycle": 0, "mode": "pilot",
                       "cycle_dir": str(session_directory(output, case["case_id"], "pilot")),
                       "started_at": time.time(), "finished_at": None, "events": [], "verifications": {}, "output_hashes": {}}
                item = {"case_id": case["case_id"], "repeat": None, "median_ms": None, "pilot": run}
                calibration["cases"].append(item)
                run_session(config, case, run, 100, snapshot, env, worker,
                            {r: slots[("calibration", case["case_id"], None, r)] for r in ROLES}, store, deadline)
                from aprof_runtime.measurement_admission import _pilot_samples
                item["median_ms"] = statistics.median(_pilot_samples(run, config))
                item["repeat"] = 100 * max(1, math.ceil(50 / item["median_ms"]))
                if item["repeat"] > 100000:
                    raise ValueError(f"case {case['case_id']}: pilot repeat exceeds 100000 cap")
                raw["repeat_by_case"][str(case["case_id"])] = item["repeat"]
                save(output / "calibration.json", calibration)
            calibration["finished_at"] = time.time()
            save(output / "calibration.json", calibration)
            raw["calibration_ref"] = store.register_artifact(output / "calibration.json")
            registration = {
                "protocol": PROTOCOL, "created_at": time.time(), "config_ref": config_ref,
                "identity": identity, "inventory": snapshot, "producer_files": snapshot["producer_files"],
                "attempt_policy": "exactly_once_no_resume_no_resampling", "cycles": 6,
                "pairs_per_phase": 5, "warmup": 10, "prime_repeat": 100,
                "cpu_affinity": sorted(os.sched_getaffinity(0)), "hardware_ref": hardware_ref,
                "calibration_ref": raw["calibration_ref"], "repeat_by_case": dict(raw["repeat_by_case"]),
                "verifier_request_plan_ref": plan_ref,
            }
            save(output / "registration.json", registration)
            registration_ref = store.register_artifact(output / "registration.json")
            raw.update(registration_ref=registration_ref, started_at=time.time())
            for case in config["cases"]:
                repeat = raw["repeat_by_case"][str(case["case_id"])]
                for cycle in range(6):
                    run = {"case_id": case["case_id"], "cycle": cycle, "mode": "confirmation",
                           "cycle_dir": str(session_directory(output, case["case_id"], "confirmation", cycle)),
                           "started_at": time.time(), "finished_at": None, "events": [], "verifications": {}, "output_hashes": {}}
                    raw["sessions"].append(run)
                    run_session(config, case, run, repeat, snapshot, env, worker,
                                {r: slots[("confirmation", case["case_id"], cycle, r)] for r in ROLES}, store, deadline)
                    from aprof_runtime.measurement_admission import _phase_controls, _session_samples
                    quality = _phase_controls(_session_samples(run, config, expected_repeat=repeat))
                    run["control_summary"] = quality
                    control_phases = PHASES if same_source else ("aa_before", "aa_after")
                    if (any(quality[p]["role_bias"] > 0.02 for p in control_phases)
                            or any(quality[p][r + "_cv"] > 0.05 for p in PHASES for r in ROLES)
                            or any(value > 0.02 for value in quality["drift"].values())):
                        raise ValueError(f"case {case['case_id']} cycle {cycle}: measurement control failed")
                    save(output / "raw_measurements.json", raw)
                from aprof_runtime.measurement_admission import summarize_shared_raw
                case_raw = dict(raw, complete=True, sessions=[s for s in raw["sessions"] if s["case_id"] == case["case_id"]],
                                repeat_by_case={str(case["case_id"]): repeat})
                case_config = dict(config, expected_case_ids=[case["case_id"]], cases=[case])
                case_report = summarize_shared_raw(case_raw, case_config)
                if not case_report["stable"]:
                    raise ValueError(f"case {case['case_id']}: " + "; ".join(case_report["reasons"]))
                if same_source and case_report["controls"][0]["overall"]["formal"]["role_bias"] > 0.02:
                    raise ValueError(f"case {case['case_id']}: same-source formal A/A role bias exceeds 2%")
            raw["complete"] = True
    except BaseException as error:
        raw["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        if worker is not None and worker.directory.is_dir():
            raw["verifier_worker_ref"] = worker.finish(abort=not raw["complete"])
            if raw["complete"] and worker.report["status"] != "complete":
                raw["complete"] = False
                raw["error"] = {"type": "RuntimeError", "message": "persistent oracle did not complete"}
        if calibration["finished_at"] is None:
            calibration["finished_at"] = time.time()
            save(output / "calibration.json", calibration)
            raw["calibration_ref"] = store.register_artifact(output / "calibration.json")
        raw["finished_at"] = time.time()
        save(output / "raw_measurements.json", raw)
        raw_ref = store.register_artifact(output / "raw_measurements.json")
        from aprof_runtime.measurement_admission import summarize_shared_raw
        report = summarize_shared_raw(raw, config)
        save(output / "measurement_report.json", report)
        report_ref = store.register_artifact(output / "measurement_report.json")
        receipt = {"schema_version": "1.0.0", "protocol": PROTOCOL,
                   **{k: config[k] for k in ("operator", "run_id", "session_id", "candidate_id")},
                   "source_hashes": identity["source_hashes"], "registration_ref": registration_ref,
                   "config_ref": config_ref, "raw_ref": raw_ref, "measurement_report_ref": report_ref}
        save(output / "measurement_admission.json", receipt)
        receipt_ref = store.register_artifact(output / "measurement_admission.json")
        save(output / "artifacts.json", {"measurement_report": report_ref, "measurement_admission": receipt_ref})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--store", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=3600)
    args = parser.parse_args()
    with EpisodeStore(args.store) as store:
        report = collect(_json(args.config.read_text()), args.output, store, timeout_seconds=args.timeout_seconds)
    print(json.dumps({"measurement_stable": report["stable"], "authority": "measurement_only_no_performance_verdict"}))
    return 0 if report["stable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
