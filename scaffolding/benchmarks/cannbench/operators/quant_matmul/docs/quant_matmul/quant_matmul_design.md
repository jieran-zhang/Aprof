# quant_matmul design

The implementation is a two-kernel direct-launch pipeline and contains no
ACLNN call or host-side result computation.

1. An AIC kernel instantiates AscendC `MatmulImpl` with GM/ND int8 A and B and
   GM/ND int32 C. Host tiling uses `MatmulApiTiling` for Ascend910B/dav-2201.
   Each batch is launched separately and serialized before the shared tiling
   buffer is reused. Cube performs all K contraction and exact int32
   accumulation on device.
2. An AIV kernel walks the device int32 MN buffer, broadcasts scale/offset by
   N and per-token scale by M, places integer or floating bias at the required
   side of dequantization, then performs explicit RNE FP16/BF16 conversion.

The AIV path currently uses one logical block. This deliberately avoids the
dav-2201 direct-AIV parent-core/subcore block-index ambiguity discovered during
validation and guarantees every MN element is written exactly once. It is a
correctness-only choice; no performance claim is made.

Device buffers are: int8 A (`B*M*K`), int8 B (`B*K*N`), int32 accumulator
(`B*M*N`), 16-bit output (`B*M*N`), and the small parameter tensors. The Cube
library owns its internal L0/L1/UB schedule from `TCubeTiling`; the scalar AIV
postprocess allocates no UB buffers.
