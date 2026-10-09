# ApplyRotaryPosEmb 算子 API 描述

## 1. 算子简介

对 query 和 key 执行旋转位置编码 (RoPE) 计算。

**主要应用场景**：
- 大语言模型（LLaMA、GPT-NeoX 等）中的位置编码
- Transformer 自注意力机制中 query 和 key 的位置信息注入
- 支持长序列外推的相对位置编码方案

**算子特征**：
- 难度等级：L2（FusedComposite）
- 四输入（query、key、cos、sin）双输出（query_out、key_out）
- 支持 BSND 和 BNSD 两种布局，以及 half 和 interleaved 两种旋转模式

## 2. 算子定义

### 数学公式

$$
rotate\_half(x) = concat(-x[head\_dim/2:], x[:head\_dim/2])
$$

$$
y = x \cdot cos + rotate\_half(x) \cdot sin
$$

其中：
- 在 half（连续半分）模式下，将最后一维分为前后两半进行旋转
- 在 interleaved（交错）模式下，取偶数/奇数索引位置交错旋转
- cos 和 sin 为预计算的位置编码，需要广播到与 query/key 匹配的 shape

## 3. 接口规范

### 算子原型

```python
cann_bench.apply_rotary_pos_emb(Tensor query, Tensor key, Tensor cos, Tensor sin, int layout=0, str rotaryMode="half") -> (Tensor query_out, Tensor key_out)
```

### 输入参数说明

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| query | Tensor | 必选 | 查询张量 |
| key | Tensor | 必选 | 键张量 |
| cos | Tensor | 必选 | 余弦位置编码 |
| sin | Tensor | 必选 | 正弦位置编码 |
| layout | int | 0 | 输入布局 (0: [B,S,N,D], 1: [B,N,S,D]) |
| rotaryMode | string | "half" | 旋转模式 ("half": 连续半分式，"interleaved": 交错式) |

### 输出

| 参数 | Shape | dtype | 描述 |
|------|-------|-------|------|
| query_out | 与输入 query 相同 | 与输入 query 相同 | 旋转后的查询张量 |
| key_out | 与输入 key 相同 | 与输入 key 相同 | 旋转后的键张量 |

### 数据类型

| 输入 dtype | 输出 dtype |
|-----------|-----------|
| float32 | float32 |
| float16 | float16 |
| bfloat16 | bfloat16 |

### 规则与约束

- query 和 key 的 shape 必须相同
- query/key 为 4D 张量：layout=0 时为 (batch_size, seq_len, num_heads, head_dim)，layout=1 时为 (batch_size, num_heads, seq_len, head_dim)
- cos/sin 为 (seq_len, head_dim/2) 或 (batch_size, seq_len, head_dim/2)
- head_dim 必须为偶数（需要分为两半进行旋转）
- 所有输入张量的 dtype 必须一致

### 支持范围

输入 tensor 各维度与参数的支持范围：

| 维度 / 参数 | 范围 | 备注 |
|---|---|---|
| `B`（batch_size） | 1 ~ 8192 | cases.csv 实测 3 ~ 4001 |
| `S`（seq_len） | 1 ~ 1048576 | cases.csv 实测 3 ~ 500001 |
| `N`（num_heads） | 1 ~ 128 | cases.csv 实测 3 ~ 31 |
| `D`（head_dim） | 2 ~ 2048 | cases.csv 实测 4 ~ 2048；必须为偶数（旋转需对半切分） |
| `cos`/`sin` shape | (S, D/2) 或 (B, S, D/2) | cases.csv 全部使用 2D 形式 (S, D/2) |
| `layout` | 0 / 1 | cases.csv 已覆盖两种取值；0=[B,S,N,D]，1=[B,N,S,D] |
| `rotaryMode` | `"half"` / `"interleaved"` | cases.csv 已覆盖两种模式 |

约束：`query` 与 `key` shape 必须相同；所有四个输入张量 dtype 一致；`D` 必须为偶数。

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
ApplyRotaryPosEmb 算子 Torch Golden 参考实现

对 query 和 key 执行旋转位置编码 (RoPE) 计算
公式:
    rotate_half(x) = concat(-x[head_dim/2:], x[:head_dim/2])
    y = (x * cos) + (rotate_half(x) * sin)

参考:
    - RoFormer: https://arxiv.org/abs/2104.09864
    - LLaMA: https://github.com/meta-llama/llama
    - HuggingFace transformers: https://huggingface.co/docs/transformers/internal/rope_utils
