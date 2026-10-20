---
schema_version: aprof.diagnosis-record/v1
id: edge.action.register_spill
kind: edge
version: 1.1.0
status: active
title: problem.register_spill → action.shorten_scalar_lifetimes
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
  weight: 2
tags: []
seed_reason: 2 分：缩短对象存活期可能减少 spill，但实际寄存器分配由编译器决定，须重新核对报告。
relation: mitigated_by
from: problem.register_spill
to: action.shorten_scalar_lifetimes
conditions: []
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
  text: '原种子：problem.register_spill → action.shorten_scalar_lifetimes；原learning={"weight": 2}；2 分：缩短对象存活期可能减少 spill，但实际寄存器分配由编译器决定，须重新核对报告。'
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
- id: conditional_relation
  text: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，缩短标量变量生存期、减少不必要取地址或拆分热区对象才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果
  - joint_requirements是必要联合条件，不构成机制充分证据
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
- id: exception_1
  text: 生成物无spill且LoadStore均有算法来源，反证实际spill机制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_2
  text: 仅有局部变量多或结构体大不足以认定spill
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_3
  text: 重计算可能增加算术量
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_4
  text: 拆分与展开改变代码体积/ICache压力
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 先把必要GM标量读取、成员解引用与实际spill分开；保持编译配置比较报告及热PC，不能把所有LoadStore统称spill；生成物无spill且LoadStore均有算法来源，反证实际spill机制
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 编译器版本和优化选项改变结论，需绑定artifact
  - 源码审读不声称已证实spill
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task与parent实现，绑定同一target身份；指定编译配置下Scalar寄存器存活集合及栈/LoadStore指令
  - from_slot: stage
    to_slot: stage
    rule: 同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
  - from_slot: workload
    to_slot: workload
    rule: 同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
  - from_slot: implementation
    to_slot: implementation
    rule: 同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测
  joint_requirements:
  - fact: symptom.source.register_spill
    state: true
  - fact: constraint.compiler_report
    state: true
  - fact: constraint.semantic_equivalence
    state: true
  - fact: constraint.capacity
    state: true
  - fact: constraint.diagnosis.register_spill.target_stage_bound
    state: true
  exceptions:
  - 生成物无spill且LoadStore均有算法来源，反证实际spill机制
  - 仅有局部变量多或结构体大不足以认定spill
  - 重计算可能增加算术量
  - 拆分与展开改变代码体积/ICache压力
  rationale: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，缩短标量变量生存期、减少不必要取地址或拆分热区对象才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  discriminating_checks:
  - 先把必要GM标量读取、成员解引用与实际spill分开
  - 保持编译配置比较报告及热PC，不能把所有LoadStore统称spill
---

# problem.register_spill → action.shorten_scalar_lifetimes

## 关系与对象绑定

problem.register_spill —mitigated_by→ action.shorten_scalar_lifetimes。

- target→target：同一task与parent实现，绑定同一target身份；指定编译配置下Scalar寄存器存活集合及栈/LoadStore指令
- stage→stage：同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
- workload→workload：同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
- implementation→implementation：同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测

## 联合条件与边界

- symptom.source.register_spill=true
- constraint.compiler_report=true
- constraint.semantic_equivalence=true
- constraint.capacity=true
- constraint.diagnosis.register_spill.target_stage_bound=true

原conditions字段逐值保留。历史空数组没有表达无条件因果或普适适用性；新增条件必须来自绑定scope的证据。

## 依据与判别

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，缩短标量变量生存期、减少不必要取地址或拆分热区对象才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

- 先把必要GM标量读取、成员解引用与实际spill分开
- 保持编译配置比较报告及热PC，不能把所有LoadStore统称spill

## 例外与代价

- 生成物无spill且LoadStore均有算法来源，反证实际spill机制
- 仅有局部变量多或结构体大不足以认定spill
- 重计算可能增加算术量
- 拆分与展开改变代码体积/ICache压力

## 历史参数

原learning={"weight": 2}与seed_reason保留为历史；新检索不把weight当可靠性、概率或自动动作选择依据。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：problem.register_spill → action.shorten_scalar_lifetimes；原learning={"weight": 2}；2 分：缩短对象存活期可能减少 spill，但实际寄存器分配由编译器决定，须重新核对报告。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_scalar [source_statement]

标量编码原则讨论动态数组寻址、别名、变量存活期和热循环内对象构造对Load/Store与寄存器分配的影响。

来源索引：1, 2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_scalar_guide [source_statement]

Scalar负责地址计算、参数构造和指令分发；文档要求以目标profiling、汇编或编译证据确认Load/Store及spill假设。

来源索引：4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### conditional_relation [mechanism_inference]

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，缩短标量变量生存期、减少不必要取地址或拆分热区对象才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

来源索引：1, 2, 3, 4。限制：旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果；joint_requirements是必要联合条件，不构成机制充分证据；编译器版本和优化选项改变结论，需绑定artifact；源码审读不声称已证实spill

### exception_1 [mechanism_inference]

生成物无spill且LoadStore均有算法来源，反证实际spill机制

来源索引：1, 2, 3, 4。限制：例外需在当前scope核验，未观测不当false

### exception_2 [mechanism_inference]

仅有局部变量多或结构体大不足以认定spill

来源索引：1, 2, 3, 4。限制：例外需在当前scope核验，未观测不当false

### exception_3 [mechanism_inference]

重计算可能增加算术量

来源索引：1, 2, 3, 4。限制：例外需在当前scope核验，未观测不当false

### exception_4 [mechanism_inference]

拆分与展开改变代码体积/ICache压力

来源索引：1, 2, 3, 4。限制：例外需在当前scope核验，未观测不当false
