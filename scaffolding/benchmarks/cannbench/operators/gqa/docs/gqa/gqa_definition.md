# GQA definition

Inputs are `Q[B,S,Nq,D]`, `K/V[B,Skv,Nkv,D]`, with `Nq % Nkv == 0` and
`G=Nq/Nkv`. Query head `h` uses KV head `floor(h/G)`. For every batch/query
head, the result is `softmax(Q K^T * scale) V`; non-positive scale selects
`1/sqrt(D)`. Causal masking is right-bottom aligned and retains
`j <= i + Skv - S`. Inputs and output are FP16 or BF16.

The authoritative cases are read directly from
`third_party/cann-bench/tasks/level4/gqa/cases.yaml` and cover GQA, MQA, MHA,
cross-attention, decode/MTP, long prefill, D128/D256, both dtypes, and explicit
scale.
