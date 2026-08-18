# dynamic_quant flash state

- Source: `third_party/cann-bench/tasks/level2/dynamic_quant`
- Target: Ascend910 / `dav-2201`
- Reference: official `ops-direct-invoke-flash` workflow and completed cannbench direct-invocation framework
- [x] Definition and flash design recorded
- [x] Standalone direct-invocation framework implemented
- [x] Real-NPU build verified (`build/dynamic_quant`, CANN 9.0.0, Ascend910, device 0)
- [x] Official cases.csv cases 1-20 precision verified (20/20 passed)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Performance optimization and profiling intentionally skipped per user request.
- Shared dirty worktree: commit skipped.

## Verification evidence

- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU run: `./run.sh --all --skip-build --device 0`
- Aggregate: `results.json`
- Per-case records: `build/cases/case_01/result.json` through `build/cases/case_20/result.json`
- Verified at: 2026-08-11 12:22 UTC
