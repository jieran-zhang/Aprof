---
schema_version: aprof.knowledge-record/v1
id: edge.prior.sync.narrow
kind: edge
version: 1.0.0
status: active
title: problem.excessive_sync_scope → action.narrow_sync_scope
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  original_path: skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  lines:
  - 8
  - 15
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:ba3e3f7359e9f6cc4fc631b9d329731f4b513e7ac68da8d315024614ac3a94f1
learning:
  weight: 3
tags: []
seed_reason: 3 分：“缩小同步范围”直接消除“同步范围或频次超过依赖要求”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.excessive_sync_scope
to: action.narrow_sync_scope
conditions: []
---

# problem.excessive_sync_scope → action.narrow_sync_scope

关系为 mitigated_by，专家排序初值为 3。3 分：“缩小同步范围”直接消除“同步范围或频次超过依赖要求”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
