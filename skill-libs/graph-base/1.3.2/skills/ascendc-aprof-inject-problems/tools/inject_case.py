#!/usr/bin/env python3
# Copyright (c) 2026 AProf contributors.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
"""Generate bounded algorithm-selection cases with explicit semantic contracts."""

import argparse
import hashlib
import json
import math
from pathlib import Path

RECIPES = ("full_sort_for_topk", "two_pass_softmax")


def reference(values, recipe, k=1, injected=False):
    if not values or len(values) > 2048 or not all(math.isfinite(v) for v in values):
        raise ValueError("expected 1..2048 finite input values")
    if recipe == "full_sort_for_topk":
        if not 1 <= k <= len(values):
            raise ValueError("expected 1 <= k <= size")
        pairs = list(enumerate(values))
        rounds = len(values) if injected else k
        for i in range(rounds):
            best = min(range(i, len(pairs)), key=lambda j: (-pairs[j][1], pairs[j][0]))
            pairs[i], pairs[best] = pairs[best], pairs[i]
        return pairs[:k]
    if recipe != "two_pass_softmax":
        raise ValueError("unknown recipe")
    if injected:
        maximum = max(values)
        total = sum(math.exp(v - maximum) for v in values)
    else:
        maximum, total = values[0], 1.0
        for v in values[1:]:
            next_max = max(maximum, v)
            total = total * math.exp(maximum - next_max) + math.exp(v - next_max)
            maximum = next_max
    return [math.exp(v - maximum) / total for v in values]


def kernel(recipe, size, k, injected):
    preamble = """#include "kernel_operator.h"
using namespace AscendC;
"""
    if recipe == "full_sort_for_topk":
        rounds = size if injected else k
        return (
            preamble
            + f"""
extern "C" __global__ __aicore__ void aprof_case(GM_ADDR x, GM_ADDR y, GM_ADDR indices) {{
    KERNEL_TASK_TYPE_DEFAULT(KERNEL_TYPE_AIV_ONLY);
    if (GetBlockIdx() != 0) {{ return; }}
    TPipe pipe;
    TBuf<TPosition::VECCALC> storage;
    pipe.InitBuffer(storage, {((size * 8 + 31) // 32) * 32});
    LocalTensor<float> values = storage.Get<float>();
    LocalTensor<int32_t> order = storage.Get<int32_t>()[{size}];
    GlobalTensor<float> input;
    GlobalTensor<float> output;
    GlobalTensor<int32_t> indexOutput;
    input.SetGlobalBuffer((__gm__ float*)x, {size});
    output.SetGlobalBuffer((__gm__ float*)y, {k});
    indexOutput.SetGlobalBuffer((__gm__ int32_t*)indices, {k});
    for (int i = 0; i < {size}; ++i) {{ values.SetValue(i, input.GetValue(i)); order.SetValue(i, i); }}
    for (int i = 0; i < {rounds}; ++i) {{
        int best = i;
        for (int j = i + 1; j < {size}; ++j) {{
            float a = values.GetValue(j), b = values.GetValue(best);
            if (a > b || (a == b && order.GetValue(j) < order.GetValue(best))) {{ best = j; }}
        }}
        float oldValue = values.GetValue(i);
        int32_t oldIndex = order.GetValue(i);
        values.SetValue(i, values.GetValue(best)); order.SetValue(i, order.GetValue(best));
        values.SetValue(best, oldValue); order.SetValue(best, oldIndex);
    }}
    for (int i = 0; i < {k}; ++i) {{ output.SetValue(i, values.GetValue(i)); indexOutput.SetValue(i, order.GetValue(i)); }}
    DataCacheCleanAndInvalid<float, CacheLine::ENTIRE_DATA_CACHE, DcciDst::CACHELINE_OUT>(output);
    DataCacheCleanAndInvalid<int32_t, CacheLine::ENTIRE_DATA_CACHE, DcciDst::CACHELINE_OUT>(indexOutput);
}}
"""
        )
    stats = (
        f"""for (int i = 1; i < {size}; ++i) {{ float v = input.GetValue(i); maximum = v > maximum ? v : maximum; }}
    float total = 0;
    for (int i = 0; i < {size}; ++i) {{ total += exponent(input.GetValue(i) - maximum, temp); }}"""
        if injected
        else f"""float total = 1;
    for (int i = 1; i < {size}; ++i) {{
        float v = input.GetValue(i), nextMax = v > maximum ? v : maximum;
        total = total * exponent(maximum - nextMax, temp) + exponent(v - nextMax, temp);
        maximum = nextMax;
    }}"""
    )
    return (
        preamble
        + f"""
__aicore__ inline float exponent(float value, LocalTensor<float> temp) {{
    temp.SetValue(0, value);
    PipeBarrier<PIPE_ALL>();
    Exp(temp, temp, 8);
    PipeBarrier<PIPE_ALL>();
    return temp.GetValue(0);
}}
extern "C" __global__ __aicore__ void aprof_case(GM_ADDR x, GM_ADDR y, GM_ADDR indices) {{
    KERNEL_TASK_TYPE_DEFAULT(KERNEL_TYPE_AIV_ONLY);
    if (GetBlockIdx() != 0) {{ return; }}
    TPipe pipe;
    TBuf<TPosition::VECCALC> storage;
    pipe.InitBuffer(storage, 32);
    LocalTensor<float> temp = storage.Get<float>();
    for (int i = 0; i < 8; ++i) {{ temp.SetValue(i, 0); }}
    GlobalTensor<float> input;
    GlobalTensor<float> output;
    input.SetGlobalBuffer((__gm__ float*)x, {size});
    output.SetGlobalBuffer((__gm__ float*)y, {size});
    float maximum = input.GetValue(0);
    {stats}
    for (int i = 0; i < {size}; ++i) {{ output.SetValue(i, exponent(input.GetValue(i) - maximum, temp) / total); }}
    DataCacheCleanAndInvalid<float, CacheLine::ENTIRE_DATA_CACHE, DcciDst::CACHELINE_OUT>(output);
}}
"""
    )


