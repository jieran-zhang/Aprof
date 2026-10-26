---
schema_version: aprof.knowledge-record/v1
id: action.restructure_broadcast
kind: action
version: 1.0.0
status: active
title: 调整广播分块和复用
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 90
  - 90
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:5b45f68f39db91d205aded22104d3541a355e714ce07a82e0d80a5fc1c059e36
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 68
  - 68
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:57f549afbd96c61a5daf7debee3ab166f2051707846c0b79e023e902b0d05dab
learning:
  bias: 0
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 调整广播分块和复用
preconditions:
- fact: symptom.source.broadcast_strategy_mismatch
  state: true
- fact: constraint.broadcast_semantics
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 预期减少该机制的额外成本；具体方案由 C2 比较、C3 实施，统一计时核验。
---

# 调整广播分块和复用

调整广播分块和复用。

这是方向性变换，不规定 tile、核数、buffer 个数或上游硬件常数。C1 携带此内容和前提快照；C2 从规划知识树选择方案、容量公式和 fallback；C3 从执行知识树选择实现方法。
