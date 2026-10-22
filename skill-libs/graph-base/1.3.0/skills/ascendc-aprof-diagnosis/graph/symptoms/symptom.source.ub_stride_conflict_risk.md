---
schema_version: aprof.diagnosis-record/v1
id: symptom.source.ub_stride_conflict_risk
kind: symptom
version: 1.1.0
status: active
title: UB 起址或 stride 存在周期性冲突风险
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/diagnosis/references/source-hypothesis-routing.md
  original_path: skills/aprof/diagnosis/references/source-hypothesis-routing.md
  revision: aprof-1.1.0-pre-governance:sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  lines:
  - 27
  - 32
  sha256: sha256:ef273a362b02e6e2409ca55e684d55d5f54cf539529acb9154319b996090dd1c
  excerpt_sha256: sha256:7754b4a7717efa2eea08cad77ec1ecab5a5c96736871d7fd98c7782a5c121bc1
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
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: source
evidence:
  rule: UB 起址或 stride 存在周期性冲突风险；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - ub_offsets
  - block_strides
  - operand_layout
  - hardware_bank_geometry
  units:
    ub_offsets: 按原报告单位；比值与容量分母须绑定平台
    block_strides: 按原报告单位；比值与容量分母须绑定平台
    operand_layout: 按原报告单位；比值与容量分母须绑定平台
    hardware_bank_geometry: 按原报告单位；比值与容量分母须绑定平台
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: 同Repeat并发地址映射与Vector冲突次数/后端规定分母；周期需同指令/有效元素比较。
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
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
  text: '原种子：UB 起址或 stride 存在周期性冲突风险；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: observation_component_1
  text: 当前同Repeat候选并发src/dst的UB地址与stride映射到目标规则定义的潜在冲突集合
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_2
  text: 当前src0/src1/dst起址、blk/repeat stride、dtype和实际并发关系有源码引用
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_3
  text: 当前bank/group几何具有目标依据；几何未知则unknown，不要求先padding或测得周期下降
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: interpretation_boundary
  text: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前同Repeat候选并发src/dst的UB地址与stride映射到目标规则定义的潜在冲突集合；当前src0/src1/dst起址、blk/repeat stride、dtype和实际并发关系有源码引用；当前bank/group几何具有目标依据；几何未知则unknown，不要求先padding或测得周期下降
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.source.ub_stride_conflict_risk.component_1
    description: 当前同Repeat候选并发src/dst的UB地址与stride映射到目标规则定义的潜在冲突集合
  - id: symptom.source.ub_stride_conflict_risk.component_2
    description: 当前src0/src1/dst起址、blk/repeat stride、dtype和实际并发关系有源码引用
  - id: symptom.source.ub_stride_conflict_risk.component_3
    description: 当前bank/group几何具有目标依据；几何未知则unknown，不要求先padding或测得周期下降
---

# UB 起址或 stride 存在周期性冲突风险

## 当前观察对象与槽位

- target：同一Vector Repeat并发访问的src/dst地址与stride
- stage：kernel UB布局；Vector执行同一Repeat
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前同Repeat候选并发src/dst的UB地址与stride映射到目标规则定义的潜在冲突集合
- 当前src0/src1/dst起址、blk/repeat stride、dtype和实际并发关系有源码引用
- 当前bank/group几何具有目标依据；几何未知则unknown，不要求先padding或测得周期下降

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- ub_offsets：按原报告单位；比值与容量分母须绑定平台
- block_strides：按原报告单位；比值与容量分母须绑定平台
- operand_layout：按原报告单位；比值与容量分母须绑定平台
- hardware_bank_geometry：按原报告单位；比值与容量分母须绑定平台
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：同Repeat并发地址映射与Vector冲突次数/后端规定分母；周期需同指令/有效元素比较。

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

原种子：UB 起址或 stride 存在周期性冲突风险；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_bank [source_statement]

arch22文档按同一Repeat的并发读写及bank/group映射判断冲突，并明确不同芯片的规则有差异。

来源索引：1。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### observation_component_1 [mechanism_inference]

当前同Repeat候选并发src/dst的UB地址与stride映射到目标规则定义的潜在冲突集合

来源索引：1, 2, 3。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

当前src0/src1/dst起址、blk/repeat stride、dtype和实际并发关系有源码引用

来源索引：1, 2, 3。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

当前bank/group几何具有目标依据；几何未知则unknown，不要求先padding或测得周期下降

来源索引：1, 2, 3。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：1, 2, 3。限制：arch22与arch35读读条件不同，禁止互用固定padding和几何；通用冲突字段必须映射到目标后端实际计数器
