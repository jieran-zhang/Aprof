---
name: ascendc-aprof-optimization
description: Instantiate a selected AProf transformation contract into an isolated Ascend C candidate. Use after evidence collection and SkillGraph routing to propose one bounded optimization intent, preserve action parameters and provenance, and submit the draft to the machine candidate gate. This skill cannot accept a candidate or update learned policy state.
---

# AscendC AProf Optimization

## Machine boundary

- Select an atomic transformation from the published SkillGraph and record its
  exact `skill_id`, contract version, selected edge, complete legal candidate
  set, and behavior probability.
- Treat the historical six-family routing documents as expert explanation and
  cold-start prior only. They are not the runtime selector or root-cause truth.
- Generate a candidate draft only. Do not emit `selected_as_best`, terminal
  utility, or a production verdict. Submit evidence to `aprofctl candidate gate`.
- Finalize every attempted candidate, including early failures and stable
  regressions, as a versioned episode. Do not update flat optimization memory as
  training authority.

Use this skill after `/ascendc-aprof-diagnosis` and `/ascendc-aprof-profiling` have produced source hypotheses, profiling data, or a final diagnosis. The target is a complete direct-invoke `op_dir`; raw kernel scaffolding stays in `/ascendc-kernel-direct-invoke`.

When interpreting the cold-start route, read [references/optimization-strategy-routing.md](references/optimization-strategy-routing.md). It documents the legacy expert prior; the published graph contract and policy remain authoritative.

For candidate generation, read [references/optimization-candidate-design.md](references/optimization-candidate-design.md) and then only the branch reference(s) for the selected `problem_family`. For complex MatMul, Softmax/FA, Reduction/Sort, or Vector/Scalar pipeline cases, additionally load exactly one matching operator playbook from this skill.

## Required Inputs

- `op_dir`: complete local Ascend C direct-invoke project.
- Optional `diagnosis_hypotheses.json` or `single_case_diagnosis.json`.
- Optional `profiling_results.json` or report directory.
- Optional `execution_context.build_cmd`, `verify_cmd`, and `profile_cmd`.

## Workflow

1. Run or require **EnvironmentPreflight** before local execution: use `ascendc-env-check` to confirm CANN env, device visibility, SoC/NPU arch, and `msprof`/`cannsim` availability.
2. Read the selected transformation contract from the immutable graph snapshot and generate a draft plan. Include diagnosis/profiling links, source anchors, action parameters, capacity model, abort conditions, and exact graph/policy/contract versions.
3. Use the graph route selected from current evidence. Use diagnosis facets, profiling bound, and source scan only to construct the expert prior or explain missing evidence; preserve the full candidate set and behavior probability.
4. Before candidate generation, do **Workload/Tiling/Bound Modeling** with AProf local references, `workload-aware-diagnosis.md`, `roofline-single-case.md`, and `npu-arch` where available.
5. Apply **CorrectnessAndGeneralityGate** before patching: default scope is `production_safe`; preserve operator math, dtype precision, dynamic shape/tiling, tail handling, and boundary safety.
6. If candidates should be created, copy the baseline `op_dir` into `aprof_opt/candidates/candidate_N/op/` and write `candidate_plan.json` / `candidate_plan.md` for each selected strategy.
7. Modify only files under `aprof_opt/candidates/candidate_N/op/`. Never edit the baseline `op_dir`.
8. For each candidate, apply exactly one strategy from `candidate_plan.json`; one strategy may still require coordinated multi-line edits such as loop restructuring, buffer lifetime changes, Host Tiling updates, workspace slot changes, or API fusion.
9. Before risky API, pipeline, MatMul, Softmax, Sort, or DataCopy edits, first use the selected family reference plus at most one operator playbook. Use [references/optimization-cannbot-knowledge-index.md](references/optimization-cannbot-knowledge-index.md) only if local references do not settle the mechanism.
10. After patching and before build, run **StaticReview** focused on API legality, UB/L1/L0/workspace bounds, DataCopy alignment, pipeline ordering, portability, and performance clauses.
11. Submit draft and collected evidence to the machine gate. Do not reproduce gate authority in prose.
12. Register every referenced object in the task-local CAS. Finalize with
    `aprofctl episode finalize --graph <snapshot>` and the exact behavior
    `--policy` when applicable, under `<op_dir>/.aprof/`.
13. Copy or report `best_op` only when the runtime returns a production-safe accepted verdict.

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

## Expert-prior lookup

Use non-exclusive diagnosis facets to find human guidance for the graph-selected mechanism and transformation:

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

Use these only after a mechanism and transformation are selected; load at most one matching playbook:

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
- Failed compile/API attempts are valuable typed negative episodes. Preserve the first failed gate, evidence, patch hash, and failure handoff in the append-only episode store.
- Accuracy failure hands off to `ascendc-precision-debug`.
- Runtime nonzero/error-code failure hands off to `ascendc-runtime-debug`.
- Timeout, hang, crash, illegal access, or AIC error hands off to `ascendc-crash-debug`.
- Profile artifact/metric gaps hand off to `ops-profiling`.
- Stable metric regression is finalized as a negative episode and the session may route to the next candidate.

## Outputs

- Draft candidate plan: selected transformation, source anchors, expected benefit/risk, evidence linkage, parameters, checks, and exact versions.
- Runtime gate outcome: per-candidate state path, semantic/scope/portability status, before/after evidence, utility, failure reason, and handoff.
- `.aprof/` episode state: append-only, versioned candidate attempts with route propensity, gate outcomes, hashes, metrics, and handoff. Legacy `optimization_memory.jsonl` is read-only and unverified.
- For v0001 exploration, a separate versioned handler sidecar: handler ID and
  version, exact parameters, shape/profile context buckets, parent attempt,
  typed failure signature, and why the next step chose a sibling handler,
  sibling transformation, evidence recollection, or debug handoff. A terminal
  stop remains the typed episode outcome plus absence of a child until an
  explicit transition contract is published. Do not
  add these fields silently to the strict v1 episode schema. Serialize it as
  the shape-validated `handler_attempt` exploration contract and validate with
  `aprofctl contract validate --kind handler_attempt`. It is not an attested
  policy-training input.
- `final_optimization_report.md`: production-safe best candidate, metric evidence summary, and faster rejected/benchmark-only candidates with reasons.

Use the versioned files under repository `schemas/` as the machine contracts. Read `skills/aprof/references/contracts.md` only when adapting legacy artifacts.
