---
schema_version: aprof.knowledge-record/v1
id: edge.action.noncontiguous_access
kind: edge
version: 1.0.0
status: active
title: problem.noncontiguous_access → action.reorder_contiguous_access
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
  weight: 3
tags: []
seed_reason: 3 分：“按连续轴重排访问”直接消除“非连续访问破坏有效搬运”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.noncontiguous_access
to: action.reorder_contiguous_access
conditions: []
---

# problem.noncontiguous_access → action.reorder_contiguous_access

关系为 mitigated_by，专家排序初值为 3。3 分：“按连续轴重排访问”直接消除“非连续访问破坏有效搬运”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
