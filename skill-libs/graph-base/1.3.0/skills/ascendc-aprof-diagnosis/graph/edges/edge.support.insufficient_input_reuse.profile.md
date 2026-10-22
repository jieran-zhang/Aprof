---
schema_version: aprof.diagnosis-record/v1
id: edge.support.insufficient_input_reuse.profile
kind: edge
version: 1.1.0
status: active
title: symptom.profile.insufficient_input_reuse → problem.insufficient_input_reuse
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/data-movement-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  lines:
  - 67
  - 67
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:a374c2ad0072ec617e1ee3f8b5854465e2148afe3fcb4cfa3215c9d6dc2ce37c
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
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 24
  - 35
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:e9a7c01b4dd1338cd812a8b6940b482fe8e12aa04ec8e88ef5b84b7450736933
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 48
  - 84
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:b48b1b038cc6090996c91bafcb22133ac35868808e5f715359c1907a8cb794cc
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/reuse_and_split_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 123
  - 134
  sha256: sha256:080b31488432d91c218eacb24f37608c99425ab7b6b692f2e6e7691a407475a6
  excerpt_sha256: sha256:1d4888316baa02f73aee3c82d6eff75edd9d7e71281705a17178023794f55107
learning:
  weight: 2
tags: []
seed_reason: 2 分：“输入流量高于按复用次数计算的下界”支持“重复输入未复用”；有明确关联，仍需排除邻近机制或工作量解释。
relation: supports
from: symptom.profile.insufficient_input_reuse
to: problem.insufficient_input_reuse
conditions: []
slots:
- name: target
  kind: object
  description: 跨tile/迭代保持不变的输入切片
  required: true
- name: stage
  kind: stage
  description: host tile顺序与分核；kernel CopyIn及片上驻留期
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
  text: '原种子：symptom.profile.insufficient_input_reuse → problem.insufficient_input_reuse；原learning={"weight": 2}；2
    分：“输入流量高于按复用次数计算的下界”支持“重复输入未复用”；有明确关联，仍需排除邻近机制或工作量解释。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_resident
  text: arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。
  basis: source_statement
  source_indexes:
  - 1
  - 2
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_mm_reuse
  text: arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。
  basis: source_statement
  source_indexes:
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: conditional_relation
  text: 该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“软件重复copy与L2替换造成的miss是不同层次”。满足后仍需比较替代解释，相关性不单独确立机制。
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
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
- id: exception_1
  text: 循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_2
  text: 驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据；比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省；循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task与parent实现，绑定同一target身份；跨tile/迭代保持不变的输入切片
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
  - fact: symptom.profile.insufficient_input_reuse
    state: true
  - fact: constraint.diagnosis.insufficient_input_reuse.profile_scope_verified
    state: true
  exceptions:
  - 循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
  - 驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用
  rationale: 该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“软件重复copy与L2替换造成的miss是不同层次”。满足后仍需比较替代解释，相关性不单独确立机制。
  discriminating_checks:
  - 按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据
  - 比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省
---

# symptom.profile.insufficient_input_reuse → problem.insufficient_input_reuse

## 关系与对象绑定

symptom.profile.insufficient_input_reuse —supports→ problem.insufficient_input_reuse。

- target→target：同一task与parent实现，绑定同一target身份；跨tile/迭代保持不变的输入切片
- stage→stage：同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
- workload→workload：同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
- implementation→implementation：同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测

## 联合条件与边界

- symptom.profile.insufficient_input_reuse=true
- constraint.diagnosis.insufficient_input_reuse.profile_scope_verified=true

原conditions字段逐值保留。历史空数组没有表达无条件因果或普适适用性；新增条件必须来自绑定scope的证据。

## 依据与判别

该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“软件重复copy与L2替换造成的miss是不同层次”。满足后仍需比较替代解释，相关性不单独确立机制。

- 按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据
- 比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省

## 例外与代价

- 循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
- 驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用

## 历史参数

原learning={"weight": 2}与seed_reason保留为历史；新检索不把weight当可靠性、概率或自动动作选择依据。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：symptom.profile.insufficient_input_reuse → problem.insufficient_input_reuse；原learning={"weight": 2}；2 分：“输入流量高于按复用次数计算的下界”支持“重复输入未复用”；有明确关联，仍需排除邻近机制或工作量解释。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：1, 2。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mm_reuse [source_statement]

arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。

来源索引：3, 4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### conditional_relation [mechanism_inference]

该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“软件重复copy与L2替换造成的miss是不同层次”。满足后仍需比较替代解释，相关性不单独确立机制。

来源索引：1, 2, 3, 4, 5。限制：旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果；joint_requirements是必要联合条件，不构成机制充分证据；常驻需要目标平台容量及同步证明；arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号

### exception_1 [mechanism_inference]

循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_2 [mechanism_inference]

驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false
