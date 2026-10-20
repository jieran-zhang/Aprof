---
schema_version: aprof.diagnosis-record/v1
id: edge.support.tiny_copy.profile
kind: edge
version: 1.1.0
status: active
title: symptom.profile.mte_setup_dominated → problem.tiny_transfer_setup_amplification
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
  - 46
  - 51
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:a2be289520d72c7e7723e6d6dfb7fe1cde47c924097dfb4347c8a2e2fdaa3477
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
  weight: 3
tags: []
seed_reason: 3 分：“MTE 占比高且单位指令有效搬运小、带宽低”支持“小搬运放大发射开销”；带完整判别条件的证据能直接区分机制。
relation: supports
from: symptom.profile.mte_setup_dominated
to: problem.tiny_transfer_setup_amplification
conditions: []
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
  text: '原种子：symptom.profile.mte_setup_dominated → problem.tiny_transfer_setup_amplification；原learning={"weight":
    3}；3 分：“MTE 占比高且单位指令有效搬运小、带宽低”支持“小搬运放大发射开销”；带完整判别条件的证据能直接区分机制。'
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
- id: conditional_relation
  text: 该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限”。满足后仍需比较替代解释，相关性不单独确立机制。
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
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
- id: exception_1
  text: 大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_2
  text: 单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加；把搬入、计算和等待按tile展开，检查是否有可合并的边界；大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task与parent实现，绑定同一target身份；同一tensor切片的搬入块、DMA发射点及所属tile循环
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
  - fact: symptom.profile.mte_setup_dominated
    state: true
  - fact: constraint.diagnosis.tiny_transfer_setup_amplification.profile_scope_verified
    state: true
  exceptions:
  - 大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
  - 单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本
  rationale: 该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限”。满足后仍需比较替代解释，相关性不单独确立机制。
  discriminating_checks:
  - 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加
  - 把搬入、计算和等待按tile展开，检查是否有可合并的边界
---

# symptom.profile.mte_setup_dominated → problem.tiny_transfer_setup_amplification

## 关系与对象绑定

symptom.profile.mte_setup_dominated —supports→ problem.tiny_transfer_setup_amplification。

- target→target：同一task与parent实现，绑定同一target身份；同一tensor切片的搬入块、DMA发射点及所属tile循环
- stage→stage：同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
- workload→workload：同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
- implementation→implementation：同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测

## 联合条件与边界

- symptom.profile.mte_setup_dominated=true
- constraint.diagnosis.tiny_transfer_setup_amplification.profile_scope_verified=true

原conditions字段逐值保留。历史空数组没有表达无条件因果或普适适用性；新增条件必须来自绑定scope的证据。

## 依据与判别

该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限”。满足后仍需比较替代解释，相关性不单独确立机制。

- 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加
- 把搬入、计算和等待按tile展开，检查是否有可合并的边界

## 例外与代价

- 大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
- 单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本

## 历史参数

原learning={"weight": 3}与seed_reason保留为历史；新检索不把weight当可靠性、概率或自动动作选择依据。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：symptom.profile.mte_setup_dominated → problem.tiny_transfer_setup_amplification；原learning={"weight": 3}；3 分：“MTE 占比高且单位指令有效搬运小、带宽低”支持“小搬运放大发射开销”；带完整判别条件的证据能直接区分机制。

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

### conditional_relation [mechanism_inference]

该profile复合观察需同时满足对象、有效域、窗口、单位与模型要求，并按本边检查区分“setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限”。满足后仍需比较替代解释，相关性不单独确立机制。

来源索引：1, 2, 3, 4, 5。限制：旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果；joint_requirements是必要联合条件，不构成机制充分证据；来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据；当前任务没有采集数据，不能把文档样例收益写为本任务收益

### exception_1 [mechanism_inference]

大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false

### exception_2 [mechanism_inference]

单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本

来源索引：1, 2, 3, 4, 5。限制：例外需在当前scope核验，未观测不当false
