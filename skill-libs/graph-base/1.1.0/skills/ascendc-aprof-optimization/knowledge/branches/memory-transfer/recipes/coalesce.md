---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer.coalesce
kind: recipe
version: 1.0.0
status: active
title: 连续搬运合并与批量写回
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 351
  sha256: sha256:e8cc9f2915a016c276cf431de51a66748779c510f82de2cc293e523beaed679e
  excerpt_sha256: sha256:e8cc9f2915a016c276cf431de51a66748779c510f82de2cc293e523beaed679e
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.memory-transfer
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 连续搬运合并与批量写回

## 适用条件

相邻有效地址可合并且输入输出无不允许的别名。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

列出每次 copy 地址和有效字节；合并相邻区间；保留 layout stride 语义；按输出所有权批量写回；一次性数据的 cache 策略与复用输入分别核验。

总读写字节不应因合并重复扩大；API 长度、stride、对齐与容量必须合法。

## 关键代码

```cpp
// 连续且满足该 DataCopy 重载的对齐要求时，count 为元素数。
AscendC::DataCopy(dstLocal, srcGm[offset], alignedCount);
// 非对齐有效尾部改用已核验的 DataCopyPad；不能为对齐越界读 GM。
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

比较原始 Task CSV 和 Memory/MTE 指令；检查布局、alias、非连续 stride、写回唯一性。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

MTE 指令减少但读字节增大、相邻 task 输出被覆盖、短尾越界。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

