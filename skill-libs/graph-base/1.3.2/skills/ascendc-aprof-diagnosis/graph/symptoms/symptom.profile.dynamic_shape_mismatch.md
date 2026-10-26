---
schema_version: aprof.diagnosis-record/v1
id: symptom.profile.dynamic_shape_mismatch
kind: symptom
version: 1.1.0
status: active
title: 不同 shape 区间分别欠并行、开销高或流量放大
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
  gain: 1
tags:
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 不同 shape 区间分别欠并行、开销高或流量放大
  fields:
  - shape / tiling metadata
  - 'OpBasicInfo.csv: Block Dim/Task Duration'
  - per-core time / memory traffic
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: 每shape/dtype/feature区间绑定实际tile、BlockDim、workspace B与相同计时范围s。
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
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
  text: '原种子：不同 shape 区间分别欠并行、开销高或流量放大；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: observation_component_1
  text: 当前parent实现已支持的多个shape区间呈现不同任务活跃、逐核耗时、启动占比或流量模式
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
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_2
  text: 每份既有profile绑定其真实shape、dtype、feature、tiling参数及当前构建身份
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
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_3
  text: 跨区间比较注明平台、编译、缓存和计时范围，以及实际发生变化的工作量；不要求先新增dispatch
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
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: interpretation_boundary
  text: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
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
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - 不把来源阈值硬编码为目标最优边界
  - SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前parent实现已支持的多个shape区间呈现不同任务活跃、逐核耗时、启动占比或流量模式；每份既有profile绑定其真实shape、dtype、feature、tiling参数及当前构建身份；跨区间比较注明平台、编译、缓存和计时范围，以及实际发生变化的工作量；不要求先新增dispatch
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.profile.dynamic_shape_mismatch.component_1
    description: 当前parent实现已支持的多个shape区间呈现不同任务活跃、逐核耗时、启动占比或流量模式
  - id: symptom.profile.dynamic_shape_mismatch.component_2
    description: 每份既有profile绑定其真实shape、dtype、feature、tiling参数及当前构建身份
  - id: symptom.profile.dynamic_shape_mismatch.component_3
    description: 跨区间比较注明平台、编译、缓存和计时范围，以及实际发生变化的工作量；不要求先新增dispatch
---

# 不同 shape 区间分别欠并行、开销高或流量放大

## 当前观察对象与槽位

- target：同一算子多个shape/dtype/feature区间的dispatch及参数域
- stage：host shape归类与TilingKey；kernel模板/运行时分支
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前parent实现已支持的多个shape区间呈现不同任务活跃、逐核耗时、启动占比或流量模式
- 每份既有profile绑定其真实shape、dtype、feature、tiling参数及当前构建身份
- 跨区间比较注明平台、编译、缓存和计时范围，以及实际发生变化的工作量；不要求先新增dispatch

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- raw：采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
- derived：比值与差值需注明分子分母、时间窗口、平台上限来源
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：每shape/dtype/feature区间绑定实际tile、BlockDim、workspace B与相同计时范围s。

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

原种子：不同 shape 区间分别欠并行、开销高或流量放大；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### observation_component_1 [mechanism_inference]

当前parent实现已支持的多个shape区间呈现不同任务活跃、逐核耗时、启动占比或流量模式

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

每份既有profile绑定其真实shape、dtype、feature、tiling参数及当前构建身份

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

跨区间比较注明平台、编译、缓存和计时范围，以及实际发生变化的工作量；不要求先新增dispatch

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：2, 3, 4, 5, 6, 7, 8, 9。限制：不把来源阈值硬编码为目标最优边界；SquaredRelu host与kernel只证明dtype key的连接结构，不证明该算子存在shape失配
