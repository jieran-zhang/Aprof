#!/usr/bin/python3
# coding=utf-8

# ----------------------------------------------------------------------------------------------------------
# Copyright (c) 2025 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# ----------------------------------------------------------------------------------------------------------

import os
import numpy as np


def calculateSum(arr, dtype):
    """递归二分求和，模拟硬件归约过程"""
    n = len(arr)
    if n == 1:
        return arr[0]
    if n % 2 != 0:
        newInput = np.zeros(n // 2 + 1).astype(dtype)
        for i in range(n // 2):
            newInput[i] = arr[i * 2] + arr[i * 2 + 1]
        newInput[n // 2] = arr[-1]
    else:
        newInput = np.zeros(n // 2).astype(dtype)
        for i in range(n // 2):
            newInput[i] = arr[i * 2] + arr[i * 2 + 1]
    return calculateSum(newInput, dtype)


def Sum(x, n, insum):
    """计算每行的和"""
    for i, _ in enumerate(x):
        res = calculateSum(x[i, :n], x.dtype)
        insum[i] = res


def gen_golden_data():
    """
    生成测试输入数据和真值数据
    """
    dtype = np.float32
    outer = 3  # 行数
    inner = 32  # 列数
    n = 32  # 实际元素个数

    # 生成随机输入数据
    x = np.random.randint(-100, 100, [outer, inner]).astype(dtype)

    # 计算输出对齐后的大小
    if dtype == np.float16:
        outer_pad = (outer * 2 + 31) // 32 * 32 // 2
    else:
        outer_pad = (outer * 4 + 31) // 32 * 32 // 4

    golden = np.zeros(outer_pad, dtype=dtype)

    # 场景：Sum - 求和
    Sum(x, n, golden)

    # 保存二进制文件
    os.makedirs("input", exist_ok=True)
    x.tofile("./input/input_x.bin")
    os.makedirs("output", exist_ok=True)
    golden.tofile("./output/golden.bin")


if __name__ == "__main__":
    gen_golden_data()
