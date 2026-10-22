---
schema_version: aprof.diagnosis-record/v1
id: action.coalesce_contiguous_transfers
kind: action
version: 1.2.0
status: active
title: 合并连续小搬运
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/data-movement-optimization-strategies.md
  original_path: skills/aprof/optimization/references/data-movement-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  lines:
  - 15
  - 24
  sha256: sha256:5c3a68ff44e8f93f33ca3d6492c5b1894224e66b382e2e59fcb842b7e1086479
  excerpt_sha256: sha256:442645c8d750d1f3edee4654d63a5c17fa7465142b9a4e54f5c6334b143b7151
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 7
  - 10
  sha256: sha256:dbb672d9f6f872d02ba5a255ac9b1949595d8fa869efb174c27895da04560a38
  excerpt_sha256: sha256:5e467f037325364ca135631c4c9a41c7f69834af8d2348b1be493c82cdf5a820
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 45
  - 55
  sha256: sha256:dbb672d9f6f872d02ba5a255ac9b1949595d8fa869efb174c27895da04560a38
  excerpt_sha256: sha256:34fb85b54e7b505ed72fd234f9664cf45cab62643b24a4aed606925df8559689
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  original_path: ops/ascendc-performance-best-practices/references/common/arch22/datacopy_optimization_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 233
  - 251
  sha256: sha256:dbb672d9f6f872d02ba5a255ac9b1949595d8fa869efb174c27895da04560a38
  excerpt_sha256: sha256:00a813bbe2ea146de5a8703ee82bfb0014b8c70b92b498646c7cd450099c5737
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 145
  - 177
  sha256: sha256:7126d511236c3539b2710934c468c56500e39ac336531597a3360d6c74282cff
  excerpt_sha256: sha256:7b6fd467d0158bb6da05a6eee05102706b180cc2a4992bee560a24662c4a7c48
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  original_path: docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 97
  - 108
  sha256: sha256:36da88132f7d5f62484bc98896bd99577bcce25d71a84e21220731a557aea34d
  excerpt_sha256: sha256:e2ee07f2f75d3a3f11d1ba56e11c5cad9974e2e78bb6ce215cd610ef9d8c985d
learning:
  bias: 0
tags:
- data_movement
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 合并连续小搬运
preconditions:
- fact: symptom.source.inner_loop_copy
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 算子语义与精度要求保持
- 有效写回无重叠且覆盖完整
- 资源与依赖约束经核验
expected_effect: 合并可减少发射数；若原路径已充分流水或带宽占主导，时间收益可能小，UB峰值可能增加。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
slots:
- name: target
  kind: tensor
  description: 同一tensor切片的搬入块、DMA发射点及所属tile循环
  required: true
- name: stage
  kind: stage
  description: host计算tile和尾长；kernel内层CopyIn及等待
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
  text: '原种子：合并连续小搬运；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_copy
  text: 来源将批量合并搬运与减少DMA启动次数联系起来，并明确经验粒度阈值只针对原设备。
  basis: source_statement
  source_indexes:
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_copy_sample
  text: 公开搬运样例比较相同张量的多种分块，并把增大块后减少指令和循环开销列为解释；表中收益只属于该样例。
  basis: source_statement
  source_indexes:
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_init
  text: InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。
  basis: source_statement
  source_indexes:
  - 5
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
- id: costs
  text: 更大UB/L1暂存与更长buffer生命周期；可能减少可并行任务或改变流水预取距离
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 源/目标区间、stride单位、对齐、有效尾长和依赖完成点可证明可用目标API合并；容量与唯一输出保持合法。 循环内多次Copy是结构线索，必须另外检查相邻性，不能把任何内循环搬运都合并。 合并可减少发射数；若原路径已充分流水或带宽占主导，时间收益可能小，UB峰值可能增加。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加；把搬入、计算和等待按tile展开，检查是否有可合并的边界；大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
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
  effect: 合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度；预期变化仅为prediction：若仅合并合法相邻搬运，发射数应下降而算法有效字节不变；这是prediction；MTE比例可能仍高，不能用比例下降作为唯一成功标准
  costs:
  - 更大UB/L1暂存与更长buffer生命周期
  - 可能减少可并行任务或改变流水预取距离
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 合并连续小搬运

## 变换与作用对象

合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度。

同一tensor切片的搬入块、DMA发射点及所属tile循环；阶段：host计算tile和尾长；kernel内层CopyIn及等待。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

源/目标区间、stride单位、对齐、有效尾长和依赖完成点可证明可用目标API合并；容量与唯一输出保持合法。

- `symptom.source.inner_loop_copy=true`：循环内多次Copy是结构线索，必须另外检查相邻性，不能把任何内循环搬运都合并。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。

不变量：算子语义与精度要求保持；有效写回无重叠且覆盖完整；资源与依赖约束经核验。

## 性能假设、比较与补证据

循环内多次Copy是结构线索，必须另外检查相邻性，不能把任何内循环搬运都合并。

合并可减少发射数；若原路径已充分流水或带宽占主导，时间收益可能小，UB峰值可能增加。

以下旧门槛作为性能/选择线索保留，不再与实施安全混用；期望false也原样保留：

- `symptom.profile.mte_setup_dominated=true`：发射成本主导是待验证机制；相邻搬运是否可合并由地址、依赖和API范围证明。

1. 由地址式求每次有效字节和调用次数，证明合并后读写映射等价；结合固定来源API限制决定count/stride方案。
2. 区分“小搬运发射成本”与“总必要字节”预测；缺MTE setup计数不禁止已有合法连续段的实验。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度；预期变化仅为prediction：若仅合并合法相邻搬运，发射数应下降而算法有效字节不变；这是prediction；MTE比例可能仍高，不能用比例下降作为唯一成功标准

- 更大UB/L1暂存与更长buffer生命周期
- 可能减少可并行任务或改变流水预取距离

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
- 当前任务没有采集数据，不能把文档样例收益写为本任务收益

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：合并连续小搬运；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_copy [source_statement]

来源将批量合并搬运与减少DMA启动次数联系起来，并明确经验粒度阈值只针对原设备。

来源索引：1, 2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_copy_sample [source_statement]

公开搬运样例比较相同张量的多种分块，并把增大块后减少指令和循环开销列为解释；表中收益只属于该样例。

来源索引：4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_init [source_statement]

InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。

来源索引：5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度

来源索引：1, 2, 3, 4, 5。限制：来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据；当前任务没有采集数据，不能把文档样例收益写为本任务收益

### costs [mechanism_inference]

更大UB/L1暂存与更长buffer生命周期；可能减少可并行任务或改变流水预取距离

来源索引：1, 2, 3, 4, 5。限制：代价需要绑定具体候选量化，尚无本任务收益


### condition_separation [mechanism_inference]

源/目标区间、stride单位、对齐、有效尾长和依赖完成点可证明可用目标API合并；容量与唯一输出保持合法。 循环内多次Copy是结构线索，必须另外检查相邻性，不能把任何内循环搬运都合并。 合并可减少发射数；若原路径已充分流水或带宽占主导，时间收益可能小，UB峰值可能增加。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。
