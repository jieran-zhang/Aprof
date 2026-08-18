# conv_3d_backprop_filter direct Ascend C benchmark

Correctness-first implementation for the level-3 task. AIV kernels pack the output gradient and gather the grouped 3-D im2col matrix; a custom AIC `AscendC::MatmulImpl` computes `grad^T × im2col`; AIV casts the FP32 filter-gradient accumulator. The host only parses metadata, allocates/copies buffers, produces Cube tiling, and launches kernels. It does not precompute the output and no ACLNN operator is used.

```bash
ASCEND_RT_VISIBLE_DEVICES=2 ./run.sh --case 1 --device 0
ASCEND_RT_VISIBLE_DEVICES=2 ./run.sh --all --device 0
```

The original 20 cases are read directly from `third_party/cann-bench/tasks/level3/conv_3d_backprop_filter/cases.csv`.
