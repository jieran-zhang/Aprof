---
schema_version: aprof.knowledge-record/v1
id: implementation.memory-transfer
kind: router
version: 1.3.0
status: active
title: 搬运与写回 路由
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-optimization/knowledge/sources/cannbot-skills/ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/reference/common/datacopy_optimization_design.md
  revision: c60a48af8f0ff2374e1491a313d9f26b02620d1e
  lines:
  - 1
  - 351
  sha256: sha256:e8cc9f2915a016c276cf431de51a66748779c510f82de2cc293e523beaed679e
  excerpt_sha256: sha256:e8cc9f2915a016c276cf431de51a66748779c510f82de2cc293e523beaed679e
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: implementation.root
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: implementation.memory-transfer.input-tile-residency
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.memory-transfer.input-tile-residency
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.reuse_domain
  - constraint.dependency_lifetime
  - constraint.output_ownership
  - constraint.same_input_region
  - constraint.input_value_preserved
  prior_score: 2
  fallback: false
  seed_reason: 同一 owner 的多个消费者保留同一原输入片，删除重复 GM 读取；先证明原值、有效地址域、生命周期及物理容量，不由 Action 名称或带宽指标代填。
- target: implementation.memory-transfer.coalesce
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.memory-transfer.coalesce
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.output_ownership
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: implementation.memory-transfer.example.tile-amortization
  match:
  - field: examples
    op: contains
    value: tile-amortization
  exclude: []
  required_evidence: []
  prior_score: 1
  fallback: false
  seed_reason: 探索性参照，需要额外证据。
- target: implementation.memory-transfer.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
- target: implementation.memory-transfer.cache-hint
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.memory-transfer.cache-hint
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.target_api
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.memory-transfer.l2-reuse-order
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.memory-transfer.l2-reuse-order
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.output_ownership
  - constraint.dependency_lifetime
  - constraint.l2_cache_enabled
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
- target: implementation.memory-transfer.strided-pad
  match: []
  exclude:
  - field: excluded_recipes
    op: contains
    value: implementation.memory-transfer.strided-pad
  required_evidence:
  - constraint.semantic_equivalence
  - constraint.capacity
  - constraint.plan_freedom
  - constraint.target_api
  - constraint.output_ownership
  prior_score: 2
  fallback: false
  seed_reason: 属于本分支的条件性方案；先核验正文的能力、语义和资源前提，再比较成本。
---

# 搬运与写回 路由

按 C2 冻结的方案与 features 选择实现技巧；可同时进入多个分支。保持算法、所有权和数值契约；超出已声明自由度时请求重规划。

- [同一 owner 内保留输入 tile 并删除重复 GM 读取](recipes/input-tile-residency.md)：多个真实消费者读取同一原值；不同值共槽、L2 命中、链融合另读其主正文。
- [连续搬运合并与批量写回](recipes/coalesce.md)
- [tile 放大与每 tile 设置开销的历史观察](examples/tile-amortization.md)
- [搬运与写回 回退方法](fallback.md)
- [一次性流式输入与复用输入的 L2 hint 区分](recipes/cache-hint.md)
- [分片内复用与 L2 工作集约束](recipes/l2-reuse-order.md)：要求同一目标输入的 `constraint.l2_cache_enabled=true`。当前 DISABLE 为 false；未知或缺证据保持 unknown，两者都不能成为就绪配方。输入驻留不依赖该缓存门禁。
- [规则跨行 DataCopyPad 与双端 stride 单位](recipes/strided-pad.md)

来源审读不等于目标硬件收益验证；不确定的能力或容量返回 needs_evidence，不能由模板代填。
