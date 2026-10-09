# gather 定义

本算子严格采用 PyTorch `torch.gather` 语义。对 rank 为 `n` 的 `x` 和同 rank 的
`index`，沿 `dim=k`：

`y[i0,...,in-1] = x[i0,...,i(k-1), index[i0,...,in-1], i(k+1),...,in-1]`。

输出 shape 等于 `index.shape`，输出 dtype 等于 `x.dtype`。`x` 支持 float16、
float32、bfloat16、int8、int32、int64；index 支持 int8、int32、int64。
除 gather 维外，`index.shape[d] <= x.shape[d]`。

接口只有 `dim`，没有 `batch_dims`；因此不存在 TensorFlow gather 的批维扩展，等价于
不启用额外 batch_dims。规格要求 `0 <= dim < rank`，index 值必须位于
`[0, x.shape[dim])`。负 index、越界 index、负 dim 均拒绝，不做 Python 风格回绕。
