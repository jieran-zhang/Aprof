---
schema_version: aprof.knowledge-record/v1
id: problem.excessive_sync_scope
kind: problem
version: 1.0.0
status: active
title: 同步范围或频次超过依赖要求
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/bound-deep-routing.md
  original_path: skills/aprof/diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  lines:
  - 83
  - 87
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:3f1619f1c79c4f97938c9ee8866c29bdc50f8fd8749486e79626cf99c8ed6c1e
learning:
  bias: 0
tags:
- api_algorithm
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 同步范围或频次超过依赖要求
alternatives:
- 工作负载限制
- 其他流水或搬运机制
---

# 同步范围或频次超过依赖要求

同步范围或频次超过依赖要求。先核验关联症状及反证，再提出本轮可检验假设。问题族只作为标签，不能代替机制。容量超限和同步错误应先作为正确性约束排查。
