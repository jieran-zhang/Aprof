# AddRmsNormDynamicQuant definition

## Source and interface

The authority is `third_party/cann-bench/tasks/level3/add_rms_norm_dynamic_quant`.
Inputs are rank-2 `x1, x2` with shape `[M,N]` and `gamma` with shape `[N]`.
All three inputs share FP16 or BF16 dtype. `epsilon` is positive.

The three outputs are `y: int8[M,N]`, `xOut: input_dtype[M,N]`, and
`scaleOut: float32[M]`.

## Semantics

All arithmetic before the explicitly stated casts is FP32:

```
s = float(x1) + float(x2)
xOut = cast_input_dtype(s)
inv_rms = 1 / sqrt(mean(s * s, last_dim) + epsilon)
z = s * inv_rms * float(gamma)
scaleOut = clamp(max(abs(z), last_dim), min=1e-12) / 127
y = int8(clamp(round_to_nearest_even(z / scaleOut), -128, 127))
```

The scale is a dequantization scale. NaN and infinity behavior follows the
PyTorch golden. The clamp makes an all-zero row yield finite scale and zero y.

## Constraints and cases

The benchmark covers exactly the 20 source cases: `M=256..524288`,
`N=128..16384`, epsilon `1e-6..1e-3`, FP16/BF16, prime tail dimensions,
zero, NaN, infinity, and large finite ranges. Shape and dtype mismatches are
rejected by the host-side benchmark contract; computation is never performed
by the host.
