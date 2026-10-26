---
schema_version: aprof.knowledge-record/v1
id: implementation.scalar-control
kind: router
version: 1.0.0
status: active
title: 标量、地址与控制开销
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 478
  sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
  excerpt_sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/scalar_overhead_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/scalar_overhead_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 119
  sha256: sha256:5980d08caaca929c00df820df4ef855e52d8574db112d97f57078e9131ed09a1
  excerpt_sha256: sha256:5980d08caaca929c00df820df4ef855e52d8574db112d97f57078e9131ed09a1
- path: skills/ascendc-aprof-optimization/knowledge/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/LocalTensor/LocalTensor_constructor.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 296
  sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
  excerpt_sha256: sha256:103ec2d4324f59620a49df8b4ddaec36c81552c1a5a850233177ecec77a34946
learning: {}
tags: []
seed_reason: 固定开源修订审读并以中文提炼；未做性能训练或硬件收益验证。
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.scalar-control.constant_lifetime
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.scalar-control.constant_lifetime
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.invariant_scope
  - constraint.target_api
  - constraint.static_layout_lifetime
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.scalar-control.hot_loop_address
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.scalar-control.hot_loop_address
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.invariant_scope
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.scalar-control.tilingdata_access
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.scalar-control.tilingdata_access
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.invariant_scope
  - constraint.target_api
  - constraint.tiling_abi
  - constraint.read_only_lifetime
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.scalar-control.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知条件保留现有合法方案并补资料。
---

# 标量、地址与控制开销

按 C2 冻结的方案与 features 选择实现技巧；可同时进入多个分支。保持算法、所有权和数值契约；超出已声明自由度时请求重规划。

- [编译期常量、对象别名与标量存活期](recipes/constant-lifetime.md)
- [标量热循环地址外提与首主尾分离](recipes/hot-loop-address.md)
- [TilingData GM 直读与热点字段局部缓存](recipes/tilingdata-access.md)
- [标量、地址与控制开销：保守回退](fallback.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
