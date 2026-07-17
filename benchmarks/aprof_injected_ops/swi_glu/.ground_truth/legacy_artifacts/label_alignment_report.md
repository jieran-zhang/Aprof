# swi_glu Label Alignment

## Summary

- Total: 7
- Passed: 0
- Failed: 0
- Pending: 1
- Skipped: 6

## Cases

| Variant | Family | Problem ID | Ground Truth | Predicted | Status | Reason |
| ------- | ------ | ---------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | baseline | baseline | None | pending | no diagnosis prediction provided |
| inject_blockdim | tiling | blockdim_too_small | blockdim_too_small | None | skipped | quality_status=unverified |
| inject_dynshape | tiling | fixed_tiling_dynamic_shape | fixed_tiling_dynamic_shape | None | skipped | quality_status=unverified |
| inject_tail | tiling | tail_inefficient | tail_inefficient | None | skipped | quality_status=unverified |
| inject_tilelen_large | tiling | tile_length_too_large | tileLength_too_large | None | skipped | quality_status=unverified |
| inject_tilelen_small | tiling | tile_length_too_small | tileLength_too_small | None | skipped | quality_status=unverified |
| inject_tilenum | tiling | tile_num_unreasonable | tileNum_unreasonable | None | skipped | quality_status=unverified |
