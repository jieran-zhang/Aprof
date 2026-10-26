---
schema_version: aprof.diagnosis-record/v1
id: edge.support.conflict.profile
kind: edge
version: 1.1.0
status: active
title: symptom.profile.ub_conflict_high → problem.ub_bank_conflict
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/bound-deep-routing.md
  original_path: skills/aprof/diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  lines:
  - 58
  - 64
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:8e89ada79f00c47215a93a0214ab24ee0e350adcc21bccb8cb2f914aa98750db
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
learning:
  weight: 3
tags: []
seed_reason: 3 分：“Vector 的 UB 冲突计数偏高”支持“UB 布局引起 bank 冲突”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.profile.ub_conflict_high
to: problem.ub_bank_conflict
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
- id: legacy_seed
  text: '原种子：symptom.profile.ub_conflict_high → problem.ub_bank_conflict；原learning={"weight": 3}；3 分：“Vector 的 UB
    冲突计数偏高”支持“UB 布局引起 bank 冲突”；带完整判别条件的证据能直接区分机制。'
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
- id: conditional_relation
  text: 该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“本项是Vector内部操作数冲突，后者含MTE与Vector同时访问”。满足后仍需比较替代解释，相关性不单独确立机制。
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果
  - joint_requirements是必要联合条件，不构成机制充分证据
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
- id: exception_1
  text: 不同时间访问同bank不构成本机制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_2
  text: 没有目标几何或实际地址时只能保留风险，不能认定冲突
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 分别判断读写、写写、读读，不能把同一group一概视为冲突；固定有效元素、mask与指令路径比较padding或stride；不同时间访问同bank不构成本机制
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task与parent实现，绑定同一target身份；同一Vector Repeat并发访问的src/dst地址与stride
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
  - fact: symptom.profile.ub_conflict_high
    state: true
  - fact: constraint.diagnosis.ub_bank_conflict.profile_scope_verified
    state: true
  exceptions:
  - 不同时间访问同bank不构成本机制
  - 没有目标几何或实际地址时只能保留风险，不能认定冲突
  rationale: 该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“本项是Vector内部操作数冲突，后者含MTE与Vector同时访问”。满足后仍需比较替代解释，相关性不单独确立机制。
  discriminating_checks:
  - 分别判断读写、写写、读读，不能把同一group一概视为冲突
  - 固定有效元素、mask与指令路径比较padding或stride
---

# symptom.profile.ub_conflict_high → problem.ub_bank_conflict

## 关系与对象绑定

symptom.profile.ub_conflict_high —supports→ problem.ub_bank_conflict。

- target→target：同一task与parent实现，绑定同一target身份；同一Vector Repeat并发访问的src/dst地址与stride
- stage→stage：同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
- workload→workload：同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
- implementation→implementation：同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测

## 联合条件与边界

- symptom.profile.ub_conflict_high=true
- constraint.diagnosis.ub_bank_conflict.profile_scope_verified=true

原conditions字段逐值保留。历史空数组没有表达无条件因果或普适适用性；新增条件必须来自绑定scope的证据。

## 依据与判别

该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“本项是Vector内部操作数冲突，后者含MTE与Vector同时访问”。满足后仍需比较替代解释，相关性不单独确立机制。

- 分别判断读写、写写、读读，不能把同一group一概视为冲突
- 固定有效元素、mask与指令路径比较padding或stride

## 例外与代价

- 不同时间访问同bank不构成本机制
- 没有目标几何或实际地址时只能保留风险，不能认定冲突

## 历史参数

原learning={"weight": 3}与seed_reason保留为历史；新检索不把weight当可靠性、概率或自动动作选择依据。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：symptom.profile.ub_conflict_high → problem.ub_bank_conflict；原learning={"weight": 3}；3 分：“Vector 的 UB 冲突计数偏高”支持“UB 布局引起 bank 冲突”；带完整判别条件的证据能直接区分机制。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_bank [source_statement]

arch22文档按同一Repeat的并发读写及bank/group映射判断冲突，并明确不同芯片的规则有差异。

来源索引：1。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### conditional_relation [mechanism_inference]

该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“本项是Vector内部操作数冲突，后者含MTE与Vector同时访问”。满足后仍需比较替代解释，相关性不单独确立机制。

来源索引：1, 2, 3。限制：旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果；joint_requirements是必要联合条件，不构成机制充分证据；arch22与arch35读读条件不同，禁止互用固定padding和几何；通用冲突字段必须映射到目标后端实际计数器

### exception_1 [mechanism_inference]

不同时间访问同bank不构成本机制

来源索引：1, 2, 3。限制：例外需在当前scope核验，未观测不当false

### exception_2 [mechanism_inference]

没有目标几何或实际地址时只能保留风险，不能认定冲突

来源索引：1, 2, 3。限制：例外需在当前scope核验，未观测不当false
