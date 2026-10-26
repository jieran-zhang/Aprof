---
schema_version: aprof.diagnosis-record/v1
id: problem.redundant_cast
kind: problem
version: 1.1.0
status: active
title: 重复类型转换
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 65
  - 65
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:fc6046ab557edc2427920fd72df3a792b7640585fc670416312cc9c0948147c9
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 61
  - 61
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:7a330c74b26bff1596853d8e04a44dfeaf9e8a9fa3e8ff1249e143fb7f406b37
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/type_conversion/Cast.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 40
  sha256: sha256:a41d8e8b10d541452de9c4542158d0bba6bc53f15e68c3d1d929712856a11f12
  excerpt_sha256: sha256:85aa20463c85a25f635449f07437ced5ba884752304c723589b35f5de2cbd8a4
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  original_path: ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 7
  - 31
  sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
  excerpt_sha256: sha256:4ab728639a7253d7c18577a2d3cce67a90a28d160fcc90be30e4f24501cf37b2
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  original_path: ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 43
  - 50
  sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
  excerpt_sha256: sha256:67d6c06531f1ce7e2dd5f726b793b88708cb6760b7e0039bcfb9e68c7ce31dd3
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  original_path: ops/ops-design-paradigms/references/paradigms/reduction/generic/liveness-fusion.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 53
  - 92
  sha256: sha256:08f91ab6c5846b60435aa9e70fed185f0947718604320544a99dbd8132ba8477
  excerpt_sha256: sha256:9a78768af62323a9c9e8b54b261df2e1b8db85985a1b970261b8f068a19cda46
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
mechanism: 局部链在相邻阶段反复宽窄往返转换 → 部分转换不承担必须的数值边界或消费者dtype契约 → 额外Cast指令、临时buffer与控制增加成本
alternatives:
- problem.control_metadata_overhead：转换指令成本与其参数/控制成本可共存；检查：按PC拆Cast和Scalar设置
- problem.onchip_capacity_pressure：宽dtype延长生存期可增容量，删Cast未必省峰值；检查：按实际dtype逐阶段核算
slots:
- name: target
  kind: object
  description: 局部计算链中有明确dtype、舍入模式和精度边界的转换
  required: true
- name: stage
  kind: stage
  description: kernel载入扩位；中间计算与缩位；最终输出转换
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
  text: '原种子：重复类型转换；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  - 1
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_cast
  text: Cast文档给出产品支持和转换接口，转换路径必须结合目标dtype和舍入要求核验。
  basis: source_statement
  source_indexes:
  - 2
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_liveness
  text: 存活分析文档要求沿计算链核算物理峰值，融合可能增加同时活着的输入和多消费者输出，必要时主动拆链。
  basis: source_statement
  source_indexes:
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_vector
  text: Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。
  basis: source_statement
  source_indexes:
  - 6
  - 7
  - 8
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: mechanism_1
  text: 局部链在相邻阶段反复宽窄往返转换
  basis: mechanism_inference
  source_indexes: &id001
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  review_status: reviewed
  limitations:
  - Cast产品及dtype支持按固定API文档核对
  - 必须保持原A的精度与语义前提，不能以时延替代精度
- id: mechanism_2
  text: 部分转换不承担必须的数值边界或消费者dtype契约
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - Cast产品及dtype支持按固定API文档核对
  - 必须保持原A的精度与语义前提，不能以时延替代精度
- id: mechanism_3
  text: 额外Cast指令、临时buffer与控制增加成本
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - Cast产品及dtype支持按固定API文档核对
  - 必须保持原A的精度与语义前提，不能以时延替代精度
- id: prediction_1
  text: 去掉经证明冗余的Cast或调整扩缩位位置可减少指令/临时区；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 测试/分析正常数、极值、NaN/Inf、舍入与溢出契约，禁止只比较普通随机值
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 看源API支持和实际生成指令，语法Cast不必然对应相同成本
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 中间缩位是算法定义或外部消费者要求时不能删除
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 双向Cast通常不互为恒等，缺数值等价证明时维持needs_evidence
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.control_metadata_overhead：转换指令成本与其参数/控制成本可共存；检查：按PC拆Cast和Scalar设置
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.onchip_capacity_pressure：宽dtype延长生存期可增容量，删Cast未必省峰值；检查：按实际dtype逐阶段核算
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界。代价：扩大中间dtype会增加容量/寄存器压力；更少转换可能改变舍入、饱和和异常值行为
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 测试/分析正常数、极值、NaN/Inf、舍入与溢出契约，禁止只比较普通随机值；看源API支持和实际生成指令，语法Cast不必然对应相同成本；中间缩位是算法定义或外部消费者要求时不能删除
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - Cast产品及dtype支持按固定API文档核对
  - 必须保持原A的精度与语义前提，不能以时延替代精度
