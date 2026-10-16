---
schema_version: aprof.knowledge-record/v1
id: planning.matmul.resident
kind: template
version: 1.0.0
status: active
title: 小侧驻留与 L1/L0 复用
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/matmul/fullload_design.md
  original_path: ops/ascendc-performance-best-practices/reference/matmul/fullload_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 344
  sha256: sha256:e96e583c3cddcfba079a664f273533ecef25eec7bdc48fae8c1ae4f50e755f50
  excerpt_sha256: sha256:e96e583c3cddcfba079a664f273533ecef25eec7bdc48fae8c1ae4f50e755f50
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.matmul
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 小侧驻留与 L1/L0 复用

## 适用域与算法骨架

一侧矩阵或 scale 可在明确的生命周期内驻留，且重复使用超过一次。

驻留可复用侧，沿另一侧推进；分别规划 L1 端口、L0 片段、输出和 pingpong 占用。

## 任务所有权、归约与同步

仍按 MN 输出所有权；驻留数据不可在消费者完成前覆写。

## 资源与成本公式

saved_read≈(reuseCount−1)*residentBytes；resident+streamSlots+otherL1≤availableL1；同时校验 L0A/B/C。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

residentSide、reuseWindow、streamTile、stageDepth。

若 Cube 主导、复用不足或容量紧张，回退常规分块；不能泛化上游 L1/2 数值。

## 伪代码

```text
load reusable matrix side into the budgeted L1 region
for streaming-side tile: load -> stage L0 -> compute -> consume result
release resident region only after all consumers complete
```

## 可复用 Ascend C 关键片段

```cpp
// 使用 C2 的容量结果初始化相应 buffer；bytes 是字节，不是元素数。
pipe.InitBuffer(residentBuffer, residentBytes);
// TBuf 位置和 MatMul API 由目标平台核验；这里只复用 InitBuffer 的单位契约。
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

