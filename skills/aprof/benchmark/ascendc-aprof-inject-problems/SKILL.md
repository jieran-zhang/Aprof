---
name: ascendc-aprof-inject-problems
description: Ascend C benchmark 性能问题注入 Skill。用于从单个 kernel 文件、AProf sim-only baseline 或完整 direct-invoke 脚手架工程生成 injected case，注入受控性能反模式，生成 ground-truth label，并通过远程编译、运行/profile 与诊断对齐验证。
---

# AscendC AProf Benchmark 性能问题注入

## 使用场景

当需要为 AProf benchmark 库构造“已知根因”的算子变体时使用本 Skill：

- 已有 `benchmarks/aprof_injected_ops/<op>/baseline/` 或可复用的 direct-invoke 基线工程。
- 需要注入单一、可控的性能反模式，同时保持算子数学正确性和可编译性。
- 需要为 Diagnosis agent 提供 `metadata.json` ground-truth label 和可复现的 msprof 证据。
- 需要把 weekly report / 设计文档中的性能问题沉淀为可执行注入配方。
- 用户提供单个 kernel 文件，需要补齐 sim-only 脚手架并注入 kernel 内性能问题。
- 用户提供完整 direct-invoke 工程，需要在 host 或 kernel 侧注入 blockDim、tiling、workspace、dynamic shape 等问题并远程验证。
- 需要构造 blind diagnosis 输入，只暴露中性源码/tiling/report/硬件信息，不暴露 ground-truth label。

## 输入模式

| 模式 | 输入 | 输出工程 | 适合注入 | 验证 |
| --- | --- | --- | --- | --- |
| `kernel_only` | 单个 `<op>_kernel.asc`，可选 tiling 头和算子上下文 | sim-only AProf 工程 | tail、tileLength、DataCopy、同步等 kernel 内问题 | `msprof op simulator` |
| `existing_aprof_baseline` | `benchmarks/aprof_injected_ops/<op>/baseline/` | sim-only inject variants | 迁移现有 fast_gelu/mish/swi_glu benchmark | `run.sh build/sim` |
| `scaffold_project` | 完整 direct-invoke 工程，含 `op_host/`、`CMakeLists.txt`、`run.sh` | full-scaffold inject variants | blockDim、host tiling、dynamic shape、workspace、真机 profile | CMake build + host run + hw-msprof/hw-op |

## 注入流程

1. 读取 [references/inject-agent-contracts.md](references/inject-agent-contracts.md)，明确 `inject_request.json` 与产物契约。
2. 根据输入判断 `kernel_only`、`existing_aprof_baseline` 或 `scaffold_project`。
3. 选择要注入的问题族，读取本 Skill 对应 reference 文档。
4. 生成 `inject_<variant>/`，仅修改 reference 白名单中的旋钮，不改算子数学逻辑。
5. 写入 `metadata.json`、`inject_manifest.json` 和每 case 的 `profiling_plan.json`。
6. 生成批量 `inject_deploy_manifest.json`，交给 remote deploy 做远程编译、运行/profile 和产物拉取。
7. 写入 `validation_summary.json`，再用 `/ascendc-aprof-diagnosis` 或 label alignment 工具验证 label 对齐。

## Blind Diagnosis 评测流程

注入 case 的 `metadata.json` 是 ground truth，不应直接交给 diagnosis agent。需要单 case 盲测时：

```bash
python skills/aprof/benchmark/ascendc-aprof-inject-problems/tools/build_blind_diagnosis_input.py \
  --case-dir benchmarks/aprof_injected_ops/<op>/<case> \
  --trace benchmarks/aprof_injected_ops/<op>/remote_inject_out/<case>/.../trace.json \
  --hardware-context-json <hardware_context.json> \
  --out benchmarks/aprof_injected_ops/<op>/blind_inputs/<case>.json
```

该工具只保留中性 metadata（shape、tiling、stride、blockDim 等），自动屏蔽 `injected_label`、`injected_problem`、variant 名和注入 manifest。输出必须按 `skills/aprof/references/contracts.md#single_case_diagnosisjson` 由 diagnosis agent 独立诊断，不能使用 baseline。

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

完整 direct-invoke case 还必须保留：

```text
benchmarks/aprof_injected_ops/<op>/<variant>/
  CMakeLists.txt
  op_host/
  op_kernel/
  scripts/gen_data.py
  scripts/verify_result.py       # 可选但推荐
  run.sh
```

常用旋钮文件：

| 文件 | 作用 |
| --- | --- |
| `scripts/gen_data.py` | `DEFAULT_BLOCKDIM`、`DEFAULT_TILE_LENGTH`、`DEFAULT_TILE_NUM_MUL`、输出 shape、injected label |
| `op_kernel/aprof_variant_config.h` | `APROF_INJECT_TAIL`、`APROF_INJECT_DYNSHAPE` 等编译期开关 |
| `op_kernel/<op>_kernel.asc` | tail / loop / tiling 行为 |
| `metadata.json` | AProf ground-truth：`injected_label`、`blockdim`、`tile_length`、`tile_num`、`tail_length` |
| `tools/build_blind_diagnosis_input.py` | 生成单 case blind diagnosis 输入，屏蔽 ground-truth 信息 |

## 当前内置注入问题

- BlockDim 不合理：[references/blockdim-inject.md](references/blockdim-inject.md)
- Tail 处理低效：[references/tail-inject.md](references/tail-inject.md)
- tileLength 过小：[references/tilelen-small-inject.md](references/tilelen-small-inject.md)
- tileLength 过大：[references/tilelen-large-inject.md](references/tilelen-large-inject.md)
- tileNum 不合理：[references/tilenum-inject.md](references/tilenum-inject.md)
- 动态 shape 固定 Tiling：[references/dynshape-inject.md](references/dynshape-inject.md)
- Agent 契约：[references/inject-agent-contracts.md](references/inject-agent-contracts.md)

## 问题索引与诊断标签

完整索引、variant 命名和 AProf label 映射见：

- [references/inject-problems-meta.md](references/inject-problems-meta.md)

## 关联 Skill

- Simulator 采集：`skills/aprof/benchmark/ascendc-msprof-simulator`
- 性能诊断：`skills/aprof/diagnosis`（`/ascendc-aprof-diagnosis`）
- Profiling 规划：`skills/aprof/profiling`（`/ascendc-aprof-profiling`）
- 远程验证：`skills/aprof/remote-kernel-deploy`（`/ascendc-remote-kernel-deploy`）

## 约束

- 一次只注入一个问题族；其余旋钮保持与 baseline 一致。
- 不修改算子数学正确性，只改 tiling / 调度 / 分支路径。
- `metadata.json.injected_label` 必须与 reference 中 ground-truth label 一致。
- 优先单核 simulator 采集；仅在需要跨核失衡对比时提高 `blockdim`。
- host 侧问题必须使用 `scaffold_project`，不要用 sim-only metadata 伪装 host 问题。
- sim-only case 的 accuracy/run pass 默认标注 `skipped`，不能声称已完成 host 运行正确性验证。
- 每个 case 必须生成 `inject_manifest.json`；批量远程验证必须生成 `inject_deploy_manifest.json` 和 `validation_summary.json`。
- 诊断准确率评测必须使用 blind 输入；不得把 `metadata.json.injected_label`、`inject_manifest.json` 或 label alignment 报告交给 diagnosis agent。
- 注入来源可追溯：本 Skill 源自 `project_log/2026-06-11-weekly-report.md` 第 63-68 行向量算子性能问题清单。
