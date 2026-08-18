# MHA correctness-first design

The host only parses metadata, allocates/copies tensors, derives tiling, and
launches compiled kernels; it never computes attention values.

1. A scalar AIC kernel reorders BSND tensors to BNSD. A single parent block is
   used because dav-2201 direct launches do not expose AIV subcores as
   independent logical block loops.
2. AscendC Cube Matmul computes QK-transpose for each batch/head.
3. An AIV kernel converts a score row to FP32, applies scale and the
   right-aligned causal mask, then performs max-subtracted exp/sum softmax.
   Rows are split by a 131072-score-element budget and launched with one AIV
   parent to avoid the long-kernel limit and dav-2201 subcore ambiguity.
4. A second Cube Matmul computes probability-times-V.
5. A scalar AIC kernel scatters BNSD back to BSND.

The score workspace is stored in the input dtype, matching the golden
matmul/softmax dtype boundaries. UB per softmax row contains the raw
`Skv*2` bytes, FP32 row `Skv*4`, 8192-byte reduction workspace, and a
32-byte scalar buffer; maximum `Skv=2048` remains within UB.
