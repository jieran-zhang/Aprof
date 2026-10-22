---
schema_version: aprof.diagnosis-record/v1
id: problem.transfer_compute_contention
kind: problem
version: 1.1.0
status: active
title: 搬运和计算竞争片上资源
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
  bias: 0
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 搬运和Vector在重叠窗口争用同一片上资源或端口 → 重叠使仲裁/等待增多而非隐藏延迟 → 总时长受共享资源吞吐限制
alternatives:
- problem.ub_bank_conflict：同Repeat操作数冲突可在没有MTE时出现；检查：用无MTE计算窗口与并发窗口对照
- problem.pipeline_serialization：完全缺少重叠不能直接支持重叠争用；检查：核对双方是否真实同时在执行
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
  text: '原种子：搬运和计算竞争片上资源；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 搬运和Vector在重叠窗口争用同一片上资源或端口
  basis: mechanism_inference
  source_indexes: &id001
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
- id: mechanism_2
  text: 重叠使仲裁/等待增多而非隐藏延迟
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: mechanism_3
  text: 总时长受共享资源吞吐限制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: prediction_1
  text: 改变独立访问的相位或资源布局可能降低冲突，但减少重叠也可能变慢；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: check_1
  text: 把Vector内部bank冲突与MTE并发冲突分开
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: check_2
  text: 检查冲突计数分母和实际重叠区间，比较总Task Duration
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: check_3
  text: 冲突计数缺失或仅见同时执行，不能确认争用
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: check_4
  text: 并发访问属于同一未同步数据依赖时先处理正确性
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: alternative_1
  text: problem.ub_bank_conflict：同Repeat操作数冲突可在没有MTE时出现；检查：用无MTE计算窗口与并发窗口对照
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: alternative_2
  text: problem.pipeline_serialization：完全缺少重叠不能直接支持重叠争用；检查：核对双方是否真实同时在执行
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: intervention
  text: 调整合法独立访问的发射相位、buffer布局或资源分担。代价：可能牺牲重叠并增加总等待；更多buffer或padding会占用容量
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
- id: optional_discriminating_intervention
  text: 可选判别实验：在原硬前提满足且C2允许的单独候选中，保持工作量而仅错开独立MTE/Vector发射或调整合法布局，比较并发冲突、等待与总时长。该实验用于区分争用，结果可支持或反证；S不要求先执行或获得收益。
  basis: mechanism_inference
  source_indexes: *id001
  review_status: gap
  limitations:
  - 实验需独立候选及原A硬前提，未执行不影响当前S；实验无论改善、无效或退化都可形成后继证据
review:
  state: gap
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 把Vector内部bank冲突与MTE并发冲突分开；检查冲突计数分母和实际重叠区间，比较总Task Duration；冲突计数缺失或仅见同时执行，不能确认争用
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。
analysis:
  mechanism_chain:
  - 搬运和Vector在重叠窗口争用同一片上资源或端口
  - 重叠使仲裁/等待增多而非隐藏延迟
  - 总时长受共享资源吞吐限制
  objects_and_stages:
  - 同一UB或片上通路上的并发MTE与Vector访问
  - kernel搬运与计算重叠窗口
  predictions:
  - 改变独立访问的相位或资源布局可能降低冲突，但减少重叠也可能变慢；这是prediction
  supporting_checks:
  - 把Vector内部bank冲突与MTE并发冲突分开
  - 检查冲突计数分母和实际重叠区间，比较总Task Duration
  - 可选判别实验：在原硬前提满足且C2允许的单独候选中，保持工作量而仅错开独立MTE/Vector发射或调整合法布局，比较并发冲突、等待与总时长。该实验用于区分争用，结果可支持或反证；S不要求先执行或获得收益。
  counter_checks:
  - 冲突计数缺失或仅见同时执行，不能确认争用
  - 并发访问属于同一未同步数据依赖时先处理正确性
  alternatives:
  - problem_id: problem.ub_bank_conflict
    distinction: 同Repeat操作数冲突可在没有MTE时出现
    check: 用无MTE计算窗口与并发窗口对照
  - problem_id: problem.pipeline_serialization
    distinction: 完全缺少重叠不能直接支持重叠争用
    check: 核对双方是否真实同时在执行
  actions:
  - action_id: action.stagger_resource_access
    intervention: 调整合法独立访问的发射相位、buffer布局或资源分担
    requirements:
    - symptom.source.transfer_compute_contention=true
    - constraint.dependency_lifetime=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 可能牺牲重叠并增加总等待
    - 更多buffer或padding会占用容量
  limits:
  - 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
  - 目标计数器或通路语义未核对时保持假设
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 搬运和计算竞争片上资源

