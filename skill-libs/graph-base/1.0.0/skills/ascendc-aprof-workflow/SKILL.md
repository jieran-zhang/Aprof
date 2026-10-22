---
name: ascendc-aprof-workflow
description: Run a bounded Ascend C optimization session with reusable preparation, one hypothesis and one candidate, exploratory device timing, and separate formal acceptance. Use for operator optimization or plan-only diagnosis.
---

# AProf Optimization Workflow

Treat the Agent as a proposer and `aprofctl` as the authority. Never promote a
candidate, assign terminal utility, or mutate the published SkillGraph from
natural-language judgment alone.

## Stage and knowledge routing

Follow architecture and semantics → diagnosis/profiling → algorithm and parallel
planning → execution optimization → validation/feedback. A change to algorithm,
task ownership, reduction, synchronization or workspace returns to parallel
planning; tile, buffer, transfer and pipeline tuning inherit its frozen plan.
The published v0002 graph still determines legal transformations.

Keep the active workload, code, latest feedback and budget in the immediate
context. Load the selected stage skill and one relevant reference next. When
its applicability is unclear, evidence conflicts, or a concrete counterexample
could change the decision, consult one entry from [the Wiki index](../../wiki/index.json)
and return to the graph route. Check each page's status and hardware scope in
the index. Draft observations may refine a hypothesis or reveal a missing check;
independently validated rules are distilled into the named stage skill. Neither can
activate a graph predicate, bypass a hard mask or establish a performance gain.
The grouped reading map is under `../../experience/`.

## Required inputs

当前重点支持 **Vector 算子、Ascend 910C（A3）**。源码可用于静态诊断；
执行优化需要完整工程。按下列模板收集已有字段，未知项明确标注：

```yaml
op_dir: <完整 Ascend C 工程路径；或 kernel_source / kernel_path 供 scaffold>
operator_context:
  name: <算子名>
  cases: <shape、dtype、layout、属性、输入输出及正确性容差>
execution_context:
  architecture: 910C  # A3；仍须核对实际 SoC，不能仅凭 DAV_2201 推断
  device: 0
  build_cmd: [<构建程序>, <参数>]
  verify_cmd: [<完整 case 集合的正确性程序>, <参数>]
  run_cmd: [<已构建的目标程序>, <参数>]
budget: {candidate_limit: 1, build_limit: 1, timing_limit: 1, full_profile_limit: 1}
constraints: <目标、执行范围及其他限制>
```

`operator_context` / `execution_context` 是交互输入；进入 runtime 时把工作负载
映射为 `Context.workload`，设备身份映射为 `hardware_fingerprint`，采集及
命令证据放入 `Context.evidence`。它们不是新的 Context 顶层字段。
Profiling 按架构路由：支持的 950/dav-3510 环境优先 npu-compute；当前
910C/A3 使用 msprof。工具支持 950 不代表本库已验证全部 950 算子优化能力。

- Require a complete `op_dir` before optimization. Hand raw kernels to
  `ascendc-kernel-direct-invoke` first.
- Record operator shapes, dtypes, layouts, SoC/CANN identity, build command,
  correctness command, and profiling command when available.
- Express observable limits as `candidate_limit`, `build_limit`, `timing_limit`,
  and `full_profile_limit`. These count candidate episodes that reach each
  stage, not individual warmups or profiler launches. Never start work that
  cannot fit the remaining budget.
- Treat the baseline tree as read-only. Create every patch in an isolated
  candidate directory.

## Default session

Use **one coordinator, one testable hypothesis and one isolated candidate**.
The skills and wrappers describe responsibilities; they are not a mandatory
sequence of separate agents. Delegate a bounded implementation or review only
when it helps. Expand the candidate budget only within the user's scope.

1. **Prepare once.** Preserve the operator contract, workload/input identities,
   baseline source, build and full correctness evidence. Reuse verified session
   preparation and architecture evidence while their inputs remain unchanged.
   Recheck actual device/tool identity at execution; do not cache away collector
   identity checks. Keep input generation outside timing.
2. **Choose one hypothesis.** Use source and workload evidence first; preserve
   alternatives and missing evidence. Defer full profiling by default. If a
   legal graph route needs missing predicate evidence, collect the minimum valid
   diagnostic evidence before editing; use the full capture requirements when
   that evidence needs formal provenance. An unavailable extractor stays
   unavailable: preserve the source, interpretation and threshold, and retain
   unknown when the predicate contract cannot be satisfied. A source story or
   quick timing improvement cannot establish a mechanism predicate. Six legacy
   families remain nonexclusive facets.
3. **Reuse or establish the plan.** Validate architecture, parallel and dispatch
   artifacts once for the selected algorithm. Execution tuning inherits the
   frozen plan and metadata group/key/entry with a general fallback. Rebind
   dispatch implementation identity to each candidate's source; an unchanged
   dispatch rule does not justify a stale source hash. New algorithm,
   decomposition, ownership or reduction returns to parallel planning and uses
   `optimization_stage=algorithm_parallel`; otherwise use `execution`.
4. **Implement and check.** Route on the immutable graph, retaining the legal
   candidate set, masks, edge and behavior probability. Apply one intent in an
   isolated copy, then static review, build and **full declared correctness for
   every changed candidate**, including other groups, boundaries and fallback.
   Stop at the first mandatory failure; do not spend profiling budget on it.
   If missing evidence leaves no legal action, report `needs_evidence` in the
   session record or select the graph's NOOP. An explicitly authorized source
   experiment outside a legal route remains unadmitted: preserve its actual
   evidence without fabricating an edge, episode or production best.
