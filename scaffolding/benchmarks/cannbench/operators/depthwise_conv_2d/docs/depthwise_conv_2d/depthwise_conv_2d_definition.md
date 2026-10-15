# Definition

For `x[N,C,H,W]`, `weight[C,KH,KW]`, and `bias[C]`, depthwise convolution is

`y[n,c,oh,ow] = bias[c] + sum(kh,kw, x[n,c,oh*SH+kh*DH-PH,ow*SW+kw*DW-PW] * weight[c,kh,kw])`,

where out-of-range input positions are zero. The defining constraints are
`groups == C`, one output channel per input channel, and no cross-channel sum.
The output dimensions use the standard floor convolution formula from the
task specification.

The three inputs have one common dtype: float16, float32, or bfloat16. The
kernel widens 16-bit operands and bias to float32, performs the ordered
`kh`-then-`kw` accumulation in float32, and converts once to the output dtype.
Float32 uses float32 multiply/add accumulation. IEEE NaN and Inf naturally
propagate through multiplication and addition. Kernel sizes 1, 3, and 5,
stride 1 or 2, padding 0 through 2, and dilation 1 through 3 cover all original
cases; the implementation uses runtime dimensions and attributes.

Reference pseudocode:

```text
for n, c, oh, ow:
    acc = float32(bias[c])
    for kh, kw:
        ih = oh*SH + kh*DH - PH
        iw = ow*SW + kw*DW - PW
        if 0 <= ih < H and 0 <= iw < W:
            acc += float32(x[n,c,ih,iw]) * float32(weight[c,kh,kw])
    y[n,c,oh,ow] = cast_to_output_dtype(acc)
```
