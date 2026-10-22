---
schema_version: aprof.knowledge-record/v1
id: edge.support.reduction_strategy_mismatch.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.reduction_strategy_mismatch → problem.reduction_strategy_mismatch
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
  - 92
  - 92
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:85319e9fcd2232856dda05246f506a228641871b0760298bda87d9ba8b644699
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 73
  - 73
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:af8ee073d36877e56da3f4e1f339251d6c26dae5941d3eb2a8833c65e50e6606
learning:
  weight: 2
tags: []
seed_reason: 2 分：“AR/ARA 分支未随 A/R 和容量调整”支持“归约分解与工作量不匹配”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.source.reduction_strategy_mismatch
to: problem.reduction_strategy_mismatch
conditions: []
---

# symptom.source.reduction_strategy_mismatch → problem.reduction_strategy_mismatch

关系为 supports，专家排序初值为 2。2 分：“AR/ARA 分支未随 A/R 和容量调整”支持“归约分解与工作量不匹配”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
