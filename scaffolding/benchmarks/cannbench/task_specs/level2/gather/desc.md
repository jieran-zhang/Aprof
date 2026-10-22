# Gather 算子 API 描述

## 1. 算子简介

沿指定维度 `dim` 按 `index` 张量逐元素从输入 `x` 中提取值。语义与 [PyTorch `torch.gather`](https://pytorch.org/docs/stable/generated/torch.gather.html) 完全一致。

**主要应用场景**：
- 序列模型中按 token 位置抽取隐状态（如 `output_hidden_states.gather(1, lengths-1)` 取每条序列的最后一个 token）
- 强化学习中沿 action 维度抽取 Q 值（`q_values.gather(1, actions)`）
- TopK 后按 indices 取对应概率值
- 任何需要 "在 N-D 张量的某一维上按 index 逐位置取值" 的场景

> **注**：本算子是 PyTorch `torch.gather` 风格（输出与 index 同形、逐元素索引），**不是** TensorFlow `tf.gather` 风格（沿 axis 取整段行）。两者语义不同，请勿混淆。

**算子特征**：
- 难度等级：L2（IndexGather）
- 双输入（`x` 数据源 + `index` 索引），单输出 `y`
- 支持任意维度 N-D 张量，`x` 与 `index` 必须同维度数

## 2. 算子定义

### 数学公式

设输入张量 `x` 维度为 `n`，`dim = k`，则：

$$
y[i_0, i_1, \ldots, i_{n-1}] = x[i_0, \ldots, i_{k-1},\; index[i_0, i_1, \ldots, i_{n-1}],\; i_{k+1}, \ldots, i_{n-1}]
$$

即：除第 `k` 维由 `index` 给出实际下标外，其余维度保留索引位置不变。

**示例（2D，dim=0）**：`x` shape `[H, W]`，`index` shape `[H', W]`，输出 shape `[H', W]`，则 `y[i, j] = x[index[i, j], j]`。

## 3. 接口规范

### 算子原型

```python
cann_bench.gather(Tensor x, Tensor index, int dim=0) -> Tensor y
```

### 输入参数说明

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| x | Tensor | 必选 | 输入张量（数据源） |
| index | Tensor | 必选 | 索引张量（整型；与 `x` 维度数相同） |
| dim | int64 | 0 | gather 维度索引（torch.gather 的 dim 参数） |

### 输出

| 参数 | Shape | dtype | 描述 |
|------|-------|-------|------|
| y | **与 `index.shape` 完全一致** | 与输入 `x` 相同 | gather 结果 |

### 数据类型

| x dtype | index dtype | 输出 dtype |
|---------|------------|-----------|
| float16 | int8 / int32 / int64 | float16 |
| float32 | int8 / int32 / int64 | float32 |
| bfloat16 | int8 / int32 / int64 | bfloat16 |
| int8 | int8 / int32 / int64 | int8 |
| int32 | int8 / int32 / int64 | int32 |
| int64 | int8 / int32 / int64 | int64 |

> `index` 仅支持整数类型；按索引取值的语义下浮点 index 没有意义。

### 规则与约束

- `x` 与 `index` 必须维度数相同
- `index` 在 `dim` 维以外的每一维，size 不大于 `x` 对应维度；在 `dim` 维 size 由用户决定（即输出 shape）
- `index` 元素值必须在 `[0, x.shape[dim])` 范围内
- 输出 `y.shape == index.shape`；输出 dtype 与 `x` 一致

### 支持范围

输入 tensor 各维度与参数的支持范围：

| 维度 / 参数 | 范围 | 备注 |
|---|---|---|
| `x.ndim` / `index.ndim`（张量维度数） | 1 ~ 8 | cases.csv 实测 1 ~ 5；两者必须相等 |
| `x.shape[i]`（x 各维 size） | 1 ~ 2^20 | cases.csv 实测 2 ~ 1000003 |
| `x.shape[dim]`（gather 轴 size） | 1 ~ 2^20 | cases.csv 实测 7 ~ 1000003，决定 index 合法取值上界 |
| `x.numel`（x 总元素数） | 1 ~ 2^27 | cases.csv 实测约 1.0M ~ 128M（即 1,000,003 ~ 134,217,728） |
| `index.shape[i]`（index 各维 size，i ≠ dim） | 1 ~ x.shape[i] | cases.csv 实测 2 ~ 8193；约束 `index.shape[i] ≤ x.shape[i]` |
| `index.shape[dim]`（index 在 gather 轴 size） | 1 ~ 2^20 | cases.csv 实测 7 ~ 8192，由用户自由决定（即输出 shape） |
| `index.numel`（index 总元素数 = 输出元素数） | 1 ~ 2^26 | cases.csv 实测 1,000 ~ 67,108,864 |
| `dim`（gather 维度索引） | 0 ~ x.ndim-1 | cases.csv 实测 0 / 1 / 2 |
| `index` 元素值 | 0 ~ x.shape[dim]-1 | cases.csv 实测 0 ~ 1,000,002；越界为未定义行为 |
| `x` 元素值（浮点） | 全范围（含 ±inf / NaN） | cases.csv 实测覆盖 `[-0.1, 0.1]` ~ `[-65504, 65504]` 及 ±inf / NaN / 全零 |
| `x` 元素值（整型） | 各 dtype 完整表示范围 | cases.csv int8 测全范围 `[-128, 127]`；int32 取 `[-1000, 1000]`、int64 取 `[-100000, 100000]`（gather 只搬运数据不参与算术，cases 取小范围便于配套 index 设计；整型完整范围由 dtype 本身保证） |

约束：
- `x.ndim == index.ndim`，且 `0 ≤ dim < x.ndim`
- 除 `dim` 维外，`index.shape[i] ≤ x.shape[i]`
- `index` 元素值必须落在 `[0, x.shape[dim])`，否则结果未定义
- `index` 仅支持整型（int8 / int32 / int64）；`x` 与输出 dtype 一致

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
Gather算子Torch Golden参考实现（PyTorch torch.gather 语义）

沿 dim 维按 index 逐元素提取，输出 shape 与 index.shape 一致。
公式: output[i_0,...,i_{n-1}] = x[..., index[i_0,...,i_{n-1}], ...]
      （第 dim 维替换为 index 给出的下标，其余维度保留索引位置）
"""
def gather(
    x: torch.Tensor, index: torch.Tensor, dim: int = 0
) -> torch.Tensor:
    """
    沿 dim 维按 index 逐元素提取（torch.gather 语义）。

    Args:
        x: 输入张量（数据源）
        index: 索引张量，需与 x 维度数相同；除 dim 维外，shape 各维不大于 x
        dim: gather 维度索引，默认 0

    Returns:
        输出张量，shape 与 index 完全一致，dtype 与 x 一致
    """

    # 不做 .long()：PyTorch 2.1+ 的 torch.gather 已接受任意整型 idx；
    # 在 NPU 上 .long() 会触发冗余 Cast (int32→int64) + 后端再 Cast 回 int32。
    y = torch.gather(x, dim, index)
    return y
```

## 6. 额外信息

### 算子调用示例

```python
import torch
import cann_bench

# 2D dim=0：output[i, j] = x[index[i, j], j]
x = torch.randn(1024, 1024, dtype=torch.float32, device="npu")
index = torch.randint(0, 1024, (512, 1024), dtype=torch.int32, device="npu")
y = cann_bench.gather(x, index, dim=0)   # y.shape == (512, 1024)

# 3D dim=1：output[i, j, k] = x[i, index[i, j, k], k]
x = torch.randn(128, 128, 64, dtype=torch.float16, device="npu")
index = torch.randint(0, 128, (128, 64, 64), dtype=torch.int64, device="npu")
y = cann_bench.gather(x, index, dim=1)   # y.shape == (128, 64, 64)
```
