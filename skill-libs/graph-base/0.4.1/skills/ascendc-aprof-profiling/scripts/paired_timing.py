#!/usr/bin/env python3
"""Collect deterministic AB/BA command-level paired timing samples.

Commands must be timing-only: do not include build, data generation, or result
verification. The output is a measurement draft for ``aprofctl candidate
gate``; the runtime remains authoritative for bootstrap LCB and acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import time
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    required = {"schema_version", "baseline", "candidate", "pairs", "warmup", "timeout_seconds"}
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"config must contain exactly {sorted(required)}")
    if value["schema_version"] != "1.0.0":
        raise ValueError("unsupported schema_version")
    for label in ("baseline", "candidate"):
        item = value[label]
        if not isinstance(item, dict) or set(item) != {"cwd", "command"}:
            raise ValueError(f"{label} requires cwd and command")
        if not isinstance(item["command"], list) or not item["command"] or not all(
            isinstance(token, str) and token for token in item["command"]
        ):
            raise ValueError(f"{label}.command must be a non-empty string array")
        if not Path(item["cwd"]).is_dir():
            raise ValueError(f"{label}.cwd does not exist: {item['cwd']}")
    for key in ("pairs", "warmup", "timeout_seconds"):
        if isinstance(value[key], bool) or not isinstance(value[key], int):
            raise ValueError(f"{key} must be an integer")
    if value["pairs"] < 1 or value["warmup"] < 0 or value["timeout_seconds"] < 1:
        raise ValueError("pairs/timeout must be positive and warmup non-negative")
    return value


def _measure(item: dict[str, Any], timeout: int) -> int:
    start = time.perf_counter_ns()
    completed = subprocess.run(
        item["command"],
        cwd=Path(item["cwd"]),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    elapsed = time.perf_counter_ns() - start
    if completed.returncode != 0:
        tail = completed.stderr.decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(
            f"timing command failed with exit {completed.returncode}: {tail}"
        )
    return elapsed


def _stats(values: list[int]) -> dict[str, float | int]:
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "count": len(values),
        "mean_ns": mean,
        "median_ns": statistics.median(values),
        "min_ns": min(values),
        "max_ns": max(values),
        "std_ns": std,
        "cv": std / abs(mean) if mean else math.inf,
    }


def collect(config: dict[str, Any]) -> dict[str, Any]:
    timeout = config["timeout_seconds"]
    for _ in range(config["warmup"]):
        _measure(config["baseline"], timeout)
        _measure(config["candidate"], timeout)
    baseline: list[int] = []
    candidate: list[int] = []
    order: list[str] = []
    for pair_index in range(config["pairs"]):
        labels = ("baseline", "candidate") if pair_index % 2 == 0 else ("candidate", "baseline")
        order.append("AB" if pair_index % 2 == 0 else "BA")
        measured: dict[str, int] = {}
        for label in labels:
            measured[label] = _measure(config[label], timeout)
        baseline.append(measured["baseline"])
        candidate.append(measured["candidate"])
    speedups = [base / cand for base, cand in zip(baseline, candidate, strict=True)]
    config_hash = "sha256:" + hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "1.0.0",
        "kind": "aprof_paired_timing_draft",
        "measurement_protocol": "alternating_command_wall_clock_pairs_v1",
        "config_sha256": config_hash,
        "pair_count": config["pairs"],
        "production_minimum_met": config["pairs"] >= 30,
        "order": order,
        "baseline_samples_ns": baseline,
        "candidate_samples_ns": candidate,
        "pair_speedups": speedups,
        "baseline_statistics": _stats(baseline),
        "candidate_statistics": _stats(candidate),
        "median_speedup": statistics.median(speedups),
        "authority": "draft_only; aprofctl candidate gate recomputes stability and LCB",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = collect(_load(args.config))
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {args.output}: {result['pair_count']} AB/BA pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