"""
def apply_rotary_pos_emb(
    query: torch.Tensor,
    key: torch.Tensor,
    cos: torch.Tensor,
    sin: torch.Tensor,
    layout: int = 0,
    rotaryMode: str = 'half'
) -> tuple[torch.Tensor, torch.Tensor]:
    """
    对 query 和 key 执行旋转位置编码 (RoPE) 计算

    Args:
        query: 查询张量，shape 为 (B, S, N, D) 或 (B, N, S, D)
        key: 键张量，shape 同 query
        cos: 余弦位置编码，shape 为 (S, D/2) 或 (B, S, D/2)
        sin: 正弦位置编码，shape 同 cos
        layout: 输入布局 (0: [B,S,N,D], 1: [B,N,S,D])
        rotaryMode: 旋转模式 ("half": 连续半分式，"interleaved": 交错式)

    Returns:
        query_out: 旋转后的查询张量
        key_out: 旋转后的键张量

    Examples:
        >>> B, S, N, D = 2, 4, 8, 128
        >>> query = torch.randn(B, S, N, D)
        >>> key = torch.randn(B, S, N, D)
        >>> cos = torch.randn(S, D // 2)
        >>> sin = torch.randn(S, D // 2)
        >>> q_out, k_out = apply_rotary_pos_emb(query, key, cos, sin)
    """

    # 检测输入 dtype
    input_dtype = query.dtype

    # FP16/BF16 输入需要升到 FP32 计算以保证精度
    # FP32/FP64 输入保持原样计算
    if input_dtype in (torch.float16, torch.bfloat16):
        compute_dtype = torch.float32
    else:
        compute_dtype = input_dtype

    # 转换到计算精度
    query_compute = query.to(compute_dtype)
    key_compute = key.to(compute_dtype)
    cos_compute = cos.to(compute_dtype)
    sin_compute = sin.to(compute_dtype)

    def rotate_half(x: torch.Tensor, mode: str) -> torch.Tensor:
        """
        旋转输入张量的一半维度

        Args:
            x: 输入张量
            mode: 旋转模式

        Returns:
            旋转后的张量
        """
        if mode == 'interleaved':
            # GPT-J 风格的交错式旋转
            x1 = x[..., ::2]       # 取偶数索引
            x2 = x[..., 1::2]      # 取奇数索引
            rotated = torch.stack([-x2, x1], dim=-1).flatten(-2)
        else:
            # LLaMA/Meta 风格的连续半分式旋转
            half_dim = x.shape[-1] // 2
            x1 = x[..., :half_dim]
            x2 = x[..., half_dim:]
            rotated = torch.cat([-x2, x1], dim=-1)
        return rotated

    def apply_rotary(x: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor, mode: str) -> torch.Tensor:
        """
        对单个张量应用 RoPE

        Args:
            x: 输入张量
            cos: 余弦编码
            sin: 正弦编码
            mode: 旋转模式

        Returns:
            旋转后的张量
        """
        # 调整 cos/sin 的 shape 以匹配输入
        # cos/sin: (S, D/2) 或 (B, S, D/2)
        # 需要扩展到 (B, S, N, D) 或 (B, N, S, D)

        if cos.dim() == 2:
            # cos: (S, D/2) -> 需要扩展到 (B, S, 1, D)
            cos = cos.unsqueeze(0).unsqueeze(2)  # (1, S, 1, D/2)
            sin = sin.unsqueeze(0).unsqueeze(2)
        elif cos.dim() == 3:
            # cos: (B, S, D/2) -> 需要扩展到 (B, S, 1, D)
            cos = cos.unsqueeze(2)  # (B, S, 1, D/2)
            sin = sin.unsqueeze(2)

        # 如果 layout=1 (B,N,S,D)，需要调整
        if layout == 1:
            cos = cos.transpose(1, 2)  # (B, 1, S, D/2)
            sin = sin.transpose(1, 2)

        # 重复 cos/sin 到完整的 head_dim
        # interleaved 模式需要 cos/sin 也是 interleaved 格式
        if mode == 'interleaved':
            # interleaved 格式: [c1, c1, c2, c2, ...]
            cos_full = torch.zeros_like(cos.repeat(1, 1, 1, 2))
            sin_full = torch.zeros_like(sin.repeat(1, 1, 1, 2))
            cos_full[..., ::2] = cos  # 偶数位置
            cos_full[..., 1::2] = cos  # 奇数位置
            sin_full[..., ::2] = sin
            sin_full[..., 1::2] = sin
            cos = cos_full
            sin = sin_full
        else:
            # half 格式: [c1, c2, ..., c1, c2, ...]
            cos = cos.repeat(1, 1, 1, 2)
            sin = sin.repeat(1, 1, 1, 2)

        # 应用 RoPE 公式
        x_rotate = rotate_half(x, mode)
        return (x * cos) + (x_rotate * sin)

    # 对 query 和 key 分别应用 RoPE
    query_out = apply_rotary(query_compute, cos_compute, sin_compute, rotaryMode)
    key_out = apply_rotary(key_compute, cos_compute, sin_compute, rotaryMode)

    # 转回原始 dtype
    if input_dtype in (torch.float16, torch.bfloat16):
        return query_out.to(input_dtype), key_out.to(input_dtype)
    return query_out, key_out
```

## 6. 额外信息

### 算子调用示例

```python
import torch
import cann_bench

B, S, N, D = 2, 128, 32, 128
query = torch.randn(B, S, N, D, dtype=torch.float16, device="npu")
key = torch.randn(B, S, N, D, dtype=torch.float16, device="npu")
cos = torch.randn(S, D // 2, dtype=torch.float16, device="npu")
sin = torch.randn(S, D // 2, dtype=torch.float16, device="npu")

# BSND 布局，half 模式
q_out, k_out = cann_bench.apply_rotary_pos_emb(query, key, cos, sin, layout=0, rotaryMode="half")

# BNSD 布局，interleaved 模式
query_bnsd = query.transpose(1, 2)
key_bnsd = key.transpose(1, 2)
q_out, k_out = cann_bench.apply_rotary_pos_emb(query_bnsd, key_bnsd, cos, sin, layout=1, rotaryMode="interleaved")
```
