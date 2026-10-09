# MoeFinalizeRouting design

The host validates shape dependencies, allocates and copies the original tensors, constructs a
small tiling structure, and launches `moe_finalize_routing_kernel`. It never reads routing values
and never computes output data. No ACLNN or framework operator is used.

The device partitions the flattened `(N*H)` output into 128-element-aligned contiguous core ranges.
For every owned element it derives `(row,column)`, performs the mode-dependent mapping lookup,
checks drop and expert sentinels, gathers expanded and bias data, widens values, applies the scale,
and accumulates in increasing-k order. Thus routing, gather, scale, bias and both residual additions
are all device-side. Contiguous ownership prevents cache-line write races.

Each core uses a 1024-element FP32 UB buffer (4096 bytes). FP16/BF16 specializations additionally
use a 1024-element raw output buffer (2048 bytes), for 6144 live UB bytes. The final chunk is cast
with `CAST_NONE` for FP16 or round-to-nearest for BF16 and copied with byte-accurate DataCopyPad.
FP32 output copies the accumulation buffer directly. Scalar GM gathers are intentionally retained
for correctness-first delivery; profiling and optimization are outside the requested scope.
