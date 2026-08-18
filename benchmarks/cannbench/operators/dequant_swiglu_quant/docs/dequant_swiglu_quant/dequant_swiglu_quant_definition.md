# Definition

For `x[rows,2H]`, int32 inputs are converted elementwise as `d=x.float()*weight_scale*activation_scale[:,None]`; fp16/bf16 inputs are converted directly to float32. Split `d=(A,B)`. The fused activation is `silu(A)*B` when `activate_left`, otherwise `silu(B)*A`. Optional `quant_scale[1,H]` is broadcast over rows. For each row, `scale=max(abs(out))/127`, clamped to at least `1e-12`, and `y=clamp(round(out/scale),-128,127).int8` using round-to-nearest-even. Outputs are `y[rows,H]` int8 and `scale[rows]` float32.

The accepted dtypes, optional argument rules, shapes, broadcast semantics, and 20-case matrix are exactly those in `third_party/cann-bench/tasks/level3/dequant_swiglu_quant`.
