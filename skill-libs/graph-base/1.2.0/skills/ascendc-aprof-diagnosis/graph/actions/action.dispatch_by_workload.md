---
schema_version: aprof.knowledge-record/v1
id: action.dispatch_by_workload
kind: action
version: 1.0.0
status: active
title: 按工作量分组选择策略
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
  - 71
  - 71
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:ce7b8db8872e68fc98b2f9aa70bcc82cd14ad59da0027fbfdabba1be7708f744
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 74
  - 74
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:cdedaa2452701b501d11be72749d2d3d5f22a842c4bbab1b2cef6b73af7375fd
learning:
  bias: 0
tags:
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 按工作量分组选择策略
preconditions:
- fact: symptom.source.dynamic_shape_mismatch
  state: true
- fact: constraint.dispatch_coverage
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

# 按工作量分组选择策略

按工作量分组选择策略。

这是方向性变换，不规定 tile、核数、buffer 个数或上游硬件常数。C1 携带此内容和前提快照；C2 从规划知识树选择方案、容量公式和 fallback；C3 从执行知识树选择实现方法。
