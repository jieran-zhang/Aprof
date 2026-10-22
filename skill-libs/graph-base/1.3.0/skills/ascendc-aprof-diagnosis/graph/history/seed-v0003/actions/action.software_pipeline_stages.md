---
schema_version: aprof.knowledge-record/v1
id: action.software_pipeline_stages
kind: action
version: 1.0.0
status: active
title: 重排软件流水阶段
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  original_path: skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  lines:
  - 17
  - 30
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:0ddacaf1380e88c73e90e584cab87eae3ed42968a03b49110ab1d3ce6737a98e
learning:
  bias: 0
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 重排软件流水阶段
preconditions:
- fact: symptom.profile.overlap_low
  state: true
- fact: symptom.source.serial_queue_or_event_order
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
- fact: constraint.dependency_lifetime
  state: true
invariants:
- 算子语义与精度要求保持
- 有效写回无重叠且覆盖完整
- 资源与依赖约束经核验
expected_effect: 由机制相关指标和统一计时共同核验；不承诺收益。
---

# 重排软件流水阶段

优化变换：重排软件流水阶段。规划角色决定适用 workload、任务所有权、容量与成本比较；实现角色选择 API、参数和执行细节。

前提见 preconditions；缺证据时只返回待验证方向。完整正确性后按 single_role_l2_clean_task_v1 计时。动作快照必须随 C1 交给 planning。

旧协议门禁和收益只在历史归档中保留，不迁入当前验收。
