#!/usr/bin/env python3
"""Run remote deployment for cases listed in inject_deploy_manifest.json."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[5]
REMOTE_TOOL = REPO_ROOT / "skills/aprof/remote-kernel-deploy/tools/remote_msprof_deploy.py"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run remote deploy for injected cases")
    parser.add_argument("--manifest", required=True, help="inject_deploy_manifest.json")
    parser.add_argument("--cases", default="", help="Comma-separated variants to run; default all non-deprecated")
    parser.add_argument("--include-weak", action="store_true", help="Run weak/deprecated cases too")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without executing")
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected = {c.strip() for c in args.cases.split(",") if c.strip()}
    results: dict[str, dict] = {}

    for case in manifest.get("cases", []):
        variant = case["variant"]
        if selected and variant not in selected:
            continue
        if not args.include_weak and case.get("quality_status") in {"weak", "deprecated_or_weak", "unsupported"}:
            results[variant] = {"skipped": True, "reason": f"quality_status={case.get('quality_status')}"}
            continue
        if case.get("applicability_status") == "unsupported":
            results[variant] = {"skipped": True, "reason": "applicability_status=unsupported"}
            continue
        cmd = [
            sys.executable,
            str(REMOTE_TOOL),
            "--local-dir",
            case["local_dir"],
            "--local-out",
            case["local_out"],
            "--remote-name",
            variant,
            "--profile-mode",
            manifest.get("profile_mode", "sim"),
            "--profiling-plan",
            case["profiling_plan"],
            "--inject-common-dir",
            manifest["inject_common_dir"],
        ]
        print(" ".join(cmd))
        if args.dry_run:
            results[variant] = {"dry_run": True, "command": cmd}
            continue
        proc = subprocess.run(cmd, cwd=REPO_ROOT)
        results[variant] = write_validation_summary(case, proc.returncode)

    batch = {
        "schema_version": 1,
        "op_name": manifest.get("op_name", "unknown"),
        "profile_mode": manifest.get("profile_mode", "sim"),
        "cases": results,
        "batch_pass": all(r.get("skipped") or r.get("returncode", 1) == 0 for r in results.values()),
    }
    out = Path(manifest["batch_local_out"]) / "batch_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(batch, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(batch, indent=2, ensure_ascii=False))
    return 0 if batch["batch_pass"] else 1


def write_validation_summary(case: dict, returncode: int) -> dict:
    local_out = Path(case["local_out"])
    deploy_results = read_json(local_out / "deploy_results.json")
    artifact_manifest = read_json(local_out / "artifact_manifest.json")
    downloaded = deploy_results.get("downloaded", [])
    summary = {
        "schema_version": 1,
        "variant": case["variant"],
        "ground_truth_label": case.get("ground_truth_label", "unknown"),
        "profile_mode": deploy_results.get("profile_mode", "sim"),
        "build_pass": deploy_results.get("build_exit") in (None, 0),
        "run_pass": "skipped",
        "profile_pass": deploy_results.get("profile_exit") in (None, 0) and bool(deploy_results.get("has_artifacts")),
        "accuracy_check": "skipped",
        "accuracy_reason": "sim-only inject path has no host execution",
        "has_trace": any(str(p).endswith("trace.json") for p in downloaded),
        "has_instr_exe": any("instr_exe" in str(p) for p in downloaded),
        "ready_for_label_alignment": bool(artifact_manifest.get("ready_for_diagnosis")),
        "deploy_results": str(local_out / "deploy_results.json"),
        "artifact_manifest": str(local_out / "artifact_manifest.json"),
        "returncode": returncode,
        "notes": [] if returncode == 0 else [f"remote deploy exited {returncode}"],
    }
    local_out.mkdir(parents=True, exist_ok=True)
    (local_out / "validation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return summary


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
