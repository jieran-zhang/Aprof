---
name: ascendc-aprof-workflow
description: Run the trace-producing AProf workflow for an Ascend C operator. Use when an agent must diagnose a kernel, collect or parse profiling evidence, propose bounded optimization candidates, validate them through the machine gate, and preserve versioned candidate episodes for later SkillGraph training. Do not use this skill to generate injected benchmark problems.
---

# AProf Trainable Workflow

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
8. Register source, patch, plan/profile/dispatch and evidence objects in the task CAS. When a compatible runtime gate actually ran, finalize with `aprofctl episode finalize --graph <snapshot>` and the exact behavior `--policy` if used. For a research campaign without that gate, retain optimization-memory/conditional-lesson v2 evidence with `formal_admission=not_evaluated`, `graph_policy_eligible=false` and no episode reference. Preserve every failed, regressed and NOOP attempt, stage labels, per-group results, parent lineage and budget.
9. For requested consecutive rounds, seed the next round from the selected previous parent that passed correctness and runtime validation, with explicit source lineage. Keep performance admission separate: an exploratory parent is not a production best; a failed round retains the previous validated parent. Report measured changes by group and overall, and only the runtime's production verdict. A proposal, schema-valid plan, simulator run or trace export is not proof of hardware improvement.

## Training boundary

For iterative research campaigns, use the bounded [search measurement workflow](references/search-measurement.md).
New Level2 searches use two processes and six paired samples, compare directly
with the selected parent, and retain all-case correctness. Reserve full
calibration and six-process evaluation for frozen final comparisons. Reuse the
maintained executor and verified session results; do not add per-round runners
or repeated evidence-review packages. Keep historical protocols immutable.

- Write runtime state under `<op_dir>/.aprof/`; never write learned state into
  `skills/` or `skillgraph/source/`.
- Treat `skillgraph/versions/` as immutable. Update edge weights in a compatible
  policy revision; create a new graph version for any hard contract or
  structural change.
- Do not use legacy optimization memory, injected labels, or historical
  FastGELU demonstrations as verified policy reward.
- Train only from the verified SQLite EpisodeStore. Raw JSON/JSONL traces lack
  CAS and chain attestation.
- Research memory and lesson v2 may preserve verified measurements and portable
  evidence without formal runtime admission. Link each lesson to a real memory;
  separate algorithm-parallel and execution lessons, including their conditions,
  counterexamples and uncertainty. Neither a portable evidence bundle nor a
  research runtime-safety assessment is a compatible formal gate result.
- Keep benchmark generation in `ascendc-aprof-inject-problems` outside this
  workflow. It may later supply sealed tasks through an adapter, but it is not
  part of the production SkillGraph.
- Preserve historical `v0001` as a fixed mechanism/transformation skeleton. New stage-aware runs use the published `v0002` snapshot; do not rewrite old episodes.
- Treat `v0001` as a fixed mechanism/transformation skeleton. Its formal
  predicates map one-to-one to mechanisms, and each actionable mechanism has
  one positive transformation plus `NOOP`. Do not describe its global edge-bias
  update as end-to-end decision-graph learning.
- For the first CANNBench trace study, preserve handler ID/version, exact
  parameters, context buckets, typed failure, parent candidate, and next-attempt
  reason in a `handler_attempt` exploration sidecar. Validate its shape with
  `aprofctl contract validate --kind handler_attempt --input <file>`. It is not
  EpisodeStore/CAS-attested and cannot train the current policy; the strict v1
  episode remains unchanged. Promote repeated, supported
  handler/action/recovery branches only in a new graph/schema version.
- From an AProf source checkout root, maintainers can audit the published
  decision surface with `python3 scripts/audit_skillgraph_decisions.py --graph
  skillgraph/versions/v0001`. This repository tool is not bundled into the
  portable Codex skill.

## Stop conditions

- Stop at a validated plan when execution is not authorized or required tools
  are unavailable.
- Stop a candidate after the first failed mandatory gate. Finalize a typed
  negative episode only for a compatible gate execution; otherwise retain the
  failed research attempt and its raw evidence without a graph episode.
- Select `NOOP` when no transformation satisfies evidence, applicability,
  capacity, or safety constraints.
