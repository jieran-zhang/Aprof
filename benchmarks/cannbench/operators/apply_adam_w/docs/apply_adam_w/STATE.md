# ApplyAdamW state

- Source: `third_party/cann-bench/tasks/level2/apply_adam_w`
- Target: Ascend910 / dav-2201
- [x] Standalone direct-invocation CMake, host, kernel, runner, and verifier implemented
- [x] Real-NPU build verified (`build/apply_adam_w`, CANN 9.0.0)
- [x] Original cases 1-20 correctness verified (20/20 passed)
- [x] Existing performance collection retained (operator score `73.18754129597957`)
- [x] Review completed with PASS, score 92/100

## Evidence

- Aggregate correctness and performance: `results.json`
- Precision summary: `docs/precision/summary.txt`
- Performance summary: `docs/perf/round_003/summary.txt`
- Review: `docs/REVIEW.md`
- Design and implementation notes: `docs/DESIGN.md`, `docs/WALKTHROUGH.md`
