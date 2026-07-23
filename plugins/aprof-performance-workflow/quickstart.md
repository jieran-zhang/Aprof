# AProf Performance Workflow Quickstart

## 安装

从仓库根目录执行：

```bash
bash plugins/aprof-performance-workflow/init.sh
```

如果提示缺少 `ascendc-*`、`ops-profiling`、`ops-simulator` 或 `npu-arch`：

```bash
git submodule update --init third_party/cannbot-skills
```

## 使用方式

在 Cursor 中调用诊断：

```text
@aprof-performance-workflow
请分析这个 Ascend C kernel 的潜在性能问题，并给出需要采集的硬件 metric。
kernel_path: <path/to/kernel.asc>
op_dir: <path/to/direct-invoke-op>
```

若只想生成计划，不执行 msprof：

```text
@aprof-performance-workflow
只生成 diagnosis_hypotheses.json 和 profiling_plan.json，不执行 msprof。
```

若允许采集，给出执行所需命令：

```text
run_cmd: ./<binary> <args>
gen_data_cmd: python3 scripts/gen_data.py ...
profiling_output_dir: profiling_out
warm_up: 10
repeat: 5
```

## 产物

典型产物包括：

- `diagnosis_hypotheses.json`：源码阶段的问题假设和最多 3 个 metric。
- `profiling_plan.json`：msprof 命令、warmup/repeat 执行计划和 report 解析方案。
- `profiling_results.json`：采集产物、缺失项、metric 样本、统计值和稳定性状态。
- `profiling_out/`：`msprof` 生成的 CSV、trace 或 summary。
- `final_diagnosis.md`：带硬件数据支撑的最终诊断。
- `aprof_opt/optimization_plan.json`：多算子族优化策略候选。
- `aprof_opt/candidates/`：隔离复制的候选工程。
- `aprof_opt/optimization_memory.jsonl`：历史成功/失败策略记忆。
- `aprof_opt/final_optimization_report.md`：最终优化报告。
- `aprof_opt/best_op/`：production-safe、语义保持、测量稳定且性能改善的最佳候选。

## 优化入口

优化只接受完整 `op_dir`，不会直接覆盖 baseline；候选会写到 `aprof_opt/candidates/`：

```text
@aprof-performance-workflow
请在已有诊断和 profiling 基础上优化这个 Ascend C 算子。
op_dir: benchmarks/reference_ops/fast_gelu
diagnosis: <path/to/diagnosis_hypotheses.json>
profiling_results: <path/to/profiling_results.json>
```

本地 dry-run 只生成优化计划：

```text
@aprof-performance-workflow
只生成 optimization_plan.json，不修改 baseline，不运行 build/profile。
op_dir: benchmarks/reference_ops/fast_gelu
diagnosis: path/to/diagnosis_hypotheses.json
profiling_results: path/to/profiling_results.json
```

如果要准备候选目录或让 agent 修改候选工程，需要明确授权 candidate 生成和本地 gate。

## 边界

- 源码诊断阶段只产生假设，不直接确认瓶颈。
- 最终诊断必须先构造 workload model；小 workload 的低 UB/AI Core 利用率默认是 `workload_limited`。
- `sim` 只提供 trace / 指令 / 热点 proxy，不产出 msopprof 8 CSV。
- 真实硬件 metric 优先通过 `hw-op` 或 `hw-msprof` 获取；final evidence 需要 warmup/repeat 和稳定性统计。
- 优化候选不得直接覆盖 baseline `op_dir`。
- 优化入口按诊断六问题族优先路由；profiling bound 次之，源码扫描兜底。
- 本地优化执行前需要环境预检，patch 后 build 前需要静态检视。
- 硬编码 shape/core/UB/tile、删除动态 tiling、降精度或缩小边界支持的候选标为 benchmark-only，不得默认成为 final output。
- gate 失败会写入 `failure_handoff`，用于转给 precision/runtime/crash/debug skill。
- simulator-only 性能数据必须标为 proxy。
