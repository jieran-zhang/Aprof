---
schema_version: aprof.knowledge-record/v1
id: problem.core_tail_imbalance
kind: problem
version: 1.0.0
status: active
title: 尾块或核间工作失衡
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/ai-core-utilization-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  lines:
  - 69
  - 75
  sha256: sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  excerpt_sha256: sha256:151fee08eb7bb07239cd8a1efc85c9ad5e0ae8e81ba270bf63f767908c94e110
learning:
  bias: 0
tags:
- ai_core_utilization
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 尾块或核间工作失衡
alternatives:
- 工作负载限制
- 其他流水或搬运机制
---

# 尾块或核间工作失衡

尾块或核间工作失衡。先核验关联症状及反证，再提出本轮可检验假设。问题族只作为标签，不能代替机制。容量超限和同步错误应先作为正确性约束排查。
