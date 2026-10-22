# AProf Evidence Contracts and Legacy Mapping

This file describes current evidence handoff and maps the pre-SkillGraph
Markdown workflow. It is not a machine schema or validation authority.

Use the versioned JSON schemas under repository `schemas/` and the strict
models in `runtime/src/aprof_runtime/`. Validate drafts with:

```bash
aprofctl contract validate --kind <kind> --input <file.json>
```

Unknown fields are rejected. Agent-produced JSON is always a draft. In
particular, an Agent must not submit `selected_as_best`, `terminal_utility`, a
gate verdict, or a graph update.

## Runtime contracts

| Kind | Authority | Purpose |
| --- | --- | --- |
| `context` | `schemas/context.schema.json` | Task, hardware, workload, budget, and evidence views |
| `candidate_draft` | `schemas/candidate-draft.schema.json` | Route, complete candidate set, behavior policy, transformation, action parameters, and producer/source identities |
| `handler_attempt` | `schemas/handler-attempt.schema.json` | Shape-validated, non-attested handler/parameter exploration sidecar; not policy reward |
| `gate_request` | `schemas/gate-request.schema.json` | Candidate drafts plus stage, artifact, correctness, timing, scope, and portability evidence |
| `gate_outcome` | `schemas/gate-outcome.schema.json` | Machine-generated state path, paired statistics, utility, and verdict |
| `candidate_episode` | `schemas/candidate-episode.schema.json` | Immutable trace binding context, full gate batch, graph/policy attestation, projected candidate, evidence, and outcome |
| `architecture_profile`, `parallel_plan`, `dispatch_plan` | Matching `schemas/` documents | Hardware/algorithm/dispatch planning and source evidence |
| `capture_manifest` | `schemas/capture-manifest.schema.json` | Recorded backend, workload/source/hardware identity, warmups, independent captures and raw inventory |
| `normalized_profile` | `schemas/normalized-profile.schema.json` | Legacy 1.0 CSV profile or 1.1 capture-bound CSV/JSONL selectors, samples and aggregation |
| `mechanism_report` | `schemas/mechanism-report.schema.json` | Candidate mechanism direction with baseline/candidate profile hashes |

Trace/exploration contracts also have dedicated kinds. A `profiling_plan`,
`profiling_results`, stage report, symptom draft or paired-timing output is not
one of these contracts.

## Formal profile handoff

For proposed v4 `local_profile_only`, optimization runs complete local online
admission within its task budget and returns code plus a small report. The local
index is an internal tool input or requested collection handoff. The CAS/episode
commands below belong to the optional post-task
trace/training archive/import stage; their existing verification requirements
remain intact. They are not instructions for the optimization Agent to copy all
profiles or perform permanent CAS registration. V4 qualification requires a
verified stable release manifest; a small report or delayed archive is not a substitute.

New hardware profiles use `capture_manifest` and normalized-profile 1.1 for both
msprof and npu-compute. See the
[collector commands](../skills/ascendc-aprof-profiling/references/collector-interface.md)
for task-local capture/normalization and its local index. Validate shape with:

```bash
aprofctl contract validate --kind capture_manifest --input <capture-manifest.json>
aprofctl contract validate --kind normalized_profile --input <normalized-profile.json>
aprofctl contract validate --kind mechanism_report --input <mechanism-report.json>
```

A mechanism report keeps its existing metric names, expected directions, units,
values and `baseline_profile_hash` / `candidate_profile_hash`. Its selected
metric must be present under the same name in both profiles. Record the report
hash as `GateEvidence.artifacts.mechanism_report`; source hashes must match the
candidate draft's baseline/candidate source identity. Preserve `profile_report`
in the artifact map when a full-profile attempt occurred so its budget is counted.

Source replay requires the store and original artifacts. For the existing CAS-based
archival gate replay and episode finalization, pass that same store:

```bash
aprofctl candidate gate --request <gate-request.json> --store <episodes.sqlite>
aprofctl episode finalize --context <context.json> --request <gate-request.json> \
  --graph <release-graph-snapshot> --store <episodes.sqlite>
aprofctl episode verify --store <episodes.sqlite>
```

