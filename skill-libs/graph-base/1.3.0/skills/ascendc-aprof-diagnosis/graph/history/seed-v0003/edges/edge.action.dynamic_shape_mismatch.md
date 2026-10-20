---
schema_version: aprof.knowledge-record/v1
id: edge.action.dynamic_shape_mismatch
kind: edge
version: 1.0.0
status: active
title: problem.dynamic_shape_mismatch → action.dispatch_by_workload
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
seed_reason: 2 分：按 workload 分发改善局部策略，同时增加分支/编译维护成本并必须保留域覆盖。
relation: mitigated_by
from: problem.dynamic_shape_mismatch
to: action.dispatch_by_workload
conditions: []
---

# problem.dynamic_shape_mismatch → action.dispatch_by_workload

关系为 mitigated_by，专家排序初值为 2。2 分：按 workload 分发改善局部策略，同时增加分支/编译维护成本并必须保留域覆盖。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
