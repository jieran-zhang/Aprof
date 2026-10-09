# WeightQuantBatchMatmul Ascend C implementation

Source: `third_party/cann-bench/tasks/level3/weight_quant_batch_matmul`
Target: `Ascend910_9362 / dav-2201`

- [x] Read repository AGENTS.md and complete ops-direct-invoke-flash skill.
- [x] Inspect proto, golden, description, and all 20 original cases.
- [x] Write definition and design documents before validation.
- [x] Implement CMake, host, AIV dequant/postprocess, AIC Cube matmul, runner, generator, verifier, and summary.
- [x] Build successfully for dav-2201.
- [x] Verify representative FP16/BF16 and optional-input cases on physical NPU device 1.
- [x] Complete all 20 original cases and generate results.json.
- [x] Record `harness.test_gate=off`; skip black/white-box gate.
- [x] Skip profiling, optimization, heavyweight review, and commits as requested.

Final evidence: `results.json` records physical `Ascend910_9362 / dav-2201`
validation with `20/20`, `all_passed=true`. Case 20 covers the maximum
`M=32, K=28672, N=8192` input. Device computation is AIV dequantization,
AIC Cube FP32-accumulating matmul, and AIV bias/output conversion.
