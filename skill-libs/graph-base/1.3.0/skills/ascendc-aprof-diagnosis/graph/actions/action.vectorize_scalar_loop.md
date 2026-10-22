---
schema_version: aprof.diagnosis-record/v1
id: action.vectorize_scalar_loop
kind: action
version: 1.2.0
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
expected_effect: 合法向量化可能减少逐元素Scalar处理与发射，但Gather/转换、UB暂存和精度路径可成为新成本。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
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
  source_indexes:
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
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 当前逐元素数据计算可用目标支持的Vector路径等价表达；数学/异常值/舍入、索引依赖、mask、别名和有效范围合法。 逐元素Scalar循环是源码事实，不要求先测到scalar_hot；索引控制与实际数据运算需区分。
    合法向量化可能减少逐元素Scalar处理与发射，但Gather/转换、UB暂存和精度路径可成为新成本。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
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
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 向量化逐元素热循环

## 变换与作用对象

把满足等价语义的逐元素Scalar数据处理改为批量Vector操作。

热路径逐元素Scalar读写/算术及下游发射队列；阶段：kernel Scalar逐元素循环；Vector/Cube/MTE指令分发。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

当前逐元素数据计算可用目标支持的Vector路径等价表达；数学/异常值/舍入、索引依赖、mask、别名和有效范围合法。

- `symptom.source.scalar_element_loop=true`：逐元素Scalar循环是源码事实，不要求先测到scalar_hot；索引控制与实际数据运算需区分。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。

不变量：算子语义与精度要求保持；有效写回无重叠且覆盖完整；资源与依赖约束经核验。

## 性能假设、比较与补证据

逐元素Scalar循环是源码事实，不要求先测到scalar_hot；索引控制与实际数据运算需区分。

合法向量化可能减少逐元素Scalar处理与发射，但Gather/转换、UB暂存和精度路径可成为新成本。

以下旧门槛作为性能/选择线索保留，不再与实施安全混用；期望false也原样保留：

- `symptom.profile.scalar_hot=true`：Scalar热点证据提高试验优先级，但不是等价逐元素向量化的安全前提。

1. 统计每输出标量运算/地址解码及数据复用，读取匹配dtype和形态的Vector/API文档，证明批量路径的精度和mask合法。
2. 已有Vector数据运算而仅Scalar控制时不要机械替换；无PMU可从逐元素工作规模提出有来源的试验。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

把满足等价语义的逐元素Scalar数据处理改为批量Vector操作；预期变化仅为prediction：合法向量化应减少Scalar迭代次数与发射控制；这是prediction

- UB暂存、mask、尾处理及alias限制
- 向量API可能采用不同舍入或异常值行为

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

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


### condition_separation [mechanism_inference]

当前逐元素数据计算可用目标支持的Vector路径等价表达；数学/异常值/舍入、索引依赖、mask、别名和有效范围合法。 逐元素Scalar循环是源码事实，不要求先测到scalar_hot；索引控制与实际数据运算需区分。 合法向量化可能减少逐元素Scalar处理与发射，但Gather/转换、UB暂存和精度路径可成为新成本。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。

## v0006 选择与语义边界

选择前统计主要数据循环与剩余控制工作，记录向量化覆盖的 dtype/形态和仍保留 Scalar 的域。批量化引入的 Gather、搬运、转换、初始化、mask 和同步属于方案成本；有 Vector 调用不说明这些成本已解决。R2 可在同一意图继续改善通路，也可回 C2 调整任务组织，依据新的工作/代价比较而非改动次数。

此段为基于既有变换语义的维护归纳，不新增上游性能声明、不放宽 preconditions，也不将当前任务的性能 unknown 改成 true。
