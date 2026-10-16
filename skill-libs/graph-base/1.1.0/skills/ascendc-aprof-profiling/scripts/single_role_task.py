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
        try:
            stdout, stderr = process.communicate(timeout=timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            timed_out = True
        return {"returncode": process.returncode, "pid": process.pid,
                "stdout": stdout, "stderr": stderr, "timed_out": timed_out}


def run_stage(root, name, argv, env, deadline, runner):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("统一采集总预算已耗尽")
    started_at, started = now(), time.monotonic()
    result = runner(argv, cwd=str(root), env=env, timeout_seconds=remaining)
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
    if result.get("timed_out") or time.monotonic() > deadline:
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
    if record != {**expected, "pid": stage["pid"]}:
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


def collect_case(config, case, root, declaration, deadline, runner, store, *, correctness_only=False, verified=None):
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
    oracle_command = command(case["oracle_command"])
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
                           *map(str, (SCRIPTS.parent / "assets").glob("device_*task*.h")),
                           str(SCRIPTS.parent / "assets/device_shared_timing.h"), *config["adapter_files"]]
        artifacts["collector"] = inventory(root, "collector", collector_files, store)
    oracle_source = snapshot(root, case["oracle_source"], "oracle", 0, store)
    checks = []
    if not isinstance(case["checks"], list) or not case["checks"]:
        raise ValueError("每个 case 必须预声明输出数值检查")
    seen = set()
    for index, check in enumerate(case["checks"]):
        actual = safe_child(root, check["actual"])
        if actual.exists() or actual in seen or not str(actual.relative_to(root)).startswith("outputs/"):
            raise ValueError("输出必须为 outputs 下互不重复的新文件")
        seen.add(actual)
        actual.parent.mkdir(parents=True, exist_ok=True)
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
        signature = {"oracle_source_sha256": oracle_source["sha256"], "checks": [
            {"actual_path": str(check["actual_path"].relative_to(root)),
             "expected_sha256": check["expected"]["sha256"],
             **{key: check[key] for key in ("dtype", "atol", "rtol", "equal_nan")}}
            for check in sorted(checks, key=lambda item: str(item["actual_path"]))]}
        if signature != verified["oracle_signature"]:
            raise ValueError("计时 oracle 或 golden 与完整正确性不一致")
    env = os.environ.copy()
    for key in tuple(env):
        if key.startswith("APROF_TASK_"):
            del env[key]
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
        profile = profile_tree(profile_root)
        before_export = profile_inventory(profile_root)
        if not before_export:
            raise ValueError("native profile 目录为空")
        log_prefixes = {}
        for name in before_export:
            if re.fullmatch(r"PROF_[^/]+/mindstudio_profiler_log/collection_(?:host|device_[0-9]+)\.log", name):
                log_prefixes[name] = (profile_root / name).read_bytes()
        export_command = [str(exporter_python), str(exporter_script), "export", "summary", "-dir", str(profile), "--format", "csv"]
        stages["export"] = run_stage(root, "export", export_command, env, deadline, runner)
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
    stages["oracle"] = run_stage(root, "oracle", oracle_command, env, deadline, runner)
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
        stages["hardware_after"] = run_stage(root, "hardware_after", hardware_command, env, deadline, runner)
        if hardware_report(root, stages["hardware_after"], config["device"]) != hardware:
            raise ValueError("采集期间设备身份或观测状态变化")
        write_json(root / "hardware.json", hardware)
        artifacts["hardware"] = reference(root, root / "hardware.json")
    identity = {"source_sha256": artifacts["source"]["sha256"], "binary_sha256": artifacts["binary"]["sha256"]}
    identity.update({name + "_ref": artifacts[name]["sha256"] for name in ("workload", "input", "hardware", "toolchain", "collector") if name in artifacts})
    if not correctness_only:
        write_json(root / "native_receipt.json", native)
        artifacts["native_receipt"] = reference(root, root / "native_receipt.json")
    oracle_receipt = {"status": "passed", "source_sha256": identity["source_sha256"],
                      "binary_sha256": identity["binary_sha256"], "input_ref": identity["input_ref"],
                      "output_sha256": artifacts["output"]["sha256"], "case_id": case_id,
                      "checks": checks, "oracle_source": oracle_source}
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
    replay_oracle(root, oracle_receipt, artifacts["output"], limits)
    store.replay_seconds += time.monotonic() - replay_started
    return path


