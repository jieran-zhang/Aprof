---
name: ascendc-aprof-workflow
description: Diagnose and optimize an Ascend C operator using architecture-aware planning, profiling, isolated candidates and machine validation. Use for an operator optimization session or a plan-only diagnosis.
---

# AProf Optimization Workflow

Treat the Agent as a proposer and `aprofctl` as the authority. Never promote a
candidate, assign terminal utility, or mutate the published SkillGraph from
natural-language judgment alone.

## Required inputs

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

## Workflow

1. Preserve the full operator contract, workload metadata and baseline source hash. Run the bundled environment preflight and `npu-arch`; record actual SoC/ISA, SDK, visible resources and unknown capabilities. Do not infer 910B versus 910C from the shared 2201 ISA enum.
2. Use `ascendc-aprof-diagnosis` to construct source/workload evidence and collect only missing profile views with `ascendc-aprof-profiling`. Preserve ambiguity; six legacy families remain nonexclusive evidence facets.
3. Run **algorithm parallel planning** with `ascendc-aprof-parallel-planning`: compare legal algorithms, partitions, ownership, reduction/synchronization and workspace per workload group. Validate `architecture_profile` and `parallel_plan`. Any algorithm implementation candidate uses `optimization_stage=algorithm_parallel` and the normal gates.
4. Create and validate `dispatch_plan` for metadata → workload group → uint64 tiling key → actual kernel entry, with a general fallback. Implement equivalent host/kernel dispatch for the project's registered or direct-launch mode; trace-only keys do not satisfy this stage. Verify overlap, boundary and unseen-metadata behavior.
5. Freeze the selected parallel plan and dispatch. Bind all three artifact objects and canonical hashes in `Context.evidence`, and use `optimization_stage=execution` for **execution optimization**. A new decomposition/ownership/reduction returns to parallel planning. Route on the immutable stage-aware graph snapshot; retain full legal candidate set, hard-mask reasons, selected edges and actual behavior probability.
6. Use `ascendc-aprof-optimization` to instantiate one selected execution intent per isolated candidate, scoped to the selected group/key. Tile size, buffer depth, memory movement and pipeline scheduling are evaluated under the frozen algorithm plan. Test the complete correctness contract and all other regions/fallback for regression.
7. Submit supported runtime contracts through `aprofctl contract validate`, then run `aprofctl candidate gate` in the declared gate order. Profiling plan/result, stage report, timing and symptom files are drafts until mapped into runtime evidence; planning JSON has its own strict contract kinds. Stop a candidate at the first mandatory failure.
8. Register source, patch, plan/profile/dispatch and evidence objects in the task CAS. When a compatible runtime gate actually ran, finalize with `aprofctl episode finalize --graph <snapshot>` and the exact behavior `--policy` if used. When no compatible gate ran, retain the source, measurements, verification and failure evidence with admission explicitly not evaluated; do not invent an episode or a production-best verdict. Preserve every failed, regressed and NOOP attempt, stage labels, per-group results, parent lineage and budget.
9. For requested consecutive rounds, seed the next round from the selected previous parent that passed correctness and runtime validation, with explicit source lineage. Keep performance admission separate: an exploratory parent is not a production best; a failed round retains the previous validated parent. Report measured changes by group and overall, and only the runtime's production verdict. A proposal, schema-valid plan, simulator run or trace export is not proof of hardware improvement.

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
