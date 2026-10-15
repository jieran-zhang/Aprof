"""Synthetic CAS receipts test admission integrity, never hardware performance."""
import json
import os
from pathlib import Path
import struct
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "collection/scripts"
SELECTED_RELEASE = Path(os.environ["APROF_SKILL_LIB"])
if not (SELECTED_RELEASE / "skills/ascendc-aprof-profiling/scripts/device_paired_timing.py").is_file():
    pytest.skip("timing admission requires the frozen 0.5.0 or 1.0.0 collector", allow_module_level=True)
sys.path.insert(0, str(SCRIPTS))
import timing_admission as admission


class Store:
    def __init__(self, root):
        self.root = root
        root.mkdir()

    def put(self, value):
        data = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        ref = admission.digest(data)
        (self.root / ref[7:]).write_bytes(data)
        return ref

    def verify_artifact(self, ref):
        path = self.root / ref[7:]
        assert admission.digest(path.read_bytes()) == ref
        return path


def fixture(tmp_path, *, fault=None):
    store = Store(tmp_path / "cas")
    collector = admission._collector()
    missing = tmp_path / "archived-only"
    oracle_path = str(missing / "verify_result.py")
    generator_path = str(missing / "gen_data.py")
    python_path = str(missing / "python")
    oracle_files = {oracle_path: store.put(b"frozen native verifier"), generator_path: store.put(b"frozen generator"),
                    python_path: store.put(b"frozen interpreter")}
    binaries = {role: store.put(("test only binary " + role).encode()) for role in admission.ROLES}
    inventories = {role: {"kernel.asc": store.put(("test only source " + role).encode()),
                         "scripts/verify_result.py": oracle_files[oracle_path]} for role in admission.ROLES}
    sources = {role: store.put({"schema_version": "1.0.0", "files": files}) for role, files in inventories.items()}
    expected = dict(run_id="independent-test", candidate_id="test-only", operator="exp", source_hashes=sources, purpose="promotion")
    inputs, phase_values = {}, {}
    runtime = Path(collector.v1.runtime_gates.__file__).parent
    runtime_files = {path.relative_to(runtime).as_posix(): admission.digest(path.read_bytes()) for path in sorted(runtime.rglob("*.py"))}
    dependencies = {"frozen_collector": admission.digest(collector.V1_PATH.read_bytes()),
        "device_timer_v2.h": admission.digest(collector.HEADER.read_bytes()),
        "profile_capture.py": admission.digest((collector.v1.SCRIPTS / "profile_capture.py").read_bytes()),
        "runtime_source_files": runtime_files, "runtime_source_hash": admission.content_hash(runtime_files)}
    for phase_index, phase in enumerate(("aa_before", "screen", "formal", "aa_after")):
        count = 6 if phase == "screen" else 30
        case_ids = list(range(1, 21)) if phase == "formal" else admission.RULE_CONTROL_CASES["exp"]
        config = dict(schema_version="2.0.0", operator="exp", epochs=2, prime_repeat=100, repeat=100, warmup=10,
                      pairs=count, mode="explore" if phase == "screen" else "formal", expected_case_ids=case_ids,
                      device=0, physical_device=0, timeout_seconds=180, cases=[])
        for role in admission.ROLES:
            source_role = "baseline" if phase.startswith("aa_") else role
            config[role] = {"binary": str(missing / source_role / "binary"), "cwd": str(missing / source_role),
                            "source_dir": str(missing / source_role)}
        raw = dict(schema_version="2.0.0", measurement_protocol=collector.PROTOCOL, operator="exp", epochs=2,
                   prime_repeat=100, repeat=100, warmup=10, pairs=count, mode=config["mode"], case_ids=case_ids,
                   device=0, physical_device=0, unit="ns", source="acl_event", complete=True, host="synthetic-test-host",
                   environment={"APROF_TIMING_INTERACTIVE": "1", "APROF_TIMING_V2": "1", "APROF_WARMUP": "10",
                                "APROF_REPEAT": "100", "APROF_PRIME_REPEAT": "100", "APROF_CAPTURE_REPLAY": None},
                   timing_scope="complete_operator_device_event_interval", producer_hash=admission.digest(Path(collector.__file__).read_bytes()),
                   producer_dependencies=dependencies, records=[], case_executions=[], case_identities={})
        start = 1000 + phase_index * 10000
        tick = start * 1000000
        for ci, case_id in enumerate(case_ids):
            input_path = str(missing / f"case-{case_id}-input")
            inputs[input_path] = store.put(("prepared" + str(case_id)).encode())
            case = {"case_id": case_id, "workload": {"case_id": case_id}, "prepared_files": [input_path], "epochs": []}
            case_start = start + ci * 100
            execution = {"case_id": case_id, "workload": case["workload"], "exit_status": 0,
                         "started_at": case_start, "finished_at": case_start + 90, "epochs": []}
            identities = []
            for epoch in (0, 1):
                epoch_start = case_start + epoch * 40
                startup = list(admission.ROLES if epoch == 0 else reversed(admission.ROLES))
                state = {"epoch": epoch, "startup_order": startup, "started_at": epoch_start, "finished_at": epoch_start + 35,
                         "started_monotonic_ns": tick, "commands": {}, "ready_receipts": {}, "prime_receipts": [],
                         "verifications": {}, "output_hashes": {}, "exit_status": 0}
                tick += 1
                ident = {"workload_hash": admission.content_hash(case["workload"]), "prepared_files": {input_path: inputs[input_path]}}
                epoch_case = {}
                for role in startup:
                    source_role = "baseline" if phase.startswith("aa_") else role
                    pid = phase_index * 10000 + ci * 10 + epoch * 2 + admission.ROLES.index(role) + 1
                    output = str(missing / f"{phase}-{case_id}-{epoch}-{role}-output")
                    argv = [config[role]["binary"], input_path, output]
                    verify = [python_path, oracle_path, output]
                    epoch_case[role] = {"command": argv, "verify_command": verify, "output_files": [output], "launches_per_operator": 1}
                    state["commands"][role] = {"argv": argv, "cwd": config[role]["cwd"], "pid": pid, "exit_status": 0,
                        "started_at": epoch_start + 1, "finished_at": epoch_start + 25}
                    state["ready_receipts"][role] = {"pid": pid, "wait_started_monotonic_ns": tick, "ready_monotonic_ns": tick + 1}
                    tick += 2
                    state["verifications"][role] = {"argv": verify, "cwd": config[role]["cwd"], "exit_status": 0,
                        "started_at": epoch_start + 26, "finished_at": epoch_start + 30,
                        "log_path": str(missing / f"{phase}-{case_id}-{epoch}-{role}-verify.log"), "log_hash": store.put(b"verified")}
                    state["output_hashes"][output] = store.put(b"correct test output")
                    ident[role] = {"binary_hash": binaries[source_role], "source_files": inventories[source_role],
                                  "source_hash": admission.content_hash(inventories[source_role]),
                                  "verifier_files": {path: oracle_files[path] for path in (python_path, oracle_path)}}
                counters = dict.fromkeys(admission.ROLES, 0)
                for role in [startup[0], startup[1], startup[1], startup[0]]:
                    ack = {"schema_version": "2.0.0", "operator": "exp", "device": 0, "prime_index": counters[role],
                           "repeat": 100, "launches_per_operator": 1}
                    state["prime_receipts"].append({"role": role, "pid": state["commands"][role]["pid"],
                        "request_monotonic_ns": tick, "response_monotonic_ns": tick + 1, "acknowledgement": ack})
                    tick += 2
                    counters[role] += 1
                selected = []
                for local in range(count // 2):
                    index = epoch * (count // 2) + local
                    order = list(admission.ROLES if index % 2 == 0 else reversed(admission.ROLES))
                    row = {"case_id": case_id, "epoch": epoch, "local_round": local, "round": index,
                           "order": order, "device": 0, "sample_receipts": {}}
                    for role in order:
                        elapsed = 100 if phase.startswith("aa_") or role == "baseline" else 80
                        if fault == "role_bias" and phase == "aa_after" and role == "candidate":
                            elapsed = 103
                        if fault == "drift" and phase == "aa_after":
                            elapsed = 103
                        if fault == "epoch_bias" and phase == "aa_after" and role == "candidate":
                            elapsed = 103.5 if epoch == 0 else 96.5
                        row[role] = {"schema_version": "1.0.0", "operator": "exp", "device": 0, "source": "acl_event",
                            "unit": "ns", "sample_index": local, "warmup": 10, "repeat": 100, "launches_per_operator": 1, "elapsed_ns": elapsed}
                        row["sample_receipts"][role] = {"pid": state["commands"][role]["pid"],
                            "request_monotonic_ns": tick, "response_monotonic_ns": tick + 1}
                        tick += 2
                    selected.append(row)
                raw["records"] += selected
                for role in admission.ROLES:
                    lines = ["APROF_TIMING_READY"]
                    lines += ["APROF_PRIME_JSON:" + json.dumps(item["acknowledgement"]) for item in state["prime_receipts"] if item["role"] == role]
                    lines += ["APROF_TIMING_JSON:" + json.dumps(item[role]) for item in selected]
                    state["commands"][role].update(log_path=str(missing / f"{phase}-{case_id}-{epoch}-{role}.log"),
                                                   log_hash=store.put(("\n".join(lines) + "\n").encode()))
                state.update(identity_before=ident, identity_after=ident, finished_monotonic_ns=tick)
                tick += 1
                identities.append(ident)
                execution["epochs"].append(state)
                case["epochs"].append(epoch_case)
            config["cases"].append(case)
            raw["case_executions"].append(execution)
            raw["case_identities"][str(case_id)] = {"epochs": identities}
        raw["config_hash"] = admission.content_hash(config)
        report = collector.v1.summarize(raw, config)
        report.update(schema_version="2.0.0", measurement_protocol=collector.PROTOCOL)
        phase_values[phase] = {"raw_ref": store.put(raw), "config_ref": store.put(config), "report_ref": store.put(report)}
    boundary_plan, boundary_rows = boundary_fixture(store, missing, expected, binaries, oracle_files)
    protocol = {"schema_version": 1, **{k: expected[k] for k in ("run_id", "candidate_id", "operator", "source_hashes")},
        "purpose": "promotion", "measurement_policy": {"repeat": 100}, "binary_hashes": binaries,
        "collector_ref": store.put(Path(collector.__file__).read_bytes()), "created_at": 1,
        "input_inventory_ref": store.put(inputs), "oracle_files": oracle_files, "boundary_plan_ref": store.put(boundary_plan),
        "phases": {phase: {"config_ref": values["config_ref"]} for phase, values in phase_values.items()}, "history_refs": [store.put({"old_failed_attempt": True})]}
    protocol_ref = store.put(protocol)
    stages = ["correctness", "boundary", "aa_before", "screen", "formal", "aa_after", "profile"]
    registration = {"schema_version": 1, "protocol_ref": protocol_ref, "run_id": expected["run_id"],
        "candidate_id": expected["candidate_id"], "created_at": 2, "max_attempts": 1, "stop_on_failure": True,
        "resampling": "none", "stages": stages}
    previous = registration_ref = store.put(registration)
    expected["registration_ref"] = registration_ref
    expected["boundary_window"] = [101, 200]
    events = []
    intervals = [(10, 100), (101, 200), (900, 4000), (10900, 14000), (20900, 24000), (30900, 34000), (35000, 36000)]
    for stage, window in zip(stages, intervals, strict=True):
        for state, timestamp in zip(("started", "completed"), window, strict=True):
            event = {"sequence": len(events), "previous_ref": previous, "registration_ref": registration_ref,
                "stage": stage, "state": state, "at": timestamp, "evidence_refs": [] if state == "started" else
                list(phase_values[stage].values()) if stage in phase_values else [store.put({"stage": stage})]}
            if state == "completed":
                event["exit_status"] = 0
            previous = store.put(event)
            events.append(previous)
    roster = {"schema_version": 1, "registration_ref": registration_ref, "events": events}
    report = {"schema_version": 1, **{k: expected[k] for k in ("run_id", "candidate_id", "operator", "source_hashes")},
              "protocol_ref": protocol_ref, "registration_ref": registration_ref, "attempt_roster_ref": store.put(roster), **phase_values}
    boundary = {"schema_version": 1, **{k: expected[k] for k in ("run_id", "candidate_id", "operator", "source_hashes")},
                "protocol_ref": protocol_ref, "status": "passed", "case_ids": [case["case_id"] for case in boundary_plan["cases"]],
                "passed_case_ids": [case["case_id"] for case in boundary_plan["cases"]], "rows": boundary_rows}
    return store, report, expected, boundary


def boundary_fixture(store, missing, expected, binaries, oracle_files):
    cases, rows = [], []
    operator = expected["operator"]
    for dtype, threshold in admission.THRESHOLDS.items():
        for size in admission.BOUNDARY_SIZES[operator]:
            case_id = 101 + len(cases)
            special = ["-inf", "inf", "nan", "-0", "0"] if size == 65 else []
            values = [-float("inf"), float("inf"), float("nan"), -0., 0.] + [0.] * 60 if special else [0.] * size
            if dtype == "bfloat16":
                data = b"".join(struct.pack("<f", value)[2:] for value in values)
            else:
                data = struct.pack("<" + str(size) + ("f" if dtype == "float32" else "e"), *values)
            input_path = str(missing / f"boundary-{case_id}-input")
            attrs = {"base": -1., "scale": 1., "shift": 0.} if operator == "exp" else {}
            case = {"case_id": case_id, "shape": [size], "numel": size, "dtype": dtype, "attrs": attrs,
                    "input_files": {input_path: store.put(data)}, "special_values": special}
            cases.append(case)
            for role in admission.ROLES:
                output = str(missing / f"boundary-{case_id}-{role}-output")
                metadata = {key: case[key] for key in ("case_id", "shape", "numel", "dtype")}
                metadata.update(input=input_path, output=output, **attrs)
                native = {key: case[key] for key in ("case_id", "shape", "numel", "dtype", "attrs")}
                native.update(mere=0., mare=0., threshold=threshold, special_values_match=True, passed=True)
                execution = {"argv": [str(missing / role / "binary"), input_path, output],
                             "started_at": 102, "finished_at": 103, "exit_status": 0, "log_ref": store.put(b"ran")}
                verification = {"argv": [str(missing / "python"), str(missing / "verify_result.py"),
                                         "--metadata", str(missing / f"boundary-{case_id}-{role}-metadata.json")],
                                "started_at": 104, "finished_at": 105, "exit_status": 0,
                                "log_ref": store.put((json.dumps(native) + "\n").encode())}
                rows.append({"case_id": case_id, "role": role, "source_hash": expected["source_hashes"][role],
                    "binary_hash": binaries[role], "metadata_ref": store.put(metadata), "result_ref": store.put(native),
                    "kernel_execution_ref": store.put(execution), "verifier_execution_ref": store.put(verification),
                    "output_refs": [store.put(data)]})
    return {"schema_version": 1, "operator": operator, "generator_ref": oracle_files[str(missing / "gen_data.py")],
            "verifier_ref": oracle_files[str(missing / "verify_result.py")], "cases": cases}, rows


def test_complete_synthetic_admission_replays(tmp_path):
    store, report, expected, boundary = fixture(tmp_path)
    result = admission.verify_timing_admission(store, store.put(report), expected=expected)
    assert result["passed"] is True
    assert admission.verify_boundary_report(store, store.put(boundary), protocol_ref=report["protocol_ref"], expected=expected)["case_count"] == 42


@pytest.mark.parametrize("fault,match", [("role_bias", "role bias"), ("drift", "session drift"), ("epoch_bias", "role bias")])
def test_stable_formal_report_does_not_override_failed_aa(tmp_path, fault, match):
    store, report, expected, _ = fixture(tmp_path, fault=fault)
    assert admission.read(store, report["aa_after"]["report_ref"])["stable"] is True
    with pytest.raises(ValueError, match=match):
        admission.verify_timing_admission(store, store.put(report), expected=expected)


@pytest.mark.parametrize("fault", ["missing_after", "roster_truncated", "roster_reordered", "different_anchor", "wrong_formal", "raw_stdout", "reused_pid", "missing_epoch_sample", "changed_prime", "different_host"])
def test_forged_or_incomplete_control_evidence_is_rejected(tmp_path, fault):
    store, report, expected, _ = fixture(tmp_path)
    if fault == "missing_after":
        del report["aa_after"]
    elif fault.startswith("roster_"):
        roster = admission.read(store, report["attempt_roster_ref"])
        if fault == "roster_truncated":
            roster["events"] = roster["events"][2:]
        else:
            roster["events"][0], roster["events"][1] = roster["events"][1], roster["events"][0]
        report["attempt_roster_ref"] = store.put(roster)
    elif fault == "different_anchor":
        expected["registration_ref"] = store.put({"fake": True})
    elif fault == "wrong_formal":
        expected["formal_refs"] = report["aa_before"]
    else:
        raw = admission.read(store, report["aa_after"]["raw_ref"])
        if fault == "raw_stdout":
            raw["case_executions"][0]["epochs"][0]["commands"]["baseline"]["log_hash"] = store.put(b"forged empty stdout")
        elif fault == "reused_pid":
            raw["case_executions"][0]["epochs"][1]["commands"]["baseline"]["pid"] = raw["case_executions"][0]["epochs"][0]["commands"]["baseline"]["pid"]
        elif fault == "changed_prime":
            raw["case_executions"][0]["epochs"][0]["prime_receipts"][0]["acknowledgement"]["repeat"] = 99
        elif fault == "different_host":
            raw["host"] = "different-hardware-host"
        else:
            raw["records"].pop()
        old = report["aa_after"]["raw_ref"]
        report["aa_after"]["raw_ref"] = store.put(raw)
        # Keep the ledger honestly bound to the forged attachment so replay,
        # not merely a stale attachment checksum, must reject it.
        rechain(store, report, old, report["aa_after"]["raw_ref"])
    with pytest.raises((ValueError, KeyError)):
        admission.verify_timing_admission(store, store.put(report), expected=expected)


def rechain(store, report, old, new):
    roster = admission.read(store, report["attempt_roster_ref"])
    previous = report["registration_ref"]
    for index, ref in enumerate(roster["events"]):
        event = admission.read(store, ref)
        event["previous_ref"] = previous
        event["evidence_refs"] = [new if value == old else value for value in event["evidence_refs"]]
        previous = store.put(event)
        roster["events"][index] = previous
    report["attempt_roster_ref"] = store.put(roster)


@pytest.mark.parametrize("fault", ["omitted_case", "summary_only", "native_failure", "wrong_threshold", "wrong_binary", "different_stdout", "outside_stage"])
def test_boundary_replays_native_results_and_exact_inventory(tmp_path, fault):
    store, report, expected, boundary = fixture(tmp_path)
    if fault == "omitted_case":
        boundary["rows"] = boundary["rows"][:-2]
    elif fault == "summary_only":
        boundary["rows"] = []
    elif fault == "wrong_binary":
        boundary["rows"][0]["binary_hash"] = boundary["rows"][1]["binary_hash"]
    elif fault == "different_stdout":
        verifier = admission.read(store, boundary["rows"][0]["verifier_execution_ref"])
        verifier["log_ref"] = store.put(b'{"passed": false}\n')
        boundary["rows"][0]["verifier_execution_ref"] = store.put(verifier)
    elif fault == "outside_stage":
        expected["boundary_window"] = [106, 200]
    else:
        native = admission.read(store, boundary["rows"][0]["result_ref"])
        native["mere" if fault == "native_failure" else "threshold"] = 1.
        boundary["rows"][0]["result_ref"] = store.put(native)
    with pytest.raises(ValueError):
        admission.verify_boundary_report(store, store.put(boundary), protocol_ref=report["protocol_ref"], expected=expected)


@pytest.mark.parametrize("fault", [None, "profile_configs", "old_capture", "forged_embedded_time", "missing_capture", "old_warmup",
                                   "other_binary", "other_source", "other_host", "other_device", "other_workload",
                                   "other_role", "unregistered_kernel", "unregistered_case"])
def test_profile_window_uses_original_execution_timestamps(tmp_path, fault):
    store = Store(tmp_path / "cas")
    manifest = {"policy": {"warmups": 10, "repeats": 5}, "warmup_runs": [], "captures": []}
    for index in range(15):
        record = {"argv": ["frozen-binary"], "cwd": "/archived", "started_at": 10 + index * 2,
                  "ended_at": 11 + index * 2, "exit_code": 0, "error": None,
                  "stdout_hash": store.put(b"actual stdout"), "stderr_hash": store.put(b"")}
        if fault == "old_capture" and index == 10 or fault == "old_warmup" and index == 0:
            record.update(started_at=0, ended_at=1)
        reference = store.put(record)
        if index < 10:
            manifest["warmup_runs"].append({"argv": record["argv"], "exit_code": 0, "log_hash": reference})
        else:
            embedded = {**record, "log_hash": reference}
            if fault == "forged_embedded_time" and index == 10:
                embedded["started_at"] += .1
            receipt = store.put({"capture": embedded})
            manifest["captures"].append({"capture_id": f"capture-{index - 10:03d}", "argv": record["argv"],
                                        "exit_code": 0, "log_hash": receipt})
    if fault == "missing_capture":
        manifest["captures"].pop()
    workload = {"case_id": 1, "shape": [8], "dtype": "float32"}
    sources = {role: store.put({"synthetic_source": role}) for role in admission.ROLES}
    binaries = {role: store.put((role + " binary").encode()) for role in admission.ROLES}
    hardware = {"host": "qualified-host", "device": "0", "physical_device": "0"}
    profiles = {}
    for role in admission.ROLES:
        scoped = {**manifest, "role": role, "case_id": 1, "kernel": "declared_kernel",
                  "source_hash": sources[role], "binary_hash": binaries[role],
                  "workload_hash": store.put(workload), "hardware_hash": store.put(hardware)}
        if fault == "other_binary":
            scoped["binary_hash"] = store.put(b"different executable")
        elif fault == "other_source":
            scoped["source_hash"] = store.put({"other_source": True})
        elif fault in {"other_host", "other_device"}:
            scoped["hardware_hash"] = store.put({**hardware, "host" if fault == "other_host" else "device": "different"})
        elif fault == "other_workload":
            scoped["workload_hash"] = store.put({**workload, "shape": [16]})
        elif fault == "other_role":
            scoped["role"] = "candidate" if role == "baseline" else "baseline"
        elif fault == "unregistered_kernel":
            scoped["kernel"] = "posthoc_kernel"
        profiles[role + "_profile_hash"] = store.put({"capture_manifest_hash": store.put(scoped)})
    protocol = {"source_hashes": sources, "binary_hashes": binaries,
        "profile_scope": {"case_id": 2 if fault == "unregistered_case" else 1, "kernels": ["declared_kernel"]},
        "phases": {"formal": {"config_ref": store.put({"cases": [{"case_id": 1, "workload": workload}]})}}}
    if fault == "profile_configs":
        del protocol["profile_scope"]
        protocol["profile_configs"] = {role: store.put({"case_id": 1, "kernel": "declared_kernel"}) for role in admission.ROLES}
    control = store.put({"protocol_ref": store.put(protocol), "formal": {
        "raw_ref": store.put({"host": "qualified-host", "device": 0, "physical_device": 0})}})
    mechanism = store.put({"metrics": [profiles]})
    if fault in (None, "profile_configs"):
        assert admission.verify_profile_window(store, mechanism, window=[10, 50], control_report_ref=control)["passed"]
    else:
        with pytest.raises(ValueError):
            admission.verify_profile_window(store, mechanism, window=[10, 50], control_report_ref=control)
