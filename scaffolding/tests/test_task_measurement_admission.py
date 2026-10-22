"""Synthetic CAS boundary tests. No fixture is hardware or publication evidence."""
from copy import deepcopy
import json
import shlex

import pytest

from aprof_runtime.contracts import GateEvidence
from aprof_runtime.errors import ContractError
from aprof_runtime.measurement_admission import (
    _phase_controls, replay_historical_measurement_admission, replay_measurement_admission,
    verify_measurement_admission,
)
from aprof_runtime.task_measurement_admission import (
    PROTOCOL, PRODUCER_FILES, PROFILE_FLAGS, _commands, select_mount,
    replay_task_measurement_admission, replay_historical_task_measurement_admission, summarize_task_raw,
)
from aprof_runtime.task_timing import partition_task_samples
from aprof_runtime.traces import register_json_artifact
from test_shared_measurement_admission import archive, draft, wire, set_sample, RELEASE, ROLES
from test_task_timing import task_rows, table


@pytest.fixture
def task_archive(archive):
    store, original, config, registration, calibration, worker, _, expected, blob = archive
    raw, config, registration, worker = map(deepcopy, (original, config, registration, worker))
    value = lambda item: register_json_artifact(store, item)
    load = lambda ref: json.loads(store.verify_artifact(ref).read_text())
    config["task_profile"] = {"profiler": "/synthetic/msprof", "scratch_root": "/synthetic/scratch",
        "role_kernel_names": {role: ["exp_kernel"] for role in ROLES}}
    profiler_ref = blob("synthetic profiler executable")
    producers = {name: store.register_artifact(RELEASE / name) for name in PRODUCER_FILES}
    registration["producer_files"] = producers
    registration["inventory"]["producer_files"] = deepcopy(producers)
    registration["inventory"]["files"]["/synthetic/msprof"] = profiler_ref
    registration.update(protocol=PROTOCOL, repeat=100, profiler_ref=profiler_ref,
                        task_profile=config["task_profile"])
    mountinfo = "1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /synthetic/results rw - fuse.juicefs fixture rw\n"
    registration["profile_storage_ref"] = value({"schema_version": 1, "mode": "local_profile_then_copy",
        "scratch_root": "/synthetic/scratch", "persistent_root": "/synthetic/results", "created_at": 1.1,
        "host": raw["host"], "directory_mode": 0o700, "mountinfo_ref": blob(mountinfo),
        "scratch_mount": select_mount(mountinfo, "/synthetic/scratch"),
        "persistent_mount": select_mount(mountinfo, "/synthetic/results"),
        "collection_started_at": .1, "timeout_seconds": 120})
    for key in ("calibration_ref", "repeat_by_case"):
        registration.pop(key)
        raw.pop(key, None)
    raw["protocol"] = PROTOCOL
    requests = load(registration["verifier_request_plan_ref"])
    requests["requests"] = requests["requests"][2:]
    transcript = load(worker["transcript_ref"])
    transcript["events"] = [transcript["events"][0], *transcript["events"][5:]]
    transcript["events"][0]["at"] = 4.15
    worker.update(started_at=4.1, ready_at=4.2)
    worker["request_refs"] = worker["request_refs"][2:]
    worker["worker_source_ref"] = producers["skills/ascendc-aprof-profiling/scripts/persistent_oracle.py"]
    for index, request in enumerate(requests["requests"]):
        request["request_index"] = index
        session = raw["sessions"][index // 2]
        receipt = session["verifications"][ROLES[index % 2]]
        response = load(receipt["request_ref"])
        response["request_index"] = index
        reference = value(response)
        receipt.update(request_index=index, request_ref=reference)
        worker["request_refs"][index] = reference
        transcript["events"][index * 2 + 1]["message"]["request_index"] = index
        transcript["events"][index * 2 + 2]["message"] = response
    request_plan_ref = value(requests)
    registration["verifier_request_plan_ref"] = request_plan_ref
    worker["request_plan_ref"] = request_plan_ref
    transcript["events"][0]["message"]["request_plan_ref"] = request_plan_ref
    transcript["events"][-1]["message"]["completed_requests"] = 12
    for index, event in enumerate(transcript["events"]):
        event["monotonic_ns"] = index + 1
    worker["transcript_ref"] = value(transcript)
    raw["verifier_worker_ref"] = value(worker)
    for session in raw["sessions"]:
        directory = session["cycle_dir"]
        ready, events = wire(config, session["cycle"], repeat=100)
        messages = [ready, *(event["message"] for event in events)]
        csv_text = table(task_rows(messages, config["task_profile"]["role_kernel_names"]))
        table_ref = blob(csv_text)
        partition = partition_task_samples(csv_text=csv_text, messages=messages, operator=config["operator"],
            cycle=session["cycle"], role_kernel_names=config["task_profile"]["role_kernel_names"])
        stdout = blob("\n".join("APROF_SHARED_TIMING_JSON:" + json.dumps(message) for message in messages) + "\n")
        command = [token.replace("{cycle_dir}", directory) for token in config["cases"][0]["command"]]
        scratch_profile = f"/synthetic/scratch/case-01-cycle-{session['cycle']}/profile"
        capture = {"argv": ["/synthetic/msprof", "--output=" + scratch_profile, *PROFILE_FLAGS,
                "--application=" + shlex.join(command)], "cwd": config["build"]["source_dir"],
            "started_at": session["started_at"] + .1, "ended_at": session["started_at"] + 1,
            "exit_code": 0, "error": None, "pid": 1000 + session["cycle"],
            "stdout_hash": stdout, "stderr_hash": blob(""), "timeout_seconds": 60,
            "environment": {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(session["cycle"]),
                "APROF_SHARED_MODE": "confirmation", "APROF_SHARED_REPEAT": "100",
                "APROF_SHARED_COMMANDS": directory + "/commands.txt"}}
        capture["log_hash"] = value(capture)
        inventory_ref = value({"PROF_SYNTH/mindstudio_profiler_output/op_summary.csv": table_ref})
        session.update(capture=capture, export=None, commands_ref=blob(_commands()),
            task_table_ref=table_ref, native_messages_ref=value(messages), partition_ref=value(partition),
            control_summary=_phase_controls(partition["values_ns_per_call"]),
            capture_files_ref=inventory_ref, profile_files_ref=inventory_ref,
            identity_before=deepcopy(registration["inventory"]), identity_after=deepcopy(registration["inventory"]))
        session["profile_transfer_ref"] = value({"source_dir": scratch_profile,
            "destination_dir": directory + "/profile", "started_at": session["started_at"] + 1.06,
            "finished_at": session["started_at"] + 1.08, "source_inventory_ref": inventory_ref,
            "persisted_inventory_ref": inventory_ref, "source_after_inventory_ref": inventory_ref})
        for key in ("ready", "events", "execution"):
            session.pop(key)
    def seal(report_override=None):
        registration["config_ref"] = value(config)
        registration_ref = value(registration)
        raw["registration_ref"] = registration_ref
        receipt = {"schema_version": "1.0.0", "protocol": PROTOCOL,
            **{key: config[key] for key in ("operator", "run_id", "session_id", "candidate_id")},
            "source_hashes": registration["identity"]["source_hashes"],
            "config_ref": registration["config_ref"], "registration_ref": registration_ref,
            "raw_ref": value(raw), "measurement_report_ref": value(
                summarize_task_raw(raw, config, store) if report_override is None else report_override)}
        return value(receipt)
    return store, raw, config, registration, worker, seal, expected, blob, value, load


def test_task_full_replay_uses_thirty_pairs_and_no_pilot(task_archive):
    store, raw, config, registration, worker, seal, expected, *_ = task_archive
    result = replay_task_measurement_admission(store, seal(), expected=expected)
    assert result["valid"] is True and result["protocol"] == PROTOCOL
    assert result["report"]["speedup"] == pytest.approx(2)
    assert len(result["gate_projection"]["baseline_samples_ns"]) == 30
    assert "calibration_ref" not in registration and len(worker["request_refs"]) == 12
    assert "accepted" not in result


def test_task_gate_requires_exact_replayed_projection(task_archive):
    store, raw, config, registration, worker, seal, expected, _, _, load = task_archive
    reference = seal()
    report = summarize_task_raw(raw, config, store)
    evidence = {"candidate_id": config["candidate_id"], **{key: "passed" for key in
        ("static_review", "build", "accuracy", "runtime", "semantic", "scope", "portability")},
        **deepcopy(report["gate_projection"]), "artifacts": {"measurement_admission": reference,
        "measurement_report": load(reference)["measurement_report_ref"]}}
    verify_measurement_admission(GateEvidence.from_dict(evidence), store, source_hashes=expected["source_hashes"])
    evidence["candidate_samples_ns"][0] /= 2
    with pytest.raises(ContractError, match="projection differs"):
        verify_measurement_admission(GateEvidence.from_dict(evidence), store, source_hashes=expected["source_hashes"])


def test_task_optional_export_replays_original_capture_before_one_export(task_archive):
    store, raw, config, registration, worker, seal, expected, blob, value, load = task_archive
    session = raw["sessions"][0]
    captured = {"PROF_SYNTH/device_0/data.raw": blob("synthetic original task records")}
    session["capture_files_ref"] = value(captured)
    session["profile_files_ref"] = value({**captured, **load(session["profile_files_ref"])})
    exported = deepcopy(session["capture"])
    exported.update(argv=[config["task_profile"]["profiler"], "--export=on", "--type=text",
                          "--output=" + config["task_profile"]["scratch_root"] + "/case-01-cycle-0/profile/PROF_SYNTH"],
                    started_at=session["capture"]["ended_at"] + .01,
                    ended_at=session["capture"]["ended_at"] + .05,
                    pid=2000, stdout_hash=blob("export completed"))
    exported.pop("log_hash")
    exported["log_hash"] = value(exported)
    session["export"] = exported
    transfer = load(session["profile_transfer_ref"])
    for key in ("source_inventory_ref", "persisted_inventory_ref", "source_after_inventory_ref"):
        transfer[key] = session["profile_files_ref"]
    session["profile_transfer_ref"] = value(transfer)
    assert replay_task_measurement_admission(store, seal(), expected=expected)["valid"]


def test_auxiliary_event_instability_does_not_veto_stable_task_duration(task_archive):
    store, raw, config, registration, worker, seal, expected, blob, value, load = task_archive
    for session in raw["sessions"]:
        messages = load(session["native_messages_ref"])
        for message in messages:
            if message["kind"] == "pair":
                set_sample(message["candidate"], 400 if message["pair_index"] == 0 else 100, 100)
        session["native_messages_ref"] = value(messages)
        session["capture"]["stdout_hash"] = blob("\n".join(
            "APROF_SHARED_TIMING_JSON:" + json.dumps(message) for message in messages) + "\n")
        record = {key: item for key, item in session["capture"].items() if key != "log_hash"}
        session["capture"]["log_hash"] = value(record)
        partition = partition_task_samples(table_path=store.verify_artifact(session["task_table_ref"]),
            messages=messages, operator=config["operator"], cycle=session["cycle"],
            role_kernel_names=config["task_profile"]["role_kernel_names"])
        session["partition_ref"] = value(partition)
    result = replay_task_measurement_admission(store, seal(), expected=expected)
    assert result["report"]["stable"] is True
    assert result["report"]["speedup"] == pytest.approx(2)


@pytest.mark.parametrize("change", ["missing_cycle", "producer", "tool", "flags", "env", "commands", "raw_csv",
    "partition", "stdout", "two_tables", "export_without_need", "identity", "late_registration", "oracle",
    "output", "late_oracle", "worker_lifecycle", "reused_directory", "wrong_role_symbol", "report"])
def test_task_replay_rejects_incomplete_or_substituted_evidence(task_archive, change):
    store, raw, config, registration, worker, seal, expected, blob, value, load = task_archive
    session = raw["sessions"][0]
    override = None
    if change == "missing_cycle": raw["sessions"].pop()
    elif change == "producer": registration["producer_files"][PRODUCER_FILES[-1]] = blob("other producer")
    elif change == "tool": registration["profiler_ref"] = blob("other msprof")
    elif change == "flags": session["capture"]["argv"][3] = "--ai-core=on"
    elif change == "env": session["capture"]["environment"]["APROF_SHARED_REPEAT"] = "7300"
    elif change == "commands": session["commands_ref"] = blob(_commands().replace("pair 1", "pair 9", 1))
    elif change == "raw_csv": session["task_table_ref"] = blob(store.verify_artifact(session["task_table_ref"]).read_text().replace("2,AI_CORE", "1,AI_CORE", 1))
    elif change == "partition":
        partition = load(session["partition_ref"])
        partition["values_ns_per_call"]["formal"]["candidate"][0] *= .5
        session["partition_ref"] = value(partition)
    elif change == "stdout": session["capture"]["stdout_hash"] = blob("APROF_SHARED_TIMING_JSON:{}\n")
    elif change == "two_tables":
        files = load(session["profile_files_ref"]); files["PROF_OTHER/op_summary.csv"] = session["task_table_ref"]
        session["capture_files_ref"] = session["profile_files_ref"] = value(files)
    elif change == "export_without_need": session["export"] = deepcopy(session["capture"])
    elif change == "identity": session["identity_after"]["files"][config["build"]["binary"]] = blob("changed binary")
    elif change == "late_registration": registration["created_at"] = 6
    elif change == "oracle": session["verifications"]["candidate"]["log_ref"] = blob('{"passed":false}')
    elif change == "output": session["output_hashes"] = {}
    elif change == "late_oracle": session["verifications"]["candidate"]["finished_at"] = 100
    elif change == "worker_lifecycle":
        worker["ready_at"] = 100; raw["verifier_worker_ref"] = value(worker)
    elif change == "reused_directory": raw["sessions"][1]["cycle_dir"] = session["cycle_dir"]
    elif change == "wrong_role_symbol": config["roles"]["candidate"]["symbol"] = "different_callback"
    elif change == "report":
        override = summarize_task_raw(raw, config, store)
        override["gate_projection"]["candidate_samples_ns"][0] *= .5
    with pytest.raises(ContractError):
        replay_task_measurement_admission(store, seal(override), expected=expected)


def test_task_raw_control_failure_cannot_be_hidden_by_stable_report(task_archive):
    store, raw, config, registration, worker, seal, expected, blob, value, load = task_archive
    override = summarize_task_raw(raw, config, store)
    session = raw["sessions"][0]
    messages = load(session["native_messages_ref"])
    rows = task_rows(messages, config["task_profile"]["role_kernel_names"])
    partition = load(session["partition_ref"])
    group = next(item for item in partition["groups"] if item["kind"] == "pair" and item["role"] == "candidate")
    for index in group["csv_row_indices"]:
        rows[index]["Task Duration(us)"] = "8"
    csv_text = table(rows)
    session["task_table_ref"] = blob(csv_text)
    partition = partition_task_samples(csv_text=csv_text, messages=messages, operator=config["operator"], cycle=0,
        role_kernel_names=config["task_profile"]["role_kernel_names"])
    session["partition_ref"] = value(partition)
    session["control_summary"] = _phase_controls(partition["values_ns_per_call"])
    session["capture_files_ref"] = session["profile_files_ref"] = value({"PROF_SYNTH/op_summary.csv": session["task_table_ref"]})
    transfer = load(session["profile_transfer_ref"])
    for key in ("source_inventory_ref", "persisted_inventory_ref", "source_after_inventory_ref"):
        transfer[key] = session["profile_files_ref"]
    session["profile_transfer_ref"] = value(transfer)
    with pytest.raises(ContractError, match="CV|role bias"):
        replay_task_measurement_admission(store, seal(override), expected=expected)


def test_task_partial_raw_has_empty_projection(task_archive):
    store, raw, config, *_ = task_archive
    raw.update(complete=False, error={"message": "actual collection failed"})
    report = summarize_task_raw(raw, config, store)
    assert not report["stable"] and report["reasons"]
    assert not report["gate_projection"]["baseline_samples_ns"]


@pytest.mark.parametrize("change", ["source", "destination", "missing_file", "extra_file", "source_after",
    "late_copy", "early_copy", "missing_transfer", "mount", "remote_mount", "mode", "late_storage", "total_budget"])
def test_v2_storage_and_complete_transfer_cannot_be_substituted(task_archive, change):
    store, raw, config, registration, worker, seal, expected, blob, value, load = task_archive
    session = raw["sessions"][0]
    transfer = load(session["profile_transfer_ref"])
    storage = load(registration["profile_storage_ref"])
    if change == "source": transfer["source_dir"] = "/different/scratch"
    elif change == "destination": transfer["destination_dir"] = "/different/persistent"
    elif change == "missing_file": transfer["persisted_inventory_ref"] = value({})
    elif change == "extra_file": transfer["persisted_inventory_ref"] = value({
        **load(transfer["persisted_inventory_ref"]), "unexpected": blob("extra")})
    elif change == "source_after": transfer["source_after_inventory_ref"] = value({"changed": blob("changed")})
    elif change == "late_copy": transfer["finished_at"] = session["finished_at"]
    elif change == "early_copy": transfer["started_at"] = session["capture"]["started_at"]
    elif change == "missing_transfer": session.pop("profile_transfer_ref")
    elif change == "mount": storage["scratch_mount"]["mount_id"] += 1
    elif change == "remote_mount":
        mountinfo = "1 0 0:1 / / rw - nfs remote rw\n"
        storage["mountinfo_ref"] = blob(mountinfo)
        storage["scratch_mount"] = select_mount(mountinfo, storage["scratch_root"])
        storage["persistent_mount"] = select_mount(mountinfo, storage["persistent_root"])
    elif change == "mode": storage["directory_mode"] = 0o755
    elif change == "late_storage": storage["created_at"] = 99
    elif change == "total_budget": storage["timeout_seconds"] = 10
    if change != "missing_transfer": session["profile_transfer_ref"] = value(transfer)
    registration["profile_storage_ref"] = value(storage)
    with pytest.raises(ContractError):
        replay_task_measurement_admission(store, seal(), expected=expected)


def test_longest_mount_is_selected_and_escaped_paths_are_preserved():
    text = "1 0 0:1 / / rw - overlay overlay rw\n2 1 0:2 / /local\\040scratch rw - tmpfs tmpfs rw\n"
    assert select_mount(text, "/local scratch/trial")["mount_id"] == 2
    assert select_mount(text, "/local scratchpad/trial")["mount_id"] == 1


def test_explicit_historical_producer_replay_never_grants_current_eligibility(archive):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    reference = seal()
    result = replay_measurement_admission(store, reference, expected=expected)
    resolved = []
    def resolver(path, digest):
        resolved.append(str(path))
        return store.verify_artifact(digest)
    historical = replay_historical_measurement_admission(store, reference, expected=expected, producer_resolver=resolver)
    assert historical == {"replay": result, "eligible_for_publication": False}
    assert len(resolved) == 10


def test_historical_resolver_cannot_substitute_other_producer_bytes(archive):
    store, raw, config, registration, calibration, worker, seal, expected, blob = archive
    other = store.verify_artifact(blob("wrong historical source"))
    with pytest.raises(ContractError, match="untrusted producer bytes"):
        replay_historical_measurement_admission(store, seal(), expected=expected,
            producer_resolver=lambda path, digest: other)


def test_task_history_requires_explicit_archived_bytes_and_never_grants_admission(task_archive):
    store, raw, config, registration, worker, seal, expected, blob, *_ = task_archive
    producer = PRODUCER_FILES[-1]
    old_ref = blob("historical producer bytes")
    registration["producer_files"][producer] = old_ref
    registration["inventory"]["producer_files"][producer] = old_ref
    for session in raw["sessions"]:
        for key in ("identity_before", "identity_after"):
            session[key]["producer_files"][producer] = old_ref
    reference = seal()
    with pytest.raises(ContractError, match="untrusted producer bytes"):
        replay_task_measurement_admission(store, reference, expected=expected)
    resolved = []
    def resolver(path, digest):
        resolved.append((path, digest))
        return store.verify_artifact(digest)
    result = replay_historical_task_measurement_admission(
        store, reference, expected=expected, producer_resolver=resolver)
    assert result["eligible_for_publication"] is False
    assert result["authority"] == "historical_task_measurement"
    assert result["replay"]["valid"] is True
    assert len(resolved) == len(PRODUCER_FILES)
    assert "gate_projection" not in result["replay"]
    assert "gate_projection" not in result["replay"]["report"]
    with pytest.raises(ContractError, match="historical producer resolver is required"):
        replay_historical_task_measurement_admission(store, reference, expected=expected,
                                                   producer_resolver=None)
    with pytest.raises(ContractError, match="untrusted producer bytes"):
        replay_historical_task_measurement_admission(store, reference, expected=expected,
            producer_resolver=lambda path, digest: store.verify_artifact(old_ref))
