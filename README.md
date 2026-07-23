# AProf

AProf 是面向 Ascend C 算子的 agent-native 性能诊断与优化插件集合。当前仓库不再维护 Python `src/` 包和
`tests/unit/` 单测入口，主入口是 `plugins/aprof-performance-workflow` 以及 `skills/aprof/` 下的本地 skills。

最新 workflow 做三件事：

- **Diagnosis**：从 kernel 源码或完整 `op_dir` 生成 `diagnosis_hypotheses.json`，按六类问题族定位源码假设和最多 3 个关键 metric。
- **Profiling**：生成 warmup/repeat 的 `profiling_plan.json`，在用户授权后采集或解析 msprof/cannsim 产物，并输出 `profiling_results.json`。
- **Optimization**：在完整 `op_dir` 上生成多算子族 optimization candidates，只修改隔离的 candidate 工程，默认只接受 production-safe 结果。

## Repository Layout

```text
plugins/aprof-performance-workflow/  # AProf 总编排 plugin 和 wrapper agents
skills/aprof/                        # AProf 本地 diagnosis / profiling / optimization / benchmark skills
third_party/cannbot-skills/          # CANNBot 官方 skills（git submodule）
benchmarks/                          # reference / injected / aprof benchmark 工程
docs/                                # 设计记录和 benchmark 文档
scripts/                             # 环境、远端部署和辅助脚本
```

`src/` 和 `tests/unit/` 已从当前仓库形态中移除；不要再通过 `pip install -e .`、`aprof ...` CLI 或 unit test 作为默认使用方式。

## Install Plugin

先拉取 CANNBot submodule：

```bash
git submodule update --init --recursive third_party/cannbot-skills
```

从仓库根目录安装 AProf workflow plugin 到当前项目的 `.cursor/` 配置：

```bash
bash plugins/aprof-performance-workflow/init.sh
```

安装脚本会链接：

- AProf 本地 skills：diagnosis、profiling、optimization、direct-invoke scaffold。
- AProf agents：workflow、diagnosis/profiling/optimization wrappers。
- 必要 CANNBot skills：`ops-profiling`、`ops-simulator`、`npu-arch`、env/debug/API/code-review 等。

注意：部分大型 CANNBot optimization/design/API skills 只是被安装为可用知识源，不会被 diagnosis 或 optimization agent 默认加载。运行时仍按 AProf 本地 reference 优先，只有 API、平台或算子机制不确定时才点读单个精确文档。

## Use In Cursor

安装后，在 Cursor 中调用：

```text
@aprof-performance-workflow
请分析这个 Ascend C kernel 的潜在性能问题，并给出需要采集的硬件 metric。
kernel_path: <path/to/kernel.asc>
op_dir: <path/to/direct-invoke-op>
```

如果只有 raw kernel，workflow 会先交给 `ascendc-kernel-direct-invoke` 搭建 direct-invoke 工程。若已经有完整 `op_dir`，会直接进入诊断。

只生成计划、不执行 msprof：

```text
@aprof-performance-workflow
只生成 diagnosis_hypotheses.json 和 profiling_plan.json，不执行 msprof。
op_dir: <path/to/direct-invoke-op>
```

允许 profiling 时，给出执行上下文：

```text
@aprof-performance-workflow
请完成诊断并采集缺失 metric。
op_dir: <path/to/direct-invoke-op>
run_cmd: ./<binary> <args>
gen_data_cmd: python3 scripts/gen_data.py
profiling_output_dir: profiling_out
warm_up: 10
repeat: 5
```

请求优化时，需要完整 `op_dir` 和已有诊断/profiling 证据：

```text
@aprof-performance-workflow
请基于已有诊断和 profiling 结果优化这个 Ascend C 算子。
op_dir: <path/to/direct-invoke-op>
diagnosis: <path/to/diagnosis_hypotheses.json>
profiling_results: <path/to/profiling_results.json>
constraints: production_safe
```

## Workflow Outputs

常见输出包括：

