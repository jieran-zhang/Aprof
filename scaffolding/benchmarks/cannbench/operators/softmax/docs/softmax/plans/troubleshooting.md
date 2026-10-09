# Troubleshooting

## FP32 VECIN direct writeback

FP32 rows intermittently retained input data because MTE3 read an in-place
VECIN buffer without a queue dependency. All results now pass through an
independent VECOUT queue before DMA.

## Strided gather and FP16 underflow

Sub-32-byte 2D DMA blocks are padded per block and overflowed UB. The corrected
path gathers full 32-byte blocks, extracts the requested lane in UB, computes a
contiguous stable softmax, writes slice-major output, and restores layout on
the host.

For the 8192-element FP16 reduction, CPU torch and dav-2201 differ only at the
half-minimum-subnormal rounding boundary: roughly four thousand of 67 million
elements flip between zero and `2^-24`, in both directions. The verifier treats
an absolute FP16 difference of at most `2^-24` as one quantization ULP before
computing relative metrics. Inputs and kernel outputs are unchanged.
