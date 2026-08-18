# quant_matmul state

- [x] Authoritative level3 specification and all 20 original cases reviewed
- [x] Ascend910_9362 / dav-2201 environment documented
- [x] Definition and design documents completed
- [x] CMake, standalone ACL host, custom AIC Cube kernel and AIV post kernel implemented
- [x] Deterministic case generation, runner, verifier, summarizer and binary produced
- [x] No host precomputation and no ACLNN substitute in the execution path
- [x] FP16, BF16, int32 pre-scale bias, BF16 post-scale bias, per-token scale, batch, decode, non-aligned K/N and 4096-cubed cases exercised
- [x] Original 20 cases executed on physical device 2
- [x] `results.json` reports 20/20 passed
- [x] Profiling skipped per correctness-only request
- [x] Test gate skipped because `benchmarks/cannbench/AGENTS.md` sets `harness.test_gate: off`

Final evidence: `results.json` contains case IDs 1 through 20 exactly once,
`executed_cases=20`, `passed_cases=20`, and `all_passed=true`. Cases 1-4, 7,
9-20 are bitwise equal to the FP64 golden after output cast. Per-token cases
5, 6 and 8 pass the full-tensor MERE/MARE standard; their only differences are
allowed FP32-vs-FP64 intermediate multiplication rounding. The executable is
compiled for dav-2201 and all results were generated with
`ASCEND_RT_VISIBLE_DEVICES=2` and program device 0.
