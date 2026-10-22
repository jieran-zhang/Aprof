---
schema_version: aprof.knowledge-record/v1
id: planning.layout.transpose
kind: template
version: 1.0.0
status: active
title: 布局转换、有效宽度与对齐宽度
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/conversion/patterns.md
  original_path: ops/ascendc-tiling-design/references/conversion/patterns.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 261
  sha256: sha256:3b11c42fec83631ee8b2c26eefd3ac7b16b2606b6a09ea7ad15991c0b806e306
  excerpt_sha256: sha256:3b11c42fec83631ee8b2c26eefd3ac7b16b2606b6a09ea7ad15991c0b806e306
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.layout
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 布局转换、有效宽度与对齐宽度

## 适用域与算法骨架

明确输入输出 stride；转置不改变数值但可能涉及 padding、非连续输入。

按连续内轴搬入对齐 tile，片上转换，再按输出连续块写回；把有效 curN 和存储 tileNA 分开。

## 任务所有权、归约与同步

每个输出矩形单 owner；相邻 tile 的边界有效范围不重叠。

## 资源与成本公式

UB=inAligned+outAligned+offsetTable+tmp；repeats 与 stride 不超过目标 API 限制；额外 padding 计入容量。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

tileN、tileC、布局方案、repeat/mask；上限按 SDK/平台查询。

不支持的 stride/尾块走通用转换；不从历史示例推导通用 255 repeat 限制。

## 伪代码

```text
map task to unique output rectangle
load valid source using declared strides into aligned UB tile
convert using legal repeat/stride and offset table
write curN valid columns; tileNA only describes UB storage
```

## 可复用 Ascend C 关键片段

```cpp
// 有效长度和存储跨度保持两个变量，元素偏移不乘 sizeof 两次。
const uint64_t valid = remaining < tileN ? remaining : tileN;
const uint64_t localRow = row * tileNA;
// LocalTensor 分配/row offset 用 tileNA；GM 写回只覆盖 valid。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

