# Local optimization trace contracts

The collection layer adds evidence JSONL alongside the existing machine-validated
SQLite EpisodeStore. It does not make exploration examples eligible for graph
policy training. The authoritative schemas are JSON Schema 2020-12, version
`1.0.0`, mirrored under `schemas/` and packaged in `aprof_runtime.trace_schemas`.

## Files and identities

- `trace_events.jsonl`: worker-owned append-only events. Each event contains
  run/task/session/attempt/candidate identities, a sequence number and timestamp,
  a typed payload, CAS references, and previous/current event hashes.
- `optimization_traces.jsonl`: one immutable candidate-attempt summary containing
  identity, provenance, knowledge, workload, diagnosis, intervention, routing,
  validation, result, lesson, and explicit reasons for null values.
- `episodes.jsonl`: a verified export from SQLite, including graph candidates
  only. This export is not a policy-training input.

Every worker uses a separate stream and session identity. The coordinator merges
streams without rewriting their original hashes. Within each stream sequences
start at 1 and the previous hash starts at `sha256:` followed by 64 zeros. An
event's hash is SHA-256 over canonical JSON with only `event_hash` omitted.
Supported events and their exact payloads are in `EVENT_PAYLOADS` in
`aprof_runtime.trace_schemas`; unknown structure fields and non-finite numbers
are rejected. Operator parameters, attributes and named shape maps are explicitly
open extension points.

## Writer API

```python
from aprof_runtime.store import EpisodeStore
from aprof_runtime.traces import (
    TraceWriter, execution_record, register_json_artifact,
    make_optimization_trace, write_optimization_trace,
)

with EpisodeStore(split_dir / "episodes.sqlite") as store:
    writer = TraceWriter(task_dir / "trace_events.jsonl", run_id=run_id,
                         task_id=task_id, session_id=session_id, store=store)
    writer.append("stage_completed", {
        "stage": "build", "status": "passed", "reason": None,
        "artifact_refs": [build_log_hash],
        "execution": execution_record(
            argv=argv, cwd=build_dir, host=host, device=device,
            started_at=started_at, finished_at=finished_at,
            exit_status=0, log_ref=build_log_hash),
    }, attempt_id=attempt_id, candidate_id=candidate_id,
       event_id=stable_external_job_id)
```

Append is protected by a file lock and fsynced. Reusing an event ID with identical
content is idempotent; a conflicting retry fails. Partial final lines require
explicit recovery, which preserves discarded bytes and can register them in CAS.
Use a new candidate/attempt ID for a repaired-source rebuild.

The Level1 coordinator uses `verify_history_artifacts=False` while collecting:
each append verifies the entire event hash chain and all referenced bytes in the
new event. Startup, attempt sealing and final export/verification perform full
historical CAS verification. This avoids rereading every prior profile/input for
each newly completed job. The default writer retains full historical checks;
explicit verification never uses a cross-call artifact cache.

`make_optimization_trace(identity, **groups)` merges recorded facts into a
conservative incomplete summary, with stages initially `not_run`, lesson status
`inconclusive`, and explicit null reasons. Supply source/patch provenance and
handler/parameters from the frozen candidate. `write_optimization_trace` validates
the summary and references; a changed summary cannot replace an existing attempt.
Supported/refuted lessons require evidence references. Final outcomes are checked
against their frozen candidates and replayed gates.

## Freeze and exploration gate

Before final evaluation, write exactly one `candidate_proposed` event per attempt,
then call `writer.seal_attempt(attempt_id)`. This stores the pre-evaluation event
fragment in CAS. The fragment deliberately precedes outcome and episode hashes.
Freeze the complete source/handler/parameter roster with
`freeze_exploration_manifest`; record later full measurements as separate evidence
artifacts. Exploration requests use the existing `GateEvidence`/`GateConfig`
shape but have no route, edge, transformation or propensity field.

`ExplorationGate().evaluate(request, store=store)` verifies CAS, source/patch and
handler bindings, and a complete frozen batch. The measurement report's
`gate_projection` must equal GateEvidence. Admitted final arrays require all 20
cases, enough paired samples, per-case CV at most 5%, and reproducible equal-case
geometric aggregation. Regression uses the signed paired geometric candidate /
baseline ratio minus one. Failed or incomplete raw measurements remain artifacts
but do not become admitted timing arrays.

