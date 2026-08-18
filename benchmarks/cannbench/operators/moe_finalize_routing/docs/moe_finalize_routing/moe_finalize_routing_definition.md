# MoeFinalizeRouting definition

Let `N` be the number of source rows, `H` the hidden size, and `K` the number of routed experts.
For output element `(i,j)`, initialize a FP32 accumulator from the present residual tensors, then
visit `k=0..K-1` in order:

```text
p = k*N+i                 when drop_pad_mode is 0 or 1
p = i*K+k                 when drop_pad_mode is 2 or 3
r = expanded_src_to_dst_row[p]
if r == -1: continue
term = expanded_permuted_rows.reshape(-1,H)[r,j]
if bias is present and 0 <= expert_for_source_row[i,k] < E:
    term += bias[expert_for_source_row[i,k],j]
acc += (scales[i,k] if present else 1) * term
```

The output has shape `(N,H)` and the same dtype as `expanded_permuted_rows`. FP16 and BF16 inputs
are widened to FP32 for residual addition, bias addition, scaling and ordered accumulation, then
converted once to the output dtype. Case 12 permits FP32 scales with BF16 data.

Modes 0/2 use a flattened `(N*K,H)` expanded tensor. Modes 1/3 flatten `(E,C,H)` to `(E*C,H)`.
An index of `-1` drops the whole routed contribution, including bias. Invalid expert sentinels add
no bias. Optional inputs obey: skip2 requires skip1; bias requires expert ids; absent scales implies
`K=1`. The original matrix covers all four modes, K 1–16, H 32–2048, FP16/FP32/BF16, optional
residuals/bias/scales, mixed BF16/FP32 scales, prime shapes, zeros, and a 262144-row expanded input.
