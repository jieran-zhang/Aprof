---
schema_version: aprof.diagnosis-record/v1
id: problem.cache_policy_mismatch
kind: problem
version: 1.1.0
status: active
title: 缓存策略与复用模式不匹配
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
mechanism: 一次性流量和待复用数据采用不合适的缓存策略或共享工作集超过有效L2 → 缓存填充/替换增加成本，或重复访问未命中 → 额外GM访问或缓存管理影响关键路径
alternatives:
- problem.insufficient_input_reuse：缺少软件驻留与cache miss会共存，前者不要求hint错误；检查：核对Copy次数、L2命中和GM实际字节
- problem.memory_bandwidth_saturation：缓存策略是字节/替换原因，带宽饱和是资源状态；检查：同时检查重复读来源与持续带宽
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
  text: '原种子：缓存策略与复用模式不匹配；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 一次性流量和待复用数据采用不合适的缓存策略或共享工作集超过有效L2
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
- id: mechanism_2
  text: 缓存填充/替换增加成本，或重复访问未命中
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 不同产品支持情况按源API表复核
  - 禁止以枚举存在推断PERSISTENT可用
- id: mechanism_3
  text: 额外GM访问或缓存管理影响关键路径
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 不同产品支持情况按源API表复核
  - 禁止以枚举存在推断PERSISTENT可用
- id: prediction_1
  text: 符合API支持的策略或tile顺序调整可能改变命中及实际GM字节；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 按访问对象而非算子整体命中率划分，比较同一访问模式下的策略
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 一次性输入先比较禁用/默认的成本，不假定启用必快
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 低命中只来自首次或一次性读取时，不证明策略错误
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: PERSISTENT虽有枚举但该固定修订明确暂不支持，不能作为可执行动作
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.insufficient_input_reuse：缺少软件驻留与cache miss会共存，前者不要求hint错误；检查：核对Copy次数、L2命中和GM实际字节
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.memory_bandwidth_saturation：缓存策略是字节/替换原因，带宽饱和是资源状态；检查：同时检查重复读来源与持续带宽
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 按目标支持范围比较默认或禁用等缓存策略及复用顺序。代价：可能降低其他tensor命中或增加GM字节；hint只表达意图，不能保证硬件驻留或收益
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按访问对象而非算子整体命中率划分，比较同一访问模式下的策略；一次性输入先比较禁用/默认的成本，不假定启用必快；低命中只来自首次或一次性读取时，不证明策略错误
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 不同产品支持情况按源API表复核
  - 禁止以枚举存在推断PERSISTENT可用
analysis:
  mechanism_chain:
  - 一次性流量和待复用数据采用不合适的缓存策略或共享工作集超过有效L2
  - 缓存填充/替换增加成本，或重复访问未命中
  - 额外GM访问或缓存管理影响关键路径
  objects_and_stages:
  - 具有明确访问次数和复用距离的GlobalTensor及其L2策略
  - kernel GlobalTensor策略设置
  - 多次读写与cache替换窗口
  predictions:
  - 符合API支持的策略或tile顺序调整可能改变命中及实际GM字节；这是prediction
  supporting_checks:
  - 按访问对象而非算子整体命中率划分，比较同一访问模式下的策略
  - 一次性输入先比较禁用/默认的成本，不假定启用必快
  counter_checks:
  - 低命中只来自首次或一次性读取时，不证明策略错误
  - PERSISTENT虽有枚举但该固定修订明确暂不支持，不能作为可执行动作
  alternatives:
  - problem_id: problem.insufficient_input_reuse
    distinction: 缺少软件驻留与cache miss会共存，前者不要求hint错误
    check: 核对Copy次数、L2命中和GM实际字节
  - problem_id: problem.memory_bandwidth_saturation
    distinction: 缓存策略是字节/替换原因，带宽饱和是资源状态
    check: 同时检查重复读来源与持续带宽
  actions:
  - action_id: action.align_cache_policy
    intervention: 按目标支持范围比较默认或禁用等缓存策略及复用顺序
    requirements:
    - symptom.source.cache_policy_mismatch=true
    - constraint.cache_api=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 可能降低其他tensor命中或增加GM字节
    - hint只表达意图，不能保证硬件驻留或收益
  limits:
  - 不同产品支持情况按源API表复核
  - 禁止以枚举存在推断PERSISTENT可用
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 缓存策略与复用模式不匹配

