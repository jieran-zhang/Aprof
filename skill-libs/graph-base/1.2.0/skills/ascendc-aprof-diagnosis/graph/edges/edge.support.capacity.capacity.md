---
schema_version: aprof.knowledge-record/v1
id: edge.support.capacity.capacity
kind: edge
version: 1.0.0
status: active
title: symptom.source.ub_live_bytes_near_capacity → problem.onchip_capacity_pressure
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/onchip-memory-optimization-strategies.md
  original_path: skills/aprof/optimization/references/onchip-memory-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:e7f4c274e3b3dbf51286c3131d382225cec631480111322fc8beca9b0a6f5de0
  lines:
  - 8
  - 16
  sha256: sha256:e7f4c274e3b3dbf51286c3131d382225cec631480111322fc8beca9b0a6f5de0
  excerpt_sha256: sha256:9bfd9df5863281f66bf903b876b9e2aabd3faad27d9687f6230baba8f373537a
learning:
  weight: 3
tags: []
seed_reason: 3 分：“对齐后同时存活的片上 buffer 接近可用容量”支持“同时存活区间限制片上容量”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.source.ub_live_bytes_near_capacity
to: problem.onchip_capacity_pressure
conditions: []
---

# symptom.source.ub_live_bytes_near_capacity → problem.onchip_capacity_pressure

关系为 supports，专家排序初值为 3。3 分：“对齐后同时存活的片上 buffer 接近可用容量”支持“同时存活区间限制片上容量”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
