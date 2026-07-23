# AProf Performance Workflow

目标：输入 Ascend C kernel 源码或完整 `op_dir`，输出 workload-aware 性能诊断、带 warmup/repeat 的 profiling 证据，并在用户要求时生成默认 production-safe 的多算子族优化候选。

本文件只保留总编排。详细 gate、handoff、memory 和六类优化路由见：

- [workflow-details.md](references/workflow-details.md)
- [optimization-strategy-routing.md](../../../skills/aprof/optimization/references/optimization-strategy-routing.md)
- [contracts.md](../../../skills/aprof/references/contracts.md)

## Inputs

| Field | Required | Notes |
| --- | --- | --- |
| `kernel_source` / `kernel_path` / `op_dir` | yes | kernel 文本、源码路径或完整 direct-invoke 工程 |
| `operator_context` | no | op 名、shape、dtype、format、输入输出个数 |
| `execution_context` | no | run/gen/profile/build/verify 命令、本机 NPU 或 simulator 环境、warmup/repeat/statistic |
| `constraints` | no | dry-run、不执行 msprof、不执行优化、强制 sim 或上板、允许 benchmark-only |

## Main Flow

1. **Input normalization**
   - 完整 `op_dir` 直接进入诊断。
   - raw kernel 先交给 `ascendc-kernel-direct-invoke` scaffold。

2. **Source audit**
   - Agent: `aprof-diagnosis-agent`
   - Output: `diagnosis_hypotheses.json`
   - Problem families: `tiling`、`data_movement`、`pipeline_parallel`、`onchip_memory`、`ai_core_utilization`、`api_algorithm`

3. **Workload model**
   - Agent: `aprof-diagnosis-agent`
   - Output: `workload_model` / `attainable_utilization`
   - Low UB or AI Core utilization is interpreted relative to workload and hardware limits.

4. **Profiling plan and repeated execution**
   - Agent: `aprof-profiling-agent`
   - Outputs: `profiling_plan.json`、`profiling_results.json`、CSV/trace/summary artifacts
   - 未经用户授权，不执行 msprof；只生成 plan。
   - Real hardware evidence defaults to `warm_up=10`、`repeat=5`、`statistic=median`。

5. **Final diagnosis**
   - Agent: `aprof-diagnosis-agent`
   - Output: `final_diagnosis.md`
   - 结论必须能追溯到 workload model、metric、report artifact 或源码证据。

6. **Optional optimization**
   - Agent: `aprof-optimization-agent`
   - Only for complete `op_dir`
   - Outputs: `aprof_opt/optimization_plan.json`、candidate dirs、`candidate_result.json`、`optimization_memory.jsonl`、`final_optimization_report.md`

7. **Independent cross-check**
   - Agent: sub-agent reviewer
   - Review diagnosis type, metric evidence stability, and candidate acceptance.
   - Main agent only reports conclusions that pass the evidence chain.

## Optimization Summary

- 路由顺序：diagnosis problem family first -> profiling bound second -> source scan fallback。
- 每个 candidate 只应用一个 `strategy_id`。
- 单个 `strategy_id` 可以包含必要的多行结构性改动，例如 loop 重排、buffer lifetime 调整、Host Tiling 更新或 workspace slot 改写。
- baseline `op_dir` 只读；修改只允许发生在 `aprof_opt/candidates/candidate_N/op/`。
- Gate 顺序：static review -> build -> accuracy -> repeated profile -> measurement stability -> correctness/generality acceptance -> metric compare。
- 只有 accuracy 通过、metric 稳定改善、`semantic_status=preserved` 且 `scope_status=production_safe` 时，才允许生成或声明 `aprof_opt/best_op/`。
- simulator-only 性能数据必须标注为 proxy。
- 更快但 `benchmark_specialized` 的 candidate 必须单独列出，不得作为默认 final output。

## Stop Points

- 只诊断：输出 `diagnosis_hypotheses.json` 和 `profiling_plan.json`。
- profiling 数据不足：输出缺失 artifact 和下一步采集建议。
- 只生成优化计划：输出 `optimization_plan.json`，必要时准备 candidate dirs，但不声称性能已优化。

## Invocation

```text
@aprof-performance-workflow
请基于已有诊断和 profiling 结果优化这个 Ascend C 算子。
op_dir: <op_dir>
diagnosis: <diagnosis.json>
profiling_results: <profiling_results.json>
constraints: production_safe
```

## Final Report Contract

最终回答必须包含：

- `contract with metric evidence`：baseline/candidate 样本、统计值、CV、measurement_status、诊断类型和证据来源。
- `final output`：production-safe best op 路径；若没有可接受候选，明确写 none。
- `performance improvement`：只基于稳定重复采样的 selected statistic；单次或 sim-only 只能标为 proxy/exploratory。
- `rejected faster candidates`：列出性能更好但因 benchmark specialization、语义风险、portability risk 或测量不稳定被拒绝的候选。
