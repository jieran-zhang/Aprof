#!/usr/bin/env python3
"""Re-run msprof sim for one fast_gelu inject case on remote (with ulimit fix).

Copy to run_remote_fast_gelu_inject_sim.py (gitignored) and set:
  APROF_REMOTE_HOST, APROF_REMOTE_PORT (optional), APROF_REMOTE_USER,
  APROF_REMOTE_PASS, APROF_REMOTE_ROOT (optional), INJECT_CASE (optional)
"""
import json
import os
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
LOCAL_COMMON = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "benchmarks", "aprof_injected_ops", "common")
)
LOCAL_OUT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "benchmarks", "aprof_injected_ops", "fast_gelu", "remote_inject_out")
)
CASE = os.environ.get("INJECT_CASE", "inject_blockdim")


def read_lf(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read().replace(b"\r\n", b"\n")


def upload_file(sftp, local_path: str, remote_path: str) -> None:
    with sftp.open(remote_path, "w") as rf:
        rf.write(read_lf(local_path))


def run(ssh, cmd: str, timeout: int = 2400) -> tuple[int, str]:
    print(f"\n>>> {cmd[:260]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out[-8000:] if len(out) > 8000 else out)
    return code, out


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)
    sftp = ssh.open_sftp()
    upload_file(sftp, os.path.join(LOCAL_COMMON, "inject_run.sh"), f"{REMOTE_ROOT}/common/inject_run.sh")

    case_remote = f"{REMOTE_ROOT}/{CASE}"
    sim_cmd = (
        f"{ENV} && cd {case_remote} && "
        f"export APROF_INJECT_COMMON={REMOTE_ROOT}/common && "
        f"export APROF_INJECT_RUN={REMOTE_ROOT}/common/inject_run.sh && "
        "export ASC_ARCH=dav-3510 && export MSPROF_TIMEOUT=10 && "
        "ulimit -n 65536 2>/dev/null || ulimit -n 4096; "
        "bash run.sh all 2>&1 | tail -60"
    )
    code, _ = run(ssh, sim_cmd, timeout=2400)
    _, check_out = run(
        ssh,
        f"find {case_remote}/msprof_sim_output -name trace.json -o -name '*_instr_exe_*.csv' 2>/dev/null | head -15",
        timeout=120,
    )

    os.makedirs(os.path.join(LOCAL_OUT, CASE), exist_ok=True)
    for line in check_out.splitlines():
        rp = line.strip()
        if not rp.startswith(case_remote):
            continue
        rel = os.path.relpath(rp, case_remote).replace("\\", "/")
        local_path = os.path.join(LOCAL_OUT, CASE, rel.replace("/", os.sep))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        try:
            sftp.get(rp, local_path)
            print(f"downloaded {local_path}")
        except Exception as exc:
            print(f"skip {rp}: {exc}")

    result = {"case": CASE, "sim_exit": code, "artifacts": [l for l in check_out.splitlines() if l.strip()]}
    with open(os.path.join(LOCAL_OUT, f"{CASE}_sim_rerun.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    ssh.close()
    return 0 if any("trace.json" in x for x in result["artifacts"]) else 1


if __name__ == "__main__":
    sys.exit(main())
