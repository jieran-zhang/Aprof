# ApplyRotaryPosEmb flash state
- Source: `third_party/cann-bench/tasks/level2/apply_rotary_pos_emb`
- Target: Ascend910 / dav-2201
- [x] Definition/design recorded; FP16/BF16 compute in FP32
- [x] Standalone four-input/two-output direct invocation implemented
- [x] Real-NPU build verified (`build/apply_rotary_pos_emb`, CANN 9.0.0, Ascend910)
- [x] Original cases 1-20 correctness verified (20/20 passed)
- [x] `harness.test_gate=off`; skipped by configuration
- Profiling/optimization/review skipped per user request; dirty worktree not committed.

## Evidence
- Build: `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build -j4`
- Binary: SHA-256 `03020a51493a78195b7c00fee868fd7fd4f75e98051580ce8966404f9efcf8f6`
- NPU: real Ascend910 device 2, original cases 1-20
- Aggregate: `results.json` (`total_cases: 20`, `passed_cases: 20`, `all_passed: true`)
- Per-case: `build/cases/case_01/result.json` through `case_20/result.json`; all satisfy
  configured MERE/MARE thresholds and `special_values_match: true`.
