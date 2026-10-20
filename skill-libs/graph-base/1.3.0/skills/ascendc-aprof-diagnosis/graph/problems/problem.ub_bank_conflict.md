---
schema_version: aprof.diagnosis-record/v1
id: problem.ub_bank_conflict
kind: problem
version: 1.1.0
status: active
title: UB 布局引起 bank 冲突
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
  - 58
  - 64
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:8e89ada79f00c47215a93a0214ab24ee0e350adcc21bccb8cb2f914aa98750db
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
  bias: 0
tags:
- api_algorithm
- onchip_memory
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 并发数据块按目标bank/group几何映射到冲突集合 → 硬件仲裁把部分访问串行化 → 同等有效向量工作需要更多周期
alternatives:
- problem.transfer_compute_contention：本项是Vector内部操作数冲突，后者含MTE与Vector同时访问；检查：拆分并发流水窗口与同Repeat地址
- problem.vector_api_fragmentation：指令粒度小也会周期高，但不要求bank冲突；检查：比较有效repeat分布与冲突计数
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
  text: '原种子：UB 布局引起 bank 冲突；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 并发数据块按目标bank/group几何映射到冲突集合
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  review_status: reviewed
  limitations:
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
- id: mechanism_2
  text: 硬件仲裁把部分访问串行化
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
- id: mechanism_3
  text: 同等有效向量工作需要更多周期
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
- id: prediction_1
  text: 按目标映射错开地址或stride可降低冲突；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 分别判断读写、写写、读读，不能把同一group一概视为冲突
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 固定有效元素、mask与指令路径比较padding或stride
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 不同时间访问同bank不构成本机制
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 没有目标几何或实际地址时只能保留风险，不能认定冲突
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.transfer_compute_contention：本项是Vector内部操作数冲突，后者含MTE与Vector同时访问；检查：拆分并发流水窗口与同Repeat地址
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.vector_api_fragmentation：指令粒度小也会周期高，但不要求bank冲突；检查：比较有效repeat分布与冲突计数
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 根据目标真实映射增加最小padding或改变合法UB布局。代价：padding占用片上容量并可能增加搬运；布局变化需同步修改stride、mask和容量模型
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
- id: optional_discriminating_intervention
  text: 可选判别实验：在原硬前提满足且C2允许的单独候选中，仅调整合法UB布局/padding，保持有效工作、dtype、mask与指令路径可比，观察冲突及周期是否按预测变化。此实验不属于S成立的必要条件，也不预先要求改善。
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 实验需独立候选及原A硬前提，未执行不影响当前S；实验无论改善、无效或退化都可形成后继证据
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 分别判断读写、写写、读读，不能把同一group一概视为冲突；固定有效元素、mask与指令路径比较padding或stride；不同时间访问同bank不构成本机制
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
analysis:
  mechanism_chain:
  - 并发数据块按目标bank/group几何映射到冲突集合
  - 硬件仲裁把部分访问串行化
  - 同等有效向量工作需要更多周期
  objects_and_stages:
  - 同一Vector Repeat并发访问的src/dst地址与stride
  - kernel UB布局
  - Vector执行同一Repeat
  predictions:
  - 按目标映射错开地址或stride可降低冲突；这是prediction
  supporting_checks:
  - 分别判断读写、写写、读读，不能把同一group一概视为冲突
  - 固定有效元素、mask与指令路径比较padding或stride
  - 可选判别实验：在原硬前提满足且C2允许的单独候选中，仅调整合法UB布局/padding，保持有效工作、dtype、mask与指令路径可比，观察冲突及周期是否按预测变化。此实验不属于S成立的必要条件，也不预先要求改善。
  counter_checks:
  - 不同时间访问同bank不构成本机制
  - 没有目标几何或实际地址时只能保留风险，不能认定冲突
  alternatives:
  - problem_id: problem.transfer_compute_contention
    distinction: 本项是Vector内部操作数冲突，后者含MTE与Vector同时访问
    check: 拆分并发流水窗口与同Repeat地址
  - problem_id: problem.vector_api_fragmentation
    distinction: 指令粒度小也会周期高，但不要求bank冲突
    check: 比较有效repeat分布与冲突计数
  actions:
  - action_id: action.pad_ub_layout
    intervention: 根据目标真实映射增加最小padding或改变合法UB布局
    requirements:
    - symptom.profile.ub_conflict_high=true
    - symptom.source.ub_stride_conflict_risk=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - padding占用片上容量并可能增加搬运
    - 布局变化需同步修改stride、mask和容量模型
  limits:
  - arch22与arch35读读条件不同，禁止互用固定padding和几何
  - 通用冲突字段必须映射到目标后端实际计数器
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# UB 布局引起 bank 冲突

