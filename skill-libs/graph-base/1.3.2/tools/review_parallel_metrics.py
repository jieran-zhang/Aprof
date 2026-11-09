#!/usr/bin/env python3
# Copyright (c) 2026 AProf contributors.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
"""Validate explicit parallelism measurements without guessing profiler fields."""

import argparse
import json
import math
from pathlib import Path


def derive(observation):
    """Return arithmetic and missing evidence separately from mechanism claims."""
    metrics, errors, missing = {}, [], []
    integers = {}
    for name in (
        "block_dim",
        "total_tasks",
        "available_cores",
        "total_elements",
        "dtype_bytes",
    ):
        value = observation.get(name)
        if value is None:
            missing.append(name)
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            errors.append(name + " must be a nonnegative integer")
        else:
            integers[name] = value
    scope = observation.get("scope", {})
    if not isinstance(scope, dict) or not all(
        scope.get(k)
        for k in ("implementation_hash", "workload_hash", "core_type", "capture_id")
    ):
        missing.append("scope")
    elif scope["core_type"] not in {"aiv", "aic"}:
        errors.append("scope.core_type must be aiv or aic")
    if all(k in integers for k in ("block_dim", "total_tasks", "available_cores")):
        active = min(
            integers[k] for k in ("block_dim", "total_tasks", "available_cores")
        )
        metrics["active_cores_attainable"] = active
        if integers["available_cores"]:
            metrics["attainable_coverage"] = active / integers["available_cores"]
            metrics["launch_coverage"] = (
                min(integers["block_dim"], integers["available_cores"])
                / integers["available_cores"]
            )
        else:
            missing.append("positive available_cores")
        if active and "total_elements" in integers:
            elements = (integers["total_elements"] + active - 1) // active
            metrics["elements_per_core"] = elements
            if "dtype_bytes" in integers:
                metrics["useful_bytes_per_core"] = elements * integers["dtype_bytes"]
    samples = observation.get("core_times_us")
    if samples is None:
        missing.append("core_times_us")
    elif not isinstance(samples, dict) or not samples:
        errors.append("core_times_us must map all launched block IDs to times")
    elif any(
        isinstance(v, bool)
        or not isinstance(v, (int, float))
        or not math.isfinite(v)
        or v < 0
        for v in samples.values()
    ):
        errors.append("core times must be finite nonnegative numbers")
    elif "block_dim" in integers and set(samples) != {
        str(i) for i in range(integers["block_dim"])
    }:
        missing.append("complete launched block coverage")
    else:
        values = list(samples.values())
        peak = max(values)
        if peak:
            metrics["imbalance"] = (peak - min(values)) / peak
            metrics["idle_fraction"] = values.count(0) / len(values)
        else:
            missing.append("positive core time")
    return {
        "status": "invalid" if errors else "unknown" if missing else "valid",
        "metrics": metrics,
        "errors": errors,
        "unknowns": missing,
        "evidence_status": observation.get("evidence_status", "unknown"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    observation = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(observation, dict):
        parser.error("input must be a JSON object")
    result = derive(observation)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return int(result["status"] == "invalid")


if __name__ == "__main__":
    raise SystemExit(main())
