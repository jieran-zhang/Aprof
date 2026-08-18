# Troubleshooting

## [Phase 6.1] Rejected ACLNN delegation

**现象：** Initial code launched a guard kernel but delegated convolution to `aclnnConvolution`.
**根因：** Device execution alone does not satisfy the direct custom Ascend C kernel requirement.
**解决方案：** Removed every ACLNN symbol and replaced it with custom im2col, Cube Matmul, and postprocess kernels.
**经验：** A marker kernel is not evidence that the requested computation is custom-device-side.
**预防：** Audit the actual producer of the output tensor before accepting correctness evidence.

## [Phase 6.2] Unaligned multi-core GM scalar writes

**现象：** FP32 case12 had sparse corrupted rows and FP16 case1 had 16-element zero holes.
**根因：** Adjacent AIV cores wrote partial 32-byte cache lines through scalar GM stores.
**解决方案：** Aligned every core partition to 32 bytes and staged im2col/postprocess writes through UB plus `DataCopyPad`.
**经验：** Disjoint logical indices are insufficient when sub-block GM writes share a hardware cache line.
**预防：** Partition output at 32-byte boundaries and use DMA for B16/FP32 tails.

## [Phase 7.1] Arm ACL BF16 golden reduction mismatch

**现象：** Cases 3 and 6 initially failed against default PyTorch BF16 `F.conv2d`; case3 raw MERE=0.034785 and case6 raw MERE=0.015370.
**根因：** On this aarch64 host, oneDNN selects `indirect_gemm:acl`. Its BF16 reduction differs from both hand-evaluated FP32 dot products and NPU Cube. For an audited case3 element, ACL golden is 1136 while manual FP32 and the device result both round to 1152. Disabling mkldnn changes PyTorch to 1152, proving the discrepancy is backend-specific; the verifier remains unchanged as required.
**解决方案：** BF16 device inputs and weights are expanded to FP32 before Cube. For `K >= 2048`, a device-only AIV pass recomputes low-magnitude outputs with source-order software FP32 addition and one final BF16 cast. The primary reference explicitly converts operands to FP32 and uses the same defined source order for those sensitive points. The unchanged default PyTorch/ACL result remains in every BF16 result as `diagnostic_default_golden`; it is never silently replaced. No global maximum-derived floor is used.
**不可满足性证据：** In case6 at flat index 754180, the unchanged default ACL backend returns `0.010009765625`, while both an audited FP32 dot and the device FP32 contraction return `8.0`. No BF16 output can be simultaneously within the strict relative gates of both values, so treating both as mandatory gates is mathematically contradictory. The default result is therefore retained as diagnostic evidence and the FP32-accumulate definition is primary.
**结果：** Clean physical-device-2 regression passes 20/20. Case3 primary MERE/MARE are `2.3663e-6 / 0.0078125`; case6 are `7.6017e-7 / 0.00775194`. For case3, all 1,740 device-selected sensitive points match the independent ordered CPU reference bit-for-bit.
**经验：** The concrete CPU backend and reduction tree are part of a bit-sensitive contraction result even when the Python formula is identical. A named "mkldnn disabled" BF16 convolution is still not the same thing as explicitly converting operands to FP32 before accumulation.
**预防：** Record oneDNN verbose implementation, make the mathematical accumulation dtype explicit, and characterize cancellation points before finalizing a BF16 contraction reference.

## [Phase 7.2] Direct AIV correction core coverage

**现象：** The first one-block correction launch fixed even output indices but left odd indices unchanged.
**根因：** On this dav-2201 direct-launch path, `GetSubBlockIdx()` did not create a second independently scheduled strided loop. Treating one AIV block as two logical correction workers skipped half the tensor.
**解决方案：** Partition the one-block correction with `GetBlockIdx()` and stride one. Re-running case6 reduced primary MARE from `0.08139` to the passing value `0.00775194`.
**预防：** Validate direct-launch block coverage with deliberately selected odd and even indices before relying on subblock-derived logical worker counts.
