# GN002 final pre-native recovery

This extension admits one explicit second attempt for the preserved
`group_norm002-final` import failure. It does not turn the first failed attempt
into a success, release a charge, register a source, change a frozen final plan,
or assert that any native recovery has occurred.

The original `stages/final/result.json`, `stage-plan.json`, original finalization
request, task journal, and campaign journal remain unchanged. Qualification
appends a `qualify_prestart` campaign event and a `stage_prestart_qualified` task
event, after durably storing `prestart-recovery/qualification.json` and immutable
journal prefix copies. The certificate binds the exact `ModuleNotFoundError`,
zero native/sample/cost evidence, the two-file original stage inventory, six
retained failure artifacts, original022 and actual new engineering snapshots,
original final request/plan/source, and reviewed recovery producer source CAS.

Execution is separate and one-shot. It checks explicit canonical `PYTHONPATH`,
uses the same frozen cohort paths, and creates only
`stages/final/result.recovery-01.json`. The original ledger attempt stays failed;
the second real start is counted, while its timing-group charge remains zero
because the original failed start already consumed that group. A successful
result requires the actual second finish, matching result/certificate evidence,
14,400 role samples and six started/completed native processes. Qualification
alone never authorizes a successful report or storage seal. Partial publication
or a failed second attempt requires an explicit new decision; no automatic retry
or overwrite is available.

The shared data-only resolver returns the current immutable result, original
failed result, qualification, fixed protected references, and hash-checked stable
journal prefixes. It never executes archived code. Ordinary passed stages keep
the original path and do not gain a recovery or ledger dependency. Consumers
include iteration/finalizer, attestor/authority, verification/native storage,
dedup inventory, provenance and Archive. Archive retains both attempt outcomes
and attaches each comparison cohort once. Finalizer producer drift is accepted
only through this exact certificate and actual new engineering; it compares the
rest of the original frozen request byte-equivalent structure without rewriting
it.

New raw writes use `level2_closed_raw_storage_v3`. Existing v1 and v2 seals replay
their original authority producer identities: v1 verification452/nativea08 and
v2 verification78ff/nativea08. They cannot acquire recovery facts. Existing
seal/receipt/facts bytes remain unchanged. New portable exports include the
trusted stage resolver as an eighth helper. The new AA/search qualifier v4,
resumer v3, and final-shadow qualifier v2 are separate `/tmp` packages; old
seven-helper packages are preserved. Native and verification reader changes are
bound by the actual new engineering epoch; both capture producers are unchanged.

A new installed engineering freeze and the independently issued real AA/search
raw-v3 qualification are required before new production retirement. Final raw
retirement separately requires an actual completed final, a committed reviewed
retrospective attestation, and the final six-session shadow plus full catalog
offline qualification. CPU fixtures and source review do not substitute for
these real qualifications.

Future operator commands (root supplies actual paths/hashes):

```sh
export PYTHONPATH="$REPO/scripts:$REPO/src"
python3 -B "$REPO/scaffolding/collection/scripts/level2_prestart_recovery.py" audit --run "$RUN" --engineering "$ENGINEERING" --engineering-sha256 "$ENGINEERING_SHA" --writers-closed
python3 -B "$REPO/scaffolding/collection/scripts/level2_prestart_recovery.py" authorize --run "$RUN" --engineering "$ENGINEERING" --engineering-sha256 "$ENGINEERING_SHA" --writers-closed
python3 -B "$REPO/scaffolding/collection/scripts/level2_prestart_recovery.py" execute --run "$RUN" --qualification "$QUALIFICATION" --qualification-sha256 "$QUALIFICATION_SHA" --writers-closed
python3 -B "$REPO/scaffolding/collection/scripts/level2_finalize.py" --run "$RUN" --operator group_norm
```

Authorization and execution are owner-scheduled actions. None were run while
preparing this patch. Use the existing frozen timing settings; no global
`direct_parent` calibration override is introduced.
