---
schema_version: aprof.diagnosis-record/v1
id: action.stagger_resource_access
kind: action
version: 1.2.0
status: active
title: 错开冲突资源访问
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 71
  - 71
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:99b43c20006a11c2df3df1b50030607bc5a8d9c80a730f2fc3b329a4f38e0e0f
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch22/ub_bank_conflict.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch22/ub_bank_conflict.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 9
  - 62
  sha256: sha256:11c277b4ec0a5470a8b3ad2b6ed5564773e2ccc18e08a0ac07d9d625f44ef388
  excerpt_sha256: sha256:a23bcfc3bc41d3afa773ca14a7c606b26817286402407a68b96f653cee99b326
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 19
  - 46
  sha256: sha256:d097c7e2d7cd4b5473dfe5fb52a6c9bd05e71df8d15389545f1c2ff7c68dde78
  excerpt_sha256: sha256:d3920eeb4b4de9e9825bed4b1e64aa0dd2873d63403e80f09d69a444c98339bd
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch35/ub_resident_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 158
  - 172
  sha256: sha256:d097c7e2d7cd4b5473dfe5fb52a6c9bd05e71df8d15389545f1c2ff7c68dde78
  excerpt_sha256: sha256:596ea95b9ccca168b15a818fc0954785262653b5e14f933b33829f2a978a00de
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 80
  - 88
  sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
  excerpt_sha256: sha256:1d79f96e97f30651aaacf0bb67f2d3361b29c71e0ff8897ef5293dff65b215cc
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/double_buffer_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 230
  - 259
  sha256: sha256:142cc0055136ff3bc203672f4c4365cf4f09b41a175a7bfa1d89f3df3b2500ae
  excerpt_sha256: sha256:a9c18f7d1d57332297fa98ce0e4e675e13ee85a21a9ea765bf14882859ad7941
learning:
  bias: 0
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 错开冲突资源访问
preconditions:
- fact: symptom.source.transfer_compute_contention
  state: true
- fact: constraint.dependency_lifetime
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 错开访问可能降低冲突，也可能损失原有重叠并使总时间增加。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
slots:
- name: target
  kind: object
  description: 同一UB或片上通路上的并发MTE与Vector访问
  required: true
- name: stage
  kind: stage
  description: kernel搬运与计算重叠窗口
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
  text: '原种子：错开冲突资源访问；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_bank
  text: arch22文档按同一Repeat的并发读写及bank/group映射判断冲突，并明确不同芯片的规则有差异。
  basis: source_statement
  source_indexes:
  - 1
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_resident
  text: arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。
  basis: source_statement
  source_indexes:
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_double
  text: 双缓冲文档要求可重叠预取结构、容量和事件闭合；全载单轮或过度同步时增缓冲可能无收益。
  basis: source_statement
  source_indexes:
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 调整合法独立访问的发射相位、buffer布局或资源分担
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: gap
  limitations:
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: costs
  text: 可能牺牲重叠并增加总等待；更多buffer或padding会占用容量
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: gap
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: condition_separation
  text: 候选发射可在依赖许可的窗口内改相位，资源映射有当前目标依据；改变调度仍满足所有buffer寿命和事件。 同资源访问并存在重叠机会只是潜在竞争结构，不证明已发生资源争用。 错开访问可能降低冲突，也可能损失原有重叠并使总时间增加。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: gap
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 把Vector内部bank冲突与MTE并发冲突分开；检查冲突计数分母和实际重叠区间，比较总Task Duration；冲突计数缺失或仅见同时执行，不能确认争用
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
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
  effect: 调整合法独立访问的发射相位、buffer布局或资源分担；预期变化仅为prediction：改变独立访问的相位或资源布局可能降低冲突，但减少重叠也可能变慢；这是prediction
  costs:
  - 可能牺牲重叠并增加总等待
  - 更多buffer或padding会占用容量
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 错开冲突资源访问

## 变换与作用对象

调整合法独立访问的发射相位、buffer布局或资源分担。

同一UB或片上通路上的并发MTE与Vector访问；阶段：kernel搬运与计算重叠窗口。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

候选发射可在依赖许可的窗口内改相位，资源映射有当前目标依据；改变调度仍满足所有buffer寿命和事件。

- `symptom.source.transfer_compute_contention=true`：同资源访问并存在重叠机会只是潜在竞争结构，不证明已发生资源争用。
- `constraint.dependency_lifetime=true`：所有producer/consumer、异步完成、释放/覆盖/复用边界真实合法；不能把等待可能慢当成可删依赖。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。

不变量：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

## 性能假设、比较与补证据

同资源访问并存在重叠机会只是潜在竞争结构，不证明已发生资源争用。

错开访问可能降低冲突，也可能损失原有重叠并使总时间增加。

1. 根据目标资源映射与实际地址/依赖检查是否真共享资源，比较可调相位窗口及额外等待。
2. 没有争用计数时只记录资源竞争预测；资源映射未知先读对应平台文档，不能用其他代际映射补值。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

调整合法独立访问的发射相位、buffer布局或资源分担；预期变化仅为prediction：改变独立访问的相位或资源布局可能降低冲突，但减少重叠也可能变慢；这是prediction

- 可能牺牲重叠并增加总等待
- 更多buffer或padding会占用容量

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
- 目标计数器或通路语义未核对时保持假设

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：错开冲突资源访问；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_bank [source_statement]

arch22文档按同一Repeat的并发读写及bank/group映射判断冲突，并明确不同芯片的规则有差异。

来源索引：1。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_double [source_statement]

双缓冲文档要求可重叠预取结构、容量和事件闭合；全载单轮或过度同步时增缓冲可能无收益。

来源索引：4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

调整合法独立访问的发射相位、buffer布局或资源分担

来源索引：1, 2, 3, 4, 5。限制：来源对布局与流水耦合提供原理，未给本任务并发冲突实测；目标计数器或通路语义未核对时保持假设

### costs [mechanism_inference]

可能牺牲重叠并增加总等待；更多buffer或padding会占用容量

来源索引：1, 2, 3, 4, 5。限制：代价需要绑定具体候选量化，尚无本任务收益
## 待补证缺口

固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。


### condition_separation [mechanism_inference]

候选发射可在依赖许可的窗口内改相位，资源映射有当前目标依据；改变调度仍满足所有buffer寿命和事件。 同资源访问并存在重叠机会只是潜在竞争结构，不证明已发生资源争用。 错开访问可能降低冲突，也可能损失原有重叠并使总时间增加。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。
