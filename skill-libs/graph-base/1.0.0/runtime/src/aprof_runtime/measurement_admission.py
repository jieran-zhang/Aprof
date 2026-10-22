"""Package-local CAS replay for shared-buffer measurement evidence.

Measurement integrity does not establish a gain or qualify a release. The
unchanged performance gate and independent publication acceptance remain due.
"""
from __future__ import annotations

import math
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
import statistics
import struct

from .contracts import GateEvidence, SourceHashes
from .errors import ContractError
from .jsonio import canonical_json, file_hash, to_primitive
from .profile_evidence import _json, _load


PROTOCOL = "shared_buffer_acl_event_v2"
ORACLE_PROTOCOL = "persistent_python_oracle_v1"
ROLES = ("baseline", "candidate")
PHASES = ("aa_before", "formal", "aa_after")
PRODUCER_FILES = (
    "skills/ascendc-aprof-profiling/scripts/device_shared_timing.py",
    "skills/ascendc-aprof-profiling/scripts/device_paired_timing.py",
    "skills/ascendc-aprof-profiling/scripts/profile_capture.py",
    "skills/ascendc-aprof-profiling/scripts/persistent_oracle.py",
    "skills/ascendc-aprof-profiling/assets/device_shared_timing.h",
    "runtime/src/aprof_runtime/jsonio.py",
    "runtime/src/aprof_runtime/profile_evidence.py",
    "runtime/src/aprof_runtime/measurement_admission.py",
    "runtime/src/aprof_runtime/gates.py",
    "runtime/src/aprof_runtime/contracts.py",
)
_HISTORICAL_PRODUCER_RESOLVER = ContextVar('aprof_historical_producer_resolver', default=None)


@contextmanager
def historical_producer_scope(producer_resolver):
    """Trusted read-only callers may resolve an explicitly reviewed old cohort.

    The caller must authenticate the complete producer inventory and its archive
    before entering. Bytes still undergo the same hash checks. Ordinary replay
    remains release-local; context-local state is always restored, including on failure.
    """
    if not callable(producer_resolver):
        raise ContractError('historical producer resolver is required')
    token = _HISTORICAL_PRODUCER_RESOLVER.set(producer_resolver)
    try:
        yield
    finally:
        _HISTORICAL_PRODUCER_RESOLVER.reset(token)


def _require(condition, message):
    if not condition:
        raise ContractError("measurement admission: " + message)


def _number(value):
    _require(type(value) in (int, float) and math.isfinite(value), "non-finite or nonnumeric value")
    return value


def _interval(start, finish, *, within=None):
    _require(_number(start) <= _number(finish), "reversed execution interval")
    if within:
        _require(within[0] <= start <= finish <= within[1], "execution outside registered session")


def _cv(values):
    return statistics.stdev(values) / statistics.fmean(values)


def _geomean(values):
    return math.exp(statistics.fmean(math.log(value) for value in values))


def _control(a, b):
    return {"role_bias": abs(_geomean([y / x for x, y in zip(a, b, strict=True)]) - 1),
            "baseline_cv": _cv(a), "candidate_cv": _cv(b)}


