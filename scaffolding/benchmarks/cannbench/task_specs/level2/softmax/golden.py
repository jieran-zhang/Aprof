#!/usr/bin/python3
# coding=utf-8

# ----------------------------------------------------------------------------------------------------------
# Copyright (c) 2026 Huawei Technologies Co., Ltd.
# This program is free software, you can redistribute it and/or modify it under the terms and conditions of
# CANN Open Software License Agreement Version 2.0 (the "License").
# Please refer to the License for details. You may not use this file except in compliance with the License.
# THIS SOFTWARE IS PROVIDED ON AN "AS IS" BASIS, WITHOUT WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO NON-INFRINGEMENT, MERCHANTABILITY, OR FITNESS FOR A PARTICULAR PURPOSE.
# See LICENSE in the root of the software repository for the full text of the License.
# ----------------------------------------------------------------------------------------------------------

import torch

"""
Softmax 算子 Torch Golden 参考实现

沿指定维度计算 Softmax 归一化

公式:
    y_i = exp(x_i) / sum(exp(x_j))

参考 PyTorch API: torch.nn.functional.softmax
    https://pytorch.org/docs/stable/generated/torch.nn.functional.softmax.html

Parameters:
    - x: 任意维度输入张量
    - dim: int, 默认 -1 - 计算 Softmax 的维度
"""


def softmax(
    x: torch.Tensor,
    dim: int = -1
) -> torch.Tensor:
    """
    沿指定维度计算 Softmax 归一化

    Args:
        x: 输入张量，任意 shape
        dim: 计算 Softmax 的维度，默认为 -1（最后一维）

    Returns:
        Softmax 归一化后的张量，shape 与输入相同
        输出元素值在 [0, 1] 范围内，且沿 dim 维度求和为 1

    Examples:
        >>> x = torch.randn(1024, 2048)
        >>> y = softmax(x, dim=-1)
    """
    y = torch.nn.functional.softmax(x, dim=dim)

    return y
