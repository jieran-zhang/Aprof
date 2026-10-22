"""Replay a trusted, frozen Python oracle without replacing its numerical rules."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile
import time

from .errors import ContractError
from .jsonio import content_hash
from .unified_timing import fields, file_hash, reference, require

MODE = "original_python_v1"
_CHECKED_ENVIRONMENTS = set()


class OracleFailure(ContractError):
    def __init__(self, reason, message):
        self.reason = reason
        super().__init__(f"{reason}: {message}")


def relative_name(name):
    require(isinstance(name, str) and name and not Path(name).is_absolute()
            and all(part not in ("", ".", "..") for part in name.split("/"))
            and not name.startswith(".aprof-"), "oracle bundle 路径无效")
    return name


def contract(spec):
    """Exclude storage locations, but bind every semantic input and output mapping."""
    return content_hash({**spec, "files": {name: ref["sha256"] for name, ref in spec["files"].items()}})


def config_contract(spec):
    """Called during preparation, before the workload is frozen or executed."""
    return contract({**spec, "files": {name: {"sha256": file_hash(path)} for name, path in spec["files"].items()}})


def check_environment(environment, timeout):
    code = "import importlib.metadata,json,sys; p=json.loads(sys.argv[1]); assert all(importlib.metadata.version(k)==v for k,v in p.items()), 'package version mismatch'"
    try:
        result = subprocess.run([environment["python"], "-I", "-c", code, json.dumps(environment["packages"])],
                                capture_output=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OracleFailure("oracle_environment_unavailable", str(exc)) from exc
    if result.returncode:
        raise OracleFailure("oracle_environment_unavailable", result.stderr.decode(errors="replace")[-2000:])


def validate(root, spec, oracle_source, limits):
    fields(spec, {"mode", "entrypoint", "argv", "files", "outputs", "result", "environment", "timeout_seconds"}, "原 oracle 回放")
    require(spec["mode"] == MODE, "oracle_adapter_unsupported: 未知原 oracle adapter")
    fields(limits, {"mode", "contract_sha256"}, "原 oracle 冻结契约")
    require(limits["mode"] == MODE and limits["contract_sha256"] == contract(spec), "原 oracle 契约与 workload 不符")
    require(isinstance(spec["files"], dict) and spec["files"], "oracle 依赖闭包为空")
    paths = {relative_name(name): reference(root, ref) for name, ref in spec["files"].items()}
    reference(root, oracle_source)
    require(spec["entrypoint"] in paths and spec["files"][spec["entrypoint"]]["sha256"] == oracle_source["sha256"],
            "oracle 入口必须是绑定的原始源码")
    require(isinstance(spec["argv"], list) and all(isinstance(arg, str) and arg and not Path(arg).is_absolute()
            for arg in spec["argv"]), "oracle argv 必须使用 bundle 内的相对路径")
    require(isinstance(spec["outputs"], dict) and spec["outputs"], "oracle 输出映射为空")
    actuals = []
    for name, output in spec["outputs"].items():
        relative_name(name)
        fields(output, {"actual", "dtype"}, "原 oracle 输出")
        relative_name(output["actual"])
        require(output["actual"].startswith("outputs/") and isinstance(output["dtype"], str) and output["dtype"], "原 oracle 输出身份无效")
        actuals.append(output["actual"])
    require(len(set(actuals)) == len(actuals), "原 oracle 输出映射重复")
    fields(spec["result"], {"path", "passed_field"}, "原 oracle 结果")
    relative_name(spec["result"]["path"])
    require(isinstance(spec["result"]["passed_field"], str) and spec["result"]["passed_field"], "原 oracle 结果字段无效")
    names = [*paths, *spec["outputs"], spec["result"]["path"]]
    require(len(set(names)) == len(names) and not any(a != b and b.startswith(a + "/") for a in names for b in names),
            "oracle 文件、输出和结果路径冲突")
    environment = spec["environment"]
    fields(environment, {"python", "sha256", "packages"}, "oracle Python 环境")
    python = Path(environment["python"])
    if not python.is_absolute() or not python.is_file() or file_hash(python) != environment["sha256"]:
        raise OracleFailure("oracle_environment_unavailable", "Python 不存在或字节身份变化")
    require(isinstance(environment["packages"], dict) and all(isinstance(k, str) and k and isinstance(v, str) and v
            for k, v in environment["packages"].items()), "oracle 包版本清单无效")
    require(type(spec["timeout_seconds"]) in (int, float) and math.isfinite(spec["timeout_seconds"])
            and spec["timeout_seconds"] > 0, "oracle 回放预算无效")
    return paths


BOOTSTRAP = """
import importlib.metadata, json, runpy, sys
from pathlib import Path
spec = json.loads(Path('.aprof-environment.json').read_text())
try:
    for name, expected in spec['packages'].items():
        if importlib.metadata.version(name) != expected:
            raise RuntimeError('package version mismatch: ' + name)
