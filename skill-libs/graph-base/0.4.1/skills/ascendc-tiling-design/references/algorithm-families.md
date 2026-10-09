# Parallel algorithm families

Choose per workload group from mathematically valid alternatives before execution tuning. Record independent tasks, work per task, reuse, synchronization, communication/workspace bytes and precision. A task count greater than physical cores is legal scheduling, but launch/resource limits still apply.

| Family | Plan candidates | Selection and semantic constraints |
| --- | --- | --- |
| Elementwise/broadcast | Contiguous output partitions; row/axis partitions preserving broadcast reuse | Tiny work may favor few tasks; every output has one writer; account for strides and broadcast loads |
| RMSNorm/GroupNorm/Reduction | Whole-row ownership/full-load; row streaming/two-pass; split reduction and explicit merge | Whole rows avoid synchronization when enough rows exist. Few long rows may benefit from split reduction. Preserve accumulation dtype, epsilon location and reduction axes. Welford applies to variance semantics, not as an unconditional replacement for RMS calculations |
| MatMul/GMM | M/N tiles; work-balanced tile order; split-K/StreamK with partial accumulation | Prefer independent M/N tiles when plentiful; long K with too few M/N tasks may justify extra workspace/reduction. Preserve batch/group boundaries, transpose, bias and output accumulation dtype |
| Softmax/attention | Row-owned stable two-pass or online state; split KV with stable combination | Online combine uses rescaled maxima/sums/outputs; masks and causal/paged boundaries affect legal groups. Splits require explicit workspace ownership and final combination |
| Sort/TopK/Unique | Independent rows/local sorting; multi-level merge; radix/partition when semantics permit | Key dtype, stability, tie/index policy, NaN order and output cardinality are contract invariants. Merge levels add traffic and synchronization. Never infer sortedness from benchmark inputs |
| Segment/scatter | Output segment ownership; input partitions plus atomics or staged reduction | Collisions and skew affect contention; deterministic outputs may exclude atomics. Workspace initialization and completion barriers must be explicit |
| Resample/transpose/gather | Output ownership with contiguous stores; input-cache/block reuse; architecture-supported DMA layout transforms | Preserve coordinate rounding, padding/bounds and repeated-index behavior; an NDDMA path needs verified target/API support |

Architecture modifies legality and cost, not operator semantics. On 2201 plan AIC and AIV tasks against measured visible resources. A3 shares that ISA but may have different device/die/topology and SKU resources; do not multiply single-device core counts by package dies. On 3510 consider RegBase fusion and SIMT for irregular indexing, plus new CV data paths, but account for register/UB/DCache and SDK support before selecting them.

Algorithm changes need independent correctness and paired measurement before being kept. Freeze the chosen plan and its content hash before tile/buffer/pipeline candidates. Rejected algorithm plans remain negative trace evidence; do not hide them inside execution-only records.
