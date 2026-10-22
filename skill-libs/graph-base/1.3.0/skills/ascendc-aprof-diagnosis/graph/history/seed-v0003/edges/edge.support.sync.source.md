---
schema_version: aprof.knowledge-record/v1
id: edge.support.sync.source
kind: edge
version: 1.0.0
status: active
title: symptom.source.sync_inside_tile_loop → problem.excessive_sync_scope
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/source-hypothesis-routing.md
  original_path: skills/aprof/diagnosis/references/source-hypothesis-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  lines:
  - 25
  - 27
  sha256: sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  excerpt_sha256: sha256:c0596dac53fcc2bdda48da7fb7606c0f6aef5a73696107c2e4abefea44128f4b
learning:
  weight: 3
tags: []
seed_reason: 3 分：“tile 循环内存在大范围同步”支持“同步范围或频次超过依赖要求”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.source.sync_inside_tile_loop
to: problem.excessive_sync_scope
conditions: []
---

# symptom.source.sync_inside_tile_loop → problem.excessive_sync_scope

关系为 supports，专家排序初值为 3。3 分：“tile 循环内存在大范围同步”支持“同步范围或频次超过依赖要求”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
