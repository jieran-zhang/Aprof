# Exp definition

For `base <= 0`, `y = exp(scale*x + shift)`. For `base > 0`,
`y = exp((scale*x + shift)*ln(base))`. Shape and dtype are preserved. Supported
dtypes are float16, float32, and bfloat16; half formats use FP32 intermediate
calculation. NaN and infinity follow IEEE propagation.
