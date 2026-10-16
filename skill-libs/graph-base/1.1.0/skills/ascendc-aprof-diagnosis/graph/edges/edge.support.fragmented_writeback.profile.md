---
schema_version: aprof.knowledge-record/v1
id: edge.support.fragmented_writeback.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.fragmented_writeback → problem.fragmented_writeback
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
  - 68
  - 68
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:046dfba849eeb560f933ea7982af6157d5e2fe71d68cbcc073e24ffc9d82f602
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 72
  - 72
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:d7df4d171f1e21d25af9e45446cab3a978a620720009c24f873e0245d1189de4
learning:
  weight: 2
tags: []
seed_reason: 2 分：“MTE3/Fixpipe 有效字节小而发射密集”支持“碎片化写回”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.fragmented_writeback
to: problem.fragmented_writeback
conditions: []
---

# symptom.profile.fragmented_writeback → problem.fragmented_writeback

关系为 supports，专家排序初值为 2。2 分：“MTE3/Fixpipe 有效字节小而发射密集”支持“碎片化写回”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
