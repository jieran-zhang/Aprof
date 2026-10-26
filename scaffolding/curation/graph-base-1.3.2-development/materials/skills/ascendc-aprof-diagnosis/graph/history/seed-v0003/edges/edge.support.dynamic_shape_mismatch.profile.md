---
schema_version: aprof.knowledge-record/v1
id: edge.support.dynamic_shape_mismatch.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.dynamic_shape_mismatch → problem.dynamic_shape_mismatch
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
  weight: 2
tags: []
seed_reason: 2 分：“不同 shape 区间分别欠并行、开销高或流量放大”支持“固定策略未适配动态 shape”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.dynamic_shape_mismatch
to: problem.dynamic_shape_mismatch
conditions: []
---

# symptom.profile.dynamic_shape_mismatch → problem.dynamic_shape_mismatch

关系为 supports，专家排序初值为 2。2 分：“不同 shape 区间分别欠并行、开销高或流量放大”支持“固定策略未适配动态 shape”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
