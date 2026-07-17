# conv2d Label Alignment

## Summary

- Total: 8
- Passed: 0
- Failed: 3
- Pending: 1
- Skipped: 4

## Cases

| Variant | Family | Problem ID | Ground Truth | Predicted | Status | Reason |
| ------- | ------ | ---------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | baseline | baseline | None | pending | no diagnosis prediction provided |
| inject_blockdim | tiling | blockdim_too_small | blockdim_too_small | tiling | fail | predicted_label=tiling |
| inject_excessive_barrier | pipeline_parallel | excessive_pipe_barrier | excessive_pipe_barrier | None | skipped | quality_status=unverified |
| inject_redundant_copyin | data_movement | redundant_copyin | redundant_copyin | data_movement | fail | predicted_label=data_movement |
| inject_redundant_vector | api_algorithm | redundant_cast_or_vector_copy | redundant_cast_or_vector_copy | None | skipped | quality_status=unverified |
| inject_tilelen_small | tiling | tile_length_too_small | tileLength_too_small | tiling | fail | predicted_label=tiling |
| inject_ub_temp_overalloc | onchip_memory | ub_temp_overallocated | ub_temp_overallocated | None | skipped | quality_status=unverified |
| inject_underused_blockdim | ai_core_utilization | underused_blockdim | underused_blockdim | None | skipped | quality_status=unverified |
