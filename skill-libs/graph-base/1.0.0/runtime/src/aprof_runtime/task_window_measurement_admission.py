"""Replay calibrated native-API Task Duration measurements from verified bytes.

This module has no public gate dispatch or publication authority. Historical
fixed-repeat parsers remain unchanged; all prospective evidence is replayed.
"""
from pathlib import Path, PurePosixPath
import re

from . import measurement_admission as shared
from . import task_measurement_admission as task
from .errors import ContractError
from .jsonio import canonical_json
from .profile_evidence import _json, _load
from .task_timing import protocol_commands
from .task_window_timing import case_task_config, partition_window_tasks, choose_task_repeat


PROTOCOL = "shared_buffer_msprof_task_window_v5"
METRIC = task.METRIC
HEADER_FILE = "skills/ascendc-aprof-profiling/assets/device_task_profile.h"
PRODUCER_FILES = task.PRODUCER_FILES + (
    "skills/ascendc-aprof-profiling/scripts/device_task_window_timing.py",
    "runtime/src/aprof_runtime/task_window_timing.py",
    "runtime/src/aprof_runtime/task_window_measurement_admission.py",
    "runtime/src/aprof_runtime/local_evidence.py",
    "runtime/src/aprof_runtime/measurement_entry.py",
    "runtime/src/aprof_runtime/exploration.py",
    "runtime/src/aprof_runtime/full_call_pmu.py",
    "runtime/src/aprof_runtime/episodes.py",
    HEADER_FILE,
)
_CANN = "/usr/local/Ascend/cann-9.0.0"
_ANALYSIS = _CANN + "/tools/profiler/profiler_tool/analysis"
SUMMARY_PYTHON = "/usr/local/python3.11.15/bin/python3.11"
SUMMARY_ENTRY = _ANALYSIS + "/msprof/msprof.py"
PROFILE_DEPENDENCY_PATHS = (
    _CANN + "/aarch64-linux/include/acl/acl_prof.h",
    _CANN + "/aarch64-linux/lib64/libascendcl.so",
    _CANN + "/aarch64-linux/lib64/libmsprofiler.so",
    "/usr/bin/aarch64-linux-gnu-g++-11", "/usr/bin/cmake",
    _CANN + "/tools/bisheng_compiler/bin/bisheng",
    _CANN + "/tools/profiler/bin/msprof",
    SUMMARY_PYTHON, SUMMARY_ENTRY,
    _ANALYSIS + "/msinterface/msprof_entrance.py",
    _ANALYSIS + "/msinterface/msprof_export.py",
    _ANALYSIS + "/msinterface/msprof_output_summary.py",
    _ANALYSIS + "/msinterface/msprof_data_storage.py",
    _ANALYSIS + "/framework/file_dispatch.py",
    _ANALYSIS + "/framework/collection_engine.py",
    _ANALYSIS + "/common_func/profiling_scene.py",
    _ANALYSIS + "/msinterface/msprof_c_interface.py",
    _ANALYSIS + "/common_func/cpp_enable_scene.py",
    _ANALYSIS + "/common_func/common.py",
    _ANALYSIS + "/common_func/path_manager.py",
    _ANALYSIS + "/common_func/msprof_common.py",
    _ANALYSIS + "/lib64/msprof_analysis.so", _CANN + "/set_env.sh",
)
ROLES, PHASES = shared.ROLES, shared.PHASES
_need, _number, _interval = shared._require, shared._number, shared._interval


def replay_historical_task_window_measurement_admission(artifact_reader, receipt_ref, *, expected, producer_resolver):
    """Keep all Task checks; only resolve a caller-authenticated historical producer cohort."""
    with shared.historical_producer_scope(producer_resolver):
        return replay_task_window_measurement_admission(artifact_reader, receipt_ref, expected=expected)


