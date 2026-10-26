---
schema_version: aprof.diagnosis-record/v1
id: problem.tiny_transfer_setup_amplification
kind: problem
version: 1.1.0
status: active
title: 小搬运放大发射开销
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
  - 46
  - 51
  sha256: sha256:7b5f46925a304a3d6db77c905675c8ecae3d12eeedeac501743bdc07f932d44e
  excerpt_sha256: sha256:a2be289520d72c7e7723e6d6dfb7fe1cde47c924097dfb4347c8a2e2fdaa3477
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
  bias: 0
tags:
- data_movement
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 循环把可合并的有效区间分成许多小DataCopy → 每次搬运重复支付参数构造、发射与同步固定成本 → 每指令有效字节偏低，使MTE忙而有效带宽仍低
alternatives:
- problem.memory_bandwidth_saturation：setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限；检查：同窗口比较有效字节、指令数、方向和校准带宽
- problem.noncontiguous_access：离散布局会增加实际事务；小包setup可在连续数据上出现；检查：固定stride检查每次有效大小与总事务放大量
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
  text: '原种子：小搬运放大发射开销；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 循环把可合并的有效区间分成许多小DataCopy
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
- id: mechanism_2
  text: 每次搬运重复支付参数构造、发射与同步固定成本
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
- id: mechanism_3
  text: 每指令有效字节偏低，使MTE忙而有效带宽仍低
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
- id: prediction_1
  text: 若仅合并合法相邻搬运，发射数应下降而算法有效字节不变；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: prediction_2
  text: MTE比例可能仍高，不能用比例下降作为唯一成功标准
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 把搬入、计算和等待按tile展开，检查是否有可合并的边界
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.memory_bandwidth_saturation：setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限；检查：同窗口比较有效字节、指令数、方向和校准带宽
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.noncontiguous_access：离散布局会增加实际事务；小包setup可在连续数据上出现；检查：固定stride检查每次有效大小与总事务放大量
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度。代价：更大UB/L1暂存与更长buffer生命周期；可能减少可并行任务或改变流水预取距离
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
- id: optional_discriminating_intervention
  text: 可选判别实验：在原硬前提满足且C2允许的单独候选中，仅合并合法搬运以缩减发射数，保持有效字节及地址语义，比较发射、等待与总时长。原实现timeline可先支持候选；S不要求该实验或成功收益。
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 实验需独立候选及原A硬前提，未执行不影响当前S；实验无论改善、无效或退化都可形成后继证据
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加；把搬入、计算和等待按tile展开，检查是否有可合并的边界；大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
analysis:
  mechanism_chain:
  - 循环把可合并的有效区间分成许多小DataCopy
  - 每次搬运重复支付参数构造、发射与同步固定成本
  - 每指令有效字节偏低，使MTE忙而有效带宽仍低
  objects_and_stages:
  - 同一tensor切片的搬入块、DMA发射点及所属tile循环
  - host计算tile和尾长
  - kernel内层CopyIn及等待
  predictions:
  - 若仅合并合法相邻搬运，发射数应下降而算法有效字节不变；这是prediction
  - MTE比例可能仍高，不能用比例下降作为唯一成功标准
  supporting_checks:
  - 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加
  - 把搬入、计算和等待按tile展开，检查是否有可合并的边界
  - 可选判别实验：在原硬前提满足且C2允许的单独候选中，仅合并合法搬运以缩减发射数，保持有效字节及地址语义，比较发射、等待与总时长。原实现timeline可先支持候选；S不要求该实验或成功收益。
  counter_checks:
  - 大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
  - 单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本
  alternatives:
  - problem_id: problem.memory_bandwidth_saturation
    distinction: setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限
    check: 同窗口比较有效字节、指令数、方向和校准带宽
  - problem_id: problem.noncontiguous_access
    distinction: 离散布局会增加实际事务；小包setup可在连续数据上出现
    check: 固定stride检查每次有效大小与总事务放大量
  actions:
  - action_id: action.coalesce_contiguous_transfers
    intervention: 合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度
    requirements:
    - symptom.profile.mte_setup_dominated=true
    - symptom.source.inner_loop_copy=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 更大UB/L1暂存与更长buffer生命周期
    - 可能减少可并行任务或改变流水预取距离
  limits:
  - 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
  - 当前任务没有采集数据，不能把文档样例收益写为本任务收益
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 小搬运放大发射开销

