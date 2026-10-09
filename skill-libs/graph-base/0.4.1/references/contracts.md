# AProf Legacy Contract Mapping

This file is a compatibility guide for the pre-SkillGraph Markdown workflow.
It is not a machine schema and must not be used as validation authority.

Use the versioned JSON schemas under repository `schemas/` and the strict
models in `src/aprof_runtime/contracts.py`. Validate drafts with:

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

New successes and failures must first place every referenced object in the CAS,
then finalize through `aprofctl episode finalize --graph <snapshot>` into the
append-only store under `<op_dir>/.aprof/`. Production policy training accepts
that verified SQLite store, not standalone JSON/JSONL exports.
