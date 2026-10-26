---
schema_version: aprof.diagnosis-record/v1
id: action.coalesce_cast
kind: action
version: 1.2.0
status: active
title: 合并 Cast 与中间类型边界
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
transformation: 合并 Cast 与中间类型边界
preconditions:
- fact: symptom.source.redundant_cast
  state: true
- fact: constraint.precision
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 合法减少转换可能减少指令与临时区，但更宽中间值、不同指令路径或寄存器压力可抵消。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
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
  text: '原种子：合并 Cast 与中间类型边界；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: intervention
  text: 在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界
  basis: mechanism_inference
  source_indexes:
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
- id: costs
  text: 扩大中间dtype会增加容量/寄存器压力；更少转换可能改变舍入、饱和和异常值行为
  basis: mechanism_inference
  source_indexes:
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 完整数值契约、每步dtype/舍入/饱和/异常值语义和消费者明确；仅消除可证明等价的转换或移动合法边界。 宽窄往返Cast是结构事实，不说明Cast冗余或可以直接删除。 合法减少转换可能减少指令与临时区，但更宽中间值、不同指令路径或寄存器压力可抵消。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 测试/分析正常数、极值、NaN/Inf、舍入与溢出契约，禁止只比较普通随机值；看源API支持和实际生成指令，语法Cast不必然对应相同成本；中间缩位是算法定义或外部消费者要求时不能删除
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - Cast产品及dtype支持按固定API文档核对
  - 必须保持原A的精度与语义前提，不能以时延替代精度
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
  effect: 在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界；预期变化仅为prediction：去掉经证明冗余的Cast或调整扩缩位位置可减少指令/临时区；这是prediction
  costs:
  - 扩大中间dtype会增加容量/寄存器压力
  - 更少转换可能改变舍入、饱和和异常值行为
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 合并 Cast 与中间类型边界

## 变换与作用对象

在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界。

局部计算链中有明确dtype、舍入模式和精度边界的转换；阶段：kernel载入扩位；中间计算与缩位；最终输出转换。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

完整数值契约、每步dtype/舍入/饱和/异常值语义和消费者明确；仅消除可证明等价的转换或移动合法边界。

- `symptom.source.redundant_cast=true`：宽窄往返Cast是结构事实，不说明Cast冗余或可以直接删除。
- `constraint.precision=true`：Cast/中间dtype变化须保持已授权数值与异常值契约，不以可能加速放宽精度。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。

不变量：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

## 性能假设、比较与补证据

宽窄往返Cast是结构事实，不说明Cast冗余或可以直接删除。

合法减少转换可能减少指令与临时区，但更宽中间值、不同指令路径或寄存器压力可抵消。

1. 逐段展开表达式的dtype与round mode，用原oracle范围证明可删除边界，不把精度容忍当任意重排许可。
2. 比较转换调用次数、临时区峰值及预计新增宽类型工作；数值安全不明时只做分析，不实施。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界；预期变化仅为prediction：去掉经证明冗余的Cast或调整扩缩位位置可减少指令/临时区；这是prediction

- 扩大中间dtype会增加容量/寄存器压力
- 更少转换可能改变舍入、饱和和异常值行为

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- Cast产品及dtype支持按固定API文档核对
- 必须保持原A的精度与语义前提，不能以时延替代精度

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：合并 Cast 与中间类型边界；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### intervention [mechanism_inference]

在保留完整数值契约下合并转换或将扩位/缩位移到合法链边界

来源索引：2, 3, 4, 5, 6, 7, 8。限制：Cast产品及dtype支持按固定API文档核对；必须保持原A的精度与语义前提，不能以时延替代精度

### costs [mechanism_inference]

扩大中间dtype会增加容量/寄存器压力；更少转换可能改变舍入、饱和和异常值行为

来源索引：2, 3, 4, 5, 6, 7, 8。限制：代价需要绑定具体候选量化，尚无本任务收益


### condition_separation [mechanism_inference]

完整数值契约、每步dtype/舍入/饱和/异常值语义和消费者明确；仅消除可证明等价的转换或移动合法边界。 宽窄往返Cast是结构事实，不说明Cast冗余或可以直接删除。 合法减少转换可能减少指令与临时区，但更宽中间值、不同指令路径或寄存器压力可抵消。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。
