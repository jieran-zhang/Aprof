# Cummin implementation state

- Target: Ascend910_9362 / dav-2201
- Validation device: 4
- Source: `third_party/cann-bench/tasks/level2/cummin`

- [x] Source semantics and all 20 cases extracted
- [x] Direct-invoke CMake/host/kernel framework implemented
- [x] CPU golden and index-gather verifier implemented
- [x] CANN build passes
- [x] Real-NPU cases 1-20 pass
- [x] `results.json` reports `all_passed: true`

## Final evidence

- CANN build: `cmake --build build -j4` passed.
- Hardware: Ascend910_9362, `dav-2201`, device 4.
- Result: `results.json` records 20/20 passed and `all_passed: true`.
- Case 14 contains only NaNs, so `exact_values` is false under `torch.equal`; NaN masks,
  finite-value metrics, index range, and index-gather semantics all pass as required.
- [x] Test gate skipped (`benchmarks/cannbench/AGENTS.md`: `harness.test_gate: off`)
