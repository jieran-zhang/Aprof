---
schema_version: aprof.knowledge-record/v1
id: problem.noncontiguous_access
kind: problem
version: 1.0.0
status: active
title: 非连续访问破坏有效搬运
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 73
  - 73
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:00eb8d64b092277b1c935e9c8be46c2c2e00e282524b2039599e07becad94fc6
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 72
  - 72
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:53dd341a3953c0ebcd6d554405b122473a6143213ae0d4df6a59985fa8026b7b
learning:
  bias: 0
tags:
- data_movement
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 非连续访问破坏有效搬运
alternatives:
- 工作量或计数器口径受限
- 相邻搬运/流水/并行机制
---

# 非连续访问破坏有效搬运

非连续访问破坏有效搬运。源码只能提出假设；结合 profile 和工作量模型区分替代解释。正确性故障先排查实现约束，不能把错误执行的时延作为性能机制证据。
