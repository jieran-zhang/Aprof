#!/usr/bin/env python3
"""Upload gelu_mul / fast_gelu_grad / foreach_norm inject cases to remote 910B,
build with dav-2201, run `msprof op --config`, parse Task Duration(us), download CSVs.

Copy to run_remote_new_ops_inject_hw.py (gitignored) and set:
  APROF_REMOTE_HOST, APROF_REMOTE_PORT (optional), APROF_REMOTE_USER,
  APROF_REMOTE_PASS, APROF_REMOTE_ROOT (optional)
Optional env:
  INJECT_OPS=gelu_mul,fast_gelu_grad              # comma-separated subset of ops
  INJECT_CASES_gelu_mul=baseline,inject_blockdim  # per-op case override
  ASC_ARCH_HW=dav-2201
  MSPROF_WARMUP=3
"""
from __future__ import annotations

import json
import os
import posixpath
import re
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
REMOTE_ROOT = os.environ.get("APROF_REMOTE_ROOT", f"/home/{USER}/aprof_new_ops_inject")
ASC_ARCH_HW = os.environ.get("ASC_ARCH_HW", "dav-2201")

# op_name -> (kernel_name, default_cases)
OPS: dict[str, tuple[str, list[str]]] = {
    "gelu_mul": (
        "gelu_mul_kernel",
        ["baseline", "inject_blockdim", "inject_pipe_break", "inject_tilelen_small"],
    ),
    "fast_gelu_grad": (
        "fast_gelu_grad_kernel",
        ["baseline", "inject_blockdim", "inject_api_inefficient", "inject_dynshape"],
    ),
    "foreach_norm": (
        "foreach_norm_kernel",
        ["baseline", "inject_tiling_unreasonable", "inject_data_move_bottleneck", "inject_blockdim"],
    ),
}

SELECTED_OPS = [c.strip() for c in os.environ.get("INJECT_OPS", ",".join(OPS)).split(",") if c.strip()]
TEXT_EXT = {".sh", ".asc", ".h", ".py", ".md", ".json"}

LOCAL_BASE_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "benchmarks", "aprof_injected_ops")
)
LOCAL_COMMON = os.path.abspath(os.path.join(LOCAL_BASE_ROOT, "common"))


def cases_for(op: str) -> list[str]:
    env_key = f"INJECT_CASES_{op}"
    if env_key in os.environ:
        return [c.strip() for c in os.environ[env_key].split(",") if c.strip()]
    return OPS[op][1]


def local_out_dir(op: str) -> str:
    return os.path.join(LOCAL_BASE_ROOT, op, "remote_inject_out")


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
    skip = {"build_sim", "data", "msprof_sim_output", "msprof_hw_output", "remote_inject_out", "__pycache__"}
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
    print(f"\n>>> {cmd[:280]}")
    _, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    out = (stdout.read() + stderr.read()).decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out[-12000:] if len(out) > 12000 else out)
    return code, out


def parse_duration_from_text(text: str) -> float | None:
    match = re.search(r"Task Duration\(us\):\s*([\d.]+)", text)
    if match:
        return float(match.group(1))
    for line in text.splitlines():
        line = line.strip()
        if re.fullmatch(r"\d+(\.\d+)?", line):
            return float(line)
    return None


