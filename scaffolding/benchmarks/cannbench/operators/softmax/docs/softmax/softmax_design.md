# softmax flash design

The host derives contiguous `outer/reduce/inner` factors and assigns complete
softmax slices to vector cores. Last-axis slices are copied directly. For an
internal axis, each DMA block gathers a safe 32-byte source segment and scalar
UB extraction packs the requested lane into one contiguous reduction vector;
this avoids the per-block padding overflow caused by sub-32-byte DMA blocks.

The packed slice is widened to FP32, reduced by stable max, exponentiated,
summed, normalized, and cast back. The FP16 moderate-range path uses the SLEEF
u10 exp polynomial used by PyTorch CPU; large-range FP16 and all FP32/BF16
slices use hardware Exp to preserve safe underflow behavior. Inf and NaN flow
through the stable max/sub/exp/sum formula.

Results pass through a dedicated VECOUT queue. The kernel writes slice-major
contiguous output, and the host restores the original layout for internal
axes. This is a correctness-first implementation; optimization and profiling
are intentionally excluded.
