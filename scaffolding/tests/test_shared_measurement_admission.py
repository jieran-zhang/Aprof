"""Synthetic wire/CAS regressions; these fixtures do not qualify real hardware."""
from copy import deepcopy
import json
from pathlib import Path
import struct

import pytest
from aprof_runtime import __version__

if __version__ != "0.2.2":
    pytest.skip("select graph-base/0.5.1", allow_module_level=True)

from aprof_runtime.errors import ContractError
from aprof_runtime.contracts import GateEvidence
from aprof_runtime.measurement_admission import (
    PHASES, PRODUCER_FILES, PROTOCOL, ROLES, replay_measurement_admission, summarize_shared_raw,
    verify_measurement_admission,
)
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import register_json_artifact

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / "skill-libs/graph-base/0.5.1"


def event_time(ns, repeat=100):
    milliseconds = struct.unpack("f", struct.pack("f", ns * repeat / 1e6))[0]
    return milliseconds, milliseconds * 1e6 / repeat


def set_sample(sample, ns, repeat=100):
    sample["elapsed_ms"], sample["elapsed_ns"] = event_time(ns, repeat)


def wire(config, cycle, repeat=500):
    common = {"schema_version": "1.0.0", "protocol": PROTOCOL, "operator": config["operator"],
        "cycle_index": cycle, "pid": 100 + cycle, "device": 0, "context_address": "1000", "stream_address": "2000",
        "warmup": 10, "repeat": repeat, "prime_repeat": 100, "execution_mode": "direct_enqueue",
        "mode": "confirmation", "warmup_role_counts": {"baseline": 10, "candidate": 10},
        "launches_per_operator": {role: 1 for role in ROLES}, "role_symbols": {role: role + "_callback" for role in ROLES},
        "buffers": {"inputs": [{"name": "input", "address": "10000", "bytes": 4096}],
                    "outputs": [{"name": "output", "address": "20000", "bytes": 4096}], "workspaces": []}}
    base = (cycle + 1) * 10_000_000
    ready = {**deepcopy(common), "kind": "ready", "warmup_started_monotonic_ns": base,
             "warmup_finished_monotonic_ns": base + 100, "cpu_affinity": [0, 1]}
    events = []
    for index in range(19):
        start, finish = base + (index + 1) * 200_000, base + (index + 2) * 200_000 - 1
        message = {**deepcopy(common), "command_index": index}
        if index == 18:
            message.update(kind="complete", input_bytes_unchanged=True, pairs_per_phase=5,
                untimed_verifications=[{"role": role, "implementation": role, "scope": "untimed_callback_verification",
                    "started_monotonic_ns": start + 10 + ri * 60_000,
                    "finished_monotonic_ns": start + 50_000 + ri * 60_000} for ri, role in enumerate(ROLES)])
        else:
            phase, local = PHASES[index // 6], index % 6
            message.update(phase=phase, started_monotonic_ns=start + 1, finished_monotonic_ns=finish - 1)
            if local == 0:
                order = list(ROLES if cycle % 2 == 0 else reversed(ROLES))
                message.update(kind="prime", prime_order=[order[0], order[1], order[1], order[0]])
            else:
                pair = local - 1
                order = list(ROLES if (cycle + pair) % 2 == 0 else reversed(ROLES))
                message.update(kind="pair", pair_index=pair, order=order)
                for position, role in enumerate(order):
                    sample = {"implementation": role if phase == "formal" else "baseline", "launches_per_operator": 1,
                              "started_monotonic_ns": start + 10 + position * 60_000,
                              "finished_monotonic_ns": start + 50_000 + position * 60_000, "cpu_before": 0, "cpu_after": 0}
                    set_sample(sample, 80 if phase == "formal" and role == "candidate" else 100, repeat)
                    message[role] = sample
        events.append({"request_monotonic_ns": start, "response_monotonic_ns": finish, "message": message})
    return ready, events


def pilot_wire(config):
    ready, _ = wire(config, 0, repeat=100)
    ready.update(pid=900, mode="pilot", warmup_role_counts={"baseline": 20, "candidate": 0})
    common = {key: deepcopy(value) for key, value in ready.items()
              if key not in ("kind", "warmup_started_monotonic_ns", "warmup_finished_monotonic_ns", "cpu_affinity")}
    events = []
    for index in range(5):
        start, finish = 10_200_000 + index * 200_000, 10_399_999 + index * 200_000
        message = {**deepcopy(common), "command_index": index}
        if index == 0:
            message.update(kind="prime", phase="pilot", prime_order=["baseline"] * 4,
                started_monotonic_ns=start + 1, finished_monotonic_ns=finish - 1)
        elif index <= 3:
            sample = {"implementation": "baseline", "launches_per_operator": 1,
                "started_monotonic_ns": start + 10, "finished_monotonic_ns": finish - 10,
                "cpu_before": 0, "cpu_after": 0}
            set_sample(sample, 100_000)
            message.update(kind="pilot_sample", phase="pilot", sample_index=index - 1, baseline=sample)
        else:
            message.update(kind="complete", input_bytes_unchanged=True, pilot_samples=3,
                untimed_verifications=[{"role": role, "implementation": role,
                    "scope": "untimed_callback_verification",
                    "started_monotonic_ns": start + 10 + ri * 60_000,
                    "finished_monotonic_ns": start + 50_000 + ri * 60_000}
                    for ri, role in enumerate(ROLES)])
        events.append({"request_monotonic_ns": start, "response_monotonic_ns": finish, "message": message})
    return ready, events


@pytest.fixture
def draft():
    config = {"schema_version": "1.0.0", "operator": "synthetic_exp", "run_id": "run", "session_id": "session",
        "candidate_id": "candidate", "device": 0, "physical_device": 0, "expected_case_ids": [1],
        "roles": {role: {"source_dir": "/synthetic/" + role, "symbol": role + "_callback", "launches_per_operator": 1} for role in ROLES},
        "build": {"source_dir": "/synthetic/build", "binary": "/synthetic/build/kernel", "receipt_files": ["/synthetic/build/build.json"]},
        "cases": [{"case_id": 1, "workload": {"shape": [1024], "dtype": "float32"},
            "prepared_files": ["/synthetic/input.bin", "/synthetic/golden.bin"],
            "command": ["/synthetic/build/kernel", "--input", "/synthetic/input.bin", "--output-dir", "{cycle_dir}"],
            "verify_commands": {role: ["/synthetic/python", "/synthetic/verify.py",
                "--output", "{cycle_dir}/" + role + ".bin",
                "--result", "{cycle_dir}/" + role + "-result.json"] for role in ROLES},
            "output_files": {role: ["{cycle_dir}/" + role + ".bin"] for role in ROLES}}]}
    raw = {"protocol": PROTOCOL, "complete": True, "started_at": 4.0, "finished_at": 23.0, "sessions": [],
           "host": "synthetic-host", "environment": {}, "repeat_by_case": {"1": 500}}
    for cycle in range(6):
        ready, events = wire(config, cycle)
        start = 5.0 + cycle * 3
        directory = f"/synthetic/results/case-01-cycle-{cycle}"
        raw["sessions"].append({"case_id": 1, "mode": "confirmation", "cycle": cycle, "cycle_dir": directory,
            "started_at": start, "finished_at": start + 2, "ready": ready, "events": events,
            "execution": {"pid": ready["pid"], "argv": [value.replace("{cycle_dir}", directory) for value in config["cases"][0]["command"]],
                "cwd": config["build"]["source_dir"], "started_at": start + .1, "finished_at": start + 1,
                "environment": {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(cycle),
                    "APROF_SHARED_MODE": "confirmation", "APROF_SHARED_REPEAT": "500"},
                "exit_status": 0, "log_path": directory + "/stdout.log"}})
    return raw, config


def test_summary_recomputes_projection_and_controls(draft):
    raw, config = draft
    report = summarize_shared_raw(raw, config)
    assert report["stable"] is True
    assert len(report["gate_projection"]["baseline_samples_ns"]) == 30
    assert report["speedup"] == pytest.approx(1.25)
    assert len(report["controls"][0]["cycles"]) == 6
    assert report["controls"][0]["overall"]["aa_before"]["role_bias"] == 0
    assert report["controls"][0]["overall"]["formal"]["role_bias"] > .02


def test_summary_uses_each_case_frozen_repeat_without_pilot_samples(draft):
    raw, config = draft
    second_case = deepcopy(config["cases"][0])
    second_case["case_id"] = 2
    config["expected_case_ids"].append(2)
    config["cases"].append(second_case)
    raw["repeat_by_case"]["2"] = 100
    for original in list(raw["sessions"]):
        session = deepcopy(original)
        session["case_id"] = 2
        session["ready"]["repeat"] = 100
        for event in session["events"]:
            message = event["message"]
            message["repeat"] = 100
            if message["kind"] == "pair":
                for role in ROLES:
                    sample = message[role]
                    sample["elapsed_ms"], sample["elapsed_ns"] = event_time(
                        80 if message["phase"] == "formal" and role == "candidate" else 100)
        raw["sessions"].append(session)
    report = summarize_shared_raw(raw, config)
    assert report["stable"] is True
    assert len(report["per_case"]) == 2
    assert len(report["gate_projection"]["baseline_samples_ns"]) == 30
    assert report["per_case"][0]["baseline_median_ns"] == pytest.approx(
        report["per_case"][1]["baseline_median_ns"], rel=1e-6)


@pytest.mark.parametrize("change", ["incomplete", "missing_cycle", "duplicate_cycle", "pair_order", "callback", "buffer", "units", "input_changed", "duplicate_pair", "missing_prime", "nan"])
def test_malformed_raw_returns_failed_summary_without_projection(draft, change):
    raw, config = draft
    if change == "incomplete": raw["complete"] = False
    elif change == "missing_cycle": raw["sessions"].pop()
    elif change == "duplicate_cycle": raw["sessions"][1] = deepcopy(raw["sessions"][0])
    elif change == "pair_order": raw["sessions"][0]["events"][1]["message"]["order"].reverse()
    elif change == "callback": raw["sessions"][0]["events"][1]["message"]["candidate"]["implementation"] = "candidate"
    elif change == "buffer": raw["sessions"][0]["events"][1]["message"]["buffers"]["outputs"][0]["address"] = "99999"
    elif change == "units": raw["sessions"][0]["events"][1]["message"]["baseline"]["elapsed_ns"] *= 1000
    elif change == "input_changed": raw["sessions"][0]["events"][-1]["message"]["input_bytes_unchanged"] = False
    elif change == "duplicate_pair": raw["sessions"][0]["events"][2] = deepcopy(raw["sessions"][0]["events"][1])
    elif change == "missing_prime": raw["sessions"][0]["events"].pop(0)
    elif change == "nan": raw["sessions"][0]["events"][1]["message"]["baseline"]["elapsed_ms"] = float("nan")
    report = summarize_shared_raw(raw, config)
    assert report["stable"] is False and report["reasons"]
    assert report["gate_projection"] == {"baseline_samples_ns": [], "candidate_samples_ns": [], "heldout_regressions": []}


@pytest.mark.parametrize("failure", ["bias", "drift", "cv"])
def test_global_aggregation_cannot_hide_cycle_control_failure(draft, failure):
    raw, config = draft
    session = raw["sessions"][0]
    for event in session["events"]:
        message = event["message"]
        if message["kind"] != "pair": continue
        if failure == "bias" and message["phase"] == "aa_before": set_sample(message["candidate"], 103, 500)
        if failure == "drift" and message["phase"] == "aa_after":
            for role in ROLES: set_sample(message[role], 103, 500)
        if failure == "cv" and message["phase"] == "aa_before" and message["pair_index"] == 0:
            for role in ROLES: set_sample(message[role], 114, 500)
    report = summarize_shared_raw(raw, config)
    assert not report["stable"]
    assert any("cycle 0" in reason for reason in report["reasons"])


@pytest.fixture
def archive(tmp_path, draft):
    raw, config = draft
    with EpisodeStore(tmp_path / "synthetic.sqlite") as store:
        serial = 0
        def blob(text):
            nonlocal serial
            serial += 1
            path = tmp_path / f"artifact-{serial}"
            path.write_text(text)
            return store.register_artifact(path)
        def value(item): return register_json_artifact(store, item)
        source_files = {"host.cpp": blob("synthetic source, never a hardware receipt"),
                        "device_shared_timing.h": store.register_artifact(RELEASE / "skills/ascendc-aprof-profiling/assets/device_shared_timing.h")}
        source_ref = value({"schema_version": "1.0.0", "files": source_files})
        files = {path: blob("synthetic " + path) for path in [config["build"]["binary"], *config["build"]["receipt_files"],
                  *config["cases"][0]["prepared_files"], "/synthetic/python", "/synthetic/verify.py"]}
        producers = {path: store.register_artifact(RELEASE / path) for path in PRODUCER_FILES}
        inventory = {"files": files, "sources": {role: source_files for role in ROLES}, "build_sources": source_files, "producer_files": producers}
        identity = {"source_hashes": {role: source_ref for role in ROLES},
            "build": {"source_ref": source_ref, "binary_ref": files[config["build"]["binary"]],
                      "receipt_refs": {path: files[path] for path in config["build"]["receipt_files"]}},
            "cases": {"1": {"workload_ref": value(config["cases"][0]["workload"]),
                "prepared_files": {path: files[path] for path in config["cases"][0]["prepared_files"]},
                "verifier_files": {path: files[path] for path in ("/synthetic/python", "/synthetic/verify.py")}}}}
        config_ref = value(config)
        probe = {"argv": ["/synthetic/npu-smi", "info", "-t", "board", "-i", "0", "-c", "0"],
                 "cwd": "/synthetic", "started_at": .5, "ended_at": 1.0, "exit_code": 0, "error": None,
                 "stdout_hash": blob("Synthetic board fixture\nChip Name : 9392\n"), "stderr_hash": blob("")}
        probe["log_hash"] = value(probe)
        hardware = {"host": raw["host"], "physical_device": 0, "probe": probe,
                    "npu_smi_ref": blob("synthetic executable"), "cann_home": "/synthetic/cann",
                    "cann_install_info_ref": blob("version=9.0.0\n")}
        pilot_ready, pilot_events = pilot_wire(config)
        pilot_dir = "/synthetic/results/case-01-pilot"
        pilot = {"case_id": 1, "mode": "pilot", "cycle": 0, "cycle_dir": pilot_dir,
            "started_at": 1.2, "finished_at": 3.2, "ready": pilot_ready, "events": pilot_events,
            "execution": {"pid": 900, "argv": [value.replace("{cycle_dir}", pilot_dir) for value in config["cases"][0]["command"]],
                "cwd": config["build"]["source_dir"], "started_at": 1.3, "finished_at": 2.2,
                "environment": {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": "0",
                    "APROF_SHARED_MODE": "pilot", "APROF_SHARED_REPEAT": "100"},
                "exit_status": 0, "log_path": pilot_dir + "/stdout.log"}}
        calibration = {"schema_version": "1.0.0", "protocol": PROTOCOL, "config_ref": config_ref,
            "started_at": 1.1, "finished_at": 3.3, "host": raw["host"],
            "cases": [{"case_id": 1, "repeat": 500, "median_ms": 10.0, "pilot": pilot}]}
        all_runs = [pilot, *raw["sessions"]]
        for session in all_runs:
            session["identity_before"] = session["identity_after"] = deepcopy(inventory)
            session["output_hashes"] = {session["cycle_dir"] + "/" + role + ".bin": blob("synthetic output") for role in ROLES}
            session["verifications"] = {}
            for index, role in enumerate(ROLES):
                directory = session["cycle_dir"]
                log = blob(json.dumps({"case_id": 1, "passed": True, "fixture": "synthetic"}))
                session["verifications"][role] = {"argv": [token.replace("{cycle_dir}", directory) for token in config["cases"][0]["verify_commands"][role]],
                    "cwd": config["build"]["source_dir"], "started_at": session["started_at"] + 1.1 + index * .3,
                    "finished_at": session["started_at"] + 1.2 + index * .3, "exit_status": 0,
                    "log_path": directory + "/" + role + "-verify.log", "log_hash": log, "log_ref": log,
                    "output_refs": {directory + "/" + role + ".bin": session["output_hashes"][directory + "/" + role + ".bin"]}}
        plan = {"schema_version": 1, "protocol": "persistent_python_oracle_v1",
            "run_id": config["run_id"], "session_id": config["session_id"], "requests": []}
        transcript = {"schema_version": 1, "events": [
            {"direction": "receive", "at": 1.14, "monotonic_ns": 1,
             "message": {"kind": "ready", "protocol": plan["protocol"], "worker_id": "worker",
                "pid": 700, "request_plan_ref": None}}]}
        request_refs = []
        for run in all_runs:
            for role in ROLES:
                index = len(request_refs)
                directory = run["cycle_dir"]
                receipt = run["verifications"][role]
                item = {"request_index": index, "stage": "calibration" if run is pilot else "confirmation",
                    "case_id": 1, "cycle": None if run is pilot else run["cycle"], "role": role,
                    "argv": receipt["argv"], "cwd": receipt["cwd"],
                    "script_ref": files["/synthetic/verify.py"],
                    "prepared_refs": identity["cases"]["1"]["prepared_files"],
                    "output_paths": [directory + "/" + role + ".bin"],
                    "result_path": directory + "/" + role + "-result.json",
                    "log_path": receipt["log_path"],
                    "stderr_path": directory + "/" + role + "-verify.stderr.log"}
                plan["requests"].append(item)
                result_ref = value({"case_id": 1, "passed": True, "fixture": "synthetic"})
                stderr_ref = blob("")
                response = {"kind": "result", "protocol": plan["protocol"], "worker_id": "worker",
                    "pid": 700, "request_index": index,
                    "started_at": receipt["started_at"] + .02,
                    "finished_at": receipt["started_at"] + .05,
                    "exit_status": 0, "state_restored": True,
                    "script_ref": item["script_ref"],
                    "output_refs_before": receipt["output_refs"], "output_refs_after": receipt["output_refs"],
                    "log_hash": receipt["log_ref"], "stderr_hash": stderr_ref,
                    "result_hash": result_ref, "error": None}
                request_ref = value(response)
                request_refs.append(request_ref)
                receipt.update(protocol=plan["protocol"], worker_id="worker", request_index=index,
                    request_ref=request_ref, result_ref=result_ref, stderr_ref=stderr_ref)
                transcript["events"].extend([
                    {"direction": "send", "at": receipt["started_at"] + .01,
                     "monotonic_ns": len(transcript["events"]) + 1,
                     "message": {"kind": "verify", "request_index": index}},
                    {"direction": "receive", "at": receipt["finished_at"] - .01,
                     "monotonic_ns": len(transcript["events"]) + 2, "message": response}])
        plan_ref = value(plan)
        transcript["events"][0]["message"]["request_plan_ref"] = plan_ref
        transcript["events"].extend([
            {"direction": "send", "at": 22.0, "monotonic_ns": len(transcript["events"]) + 1,
             "message": {"kind": "close", "abort": False}},
            {"direction": "receive", "at": 22.1, "monotonic_ns": len(transcript["events"]) + 2,
             "message": {"kind": "closed", "completed_requests": len(request_refs)}}])
        worker = {"schema_version": 1, "protocol": plan["protocol"], "run_id": config["run_id"],
            "session_id": config["session_id"], "worker_id": "worker", "pid": 700,
            "interpreter_ref": files["/synthetic/python"],
            "worker_source_ref": producers["skills/ascendc-aprof-profiling/scripts/persistent_oracle.py"],
            "request_plan_ref": plan_ref, "started_at": 1.12, "ready_at": 1.16,
            "finished_at": 22.5, "exit_status": 0, "status": "complete",
            "request_refs": request_refs, "transcript_ref": value(transcript),
            "process_stdout_ref": blob(""), "process_stderr_ref": blob("")}
        raw["verifier_worker_ref"] = value(worker)
        registration = {"protocol": PROTOCOL, "created_at": 3.5, "config_ref": config_ref, "identity": identity,
            "inventory": inventory, "producer_files": producers, "attempt_policy": "exactly_once_no_resume_no_resampling",
            "cycles": 6, "pairs_per_phase": 5, "warmup": 10, "prime_repeat": 100,
            "calibration_ref": None, "repeat_by_case": {"1": 500},
            "verifier_request_plan_ref": plan_ref, "cpu_affinity": [0, 1], "hardware_ref": value(hardware)}
        def seal(*, report_override=None, stdout_override=None):
            for session in all_runs:
                rows = [session["ready"], *(event["message"] for event in session["events"])]
                stdout = "\n".join("APROF_SHARED_TIMING_JSON:" + json.dumps(row) for row in rows) + "\n"
                reference = blob(stdout if stdout_override is None or session is pilot else stdout_override)
                session["stdout_ref"] = session["execution"]["log_hash"] = reference
            registration["calibration_ref"] = value(calibration)
            registration_ref = value(registration)
            raw["registration_ref"] = registration_ref
            raw["calibration_ref"] = registration["calibration_ref"]
            receipt = {"schema_version": "1.0.0", "protocol": PROTOCOL,
                **{key: config[key] for key in ("run_id", "session_id", "candidate_id", "operator")},
                "source_hashes": identity["source_hashes"], "registration_ref": registration_ref,
                "config_ref": config_ref, "raw_ref": value(raw),
                "measurement_report_ref": value(summarize_shared_raw(raw, config) if report_override is None else report_override)}
            return value(receipt)
        expected = {key: config[key] for key in ("run_id", "session_id", "candidate_id", "operator")}
        expected["source_hashes"] = identity["source_hashes"]
        yield store, raw, config, registration, calibration, worker, seal, expected, blob


def test_full_synthetic_cas_replay_is_not_a_publication_claim(archive):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    result = replay_measurement_admission(store, seal(), expected=expected)
    assert result["valid"] is True and len(result["gate_projection"]["baseline_samples_ns"]) == 30
    assert registration["repeat_by_case"] == {"1": 500}
    assert result["calibration_ref"] == registration["calibration_ref"]
    assert "accepted" not in result and "production_safe_gain" not in result


def test_event_arrays_cannot_enter_current_formal_gate(archive):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    receipt_ref = seal()
    receipt = json.loads(store.verify_artifact(receipt_ref).read_text())
    report = summarize_shared_raw(raw, config)
    evidence = {"candidate_id": config["candidate_id"], **{key: "passed" for key in
                ("static_review", "build", "accuracy", "runtime", "semantic", "scope", "portability")},
                **deepcopy(report["gate_projection"]), "artifacts": {"measurement_admission": receipt_ref,
                "measurement_report": receipt["measurement_report_ref"]}}
    with pytest.raises(ContractError, match="Event evidence is historical only"):
        verify_measurement_admission(GateEvidence.from_dict(evidence), store,
            source_hashes=expected["source_hashes"], session_id=config["session_id"], run_id=config["run_id"])


@pytest.mark.parametrize("change", ["producer", "identity", "late_registration", "oracle", "output", "formal_report", "stdout", "same_cycle_dir"])
def test_outer_replay_rejects_forged_or_substituted_evidence(archive, change):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    options = {}
    if change == "producer": registration["producer_files"][PRODUCER_FILES[0]] = blob("forged producer")
    elif change == "identity": raw["sessions"][0]["identity_after"]["files"][config["build"]["binary"]] = blob("other binary")
    elif change == "late_registration": registration["created_at"] = 50
    elif change == "oracle":
        receipt = raw["sessions"][0]["verifications"]["candidate"]
        receipt["log_ref"] = receipt["log_hash"] = blob('{"passed":false}')
    elif change == "output": raw["sessions"][0]["verifications"]["candidate"]["output_refs"] = {}
    elif change == "formal_report":
        report = summarize_shared_raw(raw, config)
        report["gate_projection"]["candidate_samples_ns"][0] *= .5
        options["report_override"] = report
    elif change == "stdout": options["stdout_override"] = "APROF_SHARED_TIMING_JSON:{}\n"
    elif change == "same_cycle_dir": raw["sessions"][1]["cycle_dir"] = raw["sessions"][0]["cycle_dir"]
    with pytest.raises(ContractError):
        replay_measurement_admission(store, seal(**options), expected=expected)


@pytest.mark.parametrize("change", ["pilot_count", "pilot_candidate", "pilot_units", "pilot_median",
    "pilot_cap_exceeded",
    "pilot_repeat", "pilot_late", "freeze_late", "raw_repeat", "ready_repeat", "message_repeat",
    "confirmation_units", "pilot_in_grid"])
def test_v2_calibration_and_actual_repeat_are_replayed(archive, change):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    pilot = calibration["cases"][0]["pilot"]
    if change == "pilot_count": pilot["events"].pop(2)
    elif change == "pilot_candidate":
        pilot["events"][1]["message"]["baseline"]["implementation"] = "candidate"
    elif change == "pilot_units":
        pilot["events"][1]["message"]["baseline"]["elapsed_ns"] *= 10
    elif change == "pilot_median": calibration["cases"][0]["median_ms"] = 9.0
    elif change == "pilot_cap_exceeded":
        for event in pilot["events"][1:4]:
            event["message"]["baseline"]["elapsed_ms"] = event_time(400)[0]
            event["message"]["baseline"]["elapsed_ns"] = event_time(400)[1]
    elif change == "pilot_repeat": calibration["cases"][0]["repeat"] = 400
    elif change == "pilot_late": pilot["started_at"] = 3.4
    elif change == "freeze_late": registration["created_at"] = 4.1
    elif change == "raw_repeat": raw["repeat_by_case"]["1"] = 100
    elif change == "ready_repeat": raw["sessions"][0]["ready"]["repeat"] = 100
    elif change == "message_repeat": raw["sessions"][0]["events"][1]["message"]["repeat"] = 100
    elif change == "confirmation_units":
        raw["sessions"][0]["events"][1]["message"]["baseline"]["elapsed_ns"] *= 5
    elif change == "pilot_in_grid": raw["sessions"].insert(0, deepcopy(pilot))
    with pytest.raises(ContractError):
        replay_measurement_admission(store, seal(), expected=expected)


@pytest.mark.parametrize("change", ["worker_ref", "plan_ref", "request_order", "result_ref",
    "result_case", "stderr_ref"])
def test_v2_persistent_oracle_receipts_are_replayed(archive, change):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    receipt = raw["sessions"][0]["verifications"]["baseline"]
    if change == "worker_ref": raw["verifier_worker_ref"] = blob("{}")
    elif change == "plan_ref": registration["verifier_request_plan_ref"] = blob("{}")
    elif change == "request_order": receipt["request_index"] = 99
    elif change == "result_ref": receipt["result_ref"] = blob('{"passed":false}')
    elif change == "result_case": receipt["result_ref"] = blob('{"case_id":2,"passed":true}')
    elif change == "stderr_ref": receipt["stderr_ref"] = blob("tampered")
    with pytest.raises(ContractError):
        replay_measurement_admission(store, seal(), expected=expected)


@pytest.mark.parametrize(("field", "value"), [
    ("started_at", 1.0), ("ready_at", 1.25), ("finished_at", 23.1)])
def test_v2_oracle_lifecycle_stays_inside_collection(archive, field, value):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    worker[field] = value
    raw["verifier_worker_ref"] = register_json_artifact(store, worker)
    with pytest.raises(ContractError):
        replay_measurement_admission(store, seal(), expected=expected)
