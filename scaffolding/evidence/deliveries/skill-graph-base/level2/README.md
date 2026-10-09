# Level2 selected source projects

These are the complete tested implementations selected so far in the `skill-graph-base` campaign on Ascend910_9392 (910C), CANN 9.0.0. The campaign is still in progress.

| Operator | Selected candidate | Correctness coverage | Selection basis |
| --- | --- | --- | --- |
| RMSNorm | `rms_norm003` | All 20 standalone/prepared cases and 10 extra guards | Correctness replacement after two original-baseline guard failures; full-case task-sum comparisons are descriptive. |
| GroupNorm | `group_norm002` | All 20 standalone/prepared cases and 7 extra guards | Correctness replacement after two original-baseline guard failures; no confirmed speedup. |

Each `op/` contains the entire original source snapshot, including host dispatch, kernels, build files and original project documentation. Rebuilding its deterministic snapshot with `prepare_trace_pilot.create_source_snapshot` and the selected candidate ID as `root_label` reproduces the recorded source SHA-256 exactly. The delivery copy required no new native execution.

`manifest.json` records every source-file hash, the complete snapshot hash and copied identity sidecars. Each `evidence/` preserves the original selection, proposal, source binding, parallel/dispatch plans, launch mapping, patch and source tar bytes. Their historical absolute evidence pointers are retained. Full measurement archives and portable trace/lesson export remain separate pending campaign deliverables; these sidecars alone are not a complete measurement bundle.

Formal runtime admission remains `not_evaluated`; these research results do not generate trainable graph episodes. The original selection receipts contain uncertainty and coverage limits.
