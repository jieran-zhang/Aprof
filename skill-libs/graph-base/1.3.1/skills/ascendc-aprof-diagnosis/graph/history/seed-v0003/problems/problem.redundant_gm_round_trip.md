---
schema_version: aprof.knowledge-record/v1
id: problem.redundant_gm_round_trip
kind: problem
version: 1.0.0
status: active
title: 中间结果冗余 GM 往返
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/data-movement-optimization-strategies.md
  original_path: skills/aprof/optimization/references/data-movement-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  lines:
  - 6
  - 13
  sha256: sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  excerpt_sha256: sha256:9474fc9702b87ae125f8b2a7ab5088a4024d1c446a4222107cad2c60cb18b1c5
learning:
  bias: 0
tags:
- api_algorithm
- data_movement
- onchip_memory
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 中间结果冗余 GM 往返
alternatives:
- 工作负载限制
- 其他流水或搬运机制
---

# 中间结果冗余 GM 往返

中间结果冗余 GM 往返。先核验关联症状及反证，再提出本轮可检验假设。问题族只作为标签，不能代替机制。容量超限和同步错误应先作为正确性约束排查。
