# RmsNorm flash state

- Source: `third_party/cann-bench/tasks/level2/rms_norm`
- Target: Ascend910 / `dav-2201`
- Reference: official `ops-direct-invoke-flash` and local AscendC RMSNorm pattern
- [x] Definition/design and FP32 accumulation policy recorded
- [x] Standalone direct-invocation framework implemented
- [x] Real-NPU build verified (`build/rms_norm`, CANN 9.0.0, Ascend910)
- [x] Official cases.csv cases 1-20 correctness verified (20/20 passed)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Optimization/profiling intentionally skipped per user request; dirty worktree commit skipped.

## Verification evidence
- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU: real device 2, original cases 1-20 with final Newton-refined binary
- Aggregate: `results.json` (`total_cases: 20`, `passed_cases: 20`, `all_passed: true`)
- Per-case evidence: `build/cases/case_01/result.json` through `case_20/result.json`;
  every case passes MERE/MARE thresholds and `special_values_match: true`.
