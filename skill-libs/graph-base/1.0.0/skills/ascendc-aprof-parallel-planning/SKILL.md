---
name: ascendc-aprof-parallel-planning
description: Optimize the algorithm and task decomposition of an Ascend C operator for a verified architecture and workload groups before tiling or pipeline execution tuning. Produce hash-bound parallel and dispatch plans while preserving semantics and precision.
---

# AProf architecture-aware parallel planning

This stage answers which algorithm, task partition and ownership should execute each workload group. It precedes the concrete tile, buffer, instruction and pipeline tuning in `ascendc-aprof-optimization`. Agents propose plans; strict runtime contracts and machine gates remain authoritative.

The [parallel experience index](../../experience/optimization/parallel/README.md)
links conditional historical examples. Read it only when the current workload
matches the question; a Wiki observation cannot replace architecture capacity
or independent acceptance.

Reuse an already validated plan for execution tuning under the same semantics,
workload domain and architecture. Do not repeat algorithm exploration merely
because a new tile/buffer candidate exists. Retain the original plan basis and
rebind the dispatch implementation source to each candidate; revisit planning
when decomposition, ownership, reduction or the global algorithm changes.

## Inputs and analysis

Start with a complete read-only baseline `op_dir`, its source hash, the operator's mathematical/precision contract and workload metadata. Use local `npu-arch` to obtain a validated `architecture_profile`; unknown resources/capabilities stay unknown. Read [algorithm families](../ascendc-tiling-design/references/algorithm-families.md) for the relevant family only.

1. Recover the actual algorithm from source and reference: reduction axes, output ownership, broadcast/index semantics, rounding, tie ordering, special values and legal shapes. Do not narrow the contract to supplied benchmark cases.
2. Partition workloads by metadata that changes algorithm economics: independent rows/tasks, reduction extent, shape/aspect ratio, dtype/layout, semantic attributes and verified capacities. Analyze each region separately, retaining a general fallback.
3. Compare valid algorithm alternatives using total work, independent tasks, reuse/GM traffic, synchronization/merge cost, workspace and precision. Distinguish workload-limited parallelism from poor scheduling. For A2/A3 use the same 2201 ISA constraints but actual SKU/device resources; 950 may justify register/SIMT/CV paths only if the SDK capability is supported.
4. Record the selected plan and rejected alternatives with source/probe/profile evidence hashes. If an algorithm change needs code, create an isolated `algorithm_parallel` candidate, validate it through the same build/correctness/runtime/timing gates, and retain failures. A written plan is not proof of a speedup.
5. Freeze the selected plan before `execution` tuning. A later change to decomposition, reduction, workspace ownership or global algorithm returns to this stage and gets a new plan identity/hash.

## Strict artifacts

`parallel_plan` binds `plan_id`, `operator`, analyzed parent `source_hash` and `architecture_profile_ref`. Preserve nonempty `semantic_invariants` and `precision_invariants`. Each group records `group_id`, `algorithm`, `task_partition`, `ownership`, `reduction`, `synchronization`, `workspace_bytes`, `workspace_formula`, `required_capabilities`, `memory_requirements`, `alternatives`, and hash references in `selection_evidence`.

All size values are bytes; describe the dynamic formula and capacity domain even when the current workload has a concrete size. Capacity bounds must account for the live working set. Unknown architecture capacities cannot authorize a specialized plan. Do not attach invented fields to the strict schema; extended narrative belongs in a separate referenced report.

Create `dispatch_plan` with disjoint metadata conditions, a unique uint64 key and C kernel entry for each chosen group, plus a general fallback. Bind the same operator/profile and the parallel-plan hash. `parallel_plan.source_hash` identifies the analyzed parent or original plan basis; `dispatch_plan.source_hash` identifies the emitted implementation. For new campaign records, include both `plan_basis_source_hash` and `implementation_source_hash` in the dispatch and `Context.workload`; they must match the plan basis and implementation respectively. The routing source hash remains the proposing parent. Keep machine plans outside the snapshotted source tree to avoid a source-hash self-reference. Read [tiling-key dispatch](../ascendc-tiling-design/references/tiling-dispatch.md) for real Host/Kernel plumbing and validation.

```bash
aprofctl contract validate --kind architecture_profile --input <architecture.json>
aprofctl contract validate --kind parallel_plan --input <parallel-plan.json>
aprofctl contract validate --kind dispatch_plan --input <dispatch-plan.json>
aprofctl dispatch select --plan <dispatch-plan.json> --workload <metadata.json>
```

In runtime `Context.evidence` preserve the three objects and their canonical `architecture_profile_ref`, `parallel_plan_ref`, `dispatch_plan_ref`, plus `optimization_stage` (`algorithm_parallel` or `execution`). Index objects and supporting evidence in the task-local evidence reader; schema validation alone is not attestation. Preserve group/key/entry selection with actual launch evidence. Any permanent CAS import belongs to post-task trace/training collection.

## Handoff and iteration

Execution candidates inherit the frozen plan, selected group/key, source lineage and actual architecture profile. Compare each changed region on paired measurements, then run full declared correctness and cross-region regression checks, including fallback and neighboring metadata boundaries. Aggregate all-case performance only after per-group analysis.

When the task requests consecutive rounds, each round starts from the selected previous parent that passed correctness and runtime validation. Record that parent source hash and selection evidence; performance admission remains independent, so an exploratory parent with `formal_admission=not_evaluated` is not a production best. A failed round falls back to the previous validated parent and still records its attempted plan/candidate and reason. Separate algorithm-parallel and execution learning labels. Keep build/accuracy failures, regressions and NOOPs. Never invent a gain to fill a requested number of iterations.
