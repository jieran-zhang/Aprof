#!/usr/bin/env python3
"""运行已构建的算子 adapter，保存统一清 L2 Task 采集及可回放证据。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid

SCRIPTS = Path(__file__).resolve().parent
RELEASE = SCRIPTS.parents[2]
sys.path.insert(0, str(RELEASE / "runtime/src"))
from fast_task_samples import complete_calls
from aprof_runtime.execution_policy import wait, local_path, operation, append

PROTOCOL = "single_role_l2_clean_task_v1"
METRIC = "msprof.Task_Duration.complete_call"
NATIVE_PREFIX = "APROF_SINGLE_ROLE_TASK_JSON:"


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")


def reference(root, path):
    return {"path": str(path.relative_to(root)), "sha256": sha256(path)}


def safe_child(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("证据路径必须为非空相对路径")
    path = root / name
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ValueError("证据路径不能逃逸采集目录或指向软链接")
    return path


def original_file(value):
    path = Path(value)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError(f"依赖必须是绝对路径的普通文件: {value}")
    return path


class SnapshotStore:
    """先复制到任务私有池，再链接到各 case；绝不链接可变的用户源文件。"""
    def __init__(self, root):
        self.root = root / "_snapshots"
        self.root.mkdir(mode=0o700)
        self.files = {}
        self.copied_bytes = 0
        self.linked_bytes = 0
        self.elapsed_seconds = 0.0
        self.replay_seconds = 0.0
        self.verified_oracles = set()

    @staticmethod
    def identity(path):
        info = original_file(path).stat()
        return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)

    def bind(self, source, destination):
        started = time.monotonic()
        state = self.identity(source)
        if source not in self.files:
            digest = sha256(source)
            frozen = self.root / str(len(self.files))
            shutil.copyfile(source, frozen)
            if self.identity(source) != state or sha256(frozen) != digest or sha256(source) != digest:
                raise ValueError("冻结依赖时文件发生变化")
            frozen.chmod(0o400)
            self.files[source] = (state, digest, frozen)
            self.copied_bytes += frozen.stat().st_size
        previous, digest, frozen = self.files[source]
        if state != previous:
            raise ValueError("复用快照时原始依赖发生变化")
        os.link(frozen, destination)
        self.linked_bytes += state[2]
        self.elapsed_seconds += time.monotonic() - started
        return digest

    def verify_metadata(self):
        for path, (state, _, _) in self.files.items():
            if self.identity(path) != state:
                raise ValueError(f"采集期间冻结依赖身份变化: {path}")

    def verify(self):
        started = time.monotonic()
        self.verify_metadata()
        for path, (_, digest, _) in self.files.items():
            if sha256(path) != digest:
                raise ValueError(f"采集期间冻结依赖内容变化: {path}")
        self.elapsed_seconds += time.monotonic() - started


def snapshot(root, source, category, index, store):
    source = original_file(source)
    destination = root / "evidence" / category / f"{index:04d}-{source.name}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = store.bind(source, destination)
    return {"path": str(destination.relative_to(root)), "sha256": digest}


def inventory(root, name, paths, store):
    if not isinstance(paths, list) or not paths:
        raise ValueError(f"{name} 依赖清单不能为空")
    refs = []
    for index, path in enumerate(dict.fromkeys(paths)):
        refs.append(snapshot(root, path, name, index, store))
    destination = root / f"{name}.json"
    write_json(destination, {"files": refs})
    return reference(root, destination)


def subprocess_runner(argv, *, cwd, env, timeout_seconds):
    with subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, start_new_session=True) as process:
        stdout, stderr = wait(process, target_seconds=timeout_seconds,
            checkpoint=Path(cwd)/"checkpoints.jsonl", communicate=True)
        return {"returncode": process.returncode, "pid": process.pid,
                "stdout": stdout, "stderr": stderr, "timed_out": False}


def run_stage(root, name, argv, env, deadline, runner):
    remaining = deadline - time.monotonic()
    started_at, started = now(), time.monotonic()
    with operation(root, env.get("APROF_OPERATION_STAGE", "C4"), name,
                   target=max(0, remaining), case=env.get("APROF_OPERATION_CASE"),
                   implementation=env.get("APROF_OPERATION_IMPLEMENTATION"),
                   parent=env.get("APROF_OPERATION_PARENT")) as cost:
        result = runner(argv, cwd=str(root), env=env, timeout_seconds=max(0, remaining))
        cost["child_pid"] = result["pid"]
    logs = root / "logs"
    logs.mkdir(exist_ok=True)
    refs = {}
    for channel in ("stdout", "stderr"):
        path = logs / f"{name}.{channel}"
        data = result[channel]
        path.write_bytes(data.encode() if isinstance(data, str) else data)
        refs[channel] = reference(root, path)
    receipt = {"argv": argv, "cwd": str(root), "returncode": result["returncode"],
               "pid": result["pid"], "started_at": started_at, "finished_at": now(),
               "elapsed_seconds": time.monotonic() - started, **refs}
    write_json(logs / f"{name}.json", receipt)
    if result.get("timed_out"):
        raise TimeoutError(f"{name} 超过原始采集预算")
    if result["returncode"] != 0:
        raise ValueError(f"{name} 退出码非零: {result['returncode']}")
    return receipt


def command(value):
    if not isinstance(value, list) or not value or any(not isinstance(x, str) or not x for x in value):
        raise ValueError("命令必须为非空 argv 字符串数组")
    original_file(value[0])
    return value


def stage_text(root, stage):
    return safe_child(root, stage["stdout"]["path"]).read_text(encoding="utf-8")


def native_record(root, stage, expected):
    records = [line[len(NATIVE_PREFIX):] for line in stage_text(root, stage).splitlines()
               if line.startswith(NATIVE_PREFIX)]
    if len(records) != 1:
        raise ValueError("native stdout 必须恰好包含一条采集记录")
    record = json.loads(records[0])
    if {k:v for k,v in record.items() if k != "physical_id"} != {**expected, "pid": stage["pid"]}:
        raise ValueError("native 采集身份、次数或输入完整性记录不匹配")
    return record


def profile_tree(root):
    directories = [p for p in root.rglob("PROF_*") if p.is_dir()]
    if len(directories) != 1:
        raise ValueError("每个新进程必须产生且只产生一个 PROF 目录")
    return directories[0]


def profile_inventory(root):
    result = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("原始 profile 不允许软链接")
        if path.is_file():
            result[str(path.relative_to(root))] = sha256(path)
    return result


def selected_table(profile):
    primary = list(profile.rglob("kernel_details.csv"))
    fallback = list(profile.rglob("op_summary*.csv"))
    if len(primary) > 1 or not primary and len(fallback) != 1:
        raise ValueError("必须存在唯一完整 Task 表")
    if primary:
        return "kernel_details", primary[0]
    return "op_summary", fallback[0]


def hardware_report(root, stage, device):
    value = json.loads(stage_text(root, stage))
    if (not isinstance(value, dict) or value.get("device") != device
            or not isinstance(value.get("physical_device"), str) or not value["physical_device"]
            or not isinstance(value.get("soc_version"), str) or not value["soc_version"]):
        raise ValueError("硬件 probe 必须输出 device、physical_device、soc_version 的 JSON")
    return value


def original_spec(case, *, root=None, store=None):
    """Freeze the original program and data; its contract ignores archive paths."""
    from aprof_runtime.original_oracle import validate
    spec = dict(case["oracle_replay"])
    files = {}
    for index, (name, source) in enumerate(spec["files"].items()):
        path = original_file(source)
        files[name] = (snapshot(root, source, "oracle_bundle", index, store) if store is not None
                       else {"path": str(path.relative_to("/")), "sha256": sha256(path)})
    spec["files"] = files
    source = original_file(case["oracle_source"])
    oracle_source = (snapshot(root, source, "oracle", 0, store) if store is not None
                     else {"path": str(source.relative_to("/")), "sha256": sha256(source)})
    validate(root if store is not None else Path("/"), spec, oracle_source, case["workload"]["oracle_limits"])
    return spec, oracle_source


def preflight(config, *, deadline=None):
    """Check every oracle before launching any case; this is not NPU validation."""
    from aprof_runtime.unified_timing import FORMATS
    from aprof_runtime.original_oracle import OracleFailure, check_environment
    environments = set()
    for case in config["cases"]:
        if "oracle_replay" in case:
            spec, _ = original_spec(case)
            key = json.dumps(spec["environment"], sort_keys=True)
            if key not in environments:
                remaining = 30
                check_environment(spec["environment"], remaining)
                environments.add(key)
        else:
            if case["workload"]["oracle_limits"].get("mode"):
                raise OracleFailure("oracle_adapter_unsupported", "原 oracle 缺少 replay bundle")
            for check in case["checks"]:
                if check["dtype"] not in FORMATS:
                    raise OracleFailure("oracle_adapter_unsupported", f"case {case['case_id']} 的 {check['dtype']} 需要原 oracle adapter")
    return {"status": "capability_checked", "case_ids": [case["case_id"] for case in config["cases"]],
            "npu_executed": False}


def collect_case(config, case, root, declaration, deadline, runner, store, *, correctness_only=False, verified=None, deferred=False):
    root.mkdir(mode=0o700)
    artifacts = {}
    captured_at = now()
    case_id = case["case_id"]
    if type(case_id) is not int or case_id <= 0 or case_id not in declaration["correctness_case_ids" if correctness_only else "case_ids"]:
        raise ValueError("case 不在预声明计时集合内")
    cache = config.get("cache_policy", {})
    if not correctness_only and (cache.get("eviction_kernel") != "CannBenchCacheClean"
            or type(cache.get("l2_bytes")) is not int or cache["l2_bytes"] <= 0
            or type(cache.get("eviction_bytes")) is not int or cache["eviction_bytes"] <= cache["l2_bytes"]
            or cache.get("address_policy") != "reuse-one-allocation"):
        raise ValueError("必须声明真实 L2 容量及更大的清理缓冲区")
    for name, paths in (("source", config["source_files"]), ("input", case["input_files"])):
        artifacts[name] = inventory(root, name, paths, store)
    artifacts["binary"] = snapshot(root, config["binary"], "binary", 0, store)
    artifacts["declaration"] = snapshot(root, config["declaration"]["path"], "declaration", 0, store)
    if artifacts["declaration"]["sha256"] != config["declaration"]["sha256"]:
        raise ValueError("预声明文件在采集前发生变化")
    write_json(root / "workload.json", case["workload"])
    artifacts["workload"] = reference(root, root / "workload.json")
    limits = case["workload"]["oracle_limits"]
    native_command = command(case["correctness_command" if correctness_only else "command"])
    original = "oracle_replay" in case
    trusted = config.get("baseline_status") == "assumed" and not correctness_only
    if trusted:
        from aprof_runtime.unified_timing import check_baseline_trust
        check_baseline_trust(declaration, {"source_sha256": artifacts["source"]["sha256"],
            "binary_sha256": artifacts["binary"]["sha256"]})
    oracle_command = command([case["oracle_replay"]["environment"]["python"], case["oracle_source"]]
                             if original else case["oracle_command"])
    if Path(native_command[0]) != Path(config["binary"]):
        raise ValueError("native 命令必须直接执行绑定的已构建 adapter")
    if verified is not None:
        for name, key in (("source", "source_sha256"), ("binary", "binary_sha256"),
                          ("input", "input_ref"), ("workload", "workload_ref")):
            if artifacts[name]["sha256"] != verified["identity"][key]:
                raise ValueError(f"计时 {name} 与完整正确性不一致")
    if not correctness_only:
        hardware_command = command(config["hardware_probe_command"])
        exporter_python = original_file(config["export_python"])
        exporter_script = original_file(config["export_script"])
        tool_files = [*config["toolchain_files"], str(exporter_python), str(exporter_script),
                      oracle_command[0], hardware_command[0], case["oracle_source"]]
        for argv in (hardware_command, oracle_command):
            tool_files.extend(arg for arg in argv[1:] if Path(arg).is_absolute() and Path(arg).is_file())
        artifacts["toolchain"] = inventory(root, "toolchain", tool_files, store)
        collector_files = [str(SCRIPTS / "single_role_task.py"), str(SCRIPTS / "fast_task_samples.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/unified_task_samples.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/unified_timing.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/task_statistics.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/median_timing.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/original_oracle.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/validation_cache.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/execution_policy.py"),
                           str(RELEASE / "runtime/src/aprof_runtime/device_session.py"),
                           *map(str, (SCRIPTS.parent / "assets").glob("device_*task*.h")),
                           str(SCRIPTS.parent / "assets/device_shared_timing.h"), *config["adapter_files"]]
        artifacts["collector"] = inventory(root, "collector", collector_files, store)
    if original:
        replay, oracle_source = original_spec(case, root=root, store=store)
        configured_checks = [{**value, "oracle_path": name} for name, value in replay["outputs"].items()]
    else:
        oracle_source = snapshot(root, case["oracle_source"], "oracle", 0, store)
        configured_checks = case["checks"]
    checks = []
    if not isinstance(configured_checks, list) or not configured_checks:
        raise ValueError("每个 case 必须预声明输出数值检查")
    seen = set()
    for index, check in enumerate(configured_checks):
        actual = safe_child(root, check["actual"])
        if actual.exists() or actual in seen or not str(actual.relative_to(root)).startswith("outputs/"):
            raise ValueError("输出必须为 outputs 下互不重复的新文件")
        seen.add(actual)
        actual.parent.mkdir(parents=True, exist_ok=True)
        if original:
            checks.append({"dtype": check["dtype"], "oracle_path": check["oracle_path"], "actual_path": actual})
            continue
        for key in ("atol", "rtol"):
            if (type(check[key]) not in (int, float) or not math.isfinite(check[key])
                    or check[key] < 0 or check[key] > limits[key]):
                raise ValueError("输出容差超出冻结 workload")
        if check.get("equal_nan", False) and not limits.get("equal_nan", False):
            raise ValueError("输出 NaN 策略超出冻结 workload")
        expected = snapshot(root, check["expected"], "expected", index, store)
        checks.append({**{key: check[key] for key in ("dtype", "atol", "rtol")},
                       "equal_nan": check.get("equal_nan", False), "expected": expected,
                       "actual_path": actual})
    if verified is not None:
        from aprof_runtime.unified_timing import receipt_signature
        pending = {"oracle_source": oracle_source, "checks": [
            {**{k: v for k, v in check.items() if k != "actual_path"},
             "actual": {"path": str(check["actual_path"].relative_to(root))}} for check in checks]}
        if original:
            pending["replay"] = replay
        signature = receipt_signature(pending)
        if signature != verified["oracle_signature"]:
            raise ValueError("计时 oracle 或 golden 与完整正确性不一致")
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("APROF_TASK_"):
            del env[key]
    env.update(APROF_OPERATION_STAGE="C3" if correctness_only else "C4",
               APROF_OPERATION_CASE=str(case_id), APROF_OPERATION_IMPLEMENTATION=config["implementation"],
               APROF_OPERATION_PARENT=str(root.parent))
    stages = {}
    if correctness_only:
        stages["execute"] = run_stage(root, "execute", native_command, env, deadline, runner)
    else:
        profile_root = root / "profile"
        profile_root.mkdir(mode=0o700)
        capture_id = uuid.uuid4().hex
        env.update(APROF_TASK_PROFILE_DIR=str(profile_root), APROF_TASK_CAPTURE_ID=capture_id,
                   APROF_TASK_CASE_ID=str(case_id))
        stages["hardware_before"] = run_stage(root, "hardware_before", hardware_command, env, deadline, runner)
        hardware = hardware_report(root, stages["hardware_before"], config["device"])
        stages["native"] = run_stage(root, "native", native_command, env, deadline, runner)
        native = native_record(root, stages["native"], {
            "protocol": PROTOCOL, "operator": config["operator"], "implementation": config["implementation"],
            "case_id": case_id, "capture_id": capture_id, "device": config["device"],
            "warmup_calls": 5, "formal_calls": 20, "l2_bytes": cache["l2_bytes"],
            "eviction_bytes": cache["eviction_bytes"], "input_bytes_unchanged": True})
        if config.get("native_physical_identity") and hardware["physical_device"].rsplit("/physical-",1)[-1] != str(native.get("physical_id")):
            raise ValueError("native physical identity differs from device session")
        profile = profile_tree(profile_root)
        stages["hardware_after"] = run_stage(root, "hardware_after", hardware_command, env, deadline, runner)
        if hardware_report(root, stages["hardware_after"], config["device"]) != hardware:
            raise ValueError("采集期间静态设备身份变化")
    state = {k: v for k, v in locals().items() if k in STATE_KEYS}
    state.update(replay=replay if original else None, hardware=hardware if not correctness_only else None,
                 native=native if not correctness_only else None)
    serial = {**state, "checks": [{**c, "actual_path": str(c["actual_path"].relative_to(root))} for c in checks]}
    write_json(root / "pending.json", serial)
    if deferred:
        return root / "pending.json"
    return finish_case(root / "pending.json", deadline=deadline, runner=runner, store=store)


STATE_KEYS = ['config', 'case', 'declaration', 'correctness_only', 'artifacts', 'checks', 'stages', 'original', 'oracle_source', 'trusted', 'captured_at', 'cache']


def finish_case(pending, *, deadline, runner=subprocess_runner, store=None):
    pending = Path(pending)
    root = pending.parent
    state = json.loads(pending.read_text())
    if (root / "capture.json").exists():
        from aprof_runtime.unified_timing import replay_capture
        replay_capture(root / "capture.json")
        return root / "capture.json"
    state["checks"] = [{**c, "actual_path": safe_child(root, c["actual_path"])} for c in state["checks"]]
    return _finish_case(root=root, deadline=deadline, runner=runner, store=store, **state)


def _finish_case(*, root, deadline, runner, store, config, case, declaration, correctness_only, artifacts, checks, stages, original, oracle_source, trusted, captured_at, cache, replay, hardware, native):
    case_id = case["case_id"]
    limits = case["workload"]["oracle_limits"]
    env = os.environ.copy()
    env.update(APROF_OPERATION_STAGE="C3" if correctness_only else "C4",
               APROF_OPERATION_CASE=str(case_id), APROF_OPERATION_IMPLEMENTATION=config["implementation"],
               APROF_OPERATION_PARENT=str(root.parent))
    profile_root = root / "profile"
    profile = profile_tree(profile_root) if not correctness_only else None
    if not correctness_only:
        before_export = profile_inventory(profile_root)
        if not before_export:
            raise ValueError("native profile 目录为空")
        log_prefixes = {}
        for name in before_export:
            if re.fullmatch(r"PROF_[^/]+/mindstudio_profiler_log/collection_(?:host|device_[0-9]+)\.log", name):
                log_prefixes[name] = (profile_root / name).read_bytes()
        export_command = [config["export_python"], config["export_script"], "export", "summary", "-dir", str(profile), "--format", "csv"]
        export_name = "export" if not (root/"logs/export.json").exists() else "export_"+uuid.uuid4().hex
        stages["export"] = run_stage(root, export_name, export_command, env, deadline, runner)
        if profile_tree(profile_root) != profile:
            raise ValueError("export 改变了原始 PROF 目录")
        after_export = profile_inventory(profile_root)
        prefix_refs = []
        for path, digest in before_export.items():
            if after_export.get(path) != digest:
                if path not in log_prefixes or not (profile_root / path).read_bytes().startswith(log_prefixes[path]):
                    raise ValueError("export 改写了原始 profile 文件")
                prefix = root / "logs" / f"export_prefix_{len(prefix_refs)}.bin"
                prefix.write_bytes(log_prefixes[path])
                prefix_refs.append({"profile_path": str(Path("profile") / path), "prefix": reference(root, prefix)})
        table_name, table = selected_table(profile)
        complete_calls(table if table_name == "kernel_details" else None,
                       table if table_name == "op_summary" else None, case["kernel_names"])
        artifacts["task_csv"] = reference(root, table)
    output_before_oracle = {}
    for check in checks:
        actual = safe_child(root, str(check["actual_path"].relative_to(root)))
        output_before_oracle[actual] = sha256(original_file(actual))
    if trusted:
        stages["oracle"] = {"kind": "baseline_assumed", "reason": "user_provided_baseline",
                            "oracle_executions": 0, "elapsed_seconds": 0.0}
    elif original:
        from aprof_runtime.original_oracle import execute
        pending = {"source_sha256": artifacts["source"]["sha256"], "binary_sha256": artifacts["binary"]["sha256"],
                   "input_ref": artifacts["input"]["sha256"], "workload_ref": artifacts["workload"]["sha256"], "case_id": case_id,
                   "replay": replay, "oracle_source": oracle_source, "checks": [
            {**{k: v for k, v in check.items() if k != "actual_path"},
             "actual": reference(root, check["actual_path"])} for check in checks]}
        stages["oracle"] = execute(root, pending, limits, deadline=deadline, logs=root / "logs", verified=store.verified_oracles if store is not None else None, reuse=True)
    else:
        stages["oracle"] = run_stage(root, "oracle", command(case["oracle_command"]), env, deadline, runner)
    actual_files = []
    for check in checks:
        actual = check.pop("actual_path")
        original_file(actual)
        if sha256(actual) != output_before_oracle[actual]:
            raise ValueError("oracle 改写了 native 实际输出")
        check["actual"] = reference(root, actual)
        actual_files.append({**check["actual"], "dtype": check["dtype"]})
    write_json(root / "output.json", {"files": actual_files})
    artifacts["output"] = reference(root, root / "output.json")
    if not correctness_only:
        if hardware_report(root, stages["hardware_after"], config["device"]) != hardware:
            raise ValueError("采集期间设备身份或观测状态变化")
        write_json(root / "hardware.json", hardware)
        artifacts["hardware"] = reference(root, root / "hardware.json")
    identity = {"source_sha256": artifacts["source"]["sha256"], "binary_sha256": artifacts["binary"]["sha256"]}
    identity.update({name + "_ref": artifacts[name]["sha256"] for name in ("workload", "input", "hardware", "toolchain", "collector") if name in artifacts})
    if not correctness_only:
        write_json(root / "native_receipt.json", native)
        artifacts["native_receipt"] = reference(root, root / "native_receipt.json")
    oracle_receipt = {"status": "assumed" if trusted else "passed", "workload_ref": identity["workload_ref"], "source_sha256": identity["source_sha256"],
                      "binary_sha256": identity["binary_sha256"], "input_ref": identity["input_ref"],
                      "output_sha256": artifacts["output"]["sha256"], "case_id": case_id,
                      "checks": checks, "oracle_source": oracle_source}
    if original:
        oracle_receipt["replay"] = replay
    write_json(root / "oracle_receipt.json", oracle_receipt)
    artifacts["oracle_receipt"] = reference(root, root / "oracle_receipt.json")
    execution = {"status": "passed", "returncode": 0, "source_sha256": identity["source_sha256"],
                 "binary_sha256": identity["binary_sha256"], "input_ref": identity["input_ref"],
                 "case_id": case_id, "oracle_receipt_sha256": artifacts["oracle_receipt"]["sha256"], "stages": stages}
    if not correctness_only:
        execution.update(task_csv_sha256=artifacts["task_csv"]["sha256"],
                         native_receipt_sha256=artifacts["native_receipt"]["sha256"],
                         profile_files=[{"path": str(Path("profile") / path), "sha256": digest}
                                        for path, digest in sorted(after_export.items())],
                         profile_log_prefixes=prefix_refs)
    write_json(root / "execution_receipt.json", execution)
    artifacts["execution_receipt"] = reference(root, root / "execution_receipt.json")
    if store is not None:
        store.verify_metadata()
    manifest = {"schema_version": 1, "protocol": PROTOCOL, "operator": config["operator"],
                "case_id": case_id, "captured_at": captured_at, "identity": identity,
                "declaration_ref": artifacts["declaration"]["sha256"], "artifacts": artifacts}
    if correctness_only:
        manifest["protocol"] = "single_role_correctness_case_v1"
    else:
        manifest.update(cache_policy=cache, metric=METRIC, warmup_calls=5, formal_calls=20,
                        kernel_names=case["kernel_names"], task_table=table_name)
    path = root / "capture.json"
    write_json(path, manifest)
    from aprof_runtime.unified_timing import replay_oracle
    replay_started = time.monotonic()
    if not original and not trusted:
        replay_oracle(root, oracle_receipt, artifacts["output"], limits, deadline=deadline)
    if store is not None:
        store.replay_seconds += time.monotonic() - replay_started
    return path


def collection_steps(config, output_root, *, timeout_seconds=600, runner=subprocess_runner, correctness_only=False):
    """顺序采集声明的 case；所有子步骤共享原始总预算，失败保留局部证据。"""
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("总预算必须为正数")
    started = time.monotonic()
    deadline = started + timeout_seconds
    root = local_path(output_root)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    store = SnapshotStore(root)
    try:
        if config.get("schema_version") != 1 or config.get("protocol") != PROTOCOL:
            raise ValueError("采集配置协议不匹配")
        preflight(config, deadline=deadline)
        declaration_path = original_file(config["declaration"]["path"])
        if sha256(declaration_path) != config["declaration"]["sha256"]:
            raise ValueError("预声明 hash 不匹配")
        from aprof_runtime.unified_timing import declaration as validate_declaration
        declaration = validate_declaration(declaration_path.parent,
                                          {"path": declaration_path.name, "sha256": config["declaration"]["sha256"]})
        if datetime.fromisoformat(declaration["created_at"].replace("Z", "+00:00")) > datetime.now(timezone.utc):
            raise ValueError("必须先预声明再采集")
        case_ids = [case["case_id"] for case in config["cases"]]
        if not case_ids or len(set(case_ids)) != len(case_ids):
            raise ValueError("case 集合为空或重复")
        from aprof_runtime.unified_timing import replay_correctness
        verified = {}
        if correctness_only:
            if set(case_ids) != set(declaration["correctness_case_ids"]):
                raise ValueError("正确性入口必须覆盖全部声明 case")
        elif config.get("baseline_status") != "assumed":
            ref = config["correctness"]
            correctness_path = original_file(ref["path"])
            if sha256(correctness_path) != ref["sha256"]:
                raise ValueError("完整正确性记录 hash 不匹配")
            correctness = json.loads(correctness_path.read_text())
            replay_started = time.monotonic()
            replayed = replay_correctness(correctness_path, source=correctness["source_sha256"], operator=config["operator"],
                                          declaration_ref=config["declaration"]["sha256"], case_ids=declaration["correctness_case_ids"], deadline=deadline, verified=store.verified_oracles)
            store.replay_seconds += time.monotonic() - replay_started
            verified = {case_id: {"identity": identity, "oracle_signature": replayed["oracle_signatures"][case_id]}
                        for case_id, identity in replayed["cases"].items()}
        write_json(root / "config.json", config)
        yield {"prepared": str(root)}
        pending = [collect_case(config, case, root / f"case_{case['case_id']}", declaration, deadline, runner, store,
                                 correctness_only=correctness_only, verified=verified.get(case["case_id"]), deferred=True)
                    for case in config["cases"]]
        # Caller can capture the other implementation before any heavy export/oracle.
        yield {"pending": [str(p) for p in pending], "root": str(root)}
        captures = [finish_case(path, deadline=deadline, runner=runner, store=store) for path in pending]
        store.verify()
        if correctness_only:
            sources = {json.loads(path.read_text())["identity"]["source_sha256"] for path in captures}
            if len(sources) != 1:
                raise ValueError("正确性采集中源码发生变化")
            result = {"schema_version": 1, "operator": config["operator"], "source_sha256": sources.pop(),
                      "declaration_ref": config["declaration"]["sha256"], "cases": [reference(root, path) for path in captures]}
            write_json(root / "correctness.json", result)
            replay_started = time.monotonic()
            replay_correctness(root / "correctness.json", source=result["source_sha256"], operator=config["operator"],
                               declaration_ref=result["declaration_ref"], case_ids=declaration["correctness_case_ids"], deadline=deadline, verified=store.verified_oracles)
            store.replay_seconds += time.monotonic() - replay_started
        else:
            result = {"protocol": PROTOCOL, "captures": [reference(root, path) for path in captures]}
            write_json(root / "collection.json", result)
        yield result
    except Exception as error:
        write_json(root / "failure.json", {"error": type(error).__name__, "reason": getattr(error, "reason", "evidence_or_execution_invalid"),
                                           "message": str(error), "failed_at": now()})
        raise
    finally:
        write_json(root / "collection_costs.json", {"elapsed_seconds": time.monotonic() - started, "target_seconds": timeout_seconds,
            "overrun_seconds": max(0, time.monotonic()-deadline), "budget_warnings": ["target_exceeded"] if time.monotonic()>deadline else [],
            "snapshot_seconds": store.elapsed_seconds, "replay_seconds": store.replay_seconds, "snapshot_copied_bytes": store.copied_bytes,
            "snapshot_linked_bytes": store.linked_bytes, "snapshot_unique_files": len(store.files)})


def collect(config, output_root, **kwargs):
    if config.get("device_probe_session") and not kwargs.get("correctness_only") and "runner" not in kwargs:
        from aprof_runtime.device_session import DeviceSession
        probe = DeviceSession(config["hardware_probe_command"], Path(output_root).parent/"device-session", subprocess_runner)
        try:
            return collect(config, output_root, runner=probe, **kwargs)
        finally:
            probe.close()
    steps = collection_steps(config, output_root, **kwargs)
    next(steps)
    next(steps)
    result = next(steps)
    next(steps, None)
    return result


def collect_pair(baseline, candidate, output_root, **kwargs):
    """All A/B native calls precede all profiler export, serial on one device."""
    if baseline.get("device_probe_session") and "runner" not in kwargs:
        from aprof_runtime.device_session import DeviceSession
        if baseline["hardware_probe_command"] != candidate["hardware_probe_command"]:
            raise ValueError("A/B probe identity differs")
        probe = DeviceSession(baseline["hardware_probe_command"], Path(output_root).parent/"device-session", subprocess_runner)
        try:
            return collect_pair(baseline, candidate, output_root, runner=probe, **kwargs)
        finally:
            probe.close()
    root = local_path(output_root)
    root.mkdir(parents=True, exist_ok=False)
    a = collection_steps(baseline, root/"A", **kwargs)
    b = collection_steps(candidate, root/"B", **kwargs)
    try:
        next(a)
        next(b)
        next(a)
        next(b)
        results = {"baseline": next(a), "candidate": next(b)}
        next(a, None); next(b, None)
        return results
    finally:
        a.close(); b.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="预构建 adapter 及全部 case 的 JSON 配置")
    parser.add_argument("--output", type=Path, required=True, help="尚不存在的任务本地证据目录")
    parser.add_argument("--timeout-seconds", type=float, default=600, help="全部子步骤共用的总预算秒数")
    parser.add_argument("--correctness-only", action="store_true", help="先执行完整正确性并生成可供计时复用的证据，不启动 profiler")
    parser.add_argument("--preflight-only", action="store_true", help="在启动任何 native 进程前检查全部 case 的 oracle 能力；不代表设备链路已通过")
    args = parser.parse_args()
    if args.preflight_only:
        result = preflight(json.loads(args.config.read_text()), deadline=time.monotonic() + args.timeout_seconds)
        write_json(args.output, result)
        print(json.dumps(result, ensure_ascii=False))
        return
    print(json.dumps(collect(json.loads(args.config.read_text()), args.output,
                             timeout_seconds=args.timeout_seconds, correctness_only=args.correctness_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
