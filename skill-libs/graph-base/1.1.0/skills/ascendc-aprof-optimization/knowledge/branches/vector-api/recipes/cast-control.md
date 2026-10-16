---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api.cast-control
kind: recipe
version: 1.0.0
status: active
title: Cast 合并与标量控制简化
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/reference/scalar/coding_principles.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 476
  sha256: sha256:96c753e315deb40eebe82c9827b2babc39497868296bcf0cac17ef89b4cb9387
  excerpt_sha256: sha256:96c753e315deb40eebe82c9827b2babc39497868296bcf0cac17ef89b4cb9387
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.vector-api
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Cast 合并与标量控制简化

## 适用条件

存在可证明冗余 Cast、重复索引/分支或标量热路径。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

先区分精度边界与纯格式转换；只合并不影响可见舍入的 Cast；外提不变量，分离主/尾循环；spill 先看编译报告再改对象存活期。

每一次消除舍入都要核验误差标准；不能因 Scalar 高就删 queue/event。

## 关键代码

```cpp
// Host 预计算不会随 tile 变化的 byteStride；kernel 只递增元素偏移。
for (uint64_t i = 0, offset = begin; i < fullTiles; ++i, offset += tileElements) {
    // 选定的向量路径处理 tileElements；尾块在循环外处理。
}
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

逐步对比中间结果、极端值和 dtype；编译报告检查 spill 是否减少；Task 计时验证。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

精度边界变化、特殊值不一致、分支外提改变地址或空输入行为。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

