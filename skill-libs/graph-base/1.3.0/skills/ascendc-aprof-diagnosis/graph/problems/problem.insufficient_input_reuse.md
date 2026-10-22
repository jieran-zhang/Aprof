---
schema_version: aprof.diagnosis-record/v1
id: problem.insufficient_input_reuse
kind: problem
version: 1.1.0
status: active
title: 重复输入未复用
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
  bias: 0
tags:
- data_movement
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 同一地址和内容在复用窗口被重复从GM读入 → 片上或缓存复用机会未被利用 → 重复读增加GM/MTE成本；若进入关键路径则可能拖慢调用
alternatives:
- problem.cache_policy_mismatch：软件重复copy与L2替换造成的miss是不同层次；检查：结合GM读取口径与具体cache hint、复用距离
- problem.l1_l0_reuse_deficit：本项主看GM输入，后者主看矩阵片内L1→L0重复；检查：分层记录GM→L1/UB、L1→L0字节
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
  text: '原种子：重复输入未复用；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: mechanism_1
  text: 同一地址和内容在复用窗口被重复从GM读入
  basis: mechanism_inference
  source_indexes: &id001
  - 1
  - 2
  - 3
  - 4
  - 5
  review_status: reviewed
  limitations:
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
- id: mechanism_2
  text: 片上或缓存复用机会未被利用
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
- id: mechanism_3
  text: 重复读增加GM/MTE成本；若进入关键路径则可能拖慢调用
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
- id: prediction_1
  text: 在容量允许的窗口保留输入后GM读取次数应减少；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.cache_policy_mismatch：软件重复copy与L2替换造成的miss是不同层次；检查：结合GM读取口径与具体cache hint、复用距离
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.l1_l0_reuse_deficit：本项主看GM输入，后者主看矩阵片内L1→L0重复；检查：分层记录GM→L1/UB、L1→L0字节
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 在有效复用窗口保留输入，或调整tile顺序增加合法局部复用。代价：增加常驻UB/L1容量；可能缩小tile或减少流水buffer并拉长生命周期
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据；比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省；循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
analysis:
  mechanism_chain:
  - 同一地址和内容在复用窗口被重复从GM读入
  - 片上或缓存复用机会未被利用
  - 重复读增加GM/MTE成本；若进入关键路径则可能拖慢调用
  objects_and_stages:
  - 跨tile/迭代保持不变的输入切片
  - host tile顺序与分核
  - kernel CopyIn及片上驻留期
  predictions:
  - 在容量允许的窗口保留输入后GM读取次数应减少；这是prediction
  supporting_checks:
  - 按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据
  - 比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省
  counter_checks:
  - 循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
  - 驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用
  alternatives:
  - problem_id: problem.cache_policy_mismatch
    distinction: 软件重复copy与L2替换造成的miss是不同层次
    check: 结合GM读取口径与具体cache hint、复用距离
  - problem_id: problem.l1_l0_reuse_deficit
    distinction: 本项主看GM输入，后者主看矩阵片内L1→L0重复
    check: 分层记录GM→L1/UB、L1→L0字节
  actions:
  - action_id: action.reuse_input_tiles
    intervention: 在有效复用窗口保留输入，或调整tile顺序增加合法局部复用
    requirements:
    - symptom.source.insufficient_input_reuse=true
    - constraint.reuse_domain=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 增加常驻UB/L1容量
    - 可能缩小tile或减少流水buffer并拉长生命周期
  limits:
  - 常驻需要目标平台容量及同步证明
  - arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 重复输入未复用

## 对象、阶段与适用域

- 跨tile/迭代保持不变的输入切片
- host tile顺序与分核
- kernel CopyIn及片上驻留期

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 同一地址和内容在复用窗口被重复从GM读入
- 片上或缓存复用机会未被利用
- 重复读增加GM/MTE成本；若进入关键路径则可能拖慢调用

## 预测、支持检查与反证

- 在容量允许的窗口保留输入后GM读取次数应减少；这是prediction
- 按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据
- 比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省
- 循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力
- 驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用

## 具体替代解释

- problem.cache_policy_mismatch：软件重复copy与L2替换造成的miss是不同层次；检查：结合GM读取口径与具体cache hint、复用距离
- problem.l1_l0_reuse_deficit：本项主看GM输入，后者主看矩阵片内L1→L0重复；检查：分层记录GM→L1/UB、L1→L0字节

## 候选动作与成本

action.reuse_input_tiles：在有效复用窗口保留输入，或调整tile顺序增加合法局部复用。

原硬前提：symptom.source.insufficient_input_reuse=true；constraint.reuse_domain=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 增加常驻UB/L1容量
- 可能缩小tile或减少流水buffer并拉长生命周期

## 限制与缺口

- 常驻需要目标平台容量及同步证明
- arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：重复输入未复用；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_resident [source_statement]

arch35文档区分跨迭代常驻与串行阶段分时复用，并要求重叠流水发生变化时重算生命周期。

来源索引：1, 2。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mm_reuse [source_statement]

arch22 MatMul文档要求先核算M/N任务与最长核，再比较Split-K归并；驻留必须证明地址不变、复用次数和容量。

来源索引：3, 4, 5。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### mechanism_1 [mechanism_inference]

同一地址和内容在复用窗口被重复从GM读入

来源索引：1, 2, 3, 4, 5。限制：常驻需要目标平台容量及同步证明；arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号

### mechanism_2 [mechanism_inference]

片上或缓存复用机会未被利用

来源索引：1, 2, 3, 4, 5。限制：常驻需要目标平台容量及同步证明；arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号

### mechanism_3 [mechanism_inference]

重复读增加GM/MTE成本；若进入关键路径则可能拖慢调用

来源索引：1, 2, 3, 4, 5。限制：常驻需要目标平台容量及同步证明；arch35常驻文档仅提供原则，不能搬用其bank几何到其他型号

### prediction_1 [mechanism_inference]

在容量允许的窗口保留输入后GM读取次数应减少；这是prediction

来源索引：1, 2, 3, 4, 5。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

按重复地址集合计算unique bytes，区分真正复用与相同shape不同数据

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

比较驻留占用与原有双缓冲，确认不会以失去重叠抵消节省

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

循环每次读取内容不同或实际L2已命中且无关键路径成本则降低解释力

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

驻留数据跨核共享但缺少合法可见性时，不能把本地保留当全局复用

来源索引：1, 2, 3, 4, 5。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.cache_policy_mismatch：软件重复copy与L2替换造成的miss是不同层次；检查：结合GM读取口径与具体cache hint、复用距离

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.l1_l0_reuse_deficit：本项主看GM输入，后者主看矩阵片内L1→L0重复；检查：分层记录GM→L1/UB、L1→L0字节

来源索引：1, 2, 3, 4, 5。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

在有效复用窗口保留输入，或调整tile顺序增加合法局部复用。代价：增加常驻UB/L1容量；可能缩小tile或减少流水buffer并拉长生命周期

来源索引：1, 2, 3, 4, 5。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
