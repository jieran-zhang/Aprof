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

1. Preserve the full operator contract, workload metadata and baseline source hash. Run the bundled environment preflight and `npu-arch`; record actual SoC/ISA, SDK, visible resources and unknown capabilities. Do not infer 910B versus 910C from the shared 2201 ISA enum.
2. Use `ascendc-aprof-diagnosis` to construct source/workload evidence and collect only missing profile views with `ascendc-aprof-profiling`. Preserve ambiguity; six legacy families remain nonexclusive evidence facets.
3. Run **algorithm parallel planning** with `ascendc-aprof-parallel-planning`: compare legal algorithms, partitions, ownership, reduction/synchronization and workspace per workload group. Validate `architecture_profile` and `parallel_plan`. Any algorithm implementation candidate uses `optimization_stage=algorithm_parallel` and the normal gates.
4. Create and validate `dispatch_plan` for metadata → workload group → uint64 tiling key → actual kernel entry, with a general fallback. Implement equivalent host/kernel dispatch for the project's registered or direct-launch mode; trace-only keys do not satisfy this stage. Verify overlap, boundary and unseen-metadata behavior.
5. Freeze the selected parallel plan and dispatch. Bind all three artifact objects and canonical hashes in `Context.evidence`, and use `optimization_stage=execution` for **execution optimization**. A new decomposition/ownership/reduction returns to parallel planning. Route on the immutable stage-aware graph snapshot; retain full legal candidate set, hard-mask reasons, selected edges and actual behavior probability.
6. Use `ascendc-aprof-optimization` to instantiate one selected execution intent per isolated candidate, scoped to the selected group/key. Tile size, buffer depth, memory movement and pipeline scheduling are evaluated under the frozen algorithm plan. Test the complete correctness contract and all other regions/fallback for regression.
7. Submit supported runtime contracts through `aprofctl contract validate`, then run `aprofctl candidate gate` in the declared gate order. Profiling plan/result, stage report, timing and symptom files are drafts until mapped into runtime evidence; planning JSON has its own strict contract kinds. Stop a candidate at the first mandatory failure.
8. Register source, patch, plan/profile/dispatch and evidence objects in the task CAS. Finalize with `aprofctl episode finalize --graph <snapshot>` and the exact behavior `--policy` if used. Preserve every failed, regressed and NOOP attempt, stage labels, per-group results, parent lineage and budget.
9. For requested consecutive rounds, seed the next round from the selected previous parent that passed correctness and runtime validation, with explicit source lineage. Keep performance admission separate: an exploratory parent is not a production best; a failed round retains the previous validated parent. Report measured changes by group and overall, and only the runtime's production verdict. A proposal, schema-valid plan, simulator run or trace export is not proof of hardware improvement.

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
