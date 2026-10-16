---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync.pipeline
kind: recipe
version: 1.0.0
status: active
title: Prolog / steady / drain 与 queue/event 生命周期
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/elementwise/double_buffer_design.md
  original_path: ops/ascendc-performance-best-practices/reference/elementwise/double_buffer_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 288
  sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
  excerpt_sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.pipeline-sync
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Prolog / steady / drain 与 queue/event 生命周期

## 适用条件

存在可重叠的搬运/计算且 tile 数足以形成稳态。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

prolog 填充首个输入；steady 交错 CopyIn/Compute/CopyOut；drain 收尾；每次 Alloc 对应合法 Free，读写依赖用正确方向事件；不得用立即等待制造假双缓冲。

同槽新写必须等待上一消费者完成；depth 与事件数受当前平台/API 限制。

## 关键代码

```cpp
auto x = inQueue.AllocTensor<T>();
AscendC::DataCopy(x, xGm[offset], alignedCount);
inQueue.EnQue(x);
auto ready = inQueue.DeQue<T>();
// Compute(ready) 使用到完成；异步消费者仍活跃时不可 Free。
inQueue.FreeTensor(ready);
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

trace 分离启动、稳态和收尾；单 tile、两 tile、长流水、多轮任务正确性；核验真实 overlap。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

wait 成本增加、prolog/drain 漏处理、重复 enqueue/free、只启用双 buffer 却无重叠。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

