# Maximum flash state

- Source: `third_party/cann-bench/tasks/level2/maximum`
- Target: Ascend910 / `dav-2201`
- [x] Standalone Ascend C direct-invocation framework implemented
- [x] `build/maximum` compiled with CANN 9.0.0
- [x] Original cases 1-20 executed on real NPU device 0
- [x] Correctness: 20/20 passed (`results.json`, `all_passed: true`)
- [x] `harness.test_gate=off`; performance optimization/profiling skipped per user request
- Shared dirty worktree: commit skipped.

Reproduce: `./run.sh --all --skip-build --device 0`.
