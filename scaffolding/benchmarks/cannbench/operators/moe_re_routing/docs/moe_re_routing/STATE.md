# moe_re_routing state

- Source: `third_party/cann-bench/tasks/level3/moe_re_routing`
- SoC: Ascend910_9362
- Arch: dav-2201
- Workflow: ops-direct-invoke-flash correctness-first
- [x] Authoritative specification, golden and original 20 cases inspected
- [x] Definition and direct device-kernel design documented
- [x] Direct ACL host, device kernels and bounded-memory harness implemented
- [x] Routing index construction, expert count and token/scale gather implemented device-side
- [x] Build verified for dav-2201
- [x] Real NPU original cases 20/20 on physical device 1; all four outputs bitwise exact
- [x] Supplemental zero-count expert cells and sub-32-byte padded row passed on physical device 1
- [x] Profiling and optimization skipped per user instruction
- [x] Heavy review and test gate skipped (`harness.test_gate=off`)
