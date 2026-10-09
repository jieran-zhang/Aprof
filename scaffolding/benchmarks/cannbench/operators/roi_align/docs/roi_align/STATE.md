# ROIAlign Ascend C implementation

Source: `third_party/cann-bench/tasks/level3/roi_align`
Created: 2026-08-12
Target: `Ascend910_9362 / dav-2201`

- [x] Read complete `ops-direct-invoke-flash` skill.
- [x] Inspect proto, golden, description, and all 20 original cases.
- [x] Detect target SoC and inspect completed direct-invoke references.
- [x] Write definition/design documents.
- [x] Implement CMake, host, tiling, Ascend C kernel, runner, generator, verifier.
- [x] Build successfully for dav-2201.
- [x] Verify representative FP32, FP16 fixed-grid, aligned adaptive, and unaligned
  adaptive cases on real NPU with bit-exact results.
- [x] Complete all 20 original cases and generate `results.json`.
- [x] Record `harness.test_gate=off`; skip black/white-box gate.
- [x] Skip profiling, optimization, heavyweight review, and commits as requested.

Final evidence: real-NPU device 0 validation reports `20/20`, `all_passed=true`;
every case is bit-exact against torchvision, including NaN/Inf masks.
