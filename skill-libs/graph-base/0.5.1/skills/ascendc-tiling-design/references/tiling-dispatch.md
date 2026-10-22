# Metadata-based tiling-key dispatch

A workload group is a semantic/performance region defined by shape, dtype, layout and declared operator attributes. It is not a benchmark case number. First define a parallel plan for each group, then create the strict `dispatch_plan` contract binding the same architecture profile and explicit source lineage. The parallel plan names its analyzed parent in `source_hash`; the dispatch names the emitted implementation in `source_hash`. New campaign records include the paired `plan_basis_source_hash` and `implementation_source_hash` in both dispatch and `Context.workload`, while the routing context still names the proposing parent. Store machine plan JSON outside the snapshotted implementation source to avoid hash self-reference.

Each entry contains `group_id`, uint64 `tiling_key`, C identifier `kernel_entry`, metadata `conditions` and required capabilities. Keys identify implementations, not individual inputs; one region handles unseen neighboring shapes. Keep a general fallback whose conditions are empty. Different conditions must not overlap; the runtime rejects multiple matching entries rather than silently relying on order. Do not dispatch on expected outputs, arbitrary data-dependent values, case IDs or whether evaluation is running.

Validate using:

```bash
aprofctl contract validate --kind dispatch_plan --input <dispatch.json>
aprofctl dispatch select --plan <dispatch.json> --workload <metadata.json>
```

The selector is a validation/reference aid. The compiled host must perform the equivalent metadata test and the selected key must change the actual kernel path:

- Registered CANN operator: set the selected key in Host Tiling and use the matching SDK-supported key/template registration and kernel branch.
- Direct launch: select a compiled launcher/entry at the host, or add an explicit `uint64_t tilingKey` argument and branch in the kernel. Update declaration, launch and definition together. Do not assume `TILING_KEY_IS` works without the SDK tiling mechanism.

All entries preserve the original operator interface and checker. Tile lengths/blockDim remain capacity-derived within the selected region. Do not replace runtime platform queries with key-specific hardcoded UB/core values. Evaluate the affected group and run full correctness/regression checks across every other group and fallback.

Acceptance checks: each known case records metadata → group → key → entry; predicate boundaries include equality plus neighbors; unseen valid metadata reaches a legal optimized region or fallback; overlap and unknown metadata failures are explicit; forced/recorded key matches the path actually launched. Persist dispatch/plan/profile hashes with source and trace. Changing the dispatch predicates creates a new dispatch revision; changing decomposition/ownership creates a new parallel plan.
