---
schema_version: aprof.diagnosis-record/v1
id: edge.action.memory_bandwidth_saturation
kind: edge
version: 1.1.0
status: active
title: problem.memory_bandwidth_saturation → action.reduce_memory_traffic
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
  - 71
  - 71
  sha256: sha256:58e28c093db98279fc16b45d1140c4673e3f9b312392618908c515bdc58b04e3
  excerpt_sha256: sha256:40cf97cdaaeea3eb3cc641c95cc06f85b78db33183b9bb819b0a9260c70159b8
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  original_path: skills/ascendc-aprof-diagnosis/references/bound-deep-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  lines:
  - 48
  - 48
  sha256: sha256:620c25b91946e0523ffc99aaddae20b8b6989d8b6a1474d7c15c49cb43bfbbbe
  excerpt_sha256: sha256:33c702652aa6f9cbbc51464f7c3f1818dbc4f5e623cfe6835bd3267de4b5407c
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  original_path: examples/01_simd_cpp_api/05_best_practices/04_memory_access/data_copy/README.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 145
  - 177
  sha256: sha256:7126d511236c3539b2710934c468c56500e39ac336531597a3360d6c74282cff
  excerpt_sha256: sha256:7b6fd467d0158bb6da05a6eee05102706b180cc2a4992bee560a24662c4a7c48
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
seed_reason: 2 分：减少可消除流量能降低带宽时间下界，但需证明流量可减少且额外计算与精度成本可接受。
relation: mitigated_by
from: problem.memory_bandwidth_saturation
to: action.reduce_memory_traffic
conditions: []
slots:
- name: target
  kind: object
  description: 同一调用中连续大块输入/输出及GM带宽窗口
  required: true
- name: stage
  kind: stage
  description: host工作量与访问模型；kernel稳态MTE传输
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
  text: '原种子：problem.memory_bandwidth_saturation → action.reduce_memory_traffic；原learning={"weight": 2}；2 分：减少可消除流量能降低带宽时间下界，但需证明流量可减少且额外计算与精度成本可接受。'
  basis: legacy_seed
  source_indexes:
  - 0
  - 1
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_copy_sample
  text: 公开搬运样例比较相同张量的多种分块，并把增大块后减少指令和循环开销列为解释；表中收益只属于该样例。
  basis: source_statement
  source_indexes:
  - 2
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_copy
  text: 来源将批量合并搬运与减少DMA启动次数联系起来，并明确经验粒度阈值只针对原设备。
  basis: source_statement
  source_indexes:
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_mm_reuse
  text: arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。
  basis: source_statement
  source_indexes:
  - 6
  - 7
  - 8
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: conditional_relation
  text: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，消除可证明冗余的输入读取或中间写读，比较总GM流量与关键路径才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  basis: mechanism_inference
  source_indexes: &id001
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  review_status: reviewed
  limitations:
  - 旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果
  - joint_requirements是必要联合条件，不构成机制充分证据
  - 无目标持续带宽基准时不判饱和
  - 数据搬运样例的峰值估算和具体收益不跨平台使用
- id: exception_1
  text: 持续有效带宽远低于可达基准且每次搬运很小则转查setup
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_2
  text: 较高MTE比例可来自计算少或等待，缺少实际字节与分母时保持未知
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_3
  text: 驻留或融合会增加片上峰值及同步管理
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
- id: exception_4
  text: 压缩或重计算可能增加算术量和精度风险
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 例外需在当前scope核验，未观测不当false
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 分别计算read、write及必要时读写混合的字节/秒，不混用峰值和持续基准；排除冷cache、启动、并发外部负载和小包setup后核对重复窗口；持续有效带宽远低于可达基准且每次搬运很小则转查setup
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 无目标持续带宽基准时不判饱和
  - 数据搬运样例的峰值估算和具体收益不跨平台使用
binding:
  object_bindings:
  - from_slot: target
    to_slot: target
    rule: 同一task与parent实现，绑定同一target身份；同一调用中连续大块输入/输出及GM带宽窗口
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
  - fact: symptom.source.memory_bandwidth_saturation
    state: true
  - fact: constraint.traffic_reducible
    state: true
  - fact: constraint.semantic_equivalence
    state: true
  - fact: constraint.capacity
    state: true
  - fact: constraint.diagnosis.memory_bandwidth_saturation.target_stage_bound
    state: true
  exceptions:
  - 持续有效带宽远低于可达基准且每次搬运很小则转查setup
  - 较高MTE比例可来自计算少或等待，缺少实际字节与分母时保持未知
  - 驻留或融合会增加片上峰值及同步管理
  - 压缩或重计算可能增加算术量和精度风险
  rationale: 仅当该Problem在绑定对象/阶段上仍有可核验解释力时，消除可证明冗余的输入读取或中间写读，比较总GM流量与关键路径才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。
  discriminating_checks:
  - 分别计算read、write及必要时读写混合的字节/秒，不混用峰值和持续基准
  - 排除冷cache、启动、并发外部负载和小包setup后核对重复窗口
