---
schema_version: aprof.knowledge-record/v1
id: action.fuse_kernel_chain
kind: action
version: 1.0.0
status: active
title: 融合兼容的生产消费链
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 71
  - 71
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:a1cea15d1d3fa3b8a706be803b66f004c54a5a736cd92a6881a9cfc6116e640b
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 70
  - 70
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:a5f2ac5bc75340d70d168c6fe3a0ffd871225abe498cd727f25a2c9bc4ccc38d
learning:
  bias: 0
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 融合兼容的生产消费链
preconditions:
- fact: symptom.source.missing_kernel_fusion
  state: true
- fact: constraint.fusion_boundary
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

# 融合兼容的生产消费链

融合兼容的生产消费链。

这是方向性变换，不规定 tile、核数、buffer 个数或上游硬件常数。C1 携带此内容和前提快照；C2 从规划知识树选择方案、容量公式和 fallback；C3 从执行知识树选择实现方法。
