---
schema_version: aprof.diagnosis-record/v1
id: symptom.profile.transfer_compute_contention
kind: symptom
version: 1.1.0
status: active
title: Vector-MTE 冲突和 wait 与重叠窗口相关
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
  gain: 1
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: Vector-MTE 冲突和 wait 与重叠窗口相关
  fields:
  - 'ResourceConflictRatio.csv: aiv_vec_mte_cflt_ratio'
  - 'trace: concurrent intervals'
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: 同重叠窗口Vector-MTE冲突或wait计数/后端真实分母，与纯Vector bank计数分开。
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
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
  text: '原种子：Vector-MTE 冲突和 wait 与重叠窗口相关；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: observation_component_1
  text: 当前目标Vector-MTE冲突或wait指标与搬运/Vector重叠窗口相关，相关范围和比较分母已注明
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: gap
  limitations:
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_2
  text: 当前计数器定义、实际地址/资源范围及重叠区间绑定同一target和stage
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: gap
  limitations:
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_3
  text: 当前Vector内部bank指标与Vector-MTE并发指标分别记录；没有对应指标则unknown，不要求先错开发射或改布局
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: gap
  limitations:
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: interpretation_boundary
  text: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: gap
  limitations:
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
review:
  state: gap
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前目标Vector-MTE冲突或wait指标与搬运/Vector重叠窗口相关，相关范围和比较分母已注明；当前计数器定义、实际地址/资源范围及重叠区间绑定同一target和stage；当前Vector内部bank指标与Vector-MTE并发指标分别记录；没有对应指标则unknown，不要求先错开发射或改布局
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.profile.transfer_compute_contention.component_1
    description: 当前目标Vector-MTE冲突或wait指标与搬运/Vector重叠窗口相关，相关范围和比较分母已注明
  - id: symptom.profile.transfer_compute_contention.component_2
    description: 当前计数器定义、实际地址/资源范围及重叠区间绑定同一target和stage
  - id: symptom.profile.transfer_compute_contention.component_3
    description: 当前Vector内部bank指标与Vector-MTE并发指标分别记录；没有对应指标则unknown，不要求先错开发射或改布局
---

# Vector-MTE 冲突和 wait 与重叠窗口相关

## 当前观察对象与槽位

- target：同一UB或片上通路上的并发MTE与Vector访问
- stage：kernel搬运与计算重叠窗口
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前目标Vector-MTE冲突或wait指标与搬运/Vector重叠窗口相关，相关范围和比较分母已注明
- 当前计数器定义、实际地址/资源范围及重叠区间绑定同一target和stage
- 当前Vector内部bank指标与Vector-MTE并发指标分别记录；没有对应指标则unknown，不要求先错开发射或改布局

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- raw：采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
- derived：比值与差值需注明分子分母、时间窗口、平台上限来源
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：同重叠窗口Vector-MTE冲突或wait计数/后端真实分母，与纯Vector bank计数分开。

比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。

## 未知与解释边界

- target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
- 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
- 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

## 人工证据要求

本模板不包含当前任务实测。人工标注保留evidence_id、原始ref、task/parent/workload/target/stage；派生事实保留derived_from。原evidence.rule仅保留迁移种子表述；当前复合定义以本observation和对应claim为准。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：Vector-MTE 冲突和 wait 与重叠窗口相关；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### observation_component_1 [mechanism_inference]

当前目标Vector-MTE冲突或wait指标与搬运/Vector重叠窗口相关，相关范围和比较分母已注明

来源索引：1, 2, 3, 4, 5。限制：固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。；当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

当前计数器定义、实际地址/资源范围及重叠区间绑定同一target和stage

来源索引：1, 2, 3, 4, 5。限制：固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。；当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

当前Vector内部bank指标与Vector-MTE并发指标分别记录；没有对应指标则unknown，不要求先错开发射或改布局

来源索引：1, 2, 3, 4, 5。限制：固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。；当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：1, 2, 3, 4, 5。限制：来源对布局与流水耦合提供原理，未给本任务并发冲突实测；目标计数器或通路语义未核对时保持假设；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