---

# problem.memory_bandwidth_saturation → action.reduce_memory_traffic

## 关系与对象绑定

problem.memory_bandwidth_saturation —mitigated_by→ action.reduce_memory_traffic。

- target→target：同一task与parent实现，绑定同一target身份；同一调用中连续大块输入/输出及GM带宽窗口
- stage→stage：同一task与parent实现，绑定同一stage身份；只允许对应阶段及其已注明的直接依赖窗口
- workload→workload：同一task与parent实现，绑定同一workload身份；shape/dtype/layout/feature及有效元素域一致
- implementation→implementation：同一task与parent实现，绑定同一implementation身份；当前host/tiling/kernel及编译artifact一致，不把C2变换后属性充当当前观测

## 联合条件与边界

- symptom.source.memory_bandwidth_saturation=true
- constraint.traffic_reducible=true
- constraint.semantic_equivalence=true
- constraint.capacity=true
- constraint.diagnosis.memory_bandwidth_saturation.target_stage_bound=true

原conditions字段逐值保留。历史空数组没有表达无条件因果或普适适用性；新增条件必须来自绑定scope的证据。

## 依据与判别

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，消除可证明冗余的输入读取或中间写读，比较总GM流量与关键路径才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

- 分别计算read、write及必要时读写混合的字节/秒，不混用峰值和持续基准
- 排除冷cache、启动、并发外部负载和小包setup后核对重复窗口

## 例外与代价

- 持续有效带宽远低于可达基准且每次搬运很小则转查setup
- 较高MTE比例可来自计算少或等待，缺少实际字节与分母时保持未知
- 驻留或融合会增加片上峰值及同步管理
- 压缩或重计算可能增加算术量和精度风险

## 历史参数

原learning={"weight": 2}与seed_reason保留为历史；新检索不把weight当可靠性、概率或自动动作选择依据。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：problem.memory_bandwidth_saturation → action.reduce_memory_traffic；原learning={"weight": 2}；2 分：减少可消除流量能降低带宽时间下界，但需证明流量可减少且额外计算与精度成本可接受。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_copy_sample [source_statement]

公开搬运样例比较相同张量的多种分块，并把增大块后减少指令和循环开销列为解释；表中收益只属于该样例。

来源索引：2。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_copy [source_statement]

来源将批量合并搬运与减少DMA启动次数联系起来，并明确经验粒度阈值只针对原设备。

来源索引：3, 4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mm_reuse [source_statement]

arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。

来源索引：6, 7, 8。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### conditional_relation [mechanism_inference]

仅当该Problem在绑定对象/阶段上仍有可核验解释力时，消除可证明冗余的输入读取或中间写读，比较总GM流量与关键路径才是对应候选。联合条件继承A全部原硬前提，C2可比较未知条件，C3不能越过门禁。

来源索引：2, 3, 4, 5, 6, 7, 8。限制：旧conditions原样保留为空时，只表示历史没有机器过滤，绝不表示无条件因果；joint_requirements是必要联合条件，不构成机制充分证据；无目标持续带宽基准时不判饱和；数据搬运样例的峰值估算和具体收益不跨平台使用

### exception_1 [mechanism_inference]

持续有效带宽远低于可达基准且每次搬运很小则转查setup

来源索引：2, 3, 4, 5, 6, 7, 8。限制：例外需在当前scope核验，未观测不当false

### exception_2 [mechanism_inference]

较高MTE比例可来自计算少或等待，缺少实际字节与分母时保持未知

来源索引：2, 3, 4, 5, 6, 7, 8。限制：例外需在当前scope核验，未观测不当false

### exception_3 [mechanism_inference]

驻留或融合会增加片上峰值及同步管理

来源索引：2, 3, 4, 5, 6, 7, 8。限制：例外需在当前scope核验，未观测不当false

### exception_4 [mechanism_inference]

压缩或重计算可能增加算术量和精度风险

来源索引：2, 3, 4, 5, 6, 7, 8。限制：例外需在当前scope核验，未观测不当false
