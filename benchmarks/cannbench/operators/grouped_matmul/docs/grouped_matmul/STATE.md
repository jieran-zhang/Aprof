# grouped_matmul state

- [x] Authoritative level3 specification reviewed
- [x] Ascend910_9362 / dav-2201 detected and documented
- [x] CMake, host, custom AIC/AIV kernels, run scripts and case generator implemented
- [x] Device-side group boundaries, empty groups, transpose and mixed BF16/FP32 bias exercised
- [x] Original 20 cases executed on physical device 3
- [x] Strict full-finite MERE/MARE re-audit passes all 20 cases
- [x] Final `results.json` rebuilt with 20 strict passing records
- [x] Profiling skipped per correctness-only request
- [x] Test gate skipped because `benchmarks/cannbench/AGENTS.md` sets `harness.test_gate: off`

Final audit evidence: `results.json` contains case IDs 1–20 exactly once, all 20 records have
`sample_stride=1` and `passed=true`, and the summary reports `executed_cases=20`,
`passed_cases=20`, `all_passed=true`. The executable was rebuilt for dav-2201 and every case
was produced by physical device 3 (`ASCEND_RT_VISIBLE_DEVICES=3`, program device 0).