def collect(config, output_root, *, timeout_seconds=600, runner=subprocess_runner, correctness_only=False):
    """顺序采集声明的 case；所有子步骤共享原始总预算，失败保留局部证据。"""
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError("总预算必须为正数")
    started = time.monotonic()
    deadline = started + timeout_seconds
    root = Path(output_root).absolute()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    store = SnapshotStore(root)
    try:
        if config.get("schema_version") != 1 or config.get("protocol") != PROTOCOL:
            raise ValueError("采集配置协议不匹配")
        declaration_path = original_file(config["declaration"]["path"])
        if sha256(declaration_path) != config["declaration"]["sha256"]:
            raise ValueError("预声明 hash 不匹配")
        declaration = json.loads(declaration_path.read_text())
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
        else:
            ref = config["correctness"]
            correctness_path = original_file(ref["path"])
            if sha256(correctness_path) != ref["sha256"]:
                raise ValueError("完整正确性记录 hash 不匹配")
            correctness = json.loads(correctness_path.read_text())
            replay_started = time.monotonic()
            replayed = replay_correctness(correctness_path, source=correctness["source_sha256"], operator=config["operator"],
                                          declaration_ref=config["declaration"]["sha256"], case_ids=declaration["correctness_case_ids"])
            store.replay_seconds += time.monotonic() - replay_started
            verified = {case_id: {"identity": identity, "oracle_signature": replayed["oracle_signatures"][case_id]}
                        for case_id, identity in replayed["cases"].items()}
        write_json(root / "config.json", config)
        captures = [collect_case(config, case, root / f"case_{case['case_id']}", declaration, deadline, runner, store,
                                 correctness_only=correctness_only, verified=verified.get(case["case_id"]))
                    for case in config["cases"]]
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
                               declaration_ref=result["declaration_ref"], case_ids=declaration["correctness_case_ids"])
            store.replay_seconds += time.monotonic() - replay_started
        else:
            result = {"protocol": PROTOCOL, "captures": [reference(root, path) for path in captures]}
            write_json(root / "collection.json", result)
        if time.monotonic() > deadline:
            raise TimeoutError("证据检查超过原始采集预算")
        return result
    except Exception as error:
        write_json(root / "failure.json", {"error": type(error).__name__, "message": str(error), "failed_at": now()})
        raise
    finally:
        write_json(root / "collection_costs.json", {"elapsed_seconds": time.monotonic() - started,
            "snapshot_seconds": store.elapsed_seconds, "replay_seconds": store.replay_seconds, "snapshot_copied_bytes": store.copied_bytes,
            "snapshot_linked_bytes": store.linked_bytes, "snapshot_unique_files": len(store.files)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True, help="预构建 adapter 及全部 case 的 JSON 配置")
    parser.add_argument("--output", type=Path, required=True, help="尚不存在的任务本地证据目录")
    parser.add_argument("--timeout-seconds", type=float, default=600, help="全部子步骤共用的总预算秒数")
    parser.add_argument("--correctness-only", action="store_true", help="先执行完整正确性并生成可供计时复用的证据，不启动 profiler")
    args = parser.parse_args()
    print(json.dumps(collect(json.loads(args.config.read_text()), args.output,
                             timeout_seconds=args.timeout_seconds, correctness_only=args.correctness_only), ensure_ascii=False))


if __name__ == "__main__":
    main()
