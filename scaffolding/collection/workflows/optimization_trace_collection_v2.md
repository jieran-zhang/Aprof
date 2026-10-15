# Optimization trace collection v2

For organizing future experiments, use the
[experiment playbook](optimization_experiment_playbook.md) and the
[shared-context paired protocol](shared_context_paired_protocol.md). This page
documents the existing CPU helper and data tools. Its checkpoint policy,
probe immutability and measurement assertions below describe the existing
implementation, not an implementation of the new protocol. In particular,
the new protocol does not reject a comparison solely for cross-process absolute
latency drift above 2%; it requires true native-process A/B pairing and
process-level analysis. Do not edit an old manifest to relabel it as the new
protocol. No hardware is started by this documentation update.

The external CPU-only coordinator in `scaffolding/collection/scripts/trace_v2_campaign.py` prepares and validates paused experiment checkpoints. It does not execute experiments, query devices, invoke subprocesses, or change AProf skills, workflow, graph, gates, or existing runs. Hardware execution is deferred and requires an explicit user start. The old 21-candidate queue remains untouched.

Prepare a new manifest with `python scaffolding/collection/scripts/trace_v2_campaign.py prepare --campaign-id NAME --output NEW_FILE.json`. The output must not exist. Add at most two `--probe CASE` arguments at preparation time. Inspect descriptors with `python scaffolding/collection/scripts/trace_v2_campaign.py dry-run --manifest NEW_FILE.json`; this command reads the file and emits JSON without updating it.

The plan includes `foreach_norm` and `exp`, classified as known workloads, not held-out evaluation. Each workload has budgets of six source candidates, six builds, six timing comparison groups, and three profile groups. Cases 1, 8, 14, and 20 are mandatory sentinels. Optional probes are drawn from cases 1–20, predeclared and cannot change within a checkpoint history. Budgets count accepted recorded activity, including unsuccessful observations; they do not reset after failures. Each measured candidate consumes one timing group, containing one or two independently measured comparators. A separate comparison_groups_used counter records comparator cost. A child whose parent is the original needs one comparator; other children need two.

`prepare_plan(campaign_id, probes=())` returns a plain JSON-compatible manifest. `Campaign(plan)` validates the immutable policy and replays the checkpoint event history. Its methods mutate only an internal deep copy. Callers may serialize `campaign.plan` to a new checkpoint file themselves. This helper provides no executor or automatic start transition.

An optimizer follows the existing, unchanged AProf skills and does not produce training JSONL. The external recorder calls `register_candidate` for its actual proposal, with SHA-256 source and patch identities, the original source identity, `source_parent`, and `decision_basis`. The source parent identifies the code being edited; decision basis lists already closed observation IDs that informed the proposal. They are separate records and may differ. Each candidate must receive one closed observation before another can be registered. `close_observation` records the actual normal skill diagnostic payload externally, correctness, runtime validity, stability, comparison evidence identities, and build/profile costs. The coordinator checks bookkeeping and declared outcomes; it does not independently verify hardware evidence or diagnostic truthfulness.

A correct, runtime-valid, stable candidate in the current epoch is eligible as a source parent even if its improvement is below 3% or an unchanged production gate rejects it. Incorrect, runtime-invalid, or unstable candidates remain observations but cannot serve as parents. Existing gate behavior is not altered.

`comparison_descriptors` produces child-versus-parent and child-versus-original descriptors. The descriptors share a single group only when parent and original identities are identical. Otherwise the comparisons are independent. Results must match the candidate, control source, patch, and epoch identities. Sample IDs must be globally fresh within the campaign checkpoint, including across workloads, candidates, and comparator groups. Both comparator roles must be present before an observation can declare all three eligibility outcomes true.

The frozen measurement protocol requires a single active host, warmup 10, repeat 100, 30 paired samples per case, CV at most 5%, role bias at most 2%, and drift at most 2%. Each measured comparator supplies source/binary/input hashes, all expected cases and 60 sample IDs per case, an evidence report content hash, current baseline correctness passing all 20 cases, and before/reverse/after AA reports bound to the current control source, binary, and epoch. Quality reports explicitly declare externally attested scope; the CPU helper checks these declarations and identities but cannot establish the truth of external measurements. Hash inputs accept legacy bare SHA-256 and normalize candidate identities to sha256:hex.

