---
name: ascendc-aprof-profiling
description: Ascend C 算子 aprof/msprof 数据采集与解析 Skill。用于在诊断前规划并执行需要采集的 CSV、trace、timeline、shape、TilingData 和 NPU 架构分母；适用于用户准备采集性能数据、缺少诊断所需 metric、或需要把诊断矩阵反推为 profiling 任务清单时。
---

# AscendC AProf Profiling 采集与解析

## 使用场景

当用户还没有完整 profiling 数据，或已有数据不足以支撑 `/ascendc-aprof-diagnosis` 的诊断矩阵时，使用本 Skill：

- 需要从性能问题反推应采集哪些 `msprof` / `aprof` CSV、trace 和平台参数。
- 需要把 Tiling、数据搬运、流水、片上内存、AI Core 利用率、API/算法低效的诊断 metric 汇总成采集任务。
- 需要执行 msprof 并解析 report，得到可交给 `/ascendc-aprof-diagnosis` 验证的 metric 值。

## 工作流

1. 先读取 [references/metric-bundles.md](references/metric-bundles.md)，确认目标问题族和所需 metric 分组。
2. 若用户只给现象，先把现象映射到一个或多个诊断问题族。
3. 读取 [references/metric-to-msprof.md](references/metric-to-msprof.md)，把 metric 映射到 `hw-op`、`hw-msprof` 或 `sim`。
4. 为真实硬件采集写入 measurement policy：默认 `warm_up=10`、`repeat=5`、`statistic=median`、`stability_cv_threshold=0.05`、`min_effect_pct=3.0`。
5. 读取 [references/report-parsing.md](references/report-parsing.md)，写清楚 report 生成后如何解析字段、派生值和重复采样统计。
6. 输出 `profiling_plan.json`，契约见 [../references/contracts.md](../references/contracts.md)。
7. 若用户授权并且执行环境满足要求，执行 `msprof` / `msprof op simulator`，检查产物并输出 `profiling_results.json`。
8. 对缺失数据或不稳定数据明确说明无法直接诊断的原因，并给出下一步采集命令或文件要求。
9. 采集完成后切换到 `/ascendc-aprof-diagnosis` 使用对应诊断矩阵归因。

## 命令选型

- 优先选择能直接产出目标 metric 的真实硬件采集：
  - `hw-op`：需要 `OpBasicInfo.csv`、`PipeUtilization.csv`、`Memory.csv` 等 msopprof 8 CSV 时优先。
  - `hw-msprof`：需要 7 组 `aic-metrics`、sample、`hw_summary.txt` 或对比摘要时优先。
- 只有在无 NPU、只需 timeline/proxy metric，或明确要求 simulator 时，才选择 `sim`。
- simulator 只能作为 trace / 指令 / 源码热点代理，不能声称产出 `PipeUtilization.csv`、`Memory.csv` 等上板 CSV。
- `hw-op` 默认命令是 `msprof op --warm-up=10 --launch-count=5 ...`。
- 普通 `msprof --application` 只能作为 legacy fallback；它必须先显式 warmup，再外层 repeat 多次，每次写入独立 run 目录。
- 单次硬件采集只能标记为 `single_run_exploration`；不得作为 final metric evidence 或优化收益声明。

## 输出契约

输出必须包含：

- `profile_mode`：`sim` / `hw-msprof` / `hw-op`。
- `msprof_command`：首选命令、fallback 命令、simulator 命令。
- `required_artifacts`：诊断必须存在的 CSV、trace 或 summary。
- `parser_plan`：每个 metric 对应的文件、字段、公式和输出 key。
- `execution_plan`：执行 msprof 所需的模式、命令参数、输出目录和 summarize/parse 步骤。
- `measurement_policy`：warmup、repeat、统计值选择、稳定性阈值和最小有效提升。
- 执行后输出 `profiling_results.json`：产物清单、缺失项、metric 值、样本、统计、来源文件、字段和公式。

## 输出要求

- 不编造 `msprof` 字段、采集参数或平台规格。
- 所有派生 metric 必须写清楚分子、分母和数据来源。
- 所有 duration / throughput / bandwidth 证据必须带 `samples` 和 `statistics`；默认使用 median 参与 before/after 比较。
- CV 超过阈值、样本数不足或 baseline/candidate policy 不一致时，输出 `measurement_status=measurement_limited`，不要给确定性结论。
- 对 CSV 无法直接支持的问题，明确标注需要 trace/timeline、代码审查、TilingData 或对比实验。
- 面向用户的采集任务要可执行：说明需要提供哪些文件、字段、shape、dtype、blockDim、TilingData 和平台参数。
- 若输入来自 `diagnosis_hypotheses.json`，必须保留 `linked_hypotheses`，方便最终诊断追溯证据。
- 未经用户确认或环境缺失时，不执行 msprof；仍要输出可执行计划和缺失输入清单。
