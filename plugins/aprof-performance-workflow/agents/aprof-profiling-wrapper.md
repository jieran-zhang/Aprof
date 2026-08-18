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

在 workflow 中调用 `aprof-profiling-agent` 的轻量 wrapper。只构造采集/解析 draft；artifact completeness、paired statistics 和 measurement status 由 runtime 计算。

## 输入

- `diagnosis_hypotheses.json`
- 可选 `operator_context`
- 可选 `execution_context`

## 输出

- `profiling_plan.json`
- `profiling_results.json`（执行 msprof 后）

## 规则

- 按 metric 选择 `hw-op`、`hw-msprof` 或 `sim`。
- production gain 默认至少 30 个交错配对 cheap-timing samples，要求
  `CV<=0.05`、`speedup LCB>=1.03`；完整 msprof 使用 `warm_up=10`、
  `repeat=5` 聚合机制 metric，不能替代 timing pairs。
- `hw-op` 优先使用 `msprof op --warm-up=<warm_up> --launch-count=<repeat>`；legacy `msprof --application` 必须显式 warmup 并外层 repeat 到独立 run 目录。
- 保留 `linked_hypotheses`，不要丢失诊断追溯关系。
- build 后先执行完整 correctness，再允许 profiling；用 profiling skill 的 stage runner 保留命令、exit code、timeout、日志和 hash。
- 用 profiling skill 的 `compress_msprof.py` 把 raw CSV 转为结构化 symptom draft，保留多个 candidate mechanisms 和 unknown reason。
- CANNBot `ops-profiling` 负责采集和基础归档，但其 `summary.txt` 不是可训练 symptom，其 `--compare` 也不是 correctness 或 30-pair production gate。
- 若缺 `run_cmd` 或用户未授权执行，仍输出计划并标注需要用户补充。
- 执行后保留 raw artifacts、hash 和解析 draft；由 runtime 检查 required artifacts 并计算 metric statistics。
- 样本不足、CV 超阈值或策略不一致时设置 `measurement_status=measurement_limited` 或 `unstable`，不得交付为确定性 final evidence。
