---
schema_version: aprof.knowledge-record/v1
id: edge.action.workspace_overallocation
kind: edge
version: 1.0.0
status: active
title: problem.workspace_overallocation → action.size_workspace_by_shape
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
seed_reason: 2 分：减少无用槽位或按 shape 分配可减少初始化/访问成本；只节省分配字节本身不保证 kernel 更快。
relation: mitigated_by
from: problem.workspace_overallocation
to: action.size_workspace_by_shape
conditions: []
---

# problem.workspace_overallocation → action.size_workspace_by_shape

关系为 mitigated_by，专家排序初值为 2。2 分：减少无用槽位或按 shape 分配可减少初始化/访问成本；只节省分配字节本身不保证 kernel 更快。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
