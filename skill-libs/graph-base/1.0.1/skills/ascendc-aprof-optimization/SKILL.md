---
name: ascendc-aprof-optimization
description: Instantiate a selected AProf transformation contract into an isolated Ascend C candidate. Use after evidence collection and SkillGraph routing to propose one bounded optimization intent, preserve action parameters and provenance, and submit the draft to the machine candidate gate. This skill cannot accept a candidate or update learned policy state.
---

# AscendC AProf Optimization

The [execution experience index](../../experience/optimization/execution/README.md)
points to scoped historical observations and counterexamples. Read a Wiki page
only when its conditions or failure case matter for this candidate. Check the
Wiki index for each rule's validation status and scope. Draft observations are
hypotheses; they do not supply graph predicates or policy rewards.

## Validated exp tile rule (910C/A3, CANN 9.0.0)

For the verified contiguous exp implementation with FP16, BF16 or FP32 inputs,
consider increasing `tileElements` from 4096 to 8192 when the legal
`transformation.coalesce_contiguous_transfers` route and current workload evidence
support reducing per-tile transfer/setup work. Preserve the selected parallel
plan, block ownership, exp/base/scale/shift semantics and dynamic tail handling.

Recompute UB lifetimes before applying the change. The validated implementation
uses 98,304 bytes of explicit UB for FP16/BF16 and 65,536 for FP32; account for
the selected SDK's temporary regions and address limits as well. Do not remove
tail masks, padding, dtype conversions or the existing general path. A shape,
implementation, toolchain or hardware change needs its own validation; 8192 is
not a universal optimum and this rule does not cover mish, addcdiv or 950.

Validate full declared correctness and tile/core boundary cases, then compare
fresh complete-call Task Duration samples under passing controls. Keep screen
samples separate, check every regression, and collect source-bound mechanism
profiles. Reuse prior evidence only when its exact sources, binary, inputs,
measurement protocol and raw checks remain valid; record resumed work separately.
See [the scoped Wiki evidence and rejected controls](../../wiki/exp-tile8192.md).

## Parallel-plan and dispatch boundary

Require validated architecture/parallel/dispatch evidence before stage-aware execution tuning. Bind their content hashes, selected workload group, tiling key and actual kernel entry. Set `optimization_stage=execution`; changing task partition, ownership, reduction or global algorithm returns to `ascendc-aprof-parallel-planning` with a new plan. Optimize and measure the selected region, then run the full correctness/regression matrix including fallback. A metadata guard with a general fallback is permitted; a case-ID shortcut or narrowed contract is benchmark specialization.

## Machine boundary

- Select an atomic transformation from the published SkillGraph and record its
  exact `skill_id`, contract version, selected edge, complete legal candidate
  set, and behavior probability.
- Treat the historical six-family routing documents as expert explanation and
  cold-start prior only. They are not the runtime selector or root-cause truth.
- Generate a candidate draft only. Do not emit `selected_as_best`, terminal
  utility, or a production verdict. Submit complete local evidence to the
  compatible online runtime gate within the task deadline.
- Preserve every attempted candidate. Post-task trace/training may finalize a
  versioned episode only when a compatible runtime gate ran; exploratory stops
  retain their record without a formal verdict or training reward.

Use this skill after `/ascendc-aprof-diagnosis` and `/ascendc-aprof-profiling` have produced source hypotheses, profiling data, or a final diagnosis. The target is a complete direct-invoke `op_dir`; raw kernel scaffolding stays in `/ascendc-kernel-direct-invoke`.

When interpreting the cold-start route, read [references/optimization-strategy-routing.md](references/optimization-strategy-routing.md). It documents the legacy expert prior; the published graph contract and policy remain authoritative.

For candidate generation, read [references/optimization-candidate-design.md](references/optimization-candidate-design.md) and then only the branch reference(s) for the selected `problem_family`. For complex MatMul, Softmax/FA, Reduction/Sort, or Vector/Scalar pipeline cases, additionally load exactly one matching operator playbook from this skill.

## Required Inputs

- `op_dir`: complete local Ascend C direct-invoke project.
- Optional `diagnosis_hypotheses.json` or `single_case_diagnosis.json`.
- Optional `profiling_results.json` or report directory.
- Optional `execution_context.build_cmd`, `verify_cmd`, and `profile_cmd`.

## Workflow

