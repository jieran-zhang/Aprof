---
schema_version: aprof.knowledge-record/v1
id: action.decompose_tasks_dynamically
kind: action
version: 1.0.0
status: active
title: 重新分解任务并选择核数
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
  bias: 0
tags:
- ai_core_utilization
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 重新分解任务并选择核数
preconditions:
- fact: symptom.profile.tasks_below_available_cores
  state: true
- fact: symptom.source.fixed_or_undersubscribed_tasking
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
- fact: symptom.workload.tiny_or_overhead_limited
  state: false
- fact: constraint.task_ownership
  state: true
invariants:
- 算子语义与精度要求保持
- 有效写回无重叠且覆盖完整
- 资源与依赖约束经核验
expected_effect: 由机制相关指标和统一计时共同核验；不承诺收益。
---

# 重新分解任务并选择核数

优化变换：重新分解任务并选择核数。规划角色决定适用 workload、任务所有权、容量与成本比较；实现角色选择 API、参数和执行细节。

前提见 preconditions；缺证据时只返回待验证方向。完整正确性后按 single_role_l2_clean_task_v1 计时。动作快照必须随 C1 交给 planning。

旧协议门禁和收益只在历史归档中保留，不迁入当前验收。
