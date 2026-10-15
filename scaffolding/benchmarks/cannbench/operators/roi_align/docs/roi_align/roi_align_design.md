# ROIAlign design

The host validates shapes, computes output size, selects up to all vector cores, and
passes scalar parameters through tiling metadata. Each device worker owns a 64-byte
aligned flattened output interval. An output index decodes to `(roi,c,ph,pw)`; the
worker loads five box values, derives the sampling grid, performs four-point bilinear
interpolation for every sample, averages, and writes one result.

No UB buffers or DMA paths are used (`liveBytesPerElem=0`). GM values are scalar
loads/stores. FP16 bit conversion and round-to-nearest-even are implemented in device
helpers because dav-2201 scalar cast support is incomplete. All float/unsigned index
crossings use signed `int64_t`, and output dimensions also have precomputed float
fields in tiling.

Tiling:

```text
blockNum = min(vectorCores, max(1, ceil(outputNumel / 4096)))
alignment = 64 / itemBytes
blockLength = align_up(ceil(outputNumel / blockNum), alignment)
```

This scalar correctness-first design deliberately defers vectorization, UB tiling,
profiling, and performance optimization.
