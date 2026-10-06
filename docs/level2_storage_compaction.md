# Closed storage journal compaction

This maintenance operation reduces **directory entries** after a fully completed output deduplication. It does not change output bytes, source, inputs, native measurements, the original transaction plan, the original dedup manifest, or historical public events. Actual filesystem quota relief must be observed; hardlink counts are insufficient.

Call synchronously after all writers exit and after the `closed_outputs_deduplicated` event durably binds the successful dedup manifest. The function acquires the collector's host lock and the storage lock; do not nest it inside either lock, or run it alongside a collector launch loop.

```python
from pathlib import Path
from level2_storage import compact_journals
# Existing coordinator has completed deduplicate(...) and event(...).
archive = compact_journals(run, Path(result['transaction']),
                           writers_closed=True, apply=True)
```

For an existing transaction, first inspect, then apply:

```sh
PYTHONDONTWRITEBYTECODE=1 python scripts/level2_storage.py \
  --run /absolute/run --compact-transaction /absolute/run/storage/transactions/HEX_ID \
  --writers-closed
PYTHONDONTWRITEBYTECODE=1 python scripts/level2_storage.py \
  --run /absolute/run --compact-transaction /absolute/run/storage/transactions/HEX_ID \
  --writers-closed --apply
```

Only `passed`, complete-accounting transactions without recovery or remaining backup/temporary output links qualify. Every original intent/result must agree exactly with the original manifest and plan. The manifest must be bound by a verified public event prefix. JSON/JSONL references to individual journal paths outside the transaction cause rejection: existing consumers must first gain a separately reviewed exact-path resolver.

The archive contains the original journal bytes as regular tar members; `journals.seal.json` preserves original full paths, hashes, lengths, mode, ownership, exact modification timestamps, plan/manifest pointers, and the stable event prefix. Tar and seal are fsynced and fully reverified before any journal is unlinked. `plan.json` stays loose. `journals.compacted.json` records completion without modifying old records. For 6,712 journal files in nine nonempty closed transactions, three archive records per transaction replace those files (6,685 fewer entries); this count is not a promise of filesystem quota accounting.

Rerunning the same command resumes an interrupted removal using the verified archive. A failure before durable seal leaves original journals; a failure after durable seal can leave some or none loose, with every byte retained in the archive. A failed archive publication can leave the complete archive without a seal: compaction can resume, while ordinary dedup recovery fails closed until it does. A failure after final publication may leave a complete receipt; reentry verifies it. Do not manually remove archive, seal, receipt, or temporary evidence to force acceptance.

`recover` and `KnownOutputLinks` revalidate compacted archives before using old transaction inventories. Missing markers cannot silently make a completed transaction appear empty: the original passed manifest still requires its complete journal set. `read_compacted_journal(original_absolute_path, expected_sha256)` returns exact historical bytes only after full verification; it rejects basename substitution and traversal. It does not automatically rewrite provenance pointers or extract files.

The current portable trace archive does not automatically include run-wide storage maintenance. When exporting storage evidence, explicitly include the archive, seal, completion receipt, original plan and manifest, and event prefix. The producer pointer in the seal records the implementation used; future replay does not require the current mutable producer file to retain those bytes. Preserve its engineering snapshot separately. This operation changes storage representation, not measurement or training evidence semantics.
