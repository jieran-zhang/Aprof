# Gather flash state

- Source: `third_party/cann-bench/tasks/level2/gather`
- Target: Ascend910 / `dav-2201`
- Reference: official `ops-direct-invoke-flash` skill and standalone direct-invoke framework
- [x] Definition and design recorded
- [x] Standalone direct-invocation framework implemented
- [x] Real-NPU build verified (`build/gather`, CANN 9.0.0, Ascend910)
- [x] Official cases.csv cases 1-20 precision verified (20/20 bit-exact passed)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Performance optimization, profiling, and legacy review intentionally skipped per user request.
- Shared dirty worktree: commit skipped.

## Verification evidence

- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU run: original cases 1-20 on real device 2; case 13 was rerun after the small-output
  block tiling fix, then cases 14-20 completed with the final binary.
- Aggregate: `results.json` (`total_cases: 20`, `passed_cases: 20`, `all_passed: true`)
- Per-case records: `build/cases/case_01/result.json` through
  `build/cases/case_20/result.json`; every case has `exact_match: true`,
  `mismatch_count: 0`, `invalid_index_count: 0`, and `passed: true`.
