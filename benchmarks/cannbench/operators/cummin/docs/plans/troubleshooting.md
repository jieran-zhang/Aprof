# Troubleshooting

## Strided scalar GM writes lost data

- Symptom: aligned last-axis cases passed exactly, while dim 0/1 cases produced many zeros and
  invalid gathered indices.
- Cause: 2-byte value and 8-byte index scalar stores to strided GM addresses are not a reliable
  bulk output path on dav-2201.
- Fix: scan 32 adjacent inner lanes in UB and write values/indices with 2-D `DataCopyPad`.
- Prevention: use scalar GM stores only for rows whose value and index byte lengths are both 32B
  aligned; route non-aligned and strided rows through UB + DMA.

## DataCopyPad tail UB layout

- Symptom: every complete 32-lane group was exact, but the final partial group produced invalid
  indices and very large relative error.
- Cause: `DataCopyPad` pads each UB-side block to 32B. The compute loop incorrectly addressed
  tail rows with `axis * width` instead of the padded UB row stride.
- Fix: compute independent padded strides for values and int64 indices:
  `align32(width * sizeof(type)) / sizeof(type)`.
- Evidence: after the fix, cases 1-20 pass on real Ascend910 hardware.
