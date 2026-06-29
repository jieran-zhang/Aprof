---
name: ascendc-aprof-diagnosis
description: Ascend C 算子性能诊断 Skill。用于解读 aprof/msprof 指标，将算子分类、msprof 可观测字段、派生指标和 NPU 架构参数映射到性能问题；适用于已有 profiling 数据后进行性能归因、瓶颈定位、诊断矩阵复用或沉淀时。
---

# AscendC AProf 性能诊断

## 使用场景

当用户需要分析 Ascend C 算子性能问题时使用本 Skill：

- 已通过 `msprof` / `aprof` 采集到性能数据，需要判断瓶颈来源。
- 需要把性能现象映射到算子分类、硬件 metric、派生指标和优化方向。
- 需要沉淀新的“性能问题 ↔ metric”诊断矩阵，供后续复用。

## 诊断流程

1. 若还没有采集数据，先用 `/ascendc-aprof-profiling` 设计采集任务和 metric 清单。
2. 再用 `/ops-profiling` 读取采集方式、CSV 字段和瓶颈判定方法。
3. 再用 `/npu-arch` 获取核数、UB/L1/L0/L2/BT 容量、频率、理论带宽和理论算力等分母参数。
4. 按问题族加载本 Skill 的 reference 文档，交叉判断“直接证据、派生证据、Trace/对比证据”。
5. 输出时同时说明适用算子族、关键 metric、证据等级和下一步验证方法。

## 当前内置诊断

- Tiling 问题诊断矩阵：[references/tiling-diagnosis-metrics.md](references/tiling-diagnosis-metrics.md)
- 数据搬运瓶颈诊断矩阵：[references/data-movement-diagnosis-metrics.md](references/data-movement-diagnosis-metrics.md)
- 流水并行不足诊断矩阵：[references/pipeline-parallel-diagnosis-metrics.md](references/pipeline-parallel-diagnosis-metrics.md)
- 片上内存利用不足诊断矩阵：[references/onchip-memory-diagnosis-metrics.md](references/onchip-memory-diagnosis-metrics.md)
- AI Core 利用率低诊断矩阵：[references/ai-core-utilization-diagnosis-metrics.md](references/ai-core-utilization-diagnosis-metrics.md)
- API 与算法实现低效诊断矩阵：[references/api-algorithm-diagnosis-metrics.md](references/api-algorithm-diagnosis-metrics.md)

## 扩展新诊断矩阵

当需要为新的性能问题族生成诊断矩阵时，先读取：

- Meta 生成方法：[references/metric-matrix-meta.md](references/metric-matrix-meta.md)

新增矩阵时必须保持：

- 不编造 msprof 字段、硬件参数或未验证行为。
- 硬件容量和核数以运行时平台查询结果作为分母。
- 对没有直接计数器的问题明确标注为派生或 Trace/对比证据。
- 对尚未展开的算子类别只给通用诊断方法，不写未经验证的专属规则。