def _collection_stop_policy(value, total):
    if value is None:
        return None
    _need(isinstance(value, dict) and set(value) == {"kind", "reserve_seconds", "task_unit_seconds",
          "pmu_unit_seconds", "terminal_seconds"} and value["kind"] == "finish_started_unit_v1",
          "invalid frozen collection-stop policy")
    for key in ("reserve_seconds", "task_unit_seconds", "pmu_unit_seconds", "terminal_seconds"):
        _need(_number(value[key]) > 0, "invalid collection unit/terminal allowance")
    _need(max(value["task_unit_seconds"], value["pmu_unit_seconds"]) + value["terminal_seconds"]
          <= value["reserve_seconds"] < total, "collection reserve does not fit original budget")
    return value


def collection_unit_deadline(deadline, policy, kind, *, now):
    """One unit may drain after the soft cutoff, never after the original D."""
    deadline, now = _number(deadline), _number(now)
    _need(kind in ("task", "pmu"), "unknown collection unit")
    if policy is None:
        if now >= deadline:
            raise TimeoutError("original collection deadline expired")
        return deadline
    unit, terminal = policy[kind + "_unit_seconds"], policy["terminal_seconds"]
    if now >= deadline - policy["reserve_seconds"] or deadline - now < unit + terminal:
        raise TimeoutError("frozen collection soft budget reached; no new unit started")
    return min(deadline - terminal, now + unit)



def replay_collection_unit(reader, reference, *, parent_deadline, policy, kind):
    """Replay one original-budget boundary; complete raw/oracle checks stay with its caller."""
    _need(policy is not None, "collection unit receipt requires a frozen stop policy")
    unit = _load(reader, reference)
    _need(isinstance(unit, dict) and set(unit) == {"schema_version", "started_at", "started_monotonic",
          "deadline_monotonic"} and type(unit["schema_version"]) is int and unit["schema_version"] == 1,
          "collection unit boundary fields differ")
    wall, mono, deadline = (_number(unit[k]) for k in ("started_at", "started_monotonic", "deadline_monotonic"))
    try:
        expected = collection_unit_deadline(parent_deadline, policy, kind, now=mono)
    except TimeoutError as error:
        raise ContractError("measurement admission: " + str(error)) from error
    _need(deadline == expected, "collection unit changed its frozen drain deadline")
    return {**unit, "wall_deadline": wall + deadline - mono}


