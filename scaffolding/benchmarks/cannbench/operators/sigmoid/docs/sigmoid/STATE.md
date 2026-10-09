# Sigmoid Ascend C flash state

- Source: `third_party/cann-bench/tasks/level1/sigmoid`
- Source type: specification, Torch golden, and official case matrix
- Created: 2026-08-11
- Target: SocVersion=Ascend910_9362 / NpuArch=dav-2201 (detected by official flash skill)
- Reference: official flash `add`/`sqrt` and completed `operators/exp`
- [x] Definition and design recorded
- [x] Standalone direct-invocation framework implemented
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- [x] Real-NPU clean build verified (`build/sigmoid`, CANN 9.0.0)
- [x] Original `cases.csv` cases 1-20 precision verified (20/20 passed)
- Performance optimization and full profiling intentionally skipped per user request.
- Shared dirty worktree: commit skipped.

## Verification evidence

- Build command: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU command: `./run.sh --all --skip-build --device 0`
- Aggregate: `results.json`
- Per-case records: `build/cases/case_01/result.json` through `build/cases/case_20/result.json`
