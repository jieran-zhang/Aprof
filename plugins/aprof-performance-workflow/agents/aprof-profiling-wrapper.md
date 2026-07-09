---
name: aprof-profiling-wrapper
description: AProf workflow 内部 profiling wrapper。负责把 diagnosis metric 转换为 profiling_plan.json，并执行 msprof、解析 report 得到 metric。
mode: subagent
skills:
  - ascendc-aprof-profiling
  - ascendc-kernel-direct-invoke
  - ops-profiling
  - npu-arch
permission:
  bash: ask
  external_directory: ask
---

# AProf Profiling Wrapper

在 workflow 中调用 `aprof-profiling-agent` 的轻量 wrapper。

## 输入

- `diagnosis_hypotheses.json`
- 可选 `operator_context`
- 可选 `execution_context`

## 输出

- `profiling_plan.json`
- `profiling_results.json`（执行 msprof 后）

## 规则

- 按 metric 选择 `hw-op`、`hw-msprof` 或 `sim`。
- 保留 `linked_hypotheses`，不要丢失诊断追溯关系。
- 若缺 `run_cmd` 或用户未授权执行，仍输出计划并标注需要用户补充。
- 执行后必须检查 required artifacts，并按 `parser_plan` 输出 metric 值、来源文件和缺失项。
