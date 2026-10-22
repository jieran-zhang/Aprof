# Exp case 1 baseline prewarm diagnosis

This is a new, diagnostic-only experiment prompted by the frozen v2-local exp case 1 cycle 3 Task control failure. It cannot qualify a measurement method or publish a skill. The predecessor source, binary, input, verifier, failed raw evidence, and root-anchored roster are bound before any new run.

## Fixed comparison

- Six paired cycles, each with two fresh `msprof` application processes. Even cycles run A then B; odd cycles run B then A. Each of the 12 slots runs once. A uses the original v2 exp binary and the original 19-command confirmation protocol at repeat 100.
- B copies the original exp source into the new diagnostic directory. Its sole source change is one exact insertion in `op_host/device_shared_timing.h`, after the original immutable input snapshot and before the original warmup. It calls the original **baseline** callback 400 times and synchronizes the same stream, repeated for 25 batches. It records each batch's index, 400 calls, cumulative count, and monotonic start/end. The original 20 warmup calls, 400 prime calls per phase, 30 measured pairs, and two untimed verification snapshots remain in place. The original READY plus 19 command responses remain unchanged. A separate `APROF_PREWARM_JSON` line is diagnostic evidence, not an original protocol message. No extra device-to-host input check occurs between the prefix and original warmup; the original final `complete.input_bytes_unchanged` check compares against the snapshot taken before the prefix and therefore covers the full prefix and native sequence.
- Both use the original exp case 1 prepared input and two original verifier commands. Captures use the original seven `msprof` flags and a unique private `/tmp/aprof-exp-prewarm-<output.name>` scratch tree. Capture and any export happen locally. The complete capture tree before export, when export is needed, and the complete final profile tree are copied to the new persistent slot with full file hashes and an atomic transfer receipt. No historical directory is modified.

## Task accounting and interpretation

The entire original CSV is retained. A requires exactly 4,222 single-stream, nonoverlapping, registered compute tasks. B requires exactly 14,222: an exhaustive 10,000-task baseline prefix and the original 4,222-task sequence. The frozen Task parser validates device, stream, task identity, finite positive duration, chronology, overlap, type, names, and all 30 original macro pairs. B first validates the **full** table, saves an explicit original-row mapping for 25 groups of 400 prefix tasks, then derives only the original 4,222 rows and passes that derived table plus the unchanged real native messages to the frozen parser. The derived file is stored and checked byte-for-byte on replay. Replay also requires the original final `complete.input_bytes_unchanged=true` receipt. The prefix is excluded from pair means; all tail pairs remain. No max selection, tail trimming, or treating 10,000 prefix tasks as independent samples.

The report stores per-cycle A/B Task means, exact Task control summaries, Event and host diagnostics in the original partitions, and the complete raw CSV. A control limit failure remains a diagnostic result and does not stop the fixed matrix. Native/profiler facility failure, missing/extra/unknown Task, changed source/input/profile, wrong prewarm receipt, or oracle failure stops the matrix immediately and retains every completed slot and the failed-slot receipt. The report always states `accepted=false` and `publication_acceptance=false`.

## Sequence after the current hardware quiet window

1. Review and run only the new synthetic tests and one diagnostic B CANN build check. No test/build is authorized during the current quiet window.
2. `prepare --output <new-directory>` copies and proves the single source patch; `build --output <new-directory>` builds B exactly once; `freeze --output <new-directory>` binds all source, inputs, producer helpers, binary, original failure, profiler and matrix.
3. Root writes a new curation anchor binding `freeze.json`, with `schema_version=1`, `purpose=exp_case1_baseline_prewarm_diagnostic_only`, `max_attempts=1`, `resampling=none`, and an aware UTC `recorded_at_utc` after freeze.
4. `run --output <new-directory> --anchor <root-anchor>` executes the fixed 12-slot matrix once under the host/device locks. `replay` recomputes Task partitions, transfer inventories, original oracle results and the report from persistent evidence without requiring `/tmp` to survive.

The script is `scaffolding/collection/scripts/diagnose_exp_case1_prewarm.py`. No 0.5.1 package file, frozen producer, or old campaign file is edited by this plan.
