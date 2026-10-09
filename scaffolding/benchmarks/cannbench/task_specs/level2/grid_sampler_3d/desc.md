# GridSampler3D 算子 API 描述

## 1. 算子简介

根据 grid 中坐标信息填充输出，实现 3D 空间的网格采样。

**主要应用场景**：
- 3D 医学图像处理中的空间变换与配准
- 3D 目标检测中的特征对齐与采样
- 体素数据的插值与重采样
- 空间变换网络（STN）中的可微分采样

**算子特征**：
- 难度等级：L2（FusedComposite）
- 双输入单输出，输入为 5D 张量 (N, C, D, H, W) 和采样网格 (N, D, H, W, 3)
- 支持多种插值模式和填充模式

## 2. 算子定义

### 数学公式

$$
y = \text{grid\_sample}(x, \text{grid})
$$

根据 grid 中指定的归一化坐标 $(\theta_d, \theta_h, \theta_w) \in [-1, 1]^3$，从输入张量 $x$ 中采样得到输出 $y$。

- **bilinear 模式**：在 5D 输入下实际为三线性插值（trilinear interpolation），根据 8 个相邻体素加权计算采样值
- **nearest 模式**：取最近邻体素的值
- **align_corners**：控制坐标映射方式；为 true 时 $-1$ 和 $1$ 映射到角点像素中心，为 false 时映射到角点像素边界

> **不支持 bicubic**：PyTorch 的 `grid_sample` 仅在 4D 输入下支持 bicubic，5D（3D 体数据）下传入 `bicubic` 会直接报错 `RuntimeError: bicubic interpolation only supports 4D input`。本算子仅支持 `bilinear` / `nearest`。

## 3. 接口规范

### 算子原型

```python
cann_bench.grid_sampler_3d(Tensor x, Tensor grid, str interpolation_mode="bilinear", str padding_mode="zeros", bool align_corners=false) -> Tensor y
```

### 输入参数说明

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| x | Tensor | 必选 | 输入张量，形状为 (N, C, D, H, W) |
| grid | Tensor | 必选 | 采样网格，形状为 (N, D_out, H_out, W_out, 3) |
| interpolation_mode | str | "bilinear" | 插值模式（'bilinear': 三线性，'nearest': 最近邻）。5D 输入下不支持 'bicubic' |
| padding_mode | str | "zeros" | 填充模式（'zeros': 零填充，'border': 边界填充，'reflection': 反射填充） |
| align_corners | bool | false | 是否对齐角点 |

### 输出

| 参数 | Shape | dtype | 描述 |
|------|-------|-------|------|
| y | (N, C, D_out, H_out, W_out) | 与输入 x 相同 | 输出张量，采样结果 |

### 数据类型

| 输入 dtype | 输出 dtype |
|-----------|-----------|
| float16 | float16 |
| float32 | float32 |

### 规则与约束

- 输入 x 必须为 5D 张量，形状为 (N, C, D, H, W)
- grid 必须为 5D 张量，形状为 (N, D_out, H_out, W_out, 3)，最后一维为 3 表示 (d, h, w) 坐标
- x 和 grid 的 batch 维度 N 必须一致
- x 和 grid 的 dtype 必须一致
- grid 中的坐标值通常归一化到 [-1, 1] 范围
- interpolation_mode 可选 'bilinear'、'nearest'（不支持 'bicubic'，5D 输入 PyTorch 限制）
- padding_mode 可选 'zeros'、'border'、'reflection'

### 支持范围

输入 tensor 各维度与参数的支持范围：

| 维度 / 参数 | 范围 | 备注 |
|---|---|---|
| `N`（batch） | 1 ~ 32 | cases.csv 实测 2 ~ 5；x 与 grid 的 N 必须一致 |
| `C`（输入通道） | 1 ~ 512 | cases.csv 实测 7 ~ 256 |
| `D`（输入深度） | 1 ~ 256 | cases.csv 实测 8 ~ 64 |
| `H`（输入高度） | 1 ~ 256 | cases.csv 实测 8 ~ 127 |
| `W`（输入宽度） | 1 ~ 4096 | cases.csv 实测 8 ~ 4001 |
| `D_out`, `H_out`, `W_out`（grid 空间） | 1 ~ 256 | cases.csv 实测 7 ~ 127 |
| `grid.shape[-1]` | = 3 | 最后一维固定为 3，表示 (d, h, w) 归一化坐标 |
| `interpolation_mode` | `bilinear` / `nearest` | cases.csv 全覆盖；5D 输入不支持 `bicubic`（PyTorch 限制） |
| `padding_mode` | `zeros` / `border` / `reflection` | cases.csv 全覆盖 |
| `align_corners` | `true` / `false` | cases.csv 全覆盖 |

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
```

## 6. 额外信息

### 算子调用示例

```python
import torch
import cann_bench

x = torch.randn(2, 32, 16, 64, 64, dtype=torch.float16, device="npu")
grid = torch.rand(2, 8, 8, 8, 3, dtype=torch.float16, device="npu") * 2 - 1  # 归一化到 [-1, 1]
y = cann_bench.grid_sampler_3d(x, grid, interpolation_mode="bilinear", padding_mode="zeros", align_corners=True)

# nearest 插值 + border 填充
y = cann_bench.grid_sampler_3d(x, grid, interpolation_mode="nearest", padding_mode="border", align_corners=False)
```
