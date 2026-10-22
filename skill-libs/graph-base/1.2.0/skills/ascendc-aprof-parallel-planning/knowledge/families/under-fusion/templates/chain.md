---
schema_version: aprof.knowledge-record/v1
id: planning.under-fusion.chain
kind: template
version: 1.0.0
status: active
title: 连续逐元素链片上融合
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-parallel-planning/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
  original_path: ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 342
  sha256: sha256:422c329fdf4dcb62d095afc88371f7bb44f51aa624398cc977cdc0e995b8d5e3
  excerpt_sha256: sha256:422c329fdf4dcb62d095afc88371f7bb44f51aa624398cc977cdc0e995b8d5e3
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: planning.under-fusion
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 连续逐元素链片上融合

## 适用域与算法骨架

生产消费链共享输出分区，且中间张量没有外部可见消费者。

把一个 tile 的整个计算链放在片上；按存活期复用临时区；减少 kernel 启动和 GM 中间张量。

## 任务所有权、归约与同步

一个 task 拥有该 tile 全链输出，无跨核依赖；输入别名和原地语义要核验。

## 资源与成本公式

savedGM≈2*ΣintermediateBytes；UB_peak=max_live_aligned_bytes；成本加入更高寄存器/UB 占用造成的并行度损失。

容量、可用核数、API 临时区由当前平台与 SDK 核验。所有容量使用字节，保留对齐和同时存活区间；不得把上游 4KB、固定 tile 或核数当通用约束。

## 参数空间与替代方案

融合边界、tile、计算 dtype、复用位置。

无法容纳或有外部消费者就缩短融合链；保留原链作为 fallback。

## 伪代码

```text
for each uniquely owned output tile:
  load source inputs
  apply each operation preserving required intermediate rounding
  recycle dead temporaries only after consumers complete
  write final output once
```

## 可复用 Ascend C 关键片段

```cpp
// 仅展示经 API 核验后的局部算术链；中间舍入必须符合原语义。
AscendC::Muls(tmpLocal, xLocal, scale, validCount);
AscendC::Adds(outLocal, tmpLocal, bias, validCount);
```

片段省略工程与已声明的张量/变量，不是完整可运行算子；API 重载、作用域、别名和平台支持在 C3 核验。C2 冻结算法、所有权、合并顺序和数值语义；tile、局部 buffer/API 实现只在已声明容量/语义边界内调整。

## 验证与证据状态

来源审读完成，当前没有 NPU 性能验证。验证覆盖空/极小输入、对齐边界、尾块、多 task、特殊值和最大资源需求；完整正确性通过后才用统一计时协议比较。历史模板结果不构成当前性能承诺。

