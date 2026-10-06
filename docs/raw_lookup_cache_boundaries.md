# Explicit lookup caching at raw maintenance boundaries

This implementation keeps native-output and dedup producers unchanged. The
verification reader defaults to the previous eager path checks, including inside
an already opted-in caller. A nested default context temporarily suspends the
positive lookup map; closing it restores the caller's policy.

Only `level2_raw_archive_storage.prepare` enables the optional lookup map. It does
so inside its existing host lock. Read-only `cohort_facts` inherits the caller's
policy and never enables it itself. Full verification revalidation occurs after
streaming and the final authority comparison, before seal publication. The raw
reader first rechecks retained metadata, raw bytes and original cohort authority,
then forces full physical verification revalidation while the map is enabled.
The last logical read therefore precedes the final physical check.
Existing calls to this reader check immediately before unlink and again before
publishing the retirement receipt. The enclosing reader context exits and
revalidates while the host lock is still held.

A failed pre-seal check leaves all originals intact and publishes no seal. A
failed pre-unlink check preserves the durable seal and all original raw members.
A failure after unlink but before the completion receipt preserves the durable
archive and fails closed; restoring the exact original authority permits ordinary
idempotent resume. No automatic authority repair or receipt fabrication occurs.

The new raw-v2 writer pins the reviewed optional-cache verification producer.
Existing raw-v1 closed facts continue to use their original verification `452c…`
and native `a08b…` identities. No old seal, inert producer snapshot, or receipt is
rewritten. The capture and timing parser remain byte-identical. The real raw-v1
qualification does not qualify this producer generation: fresh raw-v2 AA/search
shadow, original-report comparison and offline closure are still required before
new production retirement. Final retrospective authority needs its own real audit
and final archive qualification.

Tiny tests deliberately mutate retained verification metadata after archive
streaming, immediately before unlink, and after unlink before receipt publication.
These are synthetic storage checks, not native execution or performance evidence.
