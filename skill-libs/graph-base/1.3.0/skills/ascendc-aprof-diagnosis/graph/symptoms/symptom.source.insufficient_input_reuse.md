---
schema_version: aprof.diagnosis-record/v1
id: symptom.source.insufficient_input_reuse
kind: symptom
version: 1.1.0
status: active
title: 循环中重复读取相同输入切片
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
  gain: 1
tags:
- data_movement
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: source
evidence:
  rule: 循环中重复读取相同输入切片
  fields:
  - 源码位置、shape 和 tiling
  units:
    raw: 原后端单位；时间区间和字节口径需记录
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: 实际输入读B/唯一输入B；复用次数按地址内容不变的窗口计。
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
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
  text: '原种子：循环中重复读取相同输入切片；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: observation_component_1
  text: 当前循环重复读取同一地址和值在已注明窗口内不变的输入切片
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
  text: 当前输入地址函数随内外循环的变化和重复次数有源码引用
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
  text: 当前唯一输入字节、owner和buffer覆盖边界已明确；不要求先证明能够常驻
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
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前循环重复读取同一地址和值在已注明窗口内不变的输入切片；当前输入地址函数随内外循环的变化和重复次数有源码引用；当前唯一输入字节、owner和buffer覆盖边界已明确；不要求先证明能够常驻
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.source.insufficient_input_reuse.component_1
    description: 当前循环重复读取同一地址和值在已注明窗口内不变的输入切片
  - id: symptom.source.insufficient_input_reuse.component_2
    description: 当前输入地址函数随内外循环的变化和重复次数有源码引用
  - id: symptom.source.insufficient_input_reuse.component_3
    description: 当前唯一输入字节、owner和buffer覆盖边界已明确；不要求先证明能够常驻
---

# 循环中重复读取相同输入切片

## 当前观察对象与槽位

- target：跨tile/迭代保持不变的输入切片
- stage：host tile顺序与分核；kernel CopyIn及片上驻留期
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前循环重复读取同一地址和值在已注明窗口内不变的输入切片
- 当前输入地址函数随内外循环的变化和重复次数有源码引用
- 当前唯一输入字节、owner和buffer覆盖边界已明确；不要求先证明能够常驻

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- raw：原后端单位；时间区间和字节口径需记录
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：实际输入读B/唯一输入B；复用次数按地址内容不变的窗口计。

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

原种子：循环中重复读取相同输入切片；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：1, 2。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mm_reuse [source_statement]

arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。

来源索引：3, 4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### observation_component_1 [mechanism_inference]

当前循环重复读取同一地址和值在已注明窗口内不变的输入切片

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

当前输入地址函数随内外循环的变化和重复次数有源码引用

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

当前唯一输入字节、owner和buffer覆盖边界已明确；不要求先证明能够常驻

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：1, 2, 3, 4, 5。限制：常驻需要目标平台容量及同步证明；arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
