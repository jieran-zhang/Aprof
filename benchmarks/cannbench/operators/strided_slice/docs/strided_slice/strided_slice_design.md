# StridedSlice design

## Strategy

The host converts all masks and slice parameters into compact affine metadata:
`sourceBase`, `outputShape[8]`, and `sourceStep[8]`. The device kernel partitions
the flattened output among vector cores. Each core reconstructs output coordinates,
computes the corresponding flattened input offset, and copies one raw storage word.

Dispatch is by storage width (`uint8_t`, `uint16_t`, `uint32_t`, or `uint64_t`),
which makes float, bfloat, integer, NaN, infinity, and signed-zero values bit exact.

## Tiling

```text
usefulCores = ceil(outputNumel / 4096)
blockNum = min(vectorCoreCount, max(1, usefulCores))
rawBlockLength = ceil(outputNumel / blockNum)
blockLength = align_up(rawBlockLength, 64 / itemBytes)
```

Core `b` owns `[b * blockLength, min((b+1) * blockLength, outputNumel))`.
The dtype-dependent alignment prevents adjacent vector cores from issuing scalar
stores into the same 64-byte GM cache line.
The 4096-element threshold avoids launching adjacent empty/tiny cores while retaining
multicore execution for large cases.

## Memory and instruction sequence

No UB buffers and no UB-to-UB DMA path are used (`liveBytesPerElem = 0`). Each output
element performs rank-many integer div/mod operations, one GM scalar load, and one GM
scalar store. There is no Cast chain and no arithmetic conversion. Scalar GM access
also removes 32-byte DMA tail-alignment hazards, which is appropriate for this
correctness-first Flash implementation.

## Limits

- input/output rank metadata: at most 8
- one ellipsis bit
- nonzero stride
- the supplied 20-case matrix uses positive strides
- performance optimization and profiling are deliberately deferred
