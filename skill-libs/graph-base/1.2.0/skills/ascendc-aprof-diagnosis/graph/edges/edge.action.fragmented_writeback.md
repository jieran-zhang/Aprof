---
schema_version: aprof.knowledge-record/v1
id: edge.action.fragmented_writeback
kind: edge
version: 1.0.0
status: active
title: problem.fragmented_writeback → action.batch_writeback
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
  weight: 3
tags: []
seed_reason: 3 分：“合并连续有效输出写回”直接消除“碎片化写回”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.fragmented_writeback
to: action.batch_writeback
conditions: []
---

# problem.fragmented_writeback → action.batch_writeback

关系为 mitigated_by，专家排序初值为 3。3 分：“合并连续有效输出写回”直接消除“碎片化写回”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
