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
| `budget` | recommended | Runtime-enforced candidate/build/timing/full-profile limits; declared token and wall-clock limits |
| `constraints` | no | Plan-only, no hardware, production-safe, or explicit benchmark-only mode |

## Main flow

The authoritative procedure is the
[workflow skill](../skills/ascendc-aprof-workflow/SKILL.md).
Load that entry once; this document only describes orchestration interfaces.

Default to one coordinator, one hypothesis and one candidate. Reuse verified
session preparation and the frozen algorithm plan; update candidate source
bindings and perform full correctness after every source change. Run the
exploratory screen before spending the finalist's full timing/profile budget.
Invoke wrappers only for useful delegation; a handoff is not a required extra
reasoning or report-writing stage.

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

This local ownership contract is proposed for v4 `local_profile_only`; qualification
and release remain pending. An archival pass cannot override an online failure.

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

Details of wrapper responsibilities and failure handoff are in
`references/workflow-details.md`.
