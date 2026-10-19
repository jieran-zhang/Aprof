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
                                capture_output=True, timeout=timeout)
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


def execute(root, receipt, limits, *, deadline=None, logs=None, verified=None, reuse=False):
    """Run the same original program for live validation and offline replay.

    This executes trusted task code, not a security sandbox. No device is needed.
    Copies keep oracle side effects away from retained inputs and native outputs.
    """
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
    # A per-invocation cache is populated only after real execution. All retained
    # bytes above are still rehashed; no receipt label can populate this cache.
    key = content_hash({"contract": contract(spec), "checks": receipt["checks"]})
    if deadline is not None and time.monotonic() >= deadline:
        raise OracleFailure("oracle_timeout", "原始采集预算已耗尽")
    if reuse and verified is not None and key in verified:
        return None
    timeout = spec["timeout_seconds"]
    if deadline is not None:
        timeout = min(timeout, deadline - time.monotonic())
    if timeout <= 0:
        raise OracleFailure("oracle_timeout", "原始采集预算已耗尽")
    started = time.monotonic()
    started_at = datetime.now(timezone.utc).isoformat()
    with tempfile.TemporaryDirectory(prefix="aprof-oracle-") as temporary:
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
        timeout -= time.monotonic() - started
        if timeout <= 0:
            raise OracleFailure("oracle_timeout", "复制依赖超过回放预算")
        with subprocess.Popen(argv, cwd=work, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True) as process:
            timed_out = False
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
                timed_out = True
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
        if timed_out or deadline is not None and time.monotonic() > deadline:
            raise OracleFailure("oracle_timeout", "原 oracle 超过预算")
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
        return stage
