---
name: ascendc-aprof-profiling
description: Ascend C 算子 aprof/msprof 数据采集设计 Skill。用于在诊断前规划需要采集的 CSV、trace、timeline、shape、TilingData 和 NPU 架构分母；适用于用户准备采集性能数据、缺少诊断所需 metric、或需要把诊断矩阵反推为 profiling 任务清单时。
---

# AscendC AProf Profiling 采集设计

## 使用场景

当用户还没有完整 profiling 数据，或已有数据不足以支撑 `/ascendc-aprof-diagnosis` 的诊断矩阵时，使用本 Skill：

- 需要从性能问题反推应采集哪些 `msprof` / `aprof` CSV、trace 和平台参数。
- 需要把 Tiling、数据搬运、流水、片上内存、AI Core 利用率、API/算法低效的诊断 metric 汇总成采集任务。
- 需要设计后续更细粒度的 metric skill，让大模型能按问题族主动提示用户收集对应数据。

## 工作流

1. 先读取 [todo.md](todo.md)，确认目标问题族和所需 metric 分组。
2. 若用户只给现象，先把现象映射到一个或多个诊断问题族。
3. 输出采集清单时按“必需 CSV、可选 CSV、Trace/Timeline、代码/TilingData、NPU 架构分母”分组。
4. 对缺失数据明确说明无法直接诊断的原因，并给出下一步采集命令或文件要求。
5. 采集完成后切换到 `/ascendc-aprof-diagnosis` 使用对应诊断矩阵归因。

## 输出要求

- 不编造 `msprof` 字段、采集参数或平台规格。
- 所有派生 metric 必须写清楚分子、分母和数据来源。
- 对 CSV 无法直接支持的问题，明确标注需要 trace/timeline、代码审查、TilingData 或对比实验。
- 面向用户的采集任务要可执行：说明需要提供哪些文件、字段、shape、dtype、blockDim、TilingData 和平台参数。
