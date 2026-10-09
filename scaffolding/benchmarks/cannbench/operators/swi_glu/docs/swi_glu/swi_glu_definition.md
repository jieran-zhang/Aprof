# SwiGLU definition

For an input tensor and a normalized split axis `dim`, the axis must have an
even extent. Split it into equal contiguous logical halves `x0` and `x1`:

`output = (x0 / (1 + exp(-x0))) * x1`.

The output has the same rank and dtype as the input, with the split-axis extent
halved. Supported dtypes are float16, float32, and bfloat16. Half and bfloat16
values are promoted to float32 for computation and cast back for output. NaN
and infinity propagation follows the arithmetic formula. Negative dimensions
are normalized by adding the input rank.

Source of truth: `third_party/cann-bench/tasks/level1/swi_glu`.
