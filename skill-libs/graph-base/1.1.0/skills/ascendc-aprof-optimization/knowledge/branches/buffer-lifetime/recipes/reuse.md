---
schema_version: aprof.knowledge-record/v1
id: implementation.buffer-lifetime.reuse
kind: recipe
version: 1.0.0
status: active
title: 存活期、合法复用与 UB 布局核验
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/ub_resident_design.md
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
parent: implementation.buffer-lifetime
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 存活期、合法复用与 UB 布局核验

## 适用条件

片上容量限制 tile 或存在重复临时 buffer。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

画 producer->consumer->最后使用的存活区间；只有所有消费者完成且 API 允许别名才复用；按对齐大小推进 offset；padding 变化同步重算容量。

peakBytes=max_t Σalive alignedBytes；异步搬运尚未完成时仍存活。UB bank 结构必须来自平台证据。

## 关键代码

```cpp
// 一段存储先由 phase A 使用，完成所有读取后才交 phase B。
pipe.InitBuffer(scratch, scratchBytes);
auto local = scratch.Get<T>();
// 不可仅因 C++ 变量出作用域就认为 DMA/Vector 已完成。
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

审查每个区间、异步完成边、完整正确性和多次运行；布局变更用冲突计数验证。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

偶发精度错、跨 tile 污染、padding 后容量超限；这类失败先修正确性。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

