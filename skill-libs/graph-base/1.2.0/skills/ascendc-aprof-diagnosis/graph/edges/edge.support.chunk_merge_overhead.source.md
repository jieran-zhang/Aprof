---
schema_version: aprof.knowledge-record/v1
id: edge.support.chunk_merge_overhead.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.chunk_merge_overhead → problem.chunk_merge_overhead
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
  - 93
  - 93
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:366871d951ff662a5753237fdfe20e2a4caeb59eaf3c8e3760788f86c055d5c6
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 74
  - 74
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:46552244beab6eb8e8a81ee012a507e5a086135b377ac6eb9823d37a1e0d5853
learning:
  weight: 2
tags: []
seed_reason: 2 分：“chunk 数量多且每段产生部分结果”支持“跨 chunk 合并开销过高”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.source.chunk_merge_overhead
to: problem.chunk_merge_overhead
conditions: []
---

# symptom.source.chunk_merge_overhead → problem.chunk_merge_overhead

关系为 supports，专家排序初值为 2。2 分：“chunk 数量多且每段产生部分结果”支持“跨 chunk 合并开销过高”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
