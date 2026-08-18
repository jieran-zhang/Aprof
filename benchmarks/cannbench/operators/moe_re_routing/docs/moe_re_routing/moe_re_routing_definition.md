# moe_re_routing definition

## Semantics

The source is a sequence of token blocks laid out in `(rank, expert)` row-major
order. The output contains the same blocks in `(expert, rank)` order, preserving
the order inside each block. For count matrix `C[N,E]`:

`src(r,e) = sum(C[i,j] for (i,j) before (r,e) in rank-major order)`

`dst(r,e) = sum(C[i,j] for (j,i) before (e,r) in expert-major order)`

For every `0 <= k < C[r,e]`, output gather index `idx[dst(r,e)+k]` is
`src(r,e)+k`. Tokens and optional scales are gathered with `idx`.
`expert_token_num[e] = sum_r C[r,e]`.

## Inputs and outputs

- `tokens`: `(A,H)`, float16, bfloat16, or int8.
- `expert_token_num_per_rank`: `(N,E)`, int32 or int64; authoritative cases
  use positive counts whose sum is exactly `A`. Zero-count cells are also
  naturally safe (they emit no index and contribute zero to the count).
- optional `per_token_scales`: `(A)`, float32.
- attributes are restricted to `expert_token_num_type=1` and `idx_type=0`.
- outputs are `(A,H)` tokens, `(A)` float32 scales, `(A)` int32 gather index,
  and `(E)` expert counts in the input count dtype.

When scales are absent, the scales output is all zero as required by the golden.
All outputs are pure movement/integer reduction and therefore must be bitwise exact.

## Reference pseudocode

```text
dst = 0
for expert in 0..E-1:
  expert_count[expert] = 0
  for rank in 0..N-1:
    cell = rank*E + expert
    src = sum(counts[0:cell])
    for k in 0..counts[cell]-1:
      index[dst++] = src+k
    expert_count[expert] += counts[cell]
output_tokens = gather(tokens, index)
output_scales = gather(scales, index) if scales else zeros(A)
```
