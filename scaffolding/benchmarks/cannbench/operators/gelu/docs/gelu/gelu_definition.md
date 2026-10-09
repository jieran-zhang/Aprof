# Gelu definition

Source: `third_party/cann-bench/tasks/level1/gelu`.

- `none`: `y = 0.5*x*(1 + erf(x/sqrt(2)))`.
- `tanh`: `y = 0.5*x*(1 + tanh(sqrt(2/pi)*(x + 0.044715*x^3)))`.
- Input and output have identical shape and dtype.
- Supported dtypes are float16, float32, and bfloat16; approximate is `none` or `tanh`.
- NaN and infinity behavior follows the formula and PyTorch golden implementation.