`freeze(workload)` seals the roster after pending feedback closes; new candidates are rejected. Freezing an empty roster requires an explicit blocked reason. `recover_prestart` records at most one infrastructure recovery per epoch, before any candidate is registered. There is no stability retry or epoch-reset mechanism. A future hardware driver must enforce these budgets before launching work and respect these checkpoints; implementing that driver is outside this CPU preparation change.

Run CPU tests with `python -m pytest tests/test_trace_v2_campaign.py`.

## Two primary data views

`trace_v2_dataset.py` imports immutable v1 records into a new local dataset. Each
source attempt remains one `optimization_memory`; serial remeasurements add an
evaluation without changing its original parent. The current views are committed
together using `current.json` pointing to an immutable revision. Old revisions and
record objects remain in the new CAS. Existing run archives are read-only inputs.

```bash
python3 scaffolding/collection/scripts/trace_v2_dataset.py export \
  --parent .aprof/runs/level1-20260907T152600Z \
  --serial .aprof/runs/level1-serial-final-20260908T011500Z \
  --output .aprof/runs/<new-cpu-run>/dataset/v2
python3 scaffolding/collection/scripts/trace_v2_dataset.py verify \
  --output .aprof/runs/<new-cpu-run>/dataset/v2 --deep
```

The immutable revision contains `train/optimization_traces.jsonl`,
`train/lessons.jsonl`, and separate validation counterparts. It also includes
closed structural schemas, a shared evidence index, context/catalog objects,
record-revision CAS mappings, producer hashes and a manifest. Domain-specific
`attributes` are extensible JSON maps; surrounding record, fact, condition,
claim, source and evaluation structures reject unknown fields. Nonfinite task
attributes use explicit `special_value` labels; unavailable original outcome
metrics retain null with a reason.

A lesson joins exact memory revisions and keeps concrete symptoms, interventions,
conditions and counterexamples inline. Claim status is independent of machine
admission. Historical profile evidence, measured timing and retrospective
interpretation remain distinguished. No new formal episode is generated here.
The initial historical adapter intentionally derives detailed operator lessons
only for the three completed norm measurements. It does not turn the other
21 unstable historical attempts into positive lessons.

Knowledge access logs are classified separately from parsed CSVs and hash-only
checks. Logged reading is not asserted to prove candidate-specific decision use.
Full source/patch archives, logs, raw timing and profile evidence remain at their
immutable local archive locations; `evidence_index.json` binds paths, hashes,
selectors and split. Thus the dataset is locally usable with its referenced old
archives; copying only the two JSONLs is not a complete portable evidence bundle.

For a self-contained copy of a published dataset, use:

```bash
python scaffolding/collection/scripts/trace_v2_portable.py export --dataset RUN/archive/train/v2 --output DELIVERY/train
python DELIVERY/train/verifier/trace_v2_portable.py verify --bundle DELIVERY/train
```

Repeat for the validation dataset. The portable copy retains the original JSONL
bytes, record hashes, revision history, evidence selectors and source paths as
provenance. A complete explicit map resolves evidence into bundled content-hash
objects; verification never falls back to the original paths. The bundle includes
the CPU verifier (Python and `jsonschema` are required). Missing files, changed
bytes, escaping paths and symlinks are rejected. Export verifies the entire copy
and synchronizes its files before publishing the destination; an interrupted
staging directory is not a valid published delivery.

`verify` reads only: no gate replay, SQLite constructor, artifact registration or
hardware action. Deep verification hashes each unique external file once per
invocation and validates evidence selectors. It verifies the imported evidence
closure, not unrelated objects elsewhere in the old stores. Normal export does
not rerun the old expensive runtime gates.

Analysis/code corrections publish a new immutable revision. A failed publication
cannot replace the current valid revision; leftover `.staging-*` directories are
uncommitted forensic data. Resume uses the current pointer and exact record hashes,
never a partially written latest-looking directory.
