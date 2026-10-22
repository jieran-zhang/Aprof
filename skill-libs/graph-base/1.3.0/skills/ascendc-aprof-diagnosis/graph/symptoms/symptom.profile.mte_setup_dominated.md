---
schema_version: aprof.diagnosis-record/v1
id: symptom.profile.mte_setup_dominated
kind: symptom
version: 1.1.0
status: active
title: MTE 占比高且单位指令有效搬运小、带宽低
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
  - 42
  - 51
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:e7416836e2c7c426cade861de5dc1046368fc3d93f8956fe1971fca631c2cdee
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
  gain: 1
tags: []
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: MTE 占比高且单位指令有效搬运小、带宽低；按来源中的源码/字段定义核验，不能从表面占比单独推断。
  fields:
  - mte2_ratio
  - memory_bandwidth_utilization
  - useful_bytes_per_mte_instruction
  units:
    mte2_ratio: 按原报告单位；比值与容量分母须绑定平台
    memory_bandwidth_utilization: 按原报告单位；比值与容量分母须绑定平台
    useful_bytes_per_mte_instruction: 按原报告单位；比值与容量分母须绑定平台
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: 有效B/搬运发射数；保持有效B比较指令数与传输大小分布，MTE比例不足以区分。
  extractor: unimplemented
  unknown_when: 缺少源码、原始计数、时间区间或对应平台分母；未实现 extractor 未经人工证据核验时。
  threshold_scope: 保留历史经验阈值的原平台与 shape 范围；不设通用阈值。
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
  text: '原种子：MTE 占比高且单位指令有效搬运小、带宽低；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: observation_component_1
  text: 当前有效窗口MTE占比偏高、每指令有效搬运字节偏小且有效带宽偏低，参照及分母已注明
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
  text: 当前MTE发射数、有效字节和持续时间可定位到同一切片与方向
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
  text: 当前timeline可标出发射、搬运与等待区间；字段不够分辨setup与其他等待时只保留该复合现象，不要求先缩减发射
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
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前有效窗口MTE占比偏高、每指令有效搬运字节偏小且有效带宽偏低，参照及分母已注明；当前MTE发射数、有效字节和持续时间可定位到同一切片与方向；当前timeline可标出发射、搬运与等待区间；字段不够分辨setup与其他等待时只保留该复合现象，不要求先缩减发射
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.profile.mte_setup_dominated.component_1
    description: 当前有效窗口MTE占比偏高、每指令有效搬运字节偏小且有效带宽偏低，参照及分母已注明
  - id: symptom.profile.mte_setup_dominated.component_2
    description: 当前MTE发射数、有效字节和持续时间可定位到同一切片与方向
  - id: symptom.profile.mte_setup_dominated.component_3
    description: 当前timeline可标出发射、搬运与等待区间；字段不够分辨setup与其他等待时只保留该复合现象，不要求先缩减发射
---

# MTE 占比高且单位指令有效搬运小、带宽低

## 当前观察对象与槽位

- target：同一tensor切片的搬入块、DMA发射点及所属tile循环
- stage：host计算tile和尾长；kernel内层CopyIn及等待
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前有效窗口MTE占比偏高、每指令有效搬运字节偏小且有效带宽偏低，参照及分母已注明
- 当前MTE发射数、有效字节和持续时间可定位到同一切片与方向
- 当前timeline可标出发射、搬运与等待区间；字段不够分辨setup与其他等待时只保留该复合现象，不要求先缩减发射

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- mte2_ratio：按原报告单位；比值与容量分母须绑定平台
- memory_bandwidth_utilization：按原报告单位；比值与容量分母须绑定平台
- useful_bytes_per_mte_instruction：按原报告单位；比值与容量分母须绑定平台
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：有效B/搬运发射数；保持有效B比较指令数与传输大小分布，MTE比例不足以区分。

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

原种子：MTE 占比高且单位指令有效搬运小、带宽低；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### observation_component_1 [mechanism_inference]

当前有效窗口MTE占比偏高、每指令有效搬运字节偏小且有效带宽偏低，参照及分母已注明

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

当前MTE发射数、有效字节和持续时间可定位到同一切片与方向

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

当前timeline可标出发射、搬运与等待区间；字段不够分辨setup与其他等待时只保留该复合现象，不要求先缩减发射

来源索引：1, 2, 3, 4, 5。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：1, 2, 3, 4, 5。限制：来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据；当前任务没有采集数据，不能把文档样例收益写为本任务收益
