# AProf Wrapper Responsibilities

Read this file only when coordinating stage handoff. Do not duplicate graph
contracts, schema fields, measurement thresholds, or gate rules here.

## Stage ownership

| Stage | Agent responsibility | Machine authority |
| --- | --- | --- |
| Input/scaffold | Resolve a complete `op_dir`; preserve a read-only baseline | Registry and context schema validation |
| Evidence | Propose source/workload/profile observations and missing views | Predicate IDs, graph version, strict contract validation |
| Profile collection | Propose/execute authorized commands; retain raw artifacts | Artifact hashes, parser identity, paired statistics, evidence quality |
| Route | Supply validated context and budget | Legal candidate set, masks, policy probabilities, selected edge, behavior propensity |
| Candidate | Apply one selected transformation contract in isolation | Contract/version compatibility and candidate-draft schema |
| Validation | Supply build/correctness/runtime/profile artifacts | State path, verdict, utility, and `selected_as_best` |
| Trace | Explain provenance and outcome | Episode hash and append-only store |

## Wrapper rules

- Diagnosis wrapper normalizes context and evidence; it does not force one
  anchor or choose a transformation.
- Profiling wrapper constructs collection/parse drafts; it does not declare
  stable performance evidence.
- Optimization wrapper constructs candidate drafts; it does not run an
  independent acceptance implementation.
- Reviewer audits traceability and suspicious artifacts; it cannot replace a
  machine verdict.

## Failure handoff

| Failure class | Suggested capability |
| --- | --- |
| static/API/capacity | `ascendc-code-review` or precise docs lookup |
| accuracy/semantic | `ascendc-precision-debug` |
| runtime nonzero | `ascendc-runtime-debug` |
| timeout/crash/AIC | `ascendc-crash-debug` |
| artifact/measurement | `ops-profiling` |
| stable no-gain/regression | finalize negative episode, then route next legal action |

Handoff does not erase or rewrite the original candidate episode.

## Runtime state

Store task-local state under `<op_dir>/.aprof/`. Keep raw artifacts in the
content-addressed index and metadata in the append-only episode store. Do not
write traces into `skills/` or `skillgraph/source/`.

Legacy `optimization_memory.jsonl` and historical demo summaries remain
`legacy_unverified`; they are not policy-training inputs.
