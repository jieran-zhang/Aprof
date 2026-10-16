---
schema_version: aprof.knowledge-record/v1
id: implementation.vector-api.batch
kind: recipe
version: 1.0.0
status: active
title: Repeat / mask / stride 与批量 Vector API
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/reference/elementwise/vector_efficiency_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 203
  sha256: sha256:9f427095336cbb2e8024b29f664648b75abfe3b499471b999b30867d5c29213a
  excerpt_sha256: sha256:9f427095336cbb2e8024b29f664648b75abfe3b499471b999b30867d5c29213a
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.vector-api
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Repeat / mask / stride 与批量 Vector API

## 适用条件

同类小调用可在合法 stride 下批量化。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

确认 count/repeat/mask 单位和上限；主循环批量计算、尾部使用有效 count；减少重复 mask 设置；核验操作数别名与 buffer 对齐。

不把上游某平台 repeat 上限推广；mask 状态恢复须满足后续 API 契约。

## 关键代码

```cpp
// count 重载的简化示例；不是 repeat 参数重载。
AscendC::Add(outLocal, xLocal, yLocal, validCount);
// 使用 repeat/stride 重载前读取当前 SDK 的单位、上限与地址增量规则。
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

不整齐 count、repeat 上限附近、不同 dtype 和 stride；比较有用工作/指令数。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

只有部分 lane 写对、跨 repeat 错位、batch 后 UB 越界。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

