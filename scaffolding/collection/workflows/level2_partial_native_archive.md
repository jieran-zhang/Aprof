# Partial Cummin control native archive

`level2_partial_native_archive.py` is a dedicated transport for a **failed**
Cummin full A/A control with terminal passed sessions. The ordinary native
archive correctly requires a completed six-process report; it cannot retire
this partial cohort. This adapter binds the immutable failed stage result,
the partial output dedup manifest and receipt, each passed session's
completion and validation, and every output bundle. It writes one USTAR
object per unique recorded SHA-256 and a seal that maps all original output
paths to those objects. Raw profiler and verification files stay loose.

Run a shadow with `--shadow-destination /tmp/NAME --writers-closed`. Construct
`PartialArchive(stage, shadow)` and replay original logical paths before a
canonical `--writers-closed --retire` run. The canonical tar, seal, and
directory are fsynced before any native output unlink. The reader validates
the full tar, every member hash, prior authority, and any surviving loose
aliases. An interrupted retirement resumes from the same verified tar; its
`compacted.json` receipt is written only after every mapped loose payload is
gone and the reader succeeds again. Only the fixed native payload files in
the dedup manifest are retired. All case bundles, validations, journals,
raw files, stage result, and source evidence remain unchanged.

The dedicated `PartialArchive` reader returns the original logical
fingerprint and streams bytes for a requested path. This failed control has
no full cohort report and cannot calibrate final timing or feed an ordinary
finalizer. Its evidence must be accessed through this reader after retirement;
the general six-process reader does not treat an incomplete control as passed.
The original failed control and actual work cost remain in the ledger.
