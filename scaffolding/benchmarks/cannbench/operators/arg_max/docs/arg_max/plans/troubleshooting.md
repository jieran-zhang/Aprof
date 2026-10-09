# Troubleshooting

## Scalar single-core reduction timed out

- Symptom: case 1 did not finish when one core performed 1,048,576 scalar GM
  loads.
- Cause: output-count partitioning exposed no parallelism and scalar GM access
  dominated the reduction.
- Fix: use tiled DMA plus vector ReduceMax for contiguous axes, and vectorize
  across adjacent inner positions for strided axes.
- Prevention: reduction designs must derive parallelism from both output and
  reduction dimensions and avoid element-wise GM traffic.

## Four zero indices at selected core boundaries

- Symptom: initial case 2 run had 76 mismatches, always four consecutive zero
  int64 values adjacent to a core boundary.
- Cause: the 52-output core partition was not 64-byte aligned. Neighboring
  vector cores issued scalar int64 GM stores to the same cache line and one
  read-modify-write sequence erased the other half-line.
- Fix: round `blockLength` up to eight outputs, leaving disjoint 64-byte-aligned
  GM regions for every core. The rerun and all remaining cases had zero
  mismatches.
- Prevention: align multi-core scalar GM output partitions to the hardware
  cache-line/store granularity, even when each scalar element is naturally
  aligned.
