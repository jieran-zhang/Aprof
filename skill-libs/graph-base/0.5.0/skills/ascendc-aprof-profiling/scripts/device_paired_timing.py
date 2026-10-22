#!/usr/bin/env python3
"""Persistent two-process ACL-event timing for caller-prepared operator cases.

Preparation/H2D occurs once per role and case; samples alternate AB/BA. Both
children quit before their separate output verifiers run. Every result remains a
measurement draft: full correctness, source-backed profiling and the runtime
candidate gate are separate requirements.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
from copy import deepcopy
import json
import math
import os
from pathlib import Path
import queue
import signal
import socket
import statistics
import subprocess
import sys
import threading
import time

SCRIPTS = Path(__file__).resolve().parent
RELEASE = SCRIPTS.parents[2]
sys.path.insert(0, str(RELEASE / "runtime/src"))
sys.path.insert(0, str(SCRIPTS))
from aprof_runtime import __version__ as RUNTIME_VERSION
from aprof_runtime.contracts import GateConfig
from aprof_runtime.gates import _paired_estimate
from aprof_runtime.jsonio import canonical_json, content_hash, file_hash
from aprof_runtime.profile_evidence import _json
from profile_capture import source_inventory
import aprof_runtime.gates as runtime_gates

PREFIX = "APROF_TIMING_JSON:"
ROLES = ("baseline", "candidate")
SAMPLE_FIELDS = {"schema_version", "operator", "device", "source", "unit", "sample_index",
                 "warmup", "repeat", "launches_per_operator", "elapsed_ns"}


def save(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")
    temporary.replace(path)


def argv(value, name):
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x or "\0" in x for x in value):
        raise ValueError(f"{name} must be a nonempty string argv array")
    return value


def regular(path):
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError(f"expected regular file: {path}")
    return path


def config_value(value):
    value = deepcopy(value)
    required = {"schema_version", "operator", "device", "expected_case_ids", "baseline", "candidate", "cases"}
    optional = {"mode", "pairs", "warmup", "repeat", "timeout_seconds", "physical_device"}
    if not isinstance(value, dict) or not required <= set(value) or set(value) - required - optional:
        raise ValueError("invalid device timing config fields")
    if value["schema_version"] != "1.0.0" or not isinstance(value["operator"], str) or not value["operator"]:
        raise ValueError("schema_version and operator are required")
    value.setdefault("mode", "explore")
    if value["mode"] not in {"explore", "formal"}:
        raise ValueError("mode must be explore or formal")
    for key, default, minimum in (("pairs", 30 if value["mode"] == "formal" else 6, 1),
                                  ("warmup", 10, 0), ("repeat", 100, 1), ("device", 0, 0)):
        value.setdefault(key, default)
        if type(value[key]) is not int or not minimum <= value[key] <= 1000000:
            raise ValueError(f"invalid {key}")
    if value["mode"] == "formal" and (value["pairs"] < GateConfig.MIN_PAIRS or value["warmup"] < 10):
        raise ValueError("formal timing requires at least 30 pairs and 10 warmups")
    value.setdefault("timeout_seconds", 180)
    if type(value["timeout_seconds"]) not in (int, float) or not math.isfinite(value["timeout_seconds"]) or value["timeout_seconds"] <= 0:
        raise ValueError("timeout_seconds must be positive and finite")
    ids = value["expected_case_ids"]
    if not isinstance(ids, list) or not ids or any(type(x) is not int or x < 1 for x in ids) or len(set(ids)) != len(ids):
        raise ValueError("expected_case_ids must be nonempty unique positive integers")
    for role in ROLES:
        item = value[role]
        if not isinstance(item, dict) or set(item) != {"cwd", "source_dir", "binary"}:
            raise ValueError(f"{role} requires cwd, source_dir, binary")
        for key in ("cwd", "source_dir"):
            path = Path(item[key]).resolve(strict=True)
            if not path.is_dir():
                raise ValueError(f"{role}.{key} must be a directory")
            item[key] = str(path)
        item["binary"] = str(regular(item["binary"]))
    masks = [os.environ.get(key, "") for key in ("ASCEND_RT_VISIBLE_DEVICES", "ASCEND_VISIBLE_DEVICES")]
    if any(masks) and "physical_device" not in value:
        raise ValueError("visibility-mapped devices require explicit physical_device for locking")
    value.setdefault("physical_device", value["device"])
    if type(value["physical_device"]) is not int or value["physical_device"] < 0:
        raise ValueError("physical_device must be a nonnegative integer")
    for mask in filter(None, masks):
        tokens = mask.split(",")
        if not all(token.strip().isdigit() for token in tokens):
            raise ValueError("unsupported visibility mask; use an explicit numeric device list")
        if value["device"] >= len(tokens) or int(tokens[value["device"]]) != value["physical_device"]:
            raise ValueError("physical_device disagrees with visibility-mapped logical device")
    cases = value["cases"]
    if not isinstance(cases, list) or [c.get("case_id") if isinstance(c, dict) else None for c in cases] != ids:
        raise ValueError("cases must exactly match expected_case_ids in order")
    for case in cases:
        if set(case) != {"case_id", "workload", "prepared_files", "baseline", "candidate"}:
            raise ValueError("each case requires workload, prepared_files and both commands")
        if not isinstance(case["workload"], dict) or not case["workload"]:
            raise ValueError("case workload must be a nonempty JSON object")
        content_hash(case["workload"])
        files = case["prepared_files"]
        if not isinstance(files, list) or not files or any(not isinstance(p, str) for p in files):
            raise ValueError("prepared_files must declare all immutable inputs, metadata and oracle data")
        case["prepared_files"] = [str(regular(path)) for path in files]
        if len(set(case["prepared_files"])) != len(files):
            raise ValueError("duplicate prepared file")
        for role in ROLES:
            item = case[role]
            if not isinstance(item, dict) or not {"command", "verify_command", "output_files"} <= set(item) or set(item) - {"command", "verify_command", "output_files", "launches_per_operator"}:
                raise ValueError("case role requires command, verify_command and output_files")
            for key in ("command", "verify_command"):
                argv(item[key], key)
                program = Path(item[key][0])
                if not program.is_absolute():
                    program = Path(value[role]["cwd"]) / program
                item[key][0] = str(regular(program))
            if item["command"][0] != value[role]["binary"]:
                raise ValueError("timing command must execute the declared operator binary directly")
            if not isinstance(item["output_files"], list) or not item["output_files"] or any(not isinstance(p, str) or not Path(p).is_absolute() for p in item["output_files"]):
                raise ValueError("output_files must list fresh absolute output paths")
            item["output_files"] = [str(Path(p).resolve()) for p in item["output_files"]]
            item.setdefault("launches_per_operator", 1)
            if type(item["launches_per_operator"]) is not int or item["launches_per_operator"] < 1:
                raise ValueError("launches_per_operator must be a positive integer")
    outputs = [Path(p) for c in cases for role in ROLES for p in c[role]["output_files"]]
    if len(outputs) != len(set(outputs)):
        raise ValueError("baseline/candidate outputs must be isolated across every role and case")
    protected = [Path(value[role]["source_dir"]) for role in ROLES] + [Path(p).parent for c in cases for p in c["prepared_files"]]
    for output in outputs:
        if output.exists() or output.is_symlink():
            raise ValueError("timed outputs must not exist before collection")
        if any(output == root or output.is_relative_to(root) for root in protected):
            raise ValueError("timed output overlaps a source tree or prepared-input directory")
    return value


def identities(config, case):
    result = {"workload_hash": content_hash(case["workload"]),
              "prepared_files": {p: file_hash(regular(p)) for p in case["prepared_files"]}}
    for role in ROLES:
        item = config[role]
        sources = source_inventory(item["source_dir"])
        verification = case[role]["verify_command"]
        programs = [regular(verification[0])]
        # Script interpreters are allowed; bind the actual verifier program as
        # well as its interpreter. Other oracle inputs belong in prepared_files.
        for token in verification[1:]:
            path = Path(token)
            if path.suffix in {".py", ".sh"}:
                programs.append(regular(path if path.is_absolute() else Path(item["cwd"]) / path))
        result[role] = {"binary_hash": file_hash(item["binary"]), "source_files": sources,
                        "source_hash": content_hash(sources),
                        "verifier_files": {str(p): file_hash(p) for p in programs}}
    return result


def unchanged(config, case, expected):
    actual = identities(config, case)
    if actual != expected:
        raise ValueError("binary/source/prepared/verifier identity changed during timing")
    return actual


@contextmanager
def device_lock(device, timeout):
    root = Path("/tmp/aprof-device-locks")
    root.mkdir(parents=True, exist_ok=True)
    with (root / f"device-{device}.lock").open("a+") as lock:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("device advisory lock is held by another hardware job")
                time.sleep(.05)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def terminate(process):
    # A dead process-group leader can leave a descendant holding stdout open.
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass
        if process.poll() is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                continue
    if process.poll() is None:
        process.wait(timeout=5)


class TimingChild:
    def __init__(self, command, cwd, env, path, timeout):
        self.timeout, self.path = timeout, Path(path)
        self.rows = queue.Queue()
        self.log = self.path.open("w")
        self.process = None
        self.reader = None
        self.receipt = {"argv": command, "cwd": cwd, "started_at": time.time(), "pid": None,
                        "finished_at": None, "exit_status": None, "log_path": str(self.path)}
        try:
            self.process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", bufsize=1,
                start_new_session=True)
            self.receipt["pid"] = self.process.pid
            def read():
                try:
                    for line in self.process.stdout:
                        self.log.write(line)
                        self.log.flush()
                        self.rows.put(line.rstrip("\r\n"))
                finally:
                    self.rows.put(None)
            self.reader = threading.Thread(target=read, daemon=True)
            self.reader.start()
        except BaseException:
            self.close(abort=True)
            raise

    def ready(self):
        if self.until("APROF_TIMING_READY"):
            raise ValueError("unexpected payload on timing READY")

    def until(self, prefix):
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"timing child did not emit {prefix}")
            try:
                row = self.rows.get(timeout=remaining)
            except queue.Empty:
                raise TimeoutError(f"timing child did not emit {prefix}") from None
            if row is None:
                raise RuntimeError(f"timing child exited before {prefix}; see {self.path}")
            if row.startswith("APROF_TIMING") and not row.startswith(prefix):
                raise ValueError("unexpected timing protocol message")
            if row.startswith(prefix):
                return row[len(prefix):]

    def sample(self, config, case, role, index):
        self.process.stdin.write("sample\n")
        self.process.stdin.flush()
        row = _json(self.until(PREFIX))
        if not isinstance(row, dict) or set(row) != SAMPLE_FIELDS:
            raise ValueError("invalid ACL-event sample fields")
        expected = {"schema_version": "1.0.0", "operator": config["operator"], "device": config["device"],
                    "source": "acl_event", "unit": "ns", "sample_index": index,
                    "warmup": config["warmup"], "repeat": config["repeat"],
                    "launches_per_operator": case[role]["launches_per_operator"]}
        if any(type(row[k]) is not type(v) or row[k] != v for k, v in expected.items()):
            raise ValueError("ACL-event sample identity/unit/index/protocol mismatch")
        duration = row["elapsed_ns"]
        if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
            raise ValueError("invalid ACL-event elapsed_ns")
        return row

    def close(self, abort=False):
        if self.log.closed:
            return self.receipt
        try:
            if self.process is not None:
                if abort:
                    terminate(self.process)
                elif self.process.poll() is None:
                    self.process.stdin.write("quit\n")
                    self.process.stdin.flush()
                    try:
                        self.process.wait(timeout=min(10, self.timeout))
                    except subprocess.TimeoutExpired:
                        terminate(self.process)
                        raise TimeoutError("timing child did not exit after quit")
        except BaseException:
            if self.process is not None:
                terminate(self.process)
            raise
        finally:
            if self.reader is not None:
                self.reader.join(timeout=min(1, self.timeout))
                if self.reader.is_alive():
                    terminate(self.process)
                    self.reader.join(timeout=5)
            self.log.close()
            if self.process is not None:
                self.process.stdin.close()
                self.process.stdout.close()
            self.receipt.update(finished_at=time.time(), exit_status=None if self.process is None else self.process.returncode,
                                log_hash=file_hash(self.path))
        if not abort and self.process.returncode != 0:
            raise RuntimeError("timing child failed after measurements")
        return self.receipt


def verify(command, cwd, path, timeout, receipt):
    receipt.update(argv=command, cwd=cwd, started_at=time.time(), finished_at=None, exit_status=None, log_path=str(path))
    process = None
    try:
        with Path(path).open("w") as log:
            process = subprocess.Popen(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                process.wait(timeout=timeout)
            except BaseException as error:
                receipt["error"] = {"type": type(error).__name__, "message": str(error)}
                terminate(process)
                raise
    finally:
        receipt.update(finished_at=time.time(), exit_status=None if process is None else process.returncode)
        if Path(path).exists():
            receipt["log_hash"] = file_hash(path)
    return receipt


def cv(values):
    return statistics.stdev(values) / statistics.fmean(values) if len(values) > 1 else 0.0


def geomean(values):
    return math.exp(statistics.fmean(math.log(value) for value in values))


def summarize(raw, config):
    gate = GateConfig.from_dict({})
    reasons, per_case = [], []
    if not raw["complete"]:
        reasons.append("timing collection or prepared-output verification incomplete")
    if config["mode"] != "formal":
        reasons.append("exploration screening is not formal timing evidence")
    if config["pairs"] < gate.min_pairs or config["warmup"] < 10:
        reasons.append("formal pair/warmup minimum not met")
    for case in config["expected_case_ids"]:
        rows = [r for r in raw["records"] if r["case_id"] == case and r["baseline"] is not None and r["candidate"] is not None]
        a = [r["baseline"]["elapsed_ns"] for r in rows]
        b = [r["candidate"]["elapsed_ns"] for r in rows]
        if len(rows) != config["pairs"] or [r["round"] for r in rows] != list(range(config["pairs"])):
            reasons.append(f"case {case}: incomplete independent pairs")
        ca, cb = (cv(a), cv(b)) if a else (None, None)
        if a and max(ca, cb) > gate.max_cv:
            reasons.append(f"case {case}: CV exceeds runtime threshold {gate.max_cv}")
        per_case.append({"case_id": case, "pair_count": len(rows), "baseline_samples_ns": a, "candidate_samples_ns": b,
                         "baseline_cv": ca, "candidate_cv": cb,
                         "baseline_median_ns": statistics.median(a) if a else None,
                         "candidate_median_ns": statistics.median(b) if b else None,
                         "regression": geomean([y / x for x, y in zip(a, b)]) - 1 if a else None,
                         "speedup": geomean([x / y for x, y in zip(a, b)]) if a else None})
    stable = not reasons
    suite_a = [geomean([case["baseline_samples_ns"][i] for case in per_case]) for i in range(config["pairs"])] if stable else []
    suite_b = [geomean([case["candidate_samples_ns"][i] for case in per_case]) for i in range(config["pairs"])] if stable else []
    if stable and max(cv(suite_a), cv(suite_b)) > gate.max_cv:
        reasons.append("suite CV exceeds runtime threshold")
        stable, suite_a, suite_b = False, [], []
    estimate, lcb = _paired_estimate(tuple(suite_a), tuple(suite_b), gate, config["operator"]) if stable else (None, None)
    return {"schema_version": "1.0.0", "unit": "ns", "aggregation": "equal_case_geometric_mean_per_round",
            "case_ids": config["expected_case_ids"], "mode": config["mode"], "stable": stable, "reasons": reasons,
            "per_case": per_case, "speedup": estimate, "speedup_lcb_95": lcb,
            "max_case_regression": max((c["regression"] for c in per_case if c["regression"] is not None), default=None),
            "gate_projection": {"baseline_samples_ns": suite_a, "candidate_samples_ns": suite_b,
                                "heldout_regressions": [c["regression"] for c in per_case] if stable else []},
            "authority": "measurement draft only; full correctness and runtime candidate gate required"}


def collect(value, output):
    config = config_value(value)
    with device_lock(config["physical_device"], config["timeout_seconds"]):
        return _collect(config, output)


def _collect(config, output):
    output = Path(output).resolve()
    for role in ROLES:
        if output == Path(config[role]["source_dir"]) or output.is_relative_to(Path(config[role]["source_dir"])):
            raise ValueError("output evidence directory must be outside operator source trees")
    output.mkdir(parents=True, exist_ok=False)
    save(output / "config.json", config)
    for case in config["cases"]:
        for role in ROLES:
            for path in case[role]["output_files"]:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
    raw = {"schema_version": "1.0.0", "operator": config["operator"], "host": socket.gethostname(),
           "device": config["device"], "physical_device": config["physical_device"], "unit": "ns", "source": "acl_event",
           "timing_scope": "complete_operator_device_event_interval", "case_ids": config["expected_case_ids"],
           "pairs": config["pairs"], "warmup": config["warmup"], "repeat": config["repeat"], "mode": config["mode"],
           "config_hash": content_hash(config), "producer_hash": file_hash(__file__),
           "runtime_version": RUNTIME_VERSION, "records": [], "case_executions": [], "complete": False}
    env = dict(os.environ, APROF_TIMING_INTERACTIVE="1", APROF_WARMUP=str(config["warmup"]), APROF_REPEAT=str(config["repeat"]))
    for key in ("APROF_CAPTURE_REPLAY", "APROF_SAMPLES"):
        env.pop(key, None)
    raw["environment"] = {key: env.get(key) for key in ("APROF_TIMING_INTERACTIVE", "APROF_WARMUP", "APROF_REPEAT", "APROF_CAPTURE_REPLAY", "ASCEND_RT_VISIBLE_DEVICES", "ASCEND_VISIBLE_DEVICES", "ASCEND_HOME_PATH", "ASCEND_OPP_PATH", "LD_LIBRARY_PATH")}
    try:
        runtime_root = Path(runtime_gates.__file__).resolve().parent
        runtime_files = {path.relative_to(runtime_root).as_posix(): file_hash(path)
                         for path in sorted(runtime_root.rglob("*.py"))}
        raw["producer_dependencies"] = {
            "profile_capture.py": file_hash(SCRIPTS / "profile_capture.py"),
            "device_timer.h": file_hash(SCRIPTS.parent / "assets/device_timer.h"),
            "runtime_source_files": runtime_files,
            "runtime_source_hash": content_hash(runtime_files),
        }
        raw["case_identities"] = {str(case["case_id"]): identities(config, case) for case in config["cases"]}
        for case in config["cases"]:
            before = raw["case_identities"][str(case["case_id"])]
            execution = {"case_id": case["case_id"], "workload": case["workload"], "identity_before": before,
                         "identity_after": None, "commands": {}, "verifications": {}, "exit_status": None,
                         "started_at": time.time(), "finished_at": None}
            raw["case_executions"].append(execution)
            children = {}
            try:
                for role in ROLES:
                    unchanged(config, case, before)
                    if any(Path(p).exists() or Path(p).is_symlink() for p in case[role]["output_files"]):
                        raise ValueError("timed output appeared before its role started")
                    child = TimingChild(case[role]["command"], config[role]["cwd"], env,
                        output / f"case-{case['case_id']:02d}-{role}.log", config["timeout_seconds"])
                    children[role] = child
                    execution["commands"][role] = child.receipt
                    child.ready()
                    unchanged(config, case, before)
                for index in range(config["pairs"]):
                    order = list(ROLES if index % 2 == 0 else reversed(ROLES))
                    record = {"case_id": case["case_id"], "round": index, "order": order,
                              "device": config["device"], "baseline": None, "candidate": None}
                    raw["records"].append(record)
                    for role in order:
                        record[role] = children[role].sample(config, case, role, index)
                    save(output / "raw_measurements.json", raw)
                for child in children.values():
                    child.close()
                unchanged(config, case, before)
                outputs = {}
                for role in ROLES:
                    for path in case[role]["output_files"]:
                        if Path(path).is_symlink() or not Path(path).is_file():
                            raise ValueError("timed role did not produce a regular isolated output")
                        outputs[path] = file_hash(path)
                execution["output_hashes"] = outputs
                for role in ROLES:
                    receipt = {}
                    execution["verifications"][role] = receipt
                    verify(case[role]["verify_command"], config[role]["cwd"],
                        output / f"case-{case['case_id']:02d}-{role}-verify.log", config["timeout_seconds"], receipt)
                    if receipt["exit_status"] != 0:
                        raise RuntimeError(f"{role} prepared-output verifier failed")
                    unchanged(config, case, before)
                    if any(Path(path).is_symlink() or file_hash(path) != digest for path, digest in outputs.items()):
                        raise ValueError("prepared-output verification modified a timed output")
                execution["identity_after"] = unchanged(config, case, before)
                execution["exit_status"] = 0
            finally:
                cleanup_errors = []
                for child in children.values():
                    try:
                        child.close(abort=True)
                    except Exception as error:
                        cleanup_errors.append(str(error))
                execution["finished_at"] = time.time()
                if cleanup_errors:
                    execution["cleanup_errors"] = cleanup_errors
                    if sys.exc_info()[0] is None:
                        raise RuntimeError("timing child cleanup failed: " + "; ".join(cleanup_errors))
        raw["complete"] = True
    except BaseException as error:
        raw["error"] = {"type": type(error).__name__, "message": str(error)}
        raise
    finally:
        save(output / "raw_measurements.json", raw)
        report = summarize(raw, config)
        save(output / "measurement_report.json", report)
        save(output / "timing_draft.json", {"schema_version": "1.0.0", "kind": "aprof_paired_timing_draft",
            "measurement_protocol": "persistent_acl_event_alternating_pairs_v1", "mode": config["mode"],
            "pair_count": config["pairs"], "production_minimum_met": raw["complete"] and config["mode"] == "formal" and config["pairs"] >= GateConfig.MIN_PAIRS and config["warmup"] >= 10,
            "measurement_complete": raw["complete"], "measurement_stable": report["stable"],
            "raw_measurements_hash": file_hash(output / "raw_measurements.json"),
            "measurement_report_hash": file_hash(output / "measurement_report.json"),
            "baseline_samples_ns": report["gate_projection"]["baseline_samples_ns"],
            "candidate_samples_ns": report["gate_projection"]["candidate_samples_ns"],
            "full_correctness_required": True, "authority": report["authority"]})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = collect(_json(args.config.read_text()), args.output)
    except Exception as error:
        print(f"device timing failed: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(args.output), "mode": report["mode"], "measurement_stable": report["stable"], "authority": "draft_only"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