def replay_task_budget(reader, binding, *, expected):
    """Read the original dispatcher chain; never accept a child's budget value."""
    _need(isinstance(binding, dict) and set(binding) == {"kind", "launch_ref"}
          and binding["kind"] in ("teacher", "baseline", "validation"), "invalid Task budget binding")
    refs = {}

    def read(reference):
        pointer = reference if isinstance(reference, dict) else None
        if pointer is not None:
            _need(set(pointer) == {"path", "sha256"}, "invalid dispatcher budget pointer")
            path = Path(pointer["path"])
            _need(path.is_absolute() and str(path) == pointer["path"] and ".." not in path.parts,
                  "noncanonical dispatcher budget pointer")
            reference = pointer["sha256"]
        _need(isinstance(reference, str), "missing dispatcher budget reference")
        actual = reader.verify_artifact(reference)
        refs[reference] = str(actual)
        return _load(reader, reference)

    def budget(value):
        values = [_number(value[k]) for k in ("budget_seconds", "wall_time_limit_seconds") if k in value]
        _need(values and values[0] > 0 and all(v == values[0] for v in values),
              "missing or conflicting original budget")
        return values[0]

    launch = read(binding["launch_ref"])
    if binding["kind"] == "teacher":
        _need(set(launch) == {"schema_version", "anchor_ref", "job_ref", "started_at", "started_monotonic",
              "monotonic_deadline", "issued_monotonic", "child_timeout_seconds"}
              and launch["schema_version"] == 2, "adjustable Teacher budget needs the original v2 launch")
        origin = read(launch["anchor_ref"])
        campaign = read(origin["campaign_ref"])
        total = budget(campaign)
        policy = campaign.get("collection_stop_policy")
        _need(campaign.get("kind") == "teacher_task_rule_campaign" and budget(origin) == total
              and origin["job_ref"] == launch["job_ref"]
              and sum(all(row.get(key) == origin[key] for key in ("run_id", "candidate_id", "operator", "source_hashes"))
                      for row in campaign["attempts"]) == 1, "Teacher parent budget differs")
        job = read(launch["job_ref"])
        deadline = _number(launch["monotonic_deadline"])
        created = _number(origin["created_at"])
    else:
        _need(set(launch) == {"attempt_ref", "started_at", "started_monotonic", "deadline_monotonic",
              "issued_monotonic", "child_timeout_seconds"}, "original dispatcher launch differs")
        attempt = read(launch["attempt_ref"])
        origin = read(attempt["plan_ref"])
        job = read(origin["job_ref"])
        total = budget(origin)
        policy = origin.get("collection_stop_policy")
        _need(budget(attempt) == total, "attempt changed original budget")
        deadline = _number(launch["deadline_monotonic"])
        created = _number(attempt["created_at"])
        if binding["kind"] == "validation":
            freeze, matrix = read(origin["freeze_ref"]), read(origin["matrix_ref"])
            frozen_plan = read(freeze["plan"])
            policy = frozen_plan["equal_budget_evaluation"].get("collection_stop_policy")
            _need(origin.get("kind") == "skill_release_trial_plan"
                  and budget(frozen_plan["equal_budget_evaluation"]) == total
                  and origin["run_id"] == origin["row"]["run_id"]
                  and sum(row == origin["row"] for row in matrix["runs"]) == 1,
                  "validation budget differs from original frozen matrix")
        else:
            _need(origin.get("kind") == "task_baseline_qualification_plan"
                  and attempt.get("kind") == "baseline_task_attempt"
                  and attempt["operator"] == origin["operator"], "baseline parent budget differs")
    start, wall, issued = (_number(launch[k]) for k in ("started_monotonic", "started_at", "issued_monotonic"))
    _need(_number(job["timeout_seconds"]) == total and created <= wall
          and deadline == start + total and start <= issued < deadline
          and _number(launch["child_timeout_seconds"]) == deadline - issued,
          "dispatcher renewed or changed the original task budget")
    _need(origin["run_id"] == expected["run_id"]
          and origin.get("operator", origin.get("row", {}).get("operator")) == expected["operator"],
          "Task budget belongs to a different run/operator")
    for key in ("candidate_id", "session_id"):
        if key in origin and key in expected:
            _need(origin[key] == expected[key], "Task budget identity differs: " + key)
    policy = _collection_stop_policy(policy, total)
    if "collection_stop_policy" in origin:
        _need(origin["collection_stop_policy"] == policy, "child changed frozen collection-stop policy")
    return {"budget_seconds": total, "started_monotonic": start, "started_at": wall,
            "collection_stop_policy": policy,
            "deadline_monotonic": deadline, "wall_deadline": wall + total, "references": refs}


def storage_budget(reader, storage, config):
    """Legacy storage keeps its old ceiling; new storage is parent-bound."""
    timeout = _number(storage["timeout_seconds"])
    started = _number(storage["collection_started_at"])
    if "budget_binding" not in storage:
        _need(0 < timeout <= 3600, "invalid legacy Task storage budget")
        return {"budget_seconds": 3600, "wall_deadline": started + timeout}
    parent = replay_task_budget(reader, storage["budget_binding"], expected=config)
    mono = _number(storage["collection_started_monotonic"])
    deadline = _number(storage["deadline_monotonic"])
    _need(parent["started_monotonic"] <= mono < deadline == parent["deadline_monotonic"]
          and parent["started_at"] <= started < parent["wall_deadline"]
          and 0 < timeout <= deadline - mono and started + timeout <= parent["wall_deadline"] + .01,
          "Task collection reset the original parent deadline")
    return parent


def commands(mode):
    _need(mode in ("pilot", "confirmation"), "unknown Task window mode")
    rows = (["prime 0 pilot", "sample 1 pilot 0", "sample 2 pilot 1", "sample 3 pilot 2", "finish 4"]
            if mode == "pilot" else protocol_commands())
    return "\n".join(rows) + "\n"


def _repeat_map(value, ids):
    _need(isinstance(value, dict) and set(value) == {str(cid) for cid in ids}
          and all(type(repeat) is int and 100 <= repeat <= 100000 and repeat % 100 == 0
                  for repeat in value.values()), "invalid frozen Task repeat map")
    return value


