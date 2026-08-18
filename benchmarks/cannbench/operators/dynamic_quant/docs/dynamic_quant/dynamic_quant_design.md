# dynamic_quant flash design

One vector core handles whole tokens. Each row is at most 16384 elements, so a
complete raw row (32 KiB), float32 work row (64 KiB), int8 output row (16 KiB),
reduction workspace, scalar result, and packed NaN mask fit in UB.

The first pass widens input to float32, explicitly detects any NaN with a
packed comparison mask, then computes `Abs` and `ReduceMax`. The scalar result
is clamped to `1e-12` only for finite/zero rows and written as float32 scale.
The second pass restores signed float32 input and calls the documented
`AscendQuant<float>` path with scalar `127 / clamped_absmax`, zero offset, and
an aligned count. This provides half-to-even and saturating int8 conversion;
the source task explicitly permits an absolute int8 difference of one.

Core row ranges are aligned so both int8 row output boundaries and float32
scale boundaries fall on 64-byte addresses. DMA tails use byte-counted
`DataCopyPad`. The design prioritizes complete correctness coverage and simple
direct invocation; profiling and further optimization are intentionally out of
scope.
