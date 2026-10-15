# Gelu flash state

- Source: `third_party/cann-bench/tasks/level1/gelu`
- Target: Ascend910 / `dav-2201`
- Reference: official flash `sqrt` and completed `exp`
- [x] Definition and correctness-first design recorded
- [x] Standalone direct-invocation source and official 20-case harness implemented
- [x] Real-NPU build verified (`build/gelu`, CANN 9.0.0, Ascend910 / device 2)
- [x] Official cases 1-20 precision verified (20/20 passed)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Performance optimization and profiling intentionally skipped per user request.
- Shared dirty worktree: commit skipped.

## Verification evidence

- Final-state build and full run: `./run.sh --all --device 2`
- Aggregate: `results.json` (`passed_cases: 20`, `all_passed: true`)
- Per-case records: `build/cases/case_01/result.json` through
  `build/cases/case_20/result.json`
