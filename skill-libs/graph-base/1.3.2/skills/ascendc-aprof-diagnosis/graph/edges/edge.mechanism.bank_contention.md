---
schema_version: aprof.diagnosis-record/v1
id: edge.mechanism.bank_contention
kind: edge
version: 1.1.0
status: active
title: problem.ub_bank_conflict → problem.transfer_compute_contention
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
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
  weight: 1
tags:
- mechanism_relation
seed_reason: 新增条件性机制线索；weight仅为旧壳兼容字段，不参与新检索评分。
relation: may_coexist
from: problem.ub_bank_conflict
to: problem.transfer_compute_contention
conditions: []
slots:
- name: target
  kind: object
  description: 同一Vector Repeat并发访问的src/dst地址与stride
  required: true
- name: stage
  kind: stage
  description: kernel UB布局；Vector执行同一Repeat
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
- id: source_bank
  text: arch22文档按同一Repeat的并发读写及bank/group映射判断冲突，并明确不同芯片的规则有差异。
  basis: source_statement
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_resident
  text: arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。
  basis: source_statement
  source_indexes:
  - 1
  - 2
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_double
  text: 双缓冲文档要求可重叠预取结构、容量和事件闭合；全载单轮或过度同步时增缓冲可能无收益。
  basis: source_statement
  source_indexes:
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: conditional_relation
  text: 同一UB布局可以同时存在Vector操作数bank冲突与Vector/MTE并发资源争用，二者须用各自计数器、地址及窗口分离；这是机制推导。
  basis: mechanism_inference
  source_indexes:
  - 0
  - 1
  - 2
  - 3
  - 4
  review_status: gap
  limitations:
  - 来源机制的条件化推导，无profiling/case_support；不能由P候选自动推导另一个P已确认
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
review:
  state: gap
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 分别判断读写、写写、读读，不能把同一group一概视为冲突；固定有效元素、mask与指令路径比较padding或stride；不同时间访问同bank不构成本机制
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task、parent实现、workload及绑定target；只比较已明确对应的对象和依赖阶段
  - from_slot: stage
    to_slot: stage
    rule: 同一task、parent实现、workload及绑定stage；只比较已明确对应的对象和依赖阶段
  - from_slot: workload
    to_slot: workload
    rule: 同一task、parent实现、workload及绑定workload；只比较已明确对应的对象和依赖阶段
  - from_slot: implementation
    to_slot: implementation
    rule: 同一task、parent实现、workload及绑定implementation；只比较已明确对应的对象和依赖阶段
  joint_requirements:
  - fact: constraint.diagnosis.relation.bank_contention.same_ub_target
    state: true
  - fact: constraint.diagnosis.relation.bank_contention.concurrent_mte_vector_window
    state: true
  exceptions:
  - 仅有Vector内部bank计数不能确认Vector/MTE争用
  - 无并发重叠时不支持后者
  rationale: 同一UB布局可以同时存在Vector操作数bank冲突与Vector/MTE并发资源争用，二者须用各自计数器、地址及窗口分离；这是机制推导。
  discriminating_checks:
  - 分别判断读写、写写、读读，不能把同一group一概视为冲突
  - 固定有效元素、mask与指令路径比较padding或stride
  - 把Vector内部bank冲突与MTE并发冲突分开
  - 检查冲突计数分母和实际重叠区间，比较总Task Duration
---

# problem.ub_bank_conflict → problem.transfer_compute_contention

## 条件关系

同一UB布局可以同时存在Vector操作数bank冲突与Vector/MTE并发资源争用，二者须用各自计数器、地址及窗口分离；这是机制推导。

## 绑定与联合条件

- constraint.diagnosis.relation.bank_contention.same_ub_target=true
- constraint.diagnosis.relation.bank_contention.concurrent_mte_vector_window=true

- 同一task、parent实现、workload及绑定target；只比较已明确对应的对象和依赖阶段
- 同一task、parent实现、workload及绑定stage；只比较已明确对应的对象和依赖阶段
- 同一task、parent实现、workload及绑定workload；只比较已明确对应的对象和依赖阶段
- 同一task、parent实现、workload及绑定implementation；只比较已明确对应的对象和依赖阶段

## 判别与例外

- 分别判断读写、写写、读读，不能把同一group一概视为冲突
- 固定有效元素、mask与指令路径比较padding或stride
- 把Vector内部bank冲突与MTE并发冲突分开
- 检查冲突计数分母和实际重叠区间，比较总Task Duration
- 仅有Vector内部bank计数不能确认Vector/MTE争用
- 无并发重叠时不支持后者

## 逐项主张与依据

### source_bank [source_statement]

arch22文档按同一Repeat的并发读写及bank/group映射判断冲突，并明确不同芯片的规则有差异。

来源索引：0。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：1, 2。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_double [source_statement]

双缓冲文档要求可重叠预取结构、容量和事件闭合；全载单轮或过度同步时增缓冲可能无收益。

来源索引：3, 4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### conditional_relation [mechanism_inference]

同一UB布局可以同时存在Vector操作数bank冲突与Vector/MTE并发资源争用，二者须用各自计数器、地址及窗口分离；这是机制推导。

来源索引：0, 1, 2, 3, 4。限制：来源机制的条件化推导，无profiling/case_support；不能由P候选自动推导另一个P已确认
## 待补证缺口

固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
