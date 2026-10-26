---
schema_version: aprof.diagnosis-record/v1
id: action.restructure_broadcast
kind: action
version: 1.2.0
status: active
title: 调整广播分块和复用
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 90
  - 90
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:5b45f68f39db91d205aded22104d3541a355e714ce07a82e0d80a5fc1c059e36
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 68
  - 68
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:57f549afbd96c61a5daf7debee3ab166f2051707846c0b79e023e902b0d05dab
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/broadcast/patterns.md
  original_path: ops/ascendc-tiling-design/references/broadcast/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 9
  - 18
  sha256: sha256:8b118ddbc4e70ada3debaf013838c8690abc85bb5f9d847d113ed2db40208830
  excerpt_sha256: sha256:5b96164d546a32ef2093bce71caf3c779d4f18b2266326ffceeda2b3de88ed58
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/broadcast/patterns.md
  original_path: ops/ascendc-tiling-design/references/broadcast/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 52
  - 82
  sha256: sha256:8b118ddbc4e70ada3debaf013838c8690abc85bb5f9d847d113ed2db40208830
  excerpt_sha256: sha256:4d475886f86ed85a22e839908359ce5326af94cd59de4fba6dd119f991c18945
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/broadcast/patterns.md
  original_path: ops/ascendc-tiling-design/references/broadcast/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 133
  - 141
  sha256: sha256:8b118ddbc4e70ada3debaf013838c8690abc85bb5f9d847d113ed2db40208830
  excerpt_sha256: sha256:0180281f8bb1668472247bd7c89726831dc136d53c064275653b31301a7b7df8
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/broadcast/ub-broadcast.md
  original_path: ops/ascendc-tiling-design/references/broadcast/ub-broadcast.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 1
  - 5
  sha256: sha256:4aa3bffcf13401bfa2e2f2d13525a23bb107cf7ebf50f900db54bb08dccaa6ab
  excerpt_sha256: sha256:9d2e7004b33b7f6fb49262f6a0a20efaa5156a81a37816f16270e3097f0c5bf5
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/broadcast/ub-broadcast.md
  original_path: ops/ascendc-tiling-design/references/broadcast/ub-broadcast.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 20
  - 44
  sha256: sha256:4aa3bffcf13401bfa2e2f2d13525a23bb107cf7ebf50f900db54bb08dccaa6ab
  excerpt_sha256: sha256:3d1a8007d85f0b4f688f448f0a93f5f31c46242f6e5d47edf59bd757f81c8c54
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/patterns.md
  original_path: ops/ascendc-tiling-design/references/reduction/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 73
  - 104
  sha256: sha256:9b8d774662fadf2fc4db38e48bd4124974d27a8ad7a6feac73a1ef55937fdcd8
  excerpt_sha256: sha256:9baea4b440a0b3ce9c7719a9e74012539d34b1649469265a2ed98e507551f3ab
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/patterns.md
  original_path: ops/ascendc-tiling-design/references/reduction/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 111
  - 162
  sha256: sha256:9b8d774662fadf2fc4db38e48bd4124974d27a8ad7a6feac73a1ef55937fdcd8
  excerpt_sha256: sha256:39904e1a81868ebca6db9443186e9eb894a57ed613393eb29d7c658bb7f48dbf
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/patterns.md
  original_path: ops/ascendc-tiling-design/references/reduction/patterns.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 173
  - 201
  sha256: sha256:9b8d774662fadf2fc4db38e48bd4124974d27a8ad7a6feac73a1ef55937fdcd8
  excerpt_sha256: sha256:2ade8ca091c7c005ab583cb84c791064de79557ca91672421bcfc6bf8a6e2bdc
learning:
  bias: 0
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 调整广播分块和复用
preconditions:
- fact: symptom.source.broadcast_strategy_mismatch
  state: true
- fact: constraint.broadcast_semantics
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 重组广播轴或小输入复用可能减少重复读取/展开工作；新索引或UB展开也可能更贵。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
slots:
- name: target
  kind: object
  description: 具有广播轴零stride、连续内轴与多个输入的输出域
  required: true
- name: stage
  kind: stage
  description: host合轴与切分；kernel GM搬入、UB展开及计算
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
  text: '原种子：调整广播分块和复用；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  - 1
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_broadcast
  text: 广播路由先合并同类轴并计算零stride，按目标架构、尾轴连续性和重复读成本选择广播阶段。
  basis: source_statement
  source_indexes:
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_broadcast_static
  text: DAV_2201静态Broadcast对rank、axis和原始shape字节对齐有限制，搬入后的padding不能替代原始shape约束。
  basis: source_statement
  source_indexes:
  - 5
  - 6
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_reduction
  text: 归约路由按AR/ARA、R和可放入的行/列选择全载或切分，Group Reduce及全局归约引入partial与合并阶段。
  basis: source_statement
  source_indexes:
  - 7
  - 8
  - 9
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 在目标API支持下重组广播轴、输入复用或展开阶段
  basis: mechanism_inference
  source_indexes:
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  - 9
  review_status: reviewed
  limitations:
  - DAV_2201静态Broadcast与DAV_3510动态/NDDMA不可互代
  - 原始shape的约束必须保留，不能拿padding假满足
