# UnsortedSegmentSum 算子 API 描述

## 1. 算子简介

沿 segment_ids 指定的段对数据进行求和。

**主要应用场景**：
- 图神经网络中的节点特征聚合（按邻居分段求和）
- 点云处理中的体素化聚合
- 稀疏特征的按组求和与池化
- 嵌入表梯度的按 ID 累加

**算子特征**：
- 难度等级：L2（ScatterUpdate）
- 双输入单输出，根据 segment_ids 将 data 中的元素按段分组求和

## 2. 算子定义

### 数学公式

$$
y[i] = \sum_{j: \text{segment\_ids}[j] = i} \text{data}[j]
$$

对于每个段 $i \in [0, \text{num\_segments})$，将所有 segment_ids 等于 $i$ 的 data 元素在第 0 维上求和。若某段没有对应的元素，则输出为零。

## 3. 接口规范

### 算子原型

```python
cann_bench.unsorted_segment_sum(Tensor data, Tensor segment_ids, int num_segments) -> Tensor y
```

### 输入参数说明

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| data | Tensor | 必选 | 输入数据张量 |
| segment_ids | Tensor | 必选 | 段 ID 张量，值在 [0, num_segments) 范围内 |
| num_segments | int | 必选 | 段数量 |

### 输出

| 参数 | Shape | dtype | 描述 |
|------|-------|-------|------|
| y | (num_segments, *data.shape[1:]) | 与 data 相同 | 输出张量，段求和结果 |

### 数据类型

| data dtype | segment_ids dtype | 输出 dtype |
|-----------|------------------|-----------|
| float16 | int32 / int64 | float16 |
| bfloat16 | int32 / int64 | bfloat16 |
| float32 | int32 / int64 | float32 |
| int32 | int32 / int64 | int32 |
| int64 | int32 / int64 | int64 |

### 规则与约束

- segment_ids 必须为 1D 张量，长度等于 data 的第 0 维大小，即 `segment_ids.shape == (data.shape[0],)`
- segment_ids 中的值必须在 `[0, num_segments)` 范围内
- segment_ids 的 dtype 必须为 int32 或 int64
- 输出的第 0 维大小为 num_segments，其余维度与 data 的尾部维度一致：`y.shape == (num_segments, *data.shape[1:])`
- 输出 dtype 与 data 一致
- 若某个段 ID 在 segment_ids 中未出现，对应输出段为全零
- num_segments 必须为正整数

### 支持范围

输入 tensor 各维度与参数的支持范围：

| 维度 / 参数 | 范围 | 备注 |
|---|---|---|
| `data.rank` | 1 ~ 8 | cases.csv 实测 1 ~ 5 |
| `data.shape[0]`（段轴长度，N） | 1 ~ 4194304 | cases.csv 实测 2 ~ 2097152；约束 `segment_ids.shape[0] == data.shape[0]` |
| `data.shape[1:]`（每个尾部维度） | 1 ~ 16384 | cases.csv 实测 7 ~ 8193 |
| `segment_ids.rank` | 1 | 固定为 1D，长度等于 `data.shape[0]` |
| `segment_ids.shape[0]` | 1 ~ 4194304 | cases.csv 实测 2 ~ 2097152；与 `data.shape[0]` 相等 |
| `num_segments`（attr） | 1 ~ 32768 | cases.csv 实测 1 ~ 16384；约束 `segment_ids ∈ [0, num_segments)` |

约束：
- shape 关系：`segment_ids.shape == (data.shape[0],)`（必须为 1D 且长度等于 data 第 0 维）；`y.shape == (num_segments, *data.shape[1:])`。
- dtype 关系：`y.dtype == data.dtype`（输出沿 data dtype）；`segment_ids.dtype ∈ {int32, int64}`，与 data dtype 解耦。
- 值域约束：`segment_ids` 中每个元素 `v` 必须满足 `0 ≤ v < num_segments`；越界元素的行为未定义。
- 稀疏段：未在 `segment_ids` 中出现的段 ID 对应输出行为全零（zero-fill）。
- attr 约束：`num_segments` 必须为正整数。
- 数值精度：浮点 dtype 下内部使用 fp32 累加以减小累积误差（参见 §5 golden 代码）；NaN/Inf 在求和后可能传播为输出 NaN/Inf。

## 4. 精度要求

采用[生态算子精度标准](https://gitcode.com/cann/opbase/blob/master/docs/zh/ops_precision_standard/experimental_standard.md)进行验证。

**误差指标**：

1. 平均相对误差（MERE）：采样点中相对误差平均值

   $$
   \text{MERE} = \text{avg}(\frac{\text{abs}(actual - golden)}{\text{abs}(golden)+\text{1e-7}})
   $$

2. 最大相对误差（MARE）：采样点中相对误差最大值

   $$
   \text{MARE} = \max(\frac{\text{abs}(actual - golden)}{\text{abs}(golden)+\text{1e-7}})
   $$

**通过标准**：

| 数据类型 | FLOAT16 | BFLOAT16 | FLOAT32 | HiFLOAT32 | FLOAT8 E4M3 | FLOAT8 E5M2 |
|----------|---------|----------|---------|-----------|-------------|-------------|
| **通过阈值(Threshold)** | 2^-10 | 2^-7 | 2^-13 | 2^-11 | 2^-3 | 2^-2 |

当平均相对误差 MERE < Threshold，最大相对误差 MARE < 10 * Threshold 时判定为通过。


## 5. 标准 Golden 代码

```python
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
    
    对于 FP16/BF16 输入，使用 FP32 进行内部累加以保证精度，
    其他类型保持原样
    
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
```

## 6. 额外信息

### 算子调用示例

```python
import torch
import cann_bench

data = torch.randn(1048576, dtype=torch.float16, device="npu")
segment_ids = torch.randint(0, 1024, (1048576,), dtype=torch.int32, device="npu")
y = cann_bench.unsorted_segment_sum(data, segment_ids, num_segments=1024)

# 2D 数据按段求和
data = torch.randn(1024, 1024, dtype=torch.float32, device="npu")
segment_ids = torch.randint(0, 256, (1024,), dtype=torch.int32, device="npu")
y = cann_bench.unsorted_segment_sum(data, segment_ids, num_segments=256)

# int32 数据类型
data = torch.randint(-1000, 1000, (2048, 512), dtype=torch.int32, device="npu")
segment_ids = torch.randint(0, 512, (2048,), dtype=torch.int32, device="npu")
y = cann_bench.unsorted_segment_sum(data, segment_ids, num_segments=512)
```
