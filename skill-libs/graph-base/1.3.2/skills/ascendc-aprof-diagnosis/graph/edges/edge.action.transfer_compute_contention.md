---
schema_version: aprof.diagnosis-record/v1
id: edge.action.transfer_compute_contention
kind: edge
version: 1.1.0
status: active
title: problem.transfer_compute_contention → action.stagger_resource_access
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
  weight: 2
tags: []
seed_reason: 2 分：错开访问可能降低资源冲突，也可能损失原有重叠，需比较两者成本。
relation: mitigated_by
from: problem.transfer_compute_contention
to: action.stagger_resource_access
conditions: []
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
  text: '原种子：problem.transfer_compute_contention → action.stagger_resource_access；原learning={"weight": 2}；2 分：错开访问可能降低资源冲突，也可能损失原有重叠，需比较两者成本。'
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
- id: conditional_relation
  text: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，调整合法独立访问的发射相位、buffer布局或资源分担才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: gap
  limitations:
  - 旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果
  - joint_requirements是必要联合条件，不构成机制充分证据
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: exception_1
  text: 冲突计数缺失或仅见同时执行，不能确认争用
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 例外需在当前scope核验，未观测不当false
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: exception_2
  text: 并发访问属于同一未同步数据依赖时先处理正确性
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 例外需在当前scope核验，未观测不当false
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: exception_3
  text: 可能牺牲重叠并增加总等待
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 例外需在当前scope核验，未观测不当false
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: exception_4
  text: 更多buffer或padding会占用容量
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 例外需在当前scope核验，未观测不当false
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
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
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task与parent实现，绑定同一target身份；同一UB或片上通路上的并发MTE与Vector访问
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
  - fact: symptom.source.transfer_compute_contention
    state: true
  - fact: constraint.dependency_lifetime
    state: true
  - fact: constraint.semantic_equivalence
    state: true
  - fact: constraint.capacity
    state: true
  - fact: constraint.diagnosis.transfer_compute_contention.target_stage_bound
    state: true
  exceptions:
  - 冲突计数缺失或仅见同时执行，不能确认争用
  - 并发访问属于同一未同步数据依赖时先处理正确性
  - 可能牺牲重叠并增加总等待
  - 更多buffer或padding会占用容量
  rationale: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，调整合法独立访问的发射相位、buffer布局或资源分担才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  discriminating_checks:
  - 把Vector内部bank冲突与MTE并发冲突分开
  - 检查冲突计数分母和实际重叠区间，比较总Task Duration
---

# problem.transfer_compute_contention → action.stagger_resource_access

## 关系与对象绑定

problem.transfer_compute_contention —mitigated_by→ action.stagger_resource_access。

- target→target：同一task与parent实现，绑定同一target身份；同一UB或片上通路上的并发MTE与Vector访问
- stage→stage：同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
- workload→workload：同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
- implementation→implementation：同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测

## 联合条件与边界

- symptom.source.transfer_compute_contention=true
- constraint.dependency_lifetime=true
- constraint.semantic_equivalence=true
- constraint.capacity=true
- constraint.diagnosis.transfer_compute_contention.target_stage_bound=true

原conditions字段逐值保留。历史空数组没有表达无条件因果或普适适用性；新增条件必须来自绑定scope的证据。

## 依据与判别

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，调整合法独立访问的发射相位、buffer布局或资源分担才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

- 把Vector内部bank冲突与MTE并发冲突分开
- 检查冲突计数分母和实际重叠区间，比较总Task Duration

## 例外与代价

- 冲突计数缺失或仅见同时执行，不能确认争用
- 并发访问属于同一未同步数据依赖时先处理正确性
- 可能牺牲重叠并增加总等待
- 更多buffer或padding会占用容量

## 历史参数

原learning={"weight": 2}与seed_reason保留为历史；新检索不把weight当可靠性、概率或自动动作选择依据。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：problem.transfer_compute_contention → action.stagger_resource_access；原learning={"weight": 2}；2 分：错开访问可能降低资源冲突，也可能损失原有重叠，需比较两者成本。

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

### conditional_relation [mechanism_inference]

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，调整合法独立访问的发射相位、buffer布局或资源分担才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

来源索引：1, 2, 3, 4, 5。限制：旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果；joint_requirements是必要联合条件，不构成机制充分证据；来源对布局与流水耦合提供原理，未给本任务并发冲突实测；目标计数器或通路语义未核对时保持假设

### exception_1 [mechanism_inference]

冲突计数缺失或仅见同时执行，不能确认争用

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_2 [mechanism_inference]

并发访问属于同一未同步数据依赖时先处理正确性

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_3 [mechanism_inference]

可能牺牲重叠并增加总等待

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_4 [mechanism_inference]

更多buffer或padding会占用容量

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false
## 待补证缺口

固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
