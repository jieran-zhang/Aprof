---
schema_version: aprof.knowledge-record/v1
id: edge.support.tasks.profile
kind: edge
version: 1.0.0
status: active
title: symptom.profile.tasks_below_available_cores → problem.underused_task_parallelism
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
  - 20
  - 28
  sha256: sha256:0a70b21924e9ba29d6a75280699009b1f46afd4e9bd0fd3eb9880d592105e475
  excerpt_sha256: sha256:a3eb83c9d7033f7d03bb10827f2f2c369815bffebcf3880bb1437fd2fa90f48d
learning:
  weight: 2
tags: []
seed_reason: 2 分：“有效任务数少于可用核数”支持“已有独立任务并行度未暴露”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.tasks_below_available_cores
to: problem.underused_task_parallelism
conditions: []
---

# symptom.profile.tasks_below_available_cores → problem.underused_task_parallelism

关系为 supports，专家排序初值为 2。2 分：“有效任务数少于可用核数”支持“已有独立任务并行度未暴露”；有明确关联，仍需排除邻近机制或工作量解释。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
