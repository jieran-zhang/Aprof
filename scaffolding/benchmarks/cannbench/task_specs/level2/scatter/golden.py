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
Scatter算子Torch Golden参考实现

将updates按索引indices更新到data中
公式: y[index[i][j][k]] = src[i][j][k] (if dim == 0)
"""
def scatter(
    data: torch.Tensor, dim: int, indices: torch.Tensor, updates: torch.Tensor, reduce: str = None
) -> torch.Tensor:
    """
    将updates按索引indices更新到data中

    公式: y[index[i][j][k]] = src[i][j][k] (if dim == 0)

    Args:
        data: 输入数据张量
        dim: 沿哪个维度scatter
        indices: 索引张量
        updates: 更新值张量
        reduce: 聚合方式 (None/update, add, multiply, amin, amax)

    Returns:
        输出张量，scatter结果
    """

    y = data.clone()
    idx = indices.long()
    if reduce is None or reduce == 'update':
        y.scatter_(dim, idx, updates)
    elif reduce == 'add':
        y.scatter_add_(dim, idx, updates)
    elif reduce == 'multiply':
        y.scatter_reduce_(dim, idx, updates, reduce="prod", include_self=True)
    elif reduce == 'amin':
        y.scatter_reduce_(dim, idx, updates, reduce="amin", include_self=True)
    elif reduce == 'amax':
        y.scatter_reduce_(dim, idx, updates, reduce="amax", include_self=True)
    return y


def get_input(
    data: torch.Tensor,
    indices: torch.Tensor,
    updates: torch.Tensor,
    dim: int = 0,
    reduce: str = None,
    **kwargs,
):
    """把 indices 重建为沿 dim 互异，使 reduce=None（update）语义良定义。

    PyTorch 明文规定 ``Tensor.scatter_`` 在 index 沿 dim 存在重复项时结果
    **nondeterministic**——同一目标位置被多次写入，最终留下哪一个取决于实现的
    写入顺序。而 cases.yaml 只能用单区间 value_range 表达索引，通用生成器按
    ``randint(0, D-1)`` 独立采样，生日悖论下重复几乎必然：20 个用例里 14 个是
    reduce=None，其中 12 个存在大量重复（每列约 9% 的元素被覆盖写）。

    实测两种同样符合 scatter 语义的实现（正序写=后写赢 / 逆序写=先写赢）在同一份
    输入上的输出差异：c1/c2/c3/c7/c8/c11/c17/c19/c20 约 9%，c13 10.01%，
    c15 高达 56.38%。也就是说任何 NPU kernel 只要写入顺序与 torch CPU 不一致就
    必挂，**与实现是否正确无关**。

    这里按 case 的实际形状（不写死）为每个切片重新抽取 n 个互异索引：
    n = indices.shape[dim] ≤ D = data.shape[dim]（全部用例均满足），取 [0, D) 的
    随机置换前 n 项。不排序——scatter 的结果与索引顺序无关，无重复即可。

    带 reduce 的用例（add / multiply / amin / amax）原样返回：这些归约可交换，
    重复索引下结果良定义，不需要也不应该改变其数据分布。

    kernel_eval 用输入名 + attrs 作为关键字调用本函数，并用返回值（按 golden
    签名的 Tensor 顺序）同时替换 golden 与候选的输入，故比较公平。

    Returns:
        [data, indices, updates]，顺序与 scatter 签名的 Tensor 参数一致。
    """
    # 可交换归约：重复索引良定义，保持原始分布
    if reduce not in (None, 'update'):
        return [data, indices, updates]

    ndim = indices.dim()
    dim_n = dim if dim >= 0 else ndim + dim
    D = int(data.shape[dim_n])
    n = int(indices.shape[dim_n])
    if n <= 1 or D <= 1:
        return [data, indices, updates]
    if n > D:
        # 抽屉原理：互异索引不存在，保持原样（当前用例集不会走到这里）
        return [data, indices, updates]

    # 把 dim 换到最后一维并展平前导维 -> (slices, n)，逐切片独立抽样
    moved = indices.movedim(dim_n, -1)
    moved_shape = moved.shape
    slices = moved.numel() // n

    g = torch.Generator().manual_seed(0)  # 固定种子：跨 eval 运行必须可复现
    out = torch.empty(slices, n, dtype=torch.int64)
    # 分块限制峰值内存：置换临时量为 chunk*D，最大用例 slices*D 达 49.7M
    chunk = max(1, min(slices, (1 << 22) // D or 1))
    for start in range(0, slices, chunk):
        stop = min(start + chunk, slices)
        # argsort(rand) 即随机置换；取前 n 项得到 [0, D) 内 n 个互异索引
        out[start:stop] = torch.rand(stop - start, D, generator=g).argsort(dim=1)[:, :n]

    new_indices = out.reshape(moved_shape).movedim(-1, dim_n).contiguous()
    new_indices = new_indices.to(dtype=indices.dtype, device=indices.device)
    return [data, new_indices, updates]
