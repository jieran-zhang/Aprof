---
schema_version: aprof.knowledge-record/v1
id: edge.action.redundant_cast
kind: edge
version: 1.0.0
status: active
title: problem.redundant_cast → action.coalesce_cast
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 65
  - 65
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:fc6046ab557edc2427920fd72df3a792b7640585fc670416312cc9c0948147c9
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 61
  - 61
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:7a330c74b26bff1596853d8e04a44dfeaf9e8a9fa3e8ff1249e143fb7f406b37
learning:
  weight: 3
tags: []
seed_reason: 3 分：“合并 Cast 与中间类型边界”直接消除“重复类型转换”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.redundant_cast
to: action.coalesce_cast
conditions: []
---

# problem.redundant_cast → action.coalesce_cast

关系为 mitigated_by，专家排序初值为 3。3 分：“合并 Cast 与中间类型边界”直接消除“重复类型转换”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
