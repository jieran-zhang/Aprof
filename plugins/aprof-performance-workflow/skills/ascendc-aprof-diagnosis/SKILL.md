---
name: ascendc-aprof-diagnosis
description: Build source, workload, and profile evidence for an Ascend C performance task. Use to activate auditable evidence predicates, produce non-exclusive anchor facets and provisional mechanism hypotheses, request missing metrics, or interpret existing profiling data before SkillGraph routing. Treat every Agent output as a draft for runtime validation.
---

# AscendC AProf 性能诊断

## Machine boundary

- Treat the six historical families as non-exclusive expert facets, not as
  mutually exclusive root-cause labels.
- Preserve multiple mechanism hypotheses, refuting evidence, missing views, and
  `unknown_unresolved`; do not force a classification to make routing easier.
- Emit draft evidence only. Validate it with `aprofctl contract validate` before
  it enters a route or episode. Do not assign policy reward or accept a
  candidate in this skill.

## 使用场景

当用户需要分析 Ascend C 算子性能问题时使用本 Skill：

- 只提供 kernel 源码，需要先从源码形态推断可能的性能问题，并选择最相关的硬件 metric。
- 已通过 `msprof` / `aprof` 采集到性能数据，需要判断瓶颈来源。
- 需要在没有 baseline 对照的情况下，基于单个 kernel、硬件参数和 profiling report 判断硬件利用率。
- 需要把性能现象映射到算子分类、硬件 metric、派生指标和优化方向。
- 需要沉淀新的“性能问题 ↔ metric”诊断矩阵，供后续复用。

## 诊断流程

1. 若输入是源码，先读取 [references/source-hypothesis-routing.md](references/source-hypothesis-routing.md)，把代码模式映射到一个或多个 anchor facets 和可检验机制假设。
2. 按相关 facets 加载本 Skill 的 reference 文档，提出最多 3 个 provisional mechanism hypotheses，并保留支持、反驳和缺失证据。
3. 若源码或 profiling 已呈现 Scalar / Memory / Vec / CUBE / no-bound 现象，再读取 [references/bound-deep-routing.md](references/bound-deep-routing.md) 做二级根因分流。
4. 从这些假设中挑选最多 3 个最相关硬件 metric。输出是 draft；机器 schema 位于仓库 `schemas/`，旧格式映射说明见 [../references/contracts.md](../references/contracts.md)。
5. 若还没有采集数据，把 `metrics[]` 交给 `/ascendc-aprof-profiling` 设计采集任务和 metric 清单。
6. 若已有 profiling 数据，再用 `/ops-profiling` 读取采集方式、CSV 字段和瓶颈判定方法。
7. 再用 `/npu-arch` 获取核数、UB/L1/L0/L2/BT 容量、频率、理论带宽和理论算力等分母参数。
8. 读取 [references/workload-aware-diagnosis.md](references/workload-aware-diagnosis.md)，先构造 workload model 与 attainable utilization。
9. 若是单 kernel 独立诊断，读取 [references/roofline-single-case.md](references/roofline-single-case.md)，构造 roofline / proxy roofline。
10. 交叉判断“直接证据、派生证据、Trace/对比证据”，输出诊断结论、关键 metric、证据等级和下一步验证方法。

## Context-safe deep diagnosis

- 默认只读取本 Skill 的本地 reference。不要把大型外部 Skill 加入 diagnosis agent 默认上下文。
- 源码静态诊断的默认读取集是：`source-hypothesis-routing.md`、1-3 个相关问题族 reference、必要时 `bound-deep-routing.md`。
- 证据归因阶段再按需读取 `workload-aware-diagnosis.md`、`roofline-single-case.md`、`ops-profiling` 和 `npu-arch`。
- 只有 API overload、repeat limit、DataCopyPad 参数、MatMul/FA/Sort/Softmax 机制等本地 reference 无法确认时，才读取 [references/cannbot-knowledge-index.md](references/cannbot-knowledge-index.md)，并只点读其中一个具体 reference 文件。
- 禁止把外部优化策略直接写成诊断结论。外部知识只能用于形成源码锚点、metric 需求、反证规则和 `missing_evidence`。

