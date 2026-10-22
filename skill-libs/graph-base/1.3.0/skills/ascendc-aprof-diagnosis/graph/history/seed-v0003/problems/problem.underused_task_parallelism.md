---
schema_version: aprof.knowledge-record/v1
id: problem.underused_task_parallelism
kind: problem
version: 1.0.0
status: active
title: 已有独立任务并行度未暴露
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/ai-core-utilization-optimization-strategies.md
  original_path: skills/aprof/optimization/references/ai-core-utilization-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:4b250dce13ff844f371c60c428dccb04616c7afa273c430ca9522d5a0a6b51c0
  lines:
  - 8
  - 16
  sha256: sha256:4b250dce13ff844f371c60c428dccb04616c7afa273c430ca9522d5a0a6b51c0
  excerpt_sha256: sha256:bbf4f8c97167a8c91155b677ae8fd3bae581f522fe462166a5756a23f4e6803f
learning:
  bias: 0
tags:
- ai_core_utilization
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 已有独立任务并行度未暴露
alternatives:
- 工作负载限制
- 其他流水或搬运机制
---

# 已有独立任务并行度未暴露

已有独立任务并行度未暴露。先核验关联症状及反证，再提出本轮可检验假设。问题族只作为标签，不能代替机制。容量超限和同步错误应先作为正确性约束排查。