def _release_root():
    """Resolve the importing release, including its version-local virtualenv."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        source = parent / "runtime/src/aprof_runtime/measurement_admission.py"
        if (parent / "skills/ascendc-aprof-profiling").is_dir() and source.is_file():
            _require(file_hash(source) == file_hash(here), "installed runtime differs from its release")
            return parent
    raise ContractError("measurement admission requires its independently installed skill release")


def _source_files(reader, reference):
    bundle = _load(reader, reference)
    _require(isinstance(bundle, dict) and set(bundle) == {"schema_version", "files"}
             and bundle["schema_version"] == "1.0.0", "invalid source bundle")
    files = bundle["files"]
    _require(isinstance(files, dict) and files, "source bundle is empty")
    for path, digest in files.items():
        p = PurePosixPath(path)
        _require(isinstance(path, str) and not p.is_absolute() and ".." not in p.parts
                 and str(p) == path and path != ".", "source path is not canonical relative")
        reader.verify_artifact(digest)
    return files


def _verifier_paths(case):
    paths = set()
    for command in case["verify_commands"].values():
        for index, token in enumerate(command):
            if index == 0 or ("{cycle_dir}" not in token and Path(token).suffix in {".py", ".sh"}):
                paths.add(token)
    return paths


def _config_identity(reader, receipt, *, extra_fields=(), case_launch_counts=False):
    config = _load(reader, receipt["config_ref"])
    _require(isinstance(config, dict) and set(config) == {"schema_version", "operator", "run_id", "session_id", "candidate_id",
             "device", "physical_device", "expected_case_ids", "roles", "build", "cases"}
             | set(extra_fields)
             and config["schema_version"] == "1.0.0", "invalid caller config")
    for key in ("run_id", "session_id", "candidate_id", "operator"):
        _require(isinstance(config.get(key), str) and config[key].strip() and config[key] == receipt[key],
                 "config " + key + " differs")
    for key in ("device", "physical_device"):
        _require(type(config[key]) is int and config[key] >= 0, "invalid " + key)
    ids = config.get("expected_case_ids")
    _require(isinstance(ids, list) and ids and all(type(cid) is int and cid > 0 for cid in ids)
             and len(ids) == len(set(ids)), "invalid expected case scope")
    cases = config.get("cases")
    _require(isinstance(cases, list) and [case.get("case_id") for case in cases] == ids,
             "config case scope differs")
    _require(set(config.get("roles", {})) == set(ROLES), "both source roles are required")
    for role in ROLES:
        definition = config["roles"][role]
        count = definition.get("launches_per_operator")
        valid_count = (isinstance(count, dict) and set(count) == {str(cid) for cid in ids}
                       and all(type(value) is int and value > 0 for value in count.values())
                       if case_launch_counts else type(count) is int and count > 0)
        _require(set(definition) == {"source_dir", "symbol", "launches_per_operator"}
                 and isinstance(definition.get("symbol"), str) and definition["symbol"]
                 and valid_count, "invalid callback binding")
    _require(config["roles"]["baseline"]["symbol"] != config["roles"]["candidate"]["symbol"],
             "formal callbacks must have distinct source symbols")
    return config


def _registered_identity(reader, receipt, config, registration, *, producer_files=PRODUCER_FILES,
                         producer_resolver=None, extra_files=None):
    producers = registration.get("producer_files")
    _require(isinstance(producers, dict) and set(producers) == set(producer_files), "producer inventory differs")
    root = _release_root()
    if producer_resolver is None:
        producer_resolver = _HISTORICAL_PRODUCER_RESOLVER.get()
    for path, reference in producers.items():
        reader.verify_artifact(reference)
        producer = root / path if producer_resolver is None else producer_resolver(root / path, reference)
        _require(file_hash(producer) == reference, "untrusted producer bytes: " + path)
    identity = registration.get("identity", {})
    sources = identity.get("source_hashes")
    _require(sources == receipt["source_hashes"] and set(sources) == set(ROLES), "source identity differs")
    source_files = {role: _source_files(reader, sources[role]) for role in ROLES}
    build = identity["build"]
    build_files = _source_files(reader, build["source_ref"])
    headers = [reference for path, reference in build_files.items() if PurePosixPath(path).name == "device_shared_timing.h"]
    _require(headers == [producers["skills/ascendc-aprof-profiling/assets/device_shared_timing.h"]],
             "build does not contain exactly the trusted shared timing header")
    reader.verify_artifact(build["binary_ref"])
    _require(set(config["build"]) == {"source_dir", "binary", "receipt_files"}
             and isinstance(config["build"]["receipt_files"], list) and config["build"]["receipt_files"],
             "missing build receipts")
    _require(set(build["receipt_refs"]) == set(config["build"]["receipt_files"]), "build receipt scope differs")
    files = {config["build"]["binary"]: build["binary_ref"], **build["receipt_refs"]}
    for path, reference in (extra_files or {}).items():
        reader.verify_artifact(reference)
        _require(path not in files or files[path] == reference, "conflicting tool identity")
        files[path] = reference
    for reference in build["receipt_refs"].values():
        reader.verify_artifact(reference)
    _require(set(identity["cases"]) == {str(cid) for cid in config["expected_case_ids"]}, "registered case scope differs")
    for case in config["cases"]:
        _require(set(case) == {"case_id", "workload", "prepared_files", "command", "verify_commands", "output_files"}
                 and isinstance(case["workload"], dict) and case["workload"]
                 and isinstance(case["prepared_files"], list) and case["prepared_files"]
                 and len(case["prepared_files"]) == len(set(case["prepared_files"]))
                 and set(case["verify_commands"]) == set(ROLES) and set(case["output_files"]) == set(ROLES),
                 "incomplete case/input/oracle scope")
        bound = identity["cases"][str(case["case_id"])]
        _require(_load(reader, bound["workload_ref"]) == case["workload"], "workload differs")
        _require(set(bound["prepared_files"]) == set(case["prepared_files"]), "input/oracle scope differs")
        _require(set(bound["verifier_files"]) == _verifier_paths(case), "verifier program scope differs")
        for group in (bound["prepared_files"], bound["verifier_files"]):
            for path, reference in group.items():
                reader.verify_artifact(reference)
                _require(path not in files or files[path] == reference, "conflicting file identity")
                files[path] = reference
    inventory = {"files": files, "sources": source_files, "build_sources": build_files, "producer_files": producers}
    _require(registration.get("inventory") == inventory, "registered inventory does not reproduce CAS identities")
    return inventory


def _outer_evidence(reader, receipt_ref, expected, *, producer_resolver=None):
    """Replay immutable identities without importing or executing a producer."""
    receipt = _load(reader, receipt_ref)
    fields = {"schema_version", "protocol", "run_id", "session_id", "candidate_id", "operator", "source_hashes",
              "registration_ref", "config_ref", "raw_ref", "measurement_report_ref"}
    _require(isinstance(receipt, dict) and set(receipt) == fields
             and receipt["schema_version"] == "1.0.0" and receipt["protocol"] == PROTOCOL,
             "unsupported admission receipt")
    for key, value in expected.items():
        _require(receipt.get(key) == value, "receipt " + key + " differs from gate identity")
    config = _config_identity(reader, receipt)
    ids, cases = config["expected_case_ids"], config["cases"]
    registration = _load(reader, receipt["registration_ref"])
    _require(isinstance(registration, dict) and set(registration) == {
             "protocol", "created_at", "config_ref", "identity", "inventory", "producer_files",
             "attempt_policy", "cycles", "pairs_per_phase", "warmup", "prime_repeat",
             "cpu_affinity", "hardware_ref", "calibration_ref", "repeat_by_case",
             "verifier_request_plan_ref"}
             and registration.get("protocol") == PROTOCOL
             and registration.get("config_ref") == receipt["config_ref"],
             "registration is not bound to this protocol/config")
    for key, value in {"cycles": 6, "pairs_per_phase": 5, "warmup": 10, "prime_repeat": 100,
                       "attempt_policy": "exactly_once_no_resume_no_resampling"}.items():
        _require(type(registration.get(key)) is type(value) and registration[key] == value,
                 "registered " + key + " differs from the fixed protocol")
    repeats = registration.get("repeat_by_case")
    _require(isinstance(repeats, dict) and set(repeats) == {str(cid) for cid in ids}
             and all(type(value) is int and 100 <= value <= 100000 and value % 100 == 0
                     for value in repeats.values()), "invalid frozen per-case repeat")
    _require(isinstance(registration.get("calibration_ref"), str)
             and isinstance(registration.get("verifier_request_plan_ref"), str),
             "missing frozen calibration or verifier plan")
    inventory = _registered_identity(reader, receipt, config, registration,
                                     producer_resolver=producer_resolver)
    files, identity = inventory["files"], registration["identity"]
    calibration = _load(reader, registration["calibration_ref"])
    _require(isinstance(calibration, dict) and set(calibration) == {
             "schema_version", "protocol", "config_ref", "started_at", "finished_at", "host", "cases"}
             and calibration["schema_version"] == "1.0.0" and calibration["protocol"] == PROTOCOL
             and calibration["config_ref"] == receipt["config_ref"], "invalid frozen calibration")
    _interval(calibration["started_at"], calibration["finished_at"])
    _require(_number(calibration["finished_at"]) < _number(registration["created_at"]),
             "calibration was not frozen before registration")
    _require(isinstance(calibration["cases"], list)
             and [item.get("case_id") for item in calibration["cases"]] == ids,
             "pilot case scope/order differs")
    raw = _load(reader, receipt["raw_ref"])
    _require(isinstance(raw, dict) and set(raw) == {
             "protocol", "registration_ref", "calibration_ref", "repeat_by_case",
             "verifier_worker_ref", "started_at", "finished_at", "complete", "sessions",
             "host", "environment"}
             and raw.get("protocol") == PROTOCOL
             and raw.get("registration_ref") == receipt["registration_ref"],
             "raw registration differs")
    _require(raw.get("calibration_ref") == registration["calibration_ref"]
             and raw.get("repeat_by_case") == repeats
             and isinstance(raw.get("verifier_worker_ref"), str),
             "raw calibration or verifier worker differs")
    _require(raw.get("complete") is True and "error" not in raw, "raw measurement is incomplete or failed")
    _interval(raw["started_at"], raw["finished_at"])
    _require(_number(registration["created_at"]) < raw["started_at"], "registration postdates collection")
    _require(calibration["host"] == raw.get("host"), "pilot and confirmation host differs")
    sessions = raw.get("sessions")
    _require(isinstance(sessions, list) and [(item.get("case_id"), item.get("cycle")) for item in sessions]
             == [(cid, cycle) for cid in ids for cycle in range(6)], "session scope/order differs")
    previous = raw["started_at"]
    for session in sessions:
        _interval(session["started_at"], session["finished_at"], within=(previous, raw["finished_at"]))
        previous = session["finished_at"]
        case = next(case for case in cases if case["case_id"] == session["case_id"])
        bound = identity["cases"][str(case["case_id"])]
        paths = {config["build"]["binary"], *config["build"]["receipt_files"],
                 *bound["prepared_files"], *bound["verifier_files"]}
        local_inventory = {**inventory, "files": {path: files[path] for path in paths}}
        _require(session.get("identity_before") == local_inventory and session.get("identity_after") == local_inventory,
                 "case source/build/input/oracle identity changed")
    return receipt, config, registration, calibration, raw


def _address(value):
    _require(isinstance(value, str) and value.isdecimal() and str(int(value)) == value
             and 0 < int(value) < 2 ** 64, "invalid context/stream/buffer address")
    return int(value)


def _buffers(value):
    _require(isinstance(value, dict) and set(value) == {"inputs", "outputs", "workspaces"}, "invalid buffer groups")
    names, spans = set(), []
    for name in ("inputs", "outputs", "workspaces"):
        group = value[name]
        _require(isinstance(group, list) and (group or name == "workspaces"), "missing shared buffers")
        for span in group:
            _require(isinstance(span, dict) and set(span) == {"name", "address", "bytes"}, "invalid buffer span")
            _require(isinstance(span["name"], str) and span["name"] and span["name"] not in names, "duplicate buffer name")
            begin = _address(span["address"])
            size = span["bytes"]
            _require(type(size) is int and size > 0 and begin + size < 2 ** 64, "invalid buffer size")
            _require(all(begin + size <= other or end <= begin for other, end in spans), "shared buffers overlap")
            names.add(span["name"])
            spans.append((begin, begin + size))


_COMMON_FIELDS = {"schema_version", "protocol", "kind", "operator", "cycle_index", "pid", "device",
                  "context_address", "stream_address", "warmup", "repeat", "prime_repeat", "execution_mode",
                  "launches_per_operator", "role_symbols", "buffers", "mode", "warmup_role_counts"}


def _session_samples(session, config, expected_repeat=None):
    """Replay the one fixed header state machine, including callback selection."""
    ready = session["ready"]
    cycle = session["cycle"]
    _require(session.get("mode") == "confirmation" and type(cycle) is int and 0 <= cycle < 6,
             "invalid confirmation mode or cycle index")
    _require(isinstance(ready, dict) and set(ready) == _COMMON_FIELDS | {
        "warmup_started_monotonic_ns", "warmup_finished_monotonic_ns", "cpu_affinity"}, "invalid READY fields")
    if expected_repeat is None:
        expected_repeat = ready.get("repeat")
    _require(type(expected_repeat) is int and 100 <= expected_repeat <= 100000
             and expected_repeat % 100 == 0, "invalid confirmation repeat")
    expected = {"schema_version": "1.0.0", "protocol": PROTOCOL, "kind": "ready", "operator": config["operator"],
                "cycle_index": cycle, "pid": session["execution"]["pid"], "device": config["device"],
                "warmup": 10, "repeat": expected_repeat, "prime_repeat": 100, "execution_mode": "direct_enqueue",
                "mode": "confirmation", "warmup_role_counts": {"baseline": 10, "candidate": 10},
                "launches_per_operator": {role: config["roles"][role]["launches_per_operator"] for role in ROLES},
                "role_symbols": {role: config["roles"][role]["symbol"] for role in ROLES}}
    for key, value in expected.items():
        _require(type(ready.get(key)) is type(value) and canonical_json(ready[key]) == canonical_json(value),
                 "READY " + key + " differs")
    _require(type(ready["pid"]) is int and ready["pid"] > 0, "invalid process identity")
    _address(ready["context_address"])
    _address(ready["stream_address"])
    _buffers(ready["buffers"])
    affinity = ready["cpu_affinity"]
    _require(isinstance(affinity, list) and affinity and all(type(cpu) is int and cpu >= 0 for cpu in affinity)
             and affinity == sorted(set(affinity)), "invalid CPU affinity")
    _interval(ready["warmup_started_monotonic_ns"], ready["warmup_finished_monotonic_ns"])
    previous = ready["warmup_finished_monotonic_ns"]
    events = session["events"]
    _require(isinstance(events, list) and len(events) == 19, "cycle must contain three primes, fifteen pairs and completion")
    values = {phase: {role: [] for role in ROLES} for phase in PHASES}
    common = {key: ready[key] for key in _COMMON_FIELDS - {"kind"}}
    for index, event in enumerate(events):
        _require(isinstance(event, dict) and set(event) == {"request_monotonic_ns", "response_monotonic_ns", "message"},
                 "invalid command receipt")
        start, finish = event["request_monotonic_ns"], event["response_monotonic_ns"]
        _interval(start, finish)
        _require(previous <= start < finish, "command chronology differs")
        previous = finish
        message = event["message"]
        _require(isinstance(message, dict) and all(type(message.get(key)) is type(value)
                                                 and canonical_json(message[key]) == canonical_json(value)
                                                 for key, value in common.items()), "process/context/stream/buffer/callback identity changed")
        _require(type(message.get("command_index")) is int and message["command_index"] == index,
                 "command index differs")
        if index == 18:
            fields = _COMMON_FIELDS | {"command_index", "untimed_verifications", "input_bytes_unchanged", "pairs_per_phase"}
            _require(set(message) == fields and message["kind"] == "complete"
                     and message["input_bytes_unchanged"] is True
                     and type(message["pairs_per_phase"]) is int and message["pairs_per_phase"] == 5,
                     "incomplete cycle or mutated input")
            verifications = message["untimed_verifications"]
            _require(isinstance(verifications, list) and len(verifications) == 2, "both untimed callbacks are required")
            cursor = start
            for role, record in zip(ROLES, verifications, strict=True):
                _require(set(record) == {"role", "implementation", "started_monotonic_ns", "finished_monotonic_ns", "scope"}
                         and record["role"] == record["implementation"] == role
                         and record["scope"] == "untimed_callback_verification", "untimed output callback differs")
                _interval(record["started_monotonic_ns"], record["finished_monotonic_ns"], within=(cursor, finish))
                cursor = record["finished_monotonic_ns"]
            continue
        phase, local = PHASES[index // 6], index % 6
        _require(message.get("phase") == phase, "phase order differs")
        _interval(message["started_monotonic_ns"], message["finished_monotonic_ns"], within=(start, finish))
        fields = _COMMON_FIELDS | {"command_index", "phase", "started_monotonic_ns", "finished_monotonic_ns"}
        if local == 0:
            order = list(ROLES if cycle % 2 == 0 else reversed(ROLES))
            _require(set(message) == fields | {"prime_order"} and message["kind"] == "prime"
                     and message["prime_order"] == [order[0], order[1], order[1], order[0]], "phase prime order differs")
            continue
        pair = local - 1
        order = list(ROLES if (cycle + pair) % 2 == 0 else reversed(ROLES))
        _require(set(message) == fields | {"pair_index", "order", *ROLES} and message["kind"] == "pair"
                 and type(message["pair_index"]) is int and message["pair_index"] == pair
                 and message["order"] == order, "pair scope/order differs")
        cursor = message["started_monotonic_ns"]
        for role in order:
            sample = message[role]
            implementation = role if phase == "formal" else "baseline"
            _require(set(sample) == {"implementation", "launches_per_operator", "elapsed_ms", "elapsed_ns",
                                    "started_monotonic_ns", "finished_monotonic_ns", "cpu_before", "cpu_after"},
                     "invalid sample fields")
            _require(sample["implementation"] == implementation
                     and type(sample["launches_per_operator"]) is int
                     and sample["launches_per_operator"] == config["roles"][implementation]["launches_per_operator"],
                     "sample callback or complete-operator launch count differs")
            _interval(sample["started_monotonic_ns"], sample["finished_monotonic_ns"],
                      within=(cursor, message["finished_monotonic_ns"]))
            cursor = sample["finished_monotonic_ns"]
            for key in ("cpu_before", "cpu_after"):
                _require(type(sample[key]) is int and sample[key] in affinity, "sample CPU outside recorded affinity")
            milliseconds, nanoseconds = _number(sample["elapsed_ms"]), _number(sample["elapsed_ns"])
            _require(milliseconds > 0 and nanoseconds > 0
                     and struct.unpack("f", struct.pack("f", milliseconds))[0] == milliseconds
                     and math.isclose(nanoseconds, milliseconds * 1e6 / expected_repeat, rel_tol=1e-12, abs_tol=1e-12),
                     "sample event units/repeat conversion differs")
            values[phase][role].append(nanoseconds)
    _require(all(len(values[phase][role]) == 5 for phase in PHASES for role in ROLES), "phase sample count differs")
    return values


def _pilot_samples(pilot, config):
    """Replay one independent baseline timing process before repeat is frozen."""
    ready = pilot["ready"]
    _require(pilot.get("mode") == "pilot" and pilot.get("cycle") == 0
             and isinstance(ready, dict) and set(ready) == _COMMON_FIELDS | {
                 "warmup_started_monotonic_ns", "warmup_finished_monotonic_ns", "cpu_affinity"},
             "invalid pilot READY fields")
    expected = {"schema_version": "1.0.0", "protocol": PROTOCOL, "kind": "ready",
                "operator": config["operator"], "cycle_index": 0, "pid": pilot["execution"]["pid"],
                "device": config["device"], "warmup": 10, "repeat": 100, "prime_repeat": 100,
                "execution_mode": "direct_enqueue", "mode": "pilot",
                "warmup_role_counts": {"baseline": 20, "candidate": 0},
                "launches_per_operator": {role: config["roles"][role]["launches_per_operator"] for role in ROLES},
                "role_symbols": {role: config["roles"][role]["symbol"] for role in ROLES}}
    for key, value in expected.items():
        _require(type(ready.get(key)) is type(value) and canonical_json(ready[key]) == canonical_json(value),
                 "pilot READY " + key + " differs")
    _address(ready["context_address"])
    _address(ready["stream_address"])
    _buffers(ready["buffers"])
    affinity = ready["cpu_affinity"]
    _require(isinstance(affinity, list) and affinity and all(type(cpu) is int and cpu >= 0 for cpu in affinity)
             and affinity == sorted(set(affinity)), "invalid pilot CPU affinity")
    _interval(ready["warmup_started_monotonic_ns"], ready["warmup_finished_monotonic_ns"])
    events = pilot["events"]
    _require(isinstance(events, list) and len(events) == 5, "pilot requires prime, three samples and completion")
    common = {key: ready[key] for key in _COMMON_FIELDS - {"kind"}}
    previous = ready["warmup_finished_monotonic_ns"]
    samples = []
    for index, event in enumerate(events):
        _require(isinstance(event, dict) and set(event) == {
                 "request_monotonic_ns", "response_monotonic_ns", "message"}, "invalid pilot command receipt")
        start, finish = event["request_monotonic_ns"], event["response_monotonic_ns"]
        _interval(start, finish)
        _require(previous <= start < finish, "pilot command chronology differs")
        previous = finish
        message = event["message"]
        _require(isinstance(message, dict) and all(type(message.get(key)) is type(value)
                 and canonical_json(message[key]) == canonical_json(value) for key, value in common.items())
                 and type(message.get("command_index")) is int and message["command_index"] == index,
                 "pilot process/context/buffer/repeat identity changed")
        if index == 0:
            _require(set(message) == _COMMON_FIELDS | {"command_index", "phase", "prime_order",
                     "started_monotonic_ns", "finished_monotonic_ns"}
                     and message["kind"] == "prime" and message["phase"] == "pilot"
                     and message["prime_order"] == ["baseline"] * 4, "invalid baseline pilot prime")
            _interval(message["started_monotonic_ns"], message["finished_monotonic_ns"], within=(start, finish))
        elif index <= 3:
            _require(set(message) == _COMMON_FIELDS | {"command_index", "phase", "sample_index", "baseline"}
                     and message["kind"] == "pilot_sample" and message["phase"] == "pilot"
                     and type(message["sample_index"]) is int and message["sample_index"] == index - 1,
                     "invalid baseline pilot sample")
            sample = message["baseline"]
            _require(set(sample) == {"implementation", "launches_per_operator", "elapsed_ms", "elapsed_ns",
                     "started_monotonic_ns", "finished_monotonic_ns", "cpu_before", "cpu_after"}
                     and sample["implementation"] == "baseline"
                     and type(sample["launches_per_operator"]) is int
                     and sample["launches_per_operator"] == config["roles"]["baseline"]["launches_per_operator"],
                     "pilot used a non-baseline callback")
            _interval(sample["started_monotonic_ns"], sample["finished_monotonic_ns"], within=(start, finish))
            _require(all(type(sample[key]) is int and sample[key] in affinity for key in ("cpu_before", "cpu_after")),
                     "pilot sample CPU outside affinity")
            milliseconds, nanoseconds = _number(sample["elapsed_ms"]), _number(sample["elapsed_ns"])
            _require(milliseconds > 0 and nanoseconds > 0
                     and struct.unpack("f", struct.pack("f", milliseconds))[0] == milliseconds
                     and math.isclose(nanoseconds, milliseconds * 1e6 / 100, rel_tol=1e-12, abs_tol=1e-12),
                     "pilot event units/repeat conversion differs")
            samples.append(milliseconds)
        else:
            _require(set(message) == _COMMON_FIELDS | {"command_index", "untimed_verifications",
                     "input_bytes_unchanged", "pilot_samples"}
                     and message["kind"] == "complete" and message["input_bytes_unchanged"] is True
                     and type(message["pilot_samples"]) is int and message["pilot_samples"] == 3,
                     "pilot completion differs")
            verifications = message["untimed_verifications"]
            _require(isinstance(verifications, list) and len(verifications) == 2,
                     "pilot requires both untimed callbacks")
            cursor = start
            for role, item in zip(ROLES, verifications, strict=True):
                _require(set(item) == {"role", "implementation", "started_monotonic_ns",
                         "finished_monotonic_ns", "scope"}
                         and item["role"] == item["implementation"] == role
                         and item["scope"] == "untimed_callback_verification",
                         "pilot untimed callback differs")
                _interval(item["started_monotonic_ns"], item["finished_monotonic_ns"], within=(cursor, finish))
                cursor = item["finished_monotonic_ns"]
    return samples


def _grid(raw, config):
    _require(raw.get("protocol") == PROTOCOL and raw.get("complete") is True and "error" not in raw,
             "shared measurement is incomplete or failed")
    ids = config["expected_case_ids"]
    _require(isinstance(ids, list) and ids and all(type(cid) is int and cid > 0 for cid in ids)
             and len(ids) == len(set(ids)), "invalid case scope")
    _require([case["case_id"] for case in config["cases"]] == ids, "config case scope differs")
    repeats = raw.get("repeat_by_case")
    _require(isinstance(repeats, dict) and set(repeats) == {str(cid) for cid in ids}
             and all(type(value) is int and 100 <= value <= 100000 and value % 100 == 0
                     for value in repeats.values()), "invalid raw repeat scope")
    sessions = raw["sessions"]
    _require([(item["case_id"], item["cycle"]) for item in sessions]
             == [(cid, cycle) for cid in ids for cycle in range(6)], "session scope/order differs")
    values = {cid: [] for cid in ids}
    for session in sessions:
        values[session["case_id"]].append(_session_samples(
            session, config, expected_repeat=repeats[str(session["case_id"])]))
    return values


def _phase_controls(values):
    controls = {phase: _control(values[phase]["baseline"], values[phase]["candidate"]) for phase in PHASES}
    controls["drift"] = {role: abs(statistics.fmean(values["aa_after"][role])
                                   / statistics.fmean(values["aa_before"][role]) - 1) for role in ROLES}
    return controls


def _summarize_values(values, config, *, protocol=PROTOCOL, failure=None):
    """Pure summary; partial/malformed evidence never masks the original failure.

    Statistical stability is not a performance verdict or CAS provenance proof.
    The formal replay additionally checks every source, stdout and oracle receipt.
    """
    from .contracts import GateConfig
    from .gates import _paired_estimate
    report = {"schema_version": "1.0.0", "protocol": protocol, "unit": "ns",
              "aggregation": "equal_case_geometric_mean_per_round", "mode": "formal", "stable": False,
              "case_ids": config.get("expected_case_ids", []) if isinstance(config, dict) else [],
              "reasons": [], "per_case": [], "controls": [], "speedup": None, "speedup_lcb_95": None,
              "max_case_regression": None,
              "gate_projection": {"baseline_samples_ns": [], "candidate_samples_ns": [], "heldout_regressions": []},
              "authority": "measurement draft only; full correctness and runtime candidate gate required"}
    try:
        if failure is not None:
            raise failure
        for case_id, cycles in values.items():
            merged = {phase: {role: [value for cycle in cycles for value in cycle[phase][role]] for role in ROLES}
                      for phase in PHASES}
            controls = {"case_id": case_id, "overall": _phase_controls(merged),
                        "cycles": [{"cycle": index, **_phase_controls(cycle)} for index, cycle in enumerate(cycles)]}
            report["controls"].append(controls)
            for label, item in [("overall", controls["overall"]),
                                *((f"cycle {index}", value) for index, value in enumerate(controls["cycles"]))]:
                for phase in PHASES:
                    quality = item[phase]
                    if quality["baseline_cv"] > GateConfig.MAX_CV or quality["candidate_cv"] > GateConfig.MAX_CV:
                        report["reasons"].append(f"case {case_id} {label} {phase}: CV exceeds 5%")
                    if phase != "formal" and quality["role_bias"] > 0.02:
                        report["reasons"].append(f"case {case_id} {label} {phase}: A/A role bias exceeds 2%")
                for role, value in item["drift"].items():
                    if value > 0.02:
                        report["reasons"].append(f"case {case_id} {label} {role}: A/A mean drift exceeds 2%")
            baseline, candidate = (merged["formal"][role] for role in ROLES)
            _require(len(baseline) == len(candidate) == 30, "formal pair count differs")
            report["per_case"].append({"case_id": case_id, "pair_count": 30,
                "baseline_samples_ns": baseline, "candidate_samples_ns": candidate,
                "baseline_cv": _cv(baseline), "candidate_cv": _cv(candidate),
                "baseline_median_ns": statistics.median(baseline), "candidate_median_ns": statistics.median(candidate),
                "regression": _geomean([y / x for x, y in zip(baseline, candidate, strict=True)]) - 1,
                "speedup": _geomean([x / y for x, y in zip(baseline, candidate, strict=True)])})
        report["max_case_regression"] = max(case["regression"] for case in report["per_case"])
        projection = {key: [_geomean([case[key][index] for case in report["per_case"]]) for index in range(30)]
                      for key in ("baseline_samples_ns", "candidate_samples_ns")}
        if max(_cv(projection[key]) for key in projection) > GateConfig.MAX_CV:
            report["reasons"].append("suite CV exceeds 5%")
        if not report["reasons"]:
            projection["heldout_regressions"] = [case["regression"] for case in report["per_case"]]
            report["gate_projection"] = projection
            report["speedup"], report["speedup_lcb_95"] = _paired_estimate(
                tuple(projection["baseline_samples_ns"]), tuple(projection["candidate_samples_ns"]),
                GateConfig.from_dict({}), config["operator"])
            report["stable"] = True
    except (ContractError, KeyError, TypeError, ValueError, IndexError, AttributeError, ArithmeticError) as error:
        report["reasons"].append("incomplete or malformed shared evidence: " + str(error))
        report["gate_projection"] = {"baseline_samples_ns": [], "candidate_samples_ns": [], "heldout_regressions": []}
        report["stable"] = False
    return report


def summarize_shared_raw(raw, config):
    try:
        values = _grid(raw, config)
    except (ContractError, KeyError, TypeError, ValueError, IndexError, AttributeError, ArithmeticError) as error:
        return _summarize_values(None, config, failure=error)
    return _summarize_values(values, config)


def _expanded(tokens, directory):
    _require(isinstance(tokens, list) and tokens and all(isinstance(token, str) and token for token in tokens),
             "invalid command vector")
    values = [token.replace("{cycle_dir}", directory) for token in tokens]
    _require(all("{" not in value and "}" not in value for value in values), "unknown path template")
    return values


def _passed_verifier_log(reader, reference):
    values = []
    for line in reader.verify_artifact(reference).read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("{"):
            value = _json(line)
            if isinstance(value, dict) and "passed" in value:
                values.append(value)
    _require(len(values) == 1 and values[0]["passed"] is True, "native verifier stdout did not uniquely pass")


def _session_artifacts(reader, session, config, registration):
    case = next(case for case in config["cases"] if case["case_id"] == session["case_id"])
    directory = session["cycle_dir"]
    path = PurePosixPath(directory)
    _require(path.is_absolute() and ".." not in path.parts and str(path) == directory, "invalid cycle directory")
    execution = session["execution"]
    _require(execution.get("environment") == {
             "APROF_SHARED_TIMING": "1", "APROF_SHARED_CYCLE": str(session["cycle"]),
             "APROF_SHARED_MODE": session["mode"], "APROF_SHARED_REPEAT": str(session["ready"]["repeat"])},
             "native timing environment differs from the declared mode/repeat")
    _require(execution.get("argv") == _expanded(case["command"], directory)
             and execution["argv"][0] == config["build"]["binary"]
             and execution.get("cwd") == config["build"]["source_dir"]
             and type(execution.get("exit_status")) is int and execution["exit_status"] == 0
             and "error" not in execution, "timing command failed or differs")
    _interval(execution["started_at"], execution["finished_at"], within=(session["started_at"], session["finished_at"]))
    _require(execution.get("log_hash") == session["stdout_ref"]
             and execution.get("log_path") == str(path / "stdout.log"), "timing stdout binding differs")
    messages = []
    prefix = "APROF_SHARED_TIMING_JSON:"
    for line in reader.verify_artifact(session["stdout_ref"]).read_text(encoding="utf-8").splitlines():
        if line.startswith(prefix):
            messages.append(_json(line[len(prefix):]))
        elif "APROF_SHARED_TIMING" in line:
            raise ContractError("measurement admission: malformed protocol stdout")
    _require(canonical_json(messages) == canonical_json([session["ready"], *(event["message"] for event in session["events"])]),
             "raw messages do not reproduce the exact process stdout")
    _require(session["ready"]["cpu_affinity"] == registration["cpu_affinity"], "child CPU affinity differs from registration")
    _output_artifacts(reader, session, config, after=execution["finished_at"])

def _output_artifacts(reader, session, config, *, after):
    case = next(case for case in config["cases"] if case["case_id"] == session["case_id"])
    directory = session["cycle_dir"]
    path = PurePosixPath(directory)
    outputs = {role: _expanded(case["output_files"][role], directory) for role in ROLES}
    all_outputs = [value for values in outputs.values() for value in values]
    _require(all_outputs and len(set(all_outputs)) == len(all_outputs)
             and all(PurePosixPath(value).is_relative_to(path) and ".." not in PurePosixPath(value).parts for value in all_outputs),
             "output paths overlap or escape cycle directory")
    _require(set(session["output_hashes"]) == set(all_outputs), "callback output scope differs")
    for reference in session["output_hashes"].values():
        reader.verify_artifact(reference)
    _require(set(session["verifications"]) == set(ROLES), "both native verifiers are required")
    previous = after
    for role in ROLES:
        receipt = session["verifications"][role]
        _require(receipt.get("argv") == _expanded(case["verify_commands"][role], directory)
                 and receipt.get("cwd") == config["build"]["source_dir"]
                 and type(receipt.get("exit_status")) is int and receipt["exit_status"] == 0
                 and "error" not in receipt, "native verifier failed or command differs")
        _interval(receipt["started_at"], receipt["finished_at"], within=(previous, session["finished_at"]))
        previous = receipt["finished_at"]
        _require(receipt.get("log_ref") == receipt.get("log_hash")
                 and receipt.get("log_path") == str(path / (role + "-verify.log")), "native verifier stdout binding differs")
        _require(receipt.get("output_refs") == {p: session["output_hashes"][p] for p in outputs[role]},
                 "native verifier output binding differs")
        _passed_verifier_log(reader, receipt["log_ref"])



def _calibration_artifacts(reader, calibration, config, registration):
    inventory = registration["inventory"]
    identity = registration["identity"]
    previous = calibration["started_at"]
    repeats = registration["repeat_by_case"]
    for case, item in zip(config["cases"], calibration["cases"], strict=True):
        _require(isinstance(item, dict) and set(item) == {"case_id", "repeat", "median_ms", "pilot"}
                 and item["case_id"] == case["case_id"], "invalid pilot case binding")
        pilot = item["pilot"]
        _require(isinstance(pilot, dict) and pilot.get("case_id") == case["case_id"],
                 "pilot case differs")
        _interval(pilot["started_at"], pilot["finished_at"], within=(previous, calibration["finished_at"]))
        previous = pilot["finished_at"]
        bound = identity["cases"][str(case["case_id"])]
        paths = {config["build"]["binary"], *config["build"]["receipt_files"],
                 *bound["prepared_files"], *bound["verifier_files"]}
        local_inventory = {**inventory, "files": {path: inventory["files"][path] for path in paths}}
        _require(pilot.get("identity_before") == local_inventory
                 and pilot.get("identity_after") == local_inventory,
                 "pilot source/build/input/oracle identity changed")
        samples = _pilot_samples(pilot, config)
        median = statistics.median(samples)
        repeat = 100 * max(1, math.ceil(50 / median))
        _require(repeat <= 100000, "pilot repeat exceeds 100000 cap")
        _require(type(item["median_ms"]) is float and item["median_ms"] == median
                 and type(item["repeat"]) is int and item["repeat"] == repeat
                 and repeats[str(case["case_id"])] == repeat,
                 "frozen repeat differs from pilot median")
        _session_artifacts(reader, pilot, config, registration)
    _require(previous <= calibration["finished_at"], "pilot chronology exceeds calibration")


def _oracle_artifacts(reader, config, registration, calibration, raw):
    """Bind every native output to the one frozen serial Python oracle roster."""
    plan = _load(reader, registration["verifier_request_plan_ref"])
    _require(isinstance(plan, dict) and set(plan) == {
             "schema_version", "protocol", "run_id", "session_id", "requests"}
             and plan["schema_version"] == 1 and plan["protocol"] == ORACLE_PROTOCOL
             and all(plan[key] == config[key] for key in ("run_id", "session_id")),
             "invalid frozen verifier roster")
    runs = [(item["pilot"], "calibration", None) for item in calibration["cases"]] if calibration is not None else []
    runs += [(session, "confirmation", session["cycle"]) for session in raw["sessions"]]
    expected_count = len(runs) * len(ROLES)
    requests = plan["requests"]
    _require(isinstance(requests, list) and len(requests) == expected_count,
             "verifier request roster differs from all pilot and confirmation outputs")
    worker = _load(reader, raw["verifier_worker_ref"])
    _require(isinstance(worker, dict) and set(worker) == {
             "schema_version", "protocol", "run_id", "session_id", "worker_id", "pid",
             "interpreter_ref", "worker_source_ref", "request_plan_ref", "started_at",
             "ready_at", "finished_at", "exit_status", "status", "request_refs",
             "transcript_ref", "process_stdout_ref", "process_stderr_ref"}
             and worker["schema_version"] == 1 and worker["protocol"] == ORACLE_PROTOCOL
             and worker["status"] == "complete" and type(worker["exit_status"]) is int
             and worker["exit_status"] == 0 and type(worker["pid"]) is int and worker["pid"] > 0
             and isinstance(worker["worker_id"], str) and worker["worker_id"]
             and all(worker[key] == config[key] for key in ("run_id", "session_id"))
             and worker["request_plan_ref"] == registration["verifier_request_plan_ref"]
             and worker["worker_source_ref"] == registration["producer_files"][
                 "skills/ascendc-aprof-profiling/scripts/persistent_oracle.py"],
             "persistent oracle worker identity differs")
    _interval(worker["started_at"], worker["ready_at"])
    _interval(worker["ready_at"], worker["finished_at"])
    collection_start = calibration["started_at"] if calibration is not None else raw["started_at"]
    first_native = calibration["cases"][0]["pilot"] if calibration is not None else raw["sessions"][0]
    _require(collection_start <= worker["started_at"]
             and worker["ready_at"] <= first_native["started_at"]
             and worker["finished_at"] <= raw["finished_at"],
             "persistent oracle lifecycle escapes collection")
    _require(isinstance(worker["request_refs"], list) and len(worker["request_refs"]) == expected_count,
             "persistent oracle request count differs")
    for key in ("interpreter_ref", "process_stdout_ref", "process_stderr_ref"):
        reader.verify_artifact(worker[key])
    transcript = _load(reader, worker["transcript_ref"])
    _require(isinstance(transcript, dict) and set(transcript) == {"schema_version", "events"}
             and transcript["schema_version"] == 1 and isinstance(transcript["events"], list)
             and len(transcript["events"]) == expected_count * 2 + 3,
             "persistent oracle transcript scope differs")
    events = transcript["events"]
    previous_at, previous_mono = worker["started_at"], -1
    for event in events:
        _require(isinstance(event, dict) and set(event) == {"direction", "at", "monotonic_ns", "message"}
                 and event["direction"] in ("send", "receive")
                 and isinstance(event["message"], dict), "invalid persistent oracle transcript event")
        _require(previous_at <= _number(event["at"]) <= worker["finished_at"]
                 and type(event["monotonic_ns"]) is int and event["monotonic_ns"] > previous_mono,
                 "persistent oracle transcript chronology differs")
        previous_at, previous_mono = event["at"], event["monotonic_ns"]
    _require(events[0]["direction"] == "receive"
             and events[0]["message"] == {"kind": "ready", "protocol": ORACLE_PROTOCOL,
                 "worker_id": worker["worker_id"], "pid": worker["pid"],
                 "request_plan_ref": worker["request_plan_ref"]}
             and events[0]["at"] <= worker["ready_at"], "persistent oracle READY differs")
    seen_paths = set()
    for index, (session, stage, cycle) in enumerate(runs):
        case_id = session["case_id"]
        case = next(case for case in config["cases"] if case["case_id"] == case_id)
        bound = registration["identity"]["cases"][str(case_id)]
        directory = session["cycle_dir"]
        for role in ROLES:
            request_index = index * 2 + ROLES.index(role)
            item = requests[request_index]
            receipt = session["verifications"][role]
            outputs = _expanded(case["output_files"][role], directory)
            _require(isinstance(item, dict) and set(item) == {
                     "request_index", "stage", "case_id", "cycle", "role", "argv", "cwd",
                     "script_ref", "prepared_refs", "output_paths", "result_path",
                     "log_path", "stderr_path"}
                     and type(item["request_index"]) is int and item["request_index"] == request_index
                     and item["stage"] == stage and item["case_id"] == case_id
                     and item["cycle"] == cycle and item["role"] == role
                     and item["argv"] == _expanded(case["verify_commands"][role], directory)
                     and item["cwd"] == config["build"]["source_dir"]
                     and item["prepared_refs"] == bound["prepared_files"]
                     and item["output_paths"] == outputs
                     and item["log_path"] == receipt["log_path"]
                     and len(item["argv"]) >= 2
                     and item["argv"].count("--result") == 1
                     and item["argv"].index("--result") + 1 < len(item["argv"])
                     and item["argv"][item["argv"].index("--result") + 1] == item["result_path"]
                     and item["script_ref"] == bound["verifier_files"].get(item["argv"][1]),
                     "persistent oracle frozen request differs from native output")
            _require(item["argv"][0] in bound["verifier_files"]
                     and bound["verifier_files"][item["argv"][0]] == worker["interpreter_ref"],
                     "persistent oracle interpreter differs from frozen verifier")
            for path in [*outputs, item["result_path"], item["log_path"], item["stderr_path"]]:
                p = PurePosixPath(path)
                _require(isinstance(path, str) and p.is_absolute() and ".." not in p.parts
                         and str(p) == path and p.is_relative_to(PurePosixPath(directory))
                         and path not in seen_paths, "persistent oracle artifact path escaped or was reused")
                seen_paths.add(path)
            _require(isinstance(receipt, dict) and set(receipt) == {
                     "protocol", "worker_id", "request_index", "argv", "cwd", "log_path",
                     "started_at", "finished_at", "exit_status", "log_hash", "log_ref",
                     "output_refs", "request_ref", "result_ref", "stderr_ref"}
                     and receipt["protocol"] == ORACLE_PROTOCOL
                     and receipt["worker_id"] == worker["worker_id"]
                     and type(receipt["request_index"]) is int and receipt["request_index"] == request_index
                     and receipt["request_ref"] == worker["request_refs"][request_index],
                     "persistent oracle receipt differs")
            response = _load(reader, receipt["request_ref"])
            _require(isinstance(response, dict) and set(response) == {
                     "kind", "protocol", "worker_id", "pid", "request_index", "started_at",
                     "finished_at", "exit_status", "state_restored", "script_ref",
                     "output_refs_before", "output_refs_after", "log_hash", "stderr_hash",
                     "result_hash", "error"}
                     and response["kind"] == "result" and response["protocol"] == ORACLE_PROTOCOL
                     and response["worker_id"] == worker["worker_id"] and response["pid"] == worker["pid"]
                     and type(response["request_index"]) is int and response["request_index"] == request_index
                     and response["state_restored"] is True and response["error"] is None
                     and type(response["exit_status"]) is int and response["exit_status"] == 0
                     and response["script_ref"] == item["script_ref"]
                     and response["output_refs_before"] == response["output_refs_after"] == receipt["output_refs"]
                     and response["log_hash"] == receipt["log_ref"] == receipt["log_hash"]
                     and response["stderr_hash"] == receipt["stderr_ref"]
                     and response["result_hash"] == receipt["result_ref"],
                     "persistent oracle response differs")
            sent, received = events[request_index * 2 + 1:request_index * 2 + 3]
            _require(sent["direction"] == "send"
                     and sent["message"] == {"kind": "verify", "request_index": request_index}
                     and received["direction"] == "receive"
                     and canonical_json(received["message"]) == canonical_json(response),
                     "persistent oracle request/response transcript differs")
            _require(receipt["started_at"] <= sent["at"] <= response["started_at"]
                     <= response["finished_at"] <= received["at"] <= receipt["finished_at"],
                     "persistent oracle request time differs")
            reader.verify_artifact(receipt["stderr_ref"])
            result = _load(reader, receipt["result_ref"])
            rows = [_json(line) for line in reader.verify_artifact(receipt["log_ref"])
                    .read_text(encoding="utf-8").splitlines() if line.lstrip().startswith("{")]
            passed = [row for row in rows if isinstance(row, dict) and "passed" in row]
            _require(len(passed) == 1 and isinstance(result, dict) and passed[0] == result
                     and result.get("passed") is True and type(result.get("case_id")) is int
                     and result["case_id"] == case_id,
                     "persistent oracle stdout/result does not uniquely pass")
    close_sent, close_received = events[-2:]
    _require(raw["sessions"][-1]["finished_at"] <= close_sent["at"],
             "persistent oracle closed before final native session")
    _require(close_sent["direction"] == "send"
             and close_sent["message"] == {"kind": "close", "abort": False}
             and close_received["direction"] == "receive"
             and close_received["message"] == {"kind": "closed", "completed_requests": expected_count},
             "persistent oracle close differs")


def _hardware(reader, registration, raw, config):
    hardware = _load(reader, registration["hardware_ref"])
    _require(hardware.get("host") == raw.get("host") and isinstance(hardware.get("host"), str) and hardware["host"]
             and type(hardware.get("physical_device")) is int and hardware["physical_device"] == config["physical_device"],
             "hardware host or physical device differs")
    probe = hardware["probe"]
    _require(type(probe.get("exit_code")) is int and probe["exit_code"] == 0 and probe.get("error") is None,
             "hardware probe failed")
    argv = probe.get("argv")
    _require(isinstance(argv, list) and len(argv) == 8 and PurePosixPath(argv[0]).name == "npu-smi"
             and argv[1:] == ["info", "-t", "board", "-i", str(config["physical_device"]), "-c", "0"],
             "hardware probe command differs")
    _require(_load(reader, probe["log_hash"]) == {key: value for key, value in probe.items() if key != "log_hash"},
             "hardware probe differs from original execution receipt")
    _interval(probe["started_at"], probe["ended_at"])
    _require(probe["ended_at"] <= registration["created_at"], "hardware probe postdates registration")
    for reference in (hardware["npu_smi_ref"], hardware["cann_install_info_ref"], probe["stdout_hash"], probe["stderr_hash"]):
        reader.verify_artifact(reference)
    mapped = False
    for key in ("ASCEND_RT_VISIBLE_DEVICES", "ASCEND_VISIBLE_DEVICES"):
        value = raw["environment"].get(key)
        if value:
            tokens = value.split(",")
            _require(all(token.strip().isdigit() for token in tokens) and 0 <= config["device"] < len(tokens)
                     and int(tokens[config["device"]]) == config["physical_device"], "device visibility mapping differs")
            mapped = True
    _require(mapped or config["device"] == config["physical_device"], "unmapped logical/physical device differs")
    return hardware


def _replay_shared_admission(artifact_reader, receipt_ref, *, expected, producer_resolver=None):
    """Pure CAS replay shared by runtime admission and independent publication.

    This verifies measurement integrity only. Hardware qualification, publication,
    complete optimization semantics and the unchanged gain gate remain separate.
    """
    try:
        receipt, config, registration, calibration, raw = _outer_evidence(
            artifact_reader, receipt_ref, expected, producer_resolver=producer_resolver)
        _grid(raw, config)
        directories, processes = set(), set()
        _calibration_artifacts(artifact_reader, calibration, config, registration)
        for session in [*(item["pilot"] for item in calibration["cases"]), *raw["sessions"]]:
            _require(session["cycle_dir"] not in directories, "cycle directory was reused")
            directories.add(session["cycle_dir"])
            process = (session["execution"]["pid"], session["execution"]["started_at"])
            _require(process not in processes, "fresh process identity was reused")
            processes.add(process)
            if session["mode"] == "confirmation":
                _session_artifacts(artifact_reader, session, config, registration)
        _oracle_artifacts(artifact_reader, config, registration, calibration, raw)
        hardware = _hardware(artifact_reader, registration, raw, config)
        report = summarize_shared_raw(raw, config)
        _require(report["stable"] is True, "; ".join(report["reasons"]))
        supplied = _load(artifact_reader, receipt["measurement_report_ref"])
        _require(canonical_json(supplied) == canonical_json(report), "measurement report differs from raw replay")
        return {"valid": True, "protocol": PROTOCOL, "receipt_ref": receipt_ref,
                "source_hashes": receipt["source_hashes"], "config_ref": receipt["config_ref"],
                "registration_ref": receipt["registration_ref"], "hardware_ref": registration["hardware_ref"],
                "calibration_ref": registration["calibration_ref"],
                "verifier_worker_ref": raw["verifier_worker_ref"],
                "hardware": hardware, "report": report, "gate_projection": report["gate_projection"]}
    except ContractError:
        raise
    except (KeyError, TypeError, ValueError, IndexError, AttributeError, OSError, ArithmeticError) as error:
        raise ContractError("measurement admission: malformed or missing shared evidence: " + str(error)) from error


def replay_historical_measurement_admission(artifact_reader, receipt_ref, *, expected, producer_resolver):
    """Read-only v2 replay; archived producers never confer current eligibility."""
    _require(callable(producer_resolver), "historical producer resolver is required")
    result = _replay_shared_admission(artifact_reader, receipt_ref, expected=expected,
                                     producer_resolver=producer_resolver)
    return {"replay": result, "eligible_for_publication": False}


def replay_measurement_admission(artifact_reader, receipt_ref, *, expected):
    """Dispatch current Task evidence; retain explicit v2 replay for archive tooling."""
    receipt = _load(artifact_reader, receipt_ref)
    if isinstance(receipt, dict) and receipt.get("protocol") == PROTOCOL:
        return _replay_shared_admission(artifact_reader, receipt_ref, expected=expected)
    from .task_measurement_admission import replay_task_measurement_admission
    return replay_task_measurement_admission(artifact_reader, receipt_ref, expected=expected)


def verify_measurement_admission(evidence: GateEvidence, artifact_reader, *,
                                 source_hashes, session_id=None, run_id=None) -> None:
    """Reject unqualified timing; empty timing retains failure/NOOP recording.

    ``artifact_reader`` only needs ``verify_artifact(hash) -> Path``, including
    the read-only CAS adapter used for historical episode verification. This
    module must not import collectors or depend on repository paths.
    """
    evidence = GateEvidence.from_dict(to_primitive(evidence))
    if not evidence.baseline_samples_ns and not evidence.candidate_samples_ns:
        return
    if artifact_reader is None:
        raise ContractError("measured admission requires a CAS artifact reader")
    reference = evidence.artifacts.get("measurement_admission")
    if reference is None:
        raise ContractError("measured admission requires the measurement_admission artifact")
    receipt = _load(artifact_reader, reference)
    if not isinstance(receipt, dict):
        raise ContractError("measurement_admission must be a JSON object")
    from .task_measurement_admission import PROTOCOL as TASK_PROTOCOL
    _require(receipt.get("protocol") == TASK_PROTOCOL,
             "formal admission requires Task Duration protocol; Event evidence is historical only")
    expected_sources = to_primitive(SourceHashes.from_dict(to_primitive(source_hashes), "source_hashes"))
    expected = {"candidate_id": evidence.candidate_id, "source_hashes": expected_sources}
    if session_id is not None:
        expected["session_id"] = session_id
    if run_id is not None:
        expected["run_id"] = run_id
    for key, value in expected.items():
        if receipt.get(key) != value:
            raise ContractError(f"measurement_admission {key} differs from the gate request")
    report = evidence.artifacts.get("measurement_report")
    if report is None or receipt.get("measurement_report_ref") != report:
        raise ContractError("measurement_admission measurement report binding differs")
    result = replay_measurement_admission(artifact_reader, reference, expected={**expected, "measurement_report_ref": report})
    supplied = {key: list(getattr(evidence, key)) for key in
                ("baseline_samples_ns", "candidate_samples_ns", "heldout_regressions")}
    _require(canonical_json(result["gate_projection"]) == canonical_json(supplied), "GateEvidence projection differs from raw replay")
