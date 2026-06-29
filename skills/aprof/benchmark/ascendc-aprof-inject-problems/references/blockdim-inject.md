# BlockDim 不合理注入

## 问题描述

blockDim 设置过大或过小，导致部分 core 空转或单 core 压力过高。

## Variant

- 目录：`benchmarks/aprof_injected_ops/<op>/inject_blockdim/`
- Ground-truth label：`blockdim_too_small`

## 注入配方

在 `scripts/gen_data.py` 中设置：

- `DEFAULT_BLOCKDIM=1`：用于单核过载侧实验
- 或设置为明显大于有效任务数的值：用于空核/失衡实验

其余旋钮保持 baseline 不变：

- `DEFAULT_TILE_LENGTH=256`
- `DEFAULT_TILE_NUM_MUL=1`
- `APROF_INJECT_TAIL=0`
- `APROF_INJECT_DYNSHAPE=0`

## 相关文件

| 文件 | 修改点 |
| --- | --- |
| `scripts/gen_data.py` | `DEFAULT_BLOCKDIM`、输出 shape、`injected_label` |
| `metadata.json` | `blockdim`、`injected_label` |
| `op_kernel/<op>_kernel.asc` | 通常无需改数学，仅随 tiling 参数变化 |

## 预期 msprof 特征

- 单活跃 core 耗时显著高于其他 core
- 活跃 core 数与预期不一致
- per-core 耗时 CV / max-avg 失衡明显

主要证据：`trace.json`、`*_instr_exe_*.csv`、`*_code_exe_*.csv`、`metadata.json`。

## 验证

1. `bash run.sh build` 生成 `build_sim/<op>_kernel.o`
2. `bash run.sh gen` 生成 `build_sim/op_config.json`、输入/tiling bin 和 metadata
3. 可选 `bash run.sh sim` 采集 simulator 产物
4. AProf 诊断预测 `blockdim_too_small`

## 回滚

恢复 baseline 旋钮，或直接使用 `benchmarks/aprof_injected_ops/<op>/baseline/`。
