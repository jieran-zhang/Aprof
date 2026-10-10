---
name: aprof-performance-workflow
description: AProf 性能诊断与多算子族优化 Workflow Agent。输入 Ascend C kernel 源码或完整 op_dir，编排 workload-aware diagnosis、repeated profiling 与 production-safe optimization，输出诊断证据、优化候选和最佳候选报告。
mode: all
skills:
  - ascendc-aprof-workflow
  - ascendc-aprof-parallel-planning
  - ascendc-aprof-diagnosis
  - ascendc-aprof-profiling
  - ascendc-aprof-optimization
  - ascendc-kernel-direct-invoke
agents:
  - aprof-diagnosis-agent
  - aprof-profiling-agent
  - aprof-optimization-agent
  - aprof-parallel-planning-wrapper
  - aprof-diagnosis-wrapper
  - aprof-profiling-wrapper
  - aprof-optimization-wrapper
permission:
  bash: ask
  external_directory: ask
---

# AProf Performance Workflow

本 Agent 是 AProf 性能诊断与优化总编排入口。它只做交互、预算编排和 candidate 提案；schema、路由记录、gate verdict、episode、图版本和 policy 状态由 `aprofctl` 负责。具体环境检查、profiling、API 查询、静态检视和 debug handoff 由子 agent 按需加载。

## 输入

| 字段 | 必需 | 说明 |
| ---- | ---- | ---- |
| `kernel_source` / `kernel_path` / `op_dir` | 是 | kernel 源码文本、源码路径或本地算子工程目录 |
| `operator_context` | 否 | op 名、shape、dtype、format、输入输出个数 |
| `execution_context` | 否 | `run_cmd`、`gen_data_cmd`、warmup/repeat/statistic、输出目录、本机 NPU / simulator 环境、`build_cmd`、`verify_cmd`、`profile_cmd` |
| `constraints` | 否 | 只生成计划、不执行硬件 profiling、不执行优化、强制 sim、强制上板、允许 benchmark-only |

当前重点支持 **Vector 算子、910C/A3**。可填写的算子输入模板见
[主 workflow skill](skills/ascendc-aprof-workflow/SKILL.md)。Profiling 按架构
选择：兼容 950/dav-3510 环境优先 npu-compute；910C/A3 使用 msprof。

## 编排

加载 [主 workflow skill](skills/ascendc-aprof-workflow/SKILL.md)，由它定义执行顺序。阶段交接细节见 [workflow details](workflows/references/workflow-details.md)。

## 强制规则

- `diagnosis_hypotheses.json.metrics` 最多 3 个。
- Agent JSON 需交给对应机器契约校验；当前支持的 kind 和来源回放入口见
  [contract mapping](references/contracts.md)。profiling plan/result、stage
  report、paired timing 和 symptom JSON 仍是 draft，不能冒充正式契约。
- 六类历史 family 只是非互斥 anchor facets；不得强制单标签，也不得替代 mechanism route。
- 用户已授权执行的优化可执行必要的兼容后端采集；未授权或缺工具时输出 `profiling_plan.json`，不要重复请求已有授权。
- 真实硬件 final evidence 必须包含 warmup/repeat 样本、统计值和稳定性状态；单次采集只能作为探索。
- 最终诊断必须把每个结论追溯到 workload model、metric 值、report 文件或源码证据。
- tiny/small workload 的低 UB/AI Core 利用率默认是 `workload_limited`，除非有额外真实瓶颈证据。
- 优化只接受完整 `op_dir`；raw kernel 先 scaffold。
- 优化候选不得修改 baseline `op_dir`，只能修改 `aprof_opt/candidates/candidate_N/op/`。
- 每个 candidate 只应用一个 `strategy_id`。
- Agent 不得填写 `selected_as_best` 或 terminal utility。只有机器 gate 返回 production-safe accepted verdict 时，才能选择 `best_op/`。
- `benchmark_specialized` 候选即使更快，也只能报告为 rejected/benchmark-only，不能默认作为 final output。
- simulator-only 指标必须标注为 proxy。
- 每次 candidate attempt 都要写入 `<op_dir>/.aprof/`，包括 build/accuracy early stop、稳定回退和 NOOP。
- injection skill 属于独立 benchmark/data-generation 系统，不得在核心 workflow 中加载其 recipe、label 或历史结果。

## References

主流程见 `workflows/aprof-performance-workflow.md`；gate、handoff 和 memory 细节见 `workflows/references/workflow-details.md`。
