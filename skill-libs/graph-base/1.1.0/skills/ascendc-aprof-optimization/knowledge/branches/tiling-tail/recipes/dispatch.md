---
schema_version: aprof.knowledge-record/v1
id: implementation.tiling-tail.dispatch
kind: recipe
version: 1.0.0
status: active
title: 元数据分发与实现身份接线
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-tiling-design/references/elewise/patterns.md
  original_path: ops/ascendc-tiling-design/references/elewise/patterns.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 46
  sha256: sha256:8a1351ff5295af67a53383682a4264aca6a19a113a2cdb47158938f73bae0cec
  excerpt_sha256: sha256:8a1351ff5295af67a53383682a4264aca6a19a113a2cdb47158938f73bae0cec
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.tiling-tail
references: []
evidence_status: source_reviewed_not_benchmarked
---

# 元数据分发与实现身份接线

## 适用条件

多方案、多 dtype/layout 或算法重规划后的候选。 输入是 C2 的 action/模板快照、实例参数、实现自由度、源码及架构证据。

## 操作步骤与约束

为各 workload group 设置互斥条件、稳定 uint64 key 和实际 kernel entry；保留通用 fallback；Host 设置 key，Kernel 使用相同 key 分支；更新 implementation_source_hash。

plan_basis_source_hash 仍指原分析源码；参数变化不得修改已承诺的算法/所有权。

## 关键代码

```cpp
// Host：key 来自校验通过的 dispatch_plan，不使用 case 名或 benchmark ID。
context->SetTilingKey(selectedKey);
// Kernel：对应的 TILING_KEY_IS 分支调用冻结的实现 entry。
```

片段用于表达关键契约，变量与工程由候选补齐。当前只完成来源审读；需按目标 SDK 编译和运行完整正确性，尚未进行 NPU 性能验证。

## 验证方法

dispatch select 覆盖域边界、未知 shape fallback、所有 key 都有实际实现；重新构建验证。 构建前调用 ascendc-code-review；正确性失败调用 ascendc-precision-debug，异常或挂起调用 ascendc-runtime-debug/ascendc-crash-debug。

## 失败特征与回退

计划选中了特化但实际 kernel 仍为旧分支；缺省 key 吞掉尾域。 保留原失败、完整日志与实际改动，回退到 C2 fallback 或请求重规划；不能静默改算法以继续计时。C3 记录所用条目版本、参数变化及计划符合性。

