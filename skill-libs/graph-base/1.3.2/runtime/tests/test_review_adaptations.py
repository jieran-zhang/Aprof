# Copyright (c) 2026 AProf contributors.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.

import importlib.util
import math
from pathlib import Path
import random

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


metrics = module(ROOT / "tools/review_parallel_metrics.py")
inject = module(ROOT / "skills/ascendc-aprof-inject-problems/tools/inject_case.py")


@pytest.mark.parametrize("size,k", [(1, 1), (7, 1), (7, 7), (127, 4), (2048, 3)])
def test_topk_injection_preserves_order_and_ties(size, k):
    rng = random.Random(size)
    values = [float(rng.randrange(-4, 5)) for _ in range(size)]
    expected = sorted(enumerate(values), key=lambda p: (-p[1], p[0]))[:k]
    for injected in (False, True):
        assert inject.reference(values, "full_sort_for_topk", k, injected) == expected


@pytest.mark.parametrize(
    "values", [[1.0], [-1000.0, 0.0, 1000.0], [2.0] * 129, [-5, 1, -7, 4]]
)
def test_softmax_online_and_two_pass_preserve_normalized_output(values):
    maximum = max(values)
    weights = [math.exp(v - maximum) for v in values]
    expected = [v / sum(weights) for v in weights]
    for injected in (False, True):
        actual = inject.reference(values, "two_pass_softmax", injected=injected)
        assert actual == pytest.approx(expected, abs=1e-12)
        assert sum(actual) == pytest.approx(1.0)


@pytest.mark.parametrize("values", [[], [float("nan")], [float("inf")]])
def test_injection_rejects_unsupported_input_domain(values):
    with pytest.raises(ValueError):
        inject.reference(values, "two_pass_softmax")


def test_generation_preserves_existing_output(tmp_path):
    target = tmp_path / "case"
    manifest = inject.generate("full_sort_for_topk", 7, 2, target)
    before = (target / "injected.asc").read_bytes()
    assert manifest["hardware_correctness"] == "pending"
    with pytest.raises(FileExistsError):
        inject.generate("two_pass_softmax", 7, 1, target)
    assert (target / "injected.asc").read_bytes() == before


def observation():
    return {
        "scope": {
            "implementation_hash": "case-source",
            "workload_hash": "case-workload",
            "capture_id": "capture-1",
            "core_type": "aiv",
        },
        "evidence_status": "synthetic",
        "block_dim": 4,
        "total_tasks": 2,
        "available_cores": 48,
        "total_elements": 128,
        "dtype_bytes": 4,
        "core_times_us": {"0": 10, "1": 9, "2": 0, "3": 0},
    }


def test_parallel_metrics_include_block_dim_and_preserve_evidence_status():
    data = observation()
    result = metrics.derive(data)
    assert result["status"] == "valid"
    assert result["metrics"]["active_cores_attainable"] == 2
    assert result["metrics"]["idle_fraction"] == 0.5
    assert result["metrics"]["useful_bytes_per_core"] == 256
    assert result["evidence_status"] == "synthetic"
    data["block_dim"] = 1
    data["core_times_us"] = {"0": 10}
    assert metrics.derive(data)["metrics"]["active_cores_attainable"] == 1


def test_incomplete_core_capture_cannot_infer_idle_fraction():
    data = observation()
    del data["core_times_us"]["3"]
    result = metrics.derive(data)
    assert result["status"] == "unknown"
    assert "idle_fraction" not in result["metrics"]


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf")])
def test_invalid_core_time_is_rejected(value):
    data = observation()
    data["core_times_us"]["0"] = value
    assert metrics.derive(data)["status"] == "invalid"
