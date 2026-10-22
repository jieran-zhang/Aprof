---
schema_version: aprof.diagnosis-record/v1
id: problem.vector_api_fragmentation
kind: problem
version: 1.1.0
status: active
title: Vector 调用碎片化
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
  - 59
  - 72
  sha256: sha256:9bf71febdfee0429bc107731ac339a59941e55f0aeed27cd0030a4cd1ec5aaa2
  excerpt_sha256: sha256:1ea72314f54681360c31f9fed51427b85eb98c17bb83cbf524d8ef3b1a147faa
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
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 40
  sha256: sha256:0de631e061a2e005d01aaf2efe0076a9e2adb3287edf1d1e96dd515ab919a256
  excerpt_sha256: sha256:d7c691d2216b08e98f944e42db95c3e223e5d1515796094c4fcbaddc8d5e7a8c
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
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 可批处理的Vector工作被拆成大量小count/repeat调用 → 每次重复mask/repeat和指令发射控制 → 有效lane利用偏低并增加Scalar与Vector固定开销
alternatives:
- problem.tail_slow_path：尾慢只绑定尾分支，碎片化也可发生在主体；检查：分开统计主体/尾API分布
- problem.ub_bank_conflict：冲突拉长周期但不要求API粒度小；检查：固定API数量比较冲突和周期
slots:
- name: target
  kind: object
  description: 同一有效元素域上的Vector API序列、repeat和mask分布
  required: true
- name: stage
  kind: stage
  description: kernel Vector发射与尾处理
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
  text: '原种子：Vector 调用碎片化；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_vector
  text: Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。
  basis: source_statement
  source_indexes:
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_mask
  text: SetVectorMask为向量执行配置掩码；具体产品和接口形式须以该固定修订及目标SDK核对。
  basis: source_statement
  source_indexes:
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_scalar_guide
  text: Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。
  basis: source_statement
  source_indexes:
  - 5
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: mechanism_1
  text: 可批处理的Vector工作被拆成大量小count/repeat调用
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
- id: mechanism_2
  text: 每次重复mask/repeat和指令发射控制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
- id: mechanism_3
  text: 有效lane利用偏低并增加Scalar与Vector固定开销
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
- id: prediction_1
  text: 合法批量表达应减少API和控制次数，未必改变必要算术量；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 按dtype与有效mask计有效元素而非把repeat数直接当利用率
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 区分尾部必要小调用、分支依赖和不必要的主体碎片化
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 指令数合理但bank冲突高应查布局
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.tail_slow_path：尾慢只绑定尾分支，碎片化也可发生在主体；检查：分开统计主体/尾API分布
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.ub_bank_conflict：冲突拉长周期但不要求API粒度小；检查：固定API数量比较冲突和周期
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 把语义和依赖允许的相邻Vector调用按count/repeat批量表达。代价：更长向量临时区生存期；合并受mask、地址跨度、参数上限及精度路径限制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按dtype与有效mask计有效元素而非把repeat数直接当利用率；区分尾部必要小调用、分支依赖和不必要的主体碎片化；小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
analysis:
  mechanism_chain:
  - 可批处理的Vector工作被拆成大量小count/repeat调用
  - 每次重复mask/repeat和指令发射控制
  - 有效lane利用偏低并增加Scalar与Vector固定开销
  objects_and_stages:
  - 同一有效元素域上的Vector API序列、repeat和mask分布
  - kernel Vector发射与尾处理
  predictions:
  - 合法批量表达应减少API和控制次数，未必改变必要算术量；这是prediction
  supporting_checks:
  - 按dtype与有效mask计有效元素而非把repeat数直接当利用率
  - 区分尾部必要小调用、分支依赖和不必要的主体碎片化
  counter_checks:
  - 小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
  - 指令数合理但bank冲突高应查布局
  alternatives:
  - problem_id: problem.tail_slow_path
    distinction: 尾慢只绑定尾分支，碎片化也可发生在主体
    check: 分开统计主体/尾API分布
  - problem_id: problem.ub_bank_conflict
    distinction: 冲突拉长周期但不要求API粒度小
    check: 固定API数量比较冲突和周期
  actions:
  - action_id: action.batch_vector_api_calls
    intervention: 把语义和依赖允许的相邻Vector调用按count/repeat批量表达
    requirements:
    - symptom.profile.vector_granularity_low=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 更长向量临时区生存期
    - 合并受mask、地址跨度、参数上限及精度路径限制
  limits:
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# Vector 调用碎片化

