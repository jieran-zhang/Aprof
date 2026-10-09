# moe_finalize_routing state

- Source: `third_party/cann-bench/tasks/level3/moe_finalize_routing`
- SoC: Ascend910_9362
- Arch: dav-2201
- Workflow: ops-direct-invoke-flash correctness-first
- [x] Original specification and 20 cases inspected
- [x] Definition and design documented
- [x] Direct invoke host/kernel and bounded-memory case harness implemented
- [x] Routing, gather, scale, residual and drop/skip semantics implemented device-side
- [x] Build verified on dav-2201
- [x] Real NPU original cases 20/20 (physical device 1; FP16/FP32 bitwise, BF16 within specified thresholds)
- [x] Profiling and optimization skipped per user request
- [x] Heavy review and test gate skipped (`harness.test_gate=off`)
