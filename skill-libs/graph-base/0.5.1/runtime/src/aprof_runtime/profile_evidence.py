"""CAS-backed profiling replay, independent of collectors and repository layout.

A sample is one process capture, never a core, section, or profiler replay.
The manifest is a collector receipt, not hardware remote attestation.
"""
from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import PurePosixPath

from .errors import ContractError

MIN_CAPTURES = 5
MIN_WARMUPS = 10
MAX_PROFILE_CV = 0.05
REDUCERS = {"mean": statistics.fmean, "median": statistics.median,
            "sum": sum, "min": min, "max": max}
NA = (None, "", "NA", "N/A", "--", "null")


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _json(text):
    return json.loads(text, object_pairs_hook=_object, parse_constant=lambda value: (_ for _ in ()).throw(ContractError(f"invalid JSON number: {value}")))


def _load(store, digest):
    try:
        return _json(store.verify_artifact(digest).read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ContractError(f"profiling artifact is not JSON: {digest}") from exc


def _refs(store, value):
    if isinstance(value, dict):
        for item in value.values():
            _refs(store, item)
    elif isinstance(value, list):
        for item in value:
            _refs(store, item)
    elif isinstance(value, str) and value.startswith("sha256:"):
        store.verify_artifact(value)


def _relative(path):
    p = PurePosixPath(path)
    if p.is_absolute() or ".." in p.parts or str(p) != path or path == ".":
        raise ContractError("capture paths must be canonical relative paths")
    return p


def load_capture_manifest(store, digest):
    from .traces import validate_trace_contract
    manifest = validate_trace_contract("capture-manifest", _load(store, digest))
    _refs(store, manifest)
    if manifest["kernel"] == "*":
        raise ContractError("capture requires an exact kernel identity")
    policy = manifest["policy"]
    if len(manifest["warmup_runs"]) != policy["warmups"]:
        raise ContractError("warmup count differs from recorded process executions")
    captures = manifest["captures"]
    warmup_hashes = [item["log_hash"] for item in manifest["warmup_runs"]]
    if len(set(warmup_hashes)) != len(warmup_hashes) or set(warmup_hashes).intersection(c["log_hash"] for c in captures):
        raise ContractError("warmups must have distinct process receipts")
    import shlex
    targets = []
    for capture in captures:
        argv = capture["argv"]
        if manifest["backend"] == "msprof":
            applications = [arg.split("=", 1)[1] for arg in argv if arg.startswith("--application=")]
            if len(applications) != 1:
                raise ContractError("msprof capture must record one exact workload application")
            target = shlex.split(applications[0])
        else:
            if "--" not in argv:
                raise ContractError("npu-compute capture must record the exact workload after --")
            target = argv[argv.index("--") + 1:]
        if not target:
            raise ContractError("capture workload argv is empty")
        targets.append(target)
    if any(target != targets[0] for target in targets) or any(w["argv"] != targets[0] for w in manifest["warmup_runs"]):
        raise ContractError("warmup/capture commands do not execute the same exact workload")
    if len(captures) != policy["repeats"]:
        raise ContractError("capture count differs from recorded process executions")
    if len({c["capture_id"] for c in captures}) != len(captures):
        raise ContractError("independent capture ids must be unique")
    if len({c["collection"] for c in captures}) != len(captures):
        raise ContractError("independent captures cannot reuse a collection")
    if len({c["log_hash"] for c in captures}) != len(captures):
        raise ContractError("independent captures cannot reuse a process receipt")
    for item in manifest["warmup_runs"] + captures:
        if item["exit_code"] != 0:
            raise ContractError("failed process captures cannot supply profile evidence")
        # The receipt may contain hashes for separate stdout/stderr files.
        receipt = _load(store, item["log_hash"])
        _refs(store, receipt)
        execution = receipt.get("capture", receipt)
        expected_identity = {"binary_hash": manifest["binary_hash"], "tool_hash": manifest["tool"]["executable_hash"], "source_hash": manifest["source_hash"]}
        executions = [execution]
        if item in captures and manifest["backend"] == "npu-compute":
            executions.append(receipt.get("import", {}))
        for process in executions:
            if process.get("identity_checks") != {"before": expected_identity, "after": expected_identity}:
                raise ContractError("binary/tool/source identity changed or is not checked around process execution")
        if execution.get("argv") != item["argv"] or execution.get("exit_code") != item["exit_code"]:
            raise ContractError("process receipt argv/exit status differs from manifest")
        if item in captures:
            scope = {key: manifest[key] for key in ("backend", "role", "case_id", "kernel", "workload_hash", "source_hash", "binary_hash", "hardware_hash", "tool", "policy", "collector_hash", "protocol_version")}
            scope.update({key: item[key] for key in ("capture_id", "collection", "files")})
            if receipt.get("capture_scope") != scope:
                raise ContractError("capture manifest identity/files differ from immutable process receipt")
            if manifest["backend"] == "npu-compute" and receipt.get("import", {}).get("exit_code") != 0:
                raise ContractError("npu-compute import must have a successful process receipt")
    for capture in captures:
        _relative(capture["collection"])
        paths = set()
        for file in capture["files"]:
            path = _relative(file["path"])
            if file["path"] in paths:
                raise ContractError("duplicate path in capture file inventory")
            paths.add(file["path"])
            if file["kernel"] != manifest["kernel"]:
                raise ContractError("capture file kernel differs from manifest")
    for key in ("hardware_hash", "workload_hash"):
        identity = _load(store, manifest[key])
        if not isinstance(identity, dict) or not identity:
            raise ContractError(f"{key} must bind a nonempty JSON identity")
        _refs(store, identity)
    try:
        source_bundle = _json(store.verify_artifact(manifest["source_hash"]).read_text())
    except (UnicodeError, ValueError):
        source_bundle = None
    if isinstance(source_bundle, dict) and source_bundle.get("schema_version") == "1.0.0" and "files" in source_bundle:
        if not isinstance(source_bundle["files"], dict) or not source_bundle["files"]:
            raise ContractError("source bundle files must be a nonempty mapping")
        for path, digest in source_bundle["files"].items():
            _relative(path)
            store.verify_artifact(digest)
    for capture in captures:
        _capture_identity(store, manifest, capture)
    return manifest


def _capture_identity(store, manifest, capture):
    """Replay raw operator scope; section files inherit the same collection only."""
    files = [f for f in capture["files"] if _relative(f["path"]).parent == _relative(capture["collection"])]
    hardware = _load(store, manifest["hardware_hash"])
    if manifest["backend"] == "npu-compute":
        summaries = [f for f in files if PurePosixPath(f["path"]).name == "summary.jsonl"]
        if len(summaries) != 1:
            raise ContractError("npu-compute capture requires exactly one raw summary.jsonl")
        records = [_json(line) for line in store.verify_artifact(summaries[0]["artifact_hash"]).read_text().splitlines() if line.strip()]
        rows = [r for r in records if isinstance(r, dict) and r.get("category") == "OpInfoSummary"]
        if len(rows) != 1:
            raise ContractError("npu-compute summary requires exactly one OpInfoSummary")
        row = rows[0]
        if row.get("Op Name") != manifest["kernel"]:
            raise ContractError("raw OpInfoSummary kernel differs from capture")
        if "device" not in hardware or str(row.get("Device Id")) != str(hardware["device"]):
            raise ContractError("raw OpInfoSummary device differs from hardware identity")
        for name in ("Current Freq", "Rated Freq"):
            if type(row.get(name)) not in (int, float) or not math.isfinite(row[name]) or row[name] <= 0:
                raise ContractError("raw OpInfoSummary frequency is missing/invalid")
        hardware_files = [f for f in capture["files"] if PurePosixPath(f["path"]).name == "HardwareInfo.jsonl"]
        if len(hardware_files) != 1:
            raise ContractError("npu-compute capture requires exactly one HardwareInfo.jsonl")
        info = [_json(line) for line in store.verify_artifact(hardware_files[0]["artifact_hash"]).read_text().splitlines() if line.strip()]
        categories = {"Device Info", "AI Core Information", "CPU Information"}
        selected = [r for r in info if isinstance(r, dict) and r.get("category") in categories]
        if {r["category"] for r in selected} != categories or len(selected) != 3:
            raise ContractError("HardwareInfo has missing/duplicate hardware identity records")
        identity = {r["category"]: r for r in selected}
        if str(identity["Device Info"].get("arch info")) != "3510":
            raise ContractError("npu-compute hardware is not supported dav-3510")
        identity["frequencies"] = {key: row[key] for key in ("Current Freq", "Rated Freq")}
        if hardware.get("report_identity") != identity:
            raise ContractError("raw HardwareInfo/frequencies differ from capture hardware identity")
        return {key: row.get(key) for key in ("Op Type", "Device Id", "Current Freq", "Rated Freq")}
    import re
    basics = [f for f in files if re.fullmatch(r"OpBasicInfo(?:_\d+)?\.csv", PurePosixPath(f["path"]).name)]
    if len(basics) != 1:
        raise ContractError("msprof capture requires exactly one raw OpBasicInfo CSV")
    with store.verify_artifact(basics[0]["artifact_hash"]).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        rows = list(reader)
    if not rows or len(headers) != len(set(headers)) or any(None in r or any(v is None for v in r.values()) for r in rows):
        raise ContractError("invalid raw OpBasicInfo CSV")
    for row in rows:
        names = [v for k, v in row.items() if re.sub(r"[ _]", "", k).lower() in {"opname", "kernelname"}]
        if names and any(name != manifest["kernel"] for name in names):
            raise ContractError("raw OpBasicInfo kernel differs from capture")
        if not names and manifest["kernel"] not in _relative(capture["collection"]).parts:
            raise ContractError("raw msprof collection does not identify kernel")
        for key in ("Device Id", "Device ID"):
            if key in row and str(row[key]) != str(hardware.get("device")):
                raise ContractError("raw OpBasicInfo device differs from hardware identity")
    identities = []
    for row in rows:
        identity = {"device": str(hardware.get("device")), "Op Type": row.get("Op Type")}
        for key in ("Current Freq", "Rated Freq"):
            if key in row:
                try:
                    frequency = float(row[key])
                except (TypeError, ValueError) as exc:
                    raise ContractError("raw OpBasicInfo frequency is invalid") from exc
                if not math.isfinite(frequency) or frequency <= 0:
                    raise ContractError("raw OpBasicInfo frequency is invalid")
                identity[key] = frequency
        identities.append(identity)
    if any(identity != identities[0] for identity in identities[1:]):
        raise ContractError("raw OpBasicInfo has inconsistent device/frequency identity")
    return identities[0]


def metric_unit(field):
    """Literal raw units; ratios are not percentages and GB/s is never rescaled."""
    known = {"Task Duration(us)": "us", "Duration(us)": "us", "task_duration": "us",
             "duration": "us", "aiv_time": "us", "aic_time": "us"}
    if field in known:
        return known[field]
    for suffix, unit in (("(GB/s)", "GB/s"), ("(KB)", "KB"), ("(MB)", "MB"),
                         ("(us)", "us"), ("(ns)", "ns"), ("(%)", "%")):
        if field.endswith(suffix):
            return unit
    if field.endswith(("_ratio", "_rate")):
        return "ratio"
    if field.endswith(("_cycles", "_instructions", "_count")):
        return "count"
    raise ContractError(f"unsupported raw metric unit for field {field!r}; add an explicit runtime unit mapping")


def _raw_values(store, manifest, source):
    captures = {item["capture_id"]: item for item in manifest["captures"]}
    capture = captures.get(source["capture_id"])
    if capture is None:
        raise ContractError("profile selector refers to an unknown capture")
    matches = [item for item in capture["files"] if item["path"] == source["path"]]
    if len(matches) != 1 or matches[0]["format"] != source["format"]:
        raise ContractError("profile selector does not match the capture inventory")
    file = matches[0]
    if not _relative(file["path"]).is_relative_to(_relative(capture["collection"])):
        raise ContractError("metric source is outside its selected collection")
    path = store.verify_artifact(file["artifact_hash"])
    allowed = {"Op Name", "OP Name"} if source["format"] == "csv" else {"category"}
    if not set(source["where"]).issubset(allowed):
        raise ContractError("metric selector cannot cherry-pick cores or numeric values")
    if source["format"] == "csv" and any(value != manifest["kernel"] for value in source["where"].values()):
        raise ContractError("CSV kernel selector differs from manifest")
    try:
        if source["format"] == "csv":
            with path.open(encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                headers = reader.fieldnames or []
                if len(set(headers)) != len(headers):
                    raise ContractError("duplicate raw CSV columns are ambiguous")
                if source["field"] not in headers or not set(source["where"]).issubset(headers):
                    raise ContractError("profile selector field is absent from raw CSV")
                rows = list(reader)
                if any(None in row or any(value is None for value in row.values()) for row in rows):
                    raise ContractError("malformed raw CSV row width")
        else:
            rows = [_json(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            if any(not isinstance(row, dict) for row in rows):
                raise ContractError("JSONL profiling records must be objects")
        selected = []
        for row in rows:
            # npu-compute mixes Cube and Vector subblocks in a table. The
            # metric prefix supplies a deterministic applicability mask; users
            # cannot select individual cores via an arbitrary where clause.
            subblock = row.get("sub_block_id", "")
            if manifest["backend"] == "npu-compute" and source["format"] == "csv" and subblock:
                if source["field"].startswith("aiv_") and not subblock.startswith("vector"):
                    continue
                if source["field"].startswith("aic_") and not subblock.startswith("cube"):
                    continue
            raw_kernel = row.get("Op Name", row.get("OP Name"))
            if raw_kernel is not None and raw_kernel != manifest["kernel"]:
                continue
            if all(row.get(key) == value for key, value in source["where"].items()):
                selected.append(row)
        if source["format"] == "jsonl" and len(selected) > 1:
            raise ContractError("JSONL selector must identify exactly one record")
        if not selected:
            return None
        if source["format"] == "csv":
            core_fields = next((keys for keys in (("block_id", "sub_block_id"), ("Block Id", "Sub Block Id"), ("Core ID",), ("Core Id",), ("core_id",)) if set(keys).issubset(selected[0])), None)
            if core_fields:
                identities = [tuple(row[key] for key in core_fields) for row in selected]
                if len(identities) != len(set(identities)):
                    raise ContractError("duplicate raw profiling core identity")
        values = []
        for row in selected:
            if source["field"] not in row:
                raise ContractError("profile metric field is absent from selected record")
            raw = row[source["field"]]
            # Entirely unavailable records remain unknown; missing cores cannot
            # be silently dropped to manufacture a favorable statistic.
            if raw in NA:
                return None
            if isinstance(raw, bool):
                raise ContractError("boolean is not a numeric profiling metric")
            value = float(raw)
            if not math.isfinite(value) or value < 0:
                raise ContractError("raw profiling metric must be finite and nonnegative")
            values.append(value)
        return float(REDUCERS[source["row_aggregation"]](values))
    except (UnicodeError, ValueError, TypeError, csv.Error) as exc:
        raise ContractError(f"invalid raw profile selection: {exc}") from exc


def normalize_profile(store, manifest_hash, metric_specs):
    """Return strict normalized 1.1 from raw CAS artifacts (also used by CLI)."""
    from .traces import validate_trace_contract
    manifest = load_capture_manifest(store, manifest_hash)
    metrics = {}
    capture_ids = [c["capture_id"] for c in manifest["captures"]]
    for name, spec in metric_specs.items():
        if set(spec) != {"unit", "aggregation", "sources"}:
            raise ContractError("metric specification requires unit, aggregation and sources only")
        sources = spec["sources"]
        if spec["aggregation"] not in REDUCERS or not isinstance(sources, list) or not sources:
            raise ContractError("metric specification has invalid aggregation/sources")
        for source in sources:
            if not isinstance(source, dict) or set(source) != {"capture_id", "path", "format", "field", "where", "row_aggregation"}:
                raise ContractError("metric source selector fields are invalid")
            if source["format"] not in {"csv", "jsonl"} or source["row_aggregation"] not in REDUCERS or not isinstance(source["where"], dict):
                raise ContractError("metric source format/aggregation/selection is invalid")
        if [s["capture_id"] for s in sources] != capture_ids:
            raise ContractError("profile must select each independent capture exactly once in order")
        signatures = {(s["format"], s["field"], json.dumps(s["where"], sort_keys=True), s["row_aggregation"])
                      for s in sources}
        if len(signatures) != 1:
            raise ContractError("profile selectors change metric semantics across captures")
        if spec["unit"] != metric_unit(sources[0]["field"]):
            raise ContractError("normalized metric unit differs from raw field unit")
        values = [_raw_values(store, manifest, s) for s in sources]
        samples = [v for v in values if v is not None]
        value = float(REDUCERS[spec["aggregation"]](samples)) if len(samples) == len(values) else None
        cv = None
        if len(samples) == len(values) and len(samples) >= 2:
            mean = statistics.fmean(samples)
            dev = statistics.stdev(samples)
            cv = dev / abs(mean) if mean else (0.0 if not dev else None)
        status = "missing" if value is None else (
            "available" if manifest["policy"]["warmups"] >= MIN_WARMUPS and len(samples) >= MIN_CAPTURES and cv is not None and cv <= MAX_PROFILE_CV else "unstable")
        metrics[name] = {**spec, "value": value, "samples": samples, "cv": cv, "status": status}
    profile = {"schema_version": "1.1.0", "metric_definition_version": "raw_metric_v1", "case_id": manifest["case_id"], "kernel": manifest["kernel"],
               "capture_manifest_hash": manifest_hash, "metrics": metrics}
    return validate_trace_contract("normalized-profile", profile)


def replay_profile_metric(store, profile, name):
    from .traces import validate_trace_contract
    validate_trace_contract("normalized-profile", profile)
    if name not in profile["metrics"]:
        raise ContractError(f"normalized profile is missing metric {name!r}")
    metric = profile["metrics"][name]
    replay = normalize_profile(store, profile["capture_manifest_hash"], {
        name: {key: metric[key] for key in ("unit", "aggregation", "sources")}})
    if profile["kernel"] != replay["kernel"] or profile["case_id"] != replay["case_id"]:
        raise ContractError("normalized profile workload/kernel differs from capture manifest")
    if replay["metrics"][name] != metric:
        raise ContractError("normalized profile value/samples/stability differ from raw source replay")
    return load_capture_manifest(store, profile["capture_manifest_hash"])


def compare_profiles(store, baseline_profile, candidate_profile, name, *, source_hashes=None):
    """Validate identity and independent samples; return known comparability."""
    before = replay_profile_metric(store, baseline_profile, name)
    after = replay_profile_metric(store, candidate_profile, name)
    if before["role"] != "baseline" or after["role"] != "candidate":
        raise ContractError("mechanism profiles have incorrect baseline/candidate roles")
    for key in ("backend", "case_id", "workload_hash", "hardware_hash", "tool", "policy", "collector_hash", "protocol_version"):
        if before[key] != after[key]:
            raise ContractError(f"mechanism profile identity differs: {key}")
    if source_hashes is not None:
        for manifest, role in ((before, "baseline"), (after, "candidate")):
            expected = source_hashes[role] if isinstance(source_hashes, dict) else getattr(source_hashes, role)
            if manifest["source_hash"] != expected:
                raise ContractError("profile source role differs from candidate draft")
    raw_identities = [_capture_identity(store, m, c) for m in (before, after) for c in m["captures"]]
    if any(identity != raw_identities[0] for identity in raw_identities[1:]):
        raise ContractError("raw profile device/frequency basis differs across captures")
    b = baseline_profile["metrics"][name]
    a = candidate_profile["metrics"][name]
    def semantic(metric):
        return (metric["unit"], metric["aggregation"], [(source["format"], source["field"],
            {key: "<bound-kernel>" if key in {"Op Name", "OP Name"} else value for key, value in source["where"].items()},
            source["row_aggregation"]) for source in metric["sources"]])
    if semantic(b) != semantic(a):
        raise ContractError("mechanism metrics differ in unit or aggregation/selection semantics")
    return b["status"] == a["status"] == "available"