def main() -> int:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"connecting {HOST}:{PORT} for hardware profiling (ASC_ARCH_HW={ASC_ARCH_HW})")
    ssh.connect(HOST, port=PORT, username=USER, password=PASS, timeout=60)
    sftp = ssh.open_sftp()

    run(ssh, f"mkdir -p {REMOTE_ROOT}/common")
    for rel in ("inject_run.sh", "inject_gen_data.py", "parse_hw_op_summary.py"):
        upload_file(sftp, os.path.join(LOCAL_COMMON, rel), f"{REMOTE_ROOT}/common/{rel}")

    probe_cmd = (
        f"{ENV} && npu-smi info | head -12 && "
        "which msprof bisheng 2>/dev/null; msprof op -h 2>&1 | head -5"
    )
    run(ssh, probe_cmd, timeout=120)

    all_payload: dict[str, dict] = {}

    for op in SELECTED_OPS:
        kernel_name, _ = OPS[op]
        cases = cases_for(op)
        op_root = f"{REMOTE_ROOT}/{op}"
        local_base = os.path.join(LOCAL_BASE_ROOT, op)
        local_out = local_out_dir(op)
        os.makedirs(local_out, exist_ok=True)

        print(f"\n############# op={op} kernel={kernel_name} cases={cases} #############")
        run(ssh, f"mkdir -p {op_root}")

        results: dict[str, dict] = {}
        for case in cases:
            print(f"\n========== {op}/{case} (hw) ==========")
            case_local = os.path.join(local_base, case)
            case_remote = f"{op_root}/{case}"
            run(ssh, f"mkdir -p {case_remote}")
            upload_tree(sftp, case_local, case_remote)

            hw_cmd = (
                f"{ENV} && cd {case_remote} && "
                f"export APROF_INJECT_COMMON={REMOTE_ROOT}/common && "
                f"export APROF_INJECT_RUN={REMOTE_ROOT}/common/inject_run.sh && "
                f"export ASC_ARCH_HW={ASC_ARCH_HW} && "
                f"export MSPROF_WARMUP={os.environ.get('MSPROF_WARMUP', '3')} && "
                "bash run.sh all_hw 2>&1"
            )
            code, out = run(ssh, hw_cmd, timeout=2400)

            duration = parse_duration_from_text(out)
            parse_cmd = (
                f"cd {case_remote} && "
                "python3 -c \"import json; print(json.load(open('metadata.json'))['injected_label'])\" && "
                f"python3 {REMOTE_ROOT}/common/parse_hw_op_summary.py msprof_hw_output {kernel_name} && "
                "find msprof_hw_output -name 'OpBasicInfo.csv' -o -name 'op_summary_*.csv' 2>/dev/null | head -3"
            )
            _, check_out = run(ssh, parse_cmd, timeout=120)

            label = ""
            csv_paths: list[str] = []
            for line in check_out.splitlines():
                s = line.strip()
                if not s:
                    continue
                if s.endswith(".csv"):
                    csv_paths.append(s)
                elif duration is None and re.fullmatch(r"\d+(\.\d+)?", s):
                    duration = float(s)
                elif not label and not s.startswith("/") and not s.startswith("null"):
                    label = s

            oprof_id = ""
            for line in out.splitlines():
                m = re.search(r"msprof_hw_output/(OPPROF_[^\s]+)", line)
                if m:
                    oprof_id = m.group(1)
                    break

            results[case] = {
                "injected_label": label,
                "build_hw_exit": code,
                "hw_exit": 0 if duration is not None else 1,
                "has_hw_csv": bool(csv_paths),
                "task_duration_us": duration,
                "oprof_id": oprof_id,
                "hw_csv": csv_paths[:1],
            }

            # Download the op_summary CSV for offline analysis.
            if csv_paths:
                line = csv_paths[0]
                if line.startswith(case_remote) and line.endswith(".csv"):
                    rel = os.path.relpath(line, case_remote).replace("\\", "/")
                    local_path = os.path.join(local_out, f"{case}_hw", rel.replace("/", os.sep))
                    try:
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        sftp.get(line, local_path)
                        print(f"downloaded {local_path}")
                    except Exception as exc:
                        print(f"skip download {line}: {exc}")

        payload = {
            **results,
            "op": op,
            "kernel_name": kernel_name,
            "npu_arch_hw": ASC_ARCH_HW,
            "profile_mode": "msprof op --config (mode=onboard)",
            "notes": "hardware profiling via dav-2201 kernel .o + op_config.json",
        }
        out_path = os.path.join(local_out, "results_hw.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        print(f"\n[written] {out_path}")
        all_payload[op] = payload

    # Combined summary across all 3 ops.
    combined_path = os.path.join(LOCAL_BASE_ROOT, "new_ops_inject_results.json")
    with open(combined_path, "w", encoding="utf-8") as f:
        json.dump(all_payload, f, indent=2, ensure_ascii=False)
    print(f"\n[written combined] {combined_path}")

    ssh.close()
    print(json.dumps(all_payload, indent=2, ensure_ascii=False))
    failed = [f"{op}/{c}" for op, p in all_payload.items() for c, r in p.items()
              if isinstance(r, dict) and r.get("task_duration_us") is None]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
