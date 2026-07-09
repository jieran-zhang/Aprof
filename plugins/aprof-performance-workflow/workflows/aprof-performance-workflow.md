# AProf Performance Workflow

目标：输入 Ascend C kernel 源码，输出性能问题诊断和相关硬件数据支撑。

## 状态机

```mermaid
flowchart TD
  KernelInput["Kernel source or op_dir"] --> DiagnosisAgent["aprof-diagnosis-agent"]
  DiagnosisAgent --> Hypotheses["diagnosis_hypotheses.json"]
  Hypotheses --> ProfilingAgent["aprof-profiling-agent"]
  ProfilingAgent --> ProfilingPlan["profiling_plan.json"]
  ProfilingPlan --> ProfilingRun["msprof execution + report parsing"]
  ProfilingRun --> ProfilingResults["profiling_results.json + CSV/trace/summary"]
  ProfilingResults --> FinalDiagnosis["aprof-diagnosis-agent final diagnosis"]
```

## Step 1：源码诊断

调用 `aprof-diagnosis-agent`：

- 输入：kernel 源码、源码路径或工程路径。
- 必读：`ascendc-aprof-diagnosis`、`source-hypothesis-routing.md`。
- 输出：`diagnosis_hypotheses.json`。

门禁：

- `hypotheses.length <= 3`。
- `metrics.length <= 3`。
- 每个 metric 有字段来源、公式或 trace 来源。

## Step 2：Metric 到采集计划

调用 `aprof-profiling-agent`：

- 输入：Step 1 的 `metrics[]` 和 `linked_hypotheses`。
- 必读：`metric-bundles.md`、`metric-to-msprof.md`、`report-parsing.md`。
- 输出：`profiling_plan.json`。

门禁：

- `profile_mode` 是 `sim`、`hw-msprof`、`hw-op` 之一。
- `execution_plan.profile_mode` 与 `profile_mode` 一致。
- 每个 metric 在 `parser_plan[]` 中有解析来源。

## Step 3：执行 msprof 并解析 report

继续由 `aprof-profiling-agent` 执行：

- 输入：本地 `op_dir`、`profiling_plan.json`、`execution_context`。
- 执行：`profiling_plan.json.msprof_command.preferred`，必要时使用 fallback。
- 输出：`profiling_results.json`、CSV/trace/summary。

门禁：

- `profiling_results.json.has_artifacts == true`。
- `profiling_results.json.ready_for_diagnosis == true` 时才进入强证据归因。
- 若产物缺失，记录 `missing_required_artifacts[]`，不要猜测 metric 值。

## Step 4：最终证据归因

再次调用 `aprof-diagnosis-agent`：

- 输入：源码、`diagnosis_hypotheses.json`、`profiling_plan.json`、`profiling_results.json`、report 目录。
- 输出：`final_diagnosis.md`。

最终报告必须包含：

- 最可能问题和证据等级。
- 每个关键 metric 的值、公式、来源文件。
- 缺失数据和下一步采集建议。

## 只生成计划模式

如果用户未授权执行 msprof，workflow 在 Step 2 停止，并输出：

- `diagnosis_hypotheses.json`。
- `profiling_plan.json`。
- 需要用户补充的 `run_cmd`、`gen_data_cmd`、输出目录或 NPU / simulator 环境信息。