When routing used a learned policy, also pass its exact `--policy` to finalize.
The runtime checks the raw metric sources and comparison identity and recomputes
alignment. New formal admission requires source-bound 1.1 profiles with at least
ten recorded warmups, five independent captures and CV <= 0.05; manually setting
`mechanism_alignment=true` does not substitute for that evidence. Complete build/correctness, timing and scope/portability evidence
are still required. Normalized profile samples do not replace the production
30-pair timing protocol.

Runtime 0.2.2 also requires `GateEvidence.artifacts.measurement_admission` and
`measurement_report` for new nonempty timing evidence. The runtime replays the
raw shared-buffer Task Duration groups, complete CSV task coverage, per-cycle
A/A controls and source/output identities
before exposing timing samples to the unchanged gain gate. See the
[shared timing contract](../skills/ascendc-aprof-profiling/references/shared-timing.md).

Schema validation establishes structure only. A profile or episode with absent
external CAS objects has not passed source verification. Keep the SQLite file
and its adjacent `.objects` directory together for offline replay. Historical
1.0 profiles and runtime 0.2.0 episodes retain their recorded meaning; do not
rewrite an old producer manifest or relabel it as new capture evidence.


The immutable graph schema is materialized under
`skillgraph/versions/<graph_version>/`. Source contracts live under
`skillgraph/source/`; policies are separate revisions compatible with one graph
version.

## diagnosis_hypotheses.json

Legacy diagnosis hypotheses are evidence drafts, not problem labels.

When importing them:

- Map `problem_family` to zero or more non-exclusive anchor facets.
- Map each metric or source observation to a stable evidence predicate where
  possible.
- Preserve confidence, source spans, refuting evidence, and missing views.
- Route unsupported records to `mechanism.unknown_unresolved`.
- Do not infer a behavior probability from the order of hypotheses.

## profiling_plan.json

Legacy profiling plans may be used to construct collection commands. Runtime
state must additionally pin the measurement protocol, hardware/toolchain
identity, required artifacts, and parser version. A plan never proves that the
artifacts exist.

## profiling_results.json

Legacy results are admissible only as imported evidence. Preserve raw samples,
artifact hashes, missing artifacts, parser identity, and whether evidence came
from hardware or simulator. Simulator-only results cannot train production
performance value.

## single_case_diagnosis.json

Import source/workload/profile observations separately. Do not collapse a
multi-view diagnosis into one family label. Keep workload-limited and
measurement-limited cases distinct from confirmed actionable mechanisms.

## final_diagnosis.md

This remains a human report rendered from validated evidence. It is never a
training record or graph source of truth.

## optimization_plan.json

Legacy strategies may seed a typed transformation contract only after manual
review. Migrate:

- `required_evidence` to predicate IDs;
- `capacity_model` to capacity constraints;
- `structural_edits` to transformation IR guidance;
- `semantic_requirements` to invariants;
- `expected_metric_delta` to expected profile effects;
- `abort_conditions` to contraindications and hard masks;
- failure handoff to gate/rollback specifications.

The resulting contract needs a stable ID, semantic version, applicability,
parameter schema, provenance, and an immutable graph snapshot reference.

## candidate_result.json

Do not import Agent-authored acceptance fields. Re-run the machine gate from raw
artifacts when possible. If build, correctness, paired samples, scope, or
artifact hashes are missing, retain the record as `legacy_unverified` and do not
use it for policy value training.

## optimization_memory.jsonl

Legacy flat memory is read-only. It lacks graph/policy/contract versions,
complete candidate sets, true behavior propensities, source and patch hashes,
machine gate events, and reproducible artifact identities. It may support
qualitative audit or deduplication, but it is not a verified episode store.

For training import, the post-task trace/training collector must first place
every referenced object in the CAS, then finalize through `aprofctl episode finalize --graph <snapshot> --store <store>` into the
append-only store under `<op_dir>/.aprof/`. Production policy training accepts
that verified SQLite store, not standalone JSON/JSONL exports.