analysis:
  mechanism_chain:
  - 局部链在相邻阶段反复宽窄往返转换
  - 部分转换不承担必须的数值边界或消费者dtype契约
  - 额外Cast指令、临时buffer与控制增加成本
  objects_and_stages:
  - 局部计算链中有明确dtype、舍入模式和精度边界的转换
  - kernel载入扩位
  - 中间计算与缩位
  - 最终输出转换
  predictions:
  - 去掉经证明冗余的Cast或调整扩缩位位置可减少指令/临时区；这是prediction
  supporting_checks:
  - 测试/分析正常数、极值、NaN/Inf、舍入与溢出契约，禁止只比较普通随机值
  - 看源API支持和实际生成指令，语法Cast不必然对应相同成本
  counter_checks:
  - 中间缩位是算法定义或外部消费者要求时不能删除
  - 双向Cast通常不互为恒等，缺数值等价证明时维持needs_evidence
  alternatives:
  - problem_id: problem.control_metadata_overhead
    distinction: 转换指令成本与其参数/控制成本可共存
    check: 按PC拆Cast和Scalar设置
  - problem_id: problem.onchip_capacity_pressure
    distinction: 宽dtype延长生存期可增容量，删Cast未必省峰值
    check: 按实际dtype逐阶段核算
  actions:
  - action_id: action.coalesce_cast
    intervention: 在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界
    requirements:
    - symptom.source.redundant_cast=true
    - constraint.precision=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 扩大中间dtype会增加容量/寄存器压力
    - 更少转换可能改变舍入、饱和和异常值行为
  limits:
  - Cast产品及dtype支持按固定API文档核对
  - 必须保持原A的精度与语义前提，不能以时延替代精度
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 重复类型转换

## 对象、阶段与适用域

- 局部计算链中有明确dtype、舍入模式和精度边界的转换
- kernel载入扩位
- 中间计算与缩位
- 最终输出转换

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 局部链在相邻阶段反复宽窄往返转换
- 部分转换不承担必须的数值边界或消费者dtype契约
- 额外Cast指令、临时buffer与控制增加成本

## 预测、支持检查与反证

- 去掉经证明冗余的Cast或调整扩缩位位置可减少指令/临时区；这是prediction
- 测试/分析正常数、极值、NaN/Inf、舍入与溢出契约，禁止只比较普通随机值
- 看源API支持和实际生成指令，语法Cast不必然对应相同成本
- 中间缩位是算法定义或外部消费者要求时不能删除
- 双向Cast通常不互为恒等，缺数值等价证明时维持needs_evidence

## 具体替代解释

- problem.control_metadata_overhead：转换指令成本与其参数/控制成本可共存；检查：按PC拆Cast和Scalar设置
- problem.onchip_capacity_pressure：宽dtype延长生存期可增容量，删Cast未必省峰值；检查：按实际dtype逐阶段核算

## 候选动作与成本

action.coalesce_cast：在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界。

原硬前提：symptom.source.redundant_cast=true；constraint.precision=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 扩大中间dtype会增加容量/寄存器压力
- 更少转换可能改变舍入、饱和和异常值行为

## 限制与缺口

- Cast产品及dtype支持按固定API文档核对
- 必须保持原A的精度与语义前提，不能以时延替代精度
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：重复类型转换；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_cast [source_statement]

Cast文档给出产品支持和转换接口，转换路径必须结合目标dtype和舍入要求核验。

来源索引：2。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_liveness [source_statement]

存活分析文档要求沿计算链核算物理峰值，融合可能增加同时活着的输入和多消费者输出，必要时主动拆链。

来源索引：3, 4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_vector [source_statement]

Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。

来源索引：6, 7, 8。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### mechanism_1 [mechanism_inference]

局部链在相邻阶段反复宽窄往返转换

来源索引：2, 3, 4, 5, 6, 7, 8。限制：Cast产品及dtype支持按固定API文档核对；必须保持原A的精度与语义前提，不能以时延替代精度

### mechanism_2 [mechanism_inference]

部分转换不承担必须的数值边界或消费者dtype契约

来源索引：2, 3, 4, 5, 6, 7, 8。限制：Cast产品及dtype支持按固定API文档核对；必须保持原A的精度与语义前提，不能以时延替代精度

### mechanism_3 [mechanism_inference]

额外Cast指令、临时buffer与控制增加成本

来源索引：2, 3, 4, 5, 6, 7, 8。限制：Cast产品及dtype支持按固定API文档核对；必须保持原A的精度与语义前提，不能以时延替代精度

### prediction_1 [mechanism_inference]

去掉经证明冗余的Cast或调整扩缩位位置可减少指令/临时区；这是prediction

来源索引：2, 3, 4, 5, 6, 7, 8。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

测试/分析正常数、极值、NaN/Inf、舍入与溢出契约，禁止只比较普通随机值

来源索引：2, 3, 4, 5, 6, 7, 8。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

看源API支持和实际生成指令，语法Cast不必然对应相同成本

来源索引：2, 3, 4, 5, 6, 7, 8。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

中间缩位是算法定义或外部消费者要求时不能删除

来源索引：2, 3, 4, 5, 6, 7, 8。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

双向Cast通常不互为恒等，缺数值等价证明时维持needs_evidence

来源索引：2, 3, 4, 5, 6, 7, 8。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.control_metadata_overhead：转换指令成本与其参数/控制成本可共存；检查：按PC拆Cast和Scalar设置

来源索引：2, 3, 4, 5, 6, 7, 8。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.onchip_capacity_pressure：宽dtype延长生存期可增容量，删Cast未必省峰值；检查：按实际dtype逐阶段核算

来源索引：2, 3, 4, 5, 6, 7, 8。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界。代价：扩大中间dtype会增加容量/寄存器压力；更少转换可能改变舍入、饱和和异常值行为

来源索引：2, 3, 4, 5, 6, 7, 8。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
