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

1. Load `ascendc-aprof-diagnosis` to extract source, workload, and available
   profile evidence. Preserve unknown and missing views; do not force a family.
2. Load `ascendc-aprof-profiling` only when required evidence is absent or a
   candidate needs paired measurement.
3. Validate supported runtime kinds (`context`, `candidate_draft`,
   `handler_attempt`, `gate_request`, `gate_outcome`, and `candidate_episode`)
   with `aprofctl contract validate` before using them as runtime state.
   Profiling plan/result, stage report, paired timing, and symptom JSON remain
   drafts until mapped into `context` or `gate_request`.
4. Route on the published `skillgraph/versions/<graph_version>` snapshot as
   soon as the context is schema-valid. Missing profile views remain `unknown`;
   they do not block routing because `unknown_unresolved -> NOOP` is a legal
   conservative result. They do block unsupported non-NOOP candidates.
   Record the complete legal candidate set, hard-mask reasons, selected edge
   IDs, logits, and behavior probabilities. The six historical families are
   non-exclusive facets, not ground-truth problem labels.
5. Load `ascendc-aprof-optimization` for the selected atomic transformation
   contract. Instantiate one optimization intent per candidate and preserve the
   exact contract version and action parameters.
6. Submit the candidate draft to `aprofctl candidate gate`. Import raw gate
   evidence in this order: schema/precondition,
   capacity/static review, build, accuracy/semantic, runtime safety, cheap
   timing, paired profile, stability, mechanism consistency, and generality.
7. Add every referenced source, patch, producer, and evidence object to the
   task-local CAS. Finalize with `aprofctl episode finalize --graph <snapshot>`
   and the exact `--policy` when learned routing was used. Keep verified
   failures and stable regressions.
8. Report only the runtime verdict. A faster candidate is not production-safe
   when correctness, stability, scope, portability, or held-out checks fail.

## Training boundary

- Write runtime state under `<op_dir>/.aprof/`; never write learned state into
  `skills/` or `skillgraph/source/`.
- Treat `skillgraph/versions/` as immutable. Update edge weights in a compatible
  policy revision; create a new graph version for any hard contract or
  structural change.
- Do not use legacy optimization memory, injected labels, or historical
  FastGELU demonstrations as verified policy reward.
- Train only from the verified SQLite EpisodeStore. Raw JSON/JSONL traces lack
  CAS and chain attestation.
- Keep benchmark generation in `ascendc-aprof-inject-problems` outside this
  workflow. It may later supply sealed tasks through an adapter, but it is not
  part of the production SkillGraph.
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
- Stop a candidate after the first failed mandatory gate and finalize the typed
  negative episode.
- Select `NOOP` when no transformation satisfies evidence, applicability,
  capacity, or safety constraints.
