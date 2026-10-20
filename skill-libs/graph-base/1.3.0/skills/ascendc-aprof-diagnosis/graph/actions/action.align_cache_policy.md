---
schema_version: aprof.diagnosis-record/v1
id: action.align_cache_policy
kind: action
version: 1.1.0
status: active
title: 按访问复用需求调整缓存策略
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 67
  - 67
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:6bbbe4fffe0c34b26ad3f4f5488e25af22b614c4d7d59f6092358fa8848ed539
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 68
  - 68
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:ade63739a7235448f04bfb37b4019442d94518f4bd0674423aa24011707d4d64
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 3
  - 24
  sha256: sha256:62807570650c1a69ab2bf0ba2bce606a4a3141d5d9d976fdbf3bdaf1d4df1092
  excerpt_sha256: sha256:8ca263c346e1369ddea6dc1294cf7ced14b7cfb3443d6369cd44affa59d3d7de
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 29
  - 37
  sha256: sha256:62807570650c1a69ab2bf0ba2bce606a4a3141d5d9d976fdbf3bdaf1d4df1092
  excerpt_sha256: sha256:9b2c776eb34f58c5310c2097988364047b5c7d02b5e2f4790164e399966d9ed2
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  original_path: docs/zh/api/SIMD-API/basic_api/data_structures/GlobalTensor/SetL2CacheHint.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 81
  - 88
  sha256: sha256:62807570650c1a69ab2bf0ba2bce606a4a3141d5d9d976fdbf3bdaf1d4df1092
  excerpt_sha256: sha256:33c1d1b40c2c4070d0807c58164b11e08c8eb85463fec8cf76560c55ba1bbbed
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 24
  - 35
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:e9a7c01b4dd1338cd812a8b6940b482fe8e12aa04ec8e88ef5b84b7450736933
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 48
  - 84
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:b48b1b038cc6090996c91bafcb22133ac35868808e5f715359c1907a8cb794cc
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 123
  - 134
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:1d4888316baa02f73aee3c82d6eff75edd9d7e71281705a17178023794f55107
learning:
  bias: 0
tags:
- onchip_memory
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 按访问复用需求调整缓存策略
preconditions:
- fact: symptom.source.cache_policy_mismatch
  state: true
- fact: constraint.cache_api
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 预期减少该机制的额外成本；具体方案由 C2 比较、C3 实施，统一计时核验。
slots:
- name: target
  kind: object
  description: 具有明确访问次数和复用距离的GlobalTensor及其L2策略
  required: true
- name: stage
  kind: stage
  description: kernel GlobalTensor策略设置；多次读写与cache替换窗口
  required: true
- name: workload
  kind: workload
  description: 绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
  required: true
- name: implementation
  kind: implementation
  description: 绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份
  required: true
claims:
- id: legacy_seed
  text: '原种子：按访问复用需求调整缓存策略；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  - 1
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_cache
  text: API文档说明L2默认启用，一次性输入可在实测回退时考虑禁用；枚举中的PERSISTENT在该修订明确暂不支持。
  basis: source_statement
  source_indexes:
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_mm_reuse
  text: arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。
  basis: source_statement
  source_indexes:
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 按目标支持范围比较默认或禁用等缓存策略及复用顺序
  basis: mechanism_inference
  source_indexes: &id001
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - 不同产品支持情况按源API表复核
  - 禁止以枚举存在推断PERSISTENT可用
- id: costs
  text: 可能降低其他tensor命中或增加GM字节；hint只表达意图，不能保证硬件驻留或收益
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按访问对象而非算子整体命中率划分，比较同一访问模式下的策略；一次性输入先比较禁用/默认的成本，不假定启用必快；低命中只来自首次或一次性读取时，不证明策略错误
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 不同产品支持情况按源API表复核
  - 禁止以枚举存在推断PERSISTENT可用
instantiation:
  target_slots:
  - target
  - stage
  - workload
  - implementation
  required_bindings:
  - target
  - stage
  - workload
  - implementation
  effect: 按目标支持范围比较默认或禁用等缓存策略及复用顺序；预期变化仅为prediction：符合API支持的策略或tile顺序调整可能改变命中及实际GM字节；这是prediction
  costs:
  - 可能降低其他tensor命中或增加GM字节
  - hint只表达意图，不能保证硬件驻留或收益
  unknown_policy: 任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 按访问复用需求调整缓存策略

## 变换与作用对象

按目标支持范围比较默认或禁用等缓存策略及复用顺序。

具有明确访问次数和复用距离的GlobalTensor及其L2策略；阶段：kernel GlobalTensor策略设置；多次读写与cache替换窗口。

## 实例绑定与原硬前提

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。未知信息不从样例常量或聊天推断。

- target
- stage
- workload
- implementation

- symptom.source.cache_policy_mismatch=true
- constraint.cache_api=true
- constraint.semantic_equivalence=true
- constraint.capacity=true

原invariants：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

## 预期效果与代价

按目标支持范围比较默认或禁用等缓存策略及复用顺序；预期变化仅为prediction：符合API支持的策略或tile顺序调整可能改变命中及实际GM字节；这是prediction

- 可能降低其他tensor命中或增加GM字节
- hint只表达意图，不能保证硬件驻留或收益

## 未知与返回规划

任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- 不同产品支持情况按源API表复核
- 禁止以枚举存在推断PERSISTENT可用

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：按访问复用需求调整缓存策略；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_cache [source_statement]

API文档说明L2默认启用，一次性输入可在实测回退时考虑禁用；枚举中的PERSISTENT在该修订明确暂不支持。

来源索引：2, 3, 4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mm_reuse [source_statement]

arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。

来源索引：5, 6, 7。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

按目标支持范围比较默认或禁用等缓存策略及复用顺序

来源索引：2, 3, 4, 5, 6, 7。限制：不同产品支持情况按源API表复核；禁止以枚举存在推断PERSISTENT可用

### costs [mechanism_inference]

可能降低其他tensor命中或增加GM字节；hint只表达意图，不能保证硬件驻留或收益

来源索引：2, 3, 4, 5, 6, 7。限制：代价需要绑定具体候选量化，尚无本任务收益
