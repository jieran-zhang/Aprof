# AProf Injection Problem Index

This file maps injection recipes to diagnosis families, labels, variants, and reference files.

## Families

| problem_family | Reference | Diagnosis family |
| --- | --- | --- |
| `tiling` | `tiling-inject.md` | `tiling` |
| `data_movement` | `data-movement-inject.md` | `data_movement` |
| `pipeline_parallel` | `pipeline-parallel-inject.md` | `pipeline_parallel` |
| `onchip_memory` | `onchip-memory-inject.md` | `onchip_memory` |
| `ai_core_utilization` | `ai-core-utilization-inject.md` | `ai_core_utilization` |
| `api_algorithm` | `api-algorithm-inject.md` | `api_algorithm` |

## Recipe Index

| problem_family | problem_id | variant | injected_label |
| --- | --- | --- | --- |
| `tiling` | `blockdim_too_small` | `inject_blockdim` | `blockdim_too_small` |
| `tiling` | `tail_inefficient` | `inject_tail` | `tail_inefficient` |
| `tiling` | `tile_length_too_small` | `inject_tilelen_small` | `tileLength_too_small` |
| `tiling` | `tile_length_too_large` | `inject_tilelen_large` | `tileLength_too_large` |
| `tiling` | `tile_num_unreasonable` | `inject_tilenum` | `tileNum_unreasonable` |
| `tiling` | `fixed_tiling_dynamic_shape` | `inject_dynshape` | `fixed_tiling_dynamic_shape` |
| `data_movement` | `redundant_copyin` | `inject_redundant_copyin` | `redundant_copyin` |
| `data_movement` | `extra_copyout` | `inject_extra_copyout` | `extra_copyout` |
| `data_movement` | `small_datacopy_granularity` | `inject_small_datacopy` | `small_datacopy_granularity` |
| `pipeline_parallel` | `serial_copy_compute_copyout` | `inject_serial_pipeline` | `serial_copy_compute_copyout` |
| `pipeline_parallel` | `double_buffer_disabled` | `inject_double_buffer_disabled` | `double_buffer_disabled` |
| `pipeline_parallel` | `excessive_pipe_barrier` | `inject_excessive_barrier` | `excessive_pipe_barrier` |
| `onchip_memory` | `ub_temp_overallocated` | `inject_ub_temp_overalloc` | `ub_temp_overallocated` |
| `onchip_memory` | `gm_spill_intermediate` | `inject_gm_spill` | `gm_spill_intermediate` |
| `onchip_memory` | `low_ub_reuse` | `inject_low_ub_reuse` | `low_ub_reuse` |
| `ai_core_utilization` | `underused_blockdim` | `inject_underused_blockdim` | `underused_blockdim` |
| `ai_core_utilization` | `overlaunched_empty_cores` | `inject_overlaunched_cores` | `overlaunched_empty_cores` |
| `ai_core_utilization` | `tail_core_imbalance` | `inject_tail_core_imbalance` | `tail_core_imbalance` |
| `api_algorithm` | `scalar_loop_redundant` | `inject_scalar_loop` | `scalar_loop_redundant` |
| `api_algorithm` | `small_vector_api_chunks` | `inject_small_vector_chunks` | `small_vector_api_chunks` |
| `api_algorithm` | `redundant_cast_or_vector_copy` | `inject_redundant_vector` | `redundant_cast_or_vector_copy` |

## Legacy Aliases

Old `problem_family` values remain accepted by `tools/inject_case.py` when `--problem-id` is omitted:

| Legacy value | Maps to |
| --- | --- |
| `blockdim` | `tiling/blockdim_too_small` |
| `tail` | `tiling/tail_inefficient` |
| `tilelen_small` | `tiling/tile_length_too_small` |
| `tilelen_large` | `tiling/tile_length_too_large` |
| `tilenum` | `tiling/tile_num_unreasonable` |
| `dynshape` | `tiling/fixed_tiling_dynamic_shape` |

## Quality Semantics

- `active`: build/run/profile validation passed and the case may count toward diagnosis accuracy.
- `unverified`: generated successfully but evidence is not complete yet.
- `unsupported`: recipe did not apply safely to the source.
- `weak` or `deprecated_or_weak`: retained for historical or auxiliary use, excluded from accuracy.
