---
schema_version: aprof.knowledge-record/v1
id: problem.mixed_pipeline_imbalance
kind: problem
version: 1.0.0
status: active
title: 混合计算阶段节拍失衡
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 72
  - 72
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:f332ca0ab2465065bf17f622c0bc56d90a8517fd52ffb7fc22d514addec03297
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 69
  - 69
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:9fb77b6c76c680eba3183e8e3f355bc17632e1fa4707242d412b712cc67fe6bd
learning:
  bias: 0
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 混合计算阶段节拍失衡
alternatives:
- 工作量或计数器口径受限
- 相邻搬运/流水/并行机制
---

# 混合计算阶段节拍失衡

混合计算阶段节拍失衡。源码只能提出假设；结合 profile 和工作量模型区分替代解释。正确性故障先排查实现约束，不能把错误执行的时延作为性能机制证据。
