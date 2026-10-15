#!/usr/bin/env python3
"""Execute declared build, correctness, and profiling stages with evidence logs.

This runner does not infer commands or silently install dependencies. Commands
must be JSON arrays, every stage is logged, and execution stops at the first
failed mandatory stage. It is suitable for CANNBench ``run.sh`` projects and
for explicit AProf-bundled ``ops-profiling`` commands.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
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
    command: list[str], cwd: Path, log_path: Path, timeout_seconds: int, *, deadline_monotonic=None
) -> dict[str, Any]:
    started_at = _utc_now()
    started_ns = time.monotonic_ns()
    timed_out = False
    with log_path.open("wb") as log:
        try:
            if deadline_monotonic is not None:
                timeout_seconds = min(timeout_seconds, deadline_monotonic - time.monotonic())
                if timeout_seconds <= 0:
                    raise subprocess.TimeoutExpired(command, 0)
            completed = subprocess.run(
                command,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
            )
            exit_code: int | None = completed.returncode
            timed_out = deadline_monotonic is not None and time.monotonic() > deadline_monotonic
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


def _bound_budget(config, binding, reader, task_id):
    env_ref = os.environ.get('APROF_TASK_LAUNCH_REF')
    env_index = os.environ.get('APROF_TASK_LOCAL_INDEX')
    env_deadline = os.environ.get('APROF_TASK_DEADLINE_MONOTONIC')
    if any(x is not None for x in (env_ref, env_index, env_deadline)):
        if not all(x for x in (env_ref, env_index, env_deadline)):
            raise ValueError('incomplete inherited task budget')
        inherited = {'kind':'task', 'launch_ref':env_ref}
        if binding is not None and binding != inherited:
            raise ValueError('explicit budget differs from inherited launch')
        binding = inherited
    if binding is None:
        if reader is not None or task_id is not None:
            raise ValueError('partial explicit task budget')
        return None
    sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'src'))
    from aprof_runtime.local_evidence import LocalEvidence
    from aprof_runtime.task_budget import replay_task_budget
    if reader is None:
        if env_index is None:
            raise ValueError('bound task needs a local evidence reader')
        reader = LocalEvidence.from_index(env_index)
    launch = json.loads(reader.verify_artifact(binding['launch_ref']).read_text())
    task_id = launch['task_id'] if task_id is None else task_id
    budget = replay_task_budget(reader, binding, task_id=task_id)
    if env_deadline is not None and float(env_deadline) != budget['deadline_monotonic']:
        raise ValueError('inherited deadline differs from frozen launch')
    scope = json.loads(reader.verify_artifact(budget['scope_ref']).read_text())
    refs = [stage['inputs']['command_config'] for stage in scope.get('stages', [])
            if isinstance(stage.get('inputs', {}).get('command_config'), str)]
    if not refs or not any(json.loads(reader.verify_artifact(ref).read_text()) == config for ref in refs):
        raise ValueError('stage command config is not frozen in task scope')
    return budget


def execute(config: dict[str, Any], *, dry_run: bool = False, budget_binding=None,
            budget_reader=None, task_id=None) -> dict[str, Any]:
    budget = _bound_budget(config, budget_binding, budget_reader, task_id)
    deadline = None if budget is None else budget["deadline_monotonic"]
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
    if budget is not None:
        report.update(budget_binding={'kind':'task', 'launch_ref':budget_binding['launch_ref']
            if budget_binding is not None else os.environ['APROF_TASK_LAUNCH_REF']},
            budget_ref=budget['budget_ref'], deadline_monotonic=deadline)
    def finalize():
        if budget is not None and not dry_run:
            from aprof_runtime.local_evidence import LocalEvidence
            local = LocalEvidence(output_dir / 'records')
            for row in report['stages']:
                for command in row['commands']:
                    if local.register_artifact(command['log']) != command['log_sha256']:
                        raise ValueError('command log changed before local handoff')
            if time.monotonic() > deadline:
                report['terminal_status'] = 'budget_exhausted'
            report['local_index'] = str(output_dir / 'local-evidence-index.json')
            local.register_json(report)
            local.write_index(report['local_index'])
        return report

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
                **({"deadline_monotonic": deadline} if deadline is not None else {}),
            )
            stage_result["commands"].append(command_result)
            if command_result["status"] != "passed":
                stage_result["status"] = "failed"
                stage_failed = True
                if stage.get("required", True):
                    report["terminal_status"] = f"{stage['name']}_failed"
                    report["finished_at"] = _utc_now()
                    return finalize()
                report["optional_failures"].append(stage["name"])
                break
        if not stage_failed:
            stage_result["status"] = "passed"
    if not dry_run:
        report["terminal_status"] = "passed"
        report["finished_at"] = _utc_now()
    return finalize()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--local-index", type=Path)
    parser.add_argument("--budget-launch-ref")
    parser.add_argument("--task-id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = _load_config(args.config)
        reader = None
        if args.local_index is not None:
            inherited = os.environ.get('APROF_TASK_LOCAL_INDEX')
            if inherited and args.local_index.resolve() != Path(inherited).resolve():
                raise ValueError('explicit local index differs from inherited task')
            sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'runtime' / 'src'))
            from aprof_runtime.local_evidence import LocalEvidence
            reader = LocalEvidence.from_index(args.local_index)
        report = execute(config, dry_run=args.dry_run, budget_reader=reader, task_id=args.task_id,
            budget_binding=None if args.budget_launch_ref is None else {'kind':'task', 'launch_ref':args.budget_launch_ref})
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
