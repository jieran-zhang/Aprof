# add_rms_norm_dynamic_quant flash state

- Source: `third_party/cann-bench/tasks/level3/add_rms_norm_dynamic_quant`
- Target: Ascend910_9362 / `dav-2201`, physical device 3 (logical device 0)
- Reference: `dynamic_quant`, `rms_norm`, and official `ops-direct-invoke-flash` workflow
- [x] Authoritative semantics and exact 20-case matrix extracted
- [x] Definition and tiled flash design recorded before final validation
- [x] Standalone direct-invocation CMake/host/kernel/case/verifier framework implemented
- [x] Real-NPU build verified (`build/add_rms_norm_dynamic_quant`, CANN 9.0.0)
- [x] Official cases.csv cases 1-20 precision verified (20/20 passed)
- [x] `harness.test_gate=off`; black/white-box gate skipped by configuration
- Performance optimization and profiling intentionally skipped per user request.
- Shared dirty worktree: commit skipped by parent task requirement.

## Verification evidence

- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- NPU run: `ASCEND_RT_VISIBLE_DEVICES=3 ASCEND_DEVICE_ID=3 ./run.sh --all --skip-build --device 0`
- Aggregate: `results.json` (`passed_cases=20`, `all_passed=true`)
- Per-case records: `build/cases/case_01/result.json` through `case_20/result.json`
- Verified at: 2026-08-12 UTC
