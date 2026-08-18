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

1. Load `ascendc-aprof-workflow`. Scaffold a raw kernel with
   `ascendc-kernel-direct-invoke`; keep the baseline read-only.
2. Build source/workload/profile evidence with `ascendc-aprof-diagnosis`.
   Historical families are non-exclusive facets. Preserve unresolved and
   refuting evidence.
3. Use `ascendc-aprof-profiling` only for missing evidence or paired candidate
   measurement. Raw artifacts remain immutable and content-addressed.
4. Map profiling plan/result, stage report, paired timing, and symptom drafts
   into `context` or `gate_request`, then validate the supported runtime
   contract kind with `aprofctl contract validate`. The raw profiling drafts
   are not contract kinds.
5. Route against one immutable graph snapshot and compatible policy. Record the
   entire candidate set, hard-mask reasons, selection mode/seed, selected edge,
   and true behavior probability.
6. Use `ascendc-aprof-optimization` to instantiate exactly one atomic
   transformation in an isolated candidate tree. The Agent submits a draft; it
   does not assign a verdict.
7. Run `aprofctl candidate gate`. Stop on the first mandatory failure. Preserve
   successful, failed, stable-regression, specialized, and NOOP attempts.
8. Register every referenced object in the task-local CAS, then run `aprofctl
   episode finalize --graph <snapshot>` with the exact behavior `--policy` when
   applicable. Append atomically under `<op_dir>/.aprof/`.
9. Report the machine verdict and evidence. A reviewer may audit the evidence
   chain but cannot override the gate.

## Authority boundaries

- Agent: understand intent, gather context, propose evidence and patches,
  explain results.
- SkillGraph: immutable expert contracts, legal routes, hard masks, and current
  policy-compatible IDs.
- Runtime: schema validation, paired statistics, candidate verdict, utility,
  gate/route replay, CAS verification, cumulative session budgets, append-only
  storage, and graph/policy compatibility.
- Training: consumes only eligible episodes from a verified SQLite store; it
  never rewrites a published graph in place.

Injection recipes and injected labels belong to the independent
`aprof-benchmark-tools` package. They are not loaded by this workflow and cannot
be used as online diagnosis evidence.

## Stop points

- Missing execution authority or tools: return a validated plan and missing
  inputs without claiming an optimization result.
- No legal transformation: select explicit `transformation.noop`.
- Mandatory gate failure: finalize the typed negative episode and stop that
  candidate.
- Budget exhausted: close the optimization session without inventing missing
  measurements.

Details of wrapper responsibilities and failure handoff are in
`references/workflow-details.md`.
