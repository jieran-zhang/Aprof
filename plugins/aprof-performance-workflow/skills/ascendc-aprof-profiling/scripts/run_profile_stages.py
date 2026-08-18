#!/usr/bin/env python3
"""Execute declared build, correctness, and profiling stages with evidence logs.

This runner does not infer commands or silently install dependencies. Commands
must be JSON arrays, every stage is logged, and execution stops at the first
failed mandatory stage. It is suitable for CANNBench ``run.sh`` projects and
for explicit CANNBot ``ops-profiling`` commands.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
from typing import Any


STAGE_ORDER = ("preflight", "build", "correctness", "profile")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _load_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read config {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != "1.0.0":
        raise ValueError("config must be a schema_version=1.0.0 JSON object")
    unknown = set(value) - {"schema_version", "op_dir", "output_dir", "stages"}
    if unknown:
        raise ValueError(f"unknown config fields: {sorted(unknown)}")
    stages = value.get("stages")
    if not isinstance(stages, list) or not stages:
        raise ValueError("config.stages must be a non-empty array")
    seen: list[str] = []
    for index, stage in enumerate(stages):
        if not isinstance(stage, dict):
            raise ValueError(f"config.stages[{index}] must be an object")
        extra = set(stage) - {"name", "commands", "timeout_seconds", "required"}
        if extra:
            raise ValueError(f"config.stages[{index}] unknown fields: {sorted(extra)}")
        name = stage.get("name")
        if name not in STAGE_ORDER:
            raise ValueError(f"config.stages[{index}].name must be one of {STAGE_ORDER}")
        if name in seen:
            raise ValueError(f"duplicate stage: {name}")
        seen.append(name)
        commands = stage.get("commands")
        if not isinstance(commands, list) or not commands:
            raise ValueError(f"stage {name} requires commands")
        for command_index, command in enumerate(commands):
            if (
                not isinstance(command, list)
                or not command
                or not all(isinstance(token, str) and token for token in command)
            ):
                raise ValueError(
                    f"stage {name} command {command_index} must be a non-empty string array"
                )
        timeout = stage.get("timeout_seconds", 1800)
        if isinstance(timeout, bool) or not isinstance(timeout, int) or timeout < 1:
            raise ValueError(f"stage {name} timeout_seconds must be a positive integer")
        required = stage.get("required", True)
        if type(required) is not bool:
            raise ValueError(f"stage {name} required must be boolean")
    order = [STAGE_ORDER.index(name) for name in seen]
    if order != sorted(order):
        raise ValueError(f"stages must follow {STAGE_ORDER}")
    required_by_name = {
        stage["name"]: stage.get("required", True) for stage in stages
    }
    if "correctness" in seen and "build" not in seen:
        raise ValueError("correctness stage requires a prior build stage")
    if "profile" in seen and "correctness" not in seen:
        raise ValueError("profile stage requires a prior correctness stage")
    for mandatory_gate in ("build", "correctness"):
        if mandatory_gate in required_by_name and not required_by_name[mandatory_gate]:
            raise ValueError(f"{mandatory_gate} stage cannot be optional")
    return value


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_command(
    command: list[str], cwd: Path, log_path: Path, timeout_seconds: int
) -> dict[str, Any]:
    started_at = _utc_now()
    started_ns = time.monotonic_ns()
    timed_out = False
    with log_path.open("wb") as log:
        try:
            completed = subprocess.run(
                command,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
            )
            exit_code: int | None = completed.returncode
        except subprocess.TimeoutExpired:
            exit_code = None
            timed_out = True
            log.write(f"\nAPROF_TIMEOUT after {timeout_seconds}s\n".encode("utf-8"))
    elapsed_ns = time.monotonic_ns() - started_ns
    return {
        "command": command,
        "started_at": started_at,
        "elapsed_ns": elapsed_ns,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "status": "passed" if exit_code == 0 and not timed_out else "failed",
        "log": str(log_path),
        "log_sha256": _sha256(log_path),
    }


def execute(config: dict[str, Any], *, dry_run: bool = False) -> dict[str, Any]:
    op_dir = Path(config["op_dir"]).resolve()
    if not op_dir.is_dir():
        raise ValueError(f"op_dir does not exist: {op_dir}")
    output_dir = Path(config["output_dir"])
    if not output_dir.is_absolute():
        output_dir = op_dir / output_dir
    output_dir = output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()) and not dry_run:
        raise ValueError(f"refusing to overwrite non-empty output_dir: {output_dir}")
    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "schema_version": "1.0.0",
        "kind": "aprof_profile_stage_execution",
        "op_dir": str(op_dir),
        "output_dir": str(output_dir),
        "dry_run": dry_run,
        "started_at": _utc_now(),
        "stages": [],
        "optional_failures": [],
        "terminal_status": "planned" if dry_run else "running",
    }
    for stage in config["stages"]:
        stage_result: dict[str, Any] = {
            "name": stage["name"],
            "required": stage.get("required", True),
            "commands": [],
            "status": "planned" if dry_run else "running",
        }
        report["stages"].append(stage_result)
        if dry_run:
            stage_result["commands"] = [
                {"command": command, "timeout_seconds": stage.get("timeout_seconds", 1800)}
                for command in stage["commands"]
            ]
            continue
        stage_failed = False
        for command_index, command in enumerate(stage["commands"]):
            log_path = output_dir / f"{stage['name']}.{command_index + 1}.log"
            command_result = _run_command(
                command,
                op_dir,
                log_path,
                stage.get("timeout_seconds", 1800),
            )
            stage_result["commands"].append(command_result)
            if command_result["status"] != "passed":
                stage_result["status"] = "failed"
                stage_failed = True
                if stage.get("required", True):
                    report["terminal_status"] = f"{stage['name']}_failed"
                    report["finished_at"] = _utc_now()
                    return report
                report["optional_failures"].append(stage["name"])
                break
        if not stage_failed:
            stage_result["status"] = "passed"
    if not dry_run:
        report["terminal_status"] = "passed"
        report["finished_at"] = _utc_now()
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = _load_config(args.config)
        report = execute(config, dry_run=args.dry_run)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.report}: {report['terminal_status']}")
    return 0 if report["terminal_status"] in {"planned", "passed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
