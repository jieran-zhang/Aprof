---
schema_version: aprof.knowledge-record/v1
id: edge.prior.tail.balance
kind: edge
version: 1.0.0
status: active
title: problem.core_tail_imbalance → action.balance_tail_assignment
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
  - 17
  sha256: sha256:4b250dce13ff844f371c60c428dccb04616c7afa273c430ca9522d5a0a6b51c0
  excerpt_sha256: sha256:6e9a34f87828e2e3411e63ea9605ebd2eef44c212ae45a37ef8f8e67d7b89653
learning:
  weight: 3
tags: []
seed_reason: 3 分：“重新分配尾块”直接消除“尾块或核间工作失衡”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.core_tail_imbalance
to: action.balance_tail_assignment
conditions: []
---

# problem.core_tail_imbalance → action.balance_tail_assignment

关系为 mitigated_by，专家排序初值为 3。3 分：“重新分配尾块”直接消除“尾块或核间工作失衡”对应的重复或不均衡工作，前提由动作独立核验。

适用域见 scope，额外匹配条件见 conditions。支持和反证必须引用可核验的 evidence_id；同一证据重复出现不重复计分。数值不是概率或收益预测。
