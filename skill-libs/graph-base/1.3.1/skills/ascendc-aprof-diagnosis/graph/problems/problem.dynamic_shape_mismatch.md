---
schema_version: aprof.diagnosis-record/v1
id: problem.dynamic_shape_mismatch
kind: problem
version: 1.1.0
status: active
title: 固定策略未适配动态 shape
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 71
  - 71
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:ce7b8db8872e68fc98b2f9aa70bcc82cd14ad59da0027fbfdabba1be7708f744
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 74
  - 74
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:cdedaa2452701b501d11be72749d2d3d5f22a842c4bbab1b2cef6b73af7375fd
- path: skills/ascendc-aprof-diagnosis/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_host/squared_relu_tiling.cpp
  original_path: activation/squared_relu/op_host/squared_relu_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 58
  - 69
  sha256: sha256:697c6defba0cef026c0f4a803516acf04e3addb7fd8eab135024febbd505d477
  excerpt_sha256: sha256:cc203313bc5693b288c961988a2930fea55e360f862103df07fc5bfa75fb40ea
- path: skills/ascendc-aprof-diagnosis/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_host/squared_relu_tiling.cpp
  original_path: activation/squared_relu/op_host/squared_relu_tiling.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 85
  - 117
  sha256: sha256:697c6defba0cef026c0f4a803516acf04e3addb7fd8eab135024febbd505d477
  excerpt_sha256: sha256:c8e368c5e7706efd805125f26a48cf929e67e298669d2ba060bf6bfa5d35c7b0
- path: skills/ascendc-aprof-diagnosis/sources/ops-nn/8b42e125134fa9abf1e42a67e6b2792f78c26be5/activation/squared_relu/op_kernel/squared_relu.cpp
  original_path: activation/squared_relu/op_kernel/squared_relu.cpp
  revision: 8b42e125134fa9abf1e42a67e6b2792f78c26be5
  lines:
  - 22
  - 44
  sha256: sha256:fec0dbec3c56df4d0351baa8c88deedf837558871a02491f0c425ad3ca33b6a8
  excerpt_sha256: sha256:1e067bfc4b52db7c3bab513dcd4afff4709b4b515d22ee11bd69c2a192dd8bf5
- path: skills/ascendc-aprof-diagnosis/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/tiling/matmul_tiling_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/tiling/matmul_tiling_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 35
  - 43
  sha256: sha256:32fa438fe9654c9fa9210404f7fc8917b6cc6a954517c8386ff0a3aef5b71084
  excerpt_sha256: sha256:da61bb225afe87724fbce9a4428bb7e22516a8695fbc1e0075b96d5cbdb64e8a
- path: skills/ascendc-aprof-diagnosis/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/tiling/matmul_tiling_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/tiling/matmul_tiling_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 51
  - 96
  sha256: sha256:32fa438fe9654c9fa9210404f7fc8917b6cc6a954517c8386ff0a3aef5b71084
  excerpt_sha256: sha256:dcb2cdc75345c6cd4d90e767379a9ecd147e6cb267ad31e9fde976052e1743f7
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 18
  - 33
  sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
  excerpt_sha256: sha256:f4d5ee6d43583e164553d6e72c11d144adc5e7dbb966c702ca18e8ec2a8a7b78
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 35
  - 71
  sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
  excerpt_sha256: sha256:dc896cfcbfffa7de6bc4d9b2f1eb4c536716f35f29689acb633887f4b086cdbc
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  original_path: ops/ascendc-performance-best-practices/references/flash_attention/arch22/tiling_pipeline_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 73
  - 101
  sha256: sha256:ea3be814234904a2d8a4a3b99847aec00c849f3fb3ce2647390a3dce0a734ba1
  excerpt_sha256: sha256:f5378d0c338c8fa65447c183c9d1bc14ac0c887e5159d9e5eab387d8836ae12f
learning:
  bias: 0
tags:
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 一套核数、tile、buffer或workspace覆盖不同资源主导区间 → 小shape付出不必要固定成本，大shape欠并行或流量/容量不适配 → 不同区间出现不同退化，需要条件化dispatch而非固定最优值
alternatives:
- problem.underused_task_parallelism：欠并行是某一区间的可能表现，不等于需要全局新dispatch；检查：对比小大shape的独立任务数
- problem.workspace_overallocation：workspace最大shape预留是单项资源问题，可在现dispatch内修正；检查：比较runtime shape、实际槽位与分支覆盖
slots:
- name: target
  kind: object
  description: 同一算子多个shape/dtype/feature区间的dispatch及参数域
  required: true
