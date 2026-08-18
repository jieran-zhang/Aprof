# arg_max definition

`arg_max(input, dim, keepdim=False)` returns an `int64` tensor containing the
index of the maximum element in every slice along `dim`. Negative dimensions
are normalized by adding the input rank. With `keepdim=true`, the reduced
dimension remains with extent one; otherwise it is removed.

The supported input dtypes are float16, float32, bfloat16, int32, and int64.
Comparison is strict, so equal maxima retain the lowest index. Floating-point
NaNs follow `torch.argmax`: the first NaN in a slice is selected, and later
values cannot replace it.
