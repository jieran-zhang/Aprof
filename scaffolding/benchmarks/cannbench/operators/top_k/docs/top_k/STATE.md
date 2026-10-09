# top_k state

- Source: `third_party/cann-bench/tasks/level3/top_k`
- SoC: Ascend910_9362
- Arch: dav-2201
- Workflow: ops-direct-invoke-flash correctness-first
- [x] Original specification and 20 cases inspected
- [x] Definition and design documented
- [x] Direct invoke host/kernel and case harness implemented
- [x] Build verified on dav-2201
- [x] Real NPU original cases 20/20 (value bitwise match plus index-gather validation)
- [x] Profiling and optimization skipped per user request
- [x] Heavy review and test gate skipped (`harness.test_gate=off`)
