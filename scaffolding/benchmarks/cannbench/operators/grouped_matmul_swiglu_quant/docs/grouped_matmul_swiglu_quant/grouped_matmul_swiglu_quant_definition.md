# Definition

For cumulative group boundaries `end[g]`, rows `[end[g-1], end[g])` compute `acc = x @ weight[g]` in int32. Dequantization is `z[i,j] = float(acc[i,j]) * x_scale[i] * weight_scale[g,j]`. Split `z` equally into `left,right`, compute `act = silu(left) * right`, then per row set `y_scale=max(abs(act))/127` (clamped to the smallest positive float32) and `y=clamp(round_even(act/y_scale),-128,127)` as int8. Repeated boundaries represent empty groups.
