# MHA definition

Inputs are Q `[B,S,N,D]`, K/V `[B,Skv,N,D]` in FP16 or BF16. The output has Q's shape and dtype:

`Y[b,s,n,:] = softmax_j(scale * dot(Q[b,s,n,:], K[b,j,n,:])) @ V[b,:,n,:]`.

`scaleValue <= 0` selects `1/sqrt(D)`. For causal execution, positions
`j > s + (Skv-S)` are masked, giving the required right-aligned causal
triangle. MHA requires equal Q/K/V head counts and causal cases require
`S <= Skv`.

The reference is the authoritative level4 `golden.py`. Validation uses its
FP16/BF16 operation sequence and checks special values strictly. One-local-ULP
and the standard PV forward bound `eps * sum(abs(weight * V))` are recorded
separately so near-zero relative error does not misclassify numerically
equivalent device accumulation.
