---
schema_version: aprof.diagnosis-record/v1
id: action.vectorize_scalar_loop
kind: action
version: 1.1.0
status: active
title: 向量化逐元素热循环
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
  - 6
  - 20
  sha256: sha256:27255603c8155ac2f34ba59420190390ba76d940bd9723790a6e72bb1defa5ad
  excerpt_sha256: sha256:f0d165b72d242a805fbc00e3903f2bb48703ad626737a2fc55d39d2e6ffc6332
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/guide.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/guide.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 4
  - 8
  sha256: sha256:1f9161d4bdd0ed256130213ce0e61598369c869b00ce28d54db38f5860536fdc
  excerpt_sha256: sha256:47193296d3dadc4f6cb6cf1c115a43b5e8378f6bccc04e275dac8a22b2a2093a
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 15
  - 25
  sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
  excerpt_sha256: sha256:743f93f580f11ed0c9e3153a6818733250ab0799b98476bb2dafceb8fdb27f36
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 180
  - 240
  sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
  excerpt_sha256: sha256:efde3ab67b4c0f8b83eb375e8e34414e578d86a54b791806098a317c17ab1979
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/coding_principles.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 434
  - 442
  sha256: sha256:a387544bac3f38ad940fae2930e75c9f7cda45c8e25324f4cd864bee1ce4827c
  excerpt_sha256: sha256:9d6e99db77f3f2de78230014fb6e81a352dafc2a34ebce8451d140c16ed9682f
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 5
  - 7
  sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
  excerpt_sha256: sha256:9fdf79fde327ec40103f1244c9c79ee4afac5860645886bc8ca27129f5ded562
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 64
  - 112
  sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
  excerpt_sha256: sha256:8348896087faf9bd588de56b5e1df00baa68d475f1afab6f8e8276e1f9cc60be
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 150
  - 172
  sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
  excerpt_sha256: sha256:e5e66d6dfee5187142cfec46bffa5d0f200431651a54f2df298a34412ae93434
learning:
  bias: 0
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 向量化逐元素热循环
preconditions:
- fact: symptom.profile.scalar_hot
  state: true
- fact: symptom.source.scalar_element_loop
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
slots:
- name: target
  kind: object
  description: 热路径逐元素Scalar读写/算术及下游发射队列
  required: true
- name: stage
  kind: stage
  description: kernel Scalar逐元素循环；Vector/Cube/MTE指令分发
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
  text: '原种子：向量化逐元素热循环；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_scalar_guide
  text: Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。
  basis: source_statement
  source_indexes:
  - 1
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_scalar
  text: 标量编码原则讨论动态数组寻址、别名、变量存活期和热循环内对象构造对Load/Store与寄存器分配的影响。
  basis: source_statement
  source_indexes:
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_vector
  text: Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。
  basis: source_statement
  source_indexes:
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 把满足等价语义的逐元素Scalar数据处理改为批量Vector操作
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - Scalar比例阈值不跨架构使用
  - 没有PC/指令映射时只保留来源推导
- id: costs
  text: UB暂存、mask、尾处理及alias限制；向量API可能采用不同舍入或异常值行为
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 区分Scalar算术、Load/Store、指令分发、ICache及等待；先审查依赖与有效域，再比较向量API是否产生等价精度；循环只是少量控制或真正数据相关串行递推，不能用比例高推出可向量化
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - Scalar比例阈值不跨架构使用
  - 没有PC/指令映射时只保留来源推导
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
  effect: 把满足等价语义的逐元素Scalar数据处理改为批量Vector操作；预期变化仅为prediction：合法向量化应减少Scalar迭代次数与发射控制；这是prediction
  costs:
  - UB暂存、mask、尾处理及alias限制
  - 向量API可能采用不同舍入或异常值行为
  unknown_policy: 任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 向量化逐元素热循环

## 变换与作用对象

把满足等价语义的逐元素Scalar数据处理改为批量Vector操作。

热路径逐元素Scalar读写/算术及下游发射队列；阶段：kernel Scalar逐元素循环；Vector/Cube/MTE指令分发。

## 实例绑定与原硬前提

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。未知信息不从样例常量或聊天推断。

- target
- stage
- workload
- implementation

- symptom.profile.scalar_hot=true
- symptom.source.scalar_element_loop=true
- constraint.semantic_equivalence=true
- constraint.capacity=true

原invariants：算子语义与精度要求保持；有效写回无重叠且覆盖完整；资源与依赖约束经核验。

## 预期效果与代价

把满足等价语义的逐元素Scalar数据处理改为批量Vector操作；预期变化仅为prediction：合法向量化应减少Scalar迭代次数与发射控制；这是prediction

- UB暂存、mask、尾处理及alias限制
- 向量API可能采用不同舍入或异常值行为

## 未知与返回规划

任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- Scalar比例阈值不跨架构使用
- 没有PC/指令映射时只保留来源推导

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：向量化逐元素热循环；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_scalar_guide [source_statement]

Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。

来源索引：1。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_scalar [source_statement]

标量编码原则讨论动态数组寻址、别名、变量存活期和热循环内对象构造对Load/Store与寄存器分配的影响。

来源索引：2, 3, 4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_vector [source_statement]

Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。

来源索引：5, 6, 7。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

把满足等价语义的逐元素Scalar数据处理改为批量Vector操作

来源索引：1, 2, 3, 4, 5, 6, 7。限制：Scalar比例阈值不跨架构使用；没有PC/指令映射时只保留来源推导

### costs [mechanism_inference]

UB暂存、mask、尾处理及alias限制；向量API可能采用不同舍入或异常值行为

来源索引：1, 2, 3, 4, 5, 6, 7。限制：代价需要绑定具体候选量化，尚无本任务收益