- name: stage
  kind: stage
  description: host shape归类与TilingKey；kernel模板/运行时分支
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
  text: '原种子：固定策略未适配动态 shape；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  - 1
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_relu_host
  text: SquaredRelu host读取dtype和输入shape，查询AIV核数并设置needCoreNum、tiling key与BlockDim；这些是该算子代码事实。
  basis: code_fact
  source_indexes:
  - 2
  - 3
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_relu_kernel
  text: SquaredRelu kernel入口按tiling key及编译架构选择half/float/bfloat16模板；此入口不足以证明下层Process的workspace使用或性能。
  basis: code_fact
  source_indexes:
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_sk_tiling
  text: StreamK tiling实现对K长度、M/N任务和平台核数做能力检查，并单独计算workspace；阈值属于该实现。
  basis: code_fact
  source_indexes:
  - 5
  - 6
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_fa_pipe
  text: arch22 FA文档联合评估tile、AIC/AIV核数、buffer深度、workspace与局部/跨核同步，并比较Split-KV节省路径和归并成本。
  basis: source_statement
  source_indexes:
  - 7
  - 8
  - 9
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: mechanism_1
  text: 一套核数、tile、buffer或workspace覆盖不同资源主导区间
  basis: mechanism_inference
  source_indexes: &id001
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  - 9
  review_status: reviewed
  limitations:
  - 不把来源阈值硬编码为目标最优边界
  - SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
- id: mechanism_2
  text: 小shape付出不必要固定成本，大shape欠并行或流量/容量不适配
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 不把来源阈值硬编码为目标最优边界
  - SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
- id: mechanism_3
  text: 不同区间出现不同退化，需要条件化dispatch而非固定最优值
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 不把来源阈值硬编码为目标最优边界
  - SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
- id: prediction_1
  text: 有依据的区间派发可能分别缓解小任务开销与大任务资源约束；这是prediction
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 尚无同scope profiling验证，不标为observed或case_support
- id: check_1
  text: 按相邻边界shape核验coverage、唯一分支和fallback
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_2
  text: 比较每区间机制，再决定是否需要新参数或方案，不能按shape数量造分支
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_3
  text: 现dispatch已经区分机制所需区间且退化是单一布局错误时不支持过度特化
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: check_4
  text: 样例key仅按dtype区分不能证明通用shape阈值
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 这是判别程序定义，执行结果由任务证据填充
- id: alternative_1
  text: problem.underused_task_parallelism：欠并行是某一区间的可能表现，不等于需要全局新dispatch；检查：对比小大shape的独立任务数
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: alternative_2
  text: problem.workspace_overallocation：workspace最大shape预留是单项资源问题，可在现dispatch内修正；检查：比较runtime shape、实际槽位与分支覆盖
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 替代机制可在不同对象或窗口并存，不是互斥分类
- id: intervention
  text: 按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback。代价：代码/编译体积和边界测试成本；新增区间可能改变计划dispatch域，须C2确认
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按相邻边界shape核验coverage、唯一分支和fallback；比较每区间机制，再决定是否需要新参数或方案，不能按shape数量造分支；现dispatch已经区分机制所需区间且退化是单一布局错误时不支持过度特化
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 不把来源阈值硬编码为目标最优边界
  - SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
analysis:
  mechanism_chain:
  - 一套核数、tile、buffer或workspace覆盖不同资源主导区间
  - 小shape付出不必要固定成本，大shape欠并行或流量/容量不适配
  - 不同区间出现不同退化，需要条件化dispatch而非固定最优值
  objects_and_stages:
  - 同一算子多个shape/dtype/feature区间的dispatch及参数域
  - host shape归类与TilingKey
  - kernel模板/运行时分支
  predictions:
  - 有依据的区间派发可能分别缓解小任务开销与大任务资源约束；这是prediction
  supporting_checks:
  - 按相邻边界shape核验coverage、唯一分支和fallback
  - 比较每区间机制，再决定是否需要新参数或方案，不能按shape数量造分支
  counter_checks:
  - 现dispatch已经区分机制所需区间且退化是单一布局错误时不支持过度特化
  - 样例key仅按dtype区分不能证明通用shape阈值
  alternatives:
  - problem_id: problem.underused_task_parallelism
    distinction: 欠并行是某一区间的可能表现，不等于需要全局新dispatch
    check: 对比小大shape的独立任务数
  - problem_id: problem.workspace_overallocation
    distinction: workspace最大shape预留是单项资源问题，可在现dispatch内修正
    check: 比较runtime shape、实际槽位与分支覆盖
  actions:
  - action_id: action.dispatch_by_workload
    intervention: 按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback
    requirements:
    - symptom.source.dynamic_shape_mismatch=true
    - constraint.dispatch_coverage=true
    - constraint.semantic_equivalence=true
    - constraint.capacity=true
    costs:
    - 代码/编译体积和边界测试成本
    - 新增区间可能改变计划dispatch域，须C2确认
  limits:
  - 不把来源阈值硬编码为目标最优边界
  - SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
  - 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。
---

