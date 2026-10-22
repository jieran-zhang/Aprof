---
schema_version: aprof.knowledge-record/v1
id: edge.support.noncontiguous_access.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.noncontiguous_access → problem.noncontiguous_access
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
  weight: 2
tags: []
seed_reason: 2 分：“访问切分轴跨越连续内轴”支持“非连续访问破坏有效搬运”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.source.noncontiguous_access
to: problem.noncontiguous_access
conditions: []
---

# symptom.source.noncontiguous_access → problem.noncontiguous_access

关系为 supports，专家排序初值为 2。2 分：“访问切分轴跨越连续内轴”支持“非连续访问破坏有效搬运”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