## 对象、阶段与适用域

- 同一tensor切片的搬入块、DMA发射点及所属tile循环
- host计算tile和尾长
- kernel内层CopyIn及等待

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 循环把可合并的有效区间分成许多小DataCopy
- 每次搬运重复支付参数构造、发射与同步固定成本
- 每指令有效字节偏低，使MTE忙而有效带宽仍低

## 预测、支持检查与反证

- 若仅合并合法相邻搬运，发射数应下降而算法有效字节不变；这是prediction
- MTE比例可能仍高，不能用比例下降作为唯一成功标准
- 用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加
- 把搬入、计算和等待按tile展开，检查是否有可合并的边界
- 大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降
- 单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本

## 具体替代解释

- problem.memory_bandwidth_saturation：setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限；检查：同窗口比较有效字节、指令数、方向和校准带宽
- problem.noncontiguous_access：离散布局会增加实际事务；小包setup可在连续数据上出现；检查：固定stride检查每次有效大小与总事务放大量

## 候选动作与成本

action.coalesce_contiguous_transfers：合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度。

原硬前提：symptom.profile.mte_setup_dominated=true；symptom.source.inner_loop_copy=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 更大UB/L1暂存与更长buffer生命周期
- 可能减少可并行任务或改变流水预取距离

## 限制与缺口

- 来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据
- 当前任务没有采集数据，不能把文档样例收益写为本任务收益
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 可选干预判别（非S前提）

可选判别实验：在原硬前提满足且C2允许的单独候选中，仅合并合法搬运以缩减发射数，保持有效字节及地址语义，比较发射、等待与总时长。原实现timeline可先支持候选；S不要求该实验或成功收益。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：小搬运放大发射开销；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### mechanism_1 [mechanism_inference]

循环把可合并的有效区间分成许多小DataCopy

来源索引：1, 2, 3, 4, 5。限制：来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据；当前任务没有采集数据，不能把文档样例收益写为本任务收益

### mechanism_2 [mechanism_inference]

每次搬运重复支付参数构造、发射与同步固定成本

来源索引：1, 2, 3, 4, 5。限制：来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据；当前任务没有采集数据，不能把文档样例收益写为本任务收益

### mechanism_3 [mechanism_inference]

每指令有效字节偏低，使MTE忙而有效带宽仍低

来源索引：1, 2, 3, 4, 5。限制：来源粒度阈值属于910B经验；其他型号不沿用固定256B/4KB判据；当前任务没有采集数据，不能把文档样例收益写为本任务收益

### prediction_1 [mechanism_inference]

若仅合并合法相邻搬运，发射数应下降而算法有效字节不变；这是prediction

来源索引：1, 2, 3, 4, 5。限制：尚无同scope profiling验证，不标为observed或case_support

### prediction_2 [mechanism_inference]

MTE比例可能仍高，不能用比例下降作为唯一成功标准

来源索引：1, 2, 3, 4, 5。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

用有效字节/指令数与传输大小分布定位频繁小包，区分总流量增加

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

把搬入、计算和等待按tile展开，检查是否有可合并的边界

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

大块连续传输已接近校准带宽上限时，本机制对该稳态窗口解释力下降

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

单次全载或全局依赖不允许合并时，不能据小包数量推出可消除成本

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.memory_bandwidth_saturation：setup受限预期有效带宽低；带宽饱和要求接近同平台可达上限；检查：同窗口比较有效字节、指令数、方向和校准带宽

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.noncontiguous_access：离散布局会增加实际事务；小包setup可在连续数据上出现；检查：固定stride检查每次有效大小与总事务放大量

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

合并合法相邻块或批量表达多段搬运，保持源/目标地址映射和尾部有效长度。代价：更大UB/L1暂存与更长buffer生命周期；可能减少可并行任务或改变流水预取距离

来源索引：1, 2, 3, 4, 5。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划

### optional_discriminating_intervention [mechanism_inference]

可选判别实验：在原硬前提满足且C2允许的单独候选中，仅合并合法搬运以缩减发射数，保持有效字节及地址语义，比较发射、等待与总时长。原实现timeline可先支持候选；S不要求该实验或成功收益。

来源索引：1, 2, 3, 4, 5。限制：实验需独立候选及原A硬前提，未执行不影响当前S；实验无论改善、无效或退化都可形成后继证据
