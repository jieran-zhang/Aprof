# Troubleshooting

## dav-2201 scalar cast restriction

- Symptom: compiler rejected `float(uint64_t)` inside an AICore function.
- Cause: dav-2201 forbids this scalar conversion in device code.
- Resolution: precompute `1/D` and `1/sqrt(D)` in host tiling data.
- Prevention: place shape-derived floating constants in tiling structures.

## Non-aligned BF16 state corruption

- Symptom: D=769 produced sparse zero/corrupt `conv_state_out` values while
  aligned cases passed.
- Cause: scalar 16-bit GM stores and non-32B-safe cross-core boundaries.
- Resolution: align partitions and stage state rows through a LocalTensor with
  `DataCopyPad`; Stage-1 FP32 row workspaces use the same DMA discipline.
- Prevention: never use cross-core scalar GM stores for non-aligned BF16 tails.
