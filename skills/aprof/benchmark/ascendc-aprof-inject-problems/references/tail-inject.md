# Tail 处理低效注入

## 问题描述

tail 处理低效，例如尾块单独走低效分支或重复搬运。

## Variant

- 目录：`benchmarks/aprof_injected_ops/<op>/inject_tail/`
- Ground-truth label：`tail_inefficient`

## 注入配方

1. 使用不能被 tile length 整除的输出 size
2. 在 `op_kernel/aprof_variant_config.h` 启用 `APROF_INJECT_TAIL=1`
3. 让 tail tile 在 compute 前额外执行一次 GM reload

其余旋钮保持 baseline 不变。

## 相关文件

| 文件 | 修改点 |
| --- | --- |
| `scripts/gen_data.py` | 输出 shape、`tail_length`、`injected_label` |
| `op_kernel/aprof_variant_config.h` | `APROF_INJECT_TAIL=1` |
| `op_kernel/<op>_kernel.asc` | tail 分支逻辑 |
| `metadata.json` | `tail_length`、`injected_label` |

## 预期 msprof 特征

- tail tile 出现额外 MTE 活动
- tail tile 耗时明显高于主循环 tile
- `metadata.tail_length` 非零

## 验证

1. `bash run.sh build`
2. `bash run.sh gen`
3. 可选 `bash run.sh sim`
4. AProf 诊断预测 `tail_inefficient`

## 回滚

- `APROF_INJECT_TAIL=0`
- 输出 shape 恢复为 tile length 的整数倍
