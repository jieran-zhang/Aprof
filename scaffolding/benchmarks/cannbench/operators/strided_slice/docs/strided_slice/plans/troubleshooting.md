# Troubleshooting log

## [Phase 0] Skill entry path differs from plugin root

**现象：** `ops-direct-invoke-flash/SKILL.md` does not exist at the plugin root.
**根因：** The plugin stores the skill at `skills/ops-direct-invoke-flash/SKILL.md`.
**解决方案：** Located the manifest with `find` and read the complete actual skill.
**经验：** Resolve plugin skill paths from the bundle layout before assuming a root file.
**预防：** Check `skills/<name>/SKILL.md` first for official plugin bundles.

## [Phase 7] Adjacent-core scalar-store corruption

**现象：** Case 8 had 79 mismatches among 62,500 fp32 outputs while larger aligned
cases and the affine index mapping were exact.
**根因：** The initial per-core flattened ranges ended at non-64-byte boundaries,
allowing adjacent vector cores to update the same GM write block.
An initial 32-byte alignment reduced but did not eliminate the missing boundary stores.
**解决方案：** Align `blockLength` upward to `64 / itemBytes` elements, preserving
disjoint cache-line ownership; the final core still clips to `totalLength`.
**经验：** Scalar GM writes still require reasoning about cross-core 64-byte ownership.
**预防：** Always align flattened multicore output partitions to the hardware write
block size for storage-preserving layout kernels.
