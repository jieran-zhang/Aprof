---
name: ascendc-aprof-inject-problems
description: Ascend C 向量算子 benchmark 注入 Skill。用于在 direct-invoke Ascend C 工程中注入受控的性能反模式，构建 AProf 可诊断的 injected benchmark case；适用于从 baseline 派生 inject_* 变体、生成 ground-truth label、跑通 build/gen/sim 并验证诊断对齐时。
---

# AscendC AProf Benchmark 性能问题注入

## 使用场景

当需要为 AProf benchmark 库构造“已知根因”的算子变体时使用本 Skill：

- 已有 `benchmarks/aprof_injected_ops/<op>/baseline/` 或可复用的 direct-invoke 基线工程。
- 需要注入单一、可控的性能反模式，同时保持算子数学正确性和可编译性。
- 需要为 Diagnosis agent 提供 `metadata.json` ground-truth label 和可复现的 msprof 证据。
- 需要把 weekly report / 设计文档中的性能问题沉淀为可执行注入配方。

## 注入流程

1. 确认 baseline 已存在且 `bash run.sh build` / `bash run.sh gen` 可通过。
2. 选择要注入的问题族，读取本 Skill 对应 reference 文档。
3. 从 baseline 复制到 `benchmarks/aprof_injected_ops/<op>/inject_<variant>/`。
4. 仅修改 reference 中列出的旋钮，不改算子数学逻辑。
5. 运行 `bash run.sh build`；需要刷新数据时运行 `bash run.sh gen`。
6. 可选：运行 `bash run.sh sim` 采集单核 msprof simulator 产物。
7. 用 `/ascendc-aprof-diagnosis` 或 `python scripts/run_closed_loop.py` 验证 label 对齐。

## 目标工程布局

每个 injected case 推荐保持统一结构：

```text
benchmarks/aprof_injected_ops/<op>/<variant>/
  run.sh
  scripts/gen_data.py
  op_kernel/aprof_variant_config.h
  op_kernel/<op>_kernel.asc
  metadata.json
  build_sim/
  msprof_sim_output/        # 可选，sim 后生成
```

常用旋钮文件：

| 文件 | 作用 |
| --- | --- |
| `scripts/gen_data.py` | `DEFAULT_BLOCKDIM`、`DEFAULT_TILE_LENGTH`、`DEFAULT_TILE_NUM_MUL`、输出 shape、injected label |
| `op_kernel/aprof_variant_config.h` | `APROF_INJECT_TAIL`、`APROF_INJECT_DYNSHAPE` 等编译期开关 |
| `op_kernel/<op>_kernel.asc` | tail / loop / tiling 行为 |
| `metadata.json` | AProf ground-truth：`injected_label`、`blockdim`、`tile_length`、`tile_num`、`tail_length` |

## 当前内置注入问题

- BlockDim 不合理：[references/blockdim-inject.md](references/blockdim-inject.md)
- Tail 处理低效：[references/tail-inject.md](references/tail-inject.md)
- tileLength 过小：[references/tilelen-small-inject.md](references/tilelen-small-inject.md)
- tileLength 过大：[references/tilelen-large-inject.md](references/tilelen-large-inject.md)
- tileNum 不合理：[references/tilenum-inject.md](references/tilenum-inject.md)
- 动态 shape 固定 Tiling：[references/dynshape-inject.md](references/dynshape-inject.md)

## 问题索引与诊断标签

完整索引、variant 命名和 AProf label 映射见：

- [references/inject-problems-meta.md](references/inject-problems-meta.md)

## 关联 Skill

- Simulator 采集：`skills/aprof/benchmark/ascendc-msprof-simulator`
- 性能诊断：`skills/aprof/diagnosis`（`/ascendc-aprof-diagnosis`）
- Profiling 规划：`skills/aprof/profiling`（`/ascendc-aprof-profiling`）

## 约束

- 一次只注入一个问题族；其余旋钮保持与 baseline 一致。
- 不修改算子数学正确性，只改 tiling / 调度 / 分支路径。
- `metadata.json.injected_label` 必须与 reference 中 ground-truth label 一致。
- 优先单核 simulator 采集；仅在需要跨核失衡对比时提高 `blockdim`。
- 注入来源可追溯：本 Skill 源自 `project_log/2026-06-11-weekly-report.md` 第 63-68 行向量算子性能问题清单。