5. **Screen representative cases.** Predeclare representative and regression
   cases and stopping rules. Use the
   [shared-buffer timing protocol](../ascendc-aprof-profiling/references/shared-timing.md):
   six fresh processes, five pairs per process, and the required A/A controls.
   For qualified 910C/A3 calls, use complete Task Duration groups as the primary
   metric; preserve Event and Host measurements as auxiliary scope checks.
   These observations have no formal verdict or training reward. Stop on a
   failed control, clear regression or unresolved uncertainty; preserve every
   attempted measurement. Do not extend a failed control session.
   Do not introduce a higher gain threshold that discards a possible valid 3%
   gain, or keep resampling until a gain appears.
6. **Verify the finalist.** Collect a **fresh**, independent set of at least
   thirty paired samples with new pre/post A/A controls over the full declared
   workload; do not promote or
   concatenate screening samples. If timing supports proceeding, collect the
   hypothesis-relevant baseline/candidate mechanism evidence: ten recorded
   warmups and five independent captures, with runtime source replay. Reuse a
   baseline profile only when its frozen source, workload, hardware, tool,
   collector and measurement policy remain compatible. Full correctness and
   timing coverage do not require PMU mechanism capture for every case. Formal CV, regression,
   95% speedup-LCB >= 1.03 and semantic/scope requirements remain unchanged.
7. **Close the local record.** Run compatible online admission against the
   complete task-local evidence within the remaining task budget. Return the
   candidate code and a small report with the exact machine result. The local
   evidence index is an online tool input and an optional collection handoff,
   not an extra permanent deliverable. The optimization Agent does not copy profiles to permanent
   storage, register full artifacts in CAS, or perform archival replay.
   When a compatible gate ran, record its exact result; otherwise retain
   `formal_admission=not_evaluated` as orchestration metadata without inventing
   an episode. Keep every failure, regression, inconclusive screen and NOOP.
   Only the runtime can select a production best.

   Run `tools/aprofctl episode finalize --context context.json --request request.json
   --graph skillgraph/versions/v0002 --local-index local-index.json` from the
   release root, adding `--policy` when routing used a policy checkpoint. The
   local index must cover every referenced measurement, mechanism and source
   artifact. This performs the same route and machine gate checks, returns the
   computed episodes with `store_sequences=[]`, and does not append or archive.

For each feedback round, bind the actual `source_parent`, original baseline,
candidate source/patch, full declared correctness, direct-parent and
original-baseline comparison identities, and actual build/timing/profile,
wall-clock and model-token costs. A parent-child link records lineage, not a
causal speedup; do not multiply results from separate measurement protocols.

For additional authorized rounds, retain the validated parent and lineage;
reuse preparation and unchanged plans, then repeat candidate-specific checks.
An exploratory parent is not a production best. Record actual elapsed costs;
this workflow makes no measured 20–30 minute completion claim. Detailed reuse
and handoff rules are in [workflow details](../../workflows/references/workflow-details.md).

## Package and evidence boundary

Resolve this release as the directory two levels above this skill. Its
`tools/aprofctl` launcher selects the accompanying runtime. Use its
`skillgraph/versions/v0002` for new stage-aware sessions, and preserve `v0001`
for compatible historical episodes. Use [the package guide](../../README.md)
for installation and [stage handoff details](../../workflows/references/workflow-details.md)
when coordinating agents.

- The caller supplies workload coverage, execution commands, measurement policy
  and budget. Preserve all-case correctness and label measurements by their
  actual protocol, uncertainty and comparison parent.
- For proposed `shared_buffer_msprof_task_window_v4` / `local_profile_only`,
  keep work and required evidence in private task-local storage during execution
  and online admission; never modify the release. Without a verified stable
  release manifest, V4 remains unqualified and does not change the default.
- Freeze the graph and any compatible behavior policy for the session. Record
  source/patch, plan, dispatch, profiler and measurement identities.
- Post-task trace/training may finalize an episode only from a compatible
  runtime gate; preserve unadmitted attempts and their failures as ordinary evidence. Raw JSON/JSONL does not
  establish verified training reward or formal admission.
- After returning code and the small report, delete the temporary directories
  created for this task. If trace/training collection was explicitly requested,
  hand off the complete local evidence and index before cleanup. That collector
  may copy, register, archive and independently audit the evidence. Report this cost separately from the
  optimization budget. Build, correctness, complete Task parsing, controls and
  online admission stay inside that budget; moving them after the deadline would
  change the result. A post-task archive never changes an earlier failure.
- Exporting, curating or training on session evidence is a caller-owned process.
  Do not load dataset lessons, injected labels or benchmark histories as online
  skill knowledge. Publish validated knowledge changes in a new release.

## Stop conditions

- Stop at a validated plan when execution is not authorized or required tools
  are unavailable.
- Stop a candidate after the first failed mandatory gate. Finalize a typed
  negative episode only for a compatible gate execution; otherwise retain the
  failed attempt and its raw evidence without a graph episode.
- Select `NOOP` when no transformation satisfies evidence, applicability,
  capacity, or safety constraints.
