# tileLength 过小注入

## 问题描述

tileLength 过小，导致循环和同步开销占比变高。

## Variant

- 目录：`benchmarks/aprof_injected_ops/<op>/inject_tilelen_small/`
- Ground-truth label：`tileLength_too_small`

## 注入配方

在 `scripts/gen_data.py` 中将 `DEFAULT_TILE_LENGTH` 调为很小的对齐值（如 16），保持输出 size 和算子数学不变。

推荐同时保留：

- `DEFAULT_TILE_NUM_MUL=1` 或使 `tile_num >= 4`，以便规则诊断稳定触发

## 相关文件

| 文件 | 修改点 |
| --- | --- |
| `scripts/gen_data.py` | `DEFAULT_TILE_LENGTH`、`tile_num`、`injected_label` |
| `metadata.json` | `tile_length`、`tile_num`、`injected_label` |

## 预期 msprof 特征

- 短 tile 数量多
- 指令数升高
- `SET_FLAG` / `WAIT` / `PipeBarrier` 类开销占比升高
- 循环控制开销压过有效 VEC 时间

## 验证

1. `bash run.sh build`
2. `bash run.sh gen`
3. 单核 sim 时可传 `--tile-length 16`
4. AProf 诊断预测 `tileLength_too_small`

## 回滚

恢复 `DEFAULT_TILE_LENGTH=256`。
