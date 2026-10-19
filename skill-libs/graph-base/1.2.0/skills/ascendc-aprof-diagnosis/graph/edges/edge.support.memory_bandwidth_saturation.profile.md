---
schema_version: aprof.knowledge-record/v1
id: edge.support.memory_bandwidth_saturation.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.memory_bandwidth_saturation → problem.memory_bandwidth_saturation
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 71
  - 71
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:40cf97cdaaeea3eb3cc641c95cc06f85b78db33183b9bb819b0a9260c70159b8
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 48
  - 48
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:33c702652aa6f9cbbc51464f7c3f1818dbc4f5e623cfe6835bd3267de4b5407c
learning:
  weight: 3
tags: []
seed_reason: 3 分：“大块连续搬运接近已校准带宽上限”支持“大块搬运受可达内存带宽限制”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.profile.memory_bandwidth_saturation
to: problem.memory_bandwidth_saturation
conditions: []
---

# symptom.profile.memory_bandwidth_saturation → problem.memory_bandwidth_saturation

关系为 supports，专家排序初值为 3。3 分：“大块连续搬运接近已校准带宽上限”支持“大块搬运受可达内存带宽限制”；带完整判别条件的证据能直接区分机制。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
