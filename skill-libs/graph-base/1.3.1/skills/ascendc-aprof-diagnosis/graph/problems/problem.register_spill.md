---
schema_version: aprof.diagnosis-record/v1
id: problem.register_spill
kind: problem
version: 1.1.0
status: active
title: 寄存器压力引发 spill
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
mechanism: 动态索引、大对象、取地址或过长生存期增加寄存器分配压力 → 编译器把部分值保存到栈/内存并在热区重载 → 非算法必要LoadStore与依赖增加关键路径
alternatives:
- problem.control_metadata_overhead：元数据重复读取可能无需寄存器溢出；检查：看栈偏移、编译报告与字段地址
- problem.onchip_capacity_pressure：寄存器/栈与UB/L1容量独立；检查：使用不同资源账本与报告
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
  text: '原种子：寄存器压力引发 spill；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 动态索引、大对象、取地址或过长生存期增加寄存器分配压力
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
- id: mechanism_2
  text: 编译器把部分值保存到栈/内存并在热区重载
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
- id: mechanism_3
  text: 非算法必要LoadStore与依赖增加关键路径
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
- id: prediction_1
  text: 缩短生存期或减少取地址可能减少spill；编译结果决定是否成立，属prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 先把必要GM标量读取、成员解引用与实际spill分开
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 保持编译配置比较报告及热PC，不能把所有LoadStore统称spill
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 生成物无spill且LoadStore均有算法来源，反证实际spill机制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 仅有局部变量多或结构体大不足以认定spill
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.control_metadata_overhead：元数据重复读取可能无需寄存器溢出；检查：看栈偏移、编译报告与字段地址
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.onchip_capacity_pressure：寄存器/栈与UB/L1容量独立；检查：使用不同资源账本与报告
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 缩短标量变量生存期、减少不必要取地址或拆分热区对象。代价：重计算可能增加算术量；拆分与展开改变代码体积/ICache压力
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 先把必要GM标量读取、成员解引用与实际spill分开；保持编译配置比较报告及热PC，不能把所有LoadStore统称spill；生成物无spill且LoadStore均有算法来源，反证实际spill机制
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
analysis:
  mechanism_chain:
  - 动态索引、大对象、取地址或过长生存期增加寄存器分配压力
  - 编译器把部分值保存到栈/内存并在热区重载
  - 非算法必要LoadStore与依赖增加关键路径
  objects_and_stages:
  - 指定编译配置下Scalar寄存器存活集合及栈/LoadStore指令
  - kernel热路径编译
  - Scalar寄存器分配与执行
  predictions:
  - 缩短生存期或减少取地址可能减少spill；编译结果决定是否成立，属prediction
  supporting_checks:
  - 先把必要GM标量读取、成员解引用与实际spill分开
  - 保持编译配置比较报告及热PC，不能把所有LoadStore统称spill
  counter_checks:
  - 生成物无spill且LoadStore均有算法来源，反证实际spill机制
  - 仅有局部变量多或结构体大不足以认定spill
  alternatives:
  - problem_id: problem.control_metadata_overhead
    distinction: 元数据重复读取可能无需寄存器溢出
    check: 看栈偏移、编译报告与字段地址
  - problem_id: problem.onchip_capacity_pressure
    distinction: 寄存器/栈与UB/L1容量独立
    check: 使用不同资源账本与报告
  actions:
  - action_id: action.shorten_scalar_lifetimes
    intervention: 缩短标量变量生存期、减少不必要取地址或拆分热区对象
    requirements:
    - symptom.source.register_spill=true
    - constraint.compiler_report=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 重计算可能增加算术量
    - 拆分与展开改变代码体积/ICache压力
  limits:
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 寄存器压力引发 spill

## 对象、阶段与适用域

- 指定编译配置下Scalar寄存器存活集合及栈/LoadStore指令
- kernel热路径编译
- Scalar寄存器分配与执行

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 动态索引、大对象、取地址或过长生存期增加寄存器分配压力
- 编译器把部分值保存到栈/内存并在热区重载
- 非算法必要LoadStore与依赖增加关键路径

## 预测、支持检查与反证

- 缩短生存期或减少取地址可能减少spill；编译结果决定是否成立，属prediction
- 先把必要GM标量读取、成员解引用与实际spill分开
- 保持编译配置比较报告及热PC，不能把所有LoadStore统称spill
- 生成物无spill且LoadStore均有算法来源，反证实际spill机制
- 仅有局部变量多或结构体大不足以认定spill

## 具体替代解释

- problem.control_metadata_overhead：元数据重复读取可能无需寄存器溢出；检查：看栈偏移、编译报告与字段地址
- problem.onchip_capacity_pressure：寄存器/栈与UB/L1容量独立；检查：使用不同资源账本与报告

## 候选动作与成本

action.shorten_scalar_lifetimes：缩短标量变量生存期、减少不必要取地址或拆分热区对象。

原硬前提：symptom.source.register_spill=true；constraint.compiler_report=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 重计算可能增加算术量
- 拆分与展开改变代码体积/ICache压力

## 限制与缺口

- 编译器版本和优化选项改变结论，需绑定artifact
- 源码审读不声称已证实spill
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：寄存器压力引发 spill；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_scalar [source_statement]

标量编码原则讨论动态数组寻址、别名、变量存活期和热循环内对象构造对Load/Store与寄存器分配的影响。

来源索引：1, 2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_scalar_guide [source_statement]

Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。

来源索引：4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### mechanism_1 [mechanism_inference]

动态索引、大对象、取地址或过长生存期增加寄存器分配压力

来源索引：1, 2, 3, 4。限制：编译器版本和优化选项改变结论，需绑定artifact；源码审读不声称已证实spill

### mechanism_2 [mechanism_inference]

编译器把部分值保存到栈/内存并在热区重载

来源索引：1, 2, 3, 4。限制：编译器版本和优化选项改变结论，需绑定artifact；源码审读不声称已证实spill

### mechanism_3 [mechanism_inference]

非算法必要LoadStore与依赖增加关键路径

来源索引：1, 2, 3, 4。限制：编译器版本和优化选项改变结论，需绑定artifact；源码审读不声称已证实spill

### prediction_1 [mechanism_inference]

缩短生存期或减少取地址可能减少spill；编译结果决定是否成立，属prediction

来源索引：1, 2, 3, 4。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

先把必要GM标量读取、成员解引用与实际spill分开

来源索引：1, 2, 3, 4。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

保持编译配置比较报告及热PC，不能把所有LoadStore统称spill

来源索引：1, 2, 3, 4。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

生成物无spill且LoadStore均有算法来源，反证实际spill机制

来源索引：1, 2, 3, 4。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

仅有局部变量多或结构体大不足以认定spill

来源索引：1, 2, 3, 4。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.control_metadata_overhead：元数据重复读取可能无需寄存器溢出；检查：看栈偏移、编译报告与字段地址

来源索引：1, 2, 3, 4。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.onchip_capacity_pressure：寄存器/栈与UB/L1容量独立；检查：使用不同资源账本与报告

来源索引：1, 2, 3, 4。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

缩短标量变量生存期、减少不必要取地址或拆分热区对象。代价：重计算可能增加算术量；拆分与展开改变代码体积/ICache压力

来源索引：1, 2, 3, 4。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
