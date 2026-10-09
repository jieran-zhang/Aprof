# MoeGatingTopKSoftmax definition

For every flattened token row `r`, compute `p[r,e] = exp(x[r,e]-max(x[r,:])) / sum_j exp(x[r,j]-max(x[r,:]))`, then return the `k` greatest probabilities in descending order. `y` retains the input dtype; expert indices and row indices are int32. A 2D or 3D input is flattened across all dimensions except the expert dimension.

`row_idx[r,j] = j * rows + r`, reshaped to `(..., k)`. When optional boolean `finished[r]` is true, every expert index for that row is the out-of-range sentinel `E`; probabilities and row indices are unchanged. Constraints are `1 <= E <= 2048`, `1 <= k <= min(E,1024)`, finite FP16/BF16/FP32 inputs, and ranks 2 or 3. TopK tie order is unspecified by the benchmark (`expert_idx` has `compare: false`), while values, sentinel semantics, and row indices remain checked.
