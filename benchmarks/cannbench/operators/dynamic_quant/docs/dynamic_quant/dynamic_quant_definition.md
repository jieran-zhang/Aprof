# dynamic_quant definition

For every token (all leading dimensions flattened), let the last dimension be
the row `x`. The operator computes `abs_max = max(abs(float32(x)))`,
`scale = max(abs_max, 1e-12) / 127`, and
`y = clamp(round_to_even(float32(x) / scale), -128, 127)`.

Input rank is 2 through 8 and input dtype is float16 or bfloat16. `y` has the
input shape and int8 dtype. `scale` has shape `x.shape[:-1]` and float32 dtype.
NaN propagates through absmax and scale; Inf produces an infinite scale and a
NaN division result. Converting those NaN quantization values to int8 follows
the source torch golden. An all-zero row uses the positive `1e-12 / 127` scale
and quantizes to zero.