## 对象、阶段与适用域

- 具有明确访问次数和复用距离的GlobalTensor及其L2策略
- kernel GlobalTensor策略设置
- 多次读写与cache替换窗口

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 一次性流量和待复用数据采用不合适的缓存策略或共享工作集超过有效L2
- 缓存填充/替换增加成本，或重复访问未命中
- 额外GM访问或缓存管理影响关键路径

## 预测、支持检查与反证

- 符合API支持的策略或tile顺序调整可能改变命中及实际GM字节；这是prediction
- 按访问对象而非算子整体命中率划分，比较同一访问模式下的策略
- 一次性输入先比较禁用/默认的成本，不假定启用必快
- 低命中只来自首次或一次性读取时，不证明策略错误
- PERSISTENT虽有枚举但该固定修订明确暂不支持，不能作为可执行动作

## 具体替代解释

- problem.insufficient_input_reuse：缺少软件驻留与cache miss会共存，前者不要求hint错误；检查：核对Copy次数、L2命中和GM实际字节
- problem.memory_bandwidth_saturation：缓存策略是字节/替换原因，带宽饱和是资源状态；检查：同时检查重复读来源与持续带宽

## 候选动作与成本

action.align_cache_policy：按目标支持范围比较默认或禁用等缓存策略及复用顺序。

原硬前提：symptom.source.cache_policy_mismatch=true；constraint.cache_api=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 可能降低其他tensor命中或增加GM字节
- hint只表达意图，不能保证硬件驻留或收益

## 限制与缺口

- 不同产品支持情况按源API表复核
- 禁止以枚举存在推断PERSISTENT可用
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：缓存策略与复用模式不匹配；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_cache [source_statement]

API文档说明L2默认启用，一次性输入可在实测回退时考虑禁用；枚举中的PERSISTENT在该修订明确暂不支持。

来源索引：2, 3, 4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mm_reuse [source_statement]

arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。

来源索引：5, 6, 7。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### mechanism_1 [mechanism_inference]

一次性流量和待复用数据采用不合适的缓存策略或共享工作集超过有效L2

来源索引：2, 3, 4, 5, 6, 7。限制：不同产品支持情况按源API表复核；禁止以枚举存在推断PERSISTENT可用

### mechanism_2 [mechanism_inference]

缓存填充/替换增加成本，或重复访问未命中

来源索引：2, 3, 4, 5, 6, 7。限制：不同产品支持情况按源API表复核；禁止以枚举存在推断PERSISTENT可用

### mechanism_3 [mechanism_inference]

额外GM访问或缓存管理影响关键路径

来源索引：2, 3, 4, 5, 6, 7。限制：不同产品支持情况按源API表复核；禁止以枚举存在推断PERSISTENT可用

### prediction_1 [mechanism_inference]

符合API支持的策略或tile顺序调整可能改变命中及实际GM字节；这是prediction

来源索引：2, 3, 4, 5, 6, 7。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

按访问对象而非算子整体命中率划分，比较同一访问模式下的策略

来源索引：2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

一次性输入先比较禁用/默认的成本，不假定启用必快

来源索引：2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

低命中只来自首次或一次性读取时，不证明策略错误

来源索引：2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

PERSISTENT虽有枚举但该固定修订明确暂不支持，不能作为可执行动作

来源索引：2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.insufficient_input_reuse：缺少软件驻留与cache miss会共存，前者不要求hint错误；检查：核对Copy次数、L2命中和GM实际字节

来源索引：2, 3, 4, 5, 6, 7。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.memory_bandwidth_saturation：缓存策略是字节/替换原因，带宽饱和是资源状态；检查：同时检查重复读来源与持续带宽

来源索引：2, 3, 4, 5, 6, 7。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

按目标支持范围比较默认或禁用等缓存策略及复用顺序。代价：可能降低其他tensor命中或增加GM字节；hint只表达意图，不能保证硬件驻留或收益

来源索引：2, 3, 4, 5, 6, 7。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
