# Definition

The input is flattened and its distinct values are returned in ascending
numeric order. `y` retains the exact input bit pattern and dtype. When
`return_inverse=true`, int64 `inverse` has one element per flattened input and
obeys `x.flatten() == y[inverse]`. Integer, float16, bfloat16, and float32 are
bit-exact. The supplied cases contain infinities but no NaNs. Positive and
negative infinity remain distinct; equal finite values are merged.
