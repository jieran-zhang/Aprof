# arg_max flash state

- Source: `third_party/cann-bench/tasks/level2/arg_max`
- Target: Ascend910 / `dav-2201`
- Reference: official `ops-direct-invoke-flash` workflow and completed cannbench direct-invocation operators
- [x] Definition and flash design recorded
- [x] Standalone direct-invocation framework implemented
- [x] Real-NPU build verified (`build/arg_max`, CANN 9.0.0, Ascend910, device 4)
- [x] Official cases.csv cases 1-20 precision verified (20/20, zero mismatches)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Performance optimization and profiling intentionally skipped per user request.
- Shared dirty worktree: commit skipped.

## Verification evidence

- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU run: `./run.sh --all --skip-build --device 4`
- Aggregate: `results.json`
- Per-case records: `build/cases/case_01/result.json` through `build/cases/case_20/result.json`
- Verified at: 2026-08-11 12:05 UTC
