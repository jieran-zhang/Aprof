#!/usr/bin/env python3
"""Upload fast_gelu benchmark to PKU remote NPU host, build, verify, and profile."""
from __future__ import annotations

import os
import posixpath
import sys

import paramiko

HOST, PORT, USER, PASS = "xeon6.pku-dasys.cn", 2222, "u2300013210", "2300013210@pdc2026"
ENV = "source /usr/local/Ascend/ascend-toolkit/latest/set_env.sh"
REMOTE_ROOT = "/home/u2300013210/aprof_fast_gelu"
ASC_ARCH = os.environ.get("ASC_ARCH", "dav-2201")
TEXT_EXT = {".sh", ".asc", ".h", ".cpp", ".py", ".md", ".json", ".txt", ".cmake"}

LOCAL_OP = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCAL_REPO = os.path.abspath(os.path.join(LOCAL_OP, "..", "..", ".."))
LOCAL_PROFILING = os.path.join(
    LOCAL_REPO, "third_party", "cannbot-skills", "ops", "ops-profiling"
)
LOCAL_OUT = os.path.join(LOCAL_OP, "remote_out")


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
    skip_dirs = {"build", "data", "remote_out", "msprof_hw_output", "msprof_sim_output", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(local_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        rel = os.path.relpath(dirpath, local_root).replace("\\", "/")
        remote_dir = remote_root if rel == "." else posixpath.join(remote_root, rel)
        for name in filenames:
            lp = os.path.join(dirpath, name)
            ext = os.path.splitext(name)[1].lower()
            if ext not in TEXT_EXT:
                continue
            rp = posixpath.join(remote_dir, name)
            upload_file(sftp, lp, rp)
            print(f"uploaded {rel}/{name}" if rel != "." else f"uploaded {name}")


def run(ssh: paramiko.SSHClient, cmd: str, timeout: int = 1800) -> tuple[int, str]:
    print(f"\n>>> {cmd[:240]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    tail = out[-10000:] if len(out) > 10000 else out
    print(tail)
    return code, out


def download_if_exists(sftp: paramiko.SFTPClient, remote_path: str, local_path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        sftp.get(remote_path, local_path)
        print(f"downloaded {local_path}")
        return True
    except Exception as exc:
        print(f"skip {local_path}: {exc}")
        return False


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting {HOST}:{PORT} as {USER}")
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)
    sftp = ssh.open_sftp()

    run(ssh, f"mkdir -p {REMOTE_ROOT}")
    upload_tree(sftp, LOCAL_OP, REMOTE_ROOT)

    profiling_remote = posixpath.join(REMOTE_ROOT, "ops_profiling")
    for rel in ("scripts/msprof_profile_run.sh", "scripts/msprof_perf_summary.py"):
        lp = os.path.join(LOCAL_PROFILING, rel)
        if os.path.isfile(lp):
            upload_file(sftp, lp, posixpath.join(profiling_remote, rel))

    probe_cmd = (
        f"{ENV} && "
        "echo ASCEND_HOME_PATH=$ASCEND_HOME_PATH && "
        "npu-smi info | head -20 && "
        "which cmake msprof bisheng 2>/dev/null; "
        "cmake --version | head -1"
    )
    run(ssh, probe_cmd, timeout=120)

    build_cmd = (
        f"{ENV} && cd {REMOTE_ROOT} && "
        f"cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_ASC_ARCHITECTURES={ASC_ARCH} && "
        "cmake --build build -j$(nproc)"
    )
    code, _ = run(ssh, build_cmd, timeout=1200)
    if code != 0:
        ssh.close()
        return code

    verify_cmd = (
        f"{ENV} && cd {REMOTE_ROOT} && "
        "python3 scripts/gen_data.py 8 2048 fp32 && "
        "mkdir -p build/output && rm -f build/output/output.bin && "
        "cd build && ./fast_gelu 8 2048 fp32 1 && cd .. && "
        "python3 scripts/verify_result.py fp32"
    )
    code, out = run(ssh, verify_cmd, timeout=600)
    if code != 0:
        ssh.close()
        return code

    profile_cmd = (
        f"{ENV} && cd {REMOTE_ROOT} && "
        "python3 scripts/gen_data.py 8 2048 fp32 && "
        "mkdir -p build/output msprof_hw_output && "
        f"cd build && bash ../ops_profiling/scripts/msprof_profile_run.sh "
        "--warm-up=3 --output=../msprof_hw_output -- "
        "./fast_gelu 8 2048 fp32 1 2>&1 | tail -120"
    )
    prof_code, prof_out = run(ssh, profile_cmd, timeout=2400)

    summary_cmd = (
        f"{ENV} && cd {REMOTE_ROOT} && "
        "PROFILE_DIR=$(ls -d msprof_hw_output/PROF_GROUP_* 2>/dev/null | head -1); "
        "if [ -n \"$PROFILE_DIR\" ]; then "
        "python3 ops_profiling/scripts/msprof_perf_summary.py \"$PROFILE_DIR\" . "
        "> remote_hw_summary.txt 2>&1; "
        "echo \"[INFO] summary -> remote_hw_summary.txt\"; "
        "find \"$PROFILE_DIR\" -maxdepth 2 -type d | head -20; "
        "else echo '[WARN] no PROF_GROUP_*'; fi"
    )
    run(ssh, summary_cmd, timeout=600)

    os.makedirs(LOCAL_OUT, exist_ok=True)
    downloads = [
        (f"{REMOTE_ROOT}/remote_hw_summary.txt", "remote_hw_summary.txt"),
        (f"{REMOTE_ROOT}/remote_out/verify.log", "verify.log"),
    ]
    run(ssh, f"cd {REMOTE_ROOT} && python3 scripts/verify_result.py fp32 > remote_out/verify.log 2>&1 || true")
    for remote_rel, local_name in downloads:
        download_if_exists(sftp, remote_rel, os.path.join(LOCAL_OUT, local_name))

    # try download one representative msprof csv if present
    _, ls_out = run(
        ssh,
        f"find {REMOTE_ROOT}/msprof_hw_output -maxdepth 3 -type f "
        "\\( -name '*.csv' -o -name '*.json' -o -name 'summary*.txt' \\) | head -5",
        timeout=120,
    )
    for line in ls_out.splitlines():
        rp = line.strip()
        if not rp.startswith(REMOTE_ROOT):
            continue
        rel = os.path.relpath(rp, REMOTE_ROOT).replace("\\", "/")
        download_if_exists(sftp, rp, os.path.join(LOCAL_OUT, rel.replace("/", os.sep)))

    with open(os.path.join(LOCAL_OUT, "run_remote.log"), "w", encoding="utf-8") as f:
        f.write(f"verify_exit={code}\nprofile_exit={prof_code}\n")
        f.write(prof_out)

    ssh.close()
    print(f"\n[done] artifacts under {LOCAL_OUT}")
    return 0 if code == 0 else code


if __name__ == "__main__":
    sys.exit(main())
