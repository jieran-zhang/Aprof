# fast_gelu Label Alignment

## Summary

- Total: 7
- Passed: 0
- Failed: 0
- Pending: 0
- Skipped: 7

## Cases

| Variant | Family | Problem ID | Ground Truth | Predicted | Status | Reason |
| ------- | ------ | ---------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | unknown | baseline | None | skipped | active case missing problem_family/problem_id |
| inject_blockdim | blockdim | unknown | blockdim_too_small | None | skipped | quality_status=deprecated_or_weak |
| inject_dynshape | dynshape | unknown | fixed_tiling_dynamic_shape | None | skipped | quality_status=weak |
| inject_tail | tail | unknown | tail_inefficient | tiling | skipped | active case missing problem_family/problem_id |
| inject_tilelen_large | tilelen_large | unknown | tileLength_too_large | None | skipped | quality_status=weak |
| inject_tilelen_small | tilelen_small | unknown | tileLength_too_small | tiling | skipped | active case missing problem_family/problem_id |
| inject_tilenum | tilenum | unknown | tileNum_unreasonable | None | skipped | quality_status=weak |
