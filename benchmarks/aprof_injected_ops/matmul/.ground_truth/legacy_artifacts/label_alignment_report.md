# matmul Label Alignment

## Summary

- Total: 6
- Passed: 0
- Failed: 4
- Pending: 1
- Skipped: 1

## Cases

| Variant | Family | Problem ID | Ground Truth | Predicted | Status | Reason |
| ------- | ------ | ---------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | baseline | baseline | None | pending | no diagnosis prediction provided |
| inject_blockdim | tiling | blockdim_too_small | blockdim_too_small | tiling | fail | predicted_label=tiling |
| inject_excessive_barrier | pipeline_parallel | excessive_pipe_barrier | excessive_pipe_barrier | pipeline_parallel | fail | predicted_label=pipeline_parallel |
| inject_tilelen_small | tiling | tile_length_too_small | tileLength_too_small | data_movement | fail | predicted_label=data_movement |
| inject_ub_temp_overalloc | onchip_memory | ub_temp_overallocated | ub_temp_overallocated | onchip_memory | fail | predicted_label=onchip_memory |
| inject_underused_blockdim | ai_core_utilization | underused_blockdim | underused_blockdim | None | skipped | quality_status=unverified |
