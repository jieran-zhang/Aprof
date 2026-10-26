---
schema_version: aprof.diagnosis-record/v1
id: symptom.profile.vector_granularity_low
kind: symptom
version: 1.1.0
status: active
title: Vector 指令的有效处理粒度偏小
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
  - 54
  - 64
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:329216724d9c56417c1aa4070999a3b835a7d92be1423eab089267e4f560919d
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
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: Vector 指令的有效处理粒度偏小；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - vector_api_count
  - vector_repeat_distribution
  - vector_theoretical_utilization
  units:
    vector_api_count: 按原报告单位；比值与容量分母须绑定平台
    vector_repeat_distribution: 按原报告单位；比值与容量分母须绑定平台
    vector_theoretical_utilization: 按原报告单位；比值与容量分母须绑定平台
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: 有效lane元素/(issued repeat×目标dtype每repeat容量)；mask与API数分列。
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
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
  text: '原种子：Vector 指令的有效处理粒度偏小；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: observation_component_1
  text: 当前Vector有效处理粒度相对已注明dtype/指令能力偏小，API或指令数量相对有效元素偏多
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_2
  text: 当前count、repeat、mask与有效lane元素可对应到同一窗口
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_3
  text: 有效利用率分子分母、主体/尾段及控制/发射时间的口径已注明；不要求先合并API
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
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
  - 4
  - 5
  review_status: reviewed
  limitations:
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - API理论利用率必须由目标指令和dtype推导
  - 没有自动extractor，本轮不声称已采样到repeat分布
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前Vector有效处理粒度相对已注明dtype/指令能力偏小，API或指令数量相对有效元素偏多；当前count、repeat、mask与有效lane元素可对应到同一窗口；有效利用率分子分母、主体/尾段及控制/发射时间的口径已注明；不要求先合并API
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.profile.vector_granularity_low.component_1
    description: 当前Vector有效处理粒度相对已注明dtype/指令能力偏小，API或指令数量相对有效元素偏多
  - id: symptom.profile.vector_granularity_low.component_2
    description: 当前count、repeat、mask与有效lane元素可对应到同一窗口
  - id: symptom.profile.vector_granularity_low.component_3
    description: 有效利用率分子分母、主体/尾段及控制/发射时间的口径已注明；不要求先合并API
---

# Vector 指令的有效处理粒度偏小

## 当前观察对象与槽位

- target：同一有效元素域上的Vector API序列、repeat和mask分布
- stage：kernel Vector发射与尾处理
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前Vector有效处理粒度相对已注明dtype/指令能力偏小，API或指令数量相对有效元素偏多
- 当前count、repeat、mask与有效lane元素可对应到同一窗口
- 有效利用率分子分母、主体/尾段及控制/发射时间的口径已注明；不要求先合并API

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- vector_api_count：按原报告单位；比值与容量分母须绑定平台
- vector_repeat_distribution：按原报告单位；比值与容量分母须绑定平台
- vector_theoretical_utilization：按原报告单位；比值与容量分母须绑定平台
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：有效lane元素/(issued repeat×目标dtype每repeat容量)；mask与API数分列。

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

原种子：Vector 指令的有效处理粒度偏小；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### observation_component_1 [mechanism_inference]

当前Vector有效处理粒度相对已注明dtype/指令能力偏小，API或指令数量相对有效元素偏多

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

当前count、repeat、mask与有效lane元素可对应到同一窗口

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

有效利用率分子分母、主体/尾段及控制/发射时间的口径已注明；不要求先合并API

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：1, 2, 3, 4, 5。限制：API理论利用率必须由目标指令和dtype推导；没有自动extractor，本轮不声称已采样到repeat分布
