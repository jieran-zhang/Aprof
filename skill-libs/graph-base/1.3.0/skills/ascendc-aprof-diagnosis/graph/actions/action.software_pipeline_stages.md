---
schema_version: aprof.diagnosis-record/v1
id: action.software_pipeline_stages
kind: action
version: 1.1.0
status: active
title: 重排软件流水阶段
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
  - 17
  - 30
  sha256: sha256:106abe2ae5d0fde1eebe08e995949c674b633584eb1277b828382a132863c50c
  excerpt_sha256: sha256:0ddacaf1380e88c73e90e584cab87eae3ed42968a03b49110ab1d3ce6737a98e
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
transformation: 重排软件流水阶段
preconditions:
- fact: symptom.profile.overlap_low
  state: true
- fact: symptom.source.serial_queue_or_event_order
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
- fact: constraint.dependency_lifetime
  state: true
invariants:
- 算子语义与精度要求保持
- 有效写回无重叠且覆盖完整
- 资源与依赖约束经核验
expected_effect: 由机制相关指标和统一计时共同核验；不承诺收益。
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
  text: '原种子：重排软件流水阶段；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: intervention
  text: 为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环
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
- id: costs
  text: 更多物理buffer和事件ID；增加序言/尾声与尾块分支复杂度，短任务可能付不起成本
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 把timeline按tile而非聚合比例展开，检查首轮预置和末轮释放；核对双buffer是否物理独立及容量能同时容纳；稳定同对象窗口已持续重叠，反证完全串行解释
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - num=2不等于实际重叠成立
  - 不复制来源80%等重叠率或收益为目标承诺
instantiation:
  target_slots:
  - target
  - stage
  - workload
  - implementation
  required_bindings:
  - target
  - stage
  - workload
  - implementation
  effect: 为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环；预期变化仅为prediction：合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction
  costs:
  - 更多物理buffer和事件ID
  - 增加序言/尾声与尾块分支复杂度，短任务可能付不起成本
  unknown_policy: 任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 重排软件流水阶段

## 变换与作用对象

为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环。

多个tile的CopyIn/Compute/CopyOut及其buffer事件链；阶段：kernel预取序言；稳态tile循环；排空尾声。

## 实例绑定与原硬前提

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。未知信息不从样例常量或聊天推断。

- target
- stage
- workload
- implementation

- symptom.profile.overlap_low=true
- symptom.source.serial_queue_or_event_order=true
- constraint.semantic_equivalence=true
- constraint.capacity=true
- constraint.dependency_lifetime=true

原invariants：算子语义与精度要求保持；有效写回无重叠且覆盖完整；资源与依赖约束经核验。

## 预期效果与代价

为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环；预期变化仅为prediction：合法软件流水应增加稳态重叠，但总时长仍取决于最慢阶段；这是prediction

- 更多物理buffer和事件ID
- 增加序言/尾声与尾块分支复杂度，短任务可能付不起成本

## 未知与返回规划

任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- num=2不等于实际重叠成立
- 不复制来源80%等重叠率或收益为目标承诺

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：重排软件流水阶段；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### intervention [mechanism_inference]

为合法独立tile建立预取/计算/写回软件流水并配齐事件闭环

来源索引：1, 2, 3, 4, 5, 6。限制：num=2不等于实际重叠成立；不复制来源80%等重叠率或收益为目标承诺

### costs [mechanism_inference]

更多物理buffer和事件ID；增加序言/尾声与尾块分支复杂度，短任务可能付不起成本

来源索引：1, 2, 3, 4, 5, 6。限制：代价需要绑定具体候选量化，尚无本任务收益