## 对象、阶段与适用域

- 同一Vector Repeat并发访问的src/dst地址与stride
- kernel UB布局
- Vector执行同一Repeat

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 并发数据块按目标bank/group几何映射到冲突集合
- 硬件仲裁把部分访问串行化
- 同等有效向量工作需要更多周期

## 预测、支持检查与反证

- 按目标映射错开地址或stride可降低冲突；这是prediction
- 分别判断读写、写写、读读，不能把同一group一概视为冲突
- 固定有效元素、mask与指令路径比较padding或stride
- 不同时间访问同bank不构成本机制
- 没有目标几何或实际地址时只能保留风险，不能认定冲突

## 具体替代解释

- problem.transfer_compute_contention：本项是Vector内部操作数冲突，后者含MTE与Vector同时访问；检查：拆分并发流水窗口与同Repeat地址
- problem.vector_api_fragmentation：指令粒度小也会周期高，但不要求bank冲突；检查：比较有效repeat分布与冲突计数

## 候选动作与成本

action.pad_ub_layout：根据目标真实映射增加最小padding或改变合法UB布局。

原硬前提：symptom.profile.ub_conflict_high=true；symptom.source.ub_stride_conflict_risk=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- padding占用片上容量并可能增加搬运
- 布局变化需同步修改stride、mask和容量模型

## 限制与缺口

- arch22与arch35读读条件不同，禁止互用固定padding和几何
- 通用冲突字段必须映射到目标后端实际计数器
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 可选干预判别（非S前提）

可选判别实验：在原硬前提满足且C2允许的单独候选中，仅调整合法UB布局/padding，保持有效工作、dtype、mask与指令路径可比，观察冲突及周期是否按预测变化。此实验不属于S成立的必要条件，也不预先要求改善。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：UB 布局引起 bank 冲突；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_bank [source_statement]

arch22文档按同一Repeat的并发读写及bank/group映射判断冲突，并明确不同芯片的规则有差异。

来源索引：1。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### mechanism_1 [mechanism_inference]

并发数据块按目标bank/group几何映射到冲突集合

来源索引：1, 2, 3。限制：arch22与arch35读读条件不同，禁止互用固定padding和几何；通用冲突字段必须映射到目标后端实际计数器

### mechanism_2 [mechanism_inference]

硬件仲裁把部分访问串行化

来源索引：1, 2, 3。限制：arch22与arch35读读条件不同，禁止互用固定padding和几何；通用冲突字段必须映射到目标后端实际计数器

### mechanism_3 [mechanism_inference]

同等有效向量工作需要更多周期

来源索引：1, 2, 3。限制：arch22与arch35读读条件不同，禁止互用固定padding和几何；通用冲突字段必须映射到目标后端实际计数器

### prediction_1 [mechanism_inference]

按目标映射错开地址或stride可降低冲突；这是prediction

来源索引：1, 2, 3。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

分别判断读写、写写、读读，不能把同一group一概视为冲突

来源索引：1, 2, 3。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

固定有效元素、mask与指令路径比较padding或stride

来源索引：1, 2, 3。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

不同时间访问同bank不构成本机制

来源索引：1, 2, 3。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

没有目标几何或实际地址时只能保留风险，不能认定冲突

来源索引：1, 2, 3。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.transfer_compute_contention：本项是Vector内部操作数冲突，后者含MTE与Vector同时访问；检查：拆分并发流水窗口与同Repeat地址

来源索引：1, 2, 3。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.vector_api_fragmentation：指令粒度小也会周期高，但不要求bank冲突；检查：比较有效repeat分布与冲突计数

来源索引：1, 2, 3。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

根据目标真实映射增加最小padding或改变合法UB布局。代价：padding占用片上容量并可能增加搬运；布局变化需同步修改stride、mask和容量模型

来源索引：1, 2, 3。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划

### optional_discriminating_intervention [mechanism_inference]

可选判别实验：在原硬前提满足且C2允许的单独候选中，仅调整合法UB布局/padding，保持有效工作、dtype、mask与指令路径可比，观察冲突及周期是否按预测变化。此实验不属于S成立的必要条件，也不预先要求改善。

来源索引：1, 2, 3。限制：实验需独立候选及原A硬前提，未执行不影响当前S；实验无论改善、无效或退化都可形成后继证据
