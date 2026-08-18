# Grouped Matmul Definition

For cumulative group boundaries `c[g]`, with `s[0]=0` and `s[g]=c[g-1]`:

`y[s[g]:c[g]] = x[s[g]:c[g]] @ W[g] + bias[g]`.

`x` is `[M,K]`. Weight is `[E,K,N]`, or `[E,N,K]` when `transpose_weight=true`.
Bias is optional `[E,N]`. Empty groups (`s[g]==c[g]`) perform no computation. Outputs are
reported as E group views for split items 0/1 and one `[M,N]` tensor for split items 2/3.
FP16, BF16 and FP32 inputs use FP32 accumulation semantics and cast back to the input dtype.
