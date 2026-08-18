# Mish flash state

- Source: `third_party/cann-bench/tasks/level1/mish`
- Target: Ascend910 / `dav-2201`
- Reference: official flash `add`/`sqrt` and completed `exp`/`sigmoid`
- [x] Definition and flash design recorded
- [x] Standalone direct-invocation framework implemented
- [x] Real-NPU build verified (`build/mish`, CANN 9.0.0, Ascend910_9362)
- [x] Official cases.csv cases 1-20 precision verified (20/20 passed)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Performance optimization and profiling intentionally skipped per user request.
- Shared dirty worktree: commit skipped.

## Verification evidence

- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU run: `./run.sh --all --skip-build --device 4`
- Aggregate: `results.json` (`all_passed: true`)
- Per-case records: `build/cases/case_01/result.json` through
  `build/cases/case_20/result.json`
