# MhcSinkhorn definition

Source: `third_party/cann-bench/tasks/level3/mhc_sinkhorn`.

For each independent FP32 matrix `[N,N]`, the first iteration computes stable row
softmax (`exp(x-row_max)/row_sum + eps`) followed by column normalization. Each
remaining iteration applies row normalization then column normalization, with `eps`
added to every linear normalization denominator. Shapes are `[B,N,N]`, `B=1..16384`,
`N=2..16`, and `iter_step=1..40`.

NaN propagates through the matrix. A row containing both `+Inf` and `-Inf` produces
NaN at `Inf-Inf`, matching the torch golden. Output shape and dtype equal input.
