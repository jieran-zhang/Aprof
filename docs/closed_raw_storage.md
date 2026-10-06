# Closed LOCAL raw storage and reader integration

This new helper is a separate post-capture storage layer. It does not change
`msprof_raw_storage.py`, `cannbench_msprof_timing.py`, capture argv, profiler flags,
capture filesystem identity, calibration epoch, samples or native execution cost.
The shared report/archive/dataset/portable readers passed independent review,
CPU regressions and a complete real six-process GN002 search shadow on
2026-10-06. Closed AA/search retirement uses a separate, explicit maintenance
transaction; final reports still require a separately reviewed authority path.

## Admission and scope

`prepare(session, destination=None, writers_closed=True, retire=False)` accepts
one session of an already successful **six-process LOCAL** cohort. Every process
is independently checked against the same existing report and original task and
campaign event prefixes. Eligible stage groups are `search` or `aa-*` only.
A/A requires an already-recorded calibration report pointer in a later registered
candidate timing plan. Search requires an already-closed measured feedback
observation pointing to this exact report and finished source stage. A new seal,
self-rehashed report, terminal stage alone, unanchored/final report, or caller
provided report hash cannot authorize storage.

The reviewed authority prerequisite is `level2_verification_storage.py` SHA256
`452c479151a6d0a9be43df4388a68f6577f0212c2fbd005c4501dbd8f43d7594`, together with
`level2_native_output_storage.py`
`a08bb1813cb7503b58ba95d9f1a780c61a433c955dbc8dd2254b66ac5985787c`.
The helper verifies these module bytes before importing/reusing their pure
`facts_for_version(..., ANCHORED_VERSION)` semantics. Future prerequisite changes
need an explicit reviewed compatibility update. No archive can select executable
code. `producer.py` in the archive directory is an inert provenance snapshot;
its source path/hash is informative, and is not re-imported or executed.

All six sessions must retain report-bound completion, execution, journal,
validation, bindings, original oracle evidence, and the four original raw
transport records. The copied-back raw manifest and full inventory remain at
original paths. Task and campaign journals are bound by the original stable
prefix, so legal later appends do not invalidate a seal. Historical prefix
mutation does. Original raw file hashes and sizes must occur in the independently
anchored original report and exactly match the original copyback inventory.

## Writer and recovery

The plain USTAR archive contains **every original raw file and every directory,
including empty directories**. The original logical root remains `session/raw`.
File modes inside the tar are normalized; the transport protocol did not record
original modes. No file-per-member CAS is created. With receipt, the normal
persistent storage cost is five files (`raw.tar`, `seal.json`, `producer.py`,
`maintenance.lock`, `compacted.json`) plus one directory per retired session.
Original transport records stay in place. No reclaimed-byte or inode count is
claimed without an actual filesystem measurement.

The writer holds the existing global maintenance lock and its own scope lock.
Tests replace the global lock; the tests never acquire the real device/host lock.
All mutations and source file opens walk ancestors using directory descriptors
and `O_NOFOLLOW`; symlink, special file, path traversal and unknown loose members
are rejected. Reads are chunked (1 MiB), except bounded metadata (16 MiB).

Tar bytes are fsynced, then published by no-clobber hard link. The seal and inert
producer snapshot are also fsynced and atomically published. The archive files,
archive directory and its parent directory are all explicitly synced before the
first original unlink. Original authority and hashes are rechecked at this
boundary. Each remaining file is checked again before unlink, and each directory
mutation is fsynced. Receipt publication happens only after the full raw tree is
gone and the sealed bytes and original authority still validate.

Existing seals and receipts are immutable. A crash after some unlinks resumes
from the full sealed archive and fresh original authority; absent members are
permitted only once a valid seal exists. Surviving loose files must retain their
exact original hashes, and unknown files or directories block retirement. A
receipt-write failure can replay after the tree has gone. A failure before seal
publication never deletes originals. An orphan tar can be reused only while the
complete original inventory remains intact and the resulting tar passes full
validation. Unexpected pending files are retained, not silently removed. A
failed or interrupted transaction is never reported as complete.

Shadow output must be under `/tmp`; a shadow destination cannot retire originals.
Actual retirement is restricted to `session/raw-archive-storage`. It must wait
for reader integration, independent review and explicit coordinator scheduling.

## Reader and analysis integration

`RawArchive(session, seal_ref)` independently derives the original report anchor,
validates all six closed sessions, every tar member, full tar grammar/zero trailer
and original capture identity, and verifies any surviving loose subset.
`logical_files()`, `fingerprint(path)`, `open_binary(path)` and
`evidence_binding(path, expected)` retain original absolute paths and hashes.
Use `reader_session()` around publication; its exit replays protected authority
and hashes. Maintenance references stay separate from `verify_transport()` so
replaying an original report does not add maintenance files to its artifact map.

`parse_profile()` projects only the two original CSV files into a temporary local
directory and calls the unchanged parser. The complete archive, including all
non-CSV data, is validated first. Only the exact reviewed `csv` and
`auxiliary_csv` fields are mapped back. Every known result/nested field is
allowlisted; unknown fields and path-shaped values elsewhere fail closed. The
parser must preserve both CSV hashes and cannot modify projected inputs.

The new `level2_evidence_storage.py` composes the unchanged verification and
native readers with the raw reader. An explicit raw shadow mapping declares an
archive even when its directory is missing: missing, invalid or foreign seals
fail before the context yields. Undeclared ordinary paths, including Level1,
keep the earlier loose-file behavior. Keep the shared storage context outside
any explicit native override, so final native/raw validation retains the
verification cache. Every context still revalidates before it completes.

