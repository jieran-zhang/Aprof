---
name: ascendc-aprof-optimization
description: Ascend C kernel 自动性能优化 Skill。用于在 AProf diagnosis/profiling 之后，把六类问题族映射到多算子族优化策略，生成 production-safe 或 benchmark-specialized candidate，复制候选 op_dir，本地编译、精度验证、msprof/profile 对比，并维护 optimization_memory.jsonl。
---

# AscendC AProf Optimization

Use this skill after `/ascendc-aprof-diagnosis` and `/ascendc-aprof-profiling` have produced source hypotheses, profiling data, or a final diagnosis. The target is a complete direct-invoke `op_dir`; raw kernel scaffolding stays in `/ascendc-kernel-direct-invoke`.

When selecting or applying strategies, read [references/optimization-strategy-routing.md](references/optimization-strategy-routing.md). It is the contract between the diagnosis six-family entry and the optimization candidate loop.

For candidate generation, read [references/optimization-candidate-design.md](references/optimization-candidate-design.md) and then only the branch reference(s) for the selected `problem_family`. For complex MatMul, Softmax/FA, Reduction/Sort, or Vector/Scalar pipeline cases, additionally load exactly one matching operator playbook from this skill.

## Required Inputs

- `op_dir`: complete local Ascend C direct-invoke project.
- Optional `diagnosis_hypotheses.json` or `single_case_diagnosis.json`.
- Optional `profiling_results.json` or report directory.
- Optional `execution_context.build_cmd`, `verify_cmd`, and `profile_cmd`.

## Workflow

1. Run or require **EnvironmentPreflight** before local execution: use `ascendc-env-check` to confirm CANN env, device visibility, SoC/NPU arch, and `msprof`/`cannsim` availability.
2. Generate `aprof_opt/optimization_plan.json` as an agent artifact. The plan must include selected strategy entries, diagnosis/profiling links, source anchors, capacity model, abort conditions, gate commands, and memory path.
3. Route strategies in this order: diagnosis `problem_family` first, profiling bound second, source scan last. Preserve `linked_hypotheses` and `linked_metrics`.
4. Before candidate generation, do **Workload/Tiling/Bound Modeling** with AProf local references, `workload-aware-diagnosis.md`, `roofline-single-case.md`, and `npu-arch` where available.
5. Apply **CorrectnessAndGeneralityGate** before patching: default scope is `production_safe`; preserve operator math, dtype precision, dynamic shape/tiling, tail handling, and boundary safety.
6. If candidates should be created, copy the baseline `op_dir` into `aprof_opt/candidates/candidate_N/op/` and write `candidate_plan.json` / `candidate_plan.md` for each selected strategy.
7. Modify only files under `aprof_opt/candidates/candidate_N/op/`. Never edit the baseline `op_dir`.
8. For each candidate, apply exactly one strategy from `candidate_plan.json`; one strategy may still require coordinated multi-line edits such as loop restructuring, buffer lifetime changes, Host Tiling updates, workspace slot changes, or API fusion.
9. Before risky API, pipeline, MatMul, Softmax, Sort, or DataCopy edits, first use the selected family reference plus at most one operator playbook. Use [references/optimization-cannbot-knowledge-index.md](references/optimization-cannbot-knowledge-index.md) only if local references do not settle the mechanism.
10. After patching and before build, run **StaticReview** focused on API legality, UB/L1/L0/workspace bounds, DataCopy alignment, pipeline ordering, portability, and performance clauses.
11. Run gates in order: build, accuracy, profile, measurement stability, correctness/generality acceptance.
12. Record `candidate_result.json`, append `optimization_memory.jsonl`, and write `final_optimization_report.md`.
13. Select `aprof_opt/best_op` only when accuracy passes, measurement is stable, metric improves over baseline, and `scope_status=production_safe`.

## Context-safe optimization

- Do not add large CANNBot optimization/design/API skills to the default optimization agent context.
- Default reads are this `SKILL.md`, [references/optimization-strategy-routing.md](references/optimization-strategy-routing.md), [references/optimization-candidate-design.md](references/optimization-candidate-design.md), and 1 selected branch reference.
- When one candidate spans a complex operator mechanism, load exactly one operator playbook:
  - MatMul / GMM / BatchMatMul / GroupMatMul: [references/matmul-optimization-playbook.md](references/matmul-optimization-playbook.md)
  - Softmax / FlashAttention / paged or sparse attention: [references/softmax-fa-optimization-playbook.md](references/softmax-fa-optimization-playbook.md)
  - Reduction / Sort / TopK / Argsort: [references/reduction-sort-optimization-playbook.md](references/reduction-sort-optimization-playbook.md)
  - Elementwise / Broadcast / Conversion / Vector-Scalar pipeline: [references/vector-scalar-pipeline-playbook.md](references/vector-scalar-pipeline-playbook.md)
