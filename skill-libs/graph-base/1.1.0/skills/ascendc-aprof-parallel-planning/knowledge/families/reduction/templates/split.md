---
schema_version: aprof.knowledge-record/v1
id: planning.reduction.split
kind: template
version: 1.0.0
status: active
title: ColSplit/RowSplit 与分段合并
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-colsplit.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-colsplit.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 149
  sha256: sha256:34e8f102983ce4ad564dd8f1a5b68552420f46fd01fd0345ca7d5afa962903b7
  excerpt_sha256: sha256:34e8f102983ce4ad564dd8f1a5b68552420f46fd01fd0345ca7d5afa962903b7
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.reduction
references: []
evidence_status: source_reviewed_not_benchmarked
---

# ColSplit/RowSplit 与分段合并

## 适用域与算法骨架

R 或 A0 不能全载，或独立输出任务不足；允许的数学合并已定义。

AR 切 R，ARA 根据连续内轴和 UB 预算选择 R chunk/A0 chunk；各段产生 partial，再由输出所有者合并。

## 任务所有权、归约与同步

若跨核分 R，每个 (output,split) 写独立槽，最终合并者唯一写输出；可用独立合并 kernel 建立同步。

## 资源与成本公式

S=ceil(R/Rc)；workspace=outputs*S*partialStateBytes；额外读写≈2*workspace；成本比较 parallel_compute+merge+launch。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

Rc、A0c、split 数、分层合并深度、partial dtype。

若合并成本抵消并行收益，回退单核按 chunk 累加；不硬编码 chunk 阈值。

## 伪代码

```text
map task -> (output group, reduction split)
for R chunk: load -> local reduction -> update partial state
write partial[output, split] to unique slot
after all producers complete: owner combines partials -> finalize -> output
```

## 可复用 Ascend C 关键片段

```cpp
// partial 的 index 由 C2 冻结；这里只展示合法向量加法合并。
AscendC::Add(accLocal, accLocal, partialLocal, validOutputs);
// Sum 可如此合并；Max、Welford、Softmax 状态必须使用各自合并公式。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

