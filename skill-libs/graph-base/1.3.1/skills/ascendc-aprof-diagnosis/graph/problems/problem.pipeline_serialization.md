---
schema_version: aprof.diagnosis-record/v1
id: problem.pipeline_serialization
kind: problem
version: 1.1.0
status: active
title: 搬运与计算串行
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: skills/ascendc-aprof-diagnosis/graph/history/provenance/skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  original_path: skills/aprof/optimization/references/pipeline-parallel-optimization-strategies.md
  revision: aprof-1.1.0-pre-governance:sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  lines:
  - 6
  - 15
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:592927cdbe10444156ea848793b8012a9def81eafd5c36dd4daf3e7a6e8bd5d5
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
  bias: 0
tags:
- pipeline_parallel
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断 → 生产消费依赖闭环没有留出下一tile预取窗口 → MTE、Vector或Cube顺次忙而其他流水等待
alternatives:
- problem.excessive_sync_scope：等待过宽可导致串行，但不重叠也可能来自真数据依赖；检查：列出等待覆盖的生产消费边和本可独立的部分
- problem.onchip_capacity_pressure：容量限制与事件安排是不同阻碍；检查：先重算峰值，再改事件或预取次序
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
  text: '原种子：搬运与计算串行；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断
  basis: mechanism_inference
  source_indexes: &id001
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
- id: mechanism_2
  text: 生产消费依赖闭环没有留出下一tile预取窗口
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
- id: mechanism_3
  text: MTE、Vector或Cube顺次忙而其他流水等待
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
- id: prediction_1
  text: 合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 把timeline按tile而非聚合比例展开，检查首轮预置和末轮释放
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 核对双buffer是否物理独立及容量能同时容纳
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 稳定同对象窗口已持续重叠，反证完全串行解释
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 单轮、容量不允许或算法真依赖禁止重叠时，不能建议强行加buffer
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.excessive_sync_scope：等待过宽可导致串行，但不重叠也可能来自真数据依赖；检查：列出等待覆盖的生产消费边和本可独立的部分
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.onchip_capacity_pressure：容量限制与事件安排是不同阻碍；检查：先重算峰值，再改事件或预取次序
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环。代价：更多物理buffer和事件ID；增加序言/尾声与尾块分支复杂度，短任务可能付不起成本
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 把timeline按tile而非聚合比例展开，检查首轮预置和末轮释放；核对双buffer是否物理独立及容量能同时容纳；稳定同对象窗口已持续重叠，反证完全串行解释
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
analysis:
  mechanism_chain:
  - 不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断
  - 生产消费依赖闭环没有留出下一tile预取窗口
  - MTE、Vector或Cube顺次忙而其他流水等待
  objects_and_stages:
  - 多个tile的CopyIn/Compute/CopyOut及其buffer事件链
  - kernel预取序言
  - 稳态tile循环
  - 排空尾声
  predictions:
  - 合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction
  supporting_checks:
  - 把timeline按tile而非聚合比例展开，检查首轮预置和末轮释放
  - 核对双buffer是否物理独立及容量能同时容纳
  counter_checks:
  - 稳定同对象窗口已持续重叠，反证完全串行解释
  - 单轮、容量不允许或算法真依赖禁止重叠时，不能建议强行加buffer
  alternatives:
  - problem_id: problem.excessive_sync_scope
    distinction: 等待过宽可导致串行，但不重叠也可能来自真数据依赖
    check: 列出等待覆盖的生产消费边和本可独立的部分
  - problem_id: problem.onchip_capacity_pressure
    distinction: 容量限制与事件安排是不同阻碍
    check: 先重算峰值，再改事件或预取次序
  actions:
  - action_id: action.software_pipeline_stages
    intervention: 为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环
    requirements:
    - symptom.profile.overlap_low=true
    - symptom.source.serial_queue_or_event_order=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    - constraint.dependency_lifetime=true
    costs:
    - 更多物理buffer和事件ID
    - 增加序言/尾声与尾块分支复杂度，短任务可能付不起成本
  limits:
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 搬运与计算串行

## 对象、阶段与适用域

- 多个tile的CopyIn/Compute/CopyOut及其buffer事件链
- kernel预取序言
- 稳态tile循环
- 排空尾声

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断
- 生产消费依赖闭环没有留出下一tile预取窗口
- MTE、Vector或Cube顺次忙而其他流水等待

## 预测、支持检查与反证

- 合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction
- 把timeline按tile而非聚合比例展开，检查首轮预置和末轮释放
- 核对双buffer是否物理独立及容量能同时容纳
- 稳定同对象窗口已持续重叠，反证完全串行解释
- 单轮、容量不允许或算法真依赖禁止重叠时，不能建议强行加buffer

## 具体替代解释

- problem.excessive_sync_scope：等待过宽可导致串行，但不重叠也可能来自真数据依赖；检查：列出等待覆盖的生产消费边和本可独立的部分
- problem.onchip_capacity_pressure：容量限制与事件安排是不同阻碍；检查：先重算峰值，再改事件或预取次序

## 候选动作与成本

action.software_pipeline_stages：为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环。

原硬前提：symptom.profile.overlap_low=true；symptom.source.serial_queue_or_event_order=true；constraint.semantic_equivalence=true；constraint.capacity=true；constraint.dependency_lifetime=true。

- 更多物理buffer和事件ID
- 增加序言/尾声与尾块分支复杂度，短任务可能付不起成本

## 限制与缺口

- num=2不等于实际重叠成立
- 不复制来源80%等重叠率或收益为目标承诺
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：搬运与计算串行；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### mechanism_1 [mechanism_inference]

不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断

来源索引：1, 2, 3, 4, 5, 6。限制：num=2不等于实际重叠成立；不复制来源80%等重叠率或收益为目标承诺

### mechanism_2 [mechanism_inference]

生产消费依赖闭环没有留出下一tile预取窗口

来源索引：1, 2, 3, 4, 5, 6。限制：num=2不等于实际重叠成立；不复制来源80%等重叠率或收益为目标承诺

### mechanism_3 [mechanism_inference]

MTE、Vector或Cube顺次忙而其他流水等待

来源索引：1, 2, 3, 4, 5, 6。限制：num=2不等于实际重叠成立；不复制来源80%等重叠率或收益为目标承诺

### prediction_1 [mechanism_inference]

合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction

来源索引：1, 2, 3, 4, 5, 6。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

把timeline按tile而非聚合比例展开，检查首轮预置和末轮释放

来源索引：1, 2, 3, 4, 5, 6。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

核对双buffer是否物理独立及容量能同时容纳

来源索引：1, 2, 3, 4, 5, 6。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

稳定同对象窗口已持续重叠，反证完全串行解释

来源索引：1, 2, 3, 4, 5, 6。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

单轮、容量不允许或算法真依赖禁止重叠时，不能建议强行加buffer

来源索引：1, 2, 3, 4, 5, 6。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.excessive_sync_scope：等待过宽可导致串行，但不重叠也可能来自真数据依赖；检查：列出等待覆盖的生产消费边和本可独立的部分

来源索引：1, 2, 3, 4, 5, 6。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.onchip_capacity_pressure：容量限制与事件安排是不同阻碍；检查：先重算峰值，再改事件或预取次序

来源索引：1, 2, 3, 4, 5, 6。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环。代价：更多物理buffer和事件ID；增加序言/尾声与尾块分支复杂度，短任务可能付不起成本

来源索引：1, 2, 3, 4, 5, 6。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
