# Grouped Matmul Design

The host validates cumulative boundaries and launches one locally compiled AIC kernel per
non-empty expert. `AscendC::MatmulImpl` consumes ND GM tensors and host-generated
`TCubeTiling`; its B template encodes the weight transpose. Bias is supplied to the Cube
primitive. Groups are synchronized because direct `MatmulImpl` launches share runtime Cube
resources. No host computation or ACLNN matmul is used.

For large-K FP16 contraction, an AIV correction kernel scans low-magnitude cancellation
outputs and IEEE-half overflow boundaries. It decodes FP16 bits, forms exact FP16 products,
performs ordered software IEEE binary32 addition, and writes round-to-nearest-even FP16 bits.
This remains device-side and preserves strict NaN/Inf masks. The path uses no UB arrays other
than one 32-byte accumulator buffer; the dense Cube path owns L1/L0 tiling from
`MatmulApiTiling` (base M/N/K observed as 128/256/64 for the large transpose cases).
