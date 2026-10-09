# unique state

- [x] Phase 0: source and environment inspected
- [x] Phase 1: persistent state initialized
- [x] Phase 2: direct-invoke skeleton implemented
- [x] Phase 3: definition documented
- [x] Phase 4: implementation designed
- [x] Phase 5: original 20-case harness implemented
- [x] Phase 6: Ascend C radix-sort/unique/inverse kernels implemented
- [x] Phase 7: all 20 original cases re-verified on NPU after device-side rewrite
- [x] Phase 7.5: heavy black/white-box gate skipped (`harness.test_gate: off`)
- [x] Phase 8: final results recorded

No commits, profiling, or performance optimization are part of this task.

Previous host-computed evidence was invalidated and removed. `results.json`
now records 20/20 bit-exact cases from `implementation=npu_radix_sort` on
Ascend910_9362 / dav-2201.
