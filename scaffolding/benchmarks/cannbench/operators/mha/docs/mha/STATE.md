# MHA flash state

- Source: `third_party/cann-bench/tasks/level4/mha`
- Target: Ascend910_9362 / `dav-2201`
- Physical device: 3 (`ASCEND_RT_VISIBLE_DEVICES=3`, program `--device 0`)
- [x] Definition and correctness-first design recorded
- [x] Standalone direct-invocation CMake/host/kernel/scripts framework implemented
- [x] QK, causal mask, softmax, and PV execute in compiled device kernels
- [x] Real-NPU dav-2201 build verified
- [x] Official cases 1-20 precision verified (20/20 passed)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Profiling and performance optimization intentionally skipped.
- Shared dirty worktree: commit skipped.

## Evidence

- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU: `ASCEND_RT_VISIBLE_DEVICES=3 ./run.sh --all --skip-build --device 0`
- Aggregate: `results.json`
- Per-case records: `results/case_01/result.json` through `case_20/result.json`
- Verified at: 2026-08-12 UTC
