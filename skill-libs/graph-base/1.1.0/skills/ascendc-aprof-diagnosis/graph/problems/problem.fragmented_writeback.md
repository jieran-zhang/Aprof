---
schema_version: aprof.knowledge-record/v1
id: problem.fragmented_writeback
kind: problem
version: 1.0.0
status: active
title: 碎片化写回
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
  bias: 0
tags:
- data_movement
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 碎片化写回
alternatives:
- 工作量或计数器口径受限
- 相邻搬运/流水/并行机制
---

# 碎片化写回

碎片化写回。源码只能提出假设；结合 profile 和工作量模型区分替代解释。正确性故障先排查实现约束，不能把错误执行的时延作为性能机制证据。
