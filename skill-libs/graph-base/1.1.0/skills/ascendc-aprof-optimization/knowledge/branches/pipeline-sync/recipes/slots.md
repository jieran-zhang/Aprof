---
schema_version: aprof.knowledge-record/v1
id: implementation.pipeline-sync.slots
kind: recipe
version: 1.0.0
status: active
title: Workspace 槽所有权与混合流水
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/flashattention/design.md
  original_path: ops/ascendc-tiling-design/references/flashattention/design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 634
  sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
  excerpt_sha256: sha256:83ed347947ce330ed2940beb797be67fdc3cc30d60b9cf376d81711d76ab09cb
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.pipeline-sync
references: []
evidence_status: source_reviewed_not_benchmarked
---

# Workspace 槽所有权与混合流水

## 适用条件

FA、split-K、复杂 AIC/AIV 或跨 task 状态。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

分别定义 handshakeSlot、taskStateSlot、selfRefSlot、L1RotationSlot；每类使用自己的计数器、深度和生命周期；每段列出写者、读者、释放条件和初始化。

槽数是满足并发存活区间的结果，不从一个 magic number 复用；任何跨核等待需要可证明进展。

## 关键代码

```cpp
const uint64_t handshakeSlot = stageSequence % handshakeDepth;
const uint64_t taskStateSlot = taskSequence % stateDepth;
const uint64_t selfRefSlot = loopSequence % selfRefDepth;
// 各 depth > 0；槽位代次和事件对应，公式不能互换。
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

多 task、多 s2、多 chunk、回卷后重复运行；将每槽访问序列与 trace/结果核对。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

周期性精度漂移、仅多 s2 失败、悬挂；视为 race/死锁故障，不给性能奖励。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

