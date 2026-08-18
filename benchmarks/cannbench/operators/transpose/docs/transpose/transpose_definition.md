# Transpose definition

For rank `r`, input shape `S`, and a permutation `P`, output shape is `O[d] = S[P[d]]` and
`y[o0,...,o(r-1)] = x[i0,...,i(r-1)]`, where `i[P[d]] = od`.

The operation is a bit-preserving layout transform. Supported cases use rank 2–5 and float16,
bfloat16, float32, int8, int16, int32, or int64. NaN and infinity payload bits are copied without
arithmetic. `perm` must contain every dimension exactly once.

CPU reference: `numpy.asarray(x).transpose(perm)`.
