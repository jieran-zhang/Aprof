"""Replay complete Task Duration evidence; Event/Host values are auxiliary only."""
from pathlib import PurePosixPath
import re
import shlex

from . import measurement_admission as shared
from .errors import ContractError
from .jsonio import canonical_json
from .profile_evidence import _json, _load
from .task_timing import partition_task_samples, protocol_commands


PROTOCOL = "shared_buffer_msprof_task_v2"
METRIC = "msprof.op_summary.Task_Duration"
PROFILE_FLAGS = ("--task-time=l1", "--ai-core=off", "--ascendcl=off", "--runtime-api=off",
                 "--ge-api=off", "--aicpu=off", "--type=text")
LOCAL_PROFILE_FILESYSTEMS = frozenset({"overlay", "ext4", "xfs", "btrfs", "tmpfs"})
PRODUCER_FILES = shared.PRODUCER_FILES + (
    "skills/ascendc-aprof-profiling/scripts/device_task_timing.py",
    "runtime/src/aprof_runtime/task_timing.py",
    "runtime/src/aprof_runtime/task_measurement_admission.py",
    "runtime/src/aprof_runtime/store.py",
)
_need, _number, _interval = shared._require, shared._number, shared._interval
ROLES, PHASES = shared.ROLES, shared.PHASES


def _commands():
    return "\n".join(protocol_commands()) + "\n"


def _path(value):
    _need(isinstance(value, str), "artifact path is not text")
    path = PurePosixPath(value)
    _need(path.is_absolute() and str(path) == value and ".." not in path.parts,
          "artifact path is not canonical absolute")
    return path


def select_mount(mountinfo, path):
    """Select the actual longest mount-point prefix from a frozen mountinfo text."""
    path = _path(str(path))
    matches = []
    unescape = lambda value: re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)
    for line in mountinfo.splitlines():
        left, separator, right = line.partition(" - ")
        fields, extra = left.split(), right.split()
        _need(separator and len(fields) >= 6 and len(extra) >= 3, "invalid mountinfo record")
        point = _path(unescape(fields[4]))
        if path.is_relative_to(point):
            matches.append((len(point.parts), {
                "mount_id": int(fields[0]), "parent_id": int(fields[1]), "device": fields[2],
                "root": unescape(fields[3]), "mount_point": str(point),
                "filesystem_type": extra[0], "mount_source": unescape(extra[1]),
            }))
    _need(bool(matches), "profile path has no registered mount")
    return max(enumerate(matches), key=lambda item: (item[1][0], item[0]))[1][1]


def _storage(reader, registration, config):
    storage = _load(reader, registration["profile_storage_ref"])
    _need(isinstance(storage, dict) and set(storage) == {
        "schema_version", "mode", "scratch_root", "persistent_root", "created_at", "host", "directory_mode",
        "mountinfo_ref", "scratch_mount", "persistent_mount", "collection_started_at", "timeout_seconds"},
        "invalid Task profile storage receipt")
    scratch, persistent = _path(storage["scratch_root"]), _path(storage["persistent_root"])
    _need(storage["schema_version"] == 1 and storage["mode"] == "local_profile_then_copy"
          and type(storage["directory_mode"]) is int and storage["directory_mode"] == 0o700
          and str(scratch) == config["task_profile"]["scratch_root"]
          and not scratch.is_relative_to(persistent) and not persistent.is_relative_to(scratch),
          "Task scratch/persistent storage differs")
    for source in [config["build"]["source_dir"], *(config["roles"][role]["source_dir"] for role in ROLES)]:
        root = _path(source)
        _need(not scratch.is_relative_to(root) and not root.is_relative_to(scratch),
              "Task scratch overlaps frozen sources")
    mountinfo = reader.verify_artifact(storage["mountinfo_ref"]).read_text(encoding="utf-8")
    _need(storage["scratch_mount"] == select_mount(mountinfo, scratch)
          and storage["persistent_mount"] == select_mount(mountinfo, persistent),
          "Task registered mount differs from raw mountinfo")
    _need(storage["scratch_mount"]["filesystem_type"] in LOCAL_PROFILE_FILESYSTEMS,
          "Task scratch filesystem is not a supported local filesystem")
    _need(0 < _number(storage["timeout_seconds"]) <= 3600
          and _number(storage["collection_started_at"]) <= _number(storage["created_at"])
          <= _number(registration["created_at"]), "Task storage registration time/budget differs")
    return storage


