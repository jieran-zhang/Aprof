# MhcSinkhorn Ascend C implementation

Source: `third_party/cann-bench/tasks/level3/mhc_sinkhorn`
Created: 2026-08-12
Target: `Ascend910_9362 / dav-2201`

- [x] Read complete `ops-direct-invoke-flash` skill.
- [x] Inspect proto, golden, description, and all 20 official cases.
- [x] Detect SoC and inspect validated local Exp patterns.
- [x] Implement CMake, host runner, tiling, actual device computation, generation,
  verification, definition, design, and troubleshooting.
- [x] Confirm host performs no Sinkhorn/output precomputation.
- [x] Build for dav-2201.
- [x] Validate representative N=4, N=16, and Inf cases on real NPU.
- [x] Complete all original 20 cases and generate `results.json`.
- [x] Record `harness.test_gate=off` and skip profiling/optimization/commits.

Final evidence: real NPU device 0 reports `20/20`, `all_passed=true`; maximum finite
absolute error across all cases is below `1.51e-7`, and NaN/Inf masks match exactly.
