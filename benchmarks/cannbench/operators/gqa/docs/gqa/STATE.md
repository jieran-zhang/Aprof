# GQA implementation state

- [x] Authoritative level4 specification and 20 original cases reviewed
- [x] Ascend910_9362 / dav-2201 physical environment confirmed
- [x] Definition and device design documented
- [x] Direct CMake/host/kernel runner implemented
- [x] QK, mask, softmax, PV, grouped head mapping implemented on device
- [x] FP16/BF16, causal/non-causal, cross-attention, MQA/MHA validated
- [x] Original 20 cases passed on physical NPU device 1
- [x] Raw and bounded precision diagnostics recorded per case
- [x] Test gate skipped per repository `harness.test_gate: off`
- [x] Correctness-only: profiling/optimization intentionally not collected

Status: complete. See `results.json` for the authoritative result summary.
