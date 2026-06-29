# 动态 shape 固定 Tiling 注入

## 问题描述

动态 shape 下仍使用固定 Tiling 策略，导致不同 shape 的性能波动明显。

## Variant

- 目录：`benchmarks/aprof_injected_ops/<op>/inject_dynshape/`
- Ground-truth label：`fixed_tiling_dynamic_shape`

## 注入配方

1. 使用小于固定大 tile 的实际输出 shape
2. 在 `op_kernel/aprof_variant_config.h` 启用 `APROF_INJECT_DYNSHAPE=1`
3. 保持静态 tile 策略不随 shape 更新

## 相关文件

| 文件 | 修改点 |
| --- | --- |
| `scripts/gen_data.py` | 小 shape、`tile_length`、`output_elements`、`injected_label` |
| `op_kernel/aprof_variant_config.h` | `APROF_INJECT_DYNSHAPE=1` |
| `metadata.json` | `output_elements`、`tile_length`、`injected_label` |

## 预期 msprof 特征

- 不同 shape bucket 下性能波动大
- `tile_length` 明显大于 `output_elements`
- 固定开销在小 shape 上占主导

## 验证

1. `bash run.sh build`
2. `bash run.sh gen`
3. 可选 `bash run.sh sim`
4. AProf 诊断预测 `fixed_tiling_dynamic_shape`

## 回滚

- `APROF_INJECT_DYNSHAPE=0`
- 恢复与 shape 匹配的 tile 策略
