# GroupNorm implementation state
- Target: Ascend910_9362 / dav-2201 / device 4
- Source: `third_party/cann-bench/tasks/level2/group_norm`
- [x] Source semantics and 20 cases extracted
- [x] Direct-invoke framework implemented
- [x] Golden verifier implemented
- [x] CANN build passes
- [x] Real-NPU 20/20 pass
- [x] `results.json` has `all_passed: true`

## Final evidence
- CANN build passed for dav-2201.
- Real hardware: Ascend910_9362, device 4.
- Original cases 1-20 all passed; `results.json` records `passed_cases: 20` and
  `all_passed: true`.
- [x] Test gate skipped (`harness.test_gate: off`)
