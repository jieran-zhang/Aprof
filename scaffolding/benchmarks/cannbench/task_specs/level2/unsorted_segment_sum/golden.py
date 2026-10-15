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
UnsortedSegmentSum算子Torch Golden参考实现

沿segment_ids指定的段对数据进行求和
公式: y[i] = sum(data[j]) where segment_ids[j] == i
"""
def unsorted_segment_sum(
    data: torch.Tensor, segment_ids: torch.Tensor, num_segments: int
) -> torch.Tensor:
    """
    沿segment_ids指定的段对数据进行求和

    公式: y[i] = sum(data[j]) where segment_ids[j] == i

    对于 FP16 输入，使用 FP32 进行内部累加以保证精度，其他类型保持原样

    Args:
        data: 输入数据张量
        segment_ids: 段ID张量
        num_segments: 段数量

    Returns:
        输出张量，段求和结果
    """
    output_shape = (num_segments,) + data.shape[1:]

    # FP16/BF16 输入升精度到 FP32 进行累加以保证精度
    if data.dtype in (torch.float16, torch.bfloat16):
        y_fp32 = torch.zeros(output_shape, dtype=torch.float32, device=data.device)
        data_fp32 = data.to(torch.float32)
        y_fp32.index_add_(0, segment_ids, data_fp32)
        y = y_fp32.to(data.dtype)
    else:
        y = torch.zeros(output_shape, dtype=data.dtype, device=data.device)
        y.index_add_(0, segment_ids, data)

    return y
