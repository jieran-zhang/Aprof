# AProf SkillGraph and Profiling Flow

## Authority model

The Agent-facing plugin gathers context, proposes evidence, and edits isolated
candidates. `aprofctl` owns validation, routing trace integrity, paired
statistics, candidate verdicts, CAS verification, episode hashes, cumulative
session budgets, and append-only storage.

```text
op_dir + budget
  -> context/evidence draft
  -> strict schema validation
  -> predicate evidence and mechanism route
  -> immutable graph + compatible policy
  -> isolated transformation candidate
  -> build/correctness/runtime/profile artifacts
  -> machine gate
  -> CAS objects + candidate episode in <op_dir>/.aprof/
```

## Graph state

`skillgraph/source/` is reviewed authoring state. The deterministic compiler
publishes immutable snapshots under `skillgraph/versions/`. Graph versions pin
hard contracts and topology; policy versions change only soft edge decisions.

The first graph uses six historical families only as non-exclusive facets.
Mechanisms and transformations are separate nodes, and `unknown_unresolved` and
`NOOP` are first-class choices.

## Profiling evidence

Profiling may be hardware, msprof-op, application-level, or simulator-based.
Every artifact needs a content hash, parser identity, hardware/toolchain
context, and evidence-quality label. Missing counters remain unknown.

Production performance decisions require paired baseline/candidate samples and
the configured stability/LCB checks. Simulator traces may support feasibility
or source attribution but not production value learning.

## Gate order

The runtime stops on the first mandatory failure:

1. schema and preconditions;
2. static/capacity review;
3. build;
4. accuracy and semantic checks;
5. runtime safety;
6. artifact completeness;
7. paired measurement stability and conservative gain;
8. mechanism consistency;
9. held-out shape, scope, and portability.

Build and correctness failures are finalized without requiring timing samples.
Mechanism mismatch may produce `attribution_uncertain`; a stable speedup is not
silently rewritten as mechanism evidence.

## Trace and training

A candidate episode joins one context, the complete gate batch, canonical graph
snapshot/hash, optional behavior-policy checkpoint/hash, complete route
candidate set, true behavior propensity, transformation contract/version,
patch/source/producer identities, raw gate evidence, and machine outcome. On
read and append, the runtime replays the gate and route from these inputs.

The store copies every referenced object into a content-addressed directory,
rehashes it, appends episodes transactionally, and maintains an append-only hash
chain. Its threat model excludes an administrator able to replace both the
database and the CAS; export the verified chain head to an external log when
that threat matters.

Only version- and hash-compatible eligible episodes from a verified SQLite
EpisodeStore may update a fixed-graph policy. Legacy flat memory, injection
labels, raw JSON/JSONL traces, and historical FastGELU demonstrations do not
enter production policy reward.
