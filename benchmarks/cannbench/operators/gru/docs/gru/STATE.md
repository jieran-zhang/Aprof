# GRU state

- Operator: `gru`
- Source: `third_party/cann-bench/tasks/level4/gru`
- SoC: `Ascend910_9362`
- architecture: `dav-2201`
- physical device: 1 (`ASCEND_RT_VISIBLE_DEVICES=1`, program `--device 0`)
- priority: correctness-only; profiling not collected per user

## Completion

- [x] Authoritative schema, golden, and 20 cases analyzed
- [x] Definition and device design documented
- [x] Direct CMake/host/kernel framework implemented
- [x] Gate matmuls implemented by self-compiled AIC/Cube kernels
- [x] Sigmoid/tanh and recurrent hidden update implemented by AIV kernel
- [x] FP16, BF16, FP32, bias/no-bias, h0/no-h0 validated
- [x] Batch-first, bidirectional, 1-3 layers, odd dimensions validated
- [x] Original 20/20 cases run on real NPU and recorded in `results.json`
- [x] `harness.test_gate: off` recorded; no extra black/white-box gate required
- [x] Troubleshooting and reproducible run command documented

Evidence: `build/gru`, `results/case_01..case_20/result.json`, and
`results.json` (`passed_cases=20`, `all_passed=true`).
