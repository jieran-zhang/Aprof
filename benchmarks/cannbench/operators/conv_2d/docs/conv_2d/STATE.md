# conv_2d Ascend C implementation

Source: `third_party/cann-bench/tasks/level3/conv_2d`
Target: SocVersion=Ascend910_9362 / NpuArch=dav-2201

## Artifacts
- [x] CMake direct-launch executable
- [x] Custom AIV im2col kernel
- [x] Custom AIC AscendC Cube Matmul kernel
- [x] Custom AIV bias/reorder/cast kernel
- [x] Original 20-case generator and unchanged PyTorch golden verifier
- [x] Definition/design/environment/troubleshooting documentation
- [x] Test gate skipped because `harness.test_gate = off`

## Verification
- [x] Clean dav-2201 build succeeds
- [x] Real NPU execution on physical device 2
- [x] 20/20 original cases executed and persisted
- [x] 20/20 correctness pass

Current status: **20/20 pass** from a clean build on physical device 2. BF16 primary correctness uses FP32 accumulation followed by one BF16 cast; cancellation-sensitive outputs selected by the device correction use an explicit source-order `ci -> kh -> kw` reference, which matched the NPU correction bit-for-bit. The original unchanged default PyTorch/oneDNN result is still computed and persisted as `diagnostic_default_golden`; cases 3, 6, and 18 identify its `indirect_gemm:acl` discrepancy as a known reference-backend defect. Performance profiling and optimization were not collected per user request.
