# AProf lightweight trace pilot

This pilot prepares reproducible CANNBench trace state without running a
build, NPU command, profiler, or source mutation. It is the small bridge
between the frozen `v0001` SkillGraph and the existing profiling/runtime
primitives.

The training trace is a verified candidate episode. An msprof or simulator
trace is only one evidence artifact inside that episode.

## What the preparer does

`scaffolding/collection/scripts/prepare_trace_pilot.py`:

1. validates the frozen train/validation membership digest and rejects sealed
   test tasks;
2. validates the immutable graph snapshot;
3. records the repository commit/dirty state, graph hashes, split version,
   budgets, selection mode, and seed in one run manifest;
4. creates separate train and validation EpisodeStores;
5. creates a deterministic baseline source tar, excluding generated state,
   and registers it in the corresponding CAS;
6. writes and validates `context.json`, then records the replayable
   expert-prior route for the current predicate states;
7. writes a build/full-correctness stage config and JSON command arrays for
   the next explicit steps.

It deliberately does not infer a timing command. Most CANNBench `run.sh`
scripts also generate data and verify output, so using them with
`paired_timing.py` would measure the wrong workload.

## Prerequisites

Install the local runtime and validate the self-contained skill bundle:

```bash
python3 -m pip install -e .
python3 scaffolding/tools/sync_aprof_registry.py check
aprofctl graph validate --graph skillgraph/versions/v0001
```

The standalone upstream CANNBench checkout is required for the complete split
validator but not for preparation from the already frozen manifests:

```text
third_party/cann-bench/
```

## Prepare a canary

Copy and edit the example. In particular, replace the hardware fingerprint.
For a training-eligible trace, also provide three immutable identity files:

```json
"producer_artifacts": {
  "model": "/absolute/path/model-identity.json",
  "prompt": "/absolute/path/prompt.txt",
  "agent": "/absolute/path/agent-identity.json"
}
```

Then prepare the run:

```bash
python3 scaffolding/collection/scripts/prepare_trace_pilot.py \
  --config scaffolding/collection/configs/trace-pilot.example.json
```

By default the result is written to:

```text
.aprof/runs/<run-id>/
  input-config.json
  run-manifest.json
  artifacts/empty.patch
  train/episodes.sqlite
  train/episodes.sqlite.objects/
  tasks/<task-id>/
    context.json
    route.json
    profile-stages.baseline.json
    next-commands.json
    artifacts/baseline-source.tar
```

The generated route is intentionally conservative. Empty predicate evidence
routes to `unknown_unresolved -> NOOP`. After source/profile evidence is
normalized, update `context.evidence.predicate_states` and rerun the recorded
route command. Never edit `route.json` to force an edge.

## Continue from prepared state

1. Inspect `run-manifest.json` and `next-commands.json`.
2. Run the generated baseline stage command with `--dry-run` first.
3. Execute build and all-20-case correctness only after the command/device is
   approved.
4. Collect the minimum profile bundle and compress it with
   `skill-libs/graph-base/0.4.1/skills/ascendc-aprof-profiling/scripts/compress_msprof.py`.
5. Map measured predicate drafts into `context.json`, preserving `unknown` and
   all symptom ambiguity, and rerun graph routing.
6. Create each candidate in an isolated tree. One candidate carries one atomic
   transformation and one exact parameter set.
7. Create and validate a `handler_attempt` sidecar for the implementation and
   retry decision.
8. For candidates that pass full correctness, provide explicit prepared-input
   baseline/candidate commands to `paired_timing.py`. Production performance
   requires at least 30 alternating pairs; full msprof remains separate.
9. Register source, candidate, patch, producer, build, accuracy, measurement,
   and profile artifacts before finalizing the complete candidate batch.
10. Run `aprofctl episode verify` on the split-local store.

## Boundaries

- Missing producer artifacts are recorded as `unknown`; the preparer warns
  that default policy training will skip those episodes.
- The source tar is content-addressed and self-describing. Build trees,
  `.aprof`, generated data/results, profiler output, and Python caches are
  excluded.
- Train and validation state is physically separated. Sealed test preparation
  is rejected.
- `handler_attempt` is still an offline exploration sidecar. It is not
  EpisodeStore-attested and cannot train the current policy.
- Profiling symptoms and predicate states remain drafts until stronger
  machine extractors are implemented. Missing counters stay `unknown`.