# 固定策略未适配动态 shape

## 对象、阶段与适用域

- 同一算子多个shape/dtype/feature区间的dispatch及参数域
- host shape归类与TilingKey
- kernel模板/运行时分支

旧scope=all保留作检索范围，机制成立仍须核对目标架构、dtype、shape和API支持。

## 机制链

- 一套核数、tile、buffer或workspace覆盖不同资源主导区间
- 小shape付出不必要固定成本，大shape欠并行或流量/容量不适配
- 不同区间出现不同退化，需要条件化dispatch而非固定最优值

## 预测、支持检查与反证

- 有依据的区间派发可能分别缓解小任务开销与大任务资源约束；这是prediction
- 按相邻边界shape核验coverage、唯一分支和fallback
- 比较每区间机制，再决定是否需要新参数或方案，不能按shape数量造分支
- 现dispatch已经区分机制所需区间且退化是单一布局错误时不支持过度特化
- 样例key仅按dtype区分不能证明通用shape阈值

## 具体替代解释

- problem.underused_task_parallelism：欠并行是某一区间的可能表现，不等于需要全局新dispatch；检查：对比小大shape的独立任务数
- problem.workspace_overallocation：workspace最大shape预留是单项资源问题，可在现dispatch内修正；检查：比较runtime shape、实际槽位与分支覆盖

## 候选动作与成本

action.dispatch_by_workload：按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback。

原硬前提：symptom.source.dynamic_shape_mismatch=true；constraint.dispatch_coverage=true；constraint.semantic_equivalence=true；constraint.capacity=true。

- 代码/编译体积和边界测试成本
- 新增区间可能改变计划dispatch域，须C2确认

## 限制与缺口

- 不把来源阈值硬编码为目标最优边界
- SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
- 本轮无同任务profile、无case_support、无收益或发生频率声明；源码形态只支持待核验候选。

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：固定策略未适配动态 shape；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_relu_host [code_fact]

SquaredRelu host读取dtype和输入shape，查询AIV核数并设置needCoreNum、tiling key与BlockDim；这些是该算子代码事实。

来源索引：2, 3。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_relu_kernel [code_fact]

SquaredRelu kernel入口按tiling key及编译架构选择half/float/bfloat16模板；此入口不足以证明下层Process的workspace使用或性能。

来源索引：4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_sk_tiling [code_fact]

StreamK tiling实现对K长度、M/N任务和平台核数做能力检查，并单独计算workspace；阈值属于该实现。

来源索引：5, 6。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_fa_pipe [source_statement]

arch22 FA文档联合评估tile、AIC/AIV核数、buffer深度、workspace与局部/跨核同步，并比较Split-KV节省路径和归并成本。

来源索引：7, 8, 9。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### mechanism_1 [mechanism_inference]

一套核数、tile、buffer或workspace覆盖不同资源主导区间

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：不把来源阈值硬编码为目标最优边界；SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配

### mechanism_2 [mechanism_inference]

小shape付出不必要固定成本，大shape欠并行或流量/容量不适配

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：不把来源阈值硬编码为目标最优边界；SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配

### mechanism_3 [mechanism_inference]

不同区间出现不同退化，需要条件化dispatch而非固定最优值

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：不把来源阈值硬编码为目标最优边界；SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配

### prediction_1 [mechanism_inference]

有依据的区间派发可能分别缓解小任务开销与大任务资源约束；这是prediction

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：尚无同scope profiling验证，不标为observed或case_support

### check_1 [mechanism_inference]

按相邻边界shape核验coverage、唯一分支和fallback

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：这是判别程序定义，执行结果由任务证据填充

### check_2 [mechanism_inference]

比较每区间机制，再决定是否需要新参数或方案，不能按shape数量造分支

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：这是判别程序定义，执行结果由任务证据填充

### check_3 [mechanism_inference]

现dispatch已经区分机制所需区间且退化是单一布局错误时不支持过度特化

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：这是判别程序定义，执行结果由任务证据填充

### check_4 [mechanism_inference]

样例key仅按dtype区分不能证明通用shape阈值

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：这是判别程序定义，执行结果由任务证据填充

### alternative_1 [mechanism_inference]

problem.underused_task_parallelism：欠并行是某一区间的可能表现，不等于需要全局新dispatch；检查：对比小大shape的独立任务数

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### alternative_2 [mechanism_inference]

problem.workspace_overallocation：workspace最大shape预留是单项资源问题，可在现dispatch内修正；检查：比较runtime shape、实际槽位与分支覆盖

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：替代机制可在不同对象或窗口并存，不是互斥分类

### intervention [mechanism_inference]

按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback。代价：代码/编译体积和边界测试成本；新增区间可能改变计划dispatch域，须C2确认

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：所有原A硬前提与invariants保留；动作只在实例化与证据绑定后进入规划
