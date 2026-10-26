---
schema_version: aprof.knowledge-record/v1
id: problem.broadcast_strategy_mismatch
kind: problem
version: 1.0.0
status: active
title: 广播方案与连续性或复用不匹配
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
mechanism: 广播方案与连续性或复用不匹配
alternatives:
- 工作量或计数器口径受限
- 相邻搬运/流水/并行机制
---

# 广播方案与连续性或复用不匹配

广播方案与连续性或复用不匹配。源码只能提出假设；结合 profile 和工作量模型区分替代解释。正确性故障先排查实现约束，不能把错误执行的时延作为性能机制证据。