## 源码静态诊断约束

- 源码阶段只能输出 `source-hypothesis`，不能把假设写成最终结论。
- 性能问题假设最多 3 个；硬件 metric 最多 3 个。
- Metric 必须能追溯到现有 reference、`ops-profiling` 字段、trace/timeline 或 `/npu-arch` 分母。
- 当多个问题共享同一 metric 时，优先选择能同时验证多个假设的 metric。
- 不确定源码语义时，标注需要用户补充 Host Tiling、shape、dtype、blockDim、TilingData 或 profiling 数据。

## 单 Kernel 独立诊断约束

- 默认不依赖 baseline。baseline 只能作为可选附录，不能作为主判断依据。
- 每个诊断问题必须输出独立 `metrics[]`，至少 2 个，推荐源码 metric、tiling/shape metric、report/trace metric 各 1 个。
- 必须说明硬件分母来源：`/npu-arch`、`PlatformAscendC`、msprof 字段或用户提供参数。
- 必须先输出 `workload_model` 与 `attainable_utilization`。小 workload 的低 UB/AI Core 利用率默认是 `workload_limited`，不能直接当作 `true_bottleneck`。
- 缺少真实 `Memory.csv` / `ArithmeticUtilization.csv` 时，只能输出 `roofline-estimated` 或 `trace-proxy`，不能声称真实硬件利用率。
- 缺少 warmup/repeat 或测量波动超过阈值时，输出 `measurement_limited`，不能给确定性性能归因。
- 注入评估场景禁止读取 ground-truth 泄露项：`injected_label`、`injected_problem`、variant 名、`inject_manifest.json`、`inject_audit_report.json`、`label_alignment_report.json`。

## 当前内置诊断

- Tiling 问题诊断矩阵：[references/tiling-diagnosis-metrics.md](references/tiling-diagnosis-metrics.md)
- 数据搬运瓶颈诊断矩阵：[references/data-movement-diagnosis-metrics.md](references/data-movement-diagnosis-metrics.md)
- 流水并行不足诊断矩阵：[references/pipeline-parallel-diagnosis-metrics.md](references/pipeline-parallel-diagnosis-metrics.md)
- 片上内存利用不足诊断矩阵：[references/onchip-memory-diagnosis-metrics.md](references/onchip-memory-diagnosis-metrics.md)
- AI Core 利用率低诊断矩阵：[references/ai-core-utilization-diagnosis-metrics.md](references/ai-core-utilization-diagnosis-metrics.md)
- API 与算法实现低效诊断矩阵：[references/api-algorithm-diagnosis-metrics.md](references/api-algorithm-diagnosis-metrics.md)
- 源码模式到问题族路由：[references/source-hypothesis-routing.md](references/source-hypothesis-routing.md)
- Bound 二级深层路由：[references/bound-deep-routing.md](references/bound-deep-routing.md)
- Workload-aware 可达上限诊断：[references/workload-aware-diagnosis.md](references/workload-aware-diagnosis.md)
- 单 kernel roofline 诊断：[references/roofline-single-case.md](references/roofline-single-case.md)
- Optional deep lookup 索引：[references/cannbot-knowledge-index.md](references/cannbot-knowledge-index.md)
- Agent 阶段契约：[../references/contracts.md](../references/contracts.md)

## 扩展新诊断矩阵

当需要为新的性能问题族生成诊断矩阵时，先读取：

- Meta 生成方法：[references/metric-matrix-meta.md](references/metric-matrix-meta.md)

新增矩阵时必须保持：

- 不编造 msprof 字段、硬件参数或未验证行为。
- 硬件容量和核数以运行时平台查询结果作为分母。
- 对没有直接计数器的问题明确标注为派生或 Trace/对比证据。
- 对尚未展开的算子类别只给通用诊断方法，不写未经验证的专属规则。
