# Retrospective final storage catalogs

The storage integration supports `level2_closed_raw_storage_v2` and
`level2_storage_portable_v5`. It does not change capture, execution, profiler
flags, timing plans, calibration status, or the original report bytes and paths.
`msprof_raw_storage.py` and `cannbench_msprof_timing.py` remain byte-identical.

Final storage admission requires the separate reviewed data-only authority:
`retrospective_final_report_authority_v1`. This records that a full final report
replay was consistent at the later audit. It is not an assertion of authority
at original capture time, final source acceptance, or performance admission.
Final verification storage uses its separate v3 protocol. An uncommitted audit,
unknown final slot, changed source/report, or missing authority fails closed.

## Historical compatibility

The qualified raw v1 seals continue using their original AA/search scope and
exact closed facts, including verification producer identity `452c4791…` and
native producer `a08bb181…`. The current trusted verification reader `78ff7dfc…`
replays these reviewed historical semantics; it does not execute an archived
producer. Existing v1 seals and receipts are preserved, including resumptions of
partial retirement. Old v1 does not acquire final storage authority.

New destinations use raw v2 and pin the current `78ff7dfc…` verification identity.
Native output storage remains unchanged. The original archive's `producer.py`
is retained and hashed as inert evidence, not loaded as a reader. Legacy
portable closure versions v1–v4 and ordinary unarchived Level1 paths remain
supported. A v2 raw or v3 verification seal requires portable closure v5.

## Complete export

A retrospective authority includes a compact catalog: every logical origin's
hash/seal, one archive description per seal, and deduplicated complete closed
proofs. Only the documented `report_authority` slots are interpreted. Unknown
embedded dictionaries cannot grant authority.

The collector and portable exporter retain each full tar, seal, inert producer,
protected metadata and event-prefix journal. They recurse through every catalog
origin even when that origin is absent from the top-level evidence index. The
portable verifier requires exact catalog origin/dependency coverage, compares
complete proofs against their seals, and independently validates every raw,
verification and native archive with trusted current sibling modules. Merely
copying the catalog JSON is insufficient. Full raw inventories, non-CSV files
and empty directories are preserved. No raw member is recreated as an NFS CAS
object. Large archives use the existing streaming copy/hash path.

The facade exposes exactly six metadata binding fields. The legacy verification
reader's optional cached `bytes` field is accepted only for its reviewed
versions, checked against the logical digest, then omitted. Unknown fields or
forged payloads are rejected. Export executes no bundle-selected or historical
producer module; the offline CLI carries the trusted verifier implementation.

## Engineering and qualification

Freeze the installed authority, verification, raw and facade producers together
before use. The attestor pins the reviewed storage profile and includes the
authority reader in its actual engineering dependency closure. The FRESH producer
roster includes both final authority and attestor. Existing queue manifests stay
immutable and use the explicit historical-roster compatibility checks.

Tests use tiny synthetic captures and a real append-only ledger with an explicit
fake report analyzer. They include inert exact historical producer fixtures to
avoid external checkouts or temporary-package dependencies. These tests prove
storage composition and rejection behavior, not device measurements. Independent
review and a new real full-report/offline shadow are required before retiring
final evidence. Existing raw v1's real qualification does not substitute for that
new qualification. No automatic retirement or report authority is created by
exporting a bundle.
