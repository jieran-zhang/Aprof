# Runtime execution-cost compatibility and complete handoff

Scope: runtime source except `knowledge.py`, runtime tests, this runtime report/builder, and the explicitly requested portable paper examples. No device run, target compilation, training, or memory update.

## Behavior

- Shared `action_decision_v2.workload_case_payloads` consumes `cases[{case_id,workload}]` in new first selections and effective v2/v3 feedback. Existing workload file references remain exact hash bindings; feedback compares each captured workload payload with the frozen complete payload, beyond case membership.
- D7 and later experiment/conditional selections without a complete mapping return `conditional` with `missing_workload_mapping = ["workload.full_case_payloads_before_selection"]`. They cannot enter C3. This diagnostic is separate from safety and performance facts. Bare original matrices remain readable for analysis; stop/collect remain usable. Mixed bare/wrapped rows, duplicate IDs, mismatching coverage, missing payloads, and new D7 empty payload objects are rejected rather than guessed.
- Both legacy single-instance handoff and complete v4 handoff propagate the mapping gap. The v4 C3 check is explicit and cannot be discharged with planned guarantees.
- D6 first-selection behavior remains unchanged, including absence of the new output diagnostic. Effective historical feedback continues to require the same complete mapping as before. The old v3 fixture now selects an actual frozen D6 routing bundle instead of whichever graph happens to be active.
- The complete v4 chain already rejected missing/null/wrong scheme identity. The standalone `validate_handoff_decision` entry previously skipped the optional selected-scheme check for null; it now requires a nonempty exact `scheme_id` and matching scheme hash too.
- Performance uncertainty remains allowed in experiments. Safety/structure requirements, per-instance isolation, explicit v3/v4 separation, and KEEP/fallback rules retain their existing checks.

## Paper examples

Builder: `scaffolding/curation/graph-base-1.3.0-execution-cost/runtime_examples.py`.

The test factories accept an explicit workload input so each example creates the complete canonical workload before its first decision file, rather than filling a map into an earlier decision. New-intent feature tags are supplied with an initial, hash-bound `routing-structure.json` CPU declaration and a source-context reference; metadata explicitly sets `source_understanding_verified=false`. They describe multi-consumer derived values or buffer/event completion structure, rather than injecting facts in an Action hint. Examples use actual frozen D7/P4/O7 routing, real internal routes, exact scheme/member/source/parameter/plan identities, shared compatibility, and actual selected leaf snapshots. They are paper declarations for CPU contract review. A C3 `implemented` validation status is not target build, semantic correctness, oracle, or hardware evidence.

Requested output: `workflows/references/execution-cost-1.3.0/examples/` with single transfer, transfer + derived-result reuse, and transfer + buffer/event management chains. All three examples were generated and passed actual decision and complete-chain validation against the same frozen D7/P4/O7 bundle in a local package copy. New leaves were `implementation.buffer-lifetime.derived-results` and `implementation.pipeline-sync.vector-static-lease`, each beside `implementation.memory-transfer.coalesce`. Index, per-task metadata, and README are merged in the package output. Copy/relative-reference checks are saved in `runtime-examples-check.json`. The final package owner will additionally run the three standalone replays.

## Validation

Final runtime regression results:

- Real D7 regression: **18 passed in 205.16s**. Log: `/dev/shm/aprof-execution-cost-runtime-d7.log`.
- Explicit D5/D6 legacy decision/handoff regression: **107 passed in 1055.60s**. Log: `/dev/shm/aprof-execution-cost-runtime-legacy2.log`.
- Paper example generation: **3/3 passed** actual `validate_decision(... implementation=True)` and real `bindings.validate_chain` checks. Each decision returned `ready`, each paper chain `implemented`, with no performance claim. Initial structure references, canonical workload references, nonempty exact scheme identity, and relative task references were checked after the management example was copied into the package.

- D7 regression command uses `/dev/shm/aprof-execution-cost-runtime-d7` and covers canonical first/feedback consistency, wrong payload, duplicate and malformed mappings, bare analysis/C3 refusal, stop/collect, real v4 propagation, omitted/null/empty scheme IDs, version separation, and the still-supported single-opportunity v2 entry.
- Legacy regression command uses `/dev/shm/aprof-execution-cost-runtime-legacy2` for action decision v2/v3 and handoff v4 tests, including real D6 full chains and safety/instance/KEEP negatives.
- `knowledge.py` remains byte-for-byte equal to the frozen before package; SHA-256 `f09921f590f7306cd7777415784f3b894576d48cbc648a24dc0d43d199d70076`.

An initial interrupted run used `/tmp` for FakeRunner captures and hit the existing `/dev/shm` execution policy. A second interrupted run correctly detected the temporarily changed legacy source manifest while the separate knowledge migration was in progress. Both conditions were corrected in the final fresh runs; no execution-policy or historical-source validation was relaxed. An initial new-intent example was also correctly rejected because the old fixture lacked its parent router feature. The regenerated examples include an initial, locatable CPU structure declaration for those features; no route trace was forged, no source-understanding claim was added, and no frozen knowledge body/index was changed.

## Limits

The runtime checks immutable references, structural contracts and recorded evidence identity. It does not prove arbitrary source semantics or establish a trusted real-world event chronology. The paper example evidence explicitly declares its synthetic nature and must not be treated as compiler/device/performance observation. No automatic measurements or admissions are fabricated.
