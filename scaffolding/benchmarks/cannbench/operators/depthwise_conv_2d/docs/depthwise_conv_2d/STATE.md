# depthwise_conv_2d state

- [x] Phase 0: authoritative level3 source and Ascend910_9362/dav-2201 environment inspected
- [x] Phase 1: persistent state initialized
- [x] Phase 2: compilable direct-invoke skeleton
- [x] Phase 3: definition documented
- [x] Phase 4: correctness-first device implementation designed
- [x] Phase 5: original 20-case generator and verifier implemented
- [x] Phase 6: Ascend C kernel built for dav-2201
- [x] Phase 7: all 20 original cases verified on real NPU
- [x] Phase 7.5: heavy black/white-box gate skipped (`harness.test_gate: off`)
- [x] Phase 8: final results recorded

The parent task explicitly requires no commits and no profiling/optimization.
Physical device 1 is exposed as logical device 0 for all validation.

Final evidence: `results.json` records 20/20 original cases passing on
Ascend910_9362 / dav-2201. `build/cases/case_01` through `case_20` preserve
metadata and per-case verifier results. Performance is
`not_collected_per_user` as requested.
