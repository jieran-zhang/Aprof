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
GridSampler3D算子Torch Golden参考实现

根据grid中坐标信息填充输出
公式: y = grid_sample(x, grid)
"""
def grid_sampler_3d(
    x: torch.Tensor, grid: torch.Tensor, interpolation_mode: str = 'bilinear', padding_mode: str = 'zeros', align_corners: bool = False
) -> torch.Tensor:
    """
    根据grid中坐标信息填充输出
    
    公式: y = grid_sample(x, grid)
    
    Args:
        x: 输入张量
        grid: 采样网格
        interpolation_mode: 插值模式 ('bilinear': 三线性, 'nearest': 最近邻)。5D 输入下不支持 'bicubic'（PyTorch 限制）
        padding_mode: 填充模式 ('zeros': 零填充, 'border': 边界填充, 'reflection': 反射填充)
        align_corners: 是否对齐角点
    
    Returns:
        输出张量，采样结果
    """

    return torch.nn.functional.grid_sample(
        x, grid, mode=interpolation_mode, padding_mode=padding_mode, align_corners=align_corners
    )
