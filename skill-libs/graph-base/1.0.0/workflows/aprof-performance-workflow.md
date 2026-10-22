# AProf Trace-Producing Performance Workflow

Use this file only for Agent orchestration. The canonical capability inventory
is `skillgraph/registry.json`; graph contracts and priors are under
`skillgraph/`; machine schemas and decisions belong to `aprofctl`.

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `kernel_source` / `kernel_path` / `op_dir` | yes | Optimization requires a complete direct-invoke project |
| `operator_context` | recommended | Shape, dtype, layout, operator semantics, supported boundaries |
| `execution_context` | for execution | Build, correctness, timing/profile commands and environment |
| `budget` | recommended | Runtime-enforced candidate/build/timing/full-profile limits and one shared task deadline; record actual tokens as cost |
| `constraints` | no | Plan-only, no hardware, production-safe, or explicit benchmark-only mode |

## Main flow

The authoritative procedure is the
[workflow skill](../skills/ascendc-aprof-workflow/SKILL.md).
Load that entry once; this document only describes orchestration interfaces.

Follow architecture and semantic constraints → diagnosis → parallel design →
execution optimization → validation feedback. Parallel design owns algorithm,
task ownership, reduction, synchronization and workspace. Execution optimization
owns tiles, buffers, transfers and pipelines within that accepted structure.
Use the [experience index](../experience/README.md) at the relevant stage. If
conditions are unclear or counterexamples matter, read one related page from
the [Wiki index](../wiki/index.json), then return to the legal graph route.
Missing profiling predicates remain unknown; a waiting ratio alone does not
establish `overlap_low`.

Default to one coordinator, one hypothesis and one candidate. Reuse verified
session preparation and the frozen algorithm plan; update candidate source
bindings and perform full correctness after every source change. Run the
exploratory screen before spending the finalist's full timing/profile budget.
Invoke wrappers only for useful delegation; a handoff is not a required extra
reasoning or report-writing stage.

Use `time_only_v1`: freeze one finite task budget before execution. Generation,
independent review, the single candidate build, correctness, timing, profiling
and online admission share the original task clock. The time limit is
configurable; a child cannot renew it. Reserve time to finish an already
started collection unit, save its results and stop at a unit boundary;
incomplete sampling cannot pass. Record actual proposer and reviewer tokens
as cost, without role or total token caps. Post-task archival has a separate
cost. A future equal-budget comparison must use the same calibrated budget
for every arm and seed.

This 1.0.0 release has an explicit exp-only scope on 910C/A3 with CANN
9.0.0. The original 45-run comparison and post-seal full test evaluation are
not run. This scope does not establish improved optimization performance
across the five validation operators, and other optimization rules stay draft.

## Authority boundaries

- Optimization Agent: use task-local files, propose patches, complete budgeted
  correctness/Task parsing/controls/online admission, and return code plus a small
  report and local evidence index.
- SkillGraph: immutable expert contracts, legal routes, hard masks, and current
  policy-compatible IDs.
- Runtime: schema validation, paired statistics, candidate verdict, utility,
  online gate/route replay, cumulative session budgets, and graph/policy compatibility.
- Post-task trace/training collector: optional permanent copying, CAS verification,
  archival replay and append-only episode storage, with separately reported costs.

The candidate uses Task v5 with `local_profile_only`, binding every case and
role to the complete ordered task sequence. Current exp evidence does not
qualify all multi-kernel workloads. The final exp continuation gate returned
`production_safe_gain` and its actual process exited with code 0. The two
preceding failed executions remain failed; archival cannot override a failure. The optimization agent returns task-local evidence. Only a separate,
requested post-task collector makes permanent copies.

Injection recipes and injected labels belong to the independent
`aprof-benchmark-tools` package. They are not loaded by this workflow and cannot
be used as online diagnosis evidence.

## Stop points

- Missing execution authority or tools: return a validated plan and missing
  inputs without claiming an optimization result.
- No legal transformation: select explicit `transformation.noop`.
- Mandatory gate failure: preserve the failure and finalize a typed negative episode
  only when a compatible gate ran; stop that candidate.
- Budget exhausted: close the optimization session without inventing missing
  measurements.
- Clear screening regression: stop that candidate and preserve the exploratory
  record. Borderline results get at most one predeclared extension; otherwise
  remain inconclusive. Screening never establishes a production verdict.

Registered controls, full correctness and boundaries, independent source
review, formal timing and mechanism evidence must all admit the same
source/binary. Preserve a failed control even when formal A/B says
`stable=true`; do not extend or resample a rejected measurement.

For this explicitly authorized exp continuation, replay the passed components
from the failed original attempt and collect only the missing candidate
mechanism evidence. The retained prefix contains 20 correctness cases,
42 boundaries and 30 formal Task pairs per case; the five candidate PMU
captures and oracle are complete. The original attempt's oracle-output
parsing failure and the PMU continuation's evidence-binding failure remain
failed records. A separate gate-only continuation replayed the complete
source-bound evidence, returned `production_safe_gain` and exited with code 0.
It added no candidate build, PMU capture or formal timing sample. The exp-only
scope amendment explicitly records the unrun 45-run comparison and post-seal
full test; package sealing and independent installation remain release checks.

Details of wrapper responsibilities and failure handoff are in
`references/workflow-details.md`.
