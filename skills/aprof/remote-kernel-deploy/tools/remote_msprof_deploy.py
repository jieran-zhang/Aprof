#!/usr/bin/env python3
"""Upload an Ascend C op dir to remote, build, msprof capture, download reports.

Profile modes:
  sim       - msprof op simulator (run.sh build/sim)
  hw-msprof - on-device msprof via msprof_profile_run.sh (cmake binary)
  hw-op     - on-device msprof op (cmake binary)

Config: scripts/server_config.json (APROF_REMOTE_* env vars override).
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import posixpath
import sys
from pathlib import Path

import paramiko

_REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(_REPO_ROOT / "scripts"))
from remote_server_config import connect_ssh, load_server_config, require_server_config  # noqa: E402

TEXT_EXT = {".sh", ".asc", ".h", ".py", ".md", ".json", ".cpp", ".txt", ".cmake"}
SKIP_DIRS = {
    "build",
    "build_sim",
    "data",
    "remote_out",
    "msprof_hw_output",
    "msprof_sim_output",
    "__pycache__",
}
PROFILING_SCRIPT_NAMES = ("msprof_profile_run.sh", "msprof_perf_summary.py", "perf_summary.py")


def profiling_scripts_dir() -> Path:
    for candidate in (
        _REPO_ROOT / "third_party/cannbot-skills/ops/ops-profiling/scripts",
        _REPO_ROOT / ".cursor/skills/ops-profiling/scripts",
    ):
        if (candidate / "msprof_profile_run.sh").is_file():
            return candidate
    raise SystemExit(
        "找不到 ops-profiling 脚本。请执行: git submodule update --init "
        "或 bash scripts/link_cannbot_skills.sh"
    )


def read_lf(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


def upload_file(sftp: paramiko.SFTPClient, local_path: str, remote_path: str) -> None:
    parent = posixpath.dirname(remote_path)
    parts: list[str] = []
    while parent and parent not in (".", "/"):
        parts.append(parent)
        parent = posixpath.dirname(parent)
    for d in reversed(parts):
        try:
            sftp.stat(d)
        except OSError:
            sftp.mkdir(d)
    with sftp.open(remote_path, "w") as rf:
        rf.write(read_lf(local_path))


def upload_tree(sftp: paramiko.SFTPClient, local_root: str, remote_root: str) -> None:
    for dirpath, dirnames, filenames in os.walk(local_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel = os.path.relpath(dirpath, local_root).replace("\\", "/")
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXT:
                continue
            lp = os.path.join(dirpath, name)
            rp = posixpath.join(remote_root, rel, name) if rel != "." else posixpath.join(remote_root, name)
            upload_file(sftp, lp, rp)
            print(f"uploaded {rel}/{name}" if rel != "." else f"uploaded {name}")


def upload_profiling_scripts(sftp: paramiko.SFTPClient, op_remote: str) -> None:
    scripts_dir = profiling_scripts_dir()
    remote_scripts = posixpath.join(op_remote, "ops_profiling", "scripts")
    for name in PROFILING_SCRIPT_NAMES:
        local_path = scripts_dir / name
        if local_path.is_file():
            upload_file(sftp, str(local_path), posixpath.join(remote_scripts, name))


def upload_common_tree(sftp: paramiko.SFTPClient, local_common: str, op_remote: str) -> None:
    common_root = os.path.abspath(local_common)
    if not os.path.isdir(common_root):
        raise SystemExit(f"inject common dir 不存在: {common_root}")
    remote_common = posixpath.join(posixpath.dirname(op_remote), "common")
    upload_tree(sftp, common_root, remote_common)


def run_remote(ssh: paramiko.SSHClient, cmd: str, timeout: int = 3600) -> tuple[int, str]:
    print(f"\n>>> {cmd[:280]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out[-12000:] if len(out) > 12000 else out)
    return code, out


def remote_env_prefix(cfg: dict) -> str:
    extra = str(cfg.get("_extra_env", ""))
    return f"{cfg['env']}{extra}"


def remote_op_dir(cfg: dict, remote_name: str) -> str:
    root = str(cfg["remote_root"]).rstrip("/")
    if not root:
        user = str(cfg["user"])
        root = f"/home/{user}/aprof_remote_ops"
    return f"{root}/{remote_name}"


def render_remote_env_exports(profiling_plan: dict, op_remote: str) -> str:
    args = profiling_plan.get("remote_deploy_args", {}) if profiling_plan else {}
    exports = args.get("remote_env_exports", [])
    if not exports:
        return ""
    remote_root = posixpath.dirname(op_remote)
    rendered: list[str] = []
    for item in exports:
        text = str(item).format(remote_root=remote_root, op_remote=op_remote)
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        if not key.replace("_", "").isalnum():
            raise SystemExit(f"非法远程环境变量名: {key}")
        rendered.append(f"export {key}='{value}'")
    return " && " + " && ".join(rendered) if rendered else ""


def sim_build_cmd(cfg: dict, op_remote: str) -> str:
    asc_arch = str(cfg["asc_arch"])
    return (
        f"{remote_env_prefix(cfg)} && cd {op_remote} && "
        f"export ASC_ARCH={asc_arch} && bash run.sh build 2>&1"
    )


def cmake_build_cmd(cfg: dict, op_remote: str) -> str:
    asc_arch = str(cfg["asc_arch"])
    return (
        f"{remote_env_prefix(cfg)} && cd {op_remote} && "
        f"cmake -S . -B build -DCMAKE_BUILD_TYPE=Release "
        f"-DCMAKE_ASC_ARCHITECTURES={asc_arch} && "
        "cmake --build build -j$(nproc) 2>&1"
    )


def sim_profile_cmd(cfg: dict, op_remote: str, msprof_timeout: int) -> str:
    asc_arch = str(cfg["asc_arch"])
    return (
        f"{remote_env_prefix(cfg)} && cd {op_remote} && "
        f"export ASC_ARCH={asc_arch} && export MSPROF_TIMEOUT={msprof_timeout} && "
        "chmod 700 msprof_sim_output build_sim 2>/dev/null || true && "
        "chmod u=rw,go= build_sim/* 2>/dev/null || true && "
        "ulimit -n 65536 2>/dev/null || ulimit -n 4096 2>/dev/null || true && "
        "bash run.sh sim 2>&1"
    )


def hw_msprof_profile_cmd(
    cfg: dict,
    op_remote: str,
    run_cmd: str,
    warm_up: int,
    repeat: int,
    gen_data_cmd: str,
) -> str:
    prefix = remote_env_prefix(cfg)
    gen = f"{gen_data_cmd} && " if gen_data_cmd else ""
    return (
        f"{prefix} && cd {op_remote} && {gen}"
        "mkdir -p build/output msprof_hw_output && cd build && "
        f"i=1; while [ \"$i\" -le {repeat} ]; do "
        "run_dir=\"../msprof_hw_output/run_$i\"; mkdir -p \"$run_dir\"; "
        f"bash ../ops_profiling/scripts/msprof_profile_run.sh "
        f"--warm-up={warm_up} --output=\"$run_dir\" -- {run_cmd} || exit $?; "
        "i=$((i + 1)); done 2>&1"
    )


def hw_op_profile_cmd(
    cfg: dict,
    op_remote: str,
    run_cmd: str,
    warm_up: int,
    repeat: int,
    gen_data_cmd: str,
) -> str:
    prefix = remote_env_prefix(cfg)
    gen = f"{gen_data_cmd} && " if gen_data_cmd else ""
    return (
        f"{prefix} && cd {op_remote} && {gen}"
        "mkdir -p build/output msprof_hw_output && cd build && "
        f"msprof op --warm-up={warm_up} --launch-count={repeat} --output=../msprof_hw_output {run_cmd} 2>&1"
    )


def hw_summarize_cmd(cfg: dict, op_remote: str, profile_mode: str) -> str:
    prefix = remote_env_prefix(cfg)
    if profile_mode == "hw-msprof":
        return (
            f"{prefix} && cd {op_remote} && "
            "PROFILE_DIR=$(find msprof_hw_output -type d -name 'PROF_GROUP_*' 2>/dev/null | head -1); "
            'if [ -n "$PROFILE_DIR" ]; then '
            'python3 ops_profiling/scripts/msprof_perf_summary.py "$PROFILE_DIR" . '
            "> remote_hw_summary.txt 2>&1; fi"
        )
    return (
        f"{prefix} && cd {op_remote} && "
        "OPPROF_DIR=$(find msprof_hw_output -type d -name 'OPPROF_*' 2>/dev/null | head -1); "
        'if [ -n "$OPPROF_DIR" ]; then '
        'python3 ops_profiling/scripts/perf_summary.py "$OPPROF_DIR" . '
        "> remote_hw_summary.txt 2>&1; fi"
    )


def check_artifacts(ssh: paramiko.SSHClient, op_remote: str, profile_mode: str) -> tuple[bool, str]:
    if profile_mode == "sim":
        cmd = (
            f"cd {op_remote} && "
            "find msprof_sim_output -name trace.json 2>/dev/null | head -3 && "
            "find msprof_sim_output -name '*_instr_exe_*.csv' 2>/dev/null | head -3"
        )
        _, out = run_remote(ssh, cmd, timeout=120)
        return "trace.json" in out, out

    cmd = (
        f"cd {op_remote} && "
        "find msprof_hw_output -type f "
        "\\( -name 'trace.json' -o -name 'op_summary*.csv' -o -name 'PipeUtilization.csv' "
        "-o -name 'aicore.db' -o -name 'remote_hw_summary.txt' \\) 2>/dev/null | head -15"
    )
    _, out = run_remote(ssh, cmd, timeout=120)
    markers = ("trace.json", "op_summary", "PipeUtilization.csv", "aicore.db", "remote_hw_summary.txt")
    return any(m in out for m in markers), out


def download_artifacts(
    ssh: paramiko.SSHClient,
    sftp: paramiko.SFTPClient,
    op_remote: str,
    local_out: str,
    profile_mode: str,
) -> list[str]:
    saved: list[str] = []
    if profile_mode == "sim":
        patterns = [
            f"find {op_remote}/msprof_sim_output -name trace.json | head -1",
            f"find {op_remote}/msprof_sim_output -name '*_instr_exe_*.csv' | head -1",
        ]
        for pattern_cmd in patterns:
            saved.extend(_download_find_first(ssh, sftp, pattern_cmd, op_remote, local_out))
        return saved

    _, list_out = run_remote(
        ssh,
        f"find {op_remote}/msprof_hw_output -type f "
        "\\( -name '*.csv' -o -name 'trace.json' -o -name 'aicore.db' -o -name 'msprof.log' \\) "
        "2>/dev/null | head -30",
        timeout=120,
    )
    for line in list_out.splitlines():
        rp = line.strip()
        if not rp.startswith(op_remote):
            continue
        saved.extend(_sftp_get_one(sftp, rp, op_remote, local_out))

    for extra in (f"{op_remote}/remote_hw_summary.txt",):
        saved.extend(_sftp_get_one(sftp, extra, op_remote, local_out))
    return saved


def _download_find_first(
    ssh: paramiko.SSHClient,
    sftp: paramiko.SFTPClient,
    pattern_cmd: str,
    op_remote: str,
    local_out: str,
) -> list[str]:
    _, out = run_remote(ssh, pattern_cmd, timeout=60)
    line = out.strip().splitlines()[-1] if out.strip() else ""
    if not line or line.startswith("find:") or not line.startswith(op_remote):
        return []
    return _sftp_get_one(sftp, line, op_remote, local_out)


def _sftp_get_one(
    sftp: paramiko.SFTPClient,
    remote_path: str,
    op_remote: str,
    local_out: str,
) -> list[str]:
    try:
        sftp.stat(remote_path)
    except OSError:
        return []
    rel = os.path.relpath(remote_path, op_remote).replace("\\", "/")
    local_path = os.path.join(local_out, rel.replace("/", os.sep))
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        sftp.get(remote_path, local_path)
        print(f"downloaded {local_path}")
        return [local_path]
    except Exception as exc:
        print(f"skip download {remote_path}: {exc}")
        return []


def parse_steps(raw: str, profile_mode: str) -> list[str]:
    allowed = {"upload", "build", "profile", "download", "summarize"}
    steps = [s.strip() for s in raw.split(",") if s.strip()]
    if not steps:
        return ["upload", "build", "profile", "download"] + (
            ["summarize"] if profile_mode.startswith("hw") else []
        )
    normalized: list[str] = []
    for step in steps:
        if step == "sim":
            normalized.append("profile")
        else:
            normalized.append(step)
    bad = [s for s in normalized if s not in allowed]
    if bad:
        raise SystemExit(f"未知 step: {bad}，可选: {sorted(allowed)} 或 sim(=profile)")
    return normalized


def load_profiling_plan(path: str) -> dict:
    if not path:
        return {}
    plan_path = os.path.abspath(path)
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    if not isinstance(plan, dict):
        raise SystemExit(f"profiling plan 必须是 JSON object: {plan_path}")
    return plan


def validate_local_dir(local_dir: str, profile_mode: str) -> None:
    if profile_mode == "sim":
        if not os.path.isfile(os.path.join(local_dir, "run.sh")):
            raise SystemExit(f"sim 模式需要 run.sh: {local_dir}")
    else:
        if not os.path.isfile(os.path.join(local_dir, "CMakeLists.txt")):
            raise SystemExit(f"上板模式需要 CMakeLists.txt: {local_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Remote kernel build, msprof capture, artifact download")
    parser.add_argument("--local-dir", required=True, help="Local op directory")
    parser.add_argument("--remote-name", default="", help="Remote subdirectory name")
    parser.add_argument("--local-out", default="", help="Local output dir (default: <local-dir>/remote_out)")
    parser.add_argument(
        "--profile-mode",
        choices=("sim", "hw-msprof", "hw-op"),
        default="sim",
        help="sim=msprof op simulator; hw-msprof=msprof_profile_run.sh; hw-op=msprof op",
    )
    parser.add_argument(
        "--steps",
        default="",
        help="upload,build,profile,download[,summarize]; sim is alias of profile",
    )
    parser.add_argument("--run-cmd", default="", help="Executable + args relative to build/ (hw modes)")
    parser.add_argument(
        "--gen-data-cmd",
        default="",
        help="Optional command before profile on remote (e.g. python3 scripts/gen_data.py 8 2048 fp32)",
    )
    parser.add_argument("--warm-up", type=int, default=10, help="Warm-up iterations for hw modes")
    parser.add_argument("--repeat", type=int, default=5, help="Repeated launches/runs for hw metric stability")
    parser.add_argument("--msprof-timeout", type=int, default=8, help="MSPROF_TIMEOUT minutes for sim mode")
    parser.add_argument("--summarize", action="store_true", help="Run msprof_perf_summary/perf_summary on remote")
    parser.add_argument(
        "--profiling-plan",
        default="",
        help="Optional profiling_plan.json used to validate downloaded artifacts",
    )
    parser.add_argument(
        "--inject-common-dir",
        default="",
        help="Optional benchmarks/aprof_injected_ops/common dir uploaded beside remote case",
    )
    args = parser.parse_args()

    local_dir = os.path.abspath(args.local_dir)
    if not os.path.isdir(local_dir):
        raise SystemExit(f"local-dir 不存在: {local_dir}")
    profiling_plan = load_profiling_plan(args.profiling_plan)
    plan_mode = str(profiling_plan.get("profile_mode", "")).strip()
    if plan_mode and plan_mode != args.profile_mode:
        raise SystemExit(f"profiling_plan profile_mode={plan_mode} 与 --profile-mode={args.profile_mode} 不一致")
    validate_local_dir(local_dir, args.profile_mode)

    if args.profile_mode.startswith("hw") and not args.run_cmd:
        raise SystemExit("上板模式需要 --run-cmd，例如: './fast_gelu 8 2048 fp32 1'")
    if args.profile_mode.startswith("hw") and args.repeat < 1:
        raise SystemExit("上板模式 --repeat 必须 >= 1")
    if args.profile_mode.startswith("hw") and args.warm_up < 0:
        raise SystemExit("上板模式 --warm-up 必须 >= 0")

    remote_name = args.remote_name or os.path.basename(local_dir.rstrip(os.sep))
    local_out = os.path.abspath(args.local_out or os.path.join(local_dir, "remote_out"))
    steps = parse_steps(args.steps, args.profile_mode)
    if args.summarize and "summarize" not in steps:
        steps.append("summarize")

    cfg = load_server_config()
    require_server_config(cfg)
    op_remote = remote_op_dir(cfg, remote_name)
    cfg["_extra_env"] = render_remote_env_exports(profiling_plan, op_remote)

    result: dict = {
        "profile_mode": args.profile_mode,
        "local_dir": local_dir,
        "remote_dir": op_remote,
        "local_out": local_out,
        "steps": steps,
        "build_exit": None,
        "profile_exit": None,
        "summarize_exit": None,
        "has_artifacts": False,
        "downloaded": [],
        "profiling_plan": os.path.abspath(args.profiling_plan) if args.profiling_plan else "",
        "inject_common_dir": os.path.abspath(args.inject_common_dir) if args.inject_common_dir else "",
        "measurement_policy": {
            "warm_up": args.warm_up,
            "repeat": args.repeat,
            "statistic": "median",
            "stability_cv_threshold": 0.05,
        },
    }

    ssh = connect_ssh(cfg)
    sftp = ssh.open_sftp()

    if "upload" in steps:
        run_remote(ssh, f"mkdir -p {op_remote}", timeout=60)
        if args.inject_common_dir:
            upload_common_tree(sftp, args.inject_common_dir, op_remote)
        upload_tree(sftp, local_dir, op_remote)
        if args.profile_mode.startswith("hw"):
            upload_profiling_scripts(sftp, op_remote)

    if "build" in steps:
        build = sim_build_cmd if args.profile_mode == "sim" else cmake_build_cmd
        code, _ = run_remote(ssh, build(cfg, op_remote), timeout=1200)
        result["build_exit"] = code
        if code != 0:
            _write_result(local_out, result)
            _write_artifact_manifest(local_out, result, profiling_plan)
            ssh.close()
            return code

    if "profile" in steps:
        if args.profile_mode == "sim":
            cmd = sim_profile_cmd(cfg, op_remote, args.msprof_timeout)
            timeout = 1800
        elif args.profile_mode == "hw-msprof":
            cmd = hw_msprof_profile_cmd(cfg, op_remote, args.run_cmd, args.warm_up, args.repeat, args.gen_data_cmd)
            timeout = 3600
        else:
            cmd = hw_op_profile_cmd(cfg, op_remote, args.run_cmd, args.warm_up, args.repeat, args.gen_data_cmd)
            timeout = 3600
        code, _ = run_remote(ssh, cmd, timeout=timeout)
        result["profile_exit"] = code
        has_artifacts, _ = check_artifacts(ssh, op_remote, args.profile_mode)
        result["has_artifacts"] = has_artifacts

    if "summarize" in steps and args.profile_mode.startswith("hw"):
        code, _ = run_remote(ssh, hw_summarize_cmd(cfg, op_remote, args.profile_mode), timeout=600)
        result["summarize_exit"] = code

    if "download" in steps:
        os.makedirs(local_out, exist_ok=True)
        result["downloaded"] = download_artifacts(ssh, sftp, op_remote, local_out, args.profile_mode)
        if not result["has_artifacts"]:
            has_artifacts, _ = check_artifacts(ssh, op_remote, args.profile_mode)
            result["has_artifacts"] = has_artifacts

    _write_result(local_out, result)
    _write_artifact_manifest(local_out, result, profiling_plan)
    ssh.close()

    print(json.dumps(result, indent=2, ensure_ascii=False))
    if result.get("build_exit") not in (None, 0):
        return int(result["build_exit"])
    if "profile" in steps and not result["has_artifacts"]:
        return 1
    return 0


def _write_result(local_out: str, result: dict) -> None:
    os.makedirs(local_out, exist_ok=True)
    path = os.path.join(local_out, "deploy_results.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"saved {path}")


def _write_artifact_manifest(local_out: str, result: dict, profiling_plan: dict) -> None:
    os.makedirs(local_out, exist_ok=True)
    downloaded = [os.path.abspath(str(p)) for p in result.get("downloaded", [])]
    artifacts = [_artifact_entry(local_out, path) for path in downloaded]

    required = profiling_plan.get("required_artifacts", []) if profiling_plan else []
    missing: list[str] = []
    for item in required:
        pattern = str(item.get("path_pattern", "")) if isinstance(item, dict) else str(item)
        if pattern and not _matches_any(local_out, downloaded, pattern):
            missing.append(pattern)

    ready = bool(result.get("has_artifacts")) and not missing
    manifest = {
        "profile_mode": result.get("profile_mode"),
        "local_out": result.get("local_out", local_out),
        "deploy_results": os.path.join(local_out, "deploy_results.json"),
        "profiling_plan": result.get("profiling_plan", ""),
        "artifacts": artifacts,
        "missing_required_artifacts": missing,
        "ready_for_diagnosis": ready,
        "notes": [] if ready else ["required artifacts missing or deploy_results.has_artifacts is false"],
    }

    path = os.path.join(local_out, "artifact_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"saved {path}")


def _artifact_entry(local_out: str, path: str) -> dict:
    rel = os.path.relpath(path, local_out).replace("\\", "/")
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if ext == ".csv":
        kind = "csv"
    elif name == "trace.json":
        kind = "trace"
    elif name.endswith(".txt"):
        kind = "summary"
    else:
        kind = "artifact"
    return {
        "kind": kind,
        "name": name,
        "path": path,
        "relative_path": rel,
        "satisfies": [],
    }


def _matches_any(local_out: str, paths: list[str], pattern: str) -> bool:
    normalized_pattern = pattern.replace("\\", "/").lstrip("./")
    for path in paths:
        rel = os.path.relpath(path, local_out).replace("\\", "/")
        name = os.path.basename(path)
        if fnmatch.fnmatch(rel, normalized_pattern) or fnmatch.fnmatch(name, normalized_pattern):
            return True
        if normalized_pattern in rel:
            return True
    return False


if __name__ == "__main__":
    sys.exit(main())
