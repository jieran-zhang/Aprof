# conv_3d_backprop_filter Ascend C implementation

Source: `third_party/cann-bench/tasks/level3/conv_3d_backprop_filter`
Target: SocVersion=`Ascend910_9362`, NpuArch=`dav-2201`
Mode: ops-direct-invoke-flash, correctness only

## Artifacts

- [x] Authoritative formula, dtype and group semantics documented
- [x] CMake standalone ACL direct-invoke harness
- [x] Custom AIV grouped 3-D im2col and grad packing kernels
- [x] Custom AIC `AscendC::MatmulImpl` filter-gradient contraction
- [x] AIV FP32-to-FP16/BF16 output conversion
- [x] Original CSV-driven case generation and verifier
- [x] Original 20/20 cases passed on physical device 4
- [x] `results.json` summarized and audited

## Validation policy

- No host output precomputation and no ACLNN fallback.
- Primary oracle: explicit FP32 torch contraction followed by one output cast.
- Native-dtype torch contraction retained as a diagnostic due to the documented FP16 CPU backend cancellation defect.
- Fixed `2^-5` absolute small-value equivalence plus per-element one-output-ULP equivalence; raw primary metrics remain in results.
- A uniform per-output FP32 forward-error bound handles only proven ill-conditioned cancellation points; every result records the count and maximum device/bound ratio.
- Final audit: 511/total output elements required the forward-bound rule; maximum accepted bound ratio `2.3377506295219064e-05 <= 1`.
- Repository `harness.test_gate=off`; black/white-box gate skipped by configuration.
- Profiling: `not_collected_per_user`.