def _grid(raw, config, reader):
    _need(isinstance(raw, dict) and raw.get("protocol") == PROTOCOL
          and raw.get("complete") is True and "error" not in raw,
          "Task window measurement is incomplete or failed")
    ids = config["expected_case_ids"]
    _need(isinstance(ids, list) and ids and all(type(cid) is int and cid > 0 for cid in ids)
          and len(set(ids)) == len(ids) and [case["case_id"] for case in config["cases"]] == ids,
          "Task window case scope differs")
    repeats = _repeat_map(raw["repeat_by_case"], ids)
    _need([(item["case_id"], item["cycle"]) for item in raw["sessions"]]
          == [(cid, cycle) for cid in ids for cycle in range(6)], "Task window session scope/order differs")
    values = {cid: [] for cid in ids}
    for session in raw["sessions"]:
        partition = _load(reader, session["partition_ref"])
        _need(session["mode"] == partition["mode"] == "confirmation"
              and partition["metric"] == METRIC and partition["operator"] == config["operator"]
              and type(session["repeat"]) is int and type(partition["repeat"]) is int
              and session["repeat"] == partition["repeat"] == repeats[str(session["case_id"])]
              and type(partition["cycle"]) is int and partition["cycle"] == session["cycle"],
              "Task window partition identity differs")
        sample = partition["values_ns_per_call"]
        _need(set(sample) == set(PHASES), "Task window phase scope differs")
        for phase in PHASES:
            _need(set(sample[phase]) == set(ROLES), "Task window role scope differs")
            for role in ROLES:
                _need(isinstance(sample[phase][role], list) and len(sample[phase][role]) == 5
                      and all(_number(value) > 0 for value in sample[phase][role]),
                      "Task window sample count/value differs")
        values[session["case_id"]].append(sample)
    return values


def summarize_task_window_raw(raw, config, artifact_reader):
    """Draft statistics only; acceptance additionally requires complete raw replay."""
    try:
        values = _grid(raw, config, artifact_reader)
        report = shared._summarize_values(values, config, protocol=PROTOCOL)
        registration = _load(artifact_reader, raw["registration_ref"])
        sources = registration["identity"]["source_hashes"]
        if sources["baseline"] == sources["candidate"]:
            for control in report["controls"]:
                for label, quality in [("overall", control["overall"]),
                                       *((f"cycle {i}", q) for i, q in enumerate(control["cycles"]))]:
                    if quality["formal"]["role_bias"] > .02:
                        report["reasons"].append(
                            f"case {control['case_id']} {label}: same-source formal A/A role bias exceeds 2%")
            if report["reasons"]:
                report.update(stable=False, speedup=None, speedup_lcb_95=None,
                              gate_projection={"baseline_samples_ns": [], "candidate_samples_ns": [],
                                               "heldout_regressions": []})
    except (ContractError, KeyError, TypeError, ValueError, IndexError, AttributeError, OSError, ArithmeticError) as error:
        report = shared._summarize_values(None, config, protocol=PROTOCOL, failure=ContractError(str(error)))
    report.update(metric=METRIC, sample_unit="case-frozen R complete calls per role; 30 formal pairs per case",
                  auxiliary_scope="Event, Host wall, task spans and gaps retained; excluded from Task gates")
    return report


