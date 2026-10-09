# Conv3DBackpropFilter design

## Device computation

For each group, AIV kernels create two device workspaces:

- packed grad `A[M,CoutGroup]`, where `M=N*Do*Ho*Wo`;
- 3-D gathered input `B[M,CinGroup*Kd*Kh*Kw]`.

An AIC `AscendC::MatmulImpl` directly computes `A^T B` into an FP32 ND workspace. The group result is already contiguous in filter layout, so an AIV cast writes it to the corresponding output segment. Groups execute sequentially and reuse workspaces; no output values are computed on host and no ACLNN symbol is called.

The BF16 post kernel directly recomputes only non-zero accumulators with magnitude below 1 and non-finite accumulators. The former gives an independent FP32 reduction order for severe low-amplitude cancellation; the latter avoids artificial `0 * Inf -> NaN` introduced by padded im2col entries and sums only mathematically valid coordinates. This remains device-side computation. Exact-zero outputs bypass recomputation, so the all-zero large case remains on the Cube result.

FP16 uses FP16 A/B with FP32 C. BF16 is widened to FP32 during AIV packing and uses FP32 A/B/C. `MatmulApiTiling` describes the transposed A operand and ordinary B operand for the exact `(CoutGroup, KGroup, M)` shape.

## UB and transfers

Packing kernels use one 1024-element UB tile: 2048 bytes for FP16 or 4096 bytes for FP32. Output cast uses a 4096-byte FP32 tile plus a 2048-byte B16 tile. Thus peak explicitly managed AIV UB is 6144 bytes. There is no UB-to-UB copy. Each GM tail uses `DataCopyPad` with a byte-count `blockLen`; the host block partition is rounded to `32/sizeof(T)` elements and the final logical tail uses its exact byte length. Scalar gather writes every local element before the GM transfer, including explicit zero padding.

## Semantics and boundaries

The im2col coordinate formula incorporates all stride/dilation/front-pad values and skips invalid input positions. Group offsets are applied independently to input and output channels. The host validates ranks, filter channel dimensions, group divisibility, and that the supplied grad spatial shape equals the forward-convolution result. Large and non-aligned shapes use 64-bit indexing.

This is a dav-2201 classic AscendC/Cube path, not an Ascend950 Reg path. Test gate is off in the repository AGENTS configuration; the authoritative original 20-case harness is used instead.
