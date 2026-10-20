---
schema_version: aprof.diagnosis-record/v1
id: problem.scalar_control_hot_loop
kind: problem
version: 1.1.0
status: active
title: 标量逐元素热循环
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/aprof/diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  lines:
  - 109
  - 123
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:262bd2001b98559e30850d1c573d848793147f15e3a4a5ebd0bd733ff2f1510c
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
mechanism: 本可按向量表达的元素处理使用逐元素Scalar访存或算术 → Scalar重复地址计算与读写并占据指令分发 → 其他流水不能及时获发工作并出现bubble
alternatives:
- problem.register_spill：寄存器溢出是额外LoadStore而非逐元素算法必需；检查：查spill/stack和汇编PC归属
- problem.control_metadata_overhead：mask/index等控制可外提，不要求逐元素数据运算；检查：定位热区是数据处理还是重复元数据
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
  text: '原种子：标量逐元素热循环；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 本可按向量表达的元素处理使用逐元素Scalar访存或算术
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
- id: mechanism_2
  text: Scalar重复地址计算与读写并占据指令分发
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - Scalar比例阈值不跨架构使用
  - 没有PC/指令映射时只保留来源推导
- id: mechanism_3
  text: 其他流水不能及时获发工作并出现bubble
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - Scalar比例阈值不跨架构使用
  - 没有PC/指令映射时只保留来源推导
- id: prediction_1
  text: 合法向量化应减少Scalar迭代次数与发射控制；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 区分Scalar算术、Load/Store、指令分发、ICache及等待
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 先审查依赖与有效域，再比较向量API是否产生等价精度
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 循环只是少量控制或真正数据相关串行递推，不能用比例高推出可向量化
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: Scalar高但主要spill或TilingData访存时应采用相应干预
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.register_spill：寄存器溢出是额外LoadStore而非逐元素算法必需；检查：查spill/stack和汇编PC归属
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.control_metadata_overhead：mask/index等控制可外提，不要求逐元素数据运算；检查：定位热区是数据处理还是重复元数据
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 把满足等价语义的逐元素Scalar数据处理改为批量Vector操作。代价：UB暂存、mask、尾处理及alias限制；向量API可能采用不同舍入或异常值行为
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 区分Scalar算术、Load/Store、指令分发、ICache及等待；先审查依赖与有效域，再比较向量API是否产生等价精度；循环只是少量控制或真正数据相关串行递推，不能用比例高推出可向量化
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - Scalar比例阈值不跨架构使用
  - 没有PC/指令映射时只保留来源推导
analysis:
  mechanism_chain:
  - 本可按向量表达的元素处理使用逐元素Scalar访存或算术
  - Scalar重复地址计算与读写并占据指令分发
  - 其他流水不能及时获发工作并出现bubble
  objects_and_stages:
  - 热路径逐元素Scalar读写/算术及下游发射队列
  - kernel Scalar逐元素循环
  - Vector/Cube/MTE指令分发
  predictions:
  - 合法向量化应减少Scalar迭代次数与发射控制；这是prediction
  supporting_checks:
  - 区分Scalar算术、Load/Store、指令分发、ICache及等待
  - 先审查依赖与有效域，再比较向量API是否产生等价精度
  counter_checks:
  - 循环只是少量控制或真正数据相关串行递推，不能用比例高推出可向量化
  - Scalar高但主要spill或TilingData访存时应采用相应干预
  alternatives:
  - problem_id: problem.register_spill
    distinction: 寄存器溢出是额外LoadStore而非逐元素算法必需
    check: 查spill/stack和汇编PC归属
  - problem_id: problem.control_metadata_overhead
    distinction: mask/index等控制可外提，不要求逐元素数据运算
    check: 定位热区是数据处理还是重复元数据
  actions:
  - action_id: action.vectorize_scalar_loop
    intervention: 把满足等价语义的逐元素Scalar数据处理改为批量Vector操作
    requirements:
    - symptom.profile.scalar_hot=true
    - symptom.source.scalar_element_loop=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - UB暂存、mask、尾处理及alias限制
    - 向量API可能采用不同舍入或异常值行为
  limits:
  - Scalar比例阈值不跨架构使用
  - 没有PC/指令映射时只保留来源推导
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 标量逐元素热循环

