# quant_matmul definition

The authoritative source is `third_party/cann-bench/tasks/level3/quant_matmul`.
For the original cases, `x1` and `x2` are signed int8 ND tensors with shapes
`[..., M, K]` and `[..., K, N]`. The accumulator is exact signed int32:

`acc[b,m,n] = sum_k int32(x1[b,m,k]) * int32(x2[b,k,n])`.

An int32 bias is added before scaling. A float16, bfloat16, or float32 bias is
added after scaling. Scale and offset have length one or N. Per-token scale has
length M and broadcasts over N:

`y = ((acc + int32_bias) * scale + offset) * pertoken_scale + float_bias`.

Missing optional terms are omitted. Output is rounded to IEEE float16 by
default or bfloat16 when requested. Leading batch dimensions are flattened;
the original suite contains rank-2 and rank-3 tensors. The authoritative 20
cases use int8 inputs and non-transposed x2; int4 and transpose are not part of
this task's declared API or case matrix.

FP16 uses round-to-nearest-even including subnormal, infinity and NaN handling.
BF16 uses round-to-nearest-even at bit 16. Verification follows the task's
MERE/MARE thresholds: `2^-10` for FP16 and `2^-7` for BF16, with MARE below ten
times the corresponding threshold.
