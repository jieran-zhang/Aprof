---
schema_version: aprof.diagnosis-record/v1
id: edge.prior.vector.batch
kind: edge
version: 1.1.0
status: active
title: problem.vector_api_fragmentation → action.batch_vector_api_calls
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/api-algorithm-optimization-strategies.md
  original_path: skills/aprof/optimization/references/api-algorithm-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:27255603c8155ac2f34ba59420190390ba76d940bd9723790a6e72bb1defa5ad
  lines:
  - 20
  - 31
  sha256: sha256:27255603c8155ac2f34ba59420190390ba76d940bd9723790a6e72bb1defa5ad
  excerpt_sha256: sha256:bb24449a74087725fcd3a3da85fee76127b6fed34980d9a192704cab40aa17aa
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
  weight: 3
tags: []
seed_reason: 3 分：“批量调用 Vector API”直接消除“Vector 调用碎片化”对应的重复或不均衡工作，前提由动作独立核验。
relation: mitigated_by
from: problem.vector_api_fragmentation
to: action.batch_vector_api_calls
conditions: []
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
  text: '原种子：problem.vector_api_fragmentation → action.batch_vector_api_calls；原learning={"weight": 3}；3 分：“批量调用
    Vector API”直接消除“Vector 调用碎片化”对应的重复或不均衡工作，前提由动作独立核验。'
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
- id: conditional_relation
  text: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，把语义和依赖允许的相邻Vector调用按count/repeat批量表达才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果
  - joint_requirements是必要联合条件，不构成机制充分证据
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
- id: exception_1
  text: 小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_2
  text: 指令数合理但bank冲突高应查布局
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_3
  text: 更长向量临时区生存期
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_4
  text: 合并受mask、地址跨度、参数上限及精度路径限制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按dtype与有效mask计有效元素而非把repeat数直接当利用率；区分尾部必要小调用、分支依赖和不必要的主体碎片化；小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task与parent实现，绑定同一target身份；同一有效元素域上的Vector API序列、repeat和mask分布
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
  - fact: symptom.profile.vector_granularity_low
    state: true
  - fact: constraint.semantic_equivalence
    state: true
  - fact: constraint.capacity
    state: true
  - fact: constraint.diagnosis.vector_api_fragmentation.target_stage_bound
    state: true
  exceptions:
  - 小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
  - 指令数合理但bank冲突高应查布局
  - 更长向量临时区生存期
  - 合并受mask、地址跨度、参数上限及精度路径限制
  rationale: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，把语义和依赖允许的相邻Vector调用按count/repeat批量表达才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  discriminating_checks:
  - 按dtype与有效mask计有效元素而非把repeat数直接当利用率
  - 区分尾部必要小调用、分支依赖和不必要的主体碎片化
---

# problem.vector_api_fragmentation → action.batch_vector_api_calls

## 关系与对象绑定

problem.vector_api_fragmentation —mitigated_by→ action.batch_vector_api_calls。

- target→target：同一task与parent实现，绑定同一target身份；同一有效元素域上的Vector API序列、repeat和mask分布
- stage→stage：同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
- workload→workload：同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
- implementation→implementation：同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测

## 联合条件与边界

- symptom.profile.vector_granularity_low=true
- constraint.semantic_equivalence=true
- constraint.capacity=true
- constraint.diagnosis.vector_api_fragmentation.target_stage_bound=true

原conditions字段逐值保留。历史空数组没有表达无条件因果或普适适用性；新增条件必须来自绑定scope的证据。

## 依据与判别

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，把语义和依赖允许的相邻Vector调用按count/repeat批量表达才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

- 按dtype与有效mask计有效元素而非把repeat数直接当利用率
- 区分尾部必要小调用、分支依赖和不必要的主体碎片化

## 例外与代价

- 小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并
- 指令数合理但bank冲突高应查布局
- 更长向量临时区生存期
- 合并受mask、地址跨度、参数上限及精度路径限制

## 历史参数

原learning={"weight": 3}与seed_reason保留为历史；新检索不把weight当可靠性、概率或自动动作选择依据。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：problem.vector_api_fragmentation → action.batch_vector_api_calls；原learning={"weight": 3}；3 分：“批量调用 Vector API”直接消除“Vector 调用碎片化”对应的重复或不均衡工作，前提由动作独立核验。

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

### conditional_relation [mechanism_inference]

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，把语义和依赖允许的相邻Vector调用按count/repeat批量表达才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

来源索引：1, 2, 3, 4, 5。限制：旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果；joint_requirements是必要联合条件，不构成机制充分证据；API理论利用率必须由目标指令和dtype推导；没有自动extractor，本轮不声称已采样到repeat分布

### exception_1 [mechanism_inference]

小shape仅需一次小调用或各调用存在数据依赖时，不据粒度小判可合并

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_2 [mechanism_inference]

指令数合理但bank冲突高应查布局

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_3 [mechanism_inference]

更长向量临时区生存期

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_4 [mechanism_inference]

合并受mask、地址跨度、参数上限及精度路径限制

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false
