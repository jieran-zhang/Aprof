# CrossEntropyLoss flash state
- Source: `third_party/cann-bench/tasks/level2/cross_entropy_loss`
- Target: Ascend910 / dav-2201
- [x] Definition/design recorded
- [x] Standalone direct invocation implemented for hard-label original cases
- [x] Real-NPU build verified
- [x] Original cases 1-20 passed
- [x] `harness.test_gate=off`; skipped by configuration
- Profiling/optimization/review skipped; dirty worktree not committed.

## Evidence
- Build: `build/cross_entropy_loss`, 440536 bytes, SHA-256
  `865bea24c75964d37e7ddc46217b9a4f8a2a5b4b561bbc448308efe528fbcf63`
- Hardware: Ascend910 / dav-2201, real NPU device 1
- Results: `results.json` reports `total_cases=20`, `passed_cases=20`, `all_passed=true`
- Per-case evidence: `build/cases/case_01/result.json` through
  `build/cases/case_20/result.json`
