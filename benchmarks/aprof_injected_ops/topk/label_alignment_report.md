# topk Label Alignment

## Summary

- Total: 4
- Passed: 0
- Failed: 2
- Pending: 1
- Skipped: 1

## Cases

| Variant | Family | Problem ID | Ground Truth | Predicted | Status | Reason |
| ------- | ------ | ---------- | ------------ | --------- | ------ | ------ |
| baseline | baseline | baseline | baseline | None | pending | no diagnosis prediction provided |
| inject_blockdim | tiling | blockdim_too_small | blockdim_too_small | tiling | fail | predicted_label=tiling |
| inject_excessive_barrier | pipeline_parallel | excessive_pipe_barrier | excessive_pipe_barrier | None | skipped | quality_status=unverified |
| inject_redundant_copyin | data_movement | redundant_copyin | redundant_copyin | data_movement | fail | predicted_label=data_movement |
