# Troubleshooting

## Strided output cache-line race

- Symptom: case 8 initially had 114 incorrect values although heap selection was correct.
- Cause: different vector cores owned adjacent inner lanes and performed scalar stores into the same
  GM cache lines for each selected-axis row.
- Fix: for non-last axes whose row stride is not a 32-byte multiple, assign complete outer slabs
  (all inner lanes) to one core. Cache-aligned strided rows and last-axis rows use 32-lane-aligned
  sequence boundaries, retaining multicore execution for the large aligned cases.
- Prevention: scalar-store layout kernels must partition work at cache-line-safe output boundaries.