def _grid(raw, config, reader):
    _need(raw.get("protocol") == PROTOCOL and raw.get("complete") is True and "error" not in raw,
          "Task measurement is incomplete or failed")
    ids = config["expected_case_ids"]
    _need(isinstance(ids, list) and ids and all(type(cid) is int and cid > 0 for cid in ids)
          and len(set(ids)) == len(ids) and [case["case_id"] for case in config["cases"]] == ids,
          "Task case scope differs")
    sessions = raw["sessions"]
    _need([(item["case_id"], item["cycle"]) for item in sessions] ==
          [(cid, cycle) for cid in ids for cycle in range(6)], "Task session scope/order differs")
    values, partitions = {cid: [] for cid in ids}, []
    for session in sessions:
        partition = _load(reader, session["partition_ref"])
        _need(partition["metric"] == METRIC and partition["operator"] == config["operator"]
              and type(partition["repeat"]) is int and partition["repeat"] == 100
              and type(partition["cycle"]) is int and partition["cycle"] == session["cycle"],
              "Task partition identity differs")
        sample = partition["values_ns_per_call"]
        _need(set(sample) == set(PHASES), "Task phase scope differs")
        for phase in PHASES:
            _need(set(sample[phase]) == set(ROLES), "Task role scope differs")
            for role in ROLES:
                _need(isinstance(sample[phase][role], list) and len(sample[phase][role]) == 5
                      and all(_number(value) > 0 for value in sample[phase][role]),
                      "Task sample count or value differs")
        values[session["case_id"]].append(sample)
        partitions.append(partition)
    return values, partitions


def summarize_task_raw(raw, config, artifact_reader):
    """Draft only. Admission additionally reproduces every partition from raw CSV."""
    try:
        values, _ = _grid(raw, config, artifact_reader)
        report = shared._summarize_values(values, config, protocol=PROTOCOL)
    except (ContractError, KeyError, TypeError, ValueError, IndexError, AttributeError, OSError, ArithmeticError) as error:
        report = shared._summarize_values(None, config, protocol=PROTOCOL, failure=ContractError(str(error)))
    report.update(metric=METRIC, sample_unit="100 complete calls per paired sample; 30 pairs per case",
                  auxiliary_scope="Event, Host wall, task spans and gaps remain in the complete partitions; excluded from Task gates")
    return report


def _profile_files(reader, reference):
    files = _load(reader, reference)
    _need(isinstance(files, dict) and files, "profile inventory is empty or not an object")
    for name, digest in files.items():
        path = PurePosixPath(name)
        _need(isinstance(name, str) and name and str(path) == name and not path.is_absolute()
              and ".." not in path.parts and name != ".", "profile path escaped output root")
        reader.verify_artifact(digest)
    return files


def _tables(files):
    return [name for name in files if PurePosixPath(name).name.startswith("op_summary")
            and name.endswith(".csv")]


