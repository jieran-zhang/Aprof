# UnsortedSegmentSum flash state
- Source: `third_party/cann-bench/tasks/level2/unsorted_segment_sum`
- Target: Ascend910 / dav-2201
- [x] Definition/design recorded
- [x] Standalone direct invocation implemented for all original dtypes
- [x] Local Ascend C build verified
- [x] Real-NPU build/run verified
- [x] Original cases 1-20 passed
- [x] `harness.test_gate=off`; skipped by configuration
- Profiling/optimization/review skipped; dirty worktree not committed.

## Evidence
- Build: `build/unsorted_segment_sum`, SHA-256
  `d9ab6dc553ec424a83dae142b7774560653f820ba6f98d474e742ba2ac1e373e`
- Hardware: Ascend910 / dav-2201, real NPU device 2
- Results: `results.json` reports `total_cases=20`, `passed_cases=20`, `all_passed=true`
- Per-case evidence: `build/cases/case_01/result.json` through
  `build/cases/case_20/result.json`