`msprof_exploration_report.py` uses that facade for original transport facts,
parser CSV projection and explicit CSV reads. The returned report fields,
logical paths, samples, hashes and capture environment are unchanged. Archive
publication adds separate maintenance closure pointers; it does not insert
maintenance references into the original report. The archive and dataset
readers preserve logical file identities and stream native/raw payloads.

Portable output now uses `optimization_trace_portable_v3`. Raw closure uses
`level2_storage_portable_v4`; old portable v1/v2 inputs and earlier verification
and native closure versions remain supported. Signed dataset/record schemas
are unchanged. A raw evidence-map value contains only a seal digest and exact
member path. The validator derives bounded member offsets from the complete
tar and independently anchored original report. It never trusts supplied
offsets. Raw payloads stay in one full tar; no member CAS files are created.
All non-CSV files and empty directories are checked even when the dataset
indexes only one CSV. Nested raw/native/verification protected dependencies
are included and replayed with original ledger/task event prefixes.

External verification executes only its installed trusted sibling readers,
never helpers selected from the bundle. Bundled helpers support a separately
invoked offline CLI after copying. Inert historical `producer.py` bytes are
only hashed. Portable validation checks all inventory files, full tar/member
hashes, exact proof roster, signed evidence bindings, and detects changes
during deep validation. Unknown/final reports remain ineligible.

## Engineering and compatibility boundary

`FRESH_PRODUCERS` adds exactly `level2_raw_archive_storage.py` and
`level2_evidence_storage.py`. The five analysis consumers (report, archive,
provenance, dataset and portable exporter) also change and require a new
engineering snapshot before new work uses them. Historical analysis replay
uses only the existing explicit provenance substitution rule; this patch
adds no exception for arbitrary source, profiler or calibration identity.
`msprof_raw_storage.py` and `cannbench_msprof_timing.py` remain byte-identical.
Post-capture archival does not introduce a new capture epoch or make an old
calibration applicable to a different source/measurement protocol.

The prerequisite pin is explicitly updated from independently reviewed
verification helper `26f143865acae87198a1a583ad0ed5f647287c095a43e9ed9f15f9d540cbdfad`
to `452c479151a6d0a9be43df4388a68f6577f0212c2fbd005c4501dbd8f43d7594`.
That prerequisite change only checks an archive declaration before enforcing
the strict Level2 location, preserving unarchived Level1 compatibility.
The native helper remains `a08bb1813cb7503b58ba95d9f1a780c61a433c955dbc8dd2254b66ac5985787c`.
Both prerequisite files are byte-identical in this combined proposal and
its base; the patch does not modify them. The earlier standalone raw proposal
against 26f14386 remains a separate immutable review artifact.

The separate final-report attestor currently consumes the previous reader.
Using it after real raw retirement requires an explicit facade integration
and engineering freeze; this patch does not silently broaden its contract.
Fresh queue/coordinator plans with fixed producer rosters likewise need an
explicit refresh, preserving all prior plans and observations.

## Qualification and retirement boundary

A coordinator must first preserve an explicit request binding these exact
analysis producers and an already anchored, complete six-process LOCAL
AA/search report. Under the existing host maintenance lock, make read-only
shadow seals outside the campaign, replay the complete original report and
compare every field with only the established analysis producer exception.
Then build and verify a portable dataset using the shadow overrides, including
nested verification/native dependencies; verify it after hiding originals.
The qualification completion must be written only after reader contexts have
finished revalidation. Preserve failed/interrupted requests and use a fresh
namespace on explicit recovery. No final/unanchored report is eligible.
The engineering021 qualification completed with process exit0 and all reader
contexts closed. It preserved every original report field except the existing
explicit analysis-producer substitution, all logical evidence references, and
the original invalidated baseline calibration. Six new full raw archives cover
384 files and54 directories; their portable closure also contains six previously
retired verification-v2 archives. An independent process verified the complete
bundle with original RUN access denied, and a further invocation passed with
the entire repository denied from a `/tmp` working directory. These are
evidence-only proofs: no normalized memory, trace dataset or graph episode was
created by qualification.

Retained campaign proof:
`storage/maintenance/raw-shadow-qualified-021-20261006/completion.json`,
SHA256 `f1e6ed15f43dc16a3c8ebbf58d8f3e9413a61280507fb29e929ae9c897cd5dcb`.
The complete qualification archive has SHA256
`217e023ed906b0ecaff7070007a6378188b8b66a6488033aabe86b84ae3025df`.
The earlier engineering020 shadow failed because its reader omitted the parser
's boolean `fallback` field; all six failed shadows and their original request
remain preserved. See `raw_archive_dispatch_schema_fix.md`.

After qualification, a separately frozen48-session AA/search maintenance
request was issued. Only its eventual completion/receipts establish retirement;
qualification itself removed no original files. Each six-process batch may use
the public verification reader context, keeping every writer's own host and
maintenance locks. The outer reader must exit successfully before publishing
the batch completion; an outer host lock around `prepare` could self-block.


## Reproducible CPU check

In an integrated checkout containing the reviewed prerequisite patch:

```sh
PYTHONDONTWRITEBYTECODE=1 taskset -c 200-207 python3 -B -m pytest -q -p no:cacheprovider tests/test_level2_raw_archive_storage.py tests/test_level2_raw_storage_integration.py
```

For the isolated proposal, set `APROF_TEST_REPO` to the live read-only checkout and
`APROF_REVIEWED_STORAGE_ROOT` to this combined proposal. Both paths are
only code/fixture dependencies; tests generate all session data in pytest's `/tmp`
directory. Real maintenance requires a verified closed cohort, the qualification
above, explicit scheduling with selected writers closed, and sufficient free
space for durable archives before originals are retired.
