# Closed verification tree storage

The verification storage tool preserves original bytes and logical path/hash
identities in one tar per closed native process. Only `metadata.json`,
`execution.json`, `stdout.log` and `result.json` in canonical case/config/role
directories are eligible. Profiler raw data, native outputs, source, prepared
inputs, stage reports and measurement plans remain unchanged.

Run only after all writers have exited and the six-process cohort and enclosing
stage are terminal passed. The existing completed-stage event must bind that
stage result. Example (use exact sessions from `group-completion.json`):

```sh
python scaffolding/collection/scripts/level2_verification_storage.py \
  --session /absolute/run/train/tasks/maximum/stages/aa-local-01/cohort/aa-local-01-p01 \
  --writers-closed --retire
```

The tool acquires the existing exclusive host lock and a storage lock. It does
not automatically integrate with collectors. A full 20-case six-process stage
has 1,920 eligible files and 480 case directories. Measure actual filesystem
namespace relief; hardlink counts alone do not prove quota savings.

Each session retains `verification-storage/verification.tar`, `seal.json`, an
exact maintenance `producer.py` snapshot and `compacted.json`. The archive,
seal, producer, destination directory and its parent are fsynced before any
original unlink. Partial retirement resumes from the same verified archive.
Missing or corrupt closure fails closed. Exact file metadata is in the seal;
tar headers retain their supported timestamp precision.

A shadow invocation uses `--shadow-destination /tmp/...` without `--retire`.
Readers opt into shadow locations through a scoped mapping. The actual Maximum
A/A shadow proof reads 1,440 report-bound files from tar and reproduces the full
report and its original logical hashes without retiring any live evidence.

The reader checks the complete fixed closed-state proof, event prefix, all
validation rows times four files, tar metadata and bytes, and any remaining
loose files. Transaction-scoped caches revalidate before return; archive
publication explicitly revalidates before replacing the public revision.
Only one shared mapping document per archive is created, avoiding per-member
NFS CAS files.

Portable bundles include archive/seal/producer bytes, closed-state proof and
logical mapping. Verification recomputes the complete roster, including files
not individually indexed by historical signed records. It executes only the
trusted verifier's own sibling reader, never a helper selected by the untrusted
bundle or the historical producer snapshot. The offline bundled CLI naturally
uses its sibling. Legacy portable v1 bundles without storage closure remain
readable.

Other readers must use the strict storage or v2 evidence reader for retired
logical files. Missing unrelated files, basename aliases, wrong hashes and
files outside this fixed scope are never substituted. Raw-profiler and native
output retirement are unsupported.
