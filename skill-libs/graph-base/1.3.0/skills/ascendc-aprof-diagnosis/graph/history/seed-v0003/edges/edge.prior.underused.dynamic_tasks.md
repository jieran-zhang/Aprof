---
schema_version: aprof.knowledge-record/v1
id: edge.prior.underused.dynamic_tasks
kind: edge
version: 1.0.0
status: active
title: problem.underused_task_parallelism → action.decompose_tasks_dynamically
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
  - 25
  sha256: sha256:4b250dce13ff844f371c60c428dccb04616c7afa273c430ca9522d5a0a6b51c0
  excerpt_sha256: sha256:10483179d9c321decfa5cf6e4d7c9740c9410658e45747a92906e0598bcfb586
learning:
  weight: 3
tags: []
seed_reason: 3 分：“重新分解任务并选择核数”直接消除“已有独立任务并行度未暴露”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.underused_task_parallelism
to: action.decompose_tasks_dynamically
conditions: []
---

# problem.underused_task_parallelism → action.decompose_tasks_dynamically

关系为 mitigated_by，专家排序初值为 3。3 分：“重新分解任务并选择核数”直接消除“已有独立任务并行度未暴露”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
