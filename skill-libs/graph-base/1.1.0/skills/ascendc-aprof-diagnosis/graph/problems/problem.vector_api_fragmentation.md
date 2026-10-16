---
schema_version: aprof.knowledge-record/v1
id: problem.vector_api_fragmentation
kind: problem
version: 1.0.0
status: active
title: Vector 调用碎片化
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  lines:
  - 59
  - 72
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:1ea72314f54681360c31f9fed51427b85eb98c17bb83cbf524d8ef3b1a147faa
learning:
  bias: 0
tags:
- api_algorithm
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: Vector 调用碎片化
alternatives:
- 工作负载限制
- 其他流水或搬运机制
---

# Vector 调用碎片化

Vector 调用碎片化。先核验关联症状及反证，再提出本轮可检验假设。问题族只作为标签，不能代替机制。容量超限和同步错误应先作为正确性约束排查。
