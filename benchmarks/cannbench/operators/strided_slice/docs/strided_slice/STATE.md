# StridedSlice Ascend C implementation

Source: `third_party/cann-bench/tasks/level3/strided_slice`
Source type: task specification, golden implementation, and 20-case matrix
Created: 2026-08-12
Target: SocVersion=`Ascend910_9362`, NpuArch=`dav-2201`

## Flash correctness-first phases

- [x] Read the complete `ops-direct-invoke-flash` skill and relevant implementation/failure references.
- [x] Inspect the task definition, golden, proto, and all 20 official cases.
- [x] Inspect a completed cannbench direct-invoke operator as structural reference.
- [x] Detect the target SoC and architecture.
- [x] Write operator definition and correctness-oriented design documents.
- [x] Implement CMake project, host runner, tiling metadata, and Ascend C kernel.
- [x] Implement deterministic generation and independent bit-exact verification for 20 cases.
- [x] Build successfully for `dav-2201`.
- [x] Run all 20 original cases on a real NPU and generate `results.json`.
- [x] Record `harness.test_gate=off`; black/white-box gate skipped by configuration.
- [x] Skip profiling, optimization, heavyweight reviews, and commits per task instruction.

## Current evidence

- Clean initial CMake/ASC build: passed.
- Real-NPU representative case 1 (1D stride): exact match.
- Real-NPU representative case 19 (shrink + new axis): exact match.
- Full 20-case validation on device 0: **20/20 passed**, bit-exact for every case.
- `results.json`: `passed_cases=20`, `all_passed=true`.
