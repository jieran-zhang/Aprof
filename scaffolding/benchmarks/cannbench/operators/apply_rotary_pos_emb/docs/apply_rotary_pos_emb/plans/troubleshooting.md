# ApplyRotaryPosEmb troubleshooting

## [Phase 7] ScalarCast/GM scalar output zero and FMA cancellation drift

Initial half output was entirely zero even after scalar results were routed through vector output Cast,
showing that direct GM half scalar conversion was not valid on this path. Float32 also fused multiply-add
around an exact cancellation, producing 1.7e-6 where golden's two rounded products summed to zero.

The kernel now copies complete q/k/cos/sin rows into UB, uses vector Cast to FP32, computes from FP32 UB,
uses volatile product temporaries to preserve `mul + mul + add` rounding order, then vector-casts and DMA-writes outputs.
