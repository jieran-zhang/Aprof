---
schema_version: aprof.diagnosis-record/v1
id: action.shorten_scalar_lifetimes
kind: action
version: 1.2.0
status: active
title: 缩短标量对象存活期
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 36
  - 36
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:7d686e034229907a1aa618783bf9a57377656b6b26806363f1a39ae44b8422d2
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
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/scalar/guide.md
  original_path: ops/ascendc-performance-best-practices/references/common/scalar/guide.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 4
  - 8
  sha256: sha256:1f9161d4bdd0ed256130213ce0e61598369c869b00ce28d54db38f5860536fdc
  excerpt_sha256: sha256:47193296d3dadc4f6cb6cf1c115a43b5e8378f6bccc04e275dac8a22b2a2093a
learning:
  bias: 0
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 缩短标量对象存活期
preconditions:
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
- fact: constraint.scalar_lifetime_legality
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 缩短活跃范围可能减少寄存器压力或spill，也可能增加重算和指令体积；编译器原本已处理时可能无收益。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
slots:
- name: target
  kind: object
  description: 指定编译配置下Scalar寄存器存活集合及栈/LoadStore指令
  required: true
- name: stage
  kind: stage
  description: kernel热路径编译；Scalar寄存器分配与执行
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
  text: '原种子：缩短标量对象存活期；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_scalar
  text: 标量编码原则讨论动态数组寻址、别名、变量存活期和热循环内对象构造对Load/Store与寄存器分配的影响。
  basis: source_statement
  source_indexes:
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_scalar_guide
  text: Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。
  basis: source_statement
  source_indexes:
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 缩短标量变量生存期、减少不必要取地址或拆分热区对象
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
- id: costs
  text: 重计算可能增加算术量；拆分与展开改变代码体积/ICache压力
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 变量定义/全部使用、别名/取地址/逃逸、编译地址空间和副作用已知；改写后值、可见性及执行依赖保持；不要求先观测到spill。 大对象或长存活是源码风险线索，不是spill事实；编译报告是判别资源与性能假设的证据。
    缩短活跃范围可能减少寄存器压力或spill，也可能增加重算和指令体积；编译器原本已处理时可能无收益。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 先把必要GM标量读取、成员解引用与实际spill分开；保持编译配置比较报告及热PC，不能把所有LoadStore统称spill；生成物无spill且LoadStore均有算法来源，反证实际spill机制
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
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
  effect: 缩短标量变量生存期、减少不必要取地址或拆分热区对象；预期变化仅为prediction：缩短生存期或减少取地址可能减少spill；编译结果决定是否成立，属prediction
  costs:
  - 重计算可能增加算术量
  - 拆分与展开改变代码体积/ICache压力
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 缩短标量对象存活期

## 变换与作用对象

缩短标量变量生存期、减少不必要取地址或拆分热区对象。

指定编译配置下Scalar寄存器存活集合及栈/LoadStore指令；阶段：kernel热路径编译；Scalar寄存器分配与执行。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

变量定义/全部使用、别名/取地址/逃逸、编译地址空间和副作用已知；改写后值、可见性及执行依赖保持；不要求先观测到spill。

- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。
- `constraint.scalar_lifetime_legality=true`：报告存在不是生命周期安全证明；新增可由源码、调用契约和必要编译语义证明的具体条件。

不变量：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

新增谓词 `constraint.scalar_lifetime_legality` 的证明范围：针对已绑定实现、目标对象和变换窗口，缩短标量/对象存活期后所有使用仍由正确值支配，别名/取地址/逃逸/异步访问及副作用可见性不变。

- 列出定义、全部读写使用、最后使用和控制流分支；重计算使用同一数值语义且不遗漏副作用。
- 检查取地址、引用、指针逃逸、对象成员与调用参数，不把仍被引用或异步消费的对象提前销毁/覆盖。
- 核对存储地址空间、对齐、构造析构或宏展开要求，保持ABI及跨函数执行契约。
- 标出新旧作用域及alias关系，对零/单循环和条件分支的初始化覆盖逐项证明。

具体未知条件：使用/别名/逃逸边界不完整或被不可见调用访问。；重计算副作用、数值顺序或对象生命周期契约尚未确认。。

## 性能假设、比较与补证据

大对象或长存活是源码风险线索，不是spill事实；编译报告是判别资源与性能假设的证据。

缩短活跃范围可能减少寄存器压力或spill，也可能增加重算和指令体积；编译器原本已处理时可能无收益。

以下旧门槛作为性能/选择线索保留，不再与实施安全混用；期望false也原样保留：

- `symptom.source.register_spill=true`：该S实际定义是大对象/长生存期等源码风险，非实际spill；安全生命周期改写不以已出现风险或spill为必要条件。
- `constraint.compiler_report=true`：编译报告用于判别spill、栈和活跃量，属于性能/资源归因证据；实施安全改由具体源码生命周期合法性证明，报告存在不能替代该证明。

1. 由源码画定义-最后使用和alias/escape关系，识别可缩短且不改变副作用的窗口并估算活跃量变化。
2. 优先用现有编译报告/反汇编判别spill、stack和CSE；不可得时保留可证结构与具体预测，不禁止合法试验，也不认定spill已存在。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

缩短标量变量生存期、减少不必要取地址或拆分热区对象；预期变化仅为prediction：缩短生存期或减少取地址可能减少spill；编译结果决定是否成立，属prediction

- 重计算可能增加算术量
- 拆分与展开改变代码体积/ICache压力

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- 编译器版本和优化选项改变结论，需绑定artifact
- 源码审读不声称已证实spill

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：缩短标量对象存活期；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_scalar [source_statement]

标量编码原则讨论动态数组寻址、别名、变量存活期和热循环内对象构造对Load/Store与寄存器分配的影响。

来源索引：1, 2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_scalar_guide [source_statement]

Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。

来源索引：4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

缩短标量变量生存期、减少不必要取地址或拆分热区对象

来源索引：1, 2, 3, 4。限制：编译器版本和优化选项改变结论，需绑定artifact；源码审读不声称已证实spill

### costs [mechanism_inference]

重计算可能增加算术量；拆分与展开改变代码体积/ICache压力

来源索引：1, 2, 3, 4。限制：代价需要绑定具体候选量化，尚无本任务收益


### condition_separation [mechanism_inference]

变量定义/全部使用、别名/取地址/逃逸、编译地址空间和副作用已知；改写后值、可见性及执行依赖保持；不要求先观测到spill。 大对象或长存活是源码风险线索，不是spill事实；编译报告是判别资源与性能假设的证据。 缩短活跃范围可能减少寄存器压力或spill，也可能增加重算和指令体积；编译器原本已处理时可能无收益。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。
