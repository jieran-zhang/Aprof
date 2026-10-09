# Definition

For `data.shape = (N, *tail)`, one-dimensional `segment_ids` of length `N`, and
positive `num_segments`, the output shape is `(num_segments, *tail)` and
`y[s, ...] = sum(data[n, ...] for n where segment_ids[n] == s)`. Missing segments
are zero. IDs are int32 or int64 and are in range. Output dtype equals data dtype.
FP16 and BF16 are accumulated in FP32 and cast once; FP32, int32, and int64 retain
their dtype. Input-order accumulation defines NaN/Inf and rounding behavior.