## 对象、阶段与适用域

- 热路径逐元素Scalar读写/算术及下游发射队列
- kernel Scalar逐元素循环
- Vector/Cube/MTE指令分发

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 本可按向量表达的元素处理使用逐元素Scalar访存或算术
- Scalar重复地址计算与读写并占据指令分发
- 其他流水不能及时获发工作并出现bubble

## 预测、支持检查与反证

- 合法向量化应减少Scalar迭代次数与发射控制；这是prediction
- 区分Scalar算术、Load/Store、指令分发、ICache及等待
- 先审查依赖与有效域，再比较向量API是否产生等价精度
- 循环只是少量控制或真正数据相关串行递推，不能用比例高推出可向量化
- Scalar高但主要spill或TilingData访存时应采用相应干预

## 具体替代解释

- problem.register_spill：寄存器溢出是额外LoadStore而非逐元素算法必需；检查：查spill/stack和汇编PC归属
- problem.control_metadata_overhead：mask/index等控制可外提，不要求逐元素数据运算；检查：定位热区是数据处理还是重复元数据

## 候选动作与成本

action.vectorize_scalar_loop：把满足等价语义的逐元素Scalar数据处理改为批量Vector操作。

原硬前提：symptom.profile.scalar_hot=true；symptom.source.scalar_element_loop=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- UB暂存、mask、尾处理及alias限制
- 向量API可能采用不同舍入或异常值行为

## 限制与缺口

- Scalar比例阈值不跨架构使用
- 没有PC/指令映射时只保留来源推导
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：标量逐元素热循环；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### mechanism_1 [mechanism_inference]

本可按向量表达的元素处理使用逐元素Scalar访存或算术

来源索引：1, 2, 3, 4, 5, 6, 7。限制：Scalar比例阈值不跨架构使用；没有PC/指令映射时只保留来源推导

### mechanism_2 [mechanism_inference]

Scalar重复地址计算与读写并占据指令分发

来源索引：1, 2, 3, 4, 5, 6, 7。限制：Scalar比例阈值不跨架构使用；没有PC/指令映射时只保留来源推导

### mechanism_3 [mechanism_inference]

其他流水不能及时获发工作并出现bubble

来源索引：1, 2, 3, 4, 5, 6, 7。限制：Scalar比例阈值不跨架构使用；没有PC/指令映射时只保留来源推导

### prediction_1 [mechanism_inference]

合法向量化应减少Scalar迭代次数与发射控制；这是prediction

来源索引：1, 2, 3, 4, 5, 6, 7。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

区分Scalar算术、Load/Store、指令分发、ICache及等待

来源索引：1, 2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

先审查依赖与有效域，再比较向量API是否产生等价精度

来源索引：1, 2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

循环只是少量控制或真正数据相关串行递推，不能用比例高推出可向量化

来源索引：1, 2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

Scalar高但主要spill或TilingData访存时应采用相应干预

来源索引：1, 2, 3, 4, 5, 6, 7。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.register_spill：寄存器溢出是额外LoadStore而非逐元素算法必需；检查：查spill/stack和汇编PC归属

来源索引：1, 2, 3, 4, 5, 6, 7。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.control_metadata_overhead：mask/index等控制可外提，不要求逐元素数据运算；检查：定位热区是数据处理还是重复元数据

来源索引：1, 2, 3, 4, 5, 6, 7。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

把满足等价语义的逐元素Scalar数据处理改为批量Vector操作。代价：UB暂存、mask、尾处理及alias限制；向量API可能采用不同舍入或异常值行为

来源索引：1, 2, 3, 4, 5, 6, 7。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