def generate(recipe, size, k, output):
    if recipe not in RECIPES or not 1 <= size <= 2048 or not 1 <= k <= size:
        raise ValueError("invalid recipe, size or k")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    files = {}
    runner = (
        Path(__file__).resolve().parents[1] / "assets/device_runner.cpp"
    ).read_text(encoding="utf-8")
    for name, injected in (("baseline.asc", False), ("injected.asc", True)):
        text = kernel(recipe, size, k, injected)
        (output / name).write_text(text, encoding="utf-8", newline="\n")
        files[name] = hashlib.sha256(text.encode()).hexdigest()
        output_count = k if recipe == "full_sort_for_topk" else size
        constants = (
            f"\n#define APROF_CASE_SIZE {size}\n"
            f"#define APROF_CASE_OUTPUT {output_count}\n"
            f"#define APROF_CASE_TOPK {int(recipe == 'full_sort_for_topk')}\n"
        )
        executable = text + constants + runner
        runner_name = name.replace(".asc", "-run.asc")
        (output / runner_name).write_text(executable, encoding="utf-8", newline="\n")
        files[runner_name] = hashlib.sha256(executable.encode()).hexdigest()
    manifest = {
        "recipe": recipe,
        "problem_family": "api_algorithm",
        "size": size,
        "k": k,
        "dtype": "float32",
        "input_domain": "finite",
        "block_dim": 1,
        "core_type": "aiv",
        "files": files,
        "hardware_correctness": "pending",
        "performance": "pending",
        "blind_alignment": "pending",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recipe", choices=RECIPES, required=True)
    parser.add_argument("--size", type=int, required=True)
    parser.add_argument("--k", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = generate(args.recipe, args.size, args.k, args.output)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