- id: costs
  text: UB展开结果和临时区可能增大；复杂索引/搬运路径及尾处理增加
  basis: mechanism_inference
  source_indexes:
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  - 9
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 已明确对齐shape、广播flag、零stride、输入值复用域及输出映射；目标API和临时区满足数值与容量。 现有路径未区分连续轴/重复输入是结构线索，mismatch不是已验证的错误策略。 重组广播轴或小输入复用可能减少重复读取/展开工作；新索引或UB展开也可能更贵。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 分别计算输出元素数和每输入唯一字节，不用输出字节当输入下界；按目标rank/axis/dtype与原始维度字节对齐核对可选API；同轴合并后已为高效逐元素路径或输入无复用需求时，不支持本项
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - DAV_2201静态Broadcast与DAV_3510动态/NDDMA不可互代
  - 原始shape的约束必须保留，不能拿padding假满足
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
  effect: 在目标API支持下重组广播轴、输入复用或展开阶段；预期变化仅为prediction：合法改广播阶段或复用小输入可能减少重复读，UB临时区可能增加；这是prediction
  costs:
  - UB展开结果和临时区可能增大
  - 复杂索引/搬运路径及尾处理增加
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 调整广播分块和复用

## 变换与作用对象

在目标API支持下重组广播轴、输入复用或展开阶段。

具有广播轴零stride、连续内轴与多个输入的输出域；阶段：host合轴与切分；kernel GM搬入、UB展开及计算。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

已明确对齐shape、广播flag、零stride、输入值复用域及输出映射；目标API和临时区满足数值与容量。

- `symptom.source.broadcast_strategy_mismatch=true`：现有路径未区分连续轴/重复输入是结构线索，mismatch不是已验证的错误策略。
- `constraint.broadcast_semantics=true`：shape对齐、广播轴、零stride及输入值不变范围明确，输出映射与数值合法。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。

不变量：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

## 性能假设、比较与补证据

现有路径未区分连续轴/重复输入是结构线索，mismatch不是已验证的错误策略。

重组广播轴或小输入复用可能减少重复读取/展开工作；新索引或UB展开也可能更贵。

1. 按每个输入的广播掩码/stride、唯一字节和重复次数计算成本，先选择来源匹配的广播形态。
2. 对比GM到UB与UB内部广播位置及API支持；缺PMU不阻止基于明确广播结构的方案分析。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

在目标API支持下重组广播轴、输入复用或展开阶段；预期变化仅为prediction：合法改广播阶段或复用小输入可能减少重复读，UB临时区可能增加；这是prediction

- UB展开结果和临时区可能增大
- 复杂索引/搬运路径及尾处理增加

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- DAV_2201静态Broadcast与DAV_3510动态/NDDMA不可互代
- 原始shape的约束必须保留，不能拿padding假满足

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：调整广播分块和复用；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_broadcast [source_statement]

广播路由先合并同类轴并计算零stride，按目标架构、尾轴连续性和重复读成本选择广播阶段。

来源索引：2, 3, 4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_broadcast_static [source_statement]

DAV_2201静态Broadcast对rank、axis和原始shape字节对齐有限制，搬入后的padding不能替代原始shape约束。

来源索引：5, 6。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_reduction [source_statement]

归约路由按AR/ARA、R和可放入的行/列选择全载或切分，Group Reduce及全局归约引入partial与合并阶段。

来源索引：7, 8, 9。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

在目标API支持下重组广播轴、输入复用或展开阶段

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：DAV_2201静态Broadcast与DAV_3510动态/NDDMA不可互代；原始shape的约束必须保留，不能拿padding假满足

### costs [mechanism_inference]

UB展开结果和临时区可能增大；复杂索引/搬运路径及尾处理增加

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：代价需要绑定具体候选量化，尚无本任务收益


### condition_separation [mechanism_inference]

已明确对齐shape、广播flag、零stride、输入值复用域及输出映射；目标API和临时区满足数值与容量。 现有路径未区分连续轴/重复输入是结构线索，mismatch不是已验证的错误策略。 重组广播轴或小输入复用可能减少重复读取/展开工作；新索引或UB展开也可能更贵。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。
