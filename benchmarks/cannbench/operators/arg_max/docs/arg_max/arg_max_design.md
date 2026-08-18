# arg_max flash design

The host normalizes the axis and derives three contiguous-layout factors:
`outer`, `reduce`, and `inner`. There are `outer * inner` independent output
slices. AI cores divide those output positions evenly, with each core boundary
aligned to eight int64 outputs (64 bytes) so scalar result stores cannot race
on a shared GM cache line.

For `inner == 1`, each contiguous reduction is copied to UB in 8192-element
tiles and reduced with vector `ReduceMax`; tile maxima and first indices are
combined with strict greater-than. A vector NaN mask is scanned before each
tile reduction so the first NaN has torch.argmax priority.

For strided axes, each core processes up to 512 adjacent inner positions at a
time. It copies one contiguous plane per reduction index, compares that plane
against the UB best-value vector, and selects both value and index with the
same packed mask. The update predicate is `greater || (candidate_nan &&
!best_nan)`, which preserves the first finite tie and the first NaN.

All comparisons use float32 after lossless conversion for the tested domains:
float16/bfloat16 widen directly, while int32 and int64 source cases are within
the exactly representable range specified by `cases.csv`. The output is always
contiguous int64. `keepdim` changes only the logical output shape, not its flat
layout.

The approach is selected for correctness and rapid case coverage. Performance
optimization and profiling are outside the requested flash acceptance gate.
