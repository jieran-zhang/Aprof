# TopK design

The tensor is represented as `[outer, axis, inner]`; each `(outer, inner)` pair is one independent
sequence. Cores receive cache-line-safe sequence ranges. Non-last axes with unaligned row strides
are partitioned by complete outer slabs; aligned rows retain inner-lane parallelism.

Each sequence maintains a UB binary heap of at most 2048 values plus int64 indices. For largest TopK,
the root is the smallest retained value; for smallest TopK, it is the largest. Scanning costs
`O(axis log k)`. Repeated heap removal writes from output position `k-1` backwards, yielding descending
largest or ascending smallest output. FP16 and BF16 comparisons widen in scalar helper functions;
stored values remain bit-exact. NaN is ordered above numeric values, matching the covered PyTorch
largest case. UB live storage is `k * (sizeof(T)+8)`, at most 32 KiB for int64 values.
