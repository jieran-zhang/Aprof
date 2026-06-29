#!/usr/bin/env python3
"""Re-run only msprof hardware capture on remote (after verify passed)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from run_remote import HOST, PORT, USER, PASS, ENV, REMOTE_ROOT, run, download_if_exists, LOCAL_OUT
import paramiko


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)

    profile_cmd = (
        f"{ENV} && cd {REMOTE_ROOT} && "
        "python3 scripts/gen_data.py 8 2048 fp32 && "
        "mkdir -p build/output msprof_hw_output && "
        "cd build && bash ../ops_profiling/scripts/msprof_profile_run.sh "
        "--warm-up=3 --output=../msprof_hw_output -- "
        "./fast_gelu 8 2048 fp32 1 2>&1 | tail -150"
    )
    prof_code, prof_out = run(ssh, profile_cmd, timeout=3600)

    summary_cmd = (
        f"{ENV} && cd {REMOTE_ROOT} && "
        "PROFILE_DIR=$(ls -d msprof_hw_output/PROF_GROUP_* 2>/dev/null | head -1); "
        "if [ -n \"$PROFILE_DIR\" ]; then "
        "python3 ops_profiling/scripts/msprof_perf_summary.py \"$PROFILE_DIR\" . "
        "> remote_hw_summary.txt 2>&1; "
        "find \"$PROFILE_DIR\" -name '*.csv' | head -10; "
        "fi"
    )
    run(ssh, summary_cmd, timeout=600)

    sftp = ssh.open_sftp()
    os.makedirs(LOCAL_OUT, exist_ok=True)
    download_if_exists(sftp, f"{REMOTE_ROOT}/remote_hw_summary.txt", os.path.join(LOCAL_OUT, "remote_hw_summary.txt"))
    _, ls_out = run(
        ssh,
        f"find {REMOTE_ROOT}/msprof_hw_output -type f \\( -name '*.csv' -o -name 'msprof.log' \\) | head -15",
        timeout=120,
    )
    for line in ls_out.splitlines():
        rp = line.strip()
        if not rp.startswith(REMOTE_ROOT):
            continue
        rel = os.path.relpath(rp, REMOTE_ROOT).replace("\\", "/")
        download_if_exists(sftp, rp, os.path.join(LOCAL_OUT, rel.replace("/", os.sep)))

    with open(os.path.join(LOCAL_OUT, "profile_only.log"), "w", encoding="utf-8") as f:
        f.write(prof_out)
    ssh.close()
    return prof_code


if __name__ == "__main__":
    sys.exit(main())
