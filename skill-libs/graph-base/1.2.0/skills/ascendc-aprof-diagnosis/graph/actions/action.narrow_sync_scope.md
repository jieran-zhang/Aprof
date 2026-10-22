---
schema_version: aprof.knowledge-record/v1
id: action.narrow_sync_scope
kind: action
version: 1.0.0
status: active
title: 缩小同步范围
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
  - 8
  - 15
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:ba3e3f7359e9f6cc4fc631b9d329731f4b513e7ac68da8d315024614ac3a94f1
learning:
  bias: 0
tags:
- api_algorithm
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 缩小同步范围
preconditions:
- fact: symptom.source.sync_inside_tile_loop
  state: true
- fact: symptom.profile.overlap_low
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

# 缩小同步范围

优化变换：缩小同步范围。规划角色决定适用 workload、任务所有权、容量与成本比较；实现角色选择 API、参数和执行细节。

前提见 preconditions；缺证据时只返回待验证方向。完整正确性后按 single_role_l2_clean_task_v1 计时。动作快照必须随 C1 交给 planning。

旧协议门禁和收益只在历史归档中保留，不迁入当前验收。
