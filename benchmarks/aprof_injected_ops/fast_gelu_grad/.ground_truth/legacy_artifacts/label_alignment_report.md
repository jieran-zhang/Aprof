# fast_gelu_grad Label Alignment

## Summary

- Total: 4
- Passed: 0
- Failed: 3
- Pending: 1
- Skipped: 0

## Cases

| Variant | Family | Problem ID | Ground Truth | Predicted | Status | Reason |
| ------- | ------ | ---------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | baseline | baseline | None | pending | no diagnosis prediction provided |
| inject_blockdim | tiling | blockdim_too_small | blockdim_too_small | tiling | fail | predicted_label=tiling |
| inject_dynshape | tiling | fixed_tiling_dynamic_shape | fixed_tiling_dynamic_shape | tiling | fail | predicted_label=tiling |
| inject_scalar_loop | api_algorithm | scalar_loop_redundant | scalar_loop_redundant | api_algorithm | fail | predicted_label=api_algorithm |