## 对象、阶段与适用域

- 同一UB或片上通路上的并发MTE与Vector访问
- kernel搬运与计算重叠窗口

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 搬运和Vector在重叠窗口争用同一片上资源或端口
- 重叠使仲裁/等待增多而非隐藏延迟
- 总时长受共享资源吞吐限制

## 预测、支持检查与反证

- 改变独立访问的相位或资源布局可能降低冲突，但减少重叠也可能变慢；这是prediction
- 把Vector内部bank冲突与MTE并发冲突分开
- 检查冲突计数分母和实际重叠区间，比较总Task Duration
- 冲突计数缺失或仅见同时执行，不能确认争用
- 并发访问属于同一未同步数据依赖时先处理正确性

## 具体替代解释

- problem.ub_bank_conflict：同Repeat操作数冲突可在没有MTE时出现；检查：用无MTE计算窗口与并发窗口对照
- problem.pipeline_serialization：完全缺少重叠不能直接支持重叠争用；检查：核对双方是否真实同时在执行

## 候选动作与成本

action.stagger_resource_access：调整合法独立访问的发射相位、buffer布局或资源分担。

原硬前提：symptom.source.transfer_compute_contention=true；constraint.dependency_lifetime=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 可能牺牲重叠并增加总等待
- 更多buffer或padding会占用容量

## 限制与缺口

- 来源对布局与流水耦合提供原理，未给本任务并发冲突实测
- 目标计数器或通路语义未核对时保持假设
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 可选干预判别（非S前提）

可选判别实验：在原硬前提满足且C2允许的单独候选中，保持工作量而仅错开独立MTE/Vector发射或调整合法布局，比较并发冲突、等待与总时长。该实验用于区分争用，结果可支持或反证；S不要求先执行或获得收益。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：搬运和计算竞争片上资源；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### mechanism_1 [mechanism_inference]

搬运和Vector在重叠窗口争用同一片上资源或端口

来源索引：1, 2, 3, 4, 5。限制：来源对布局与流水耦合提供原理，未给本任务并发冲突实测；目标计数器或通路语义未核对时保持假设；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### mechanism_2 [mechanism_inference]

重叠使仲裁/等待增多而非隐藏延迟

来源索引：1, 2, 3, 4, 5。限制：来源对布局与流水耦合提供原理，未给本任务并发冲突实测；目标计数器或通路语义未核对时保持假设；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### mechanism_3 [mechanism_inference]

总时长受共享资源吞吐限制

来源索引：1, 2, 3, 4, 5。限制：来源对布局与流水耦合提供原理，未给本任务并发冲突实测；目标计数器或通路语义未核对时保持假设；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### prediction_1 [mechanism_inference]

改变独立访问的相位或资源布局可能降低冲突，但减少重叠也可能变慢；这是prediction

来源索引：1, 2, 3, 4, 5。限制：尚无同scope profiling验证，不标为observed或case_support；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### check_1 [mechanism_inference]

把Vector内部bank冲突与MTE并发冲突分开

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### check_2 [mechanism_inference]

检查冲突计数分母和实际重叠区间，比较总Task Duration

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### check_3 [mechanism_inference]

冲突计数缺失或仅见同时执行，不能确认争用

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### check_4 [mechanism_inference]

并发访问属于同一未同步数据依赖时先处理正确性

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### alternative_1 [mechanism_inference]

problem.ub_bank_conflict：同Repeat操作数冲突可在没有MTE时出现；检查：用无MTE计算窗口与并发窗口对照

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### alternative_2 [mechanism_inference]

problem.pipeline_serialization：完全缺少重叠不能直接支持重叠争用；检查：核对双方是否真实同时在执行

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### intervention [mechanism_inference]

调整合法独立访问的发射相位、buffer布局或资源分担。代价：可能牺牲重叠并增加总等待；更多buffer或padding会占用容量

来源索引：1, 2, 3, 4, 5。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划；固定新来源说明bank访问与流水重叠，但没有直接核验本机制的目标Vector-MTE计数器语义或同scope争用案例；保留条件推导，需硬件文档/任务profile补证。

### optional_discriminating_intervention [mechanism_inference]

可选判别实验：在原硬前提满足且C2允许的单独候选中，保持工作量而仅错开独立MTE/Vector发射或调整合法布局，比较并发冲突、等待与总时长。该实验用于区分争用，结果可支持或反证；S不要求先执行或获得收益。

来源索引：1, 2, 3, 4, 5。限制：实验需独立候选及原A硬前提，未执行不影响当前S；实验无论改善、无效或退化都可形成后继证据
