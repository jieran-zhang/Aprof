---
schema_version: aprof.knowledge-record/v1
id: action.reuse_disjoint_onchip_buffers
kind: action
version: 1.0.0
status: active
title: 复用不重叠存活期的 buffer
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/onchip-memory-optimization-strategies.md
  original_path: skills/aprof/optimization/references/onchip-memory-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:e7f4c274e3b3dbf51286c3131d382225cec631480111322fc8beca9b0a6f5de0
  lines:
  - 8
  - 25
  sha256: sha256:e7f4c274e3b3dbf51286c3131d382225cec631480111322fc8beca9b0a6f5de0
  excerpt_sha256: sha256:69dcbe9e4be7bfcda54b88926466d334eec87a1a5e271374e81c9cc931916dc5
learning:
  bias: 0
tags:
- onchip_memory
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 复用不重叠存活期的 buffer
preconditions:
- fact: symptom.source.ub_live_bytes_near_capacity
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

# 复用不重叠存活期的 buffer

优化变换：复用不重叠存活期的 buffer。规划角色决定适用 workload、任务所有权、容量与成本比较；实现角色选择 API、参数和执行细节。

前提见 preconditions；缺证据时只返回待验证方向。完整正确性后按 single_role_l2_clean_task_v1 计时。动作快照必须随 C1 交给 planning。

旧协议门禁和收益只在历史归档中保留，不迁入当前验收。
