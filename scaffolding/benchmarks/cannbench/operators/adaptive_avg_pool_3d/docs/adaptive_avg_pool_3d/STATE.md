# adaptive_avg_pool_3d state

- [x] Phase 0: source and environment inspected
- [x] Phase 1: persistent state initialized
- [x] Phase 2: compilable direct-invoke skeleton
- [x] Phase 3: definition documented
- [x] Phase 4: implementation designed
- [x] Phase 5: original 20-case harness implemented
- [x] Phase 6: Ascend C kernel implemented
- [x] Phase 7: all 20 original cases verified on NPU
- [x] Phase 7.5: heavy black/white-box gate skipped (`harness.test_gate: off`)
- [x] Phase 8: final results recorded

The task explicitly requests no commits and no profiling/optimization. The
kernel is a correctness-first, output-parallel implementation for dav-2201.

Final evidence: `results.json` records 20/20 original cases passing on
Ascend910_9362 / dav-2201. Performance profiling was not requested.
