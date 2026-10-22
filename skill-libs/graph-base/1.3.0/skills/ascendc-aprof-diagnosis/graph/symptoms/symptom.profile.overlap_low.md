---
schema_version: aprof.diagnosis-record/v1
id: symptom.profile.overlap_low
kind: symptom
version: 1.1.0
status: active
title: 搬运与计算在时间线上缺少重叠
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
  - 83
  - 87
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:3f1619f1c79c4f97938c9ee8866c29bdc50f8fd8749486e79626cf99c8ed6c1e
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 5
  - 7
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:28ffa9d76883d46d4c3115e15e7b37b63974e9d8ce9469a003250d37dd2eb8e3
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 52
  - 80
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:45711f60b851ff9d3c3805e3a92d835cdee2c5465c506208beffbd197569abb9
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/matmul/arch22/pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 121
  - 134
  sha256: sha256:411edebe99b43b0bb05bac2754c1d4ffd4abe46c726df718c0c1b4a7131eb0ed
  excerpt_sha256: sha256:e10bdb71a109baa5e1f6383282f76aaa1b3077058647107df56c2939a6389526
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
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  original_path: docs/zh/api/SIMD-API/basic_api/resource_management/TPipe/InitBuffer.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 97
  - 108
  sha256: sha256:36da88132f7d5f62484bc98896bd99577bcce25d71a84e21220731a557aea34d
  excerpt_sha256: sha256:e2ee07f2f75d3a3f11d1ba56e11c5cad9974e2e78bb6ce215cd610ef9d8c985d
learning:
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 搬运与计算在时间线上缺少重叠；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - timeline_copy_intervals
  - timeline_compute_intervals
  - pipe_wait_ratios
  units:
    timeline_copy_intervals: 按原报告单位；比值与容量分母须绑定平台
    timeline_compute_intervals: 按原报告单位；比值与容量分母须绑定平台
    pipe_wait_ratios: 按原报告单位；比值与容量分母须绑定平台
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: 同窗口Copy∩Compute区间s/已声明稳态窗口s；排除不同任务聚合与序言尾声。
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
slots:
- name: target
  kind: object
  description: 多个tile的CopyIn/Compute/CopyOut及其buffer事件链
  required: true
- name: stage
  kind: stage
  description: kernel预取序言；稳态tile循环；排空尾声
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
  text: '原种子：搬运与计算在时间线上缺少重叠；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_mm_pipe
  text: arch22 MatMul文档把同buffer逐K搬入装载计算与流水串行联系，要求事件、容量、循环数和高阶API内部流水一并核对。
  basis: source_statement
  source_indexes:
  - 1
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
- id: source_init
  text: InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。
  basis: source_statement
  source_indexes:
  - 6
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: observation_component_1
  text: 当前同一稳态多tile窗口内Copy与Compute时间区间缺少重叠，重叠分母与覆盖范围已注明
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_2
  text: 当前timeline的Copy、Compute和wait区间绑定同一target、tile及其直接依赖阶段
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_3
  text: 序言、排空和不同任务/核的聚合统计已分开；无需先证明等待来自事件安排或排除资源瓶颈
  basis: mechanism_inference
  source_indexes:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
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
  - 6
  review_status: reviewed
  limitations:
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前同一稳态多tile窗口内Copy与Compute时间区间缺少重叠，重叠分母与覆盖范围已注明；当前timeline的Copy、Compute和wait区间绑定同一target、tile及其直接依赖阶段；序言、排空和不同任务/核的聚合统计已分开；无需先证明等待来自事件安排或排除资源瓶颈
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.profile.overlap_low.component_1
    description: 当前同一稳态多tile窗口内Copy与Compute时间区间缺少重叠，重叠分母与覆盖范围已注明
  - id: symptom.profile.overlap_low.component_2
    description: 当前timeline的Copy、Compute和wait区间绑定同一target、tile及其直接依赖阶段
  - id: symptom.profile.overlap_low.component_3
    description: 序言、排空和不同任务/核的聚合统计已分开；无需先证明等待来自事件安排或排除资源瓶颈
---

# 搬运与计算在时间线上缺少重叠

## 当前观察对象与槽位

- target：多个tile的CopyIn/Compute/CopyOut及其buffer事件链
- stage：kernel预取序言；稳态tile循环；排空尾声
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前同一稳态多tile窗口内Copy与Compute时间区间缺少重叠，重叠分母与覆盖范围已注明
- 当前timeline的Copy、Compute和wait区间绑定同一target、tile及其直接依赖阶段
- 序言、排空和不同任务/核的聚合统计已分开；无需先证明等待来自事件安排或排除资源瓶颈

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- timeline_copy_intervals：按原报告单位；比值与容量分母须绑定平台
- timeline_compute_intervals：按原报告单位；比值与容量分母须绑定平台
- pipe_wait_ratios：按原报告单位；比值与容量分母须绑定平台
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：同窗口Copy∩Compute区间s/已声明稳态窗口s；排除不同任务聚合与序言尾声。

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

原种子：搬运与计算在时间线上缺少重叠；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_mm_pipe [source_statement]

arch22 MatMul文档把同buffer逐K搬入装载计算与流水串行联系，要求事件、容量、循环数和高阶API内部流水一并核对。

来源索引：1, 2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_double [source_statement]

双缓冲文档要求可重叠预取结构、容量和事件闭合；全载单轮或过度同步时增缓冲可能无收益。

来源索引：4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_init [source_statement]

InitBuffer文档定义num为物理内存块数、len以字节计且内部按32字节向上对齐。

来源索引：6。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### observation_component_1 [mechanism_inference]

当前同一稳态多tile窗口内Copy与Compute时间区间缺少重叠，重叠分母与覆盖范围已注明

来源索引：1, 2, 3, 4, 5, 6。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

当前timeline的Copy、Compute和wait区间绑定同一target、tile及其直接依赖阶段

来源索引：1, 2, 3, 4, 5, 6。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

序言、排空和不同任务/核的聚合统计已分开；无需先证明等待来自事件安排或排除资源瓶颈

来源索引：1, 2, 3, 4, 5, 6。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：1, 2, 3, 4, 5, 6。限制：num=2不等于实际重叠成立；不复制来源80%等重叠率或收益为目标承诺
