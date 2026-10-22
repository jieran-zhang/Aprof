---
schema_version: aprof.knowledge-record/v1
id: edge.support.workspace_overallocation.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.workspace_overallocation → problem.workspace_overallocation
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
  - 69
  - 69
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:a7e65beed2193c19504543679c2b38bb8ea86d53ec3dac4c375e33e2da8c7715
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 70
  - 70
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:076752ee0df51ce93370eb1489b75db0478be214d766a391f69e9870a48817a6
learning:
  weight: 2
tags: []
seed_reason: 2 分：“按最大 shape 或过量槽位分配 workspace”支持“workspace 配置引入额外成本”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.source.workspace_overallocation
to: problem.workspace_overallocation
conditions: []
---

# symptom.source.workspace_overallocation → problem.workspace_overallocation

关系为 supports，专家排序初值为 2。2 分：“按最大 shape 或过量槽位分配 workspace”支持“workspace 配置引入额外成本”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
