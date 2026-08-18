# MhcSinkhorn design

The device kernel assigns contiguous groups of complete matrices to vector cores.
For each matrix it DMA-copies compact GM data to a raw UB buffer, repacks rows into
a compute UB with an 8-float (32-byte) aligned stride, and performs stable softmax,
all reductions/divisions, and every Sinkhorn iteration locally. It then compacts the
matrix into raw UB and DMA-writes the result. Host code never evaluates any output.

UB buffers: raw matrix 256 FP32 values and aligned compute matrix 256 FP32 values;
maximum live storage is 2048 bytes per core. Matrix partitions are aligned so core
output ranges start on 64-byte GM ownership boundaries. `AscendC::Exp` is used for
each aligned row; reductions deliberately use FP32 scalar order.

This Flash pass omits profiling, vectorized normalization, and performance tuning.