def _local_storage(reader, registration, config):
    """Bind the two private local directories used by online measurement."""
    storage = _load(reader, registration["profile_storage_ref"])
    fields = {
        "schema_version", "mode", "scratch_root", "work_root", "created_at", "host", "directory_mode",
        "mountinfo_ref", "scratch_mount", "persistent_mount", "collection_started_at", "timeout_seconds"}
    if isinstance(storage, dict) and "budget_binding" in storage:
        fields |= {"budget_binding", "collection_started_monotonic", "deadline_monotonic"}
    _need(isinstance(storage, dict) and set(storage) == fields,
        "invalid Task profile storage receipt")
    scratch, work = task._path(storage["scratch_root"]), task._path(storage["work_root"])
    _need(storage["schema_version"] == 1 and storage["mode"] == "local_profile_only"
          and type(storage["directory_mode"]) is int and storage["directory_mode"] == 0o700
          and str(scratch) == config["task_profile"]["scratch_root"]
          and not scratch.is_relative_to(work) and not work.is_relative_to(scratch),
          "Task scratch/work storage differs")
    for source in [config["build"]["source_dir"], *(config["roles"][role]["source_dir"] for role in ROLES)]:
        root = task._path(source)
        _need(all(not local.is_relative_to(root) and not root.is_relative_to(local)
                  for local in (scratch, work)), "Task scratch/work overlaps frozen sources")
    mountinfo = reader.verify_artifact(storage["mountinfo_ref"]).read_text(encoding="utf-8")
    _need(storage["scratch_mount"] == task.select_mount(mountinfo, scratch)
          and storage["persistent_mount"] == task.select_mount(mountinfo, work),
          "Task registered mount differs from raw mountinfo")
    _need(all(storage[name]["filesystem_type"] in task.LOCAL_PROFILE_FILESYSTEMS
              for name in ("scratch_mount", "persistent_mount")),
          "Task scratch/work filesystem is not a supported local filesystem")
    storage_budget(reader, storage, config)
    _need(_number(storage["collection_started_at"]) <= _number(storage["created_at"])
          <= _number(registration["created_at"]), "Task storage registration time/budget differs")
    return storage


def _profile_files(reader, reference):
    files = task._profile_files(reader, reference)
    paths = {PurePosixPath(name) for name in files}
    _need(all("\x00" not in name for name in files)
          and not any(parent in paths for path in paths for parent in path.parents),
          "Task profile manifest cannot be materialized: invalid name or file/ancestor collision")
    return files


def _profile_transition(reader, captured, final):
    """Export may append to existing collection logs; captured raw is immutable."""
    _need(set(captured) <= set(final), "captured profile file was removed")
    roots = {PurePosixPath(name).parts[0] for name in captured}
    _need(len(roots) == 1 and next(iter(roots)).startswith("PROF_")
          and all(len(PurePosixPath(name).parts) > 1 for name in captured)
          and {PurePosixPath(name).parts[0] for name in final} == roots,
          "profile inventory has an ambiguous or escaping PROF scope")
    _need(not task._tables(captured), "native API capture unexpectedly contains an exported Task table")
    for name, reference in captured.items():
        if final[name] == reference:
            continue
        parts = PurePosixPath(name).parts
        append_log = (len(parts) == 3 and parts[1] == "mindstudio_profiler_log"
                      and re.fullmatch(r"collection_(host|device_[0-9]+)\.log", parts[2]))
        _need(append_log and reader.verify_artifact(final[name]).read_bytes().startswith(
            reader.verify_artifact(reference).read_bytes()), "export changed captured raw/profile bytes: " + name)
    return next(iter(roots))


