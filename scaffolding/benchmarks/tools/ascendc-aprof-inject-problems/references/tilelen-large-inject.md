# tileLength 过大注入

## 问题描述

tileLength 过大，导致 UB 压力变高、流水粒度过粗。

## Variant

- 目录：`benchmarks/aprof_injected_ops/<op>/inject_tilelen_large/`
- Ground-truth label：`tileLength_too_large`

## 注入配方

在 `scripts/gen_data.py` 中将 `DEFAULT_TILE_LENGTH` 提高到粗粒度值（如 2048 或更大），保持 `blockdim` 和算子数学不变。

## 相关文件

| 文件 | 修改点 |
| --- | --- |
| `scripts/gen_data.py` | `DEFAULT_TILE_LENGTH`、`injected_label` |
| `metadata.json` | `tile_length`、`injected_label` |

## 预期 msprof 特征

- tile 数很少
- CopyIn / Compute / CopyOut 窗口粒度过粗
- 单 tile 耗时大，可能出现 UB 压力迹象

## 验证

1. `bash run.sh build`
2. `bash run.sh gen`
3. 可选 `bash run.sh sim`
4. AProf 诊断预测 `tileLength_too_large`

## 回滚

恢复 `DEFAULT_TILE_LENGTH=256`。