def _execution(reader, record, *, argv, cwd, environment, earliest, latest, timeout_cap=3600, deadline=None):
    _need(isinstance(record, dict) and set(record) == {
          "argv", "cwd", "started_at", "ended_at", "exit_code", "error", "stdout_hash", "stderr_hash",
          "environment", "timeout_seconds", "pid", "log_hash"}, "invalid Task execution receipt")
    _need(record["argv"] == argv and record["cwd"] == cwd and record["environment"] == environment
          and type(record["exit_code"]) is int and record["exit_code"] == 0 and record["error"] is None
          and type(record["pid"]) is int and record["pid"] > 0,
          "Task profiler command/environment failed or differs")
    timeout = _number(record["timeout_seconds"])
    _need(0 < timeout <= _number(timeout_cap), "invalid Task execution timeout")
    if deadline is not None:
        _need(_number(record["started_at"]) + timeout <= _number(deadline) + .01,
              "Task execution allowance exceeds original deadline")
    _interval(record["started_at"], record["ended_at"], within=(earliest, latest))
    _need(record["ended_at"] - record["started_at"] <= timeout, "Task execution exceeded its budget")
    for key in ("stdout_hash", "stderr_hash"):
        reader.verify_artifact(record[key])
    _need(_load(reader, record["log_hash"]) == {key: value for key, value in record.items() if key != "log_hash"},
          "Task execution does not match original receipt")
    return record["ended_at"]


def _session(reader, session, config, registration, storage):
    _need(isinstance(session, dict) and set(session) == {
          "case_id", "cycle", "mode", "cycle_dir", "started_at", "finished_at", "identity_before", "identity_after",
          "capture", "export", "commands_ref", "task_table_ref", "native_messages_ref", "partition_ref",
          "output_hashes", "verifications", "control_summary", "capture_files_ref", "profile_files_ref",
          "profile_transfer_ref"},
          "Task session fields differ")
    _need(session["mode"] == "confirmation" and type(session["cycle"]) is int
          and 0 <= session["cycle"] < 6, "invalid Task cycle")
    directory = _path(session["cycle_dir"])
    case = next(case for case in config["cases"] if case["case_id"] == session["case_id"])
    _need(directory == _path(storage["persistent_root"]) / f"case-{session['case_id']:02d}-cycle-{session['cycle']}",
          "Task persistent cycle directory differs")
    profile = _path(storage["scratch_root"]) / f"case-{session['case_id']:02d}-cycle-{session['cycle']}" / "profile"
    command_path = directory / "commands.txt"
    _need(reader.verify_artifact(session["commands_ref"]).read_text(encoding="utf-8") == _commands(),
          "Task native commands differ")
    environment = {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(session["cycle"]),
                   "APROF_SHARED_MODE": "confirmation", "APROF_SHARED_REPEAT": "100",
                   "APROF_SHARED_COMMANDS": str(command_path)}
    native_argv = shared._expanded(case["command"], str(directory))
    _need(native_argv[0] == config["build"]["binary"], "Task callback binary differs")
    profiler = config["task_profile"]["profiler"]
    argv = [profiler, "--output=" + str(profile), *PROFILE_FLAGS, "--application=" + shlex.join(native_argv)]
    finished = _execution(reader, session["capture"], argv=argv, cwd=config["build"]["source_dir"],
                          environment=environment, earliest=session["started_at"], latest=session["finished_at"])
    captured = _profile_files(reader, session["capture_files_ref"])
    files = _profile_files(reader, session["profile_files_ref"])
    if session["export"] is None:
        _need(session["capture_files_ref"] == session["profile_files_ref"], "uncaptured profile files appeared")
    else:
        roots = {PurePosixPath(name).parts[0] for name in captured if PurePosixPath(name).parts[0].startswith("PROF_")}
        _need(not _tables(captured) and len(roots) == 1, "unnecessary or ambiguous Task export")
        export_argv = [profiler, "--export=on", "--type=text", "--output=" + str(profile / next(iter(roots)))]
        finished = _execution(reader, session["export"], argv=export_argv, cwd=config["build"]["source_dir"],
                              environment=environment, earliest=finished, latest=session["finished_at"])
    transfer = _load(reader, session["profile_transfer_ref"])
    _need(isinstance(transfer, dict) and set(transfer) == {
        "source_dir", "destination_dir", "started_at", "finished_at", "source_inventory_ref",
        "persisted_inventory_ref", "source_after_inventory_ref"}, "invalid Task profile transfer")
    _need(transfer["source_dir"] == str(profile) and transfer["destination_dir"] == str(directory / "profile"),
          "Task profile transfer source/destination differs")
    _interval(transfer["started_at"], transfer["finished_at"], within=(finished, session["finished_at"]))
    for key in ("source_inventory_ref", "persisted_inventory_ref", "source_after_inventory_ref"):
        _need(_profile_files(reader, transfer[key]) == files, "Task profile transfer inventory differs")
    finished = transfer["finished_at"]
    tables = _tables(files)
    _need(len(tables) == 1 and files[tables[0]] == session["task_table_ref"],
          "Task table is absent, ambiguous or outside captured inventory")
    messages = []
    for line in reader.verify_artifact(session["capture"]["stdout_hash"]).read_text(encoding="utf-8").splitlines():
        if line.startswith("APROF_SHARED_TIMING_JSON:"):
            messages.append(_json(line[len("APROF_SHARED_TIMING_JSON:"):]))
        elif "APROF_SHARED_TIMING" in line:
            raise ContractError("measurement admission: malformed Task native stdout")
    _need(_load(reader, session["native_messages_ref"]) == messages, "Task native messages differ from stdout")
    partition = partition_task_samples(
        table_path=reader.verify_artifact(session["task_table_ref"]), messages=messages,
        operator=config["operator"], cycle=session["cycle"], repeat=100,
        role_kernel_names=config["task_profile"]["role_kernel_names"])
    ready = messages[0]
    _need(ready["device"] == config["device"] and ready["cpu_affinity"] == registration["cpu_affinity"]
          and ready["role_symbols"] == {role: config["roles"][role]["symbol"] for role in ROLES},
          "Task native hardware/callback identity differs")
    _need(canonical_json(_load(reader, session["partition_ref"])) == canonical_json(partition),
          "Task partition differs from full raw replay")
    _need(session["control_summary"] == shared._phase_controls(partition["values_ns_per_call"]),
          "Task cycle controls differ from raw replay")
    shared._output_artifacts(reader, session, config, after=finished)
    return ready["pid"], partition


