---
schema_version: aprof.diagnosis-record/v1
id: edge.mechanism.tiny_bandwidth
kind: edge
version: 1.1.0
status: active
title: problem.tiny_transfer_setup_amplification → problem.memory_bandwidth_saturation
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
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
  weight: 1
tags:
- mechanism_relation
seed_reason: 新增条件性机制线索；weight仅为旧壳兼容字段，不参与新检索评分。
relation: alternative_to
from: problem.tiny_transfer_setup_amplification
to: problem.memory_bandwidth_saturation
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
- id: source_copy
  text: 来源将批量合并搬运与减少DMA启动次数联系起来，并明确经验粒度阈值只针对原设备。
  basis: source_statement
  source_indexes:
  - 0
  - 1
  - 2
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_copy_sample
  text: 公开搬运样例比较相同张量的多种分块，并把增大块后减少指令和循环开销列为解释；表中收益只属于该样例。
  basis: source_statement
  source_indexes:
  - 3
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_init
  text: InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。
  basis: source_statement
  source_indexes:
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_mm_reuse
  text: arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。
  basis: source_statement
  source_indexes:
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: conditional_relation
  text: 同一搬运方向与稳态窗口内，小包发射受限和接近可达带宽上限是应比较的主导解释；不同阶段可以同时成立。
  basis: mechanism_inference
  source_indexes:
  - 0
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - 来源机制的条件化推导，无profiling/case_support；不能由P候选自动推导另一个P已确认
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
  - fact: constraint.diagnosis.relation.tiny_bandwidth.same_transfer_window
    state: true
  - fact: constraint.diagnosis.relation.tiny_bandwidth.bandwidth_calibration_available
    state: true
  exceptions:
  - MTE高占比不能区分两者
  - 不同目标/窗口不构成互斥替代
  rationale: 同一搬运方向与稳态窗口内，小包发射受限和接近可达带宽上限是应比较的主导解释；不同阶段可以同时成立。
  discriminating_checks:
  - 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加
  - 把搬入、计算和等待按tile展开，检查是否有可合并的边界
  - 分别计算read、write及必要时读写混合的字节/秒，不混用峰值和持续基准
  - 排除冷cache、启动、并发外部负载和小包setup后核对重复窗口
---

# problem.tiny_transfer_setup_amplification → problem.memory_bandwidth_saturation

## 条件关系

同一搬运方向与稳态窗口内，小包发射受限和接近可达带宽上限是应比较的主导解释；不同阶段可以同时成立。

## 绑定与联合条件

- constraint.diagnosis.relation.tiny_bandwidth.same_transfer_window=true
- constraint.diagnosis.relation.tiny_bandwidth.bandwidth_calibration_available=true

- 同一task、parent实现、workload及绑定target；只比较已明确对应的对象和依赖阶段
- 同一task、parent实现、workload及绑定stage；只比较已明确对应的对象和依赖阶段
- 同一task、parent实现、workload及绑定workload；只比较已明确对应的对象和依赖阶段
- 同一task、parent实现、workload及绑定implementation；只比较已明确对应的对象和依赖阶段

## 判别与例外

- 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加
- 把搬入、计算和等待按tile展开，检查是否有可合并的边界
- 分别计算read、write及必要时读写混合的字节/秒，不混用峰值和持续基准
- 排除冷cache、启动、并发外部负载和小包setup后核对重复窗口
- MTE高占比不能区分两者
- 不同目标/窗口不构成互斥替代

## 逐项主张与依据

### source_copy [source_statement]

来源将批量合并搬运与减少DMA启动次数联系起来，并明确经验粒度阈值只针对原设备。

来源索引：0, 1, 2。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_copy_sample [source_statement]

公开搬运样例比较相同张量的多种分块，并把增大块后减少指令和循环开销列为解释；表中收益只属于该样例。

来源索引：3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_init [source_statement]

InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。

来源索引：4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mm_reuse [source_statement]

arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。

来源索引：5, 6, 7。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### conditional_relation [mechanism_inference]

同一搬运方向与稳态窗口内，小包发射受限和接近可达带宽上限是应比较的主导解释；不同阶段可以同时成立。

来源索引：0, 1, 2, 3, 4, 5, 6, 7。限制：来源机制的条件化推导，无profiling/case_support；不能由P候选自动推导另一个P已确认
