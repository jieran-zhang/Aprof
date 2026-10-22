---
schema_version: aprof.diagnosis-record/v1
id: action.software_pipeline_stages
kind: action
version: 1.2.0
status: active
title: 重排软件流水阶段
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  original_path: skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  lines:
  - 17
  - 30
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:0ddacaf1380e88c73e90e584cab87eae3ed42968a03b49110ab1d3ce6737a98e
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 5
  - 7
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:28ffa9d76883d46d4c3115e15e7b37b63974e9d8ce9469a003250d37dd2eb8e3
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 52
  - 80
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:45711f60b851ff9d3c3805e3a92d835cdee2c5465c506208beffbd197569abb9
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 121
  - 134
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:e10bdb71a109baa5e1f6383282f76aaa1b3077058647107df56c2939a6389526
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
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 重排软件流水阶段
preconditions:
- fact: symptom.source.serial_queue_or_event_order
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
- fact: constraint.dependency_lifetime
  state: true
invariants:
- 算子语义与精度要求保持
- 有效写回无重叠且覆盖完整
- 资源与依赖约束经核验
expected_effect: 合法预取/计算/写回重排可能缩短稳态关键路径；短任务、单tile、最慢阶段不变或额外buffer成本会限制收益。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
slots:
- name: target
  kind: object
  description: 多个tile的CopyIn/Compute/CopyOut及其buffer事件链
  required: true
- name: stage
  kind: stage
  description: kernel预取序言；稳态tile循环；排空尾声
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
  text: '原种子：重排软件流水阶段；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_mm_pipe
  text: arch22 MatMul文档把同buffer逐K搬入装载计算与流水串行联系，要求事件、容量、循环数和高阶API内部流水一并核对。
  basis: source_statement
  source_indexes:
  - 1
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
- id: source_init
  text: InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。
  basis: source_statement
  source_indexes:
  - 6
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  review_status: reviewed
  limitations:
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
- id: costs
  text: 更多物理buffer和事件ID；增加序言/尾声与尾块分支复杂度，短任务可能付不起成本
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 多个tile/阶段之间存在可重叠的独立工作，producer/consumer事件与buffer生命周期已完整证明；新增深度/序言尾声与容量合法。 当前队列或事件的顺序是结构事实，不说明真实硬件上完全无重叠；高阶API内部流水需单独考虑。
    合法预取/计算/写回重排可能缩短稳态关键路径；短任务、单tile、最慢阶段不变或额外buffer成本会限制收益。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 把timeline按tile而非聚合比例展开，检查首轮预置和末轮释放；核对双buffer是否物理独立及容量能同时容纳；稳定同对象窗口已持续重叠，反证完全串行解释
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
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
  effect: 为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环；预期变化仅为prediction：合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction
  costs:
  - 更多物理buffer和事件ID
  - 增加序言/尾声与尾块分支复杂度，短任务可能付不起成本
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 重排软件流水阶段

## 变换与作用对象

为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环。

多个tile的CopyIn/Compute/CopyOut及其buffer事件链；阶段：kernel预取序言；稳态tile循环；排空尾声。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

多个tile/阶段之间存在可重叠的独立工作，producer/consumer事件与buffer生命周期已完整证明；新增深度/序言尾声与容量合法。

- `symptom.source.serial_queue_or_event_order=true`：当前队列或事件的顺序是结构事实，不说明真实硬件上完全无重叠；高阶API内部流水需单独考虑。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。
- `constraint.dependency_lifetime=true`：所有producer/consumer、异步完成、释放/覆盖/复用边界真实合法；不能把等待可能慢当成可删依赖。

不变量：算子语义与精度要求保持；有效写回无重叠且覆盖完整；资源与依赖约束经核验。

## 性能假设、比较与补证据

当前队列或事件的顺序是结构事实，不说明真实硬件上完全无重叠；高阶API内部流水需单独考虑。

合法预取/计算/写回重排可能缩短稳态关键路径；短任务、单tile、最慢阶段不变或额外buffer成本会限制收益。

以下旧门槛作为性能/选择线索保留，不再与实施安全混用；期望false也原样保留：

- `symptom.profile.overlap_low=true`：低重叠是性能假设/判别依据，依赖及生命周期正确才是重排的实施安全条件。

1. 画原事件DAG并统计tile数、每阶段工作量与buffer峰值，推导至少一个合法重叠窗口和序言/尾声成本。
2. 已有trace可验证空洞；无trace时可据明确串行依赖提出试验，不能把double buffer声明等同重叠已发生。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环；预期变化仅为prediction：合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction

- 更多物理buffer和事件ID
- 增加序言/尾声与尾块分支复杂度，短任务可能付不起成本

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- num=2不等于实际重叠成立
- 不复制来源80%等重叠率或收益为目标承诺

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：重排软件流水阶段；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_mm_pipe [source_statement]

arch22 MatMul文档把同buffer逐K搬入装载计算与流水串行联系，要求事件、容量、循环数和高阶API内部流水一并核对。

来源索引：1, 2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_double [source_statement]

双缓冲文档要求可重叠预取结构、容量和事件闭合；全载单轮或过度同步时增缓冲可能无收益。

来源索引：4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_init [source_statement]

InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。

来源索引：6。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环

来源索引：1, 2, 3, 4, 5, 6。限制：num=2不等于实际重叠成立；不复制来源80%等重叠率或收益为目标承诺

### costs [mechanism_inference]

更多物理buffer和事件ID；增加序言/尾声与尾块分支复杂度，短任务可能付不起成本

来源索引：1, 2, 3, 4, 5, 6。限制：代价需要绑定具体候选量化，尚无本任务收益


### condition_separation [mechanism_inference]

多个tile/阶段之间存在可重叠的独立工作，producer/consumer事件与buffer生命周期已完整证明；新增深度/序言尾声与容量合法。 当前队列或事件的顺序是结构事实，不说明真实硬件上完全无重叠；高阶API内部流水需单独考虑。 合法预取/计算/写回重排可能缩短稳态关键路径；短任务、单tile、最慢阶段不变或额外buffer成本会限制收益。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。

## v0006 选择与语义边界

有队列或多个 buffer 不等于已形成可重叠的 producer/consumer 时间区间。选择时指出当前实际搬入、计算、搬出、等待及释放的顺序，比较 tile×槽位的峰值容量和尾部成本。缺时间数据可据源码依赖提出假设，但不得宣称已经重叠或处于关键路径；跨 owner/同步拓扑变更仍需 C2。

此段为基于既有变换语义的维护归纳，不新增上游性能声明、不放宽 preconditions，也不将当前任务的性能 unknown 改成 true。
