---
schema_version: aprof.knowledge-record/v1
id: problem.memory_bandwidth_saturation
kind: problem
version: 1.0.0
status: active
title: 大块搬运受可达内存带宽限制
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
  bias: 0
tags:
- data_movement
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 大块搬运受可达内存带宽限制
alternatives:
- 工作量或计数器口径受限
- 相邻搬运/流水/并行机制
---

# 大块搬运受可达内存带宽限制

大块搬运受可达内存带宽限制。源码只能提出假设；结合 profile 和工作量模型区分替代解释。正确性故障先排查实现约束，不能把错误执行的时延作为性能机制证据。
