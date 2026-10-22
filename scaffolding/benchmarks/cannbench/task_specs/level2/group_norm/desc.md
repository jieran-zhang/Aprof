# GroupNorm 算子 API 描述

## 1. 算子简介

计算分组归一化。

**主要应用场景**：
- 计算机视觉模型中的归一化层（ResNeXt、EfficientNet 等）
- 当 batch size 较小时替代 BatchNorm（GroupNorm 不依赖 batch 统计量）
- 生成模型（GAN、Diffusion Model）中的归一化层

**算子特征**：
- 难度等级：L2（Normalization）
- 三输入（x、gamma、beta）单输出，涉及分组、均值、方差、归一化、仿射变换等多步计算
- 将通道维度分为 num_groups 组，每组内独立计算均值和方差

## 2. 算子定义

### 数学公式

**基本公式**：

$$
y = \frac{x - \mu}{\sqrt{\sigma^2 + \epsilon}} \cdot \gamma + \beta
$$

其中均值和方差按组计算：

$$
\mu_g = \frac{1}{|S_g|}\sum_{i \in S_g} x_i, \quad \sigma_g^2 = \frac{1}{|S_g|}\sum_{i \in S_g}(x_i - \mu_g)^2
$$

其中：
- `S_g` 为第 g 组所包含的元素集合（同组通道的所有空间位置）
- `num_groups` 组数，C 必须能被 num_groups 整除
- `gamma` 和 `beta` 分别为逐通道的缩放和偏置参数，shape 为 (C,)
- `epsilon` 为数值稳定性参数，防止除零

## 3. 接口规范

### 算子原型

```python
cann_bench.group_norm(Tensor x, Tensor gamma, Tensor beta, int num_groups, float epsilon) -> Tensor y
```

### 输入参数说明

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| x | Tensor | 必选 | 输入张量，shape 为 (N, C, ...) |
| gamma | Tensor | 必选 | 缩放参数，shape 为 (C,) |
| beta | Tensor | 必选 | 偏置参数，shape 为 (C,) |
| num_groups | int | 必选 | 分组数 |
| epsilon | float | 1e-5 | 数值稳定性参数 |

### 输出

| 参数 | Shape | dtype | 描述 |
|------|-------|-------|------|
| y | 与输入 x 相同 | 与输入 x 相同 | 分组归一化后的张量 |

### 数据类型

| x dtype | gamma dtype | beta dtype | 输出 dtype |
|---------|------------|-----------|-----------|
| float16 | float16 | float16 | float16 |
| float32 | float32 | float32 | float32 |
| bfloat16 | bfloat16 | bfloat16 | bfloat16 |

### 规则与约束

- x 的 shape 为 (N, C, ...) 或 (N, C)，其中 N 为 batch size，C 为通道数
- C 必须能被 num_groups 整除
- gamma 和 beta 的 shape 均为 (C,)，dtype 需与 x 一致
- num_groups=1 时等价于 LayerNorm（对所有通道归一化）
- num_groups=C 时等价于 InstanceNorm（每个通道独立归一化）
- 需注意数值稳定性：当组内方差极小时，归一化结果可能不稳定

### 支持范围

输入 tensor 各维度与参数的支持范围：

| 维度 / 参数 | 范围 | 备注 |
|---|---|---|
| `N`（batch） | 1 ~ 2048 | cases.csv 实测 1 ~ 1023 |
| `C`（通道） | 1 ~ 1024 | cases.csv 实测 31 ~ 513；必须能被 `num_groups` 整除 |
| 空间维度（`H`, `W`, ...） | 1 ~ 512 | cases.csv 实测 5 ~ 480；支持 2D `(N, C)`、3D `(N, C, L)`、4D `(N, C, H, W)`、5D `(N, C, D, H, W)` 等 |
| `num_groups` | 1 ~ 64 | cases.csv 实测 1 ~ 32；必须能整除 `C`；=1 等价 LayerNorm，=C 等价 InstanceNorm |
| `epsilon` | 1e-8 ~ 1 | cases.csv 实测 1e-8 ~ 1e-3；必须 > 0 |

约束：`C % num_groups == 0`；`gamma`、`beta` 的 shape 均为 `(C,)` 且 dtype 与 `x` 一致。

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
GroupNorm 算子 Torch Golden 参考实现

计算分组归一化

公式:
    y = (x - mean) / sqrt(var + eps) * gamma + beta

参考 PyTorch API: torch.nn.functional.group_norm
    https://pytorch.org/docs/stable/generated/torch.nn.functional.group_norm.html

Parameters:
    - x: (N, C, ...) 输入张量，N=batch size, C=通道数
    - gamma: (C,) 缩放参数
    - beta: (C,) 偏置参数
    - num_groups: int - 分组数，C 必须能被 num_groups 整除
    - epsilon: float, 默认 1e-5 - 数值稳定性参数
"""


def group_norm(
    x: torch.Tensor,
    gamma: torch.Tensor,
    beta: torch.Tensor,
    num_groups: int,
    epsilon: float = 1e-5
) -> torch.Tensor:
    """
    计算分组归一化

    Args:
        x: 输入张量，shape (N, C, ...) 或 (N, C)
           N = batch size, C = 通道数
           C 必须能被 num_groups 整除
        gamma: 缩放参数，shape (C,)
        beta: 偏置参数，shape (C,)
        num_groups: 分组数，将 C 个通道分为 num_groups 组
                    每组内独立计算均值和方差
        epsilon: 数值稳定性参数，防止除零
                 默认值 1e-5

    Returns:
        分组归一化后的张量，shape 与输入相同

    Examples:
        >>> x = torch.randn(8, 32, 64, 64)
        >>> gamma = torch.ones(32)
        >>> beta = torch.zeros(32)
        >>> y = group_norm(x, gamma, beta, num_groups=8, epsilon=1e-5)
    """
    y = torch.nn.functional.group_norm(
        input=x,
        num_groups=num_groups,
        weight=gamma,
        bias=beta,
        eps=epsilon
    )

    return y
```

## 6. 额外信息

### 算子调用示例

```python
import torch
import cann_bench

x = torch.randn(8, 32, 64, 64, dtype=torch.float32, device="npu")
gamma = torch.ones(32, dtype=torch.float32, device="npu")
beta = torch.zeros(32, dtype=torch.float32, device="npu")

y = cann_bench.group_norm(x, gamma, beta, num_groups=8, epsilon=1e-5)
y = cann_bench.group_norm(x, gamma, beta, num_groups=4, epsilon=1e-5)
y = cann_bench.group_norm(x, gamma, beta, num_groups=32, epsilon=1e-5)
```