def _replay_task_admission(artifact_reader, receipt_ref, *, expected, producer_resolver=None):
    """Independently replay fixed Task profiling, all correctness and all controls."""
    reader = artifact_reader
    try:
        receipt = _load(reader, receipt_ref)
        _need(isinstance(receipt, dict) and set(receipt) == {
              "schema_version", "protocol", "run_id", "session_id", "candidate_id", "operator", "source_hashes",
              "registration_ref", "config_ref", "raw_ref", "measurement_report_ref"}
              and receipt["schema_version"] == "1.0.0" and receipt["protocol"] == PROTOCOL,
              "unsupported Task admission receipt")
        for key, value in expected.items():
            _need(receipt.get(key) == value, "Task receipt " + key + " differs")
        config = shared._config_identity(reader, receipt, extra_fields=("task_profile",))
        profile = config["task_profile"]
        _need(isinstance(profile, dict) and set(profile) == {"profiler", "role_kernel_names", "scratch_root"}, "invalid Task profile config")
        _path(profile["profiler"])
        _path(profile["scratch_root"])
        names = profile["role_kernel_names"]
        _need(isinstance(names, dict) and set(names) == set(ROLES), "Task kernel roles differ")
        for role in ROLES:
            _need(isinstance(names[role], list) and len(names[role]) == config["roles"][role]["launches_per_operator"]
                  and all(isinstance(name, str) and name and name.strip() == name for name in names[role]),
                  "Task kernel sequence differs from complete callback")
        registration = _load(reader, receipt["registration_ref"])
        _need(isinstance(registration, dict) and set(registration) == {
              "protocol", "created_at", "config_ref", "identity", "inventory", "producer_files", "attempt_policy",
              "cycles", "pairs_per_phase", "warmup", "prime_repeat", "repeat", "cpu_affinity", "hardware_ref",
              "verifier_request_plan_ref", "profiler_ref", "task_profile", "profile_storage_ref"}, "invalid Task registration")
        for key, value in {"protocol": PROTOCOL, "config_ref": receipt["config_ref"], "task_profile": profile,
                           "attempt_policy": "exactly_once_no_resume_no_resampling", "cycles": 6,
                           "pairs_per_phase": 5, "warmup": 10, "prime_repeat": 100, "repeat": 100}.items():
            _need(type(registration.get(key)) is type(value) and registration[key] == value,
                  "Task registration " + key + " differs")
        inventory = shared._registered_identity(reader, receipt, config, registration,
            producer_files=PRODUCER_FILES, producer_resolver=producer_resolver,
            extra_files={profile["profiler"]: registration["profiler_ref"]})
        storage = _storage(reader, registration, config)
        raw = _load(reader, receipt["raw_ref"])
        _need(isinstance(raw, dict) and set(raw) == {"protocol", "registration_ref", "verifier_worker_ref", "started_at",
              "finished_at", "complete", "sessions", "host", "environment"}
              and raw["protocol"] == PROTOCOL and raw["registration_ref"] == receipt["registration_ref"],
              "Task raw registration differs")
        _grid(raw, config, reader)
        _interval(raw["started_at"], raw["finished_at"])
        _need(raw["host"] == storage["host"]
              and raw["finished_at"] - storage["collection_started_at"] <= storage["timeout_seconds"],
              "Task collection exceeded its total budget or changed host")
        _need(_number(registration["created_at"]) < raw["started_at"], "Task registration postdates collection")
        previous, directories, processes = raw["started_at"], set(), set()
        for session in raw["sessions"]:
            _interval(session["started_at"], session["finished_at"], within=(previous, raw["finished_at"]))
            previous = session["finished_at"]
            _need(session["cycle_dir"] not in directories, "Task cycle directory reused")
            directories.add(session["cycle_dir"])
            bound = registration["identity"]["cases"][str(session["case_id"])]
            paths = {config["build"]["binary"], *config["build"]["receipt_files"],
                     *bound["prepared_files"], *bound["verifier_files"], profile["profiler"]}
            local = {**inventory, "files": {path: inventory["files"][path] for path in paths}}
            _need(session["identity_before"] == session["identity_after"] == local,
                  "Task source/build/input/tool identity changed")
            pid, _ = _session(reader, session, config, registration, storage)
            process = (pid, session["capture"]["started_at"])
            _need(process not in processes, "Task process identity reused")
            processes.add(process)
        shared._oracle_artifacts(reader, config, registration, None, raw)
        hardware = shared._hardware(reader, registration, raw, config)
        report = summarize_task_raw(raw, config, reader)
        _need(report["stable"] is True, "; ".join(report["reasons"]))
        _need(canonical_json(_load(reader, receipt["measurement_report_ref"])) == canonical_json(report),
              "Task measurement report differs from raw replay")
        return {"valid": True, "protocol": PROTOCOL, "metric": METRIC, "receipt_ref": receipt_ref,
                "source_hashes": receipt["source_hashes"], "config_ref": receipt["config_ref"],
                "registration_ref": receipt["registration_ref"], "hardware_ref": registration["hardware_ref"],
                "verifier_worker_ref": raw["verifier_worker_ref"], "hardware": hardware,
                "report": report, "gate_projection": report["gate_projection"]}
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OSError, ArithmeticError) as error:
        raise ContractError("measurement admission: malformed or missing Task evidence: " + str(error)) from error


def replay_task_measurement_admission(artifact_reader, receipt_ref, *, expected):
    """Current admission always verifies the current registered producer bytes."""
    return _replay_task_admission(artifact_reader, receipt_ref, expected=expected)


def replay_historical_task_measurement_admission(artifact_reader, receipt_ref, *, expected,
                                               producer_resolver):
    """Replay archived producers for history only, without a usable gate projection."""
    _need(callable(producer_resolver), "historical producer resolver is required")
    result = _replay_task_admission(artifact_reader, receipt_ref, expected=expected,
                                  producer_resolver=producer_resolver)
    result.pop("gate_projection")
    result["report"].pop("gate_projection")
    return {"replay": result, "authority": "historical_task_measurement",
            "eligible_for_publication": False}
