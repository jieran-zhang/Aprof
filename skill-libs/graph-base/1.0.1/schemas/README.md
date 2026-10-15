# AProf runtime schemas

These JSON Schemas document serialization version `1.0.0`. The Python runtime
is the authoritative validator and additionally enforces cross-field
invariants (probability sums, candidate/evidence identity, hashes, paired
measurements, gate replay, route replay, and state-machine ordering). All object
schemas reject unknown fields. `tests/test_schema_parity.py` keeps a shared
valid/invalid corpus aligned across JSON Schema and the Python models.

`handler-attempt.schema.json` is a shape-validated exploration sidecar for the
handler, parameter, context, and retry decisions that the immutable v1
candidate episode does not model. It does not attest graph/edge/candidate
references, is not linked into EpisodeStore/CAS, grants no reward authority,
and is not embedded into the v1 episode.

The separate `architecture-profile`, `parallel-plan`, and `dispatch-plan`
contracts support the v0002 graph. Validate them with `aprofctl contract validate
--kind architecture_profile|parallel_plan|dispatch_plan --input FILE` (choose one
kind). Their strict schemas are mirrored from `aprof_runtime.planning`; semantic
validation additionally rejects conflicting identities, invalid metadata
conditions and duplicate uint64 tiling keys.

For replay, `Context.evidence` carries each complete object and its corresponding
`*_ref`, computed by `content_hash(object)`. Register canonical JSON with
`register_json_artifact` before episode storage; pretty-printed file hashes are
different. `optimization_stage` is `algorithm_parallel` or `execution`. Execution
requires a valid architecture-bound parallel plan and dispatch plan, source hash,
operator, capabilities, capacity and selected workload group/key. `Context.workload`
contains `source_hash`, `metadata` (`shape`, `dtype`, `layout`, `attributes`),
`tiling_key` and `workload_group`. Use `aprofctl dispatch validate-context --context
FILE` for the bound bundle, or `aprofctl dispatch select --plan FILE --workload
METADATA` for metadata selection alone. Selection refuses overlapping matches and
uses an explicit generic fallback; it does not generate C++ launch code.

When a plan analyzes a parent and the dispatch implements a new candidate,
`Context.workload` additionally declares `plan_basis_source_hash` and
`implementation_source_hash`. The former binds `parallel_plan.source_hash`; the
latter binds `dispatch_plan.source_hash`. The dispatch contract carries both
fields together for this lineage. Fresh campaigns require this explicit pair.
The route's `source_hash` still identifies the source from which the candidate
is proposed. Store launch/dispatch sidecars outside the source tar to avoid a
source hash referring to itself.

`architecture_profile.core_counts` records SDK platform capacities. New probes
also emit `visible_core_counts` from successful `aclrtGetDeviceInfo` queries and
`compiler` (`status`, `path`, `version`, `evidence_refs`). Missing legacy fields
mean unknown visibility/compiler identity. A verified compiler identity is
necessary, but still does not establish API or target-flag support; 950-specific
capabilities require their separate compile evidence. Already frozen profiles
are retained unchanged.

Plan validation is structural and checks declared capacity and applicability; it
does not establish algorithmic correctness. Hardware/build/correctness evidence
and review remain necessary. v0001 episodes, schemas and graph snapshots retain
their original serialization and arithmetic. The independent version 2.0.0 memory
and lesson schemas remain research records, not automatically policy episodes.
