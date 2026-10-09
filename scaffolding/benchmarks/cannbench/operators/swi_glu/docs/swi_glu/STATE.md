# SwiGLU flash state

- Source: `third_party/cann-bench/tasks/level1/swi_glu`
- Target: Ascend910 / `dav-2201`
- Workflow: official `ops-direct-invoke-flash`
- [x] Definition and accuracy-first design recorded
- [x] Compilable standalone direct-invocation framework implemented
- [x] Real-NPU build verified (`build/swi_glu`, CANN 9.0.0, Ascend910)
- [x] Official cases.csv cases 1-20 precision verified (20/20 passed on device 2)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Performance optimization and profiling intentionally skipped per user request.
- Shared dirty worktree: commit skipped.

## Verification evidence

- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU run: `./run.sh --all --skip-build --device 2`
- Aggregate: `results.json`
- Per-case records: `build/cases/case_01/result.json` through `case_20/result.json`
