# Scatter flash state

- Source: `third_party/cann-bench/tasks/level2/scatter`
- Target: Ascend910 / dav-2201
- [x] Standalone direct-invocation CMake, host, kernel, runner, and verifier implemented
- [x] Supported dtypes, dimensions, index widths, and reduction modes covered
- [x] Real-NPU build verified (`build/scatter`, CANN 9.0.0, Ascend910)
- [x] Original cases 1-20 correctness verified (20/20 passed)
- [x] `harness.test_gate=off`; skipped by configuration
- Profiling, performance optimization, and heavy review skipped per user request; dirty worktree not committed.

## Evidence

- Binary SHA-256: `59b9bf00b870c71b4efa37ef429446751c0b58a82bdf1d2c2d6733d0f9d25baa`
- NPU: real Ascend910 device 4, original cases 1-20
- Aggregate: `results.json` (`total_cases: 20`, `passed_cases: 20`, `all_passed: true`)
- Per-case: `build/cases/case_01/result.json` through `case_20/result.json`
