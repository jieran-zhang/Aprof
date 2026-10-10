Closed native-output archives preserve measured logical evidence while reducing directory entries. Apply producer changes and perform maintenance only between closed stages.

New cohorts without a prior output-dedup event may use the explicit
`--report-authority` option. This writes `level2_closed_native_outputs_v2`
only when the existing closed feedback, A/A calibration, or retrospective final
report attestation independently binds the complete report. The report must
pin every native output hash; the session request, passed validation, native
journal, and all named output parts still have to agree. Example:

```sh
python scaffolding/collection/scripts/level2_native_output_storage.py \
  --cohort /absolute/run/train/tasks/gather/candidates/gather003/stages/final/direct_parent \
  --writers-closed --report-authority --retire
```

Use a `/tmp` shadow destination without `--retire` to qualify a new cohort
first. The reader replays the archive and the original report authority before
retiring any output. An existing v1 seal remains v1; the flag cannot relabel it.
Historical v1 receipts and their dedup requirement remain unchanged.

Historical v1 scope is fixed native output bundles of a terminal-passed six-process Level2 cohort. Its helper reads real original hashes from an already event-bound, passed `level2_output_dedup_v1` manifest; it does not create maintenance authority, rerun native code, broaden case coverage, or infer that current self-consistent output/report hashes are original. The earliest scoped authority pins every binary/part hash and byte count, each named bundle index and the original requested/validated roster. A v1 scope without that prior event-bound inventory is blocked. Profiler raw trees, journals, pilot outputs, standalone/runtime/boundary outputs, inputs and source are out of scope.

The canonical implementation passed 674 regression tests (one skipped), plus focused and independent admission checks. Engineering snapshot019 qualified the real ArgMax aa-local-01 cohort in a /tmp shadow: all six processes, twenty cases, 480 output paths and 183,987,840 logical output bytes. The full report, original logical references and A/A calibration cards matched; the only permitted difference was the independently attested analysis-producer hash. An evidence-only bundle containing the native archive and six nested historical verification archives passed offline validation with original-run reads denied. No native call, source round, live output retirement, learned memory or graph episode was created by this qualification. This does not qualify every historical output or the named-output path.

Storage format `level2_closed_native_outputs_v1`:

- One uncompressed tar per cohort, with unique SHA-256 content objects. A separate seal maps each original absolute path/hash/length to its object; neither original report references nor measured records are rewritten.
- Large payloads are hashed, copied, checked and read through bounded streams. The strict metadata-only byte reader is capped; large readers use `open_binary`. Named outputs retain complete framed bundle bytes, exact key ordering, each part and its original index; streamed bundle-vs-part equality is checked.
- The original completed-stage prefix and later passed-dedup event prefix, original dedup manifest, relevant immutable index evidence, original report and closure are all retained. A new seal cannot substitute rehashed current outputs for the old passed inventory.
- All archive/seal/producer files, archive directory and parent are fsynced before the first original unlink. Unsealed partial archive files fail closed for explicit review. Sealed partial retirement resumes against exact surviving bytes. Complete receipts reject reappearing originals.
- The self-contained producer snapshot is inert evidence and never executed. Offline portable validation loads only the installed verifier's trusted reader and reconstructs the full expected member roster from the protected originals. Dropping an unsigned member and rehashing supplemental files is rejected.

Reader changes:

- `level2_verification_storage` keeps existing v1 `resolve`/seal semantics and provides the shared streaming reader, fingerprint, native logical listing and native closure branch.
- `msprof_exploration_report.sha`, `level2_adapters.verify_output_metadata`, archive pointer projection and provenance SHA use the shared strict reader.
- `trace_v2_dataset` uses streaming fingerprints for evidence without selectors. Portable export copies native members in bounded chunks and carries the complete tar/seal/protected-proof mapping. Mixed maintenance closure uses `level2_storage_portable_v2`; nested archives use v3 with a parent-proof-bound dependency graph. Native proof references to already-retired oracle executions recursively carry the verification tar, seal, inert producer, protected proofs and ledger prefix. Previous verification-only closures and portable-v1 remain readable. Export explicitly revalidates source archive proofs before publication.
- Output dedup recognizes fully retired scopes as `verified_archived`, validates them and does no mutation. A mixed retired/loose stage is rejected with an explicit request to process the remaining cohorts. `level2_iteration.reclaim_outputs` returns this no-op without manufacturing a second dedup transaction/event. KnownOutputLinks only omits missing old aliases after verifying their sealed retirement.