1. Require a valid session **EnvironmentPreflight** before local execution; reuse it while its device/toolchain inputs remain unchanged. Preserve live execution identity checks. Use `ascendc-env-check` for missing or changed CANN env, device visibility, SoC/NPU arch and profiler readiness.
2. Read the selected transformation contract from the immutable graph snapshot and generate a draft plan. Include diagnosis/profiling links, source anchors, action parameters, capacity model, abort conditions, and exact graph/policy/contract versions.
3. Use the graph route selected from current evidence. Use diagnosis facets, profiling bound, and source scan only to construct the expert prior or explain missing evidence; preserve the full candidate set and behavior probability.
4. Reuse the validated workload model and frozen parallel plan. Revisit only affected capacity/tiling assumptions; load additional references or `npu-arch` when their evidence is missing or changed.
5. Apply **CorrectnessAndGeneralityGate** before patching: default scope is `production_safe`; preserve operator math, dtype precision, dynamic shape/tiling, tail handling, and boundary safety.
6. Create one candidate by default: copy the selected immutable parent `op_dir` into `aprof_opt/candidates/candidate_N/op/`, record its source hash and selection evidence in `candidate_plan.json`, and derive any Markdown summary from that record. Rebind the candidate dispatch implementation identity while preserving the unchanged plan basis.
7. Modify only files under `aprof_opt/candidates/candidate_N/op/`. Never edit the baseline `op_dir`.
8. For each candidate, apply exactly one strategy from `candidate_plan.json`; one strategy may still require coordinated multi-line edits such as loop restructuring, buffer lifetime changes, Host Tiling updates, workspace slot changes, or API fusion.
9. Before risky API, pipeline, MatMul, Softmax, Sort, or DataCopy edits, first use the selected family reference plus at most one operator playbook. Use [references/optimization-local-knowledge-index.md](references/optimization-local-knowledge-index.md) only if local references do not settle the mechanism.
10. After patching and before build, run **StaticReview** focused on API legality, UB/L1/L0/workspace bounds, DataCopy alignment, pipeline ordering, portability, and performance clauses.
11. Build and verify the complete correctness matrix for this changed source, then follow the main workflow's exploratory screen. Stop failures and clear regressions before full profiling. Only an advancing candidate receives fresh full-coverage formal timing and the missing mechanism captures; screening samples stay separate.
12. For Task v5 `local_profile_only`, submit complete task-local evidence
    to compatible online admission before the deadline, then return code, a small
    report. Use the local index for online tools or a requested collection handoff.
    Full correctness, Task parsing and
    controls remain budgeted. The optimization Agent does not perform permanent
    profile copying, CAS registration or archival replay. Optional post-task
    trace/training owns those operations and reports their cost separately.
    Development installation is not hardware qualification. Without a compatible
    local gate retain admission as not evaluated. Never let later archiving change a failure or timeout.
13. Copy or report `best_op` only when the runtime returns a production-safe accepted verdict.

## Context-safe optimization

- Do not add large unrelated optimization/design/API skills to the default optimization agent context.
- Default reads are this `SKILL.md`, [references/optimization-strategy-routing.md](references/optimization-strategy-routing.md), [references/optimization-candidate-design.md](references/optimization-candidate-design.md), and 1 selected branch reference.
- When one candidate spans a complex operator mechanism, load exactly one operator playbook:
  - MatMul / GMM / BatchMatMul / GroupMatMul: [references/matmul-optimization-playbook.md](references/matmul-optimization-playbook.md)
  - Softmax / FlashAttention / paged or sparse attention: [references/softmax-fa-optimization-playbook.md](references/softmax-fa-optimization-playbook.md)
  - Reduction / Sort / TopK / Argsort: [references/reduction-sort-optimization-playbook.md](references/reduction-sort-optimization-playbook.md)
  - Elementwise / Broadcast / Conversion / Vector-Scalar pipeline: [references/vector-scalar-pipeline-playbook.md](references/vector-scalar-pipeline-playbook.md)
- Do not load more than one operator playbook for a single candidate unless the user explicitly asks for broad design exploration.
- Load AProf local distilled references only through `optimization-local-knowledge-index.md`, and only one precise reference at a time.
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
- Research search follows the main workflow's shared-context and shared-buffer
  screen against the selected parent: six fresh process cycles, five pairs per
  cycle, with pre/post A/A controls. Full-case correctness remains mandatory.
  Failed controls stop the attempt; preserve inconclusive results without
  appending replacement samples. No additional gain filter replaces the formal gate.
  Final timing is a fresh full-case run, followed by mechanism evidence for an
  advancing candidate. Screening never establishes formal admission or reward.
- Profiling evidence must include warmup/repeat statistics; single-run results are exploratory.
- Simulator metrics are proxy evidence; do not present them as real `Memory.csv` / `PipeUtilization.csv`.
- Production best selection requires `semantic_status=preserved`, `scope_status=production_safe`, `portability_risk != high`, and `accepted_for` containing `production`.
- A fixed tile or other tuning parameter is not automatically benchmark
  specialization when validated semantics, workload domain, capacities and
  fallback remain intact. Mark `benchmark_specialized` when case-ID shortcuts,
  unverified fixed assumptions or removed dynamic handling narrow the contract,
  precision or supported boundaries. Report such results separately; do not
  copy them to `best_op` by default.
- Preserve failed compile/API attempts with the first failure, evidence, patch
  hash and handoff. They become typed negative episodes only when a compatible
  runtime gate actually ran; otherwise retain ordinary unadmitted records.
- Accuracy failure hands off to `ascendc-precision-debug`.
- Runtime nonzero/error-code failure hands off to `ascendc-runtime-debug`.
- Timeout, hang, crash, illegal access, or AIC error hands off to `ascendc-crash-debug`.
- Profile artifact/metric gaps hand off to `ops-profiling`.
- A formal regression is finalized from the gate result. A screening regression
  remains exploratory evidence; another candidate requires remaining scope and budget.

## Outputs

- Draft candidate plan: selected transformation, source anchors, expected benefit/risk, evidence linkage, parameters, checks, and exact versions.
- Runtime gate outcome: per-candidate state path, semantic/scope/portability status, before/after evidence, utility, failure reason, and handoff.
- Task-local candidate record and evidence index: source/route identities, exact online outcome, actual costs, local artifacts and handoff. Preserve failures and partial files. Post-task trace/training owns optional verified episode import; legacy `optimization_memory.jsonl` remains read-only and unverified.
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

Use the versioned files under repository `schemas/` as the machine contracts. Read `../../references/contracts.md` only when adapting legacy artifacts.
