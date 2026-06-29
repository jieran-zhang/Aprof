# AProf 向量算子性能问题注入索引

本文汇总 AProf injected benchmark 支持的问题族、variant 命名、ground-truth label 与诊断标签映射。

## 适用范围

- 算子族：Mish、FastGeLU、SwiGlu 等 direct-invoke Vector kernel
- 基线路径：`benchmarks/aprof_injected_ops/<op>/baseline/`
- 注入路径：`benchmarks/aprof_injected_ops/<op>/inject_<variant>/`
- 清单文件：`benchmarks/aprof_injected_ops/manifest.json`

## 问题索引

| 问题 | variant | injected_label | reference |
| --- | --- | --- | --- |
| blockDim 设置过大或过小，导致部分 core 空转或单 core 压力过高 | `inject_blockdim` | `blockdim_too_small` | [blockdim-inject.md](blockdim-inject.md) |
| tail 处理低效，例如尾块单独走低效分支或重复搬运 | `inject_tail` | `tail_inefficient` | [tail-inject.md](tail-inject.md) |
| tileLength 过小，导致循环和同步开销占比变高 | `inject_tilelen_small` | `tileLength_too_small` | [tilelen-small-inject.md](tilelen-small-inject.md) |
| tileLength 过大，导致 UB 压力变高、流水粒度过粗 | `inject_tilelen_large` | `tileLength_too_large` | [tilelen-large-inject.md](tilelen-large-inject.md) |
| tileNum 不合理，导致 tile 调度次数异常或尾块过多 | `inject_tilenum` | `tileNum_unreasonable` | [tilenum-inject.md](tilenum-inject.md) |
| 动态 shape 下仍使用固定 Tiling 策略，导致不同 shape 性能波动明显 | `inject_dynshape` | `fixed_tiling_dynamic_shape` | [dynshape-inject.md](dynshape-inject.md) |

## 统一注入原则

1. **单因子注入**：每个 variant 只表达一个主要性能问题。
2. **保持可编译**：注入后必须能通过 `bash run.sh build`。
3. **保持可标注**：`metadata.json` 写入 `injected_label` 及关键 tiling 字段。
4. **保持可诊断**：优先保留 `trace.json`、`*_instr_exe_*.csv`、`*_code_exe_*.csv` 证据路径。
5. **保持可回滚**：baseline 旋钮为 `DEFAULT_BLOCKDIM=1`、`DEFAULT_TILE_LENGTH=256`、`DEFAULT_TILE_NUM_MUL=1`、`APROF_INJECT_TAIL=0`、`APROF_INJECT_DYNSHAPE=0`，且输出 shape 可被 tile length 整除。

## 验证闭环

```bash
# 单 case 验证
cd benchmarks/aprof_injected_ops/swi_glu/inject_tail
bash run.sh build
bash run.sh gen
bash run.sh sim    # 可选

# SwiGlu 1x3 label alignment
python scripts/run_closed_loop.py
```

期望 Diagnosis agent 预测标签与 `injected_label` 一致。当前闭环覆盖：

- `swi_glu/inject_blockdim` → `blockdim_too_small`
- `swi_glu/inject_tilelen_small` → `tileLength_too_small`
- `swi_glu/inject_tail` → `tail_inefficient`

## 与 Diagnosis Skill 的关系

注入 Skill 负责**构造 ground-truth case**；Diagnosis Skill 负责**从 msprof 证据映射到问题标签**。对应关系：

| injected_label | Diagnosis 问题族 |
| --- | --- |
| `blockdim_too_small` | 多核切分 / `blockDim` 不合理 |
| `tail_inefficient` | Tiling / tail 处理低效 |
| `tileLength_too_small` | UB 切分 / tileLength 过小 |
| `tileLength_too_large` | UB 切分 / tileLength 过大 |
| `tileNum_unreasonable` | Tiling / tileNum 不合理 |
| `fixed_tiling_dynamic_shape` | 动态 shape 固定 Tiling |

详细 metric 映射见 `skills/aprof/diagnosis/references/tiling-diagnosis-metrics.md`。