Mechanism support is independently recomputed by
`mechanism_alignment_from_artifacts(evidence, store)`. A `mechanism_report` binds
expected metric directions to normalized baseline/candidate profiles. Each
normalized metric binds its value, unit, aggregation and samples to a raw CSV
field. `kernel="*"` selects all rows; otherwise a row must contain the exact
kernel name. The runtime re-reads the CSV, verifies the ordered samples, and
recomputes the reduction. At least one reported directional prediction must be
supported; missing profiles yield unknown attribution. `hypothesis_basis` retains
whether the original mechanism hypothesis was supplied by a user or inferred.
Measured direction is evidence for that hypothesis, not a claim of exclusive
causality. The same helper can be called by graph collectors without changing v1
gate serialization or hashes.

Exploration results always carry `graph_policy_eligible=false` and
`episode_ref=null`. They never append to the episodes table or choose a v1
`selected_as_best`. Register the complete outcome with `register_json_artifact`
and use its returned CAS digest in `exploration_outcome_ref`; the internal
`outcome_hash` excludes itself and is not that CAS digest.

## Verification commands

```bash
aprofctl trace verify --input trace_events.jsonl --store episodes.sqlite
aprofctl trace verify --kind optimization --input optimization_traces.jsonl --store episodes.sqlite
aprofctl trace merge --input worker-a.jsonl worker-b.jsonl --output trace_events.jsonl --store episodes.sqlite
aprofctl trace recover --input interrupted-worker.jsonl --store episodes.sqlite
aprofctl trace export-episodes --store episodes.sqlite --output episodes.jsonl
aprofctl exploration gate --request exploration-request.json --store episodes.sqlite
aprofctl exploration verify --request exploration-request.json --outcomes exploration-outcomes.json --store episodes.sqlite
```

Full verification includes content-addressed artifacts and deterministic gate
replay. The existing v1 gate arithmetic and hashes are unchanged; the new
exploration checks are applied before invoking the shared non-NOOP evaluator.

## Finalizing a bounded Level1 campaign

`scaffolding/collection/scripts/finalize_level1_campaign.py --run RUN --operator OP` finalizes one
operator after `collect_level1_traces.py freeze`. Omit `--operator` to finalize all
operators and produce the split and campaign exports; `--export-only` merges
operators already finalized. The command launches no hardware jobs. It rejects
unfinished registered jobs, omitted attempts, changed frozen plans, altered raw
measurement projections, and inconsistent bound mechanism metrics.

The finalizer reads `correctness-index.json` for qualified environment retries;
initial failed executions and correctness artifacts remain evidence. An
`input-policy.json` qualification is recorded separately from kernel failures.
Before evaluating the gate it registers logs, measurement sources, inputs named
by raw measurements, normalized profiles and their CSVs, then seals each attempt.
It writes `exploration_request.json`, `exploration_outcomes.json`, immutable
`optimization_traces.jsonl`, and an `attempt_finished` event with the summary's
CAS digest. The final `task_finished` event references `finalization_report.json`.
Recorded knowledge read hashes bind the original bytes, including an initial
worker context when its current file has changed. Opaque upstream metadata can
contain special IEEE values; the summary spells them as strings.

A profiled candidate may supply `candidates/ID/mechanism_report.json` (or
`profiles/ID/mechanism_report.json`) using the strict mechanism-report schema.
The finalizer does not invent metric directions or infer mechanism support from
duration alone. Missing mechanism evidence leaves attribution unknown. Optional
`candidates/ID/gate_review.json` fields `static_review`, `semantic`, `scope`, and
`portability` are objects containing an explicit `status` and `reason`; absent
scope and portability reviews remain `not_run`.

`best_source_selection.json` and `best_source/` are a separate benchmark
deliverable. Selection requires correctness, stable all20 timing, the machine
LCB gain floor, the regression ceiling, and measured mechanism support. A
`benchmark_specialized_gain` can be selected with its scope limitation recorded;
otherwise the validated baseline is retained. Files are extracted from the
verified source snapshot, and later verification detects changes to the delivered
copy. This selection never writes a v1 `selected_as_best` value for exploration.

Per-split `trace_events.jsonl` preserves worker stream hashes;
`optimization_traces.jsonl` is verified against that split's CAS and SQLite store.
`episodes.jsonl` is the verified existing graph episode export and may be empty.
Campaign-level files concatenate the verified split exports for compatibility.
Finalized retries reverify existing artifacts and return the same reports.
Graph-mode input fails closed unless its real episode was independently finalized
in that split's store with a bound pre-outcome `attempt_evidence` fragment; the
collector never synthesizes graph routes or manufactures graph episodes.