def _session(reader, session, config, registration, storage):
    budget = storage_budget(reader, storage, config)
    policy = budget.get("collection_stop_policy")
    extra = {"collection_unit_ref"} if policy is not None else set()
    _need(isinstance(session, dict) and set(session) == {
        "case_id", "cycle", "mode", "repeat", "cycle_dir", "started_at", "finished_at", "identity_before",
        "identity_after", "capture", "export", "commands_ref", "task_table_ref", "native_messages_ref",
        "partition_ref", "output_hashes", "verifications", "control_summary", "capture_files_ref",
        "profile_files_ref"} | extra, "Task window session fields differ")
    mode, cycle, repeat = session["mode"], session["cycle"], session["repeat"]
    _need(mode in ("pilot", "confirmation") and type(cycle) is int
          and (cycle == 0 if mode == "pilot" else 0 <= cycle < 6)
          and type(repeat) is int
          and repeat == (100 if mode == "pilot" else registration["repeat_by_case"][str(session["case_id"])]),
          "Task window session mode/cycle/repeat differs")
    basename = (f"case-{session['case_id']:02d}-pilot" if mode == "pilot"
                else f"case-{session['case_id']:02d}-cycle-{cycle}")
    directory = task._path(session["cycle_dir"])
    _need(directory == task._path(storage["work_root"]) / basename,
          "Task window work directory differs")
    profile = task._path(storage["scratch_root"]) / basename / "profile"
    command_path = directory / "commands.txt"
    _need(reader.verify_artifact(session["commands_ref"]).read_text(encoding="utf-8") == commands(mode),
          "Task window native command file differs")
    environment = {"APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(cycle),
                   "APROF_SHARED_MODE": mode, "APROF_SHARED_REPEAT": str(repeat),
                   "APROF_SHARED_COMMANDS": str(command_path), "APROF_TASK_PROFILE_DIR": str(profile)}
    case = next(case for case in config["cases"] if case["case_id"] == session["case_id"])
    argv = shared._expanded(case["command"], str(directory))
    _need(argv[0] == config["build"]["binary"], "Task window callback binary differs")
    command_cap, unit_deadline = budget["budget_seconds"], budget["wall_deadline"]
    if "budget_binding" in storage:
        _need(session["finished_at"] <= budget["wall_deadline"], "Task session exceeded original budget")
        if policy is not None:
            unit = replay_collection_unit(reader, session["collection_unit_ref"],
                parent_deadline=budget["deadline_monotonic"], policy=policy, kind="task")
            _need(unit["started_at"] == session["started_at"]
                  and storage["collection_started_monotonic"] <= unit["started_monotonic"],
                  "Task unit is not bound to the actual session boundary")
            command_cap, unit_deadline = policy["task_unit_seconds"], unit["wall_deadline"]
            _need(session["finished_at"] <= unit_deadline + .01, "Task unit exceeded its frozen drain allowance")
    finished = task._execution(reader, session["capture"], argv=argv, cwd=config["build"]["source_dir"],
        environment=environment, earliest=session["started_at"], latest=session["finished_at"],
        timeout_cap=command_cap, deadline=unit_deadline if "budget_binding" in storage else None)
    captured = _profile_files(reader, session["capture_files_ref"])
    files = _profile_files(reader, session["profile_files_ref"])
    prof_name = _profile_transition(reader, captured, files)
    export_argv = [SUMMARY_PYTHON, SUMMARY_ENTRY, "export", "summary", "-dir",
                   str(profile / prof_name), "--format", "csv"]
    finished = task._execution(reader, session["export"], argv=export_argv, cwd=config["build"]["source_dir"],
        environment={}, earliest=finished, latest=session["finished_at"],
        timeout_cap=command_cap, deadline=unit_deadline if "budget_binding" in storage else None)
    tables = task._tables(files)
    _need(len(tables) == 1 and files[tables[0]] == session["task_table_ref"],
          "Task window table is absent or ambiguous")
    messages = []
    for line in reader.verify_artifact(session["capture"]["stdout_hash"]).read_text(encoding="utf-8").splitlines():
        if line.startswith("APROF_SHARED_TIMING_JSON:"):
            messages.append(_json(line[len("APROF_SHARED_TIMING_JSON:"):]))
        elif "APROF_SHARED_TIMING" in line:
            raise ContractError("measurement admission: malformed Task window native stdout")
    _need(_load(reader, session["native_messages_ref"]) == messages, "Task window stdout payload differs")
    selected_config = case_task_config(config, session["case_id"])
    partition = partition_window_tasks(table_path=reader.verify_artifact(session["task_table_ref"]),
        messages=messages, config=selected_config, mode=mode, cycle=cycle, repeat=repeat,
        role_kernel_names=selected_config["task_profile"]["role_kernel_names"])
    ready = messages[0]
    _need(ready["pid"] == session["capture"]["pid"] and ready["device"] == config["device"]
          and ready["cpu_affinity"] == registration["cpu_affinity"],
          "Task window native process/device/affinity differs")
    _need(canonical_json(_load(reader, session["partition_ref"])) == canonical_json(partition),
          "Task window partition differs from complete raw replay")
    controls = None if mode == "pilot" else shared._phase_controls(partition["values_ns_per_call"])
    _need(session["control_summary"] == controls, "Task window controls differ from raw replay")
    shared._output_artifacts(reader, session, config, after=finished)
    return partition