- `diagnosis_hypotheses.json`：源码阶段问题假设、六类 problem family 和最多 3 个 metric。
- `profiling_plan.json`：msprof/cannsim 采集命令、warmup/repeat、artifact 需求和解析计划。
- `profiling_results.json`：采集产物、metric 样本、统计值、缺失项和 measurement status。
- `final_diagnosis.md`：能追溯到 workload model、metric/report 或源码证据的最终诊断。
- `aprof_opt/optimization_plan.json`：候选优化策略列表、证据链接、容量模型、abort conditions 和 gate。
- `aprof_opt/candidates/candidate_N/`：隔离复制的候选工程；baseline `op_dir` 不应被修改。
- `aprof_opt/optimization_memory.jsonl`：成功/失败策略记忆。
- `aprof_opt/final_optimization_report.md`：最终优化报告。
- `aprof_opt/best_op/`：只有 production-safe、语义保持、测量稳定且性能改善时才会产生。

## Problem Families

Diagnosis 和 optimization 保持同一组六类入口：

| Problem family | 用途 |
| --- | --- |
| `tiling` | task/tile/tail/MatMul-FA-Sort-Reduction 分块问题 |
| `data_movement` | GM/UB/L2 流量、小块 MTE、DataCopyPad、冗余往返 |
| `pipeline_parallel` | DB、pingpong、preload、SetFlag/WaitFlag、stage overlap |
| `onchip_memory` | UB/L1/L0 resident、buffer lifetime、bank conflict、workspace slot |
| `ai_core_utilization` | blockDim、任务数、tail imbalance、StreamK、split-KV、Group Reduce |
| `api_algorithm` | Scalar/Vector/API 反模式、Cast/repeat、online softmax、MrgSort/Reduce API |

Optimization 默认读取 AProf 本地小型 reference。复杂算子只额外加载一个 operator playbook：

- MatMul / GMM：`skills/aprof/optimization/references/matmul-optimization-playbook.md`
- Softmax / FA：`skills/aprof/optimization/references/softmax-fa-optimization-playbook.md`
- Reduction / Sort / TopK：`skills/aprof/optimization/references/reduction-sort-optimization-playbook.md`
- Vector / Scalar / Broadcast / Conversion：`skills/aprof/optimization/references/vector-scalar-pipeline-playbook.md`

## Safety Rules

- 未经用户确认，不执行 msprof 或远端命令；可以先生成计划。
- 源码诊断只产生假设，最终结论必须经过 workload model 和 profiling/report 证据校验。
- 真实硬件 final evidence 默认需要 warmup/repeat 和稳定性统计；单次或 simulator-only 只能作为 proxy/exploratory。
- 优化候选不得覆盖 baseline `op_dir`，只能修改 `aprof_opt/candidates/candidate_N/op/`。
- 每个 candidate 只应用一个 strategy，但该 strategy 可以包含必要的多行结构性改动。
- 硬编码 shape/core/UB/tile、删除动态 tiling、降精度或缩小边界支持的 candidate 必须标为 benchmark-specialized，不能默认成为 `best_op`。

## Useful Files

- Plugin quickstart: [plugins/aprof-performance-workflow/quickstart.md](plugins/aprof-performance-workflow/quickstart.md)
- Workflow agent: [plugins/aprof-performance-workflow/AGENTS.md](plugins/aprof-performance-workflow/AGENTS.md)
- Workflow details: [plugins/aprof-performance-workflow/workflows/references/workflow-details.md](plugins/aprof-performance-workflow/workflows/references/workflow-details.md)
- Contracts: [skills/aprof/references/contracts.md](skills/aprof/references/contracts.md)
- Diagnosis skill: [skills/aprof/diagnosis/SKILL.md](skills/aprof/diagnosis/SKILL.md)
- Profiling skill: [skills/aprof/profiling/SKILL.md](skills/aprof/profiling/SKILL.md)
- Optimization skill: [skills/aprof/optimization/SKILL.md](skills/aprof/optimization/SKILL.md)