except Exception as exc:
    print('APROF_ORACLE_ENVIRONMENT_ERROR:' + str(exc), file=sys.stderr)
    raise SystemExit(78)
entrypoint = sys.argv[1]
sys.path[:0] = [str(Path(entrypoint).resolve().parent), str(Path.cwd())]
sys.argv = sys.argv[1:]
runpy.run_path(entrypoint, run_name='__main__')
"""


def execute(root, receipt, limits, *, deadline=None, logs=None, verified=None, reuse=True):
    """Run the same original program for live validation and offline replay.

    This executes trusted task code, not a security sandbox. No device is needed.
    Copies keep oracle side effects away from retained inputs and native outputs.
    """
    checked_at = time.monotonic()
    spec = receipt["replay"]
    paths = validate(root, spec, receipt["oracle_source"], limits)
    by_path = {check["actual"]["path"]: check for check in receipt["checks"]}
    require(len(by_path) == len(receipt["checks"]) == len(spec["outputs"]), "原 oracle 输出覆盖不符")
    for name, output in spec["outputs"].items():
        require(output["actual"] in by_path, "原 oracle 缺少实际输出")
        check = by_path[output["actual"]]
        fields(check, {"actual", "dtype", "oracle_path"}, "原 oracle check")
        require(check["dtype"] == output["dtype"] and check["oracle_path"] == name, "原 oracle 输出类型/路径不符")
        paths[name] = reference(root, check["actual"])
    # Bind numerical context and every output byte, independently of storage/targets.
    from .validation_cache import cache_for
    from .execution_policy import append
    semantic = {k: v for k, v in spec.items() if k != "timeout_seconds"}
    workload_path = Path(root)/"workload.json"
    workload = json.loads(workload_path.read_text()) if workload_path.is_file() else {}
    if receipt.get("workload_ref") is not None:
        require(file_hash(workload_path) == receipt["workload_ref"], "oracle workload identity differs")
    numerical_workload = {**workload, "oracle_limits": {"mode": MODE, "contract_sha256": contract(semantic)}}
    key = content_hash({"contract": contract(semantic), "checks": receipt["checks"], "workload": numerical_workload,
        "identity": {k: receipt.get(k) for k in ("source_sha256", "binary_sha256", "input_ref", "case_id")}})
    cache = cache_for(root)
    audit = os.environ.get("APROF_ORACLE_AUDIT") == "1"
    hit = cache.get(key) if cache is not None and reuse and not audit else None
    if hit is not None:
        # Check the live package environment once per process even on a cache hit.
        environment_key = content_hash(spec["environment"])
        if environment_key not in _CHECKED_ENVIRONMENTS:
            check_environment(spec["environment"], spec["timeout_seconds"])
            _CHECKED_ENVIRONMENTS.add(environment_key)
        stage = {"kind": "validation_reuse", "cache_key": key, "validation_ref": hit,
                 "reason": "identical_implementation_input_oracle_environment_and_all_output_bytes",
                 "elapsed_seconds": time.monotonic()-checked_at, "oracle_executions": 0}
        append(cache.root / "events.jsonl", stage)
        return stage
    if reuse and not audit and verified is not None and key in verified:
        return {"kind": "validation_reuse", "cache_key": key, "reason": "same_process_actual_validation", "elapsed_seconds": time.monotonic()-checked_at, "oracle_executions": 0}
    timeout = spec["timeout_seconds"]
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    from .execution_policy import task_root, local_path
    owned = task_root(root)
    temporary_parent = (owned / "tmp") if owned is not None else local_path(root) / "tmp"
    temporary_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="aprof-oracle-", dir=temporary_parent) as temporary:
        work = Path(temporary)
        digests = {}
        for name, source in paths.items():
            dest = work / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            digests[name] = file_hash(dest)
            require(digests[name] == file_hash(source), "oracle 复制期间输入变化")
        result_path = work / spec["result"]["path"]
        result_path.parent.mkdir(parents=True, exist_ok=True)
        (work / ".aprof-environment.json").write_text(json.dumps(spec["environment"]))
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("PYTHON", "APROF_TASK_"))}
        env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
        argv = [spec["environment"]["python"], "-B", "-c", BOOTSTRAP, spec["entrypoint"], *spec["argv"]]
        from .execution_policy import wait
        with subprocess.Popen(argv, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True) as process:
            stdout, stderr = wait(process, target_seconds=timeout,
                checkpoint=Path(root)/"checkpoints.jsonl", communicate=True)
        stage = {"argv": argv, "cwd": str(work), "pid": process.pid, "returncode": process.returncode,
                 "started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
                 "elapsed_seconds": time.monotonic() - started}
        if logs is not None:
            logs = Path(logs)
            logs.mkdir(exist_ok=True)
            for channel, data in (("stdout", stdout), ("stderr", stderr)):
                path = logs / f"oracle.{channel}"
                path.write_bytes(data)
                stage[channel] = {"path": str(path.relative_to(root)), "sha256": file_hash(path)}
            (logs / "oracle.json").write_text(json.dumps(stage, indent=2))
            if result_path.is_file():
                shutil.copyfile(result_path, logs / "oracle.result.json")
        if b"APROF_ORACLE_ENVIRONMENT_ERROR:" in stderr:
            raise OracleFailure("oracle_environment_unavailable", stderr.decode(errors="replace")[-2000:])
        for name, digest in digests.items():
            require((work / name).is_file() and file_hash(work / name) == digest
                    and file_hash(paths[name]) == digest, "原 oracle 改写了冻结依赖或实际输出")
        try:
            result = json.loads(result_path.read_text())
            passed = result[spec["result"]["passed_field"]]
            require(type(passed) is bool, "原 oracle 必须输出布尔判据")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise OracleFailure("oracle_execution_failed", f"原 oracle 未生成有效结果: {stderr.decode(errors='replace')[-2000:]}") from exc
        if passed is False:
            raise OracleFailure("numerical_mismatch", "原 oracle 对冻结实际输出判定失败")
        if process.returncode != 0:
            raise OracleFailure("oracle_execution_failed", f"原 oracle 退出码 {process.returncode}")
        if verified is not None:
            verified.add(key)
        stage["kind"] = "executed_oracle"
        stage["oracle_executions"] = 1
        if cache is not None:
            cache.put(key, {"kind": "executed_oracle", "returncode": process.returncode,
                "pid": process.pid, "started_at": started_at, "finished_at": stage["finished_at"],
                "result_sha256": file_hash(result_path), "elapsed_seconds": stage["elapsed_seconds"],
                "source_receipt_root": str(root)})
            append(cache.root / "events.jsonl", {"kind": "validation_miss", "key": key,
                "oracle_executions": 1, "audit": audit, "elapsed_seconds": stage["elapsed_seconds"]})
        return stage
