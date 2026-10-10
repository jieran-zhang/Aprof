---
name: ascendc-aprof-workflow
description: Run a bounded Ascend C optimization session with reusable preparation, one hypothesis and one candidate, exploratory device timing, and separate formal acceptance. Use for operator optimization or plan-only diagnosis.
---

# AProf Optimization Workflow

Treat the Agent as a proposer and `aprofctl` as the authority. Never promote a
candidate, assign terminal utility, or mutate the published SkillGraph from
natural-language judgment alone.

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
5. **Screen cheaply.** Predeclare representative and regression cases, warmup,
   repeat and stopping rules. Collect **six alternating AB/BA pairs** with a
   [persistent device-timing harness](../ascendc-aprof-profiling/references/prepared-timing.md). These observations are exploratory, with
   no formal verdict or training reward. Stop on clear regression. For a
   borderline/noisy result allow at most one extension whose size and decision
   rule were fixed before observing the screen; otherwise report inconclusive.
   Do not introduce a higher gain threshold that discards a possible valid 3%
   gain, or keep resampling until a gain appears.
6. **Verify the finalist.** Collect a **fresh**, independent set of at least
   thirty paired samples over the full declared workload; do not promote or
   concatenate screening samples. If timing supports proceeding, collect the
   hypothesis-relevant baseline/candidate mechanism evidence: ten recorded
   warmups and five independent captures, with runtime source replay. Reuse a
   baseline profile only when its frozen source, workload, hardware, tool,
   collector and measurement policy remain compatible. Full correctness and
   timing coverage do not require profiling every case. Formal CV, regression,
   95% speedup-LCB >= 1.03 and semantic/scope requirements remain unchanged.
7. **Close the record.** Validate the existing machine contracts and run the
   CAS-aware gate. Register artifacts once, retain one canonical candidate
   record referencing them, and derive the human summary from that record.
   When a compatible gate ran, finalize its exact result; otherwise retain
   `formal_admission=not_evaluated` as orchestration metadata without inventing
   an episode. Keep every failure, regression, inconclusive screen and NOOP.
   Only the runtime can select a production best.

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
- Write state and evidence under `<op_dir>/.aprof/`; never modify the release.
- Freeze the graph and any compatible behavior policy for the session. Record
  source/patch, plan, dispatch, profiler and measurement identities.
- Finalize an episode only from a compatible runtime gate; preserve unadmitted
  attempts and their failures as ordinary evidence. Raw JSON/JSONL does not
  establish verified training reward or formal admission.
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
