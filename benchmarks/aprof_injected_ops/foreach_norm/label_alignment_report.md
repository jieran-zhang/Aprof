# foreach_norm Label Alignment

## Summary

- Total: 4
- Passed: 0
- Failed: 1
- Pending: 1
- Skipped: 2

## Cases

| Variant | Family | Problem ID | Ground Truth | Predicted | Status | Reason |
| ------- | ------ | ---------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | baseline | baseline | None | pending | no diagnosis prediction provided |
| inject_blockdim | tiling | blockdim_too_small | blockdim_too_small | tiling | fail | predicted_label=tiling |
| inject_redundant_copyin | data_movement | redundant_copyin | redundant_copyin | None | skipped | quality_status=unverified |
| inject_tilelen_small | tiling | tile_length_too_small | tileLength_too_small | None | skipped | quality_status=unverified |
