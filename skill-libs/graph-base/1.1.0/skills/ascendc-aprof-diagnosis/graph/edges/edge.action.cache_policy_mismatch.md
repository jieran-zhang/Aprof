---
schema_version: aprof.knowledge-record/v1
id: edge.action.cache_policy_mismatch
kind: edge
version: 1.0.0
status: active
title: problem.cache_policy_mismatch → action.align_cache_policy
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
  - 67
  - 67
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:6bbbe4fffe0c34b26ad3f4f5488e25af22b614c4d7d59f6092358fa8848ed539
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 68
  - 68
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:ade63739a7235448f04bfb37b4019442d94518f4bd0674423aa24011707d4d64
learning:
  weight: 2
tags: []
seed_reason: 2 分：只在有复用需求且目标缓存 API 可用时调整；一次性流和冷缓存计时不能套用命中率经验。
relation: mitigated_by
from: problem.cache_policy_mismatch
to: action.align_cache_policy
conditions: []
---

# problem.cache_policy_mismatch → action.align_cache_policy

关系为 mitigated_by，专家排序初值为 2。2 分：只在有复用需求且目标缓存 API 可用时调整；一次性流和冷缓存计时不能套用命中率经验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
