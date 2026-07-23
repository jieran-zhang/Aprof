# AProf Workflow Details

按需读取本文件。入口 agent 不应默认加载所有 cannbot guard skill；应由 diagnosis/profiling/optimization 子 agent 根据阶段加载。

## Stage Responsibilities

| Stage | Owner | Required output | Key checks |
| --- | --- | --- | --- |
| Source audit | `aprof-diagnosis-agent` | `diagnosis_hypotheses.json` | `hypotheses <= 3`、`metrics <= 3`、每个 metric 有来源 |
| Workload model | `aprof-diagnosis-agent` | `workload_model` / `attainable_utilization` | total elements、dtype bytes、min bytes、blockDim、core denominator、workload class |
| Profiling plan | `aprof-profiling-agent` | `profiling_plan.json` | mode 为 `sim` / `hw-msprof` / `hw-op`，每个 metric 有 parser plan 和 warmup/repeat policy |
| Profiling execution | `aprof-profiling-agent` | `profiling_results.json` | artifacts 存在；缺失项写 `missing_required_artifacts[]`；样本统计和 `measurement_status` 存在 |
| Final diagnosis | `aprof-diagnosis-agent` | `final_diagnosis.md` | 结论追溯到 workload model、metric、report artifact 或源码证据 |
| Optimization routing | `aprof-optimization-agent` | `optimization_plan.json` | 保留 problem family、hypothesis/metric linkage、bound、checks、handoff |
| Candidate loop | `aprof-optimization-agent` | `candidate_result.json`、memory | baseline 只读；一个 candidate 一个 strategy；gate 顺序固定 |
| Cross-check | sub-agent reviewer | reviewer notes | 检查诊断类型、measurement evidence、candidate acceptance 是否自洽 |
| Final optimization | `aprof-optimization-agent` | `final_optimization_report.md`、可选 `best_op/` | production-safe、稳定采样、语义保持且 metric 改善才可选 best |

## Optimization Gate Cascade

1. `EnvironmentPreflight`
   - Guard skill: `ascendc-env-check`
   - 确认 CANN env、NPU/SoC、`msprof` 或 `cannsim`。

2. `OptimizationRouting`
   - 诊断六类优先：`tiling`、`data_movement`、`pipeline_parallel`、`onchip_memory`、`ai_core_utilization`、`api_algorithm`。
   - 若诊断缺失，再用 profiling bound；最后才源码扫描。

3. `Workload/Tiling/BoundModeling`
   - Default references: AProf optimization branch references、`workload-aware-diagnosis.md`、`roofline-single-case.md`、`npu-arch`。
   - optional deep lookup: only use `optimization-cannbot-knowledge-index.md` for one precise CANNBot reference when API/platform/operator mechanism is unresolved.
   - double buffer 必须证明 UB 预算；blockDim 必须证明每核任务量不会过小；MatMul/FA/Sort/Softmax 等复杂候选必须证明 workspace、数值语义和阶段边界。

4. `WorkloadAndRooflineFeasibility`
   - Guard references: `workload-aware-diagnosis.md`、`roofline-single-case.md`。
   - tiny/small workload 的低 UB/AI Core 利用率默认是 `workload_limited`，除非有额外真实瓶颈证据。

5. `CorrectnessAndGeneralityGate`
   - 默认 `production_safe`。
   - 硬编码 shape/core/UB/tile、删动态 tiling、降精度或缩小支持边界的 candidate 标为 `benchmark_specialized`。

6. `StaticReview`
   - Guard skill: `ascendc-code-review`。
   - build 前检查 API 合法性、UB/DataCopy 边界、pipeline 顺序、portability risk。

7. Local gates
   - build -> accuracy -> repeated profile -> measurement stability -> metric compare。
   - accuracy 不通过不得 profile。
   - profile metric 缺失不得声明性能提升。
   - warmup/repeat 缺失或 CV 超阈值不得声明确定性性能提升。
   - simulator-only metric 必须标注为 proxy。
   - `scope_status != production_safe` 不得生成 `best_op`，但要报告其 speedup 和拒绝原因。

## Failure Handoff

| Failure | Handoff |
| --- | --- |
| build/API/static review failure | `ascendc-code-review` |
| accuracy failure | `ascendc-precision-debug` |
| runtime nonzero / error code | `ascendc-runtime-debug` |
| timeout / hang / crash / AIC error | `ascendc-crash-debug` |
| profile artifact or metric missing | `ops-profiling` |
| measurement unstable or single run | `ops-profiling` |
| metric regression | record memory and try next candidate |
| benchmark-specialized candidate selected as best | reject selection and route to `ascendc-code-review` |

## Optimization Memory

File: `aprof_opt/optimization_memory.jsonl`

Key fields:

- `op_name`
- `shape`
- `dtype`
- `soc`
- `problem_family`
- `strategy_id`

Value fields:

- `status`
- `metric_before`
- `metric_after`
- `speedup`
- `failure_reason`
- `failure_handoff`
- `changed_files`

Memory should be filtered by op/shape/dtype/soc/problem family and read as top-K related records, not loaded wholesale.