def replay_task_window_measurement_admission(artifact_reader, receipt_ref, *, expected):
    """Replay this prospective protocol only; no hardware/publication qualification."""
    reader = artifact_reader
    try:
        receipt = _load(reader, receipt_ref)
        _need(isinstance(receipt, dict) and set(receipt) == {
            "schema_version", "protocol", "run_id", "session_id", "candidate_id", "operator", "source_hashes",
            "registration_ref", "config_ref", "raw_ref", "measurement_report_ref"}
            and receipt["schema_version"] == "1.0.0" and receipt["protocol"] == PROTOCOL,
            "unsupported Task window admission receipt")
        for key, value in expected.items():
            _need(receipt.get(key) == value, "Task window receipt " + key + " differs")
        config = shared._config_identity(reader, receipt, extra_fields=("task_profile",),
                                         case_launch_counts=True)
        profile = config["task_profile"]
        _need(isinstance(profile, dict) and set(profile) == {"profiler", "role_kernel_names", "scratch_root"}
              and profile["profiler"] == _CANN + "/tools/profiler/bin/msprof", "Task window profile config differs")
        task._path(profile["scratch_root"])
        case_task_config(config)  # Validate every registered case, not only the current session.
        registration = _load(reader, receipt["registration_ref"])
        _need(isinstance(registration, dict) and set(registration) == {
            "protocol", "created_at", "config_ref", "identity", "inventory", "producer_files", "attempt_policy",
            "cycles", "pairs_per_phase", "warmup", "prime_repeat", "cpu_affinity", "hardware_ref",
            "verifier_request_plan_ref", "profiler_ref", "task_profile", "profile_storage_ref",
            "calibration_ref", "repeat_by_case", "profile_dependency_refs"},
            "Task window registration fields differ")
        for key, value in {"protocol": PROTOCOL, "config_ref": receipt["config_ref"], "task_profile": profile,
                           "attempt_policy": "exactly_once_no_resume_no_resampling", "cycles": 6,
                           "pairs_per_phase": 5, "warmup": 10, "prime_repeat": 100}.items():
            _need(type(registration.get(key)) is type(value) and registration[key] == value,
                  "Task window registration " + key + " differs")
        repeats = _repeat_map(registration["repeat_by_case"], config["expected_case_ids"])
        dependencies = registration["profile_dependency_refs"]
        _need(isinstance(dependencies, dict) and set(dependencies) == set(PROFILE_DEPENDENCY_PATHS)
              and dependencies[profile["profiler"]] == registration["profiler_ref"],
              "Task window SDK/export dependency inventory differs")
        inventory = shared._registered_identity(reader, receipt, config, registration,
            producer_files=PRODUCER_FILES, extra_files=dependencies)
        headers = [reference for path, reference in inventory["build_sources"].items()
                   if PurePosixPath(path).name == "device_task_profile.h"]
        _need(headers == [registration["producer_files"][HEADER_FILE]],
              "Task window build lacks exactly the trusted native profiling header")
        storage = _local_storage(reader, registration, config)
        calibration = _load(reader, registration["calibration_ref"])
        _need(isinstance(calibration, dict) and set(calibration) == {
            "schema_version", "protocol", "config_ref", "started_at", "finished_at", "host", "cases"}
            and type(calibration["schema_version"]) is int and calibration["schema_version"] == 1
            and calibration["protocol"] == PROTOCOL and calibration["config_ref"] == receipt["config_ref"]
            and [item["case_id"] for item in calibration["cases"]] == config["expected_case_ids"],
            "Task window calibration scope/config differs")
        _interval(calibration["started_at"], calibration["finished_at"])
        _need(storage["created_at"] <= calibration["started_at"]
              and calibration["finished_at"] < registration["created_at"],
              "Task calibration was not frozen before confirmation registration")
        raw = _load(reader, receipt["raw_ref"])
        _need(isinstance(raw, dict) and set(raw) == {
            "protocol", "registration_ref", "calibration_ref", "repeat_by_case", "verifier_worker_ref",
            "started_at", "finished_at", "complete", "sessions", "host", "environment"}
            and raw["registration_ref"] == receipt["registration_ref"]
            and raw["calibration_ref"] == registration["calibration_ref"] and raw["repeat_by_case"] == repeats,
            "Task window raw registration/calibration differs")
        _grid(raw, config, reader)
        _interval(raw["started_at"], raw["finished_at"])
        _need(registration["created_at"] < raw["started_at"]
              and raw["host"] == calibration["host"] == storage["host"]
              and raw["finished_at"] - storage["collection_started_at"] <= storage["timeout_seconds"],
              "Task window collection chronology/host/total budget differs")
        directories, processes = set(), set()

        def replay_session(session):
            bound = registration["identity"]["cases"][str(session["case_id"]) ]
            paths = {config["build"]["binary"], *config["build"]["receipt_files"],
                     *bound["prepared_files"], *bound["verifier_files"], *dependencies}
            local = {**inventory, "files": {path: inventory["files"][path] for path in paths}}
            _need(session["identity_before"] == session["identity_after"] == local,
                  "Task window source/build/input/SDK identity changed")
            _need(session["cycle_dir"] not in directories, "Task window directory reused")
            directories.add(session["cycle_dir"])
            partition = _session(reader, session, config, registration, storage)
            process = (session["capture"]["pid"], session["capture"]["started_at"])
            _need(process not in processes, "Task window process reused")
            processes.add(process)
            return partition

        previous = calibration["started_at"]
        for item in calibration["cases"]:
            _need(isinstance(item, dict) and set(item) == {
                "case_id", "repeat", "median_100_calls_ns_decimal", "pilot", "case_ref"}
                and item["pilot"]["case_id"] == item["case_id"] and item["pilot"]["mode"] == "pilot",
                "Task window pilot case binding differs")
            _need(_load(reader, item["case_ref"]) == {key: value for key, value in item.items() if key != "case_ref"},
                  "Task window per-case calibration receipt differs")
            pilot = item["pilot"]
            _interval(pilot["started_at"], pilot["finished_at"], within=(previous, calibration["finished_at"]))
            previous = pilot["finished_at"]
            selected = choose_task_repeat(replay_session(pilot))
            _need(type(item["repeat"]) is int and item["repeat"] == selected["repeat"] == repeats[str(item["case_id"])]
                  and item["median_100_calls_ns_decimal"] == selected["median_100_calls_ns_decimal"],
                  "Task window frozen repeat/median differs from three baseline Task samples")
        previous = raw["started_at"]
        for session in raw["sessions"]:
            _interval(session["started_at"], session["finished_at"], within=(previous, raw["finished_at"]))
            previous = session["finished_at"]
            replay_session(session)
        shared._oracle_artifacts(reader, config, registration, calibration, raw)
        hardware = shared._hardware(reader, registration, raw, config)
        _need(hardware["probe"]["ended_at"] <= calibration["started_at"], "Task hardware probe postdates pilot start")
        report = summarize_task_window_raw(raw, config, reader)
        _need(report["stable"] is True, "; ".join(report["reasons"]))
        _need(canonical_json(_load(reader, receipt["measurement_report_ref"])) == canonical_json(report),
              "Task window report differs from complete raw replay")
        return {"valid": True, "protocol": PROTOCOL, "metric": METRIC, "receipt_ref": receipt_ref,
                "source_hashes": receipt["source_hashes"], "config_ref": receipt["config_ref"],
                "registration_ref": receipt["registration_ref"], "hardware_ref": registration["hardware_ref"],
                "calibration_ref": registration["calibration_ref"], "repeat_by_case": repeats,
                "verifier_worker_ref": raw["verifier_worker_ref"], "hardware": hardware,
                "report": report, "gate_projection": report["gate_projection"],
                "eligible_for_publication": False, "authority": "prospective measurement replay only"}
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OSError, ArithmeticError) as error:
        raise ContractError("measurement admission: malformed or missing Task window evidence: " + str(error)) from error
