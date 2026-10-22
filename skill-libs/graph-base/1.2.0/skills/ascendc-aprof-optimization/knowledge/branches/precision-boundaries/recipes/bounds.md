---
schema_version: aprof.knowledge-record/v1
id: implementation.precision-boundaries.bounds
kind: recipe
version: 1.0.0
status: active
title: Padding、容量和地址边界约束
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 151
  sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
  excerpt_sha256: sha256:c74ad927867806d42723213292831e22c84a2e84d75230e5aa615dee1500782a
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.precision-boundaries
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Padding、容量和地址边界约束

## 适用条件

任何 padding、动态尾、workspace 或静态 offset 变化。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

容量按实际同时存活、API tmp 和对齐计算；检查地址乘加溢出；确认 padding 中性元；仅有效元素参与输出与归约；同步错误先进入 debug。

sum padding 通常为 0、max 为负无穷，但以具体 oracle/类型语义为准；mask 不自动保护 GM 搬运。

## 关键代码

```cpp
// 在 host 使用足够宽整数并先检查乘法溢出。
const uint64_t alignedElements = ((validElements + align - 1) / align) * align;
const uint64_t bytes = alignedElements * sizeof(T);
// validElements+align-1、乘法与 bytes<=availableBytes 都需检查。
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

容量上下边界、最大索引、非对齐尾、padding 污染、同步压力；不在错误运行上做性能比较。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

ADDR_MISALIGN、越界、容量超限、随机错；调用 precision/runtime/crash debug。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

