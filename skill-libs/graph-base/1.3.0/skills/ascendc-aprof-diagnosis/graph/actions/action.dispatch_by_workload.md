---
schema_version: aprof.diagnosis-record/v1
id: action.dispatch_by_workload
kind: action
version: 1.2.0
status: active
title: 按工作量分组选择策略
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
transformation: 按工作量分组选择策略
preconditions:
- fact: symptom.source.dynamic_shape_mismatch
  state: true
- fact: constraint.dispatch_coverage
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 若不同区间受不同工作量/容量/调度成本控制，分组策略可改善相应case；额外分支也可能无益。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
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
  text: '原种子：按工作量分组选择策略；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: intervention
  text: 按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback
  basis: mechanism_inference
  source_indexes:
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
- id: costs
  text: 代码/编译体积和边界测试成本；新增区间可能改变计划dispatch域，须C2确认
  basis: mechanism_inference
  source_indexes:
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
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 已支持的shape/dtype/features域及fallback完整，host判别与kernel分支一致，每一新分支分别满足合法性。 相同核数/tile跨shape使用是结构事实，不推出必须特化；分段依据应绑定实际成本模型。
    若不同区间受不同工作量/容量/调度成本控制，分组策略可改善相应case；额外分支也可能无益。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 按相邻边界shape核验coverage、唯一分支和fallback；比较每区间机制，再决定是否需要新参数或方案，不能按shape数量造分支；现dispatch已经区分机制所需区间且退化是单一布局错误时不支持过度特化
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 不把来源阈值硬编码为目标最优边界
  - SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
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
  effect: 按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback；预期变化仅为prediction：有依据的区间派发可能分别缓解小任务开销与大任务资源约束；这是prediction
  costs:
  - 代码/编译体积和边界测试成本
  - 新增区间可能改变计划dispatch域，须C2确认
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 按工作量分组选择策略

## 变换与作用对象

按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback。

同一算子多个shape/dtype/feature区间的dispatch及参数域；阶段：host shape归类与TilingKey；kernel模板/运行时分支。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

已支持的shape/dtype/features域及fallback完整，host判别与kernel分支一致，每一新分支分别满足合法性。

- `symptom.source.dynamic_shape_mismatch=true`：相同核数/tile跨shape使用是结构事实，不推出必须特化；分段依据应绑定实际成本模型。
- `constraint.dispatch_coverage=true`：每个支持的shape/dtype/feature都命中唯一合法路径或明确fallback；边界不可漏测漏实现。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。

不变量：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

## 性能假设、比较与补证据

相同核数/tile跨shape使用是结构事实，不推出必须特化；分段依据应绑定实际成本模型。

若不同区间受不同工作量/容量/调度成本控制，分组策略可改善相应case；额外分支也可能无益。

1. 按case形态比较每核任务、tile数、尾比例、UB峰值及算法工作量，说明划分阈值来源与单位。
2. 区间边界和fallback必须覆盖全域；用已有知识与源码差异选择值得试的分支，未测阈值标成参数候选而非通用常数。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback；预期变化仅为prediction：有依据的区间派发可能分别缓解小任务开销与大任务资源约束；这是prediction

- 代码/编译体积和边界测试成本
- 新增区间可能改变计划dispatch域，须C2确认

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- 不把来源阈值硬编码为目标最优边界
- SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：按工作量分组选择策略；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### intervention [mechanism_inference]

按已证明不同机制的workload区间选择核数、tile或实现并保留合法fallback

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：不把来源阈值硬编码为目标最优边界；SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配

### costs [mechanism_inference]

代码/编译体积和边界测试成本；新增区间可能改变计划dispatch域，须C2确认

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：代价需要绑定具体候选量化，尚无本任务收益


### condition_separation [mechanism_inference]

已支持的shape/dtype/features域及fallback完整，host判别与kernel分支一致，每一新分支分别满足合法性。 相同核数/tile跨shape使用是结构事实，不推出必须特化；分段依据应绑定实际成本模型。 若不同区间受不同工作量/容量/调度成本控制，分组策略可改善相应case；额外分支也可能无益。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。

## v0006 选择与语义边界

分派本身不减少必要计算或流量。先比较通用与参数化方案及其残余限制；需要不同算法、硬件能力、数值路径或资源域时才以真实元数据选择已说明的方案。通常先改善通用路径；天然不同域可以较早分开，但不代表必然收益。不得按 case ID、已测赢家或无机制解释的阈值划分，不以 Key 数量为优化目标。R2 的回归先重新比较机制/计划/新增代价，不自动添加入口。

此段为基于既有变换语义的维护归纳，不新增上游性能声明、不放宽 preconditions，也不将当前任务的性能 unknown 改成 true。
