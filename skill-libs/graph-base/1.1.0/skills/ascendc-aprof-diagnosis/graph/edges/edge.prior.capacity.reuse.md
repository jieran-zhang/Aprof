---
schema_version: aprof.knowledge-record/v1
id: edge.prior.capacity.reuse
kind: edge
version: 1.0.0
status: active
title: problem.onchip_capacity_pressure → action.reuse_disjoint_onchip_buffers
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
  weight: 2
tags: []
seed_reason: 2 分：复用可减少同时存活字节，但是否存在合法不重叠区间以及别名/同步成本需证明。
relation: mitigated_by
from: problem.onchip_capacity_pressure
to: action.reuse_disjoint_onchip_buffers
conditions: []
---

# problem.onchip_capacity_pressure → action.reuse_disjoint_onchip_buffers

关系为 mitigated_by，专家排序初值为 2。2 分：复用可减少同时存活字节，但是否存在合法不重叠区间以及别名/同步成本需证明。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