## 对象、阶段与适用域

- 同一有效元素域上的Vector API序列、repeat和mask分布
- kernel Vector发射与尾处理

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 可批处理的Vector工作被拆成大量小count/repeat调用
- 每次重复mask/repeat和指令发射控制
- 有效lane利用偏低并增加Scalar与Vector固定开销

## 预测、支持检查与反证

- 合法批量表达应减少API和控制次数，未必改变必要算术量；这是prediction
- 按dtype与有效mask计有效元素而非把repeat数直接当利用率
- 区分尾部必要小调用、分支依赖和不必要的主体碎片化
- 小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
- 指令数合理但bank冲突高应查布局

## 具体替代解释

- problem.tail_slow_path：尾慢只绑定尾分支，碎片化也可发生在主体；检查：分开统计主体/尾API分布
- problem.ub_bank_conflict：冲突拉长周期但不要求API粒度小；检查：固定API数量比较冲突和周期

## 候选动作与成本

action.batch_vector_api_calls：把语义和依赖允许的相邻Vector调用按count/repeat批量表达。

原硬前提：symptom.profile.vector_granularity_low=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 更长向量临时区生存期
- 合并受mask、地址跨度、参数上限及精度路径限制

## 限制与缺口

- API理论利用率必须由目标指令和dtype推导
- 没有自动extractor，本轮不声称已采样到repeat分布
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：Vector 调用碎片化；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_vector [source_statement]

Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。

来源索引：1, 2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mask [source_statement]

SetVectorMask为向量执行配置掩码；具体产品和接口形式须以该固定修订及目标SDK核对。

来源索引：4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_scalar_guide [source_statement]

Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。

来源索引：5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### mechanism_1 [mechanism_inference]

可批处理的Vector工作被拆成大量小count/repeat调用

来源索引：1, 2, 3, 4, 5。限制：API理论利用率必须由目标指令和dtype推导；没有自动extractor，本轮不声称已采样到repeat分布

### mechanism_2 [mechanism_inference]

每次重复mask/repeat和指令发射控制

来源索引：1, 2, 3, 4, 5。限制：API理论利用率必须由目标指令和dtype推导；没有自动extractor，本轮不声称已采样到repeat分布

### mechanism_3 [mechanism_inference]

有效lane利用偏低并增加Scalar与Vector固定开销

来源索引：1, 2, 3, 4, 5。限制：API理论利用率必须由目标指令和dtype推导；没有自动extractor，本轮不声称已采样到repeat分布

### prediction_1 [mechanism_inference]

合法批量表达应减少API和控制次数，未必改变必要算术量；这是prediction

来源索引：1, 2, 3, 4, 5。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

按dtype与有效mask计有效元素而非把repeat数直接当利用率

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

区分尾部必要小调用、分支依赖和不必要的主体碎片化

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

指令数合理但bank冲突高应查布局

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.tail_slow_path：尾慢只绑定尾分支，碎片化也可发生在主体；检查：分开统计主体/尾API分布

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.ub_bank_conflict：冲突拉长周期但不要求API粒度小；检查：固定API数量比较冲突和周期

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

把语义和依赖允许的相邻Vector调用按count/repeat批量表达。代价：更长向量临时区生存期；合并受mask、地址跨度、参数上限及精度路径限制

来源索引：1, 2, 3, 4, 5。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
