---
schema_version: aprof.knowledge-record/v1
id: edge.action.l1_l0_reuse_deficit
kind: edge
version: 1.0.0
status: active
title: problem.l1_l0_reuse_deficit → action.retain_matrix_tiles
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 65
  - 65
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:ac3b300a1072752593ea0a84f0cf793d808f6f99c80d696bcce978ca2d197df8
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 66
  - 66
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:30185d49b95529f1307aa3f9b05105aae2745b9493b7d597fb056274f554185a
learning:
  weight: 2
tags: []
seed_reason: 2 分：驻留节省重复搬入，但会挤占 L1/L0、改变分块和任务并行度。
relation: mitigated_by
from: problem.l1_l0_reuse_deficit
to: action.retain_matrix_tiles
conditions: []
---

# problem.l1_l0_reuse_deficit → action.retain_matrix_tiles

关系为 mitigated_by，专家排序初值为 2。2 分：驻留节省重复搬入，但会挤占 L1/L0、改变分块和任务并行度。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
