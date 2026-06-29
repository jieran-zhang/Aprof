# tileNum 不合理注入

## 问题描述

tileNum 不合理，导致 tile 调度次数异常或尾块过多。

## Variant

- 目录：`benchmarks/aprof_injected_ops/<op>/inject_tilenum/`
- Ground-truth label：`tileNum_unreasonable`

## 注入配方

保持 `DEFAULT_TILE_LENGTH` 适中，通过 `DEFAULT_TILE_NUM_MUL` 放大生成的 `tileNum`，使 kernel 进入额外调度轮次。

## 相关文件

| 文件 | 修改点 |
| --- | --- |
| `scripts/gen_data.py` | `DEFAULT_TILE_NUM_MUL`、`tile_num`、`injected_label` |
| `metadata.json` | `tile_num`、`injected_label` |

## 预期 msprof 特征

- `tile_num` 明显大于 `ceil(elemsPerCore / tileLength)`
- 重复调度或空循环开销升高

## 验证

1. `bash run.sh build`
2. `bash run.sh gen`
3. 可选 `bash run.sh sim`
4. AProf 诊断预测 `tileNum_unreasonable`

## 回滚

恢复 `DEFAULT_TILE_NUM_MUL=1`。
