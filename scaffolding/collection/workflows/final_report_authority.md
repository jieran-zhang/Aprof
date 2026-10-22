# Retrospective final-report authority

The reader validates retained metadata without executing native analysis or
retiring files. It accepts only a
separately committed `final_report_consistency_attested` event whose attestation
uses `level2_final_report_consistency_attestation_v2` and a specifically reviewed
writer SHA / exact storage-profile digest. A newly read report or bare finalizer
completion cannot create authority. Old attestation v1 conveys no new permission.

The statement remains `historical_report_authority: false`: the earlier full
replay established consistency at the later audit, not at original capture time.
No performance qualification, calibration status, final selection, source round,
budget, or ledger observation is changed by this reader.

The reader checks canonical final task/candidate/relation paths; the durable task
event; immutable audit request and original ledger prefix; the separately frozen
finalization request; three registered/closed source attempts; all qualified final
plans, completed stages and exact parent/build source identities; every full
20-case x normal/swapped x six-process saved comparison and its full calibration
replay record; original report artifact identities; and engineering/CAS producer
proofs. It reconstructs the original cost counters from the ledger prefix. Valid
later task/ledger event suffixes do not alter this historical prefix. Source CAS
and archived producer snapshots are inert bytes and are never executed.

The bounded metadata callback deliberately does not read tensor/profiler payloads.
This reader validates a typed previously completed full replay; it does not claim
to independently perform that replay again. Its result has `protected` metadata,
`event_bindings` for the immutable prefixes, and the full `storage_catalog`.
`reconstruct_catalog(authority)` returns one complete binding per original seal
and every exact logical origin. A portable exporter MUST carry and stream-hash
all those seal/archive/inert-producer/protected/event objects and run the current
trusted storage-kind validators offline, even for archives with no directly
indexed member. Carrying the catalog JSON alone is insufficient. The raw reader,
evidence facade and portable exporter implement that complete closure; see
[final storage catalogs](final_storage_catalog.md). Actual full-report and offline
qualification must precede final retirement.

The verification delta introduces `level2_closed_verification_storage_v3` for
new final-only archives. Existing verification v1/v2 readers and AA/search v2
writer admission remain unchanged. Old v2 cannot gain final authority through the
new event. The raw integration must preserve old raw v1 AA/search facts including
its declared original 452c/a08 producer hashes; new raw v2 must explicitly pin the
new verification producer and use FINAL_VERSION for final cohorts. Capture
producers and old archive bytes remain unchanged.

The fresh-producer delta adds `level2_final_report_authority.py` and
`level2_final_report_attestation.py`; future engineering must freeze both actual
bytes. Historical queue producer-roster handling must remain explicit and strict.

The writer allowlist retains reviewed attestor v3 and also admits the exact v4
writer/profile described in [the writer admission record](final_authority_writer_v4.md).
Each future writer requires independent review and an explicit source/profile
row. The writer binds the authority reader through the actual engineering CAS,
avoiding a circular static hash dependency. Old attestor bytes remain unchanged.

Tests use real small campaign ledgers and the existing attestor fixtures with an
explicit fake native analyzer. They do not validate a real final performance
report, invoke a device, or read actual tensor/profiler payloads. Actual whole-final
qualification remains an explicitly scheduled root-owned quiescent operation.
