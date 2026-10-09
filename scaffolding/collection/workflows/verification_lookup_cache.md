# Optional transaction-scoped verification lookup cache

The verification reader can cache already validated member bytes within one
explicit transaction. This changes no campaign data, report, old seal, capture
producer or native execution.

Positive lookup requires explicit `reader_session(cache_verified_bytes=True)`.
The default is false and actively suspends any inherited lookup map. Before
yielding to a default nested writer and before restoring the opted-in parent,
full inherited validation runs; a nested failure poisons the parent transaction.
Thus unchanged native.prepare and deduplicate use their original physical
lookup/signature checks even inside an opted-in caller. A read-only nested helper
may explicitly inherit policy via `lookup_cache_enabled()`. Only the separately
audited raw maintenance writer should enable this policy in the current release.

After one archive passes all existing validation, its exact member paths map to
the already verified in-memory payload within the active reader transaction.
The map key includes the declared archive destination; nested shadow scopes
cannot reuse the canonical destination's entry. Positive hits still perform
canonical scope checks. Missing declarations, unsealed members, ordinary Level1
paths, and errors are never cached. All existing byte/open/fingerprint/is_file
aliases use the same resolution path. The map is discarded at outer context exit.

A positive hit intentionally uses a verified snapshot. Physical mutation is
detected at explicit `reverify_cached()` or successful outer context exit, rather
than at every hit. Those boundaries clear and bypass the lookup map, perform the
complete original archive/producer/protected evidence/loose tree/ancestor checks,
and require the original immutable seal hash to remain identical. Failed explicit
revalidation and failed nested reader contexts poison the whole transaction;
catching an exception cannot produce a successful outer close. A fresh opted-in context
starts from empty state. Without opt-in, no logical map is created.

The raw writer explicitly completes revalidation before seal publication,
original-file unlink and the completion receipt. See
[raw maintenance boundaries](raw_lookup_cache_boundaries.md); the reader alone
does not supply those publication boundaries.
Callers must finish successful revalidation before durable publication, event
append, or retirement under their existing locks. Default writer contexts retain their existing physical lookup semantics.
No native or dedup producer change is included or required for this opt-in policy. This patch changes no raw or native streaming,
cohort-fact parsing, authority acceptance, report facts, or persisted seal schema.

The local synthetic six-session fixture has 72 oracle hash inputs and 26 path
ancestors. The previous warm 1440 reads made 456480 stat/lstat calls. The candidate
makes zero filesystem calls for those positive hits and reduces complete explicit revalidation from 18828 to 13650 calls.
The additional reduction uses lexical checks for virtual tar member paths; real
session ancestors remain physically checked, a dangling loose-root symlink is
explicitly rejected, and every actual loose descendant retains the original
strict scan and byte checks. All physical tar/seal/producer/protected proof checks
remain. The one-case fixture does not quantify full20 or NFS latency. These are filesystem-call counts from
small `/tmp` data, not a measured NFS speedup. See the separate qualification
`lookup-counts.json` and previous audit for full details.

The focused tests exercise cold/hot aliases, no cross-context cache, ordinary
Level1 paths, absent-to-invalid declarations, canonical and unknown members,
seal/tar/producer/report/control mutation, loose-member reappearance, ancestor
symlinks, pre-publication failure, sticky error state, nested shadow identity,
valid appended events, and an otherwise-valid resealed JSON identity change.
Existing verification and native storage regressions are also rerun.

## Integration boundary

Do not hotpatch a running maintenance or measurement process. The changed
verification SHA requires a separately reviewed raw reader revision with an
explicit reviewed current pin, and an updated attestor profile/engineering
closure. Preserve every published package and old raw v1 facts (452/a08), seal,
receipt and report. Code installation does not qualify final retirement; the
separate actual full-report/offline qualification is still required. Scope shared
maintenance contexts to one six-process cohort, since every explicit recheck
revalidates all archives visited by that context.
