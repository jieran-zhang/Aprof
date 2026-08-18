# moe_re_routing design

## Device computation

Two custom Ascend C kernels are launched in one ACL stream.

1. `moe_re_routing_build_kernel` runs one vector core. It reads the count matrix
   from GM, iterates destination expert-major order, constructs every int32 gather
   index in GM, reduces each expert count, and gathers/zero-fills scales while the
   source offset is known. The int32/int64 paths are template specializations. No
   routing metadata is computed on the host.
2. `moe_re_routing_gather_kernel` divides destination token rows over the available
   vector cores. Every core reads device-produced indices and uses padded DMA for an
   exact `H`-element row copy. This handles sub-32-byte and non-aligned rows without
   exposing padding in the output. Missing scales are device-written as zeros by the
   first kernel.

Stream ordering makes the first kernel's mapping/count writes visible to the gather
kernel. Since each destination row belongs to exactly one core, no atomics are needed.

## Memory and tiling

- Inputs in GM: `A*H*token_bytes + N*E*count_bytes + optional A*4`.
- Outputs in GM: `A*H*token_bytes + A*4 scales + A*4 indices + E*count_bytes`.
- Tiling record: fixed-size scalar metadata in GM.
- UB live bytes per token row: `align_up(H*token_bytes, 32)`, at most 32768 bytes.
  The single row buffer is reused after each synchronized input/output DMA.
- `blockNum = min(vector_core_count, A)` and
  `tokensPerBlock = ceil(A/blockNum)`; the final block is tail-clamped.

The implementation does not call ACLNN, Torch operators, CPU routing helpers, or a
simulator. The host only validates shapes/dtypes, allocates buffers, copies files,
and launches the two kernels.
