---
schema_version: aprof.knowledge-record/v1
id: action.coalesce_contiguous_transfers
kind: action
version: 1.0.0
status: active
title: 合并连续小搬运
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/data-movement-optimization-strategies.md
  original_path: skills/aprof/optimization/references/data-movement-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  lines:
  - 15
  - 24
  sha256: sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  excerpt_sha256: sha256:442645c8d750d1f3edee4654d63a5c17fa7465142b9a4e54f5c6334b143b7151
learning:
  bias: 0
tags:
- data_movement
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 合并连续小搬运
preconditions:
- fact: symptom.profile.mte_setup_dominated
  state: true
- fact: symptom.source.inner_loop_copy
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

# 合并连续小搬运

优化变换：合并连续小搬运。规划角色决定适用 workload、任务所有权、容量与成本比较；实现角色选择 API、参数和执行细节。

前提见 preconditions；缺证据时只返回待验证方向。完整正确性后按 single_role_l2_clean_task_v1 计时。动作快照必须随 C1 交给 planning。

旧协议门禁和收益只在历史归档中保留，不迁入当前验收。