- Do not load more than one operator playbook for a single candidate unless the user explicitly asks for broad design exploration.
- Load CANNBot original docs only through `optimization-cannbot-knowledge-index.md`, and only one precise reference at a time.
- External docs can justify API parameters, platform boundaries, contraindications, and gate checks; they must not replace AProf diagnosis/profiling evidence.

## Strategy Routing

Route diagnosis problem families to these local references:

| Problem family | Strategy | Load when implementing |
| --- | --- | --- |
| `tiling` | Task/tile/shape decomposition, tail unification, MatMul/FA split choices | [references/tiling-optimization-strategies.md](references/tiling-optimization-strategies.md) |
| `data_movement` | DataCopy coalescing, DataCopyPad, GM traffic reduction, L2/reuse handling | [references/data-movement-optimization-strategies.md](references/data-movement-optimization-strategies.md) |
| `pipeline_parallel` | Double-buffer, prolog/steady/drain rewrite, event decoupling, pingpong gap repair | [references/pipeline-parallel-optimization-strategies.md](references/pipeline-parallel-optimization-strategies.md) |
| `onchip_memory` | UB/L1/L0 resident reuse, buffer lifetime, bank/layout, workspace slot design | [references/onchip-memory-optimization-strategies.md](references/onchip-memory-optimization-strategies.md) |
| `ai_core_utilization` | Task decomposition, load balance, split-K/FA decode/Sort/Reduction parallelism | [references/ai-core-utilization-optimization-strategies.md](references/ai-core-utilization-optimization-strategies.md) |
| `api_algorithm` | Scalar/vector/API rewrite, Cast/reduce/softmax/sort/matmul local algorithms | [references/api-algorithm-optimization-strategies.md](references/api-algorithm-optimization-strategies.md) |

For the full routing matrix, including trigger signals, required evidence, expected metric movement, contraindications, gate checks, and failure handoff, read `references/optimization-strategy-routing.md`.

## Operator Playbooks

Use these only after the six-family branch is selected:

| Operator family | Load when | Reference |
| --- | --- | --- |
| MatMul / GMM | SWAT, FullLoad, StreamK, MTE2 preload, L1/L0/Fixpipe decisions are candidate-relevant | [references/matmul-optimization-playbook.md](references/matmul-optimization-playbook.md) |
| Softmax / FA | online state, S2/D tiling, state resident, split-KV, or LSE/partial O combine is candidate-relevant | [references/softmax-fa-optimization-playbook.md](references/softmax-fa-optimization-playbook.md) |
| Reduction / Sort | Welford/Group Reduce/with-index or two-level MrgSort/TopK workspace is candidate-relevant | [references/reduction-sort-optimization-playbook.md](references/reduction-sort-optimization-playbook.md) |
| Vector / Scalar pipeline | Cast/repeat/Counter mode, UB fusion, broadcast/conversion, DB, scalar hot-loop, or no-bound bubble is candidate-relevant | [references/vector-scalar-pipeline-playbook.md](references/vector-scalar-pipeline-playbook.md) |

## Gates

- Build must pass before accuracy.
- Accuracy must pass before profiling.
- Profiling evidence must include warmup/repeat statistics; single-run results are exploratory.
- Simulator metrics are proxy evidence; do not present them as real `Memory.csv` / `PipeUtilization.csv`.
- Production best selection requires `semantic_status=preserved`, `scope_status=production_safe`, `portability_risk != high`, and `accepted_for` containing `production`.
- Mark candidates as `benchmark_specialized` when they hardcode shape/core/UB/tile values, remove dynamic tiling, reduce precision, or narrow supported boundaries. Report their speedup separately; do not copy them to `best_op` by default.
- Failed compile/API attempts are valuable memory. Append them to `optimization_memory.jsonl` with `status=failed` and the concise failure reason.
- Accuracy failure hands off to `ascendc-precision-debug`.
- Runtime nonzero/error-code failure hands off to `ascendc-runtime-debug`.
- Timeout, hang, crash, illegal access, or AIC error hands off to `ascendc-crash-debug`.
- Profile artifact/metric gaps hand off to `ops-profiling`.
- Metric regression is recorded in memory and the loop moves to the next candidate.

## Outputs

- `optimization_plan.json`: strategy list, source anchors, expected benefit/risk, diagnosis linkage, bound type, checks, command plan, memory path.
- `candidate_result.json`: per-candidate gate status, semantic/scope/portability status, changed files, before/after metric, measurement evidence, speedup, failure reason, failure handoff.
- `optimization_memory.jsonl`: long-lived records keyed by op, shape, dtype, soc, problem family, strategy, status, metric, and handoff.
- `final_optimization_report.md`: production-safe best candidate, metric evidence summary, and faster rejected/benchmark-only candidates with reasons.

See `skills/aprof/references/contracts.md` for exact JSON contracts.
