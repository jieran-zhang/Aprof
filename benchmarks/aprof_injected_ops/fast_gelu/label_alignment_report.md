# fast_gelu Label Alignment

## Summary

- Total: 7
- Passed: 0
- Failed: 0
- Pending: 3
- Skipped: 4

## Cases

| Variant | Ground Truth | Predicted | Status | Reason |
| ------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | None | pending | no diagnosis prediction provided |
| inject_blockdim | blockdim_too_small | None | skipped | quality_status=deprecated_or_weak |
| inject_dynshape | fixed_tiling_dynamic_shape | None | skipped | quality_status=weak |
| inject_tail | tail_inefficient | None | pending | no diagnosis prediction provided |
| inject_tilelen_large | tileLength_too_large | None | skipped | quality_status=weak |
| inject_tilelen_small | tileLength_too_small | None | pending | no diagnosis prediction provided |
| inject_tilenum | tileNum_unreasonable | None | skipped | quality_status=weak |
