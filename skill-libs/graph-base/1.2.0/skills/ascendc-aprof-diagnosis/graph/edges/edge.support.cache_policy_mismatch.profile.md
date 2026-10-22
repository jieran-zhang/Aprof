---
schema_version: aprof.knowledge-record/v1
id: edge.support.cache_policy_mismatch.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.cache_policy_mismatch → problem.cache_policy_mismatch
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
seed_reason: 2 分：“有复用需求时 L2 命中低且重复读流量增加”支持“缓存策略与复用模式不匹配”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.cache_policy_mismatch
to: problem.cache_policy_mismatch
conditions: []
---

# symptom.profile.cache_policy_mismatch → problem.cache_policy_mismatch

关系为 supports，专家排序初值为 2。2 分：“有复用需求时 L2 命中低且重复读流量增加”支持“缓存策略与复用模式不匹配”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
