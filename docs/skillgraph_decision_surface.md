# AProf v0001 decision-surface audit

`v0001` is an immutable expert skeleton, not yet a general trainable decision
graph. This distinction is part of the experimental contract. This audit
inspects formal graph predicates, not raw profiler symptoms.

Run the machine audit with:

```bash
python3 scripts/audit_skillgraph_decisions.py \
  --graph skillgraph/versions/v0001 \
  --output .aprof/v0001-decision-surface.json
```

## What v0001 actually learns

- Every formal predicate supports exactly one mechanism. Raw profiling
  symptoms can still retain multiple `candidate_problem_ids`; the fixed
  symptom-to-predicate projection discards that ambiguity before v0001 routing,
  so the runtime neither consumes nor learns it.
- Ten actionable mechanisms each expose one positive transformation plus
  `NOOP`. `unknown_unresolved` and `workload_limited` expose only `NOOP`.
- Edge hard masks use predicate states, not direct shape, dtype, operator
  family, hardware, or numeric profiling context.
- Transformation parameter schemas contain multiple implementation choices,
  but there are no handler nodes, handler propensities, or handler-specific
  rewards.
- Typed failures and human-readable handoffs exist, but the graph has no
  recovery transitions and routing does not read the previous verdict.

Consequently the current fixed-graph policy mainly calibrates which already
active positive transformation to try. It does not learn raw-symptom
attribution, handler selection, parameters, or failure recovery.

## Experimental claim for the first trace study

Use the first CANNBench trace study to investigate:

```text
fixed mechanism/transformation skeleton and global edge ranking
  -> handler implementation
  -> handler parameters
  -> build/correctness/performance outcome
  -> next-attempt observation
```

Do not describe this phase as end-to-end decision-graph learning or as an
implemented handler learner. Report it as expert-prior edge-ranking plus
handler/parameter trace collection and offline exploration.

At minimum, preserve in each exploratory trace:

- structured symptom draft and all candidate mechanism IDs;
- selected transformation edge and complete legal route candidates;
- an explicit handler ID/version supplied by the patch producer;
- exact parameter values and context buckets;
- patch/producer/artifact hashes;
- typed first-failure verdict;
- parent candidate ID and the reason a sibling handler, sibling action,
  evidence recollection, or debug handoff was selected next; record a terminal
  stop as the typed episode outcome plus no child attempt.

The current episode contract preserves the route, transformation, free-form
parameters, artifacts, verdict, and optional parent candidate ID. Store handler
identity and next-attempt reason in `handler-attempt.schema.json`, validate it
with `aprofctl contract validate --kind handler_attempt`, and keep it alongside
the episode until a new strict episode schema is published. This validation is
shape-only: the sidecar is not linked to EpisodeStore/CAS, does not attest its
graph/edge/candidate references, and is not a policy-training input. A terminal
stop remains represented by the typed episode outcome and absence of a child;
publish an explicit transition contract before training recovery decisions.
Do not silently add fields to the v1 episode.

## Promotion criteria for a future graph version

Publish a structural successor only after training traces demonstrate repeated
branches with enough support. Candidate additions should satisfy all of:

1. One raw symptom repeatedly leaves at least two plausible mechanisms after
   source/workload evidence is considered.
2. One mechanism has at least two independently viable positive actions, not
   merely action versus `NOOP`; at least one schema-valid context makes them
   jointly legal.
3. A handler choice recurs with stable applicability and a versioned parameter
   contract.
4. Shape, operator family, dtype, hardware, or profiling signature changes the
   observed ranking often enough to justify a context residual.
5. A typed failure has at least two legitimate next decisions whose outcomes
   can be compared. Topological out-degree alone is insufficient: each promoted
   branch needs empirical trace support.

Until those conditions hold, adding branches would manufacture a learning
surface instead of discovering one.
