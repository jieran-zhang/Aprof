---
schema_version: aprof.knowledge-record/v1
id: action.batch_vector_api_calls
kind: action
version: 1.0.0
status: active
title: 批量调用 Vector API
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/api-algorithm-optimization-strategies.md
  original_path: skills/aprof/optimization/references/api-algorithm-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:27255603c8155ac2f34ba59420190390ba76d940bd9723790a6e72bb1defa5ad
  lines:
  - 20
  - 31
  sha256: sha256:27255603c8155ac2f34ba59420190390ba76d940bd9723790a6e72bb1defa5ad
  excerpt_sha256: sha256:bb24449a74087725fcd3a3da85fee76127b6fed34980d9a192704cab40aa17aa
learning:
  bias: 0
tags:
- api_algorithm
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 批量调用 Vector API
preconditions:
- fact: symptom.profile.vector_granularity_low
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 算子语义与精度要求保持
- 有效写回无重叠且覆盖完整
- 资源与依赖约束经核验
expected_effect: 由机制相关指标和统一计时共同核验；不承诺收益。
---

# 批量调用 Vector API

优化变换：批量调用 Vector API。规划角色决定适用 workload、任务所有权、容量与成本比较；实现角色选择 API、参数和执行细节。

前提见 preconditions；缺证据时只返回待验证方向。完整正确性后按 single_role_l2_clean_task_v1 计时。动作快照必须随 C1 交给 planning。

旧协议门禁和收益只在历史归档中保留，不迁入当前验收。