Version/producer implications:

`level2_native_output_storage.py` and the actually used `level2_verification_storage.py` are explicitly added to FRESH_PRODUCERS. This changes the fresh engineering producer roster. Do not refresh immutable old queue requests by swapping hashes; use the separately reviewed historical-roster compatibility/handoff rules and a new engineering snapshot. Current report/adapter/iteration/portable helpers also change hashes. No running or already-frozen producer set may be replaced silently. The patch has no automatic archival integration; every retirement is an explicit root action between closed stages.

Shadow CLI, after confirming all writers are closed:

    PYTHONDONTWRITEBYTECODE=1 taskset -c 200-207 python scaffolding/collection/scripts/level2_native_output_storage.py --cohort /ABS/CLOSED/cohort --shadow-destination /tmp/native-output-shadow --writers-closed

An explicit production `--retire` uses only the canonical cohort/native-output-storage directory and requires the prior passed dedup authority. Qualify the relevant output family before retirement; preserve the separate shadow proof.

Small tests use PYTHONDONTWRITEBYTECODE=1 and `-p no:cacheprovider`. The real shadow request, replay, offline result, implementation reviews and regression log are retained under the campaign storage maintenance evidence. The shadow bundle is an evidence-transport qualification, not a full optimization-memory/lesson dataset export. No full-repository suite or real evidence replay was run concurrently with native timing.

Material limitations and remaining qualification:

1. The real unary ArgMax cohort passed. A real named-output cohort and a genuine full trace dataset export still require qualification; synthetic named-output fixtures do not establish those results.
2. Archives do not reclaim raw profiler namespace entries. Keeping the existing global output CAS can retain an extra physical copy; this patch does not garbage-collect it or claim physical bytes reclaimed.
3. The portable bundle currently carries the cohort tar plus ordinary content-deduplicated evidence CAS members needed by the unchanged signed-index format. Copying is streaming but can duplicate physical bytes. It does not recreate one file for every logical alias.
4. Metadata is bounded to 16 MiB. Unsupported/oversized metadata fails closed; no silent truncation is accepted.
5. The current archive verifier streams full hashes again before reader return/publication. This costs I/O; do not benchmark concurrently. File metadata is not a substitute for the original content hash.


New verification archive admission:

All newly written verification seals use `level2_closed_verification_storage_v2`. Before creating the destination, admission requires an independent existing ledger prefix that fixes the exact report path and SHA. Only two exact slot families are accepted: closed same-candidate `observe.feedback.comparisons[].report`, and same-workload candidate timing `start.plan.calibration_report` or the two known unique relation entries' `calibration_report`. The original successful stage start plan and finish result must match the closed process. Ledger canonical hash chain, immutable config, candidate identity, feedback hash and report relation are checked. For v2, the original report must also pin each session validation, bindings, completion, native execution and journal hash, the complete six-process list and the complete metadata/execution/stdout oracle roster; dropping validation rows cannot shrink the admitted archive. The selected prefix is stable when later unrelated events append. No ledger/event is created or altered by admission.

A finalizer completion currently writes its report pointers only to an ordinary completion file. Its earlier request/freeze does not fix reports generated afterward. That completion alone cannot authorize a new v2 archive. Missing historical authority blocks new publication; do not manufacture an event or ledger observation to satisfy this helper. An independently reviewed future attestation would require its own explicit protocol.

The independent report anchors the original `metadata.json`, `execution.json` and `stdout.log` hashes recorded by the report. The fourth oracle result file (`result.json`, or AdamW `precision.json`) may not have a prior report hash. Its current exact bytes are preserved in the seal/tar, but v2 does not claim a nonexistent independent prior hash for that fourth file.

Existing retired v1 seals, receipts and payloads remain unchanged and readable under their original strict format. Their guarantee is preservation of the sealed bytes and the report hash observed at sealing time, not independently earlier report authority. The reader does not backfill the stronger v2 claim. New retirement of an unretired v1 seal is refused; keep that evidence and separately qualify an anchored v2 archive. A self-contained v1 transport is not cryptographic proof that it predates the change; proving historical creation time would require an externally frozen seal inventory.

Ordinary files, including unarchived Level1 output names, use ordinary streaming reads when no native storage marker/shadow is declared. An existing invalid archive or explicit invalid shadow never falls back to ordinary bytes.
