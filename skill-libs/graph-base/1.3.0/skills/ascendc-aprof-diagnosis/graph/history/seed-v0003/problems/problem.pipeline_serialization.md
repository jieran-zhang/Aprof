---
schema_version: aprof.knowledge-record/v1
id: problem.pipeline_serialization
kind: problem
version: 1.0.0
status: active
title: 搬运与计算串行
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  original_path: skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  lines:
  - 6
  - 15
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:592927cdbe10444156ea848793b8012a9def81eafd5c36dd4daf3e7a6e8bd5d5
learning:
  bias: 0
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 搬运与计算串行
alternatives:
- 工作负载限制
- 其他流水或搬运机制
---

# 搬运与计算串行

搬运与计算串行。先核验关联症状及反证，再提出本轮可检验假设。问题族只作为标签，不能代替机制。容量超限和同步错误应先作为正确性约束排查。
