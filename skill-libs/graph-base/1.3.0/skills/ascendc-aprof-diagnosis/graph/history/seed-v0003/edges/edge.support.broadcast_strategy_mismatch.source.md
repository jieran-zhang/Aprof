---
schema_version: aprof.knowledge-record/v1
id: edge.support.broadcast_strategy_mismatch.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.broadcast_strategy_mismatch → problem.broadcast_strategy_mismatch
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
  weight: 2
tags: []
seed_reason: 2 分：“广播方案未区分连续内轴和重复输入”支持“广播方案与连续性或复用不匹配”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.source.broadcast_strategy_mismatch
to: problem.broadcast_strategy_mismatch
conditions: []
---

# symptom.source.broadcast_strategy_mismatch → problem.broadcast_strategy_mismatch

关系为 supports，专家排序初值为 2。2 分：“广播方案未区分连续内轴和重复输入”支持“广播方案与连续性或复用不匹配”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
