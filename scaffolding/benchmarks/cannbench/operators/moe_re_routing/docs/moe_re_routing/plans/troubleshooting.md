# Troubleshooting

## Sparse final scalar GM stores on dav-2201

- Symptom: token/index/count outputs were exact, but some isolated FP32 scale
  stores performed at the end of each multi-core token loop remained zero.
- Cause: the compiler/runtime path did not reliably publish sparse trailing scalar
  GM stores from that loop before D2H, despite stream synchronization.
- Fix: gather scales in the single-core routing builder. Its writes are contiguous
  and are followed by the token-gather kernel launch; all scale bits are preserved.
- Prevention: keep small contiguous metadata outputs in the metadata kernel rather
  than appending sparse stores to a large scalar token-copy loop.

## Rows smaller than one DMA block

- Symptom: an extra zero-count-cell test with int8 `H=3` showed missing token rows;
  every authoritative case (`H>=32`) still passed.
- Cause: direct scalar stores from several cores did not safely publish partial
  32-byte GM cache lines.
- Fix: stage one row in UB and use `DataCopyPad` in both directions with the exact
  byte count. This also explicitly covers non-aligned H and discards UB padding.
- Prevention: use padded DMA for arbitrary-width layout-transform rows, especially
  when the supported range permits less than 32 bytes.
