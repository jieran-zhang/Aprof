#!/usr/bin/env python3
"""Read-only qualification checks above the unchanged runtime performance gate.

All ``*_ref`` values are CAS sha256 strings. ``expected.registration_ref`` comes
from the trusted preregistration/controller receipt, never from a claimed verdict.
protocol binds source/binary hashes, collector_ref, input_inventory_ref,
oracle_files and phases[name].config_ref. Registration binds that protocol,
one attempt and ordered stages. The roster contains CAS events chained from the
registration: one started/completed pair per stage, with actual timestamps and
completed evidence refs. A control report binds the roster and each phase's
raw_ref/config_ref/report_ref. No measured command is executed during replay.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import struct

from run_aprof_job import sha as file_hash


ROLES = ("baseline", "candidate")
PHASES = ("aa_before", "formal", "aa_after")
BOUNDARY_SIZES = {
    "exp": [1, 31, 32, 33, 4095, 4096, 4097, 8191, 8192, 8193, 196607, 196608, 196609, 65],
    "sigmoid": [1, 7, 8, 15, 16, 17, 31, 32, 33, 4095, 4096, 4097, 196607, 196608, 196609,
                393215, 393216, 393217, 65],
}
THRESHOLDS = {"float16": 2 ** -10, "float32": 2 ** -13, "bfloat16": 2 ** -7}
RULE_CONTROL_CASES = {"exp": [1, 3, 8, 9, 14, 20], "sigmoid": [1, 3, 8, 14, 16, 20]}


def digest(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def content_hash(value):
    return digest(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                             allow_nan=False).encode())


def read(store, reference):
    path = store.verify_artifact(reference)
    if hash_file(store, path) != reference:
        raise ValueError("admission artifact hash differs")
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, float) and math.isfinite(value), "non-finite admission number")
    return value


def checked_path(store, path, reference):
    """Archived bytes are authoritative; check a surviving external file too."""
    artifact = Path(store.verify_artifact(reference))
    require(hash_file(store, artifact) == reference, "admission file hash differs")
    original = Path(path)
    if original.exists() or original.is_symlink():
        require(not original.is_symlink() and original.is_file() and hash_file(store, original) == reference,
                "admission external file changed")
    return artifact


def hash_file(store, path):
    return store.hash_file(Path(path)) if isinstance(store, ReplayCache) else file_hash(Path(path))


class ReplayCache:
    """Only reuse verified immutable bytes within one admission call."""
    def __init__(self, store):
        self.store, self.paths, self.hashes = store, {}, {}

    def hash_file(self, path):
        stat = path.stat()
        key = (str(path), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        if key not in self.hashes:
            self.hashes[key] = file_hash(path)
        return self.hashes[key]

    def verify_artifact(self, ref):
        path = self.paths.get(ref)
        if path is None:
            path = Path(self.store.verify_artifact(ref))
            self.paths[ref] = path
        require(self.hash_file(path) == ref, "admission CAS content changed")
        return path


def identity(value, expected):
    for key in ("run_id", "candidate_id", "operator", "source_hashes"):
        require(value.get(key) == expected[key], f"admission {key} differs")


def verify_roster(store, report, protocol, expected):
    reference = report.get("registration_ref")
    require(reference and reference == expected.get("registration_ref"), "admission preregistration differs")
    registration = read(store, reference)
    require(registration.get("schema_version") == 1
            and registration.get("protocol_ref") == report["protocol_ref"]
            and registration.get("run_id") == expected["run_id"]
            and registration.get("candidate_id") == expected["candidate_id"]
            and registration.get("max_attempts") == 1 and registration.get("stop_on_failure") is True
            and registration.get("resampling") == "none", "admission requires one preregistered attempt")
    stages = registration.get("stages", [])
    required = {"correctness", *PHASES}
    if protocol.get("purpose") in {"promotion", "evaluation"}:
        required.add("profile")
    if expected.get("purpose") == "promotion":
        required |= {"boundary", "screen"}
    require(isinstance(stages, list) and len(stages) == len(set(stages)) and required <= set(stages),
            "admission stage roster incomplete or duplicated")
    canonical = ["correctness", "boundary", "aa_before", "screen", "formal", "aa_after", "profile"]
    require(stages == [stage for stage in canonical if stage in stages], "admission stage order differs")
    roster = read(store, report["attempt_roster_ref"])
    require(roster.get("schema_version") == 1 and roster.get("registration_ref") == reference
            and len(roster.get("events", [])) == 2 * len(stages), "admission attempt roster incomplete")
    previous = reference
    timestamp = number(registration["created_at"])
    require(number(protocol["created_at"]) <= timestamp, "protocol was not frozen before registration")
    windows = {}
    for sequence, ref in enumerate(roster["events"]):
        event = read(store, ref)
        stage, state = stages[sequence // 2], ("started", "completed")[sequence % 2]
        require(event.get("sequence") == sequence and event.get("previous_ref") == previous
                and event.get("registration_ref") == reference and event.get("stage") == stage
                and event.get("state") == state, "admission attempt history was reordered or resampled")
        current = number(event["at"])
        require(current >= timestamp, "admission chronology differs")
        if state == "started":
            windows[stage] = [current]
        else:
            require(event.get("exit_status") == 0 and event.get("evidence_refs"),
                    "admission includes a failed or unsupported stage")
            for evidence in event["evidence_refs"]:
                store.verify_artifact(evidence)
            windows[stage].append(current)
            if stage in report and stage in protocol["phases"]:
                require(set(report[stage].values()) <= set(event["evidence_refs"]),
                        "admission phase evidence absent from attempt history")
        previous, timestamp = ref, current
    for ref in protocol.get("history_refs", []):
        store.verify_artifact(ref)
    return windows


def controls(records, cases, *, enforce=True):
    """The predeclared legacy formula; never infer A/A quality from stable."""
    rows = []
    for epoch in (None, 0, 1):
        for case in cases:
            selected = [row for row in records if row["case_id"] == case and (epoch is None or row["epoch"] == epoch)]
            a, b = ([number(row[role]["elapsed_ns"]) for row in selected] for role in ROLES)
            require(len(a) >= 2 and all(value > 0 for value in a + b), "A/A samples incomplete or nonpositive")
            bias = abs(math.exp(statistics.fmean(math.log(y / x) for x, y in zip(a, b))) - 1)
            cvs = [statistics.stdev(values) / statistics.fmean(values) for values in (a, b)]
            passed = bias <= .02 and max(cvs) <= .05
            if enforce:
                require(passed, "A/A role bias or sample CV exceeds frozen threshold")
            rows.append({"case_id": case, "epoch": epoch, "role_bias": bias, "baseline_cv": cvs[0], "candidate_cv": cvs[1], "passed": passed})
    return rows


def drift(before, after, cases):
    result = []
    for epoch in (None, 0, 1):
        for case in cases:
            row = {"case_id": case, "epoch": epoch}
            for role in ROLES:
                values = [[r[role]["elapsed_ns"] for r in records
                           if r["case_id"] == case and (epoch is None or r["epoch"] == epoch)]
                          for records in (before, after)]
                shift = abs(statistics.fmean(values[1]) / statistics.fmean(values[0]) - 1)
                require(shift <= .02, "A/A session drift exceeds frozen threshold")
                row[role + "_shift"] = shift
            result.append(row)
    return result


def control_statistics(raw, config, *, before_raw=None):
    """Early stop statistics only; full admission additionally replays all evidence."""
    rows = controls(raw["records"], config["expected_case_ids"], enforce=False)
    result = {"passed": all(row["passed"] for row in rows), "rows": rows}
    if before_raw is not None:
        try:
            result["drift"] = drift(before_raw["records"], raw["records"], config["expected_case_ids"])
        except ValueError as error:
            result.update(passed=False, reason=str(error))
    return result


def _collector():
    path = Path(__file__).with_name("device_paired_timing_v2.py")
    spec = importlib.util.spec_from_file_location("admission_paired_timing_v2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_phase(store, phase, pointers, protocol, window, collector):
    require(set(pointers) == {"raw_ref", "config_ref", "report_ref"}
            and pointers["config_ref"] == protocol["phases"][phase]["config_ref"],
            "timing configuration was not preregistered")
    raw, config, report = (read(store, pointers[name]) for name in ("raw_ref", "config_ref", "report_ref"))
    repeat = protocol["measurement_policy"]["repeat"]
    exploratory = phase == "screen" or (protocol["purpose"] == "protocol_diagnostic" and phase.startswith("aa_"))
    require(type(repeat) is int and repeat > 0, "timing repeat must be preregistered positive integer")
    require(config.get("schema_version") == "2.0.0" and config.get("epochs") == 2
            and config.get("prime_repeat") == 100 and config.get("repeat") == repeat and config.get("warmup") == 10
            and config.get("pairs") == (6 if exploratory else 30)
            and config.get("mode") == ("explore" if exploratory else "formal")
            and config.get("operator") == protocol["operator"], "timing protocol parameters differ")
    cases = config["expected_case_ids"]
    require(cases and len(cases) == len(set(cases)) and [case["case_id"] for case in config["cases"]] == cases,
            "timing case inventory differs")
    if phase == "formal":
        require(cases == list(range(1, 21)), "formal timing must cover all twenty cases")
    require(raw.get("schema_version") == "2.0.0" and raw.get("measurement_protocol") == collector.PROTOCOL
            and raw.get("complete") is True and not raw.get("error")
            and raw.get("config_hash") == content_hash(config)
            and raw.get("producer_hash") == protocol["collector_ref"] == digest(Path(collector.__file__).read_bytes()),
            "timing producer, completeness or frozen config differs")
    for key in ("operator", "device", "physical_device", "pairs", "warmup", "repeat", "epochs", "prime_repeat", "mode"):
        require(raw.get(key) == config[key], "raw timing protocol differs")
    require(raw.get("case_ids") == cases and raw.get("unit") == "ns" and raw.get("source") == "acl_event"
            and raw.get("timing_scope") == "complete_operator_device_event_interval", "timing scope differs")
    environment = raw.get("environment", {})
    require(isinstance(raw.get("host"), str) and raw["host"]
            and all(environment.get(key) == value for key, value in {
                "APROF_TIMING_INTERACTIVE": "1", "APROF_TIMING_V2": "1", "APROF_WARMUP": "10",
                "APROF_REPEAT": str(repeat), "APROF_PRIME_REPEAT": "100", "APROF_CAPTURE_REPLAY": None}.items()),
            "timing host/environment protocol differs")
    dependencies = raw["producer_dependencies"]
    runtime = Path(collector.v1.runtime_gates.__file__).parent
    runtime_files = {path.relative_to(runtime).as_posix(): digest(path.read_bytes()) for path in sorted(runtime.rglob("*.py"))}
    expected_dependencies = {"frozen_collector": digest(collector.V1_PATH.read_bytes()),
        "device_timer_v2.h": digest(collector.HEADER.read_bytes()),
        "profile_capture.py": digest((collector.v1.SCRIPTS / "profile_capture.py").read_bytes()),
        "runtime_source_files": runtime_files, "runtime_source_hash": content_hash(runtime_files)}
    require(dependencies == expected_dependencies, "timing dependency inventory differs")
    replayed = collector.v1.summarize(raw, config)
    replayed.update(schema_version="2.0.0", measurement_protocol=collector.PROTOCOL)
    require(replayed == report, "timing report does not replay from raw samples")
    if not exploratory:
        require(report["stable"] is True, "formal measurement stability failed")
    else:
        require(set(report["reasons"]) <= {"exploration screening is not formal timing evidence",
                                          "formal pair/warmup minimum not met"}, "exploration measurement quality failed")
    if phase == "screen":
        require(all(row["regression"] <= .03 for row in report["per_case"])
                and math.exp(statistics.fmean(math.log(row["speedup"]) for row in report["per_case"])) >= 1.,
                "preregistered screening criterion failed")
    inventories = {role: read(store, ref)["files"] for role, ref in protocol["source_hashes"].items()}
    native_verifier = inventories["baseline"].get("scripts/verify_result.py")
    require(native_verifier and inventories["candidate"].get("scripts/verify_result.py") == native_verifier,
            "timing must preserve the original native oracle")
    inputs = read(store, protocol["input_inventory_ref"])
    require(inputs and protocol["oracle_files"], "frozen input/oracle inventory missing")
    for path, reference in {**inputs, **protocol["oracle_files"]}.items():
        checked_path(store, path, reference)
    expected_records = [(case, index) for case in cases for index in range(config["pairs"])]
    require([(row["case_id"], row["round"]) for row in raw["records"]] == expected_records,
            "timing sample count/order differs from preregistration")
    require([item["case_id"] for item in raw["case_executions"]] == cases
            and set(raw["case_identities"]) == set(map(str, cases)), "timing execution inventory differs")
    half, prior_end = config["pairs"] // 2, window[0]
    monotonic_end = 0
    for case, execution in zip(config["cases"], raw["case_executions"], strict=True):
        require(execution["exit_status"] == 0 and execution["workload"] == case["workload"]
                and prior_end <= number(execution["started_at"]) <= number(execution["finished_at"]) <= window[1],
                "timing stage chronology differs from attempt roster")
        require([state["epoch"] for state in execution["epochs"]] == [0, 1], "timing epoch inventory differs")
        require(len(raw["case_identities"][str(case["case_id"])]["epochs"]) == 2, "timing epoch identity incomplete")
        pids = set()
        previous_epoch_end = execution["started_at"]
        for epoch, state in enumerate(execution["epochs"]):
            startup = list(ROLES if epoch == 0 else reversed(ROLES))
            ident = raw["case_identities"][str(case["case_id"])]["epochs"][epoch]
            require(state["startup_order"] == startup and state["exit_status"] == 0
                    and state["identity_before"] == ident == state["identity_after"]
                    and ident["workload_hash"] == content_hash(case["workload"])
                    and previous_epoch_end <= number(state["started_at"]) <= number(state["finished_at"]) <= execution["finished_at"],
                    "timing epoch lifecycle/workload differs")
            require(set(ident["prepared_files"]) == set(case["prepared_files"])
                    and all(inputs.get(path) == ref for path, ref in ident["prepared_files"].items()),
                    "timing prepared input differs from frozen inventory")
            clock = number(state["started_monotonic_ns"])
            require(clock >= monotonic_end, "timing monotonic chronology differs")
            commands, verifications = state["commands"], state["verifications"]
            require(set(commands) == set(verifications) == set(state["ready_receipts"]) == set(ROLES),
                    "timing role evidence incomplete")
            for role in startup:
                source_role = "baseline" if phase.startswith("aa_") else role
                source = ident[role]
                require(source["source_files"] == inventories[source_role]
                        and source["source_hash"] == content_hash(inventories[source_role])
                        and source["binary_hash"] == protocol["binary_hashes"][source_role]
                        and native_verifier in source["verifier_files"].values() and all(protocol["oracle_files"].get(path) == ref
                            for path, ref in source["verifier_files"].items()), "timing source/binary/oracle differs")
                checked_path(store, config[role]["binary"], source["binary_hash"])
                command, ready = commands[role], state["ready_receipts"][role]
                pid = command["pid"]
                require(type(pid) is int and pid > 0 and pid not in pids and ready["pid"] == pid
                        and command["argv"] == case["epochs"][epoch][role]["command"]
                        and command["argv"][0] == config[role]["binary"] and command["cwd"] == config[role]["cwd"]
                        and command["exit_status"] == 0 and not command.get("error")
                        and state["started_at"] <= number(command["started_at"]) <= number(command["finished_at"]) <= state["finished_at"],
                        "timing process/source command differs or epoch reused a PID")
                require(clock <= number(ready["wait_started_monotonic_ns"]) <= number(ready["ready_monotonic_ns"]),
                        "timing READY chronology differs")
                clock = ready["ready_monotonic_ns"]
                pids.add(pid)
            prime_order = [startup[0], startup[1], startup[1], startup[0]]
            require([prime["role"] for prime in state["prime_receipts"]] == prime_order, "timing prime order differs")
            counts = dict.fromkeys(ROLES, 0)
            for prime in state["prime_receipts"]:
                role = prime["role"]
                expected_ack = {"schema_version": "2.0.0", "operator": config["operator"], "device": config["device"],
                    "prime_index": counts[role], "repeat": 100,
                    "launches_per_operator": case["epochs"][epoch][role]["launches_per_operator"]}
                require(prime["pid"] == commands[role]["pid"] and prime["acknowledgement"] == expected_ack
                        and clock <= number(prime["request_monotonic_ns"]) <= number(prime["response_monotonic_ns"]),
                        "timing prime acknowledgement/count/chronology differs")
                clock = prime["response_monotonic_ns"]
                counts[role] += 1
            selected = [row for row in raw["records"] if row["case_id"] == case["case_id"] and row["epoch"] == epoch]
            require(len(selected) == half, "timing epoch sample count differs")
            for local, row in enumerate(selected):
                index = epoch * half + local
                order = list(ROLES if index % 2 == 0 else reversed(ROLES))
                require(row["local_round"] == local and row["round"] == index and row["order"] == order
                        and row["device"] == config["device"], "timing sample order/index differs")
                for role in order:
                    sample, receipt = row[role], row["sample_receipts"][role]
                    expected_sample = {"schema_version": "1.0.0", "operator": config["operator"], "device": config["device"],
                        "source": "acl_event", "unit": "ns", "sample_index": local, "warmup": 10, "repeat": repeat,
                        "launches_per_operator": case["epochs"][epoch][role]["launches_per_operator"]}
                    require(set(sample) == set(expected_sample) | {"elapsed_ns"}
                            and all(type(sample[key]) is type(value) and sample[key] == value for key, value in expected_sample.items())
                            and number(sample["elapsed_ns"]) > 0 and receipt["pid"] == commands[role]["pid"]
                            and clock <= number(receipt["request_monotonic_ns"]) <= number(receipt["response_monotonic_ns"]),
                            "timing sample identity/chronology differs")
                    clock = receipt["response_monotonic_ns"]
            require(clock <= number(state["finished_monotonic_ns"]), "timing samples extend beyond epoch")
            monotonic_end, previous_epoch_end = state["finished_monotonic_ns"], state["finished_at"]
            expected_outputs = {path for role in ROLES for path in case["epochs"][epoch][role]["output_files"]}
            require(set(state["output_hashes"]) == expected_outputs, "timing output inventory differs")
            for path, ref in state["output_hashes"].items():
                checked_path(store, path, ref)
            for role in ROLES:
                command, verification = commands[role], verifications[role]
                log = checked_path(store, command["log_path"], command["log_hash"])
                messages = [line for line in log.read_text().splitlines() if line.startswith(("APROF_TIMING", "APROF_PRIME"))]
                expected_messages = ["APROF_TIMING_READY"]
                expected_acks = [prime["acknowledgement"] for prime in state["prime_receipts"] if prime["role"] == role]
                require(len(messages) == 1 + 2 + half and messages[:1] == expected_messages
                        and all(line.startswith("APROF_PRIME_JSON:") for line in messages[1:3])
                        and [json.loads(line.removeprefix("APROF_PRIME_JSON:")) for line in messages[1:3]] == expected_acks
                        and all(line.startswith("APROF_TIMING_JSON:") for line in messages[3:])
                        and [json.loads(line.removeprefix("APROF_TIMING_JSON:")) for line in messages[3:]] == [row[role] for row in selected],
                        "timing samples/prime receipts differ from original device stdout")
                require(verification["exit_status"] == 0 and not verification.get("error")
                        and verification["argv"] == case["epochs"][epoch][role]["verify_command"]
                        and verification["cwd"] == config[role]["cwd"]
                        and command["finished_at"] <= number(verification["started_at"])
                        <= number(verification["finished_at"]) <= state["finished_at"], "timing output verification failed or differs")
                checked_path(store, verification["log_path"], verification["log_hash"])
        prior_end = execution["finished_at"]
    return raw, config, report


def verify_timing_admission(store, control_report_ref, *, expected):
    store = ReplayCache(store)
    report = read(store, control_report_ref)
    require(report.get("schema_version") == 1, "unsupported timing admission schema")
    identity(report, expected)
    protocol = read(store, report["protocol_ref"])
    require(protocol.get("schema_version") == 1, "unsupported timing protocol schema")
    identity(protocol, expected)
    require(protocol.get("purpose") in {"baseline_qualification", "promotion", "evaluation", "protocol_diagnostic"}
            and (expected.get("purpose") is None or protocol["purpose"] == expected["purpose"]),
            "timing qualification purpose differs")
    if protocol["purpose"] == "promotion":
        require(protocol["measurement_policy"]["repeat"] == 100, "promotion repeat differs from registered rule protocol")
        require(protocol["operator"] in RULE_CONTROL_CASES, "promotion control scope is not independently registered")
    phases = set(protocol["phases"])
    require(set(PHASES) <= phases <= set(PHASES) | {"screen"}, "timing phase inventory incomplete")
    if expected.get("purpose") == "promotion":
        require("screen" in phases and protocol.get("boundary_plan_ref"), "promotion needs screening and boundary protocol")
    windows = verify_roster(store, report, protocol, expected)
    collector = _collector()
    data = {phase: verify_phase(store, phase, report[phase], protocol, windows[phase], collector) for phase in phases}
    machine = {key: data["formal"][0][key] for key in ("host", "device", "physical_device", "environment")}
    require(all({key: raw[key] for key in machine} == machine for raw, _, _ in data.values()),
            "timing controls and candidate measurements used different hosts/devices/environments")
    if expected.get("hardware_report_ref"):
        hardware = read(store, expected["hardware_report_ref"])
        require(hardware.get("host") == machine["host"]
                and str(hardware.get("physical_device")) == str(machine["physical_device"])
                and str(hardware.get("device")) == str(machine["device"]),
                "timing control hardware differs from mechanism captures")
    before, after = data["aa_before"], data["aa_after"]
    cases = before[1]["expected_case_ids"]
    require(cases == after[1]["expected_case_ids"] and set(cases) <= set(data["formal"][1]["expected_case_ids"]),
            "A/A before/after case coverage differs")
    if protocol["purpose"] == "promotion":
        required_cases = RULE_CONTROL_CASES[protocol["operator"]]
        require(set(required_cases) <= set(cases) and data["screen"][1]["expected_case_ids"] == required_cases,
                "promotion control/screen case coverage differs from the registered rule")
    if expected.get("formal_refs") is not None:
        require(report["formal"] == expected["formal_refs"], "control does not surround gate-bound formal measurements")
    if protocol["purpose"] in {"baseline_qualification", "protocol_diagnostic"}:
        require(protocol["source_hashes"]["baseline"] == protocol["source_hashes"]["candidate"]
                and protocol["binary_hashes"]["baseline"] == protocol["binary_hashes"]["candidate"],
                "baseline qualification must compare the identical source and binary")
        controls(data["formal"][0]["records"], data["formal"][1]["expected_case_ids"])
    return {"passed": True, "protocol_ref": report["protocol_ref"], "registration_ref": report["registration_ref"],
            "stage_windows": windows,
            "aa_before": controls(before[0]["records"], cases), "aa_after": controls(after[0]["records"], cases),
            "drift": drift(before[0]["records"], after[0]["records"], cases)}


def verify_execution(store, reference):
    execution = read(store, reference)
    require(execution.get("exit_status") == 0 and not execution.get("error")
            and execution.get("argv") and number(execution["started_at"]) <= number(execution["finished_at"]),
            "boundary execution failed or incomplete")
    store.verify_artifact(execution["log_ref"])
    return execution


def verify_capture_window(store, capture_manifest_ref, *, window, control_report_ref, role):
    """Replay real execution chronology for one independent capture manifest."""
    store = store if isinstance(store, ReplayCache) else ReplayCache(store)
    require(isinstance(window, list) and len(window) == 2
            and number(window[0]) <= number(window[1]), "profile stage window missing")
    reference = capture_manifest_ref
    manifest = read(store, reference)
    control = read(store, control_report_ref)
    protocol = read(store, control["protocol_ref"])
    raw = read(store, control["formal"]["raw_ref"])
    config = read(store, protocol["phases"]["formal"]["config_ref"])
    require(role in ROLES and manifest["role"] == role
            and manifest["source_hash"] == protocol["source_hashes"][role]
            and manifest["binary_hash"] == protocol["binary_hashes"][role],
            "profile source/binary/role differs from admitted timing")
    cases = [case for case in config["cases"] if case["case_id"] == manifest["case_id"]]
    require(len(cases) == 1 and read(store, manifest["workload_hash"]) == cases[0]["workload"],
            "profile workload differs from its formal timing case")
    if "profile_configs" in protocol:
        expected = read(store, protocol["profile_configs"][role])
        scope = {"case_id": expected["case_id"], "kernels": [expected["kernel"]]}
    else:
        scope = protocol.get("profile_scope", {})
    require(manifest["case_id"] == scope.get("case_id") and manifest["kernel"] in scope.get("kernels", []),
            "profile case/kernel was not preregistered")
    hardware = read(store, manifest["hardware_hash"])
    require(hardware.get("host") == raw["host"]
            and all(str(hardware.get(key)) == str(raw[key]) for key in ("device", "physical_device")),
            "profile hardware differs from admitted timing")
    require(manifest["policy"]["warmups"] == 10 and manifest["policy"]["repeats"] == 5
            and len(manifest["warmup_runs"]) == 10
            and [row["capture_id"] for row in manifest["captures"]]
            == [f"capture-{index:03d}" for index in range(5)], "profile capture inventory differs")
    clock = window[0]

    def execution(ref):
        nonlocal clock
        record = read(store, ref)
        require(record.get("exit_code") == 0 and not record.get("error")
                and clock <= number(record["started_at"]) <= number(record["ended_at"]) <= window[1],
                "profile execution falls outside its registered stage")
        for key in ("stdout_hash", "stderr_hash"):
            store.verify_artifact(record[key])
        clock = record["ended_at"]
        return record

    for row in manifest["warmup_runs"]:
        record = execution(row["log_hash"])
        require(row["argv"] == record["argv"] and row["exit_code"] == record["exit_code"],
                "profile warmup differs from its original execution")
    for row in manifest["captures"]:
        receipt = read(store, row["log_hash"])
        for key in ("capture", "import"):
            if key == "import" and key not in receipt:
                continue
            embedded = receipt[key]
            record = execution(embedded["log_hash"])
            require({key: value for key, value in embedded.items() if key != "log_hash"} == record,
                    "profile capture differs from its original execution")
            if key == "capture":
                require(row["argv"] == record["argv"] and row["exit_code"] == record["exit_code"],
                        "profile capture command differs")
    return {"passed": True, "capture_manifest_ref": capture_manifest_ref}


def verify_profile_window(store, mechanism_report_ref, *, window, control_report_ref):
    """Reject reused captures even when their source-bound machine proof is valid."""
    store = ReplayCache(store)
    mechanism = read(store, mechanism_report_ref)
    manifests = {(role, read(store, metric[role + "_profile_hash"])["capture_manifest_hash"])
                 for metric in mechanism["metrics"] for role in ROLES}
    require(manifests, "profile stage lacks independent captures")
    for role, reference in manifests:
        verify_capture_window(store, reference, window=window, control_report_ref=control_report_ref, role=role)
    return {"passed": True, "capture_manifests": len(manifests)}


def verify_boundary_report(store, boundary_report_ref, *, protocol_ref, expected):
    store = ReplayCache(store)
    protocol = read(store, protocol_ref)
    identity(protocol, expected)
    plan = read(store, protocol["boundary_plan_ref"])
    operator = expected["operator"]
    require(plan.get("schema_version") == 1 and plan.get("operator") == operator and operator in BOUNDARY_SIZES,
            "boundary plan has no frozen operator scope")
    for key in ("generator_ref", "verifier_ref"):
        require(plan[key] in protocol["oracle_files"].values(), "boundary oracle differs from frozen protocol")
        store.verify_artifact(plan[key])
    require(plan["verifier_ref"] == read(store, expected["source_hashes"]["baseline"])["files"].get("scripts/verify_result.py"),
            "boundary verifier differs from the original native oracle")
    cases = plan["cases"]
    wanted = [(dtype, size) for dtype in THRESHOLDS for size in BOUNDARY_SIZES[operator]]
    require([(case["dtype"], case["numel"]) for case in cases] == wanted
            and [case["case_id"] for case in cases] == list(range(101, 101 + len(wanted))),
            "boundary inventory differs from the frozen 42/57 cases")
    for case in cases:
        require(case["shape"] == [case["numel"]] and case.get("input_files"), "boundary shape/input inventory differs")
        special = ["-inf", "inf", "nan", "-0", "0"] if case["numel"] == 65 else []
        require(case.get("special_values", []) == special, "boundary special-value scope differs")
        inputs = {name: checked_path(store, name, ref) for name, ref in case["input_files"].items()}
        if special:
            require(len(inputs) == 1, "special-value boundary requires its exact input")
            data = next(iter(inputs.values())).read_bytes()
            dtype = case["dtype"]
            size = 4 if dtype == "float32" else 2
            require(len(data) == 65 * size, "special-value input size differs")
            values = (list(struct.unpack("<5f", data[:20])) if dtype == "float32" else
                      list(struct.unpack("<5e", data[:10])) if dtype == "float16" else
                      [struct.unpack("<f", b"\x00\x00" + data[i:i+2])[0] for i in range(0, 10, 2)])
            require(values[0] == -math.inf and values[1] == math.inf and math.isnan(values[2])
                    and values[3] == 0 and math.copysign(1, values[3]) == -1 and values[4] == 0
                    and math.copysign(1, values[4]) == 1, "special-value input coverage differs")
    report = read(store, boundary_report_ref)
    identity({**report, "operator": report.get("operator", operator)}, expected)
    window = expected.get("boundary_window")
    if protocol.get("purpose") == "promotion":
        require(isinstance(window, list) and len(window) == 2
                and number(protocol["created_at"]) <= number(window[0]) <= number(window[1]),
                "boundary lacks its preregistered execution window")
    require(report.get("protocol_ref") == protocol_ref and report.get("status") == "passed"
            and report.get("case_ids") == [case["case_id"] for case in cases]
            and report.get("passed_case_ids") == report["case_ids"], "boundary report does not cover frozen plan")
    require([(row["case_id"], row["role"]) for row in report["rows"]]
            == [(case["case_id"], role) for case in cases for role in ROLES], "boundary raw verifier inventory incomplete")
    for row in report["rows"]:
        case = cases[row["case_id"] - 101]
        role = row["role"]
        require(row["source_hash"] == expected["source_hashes"][role]
                and row["binary_hash"] == protocol["binary_hashes"][role], "boundary source/binary differs")
        metadata, result = read(store, row["metadata_ref"]), read(store, row["result_ref"])
        metadata = {**metadata, "attrs": metadata.get("attrs", {key: metadata[key] for key in ("base", "scale", "shift") if key in metadata})}
        for key in ("case_id", "shape", "dtype", "numel", "attrs"):
            require(metadata.get(key, {}) == case.get(key, {}) and result.get(key, {}) == case.get(key, {}),
                    "boundary raw metadata/result scope differs")
        threshold = THRESHOLDS[case["dtype"]]
        require(result.get("threshold") == threshold and result.get("special_values_match") is True
                and result.get("passed") is True and 0 <= number(result["mere"]) < threshold
                and 0 <= number(result["mare"]) < 10 * threshold, "boundary native verifier failed")
        require(metadata.get("input") in case["input_files"], "boundary metadata input differs")
        output = metadata.get("output")
        require(isinstance(output, str) and len(row["output_refs"]) == 1, "boundary output evidence missing")
        output_path = checked_path(store, output, row["output_refs"][0])
        require(output_path.stat().st_size == case["numel"] * (4 if case["dtype"] == "float32" else 2),
                "boundary output byte count differs")
        kernel = verify_execution(store, row["kernel_execution_ref"])
        verifier = verify_execution(store, row["verifier_execution_ref"])
        if window is not None:
            require(window[0] <= number(kernel["started_at"])
                    <= number(verifier["finished_at"]) <= window[1],
                    "boundary execution falls outside its registered stage")
        require(number(kernel["finished_at"]) <= number(verifier["started_at"])
                and output in kernel["argv"] and metadata["input"] in kernel["argv"] and kernel["argv"][0],
                "boundary execution chronology/arguments differ")
        checked_path(store, kernel["argv"][0], row["binary_hash"])
        require(any(Path(token).name == "verify_result.py" and token in protocol["oracle_files"]
                    and protocol["oracle_files"][token] == plan["verifier_ref"] for token in verifier["argv"]),
                "boundary verifier command differs")
        argv = verifier["argv"]
        require(argv.count("--metadata") == 1 and argv.index("--metadata") + 1 < len(argv),
                "boundary verifier metadata argument missing")
        metadata_path = Path(argv[argv.index("--metadata") + 1])
        checked_path(store, metadata_path, row["metadata_ref"])
        checked_path(store, metadata_path.parent / "result.json", row["result_ref"])
        log = Path(store.verify_artifact(verifier["log_ref"])).read_text().splitlines()
        results = [json.loads(line) for line in log if line.startswith("{")]
        require(results == [result], "boundary result differs from original native verifier stdout")
    return {"passed": True, "case_count": len(cases), "protocol_ref": protocol_ref}
