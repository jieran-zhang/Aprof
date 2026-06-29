#!/usr/bin/env python3
"""Upload fast_gelu inject cases to remote host, build, msprof sim, download artifacts.

Copy to run_remote_fast_gelu_inject.py (gitignored) and set:
  APROF_REMOTE_HOST, APROF_REMOTE_PORT (optional, default 22),
  APROF_REMOTE_USER, APROF_REMOTE_PASS, APROF_REMOTE_ROOT (optional)
"""
from __future__ import annotations

import json
import os
import posixpath
import sys

import paramiko

HOST = os.environ["APROF_REMOTE_HOST"]
PORT = int(os.environ.get("APROF_REMOTE_PORT", "22"))
USER = os.environ["APROF_REMOTE_USER"]
PASS = os.environ["APROF_REMOTE_PASS"]
ENV = os.environ.get(
    "APROF_REMOTE_ENV",
    "source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh",
)
REMOTE_ROOT = os.environ.get("APROF_REMOTE_ROOT", f"/home/{USER}/aprof_fast_gelu_inject")
ASC_ARCH = os.environ.get("ASC_ARCH", "dav-3510")
CASES = ["baseline", "inject_blockdim", "inject_tail", "inject_tilelen_small"]
TEXT_EXT = {".sh", ".asc", ".h", ".py", ".md", ".json"}

LOCAL_BASE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "benchmarks", "aprof_injected_ops", "fast_gelu")
)
LOCAL_COMMON = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "benchmarks", "aprof_injected_ops", "common")
)
LOCAL_OUT = os.path.join(LOCAL_BASE, "remote_inject_out")


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
    skip = {"build_sim", "data", "msprof_sim_output", "remote_inject_out", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(local_root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        rel = os.path.relpath(dirpath, local_root).replace("\\", "/")
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXT:
                continue
            lp = os.path.join(dirpath, name)
            rp = posixpath.join(remote_root, rel, name) if rel != "." else posixpath.join(remote_root, name)
            upload_file(sftp, lp, rp)


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 3600) -> tuple[int, str]:
    print(f"\n>>> {cmd[:260]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out[-12000:] if len(out) > 12000 else out)
    return code, out


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting {HOST}:{PORT}")
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)
    sftp = ssh.open_sftp()

    run(ssh, f"mkdir -p {REMOTE_ROOT}")
    upload_file(sftp, os.path.join(LOCAL_COMMON, "inject_run.sh"), f"{REMOTE_ROOT}/common/inject_run.sh")
    upload_file(sftp, os.path.join(LOCAL_COMMON, "inject_gen_data.py"), f"{REMOTE_ROOT}/common/inject_gen_data.py")

    run(
        ssh,
        f"{ENV} && ls -d $ASCEND_HOME_PATH/tools/simulator/*/lib 2>/dev/null | head -5",
        timeout=60,
    )

    results: dict[str, dict] = {}
    for case in CASES:
        print(f"\n========== {case} ==========")
        case_local = os.path.join(LOCAL_BASE, case)
        case_remote = f"{REMOTE_ROOT}/{case}"
        run(ssh, f"mkdir -p {case_remote}")
        upload_tree(sftp, case_local, case_remote)

        prep = (
            f"{ENV} && cd {case_remote} && "
            f"export APROF_INJECT_COMMON={REMOTE_ROOT}/common && "
            f"export APROF_INJECT_RUN={REMOTE_ROOT}/common/inject_run.sh && "
            "true"
        )
        run(ssh, prep, timeout=60)

        build_sim_cmd = (
            f"{ENV} && cd {case_remote} && "
            f"export APROF_INJECT_COMMON={REMOTE_ROOT}/common && "
            f"export APROF_INJECT_RUN={REMOTE_ROOT}/common/inject_run.sh && "
            f"export ASC_ARCH={ASC_ARCH} && "
            "bash run.sh build 2>&1"
        )
        b_code, b_out = run(ssh, build_sim_cmd, timeout=600)

        sim_cmd = (
            f"{ENV} && cd {case_remote} && "
            f"export APROF_INJECT_COMMON={REMOTE_ROOT}/common && "
            f"export APROF_INJECT_RUN={REMOTE_ROOT}/common/inject_run.sh && "
            f"export ASC_ARCH={ASC_ARCH} && "
            "export MSPROF_TIMEOUT=8 && "
            "bash run.sh sim 2>&1"
        )
        s_code, s_out = run(ssh, sim_cmd, timeout=1800)

        check_cmd = (
            f"cd {case_remote} && "
            "python3 -c \"import json; print(json.load(open('metadata.json'))['injected_label'])\" && "
            "find msprof_sim_output -name trace.json 2>/dev/null | head -3 && "
            "find msprof_sim_output -name '*_instr_exe_*.csv' 2>/dev/null | head -3"
        )
        _, check_out = run(ssh, check_cmd, timeout=120)

        has_trace = "trace.json" in check_out
        results[case] = {
            "build_exit": b_code,
            "sim_exit": s_code,
            "has_trace": has_trace,
            "label": next((l for l in check_out.splitlines() if l and not l.startswith("/")), ""),
        }

    os.makedirs(LOCAL_OUT, exist_ok=True)
    with open(os.path.join(LOCAL_OUT, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    for case in CASES:
        case_remote = f"{REMOTE_ROOT}/{case}"
        for pattern_cmd, suffix in [
            (f"find {case_remote}/msprof_sim_output -name trace.json | head -1", "trace.json"),
            (f"find {case_remote}/msprof_sim_output -name '*_instr_exe_*.csv' | head -1", "instr_exe.csv"),
            (f"cat {case_remote}/metadata.json", "metadata.json"),
        ]:
            _, out = run(ssh, pattern_cmd, timeout=60)
            line = out.strip().splitlines()[-1] if out.strip() else ""
            if not line or line.startswith("find:"):
                continue
            if suffix == "metadata.json":
                local_path = os.path.join(LOCAL_OUT, f"{case}_metadata.json")
                with open(local_path, "w", encoding="utf-8") as f:
                    f.write(line + "\n")
                print(f"saved {local_path}")
            elif line.startswith(case_remote):
                rel = os.path.relpath(line, case_remote).replace("\\", "/")
                local_path = os.path.join(LOCAL_OUT, case, rel.replace("/", os.sep))
                try:
                    os.makedirs(os.path.dirname(local_path), exist_ok=True)
                    sftp.get(line, local_path)
                    print(f"downloaded {local_path}")
                except Exception as exc:
                    print(f"skip download {line}: {exc}")

    ssh.close()
    print(json.dumps(results, indent=2, ensure_ascii=False))
    failed = [c for c, r in results.items() if r["build_exit"] != 0]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
