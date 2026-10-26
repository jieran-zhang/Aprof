---
schema_version: aprof.diagnosis-record/v1
id: symptom.profile.chunk_merge_overhead
kind: symptom
version: 1.1.0
status: active
title: partial 写读和合并时间主导增长
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
  - 93
  - 93
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:366871d951ff662a5753237fdfe20e2a4caeb59eaf3c8e3760788f86c055d5c6
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/tiling-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  lines:
  - 74
  - 74
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:46552244beab6eb8e8a81ee012a507e5a086135b377ac6eb9823d37a1e0d5853
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
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/shape.md
  original_path: community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/shape.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 127
  - 155
  sha256: sha256:d7aba4c9f89b0422b630646f922fbe4705ff5329645e7f3bc85829a3b4c23a0b
  excerpt_sha256: sha256:cf7fda4b800edc845bfae928e6bf1e52b3b9ad21f5e8bcf3ab855635ddc4c35a
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/shape.md
  original_path: community/ops/ascendc-evolution-strategies/references/tiling-design/flashattention/design/shape.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 199
  - 270
  sha256: sha256:d7aba4c9f89b0422b630646f922fbe4705ff5329645e7f3bc85829a3b4c23a0b
  excerpt_sha256: sha256:9bdb2f921797739d0acca848842df9de3a3b4b64fc2510a80a5b816dc761f3f8
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  original_path: ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 25
  - 51
  sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
  excerpt_sha256: sha256:06c4a1cd8ca2e8155d32bfccfe8725b7e8bfb5d140abe0a7a6535c80c2064fc7
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  original_path: ops/ascendc-tiling-design/references/sort/alg-two-level-mrgsort.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 459
  - 475
  sha256: sha256:031b9829393ccd4f83ca8cd19d8a6ce47d42274e2975c247d487e9d87edcdcf6
  excerpt_sha256: sha256:f91c55f504d42bfb8c5ab3c6bee47af299a45496d85f567b66ac0108160f7c46
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
- path: skills/ascendc-aprof-diagnosis/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 68
  - 117
  sha256: sha256:ab29684d3cf7520f21b489fb640f6b4d0fb565b4bfbe505abc6b3b78052ae129
  excerpt_sha256: sha256:a6387ee8e35e103fcc0eab1c7dd6527cc2bde39da0f2faa488e4f763082a376e
- path: skills/ascendc-aprof-diagnosis/sources/cann-samples/17c948bb961fc6a660e4fcab45f6bf217c9c6239/Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  original_path: Samples/2_Performance/matmul_story/matmul_recipes/include/block/matmul_block_scheduler_streamk.h
  revision: 17c948bb961fc6a660e4fcab45f6bf217c9c6239
  lines:
  - 125
  - 145
  sha256: sha256:ab29684d3cf7520f21b489fb640f6b4d0fb565b4bfbe505abc6b3b78052ae129
  excerpt_sha256: sha256:1615511fc611b4fe38decefb39ad8616b8a433516017d2583a51f375a06b4962
learning:
  gain: 1
tags:
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: partial 写读和合并时间主导增长
  fields:
  - 'source: chunk count / partial bytes'
  - 'trace: merge duration'
  - read_main_memory_datas
  - write_main_memory_datas
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
    effective_bytes: B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
    duration: 引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
    counts: 指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
    source_model: shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
    mechanism_metric: chunk数、partial B、主阶段s、同步s、merge s；总节省减全部额外成本。
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
slots:
- name: target
  kind: object
  description: 被分段的归约/KV/K域及其partial、合并阶段
  required: true
- name: stage
  kind: stage
  description: host分段数量决策；各核partial生产；workspace写读与最终merge
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
  text: '原种子：partial 写读和合并时间主导增长；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  - 1
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_fa_pipe
  text: arch22 FA文档联合评估tile、AIC/AIV核数、buffer深度、workspace与局部/跨核同步，并比较Split-KV节省路径和归并成本。
  basis: source_statement
  source_indexes:
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_shape
  text: FA形态设计用任务数、可用核数、KV分段开销与变长任务成本选择切分和负载均衡，核数要求由平台查询。
  basis: source_statement
  source_indexes:
  - 5
  - 6
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_merge
  text: 两级归并文档区分核内独立归并与跨核轮次，核内group不需要全核同步，跨核每轮末尾才有全局依赖。
  basis: source_statement
  source_indexes:
  - 7
  - 8
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_sk_tiling
  text: StreamK tiling实现对K长度、M/N任务和平台核数做能力检查，并单独计算workspace；阈值属于该实现。
  basis: code_fact
  source_indexes:
  - 9
  - 10
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_sk_sched
  text: StreamK调度器由M/N/K分块计算总任务和尾块形状，并限制启动核数；这只说明源码调度结构。
  basis: code_fact
  source_indexes:
  - 11
  - 12
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: observation_component_1
  text: 当前调用的partial写读和merge阶段在全链有效时间或流量中占据较大份额，比较分母已注明
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
  - 10
  - 11
  - 12
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_2
  text: 当前chunk数量、每段有效工作和实际partial格式/字节有对应host与kernel引用
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
  - 10
  - 11
  - 12
  review_status: reviewed
  limitations:
  - 当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量
- id: observation_component_3
  text: 同一次全链计时包含主阶段、partial写读、同步、merge和最终输出；各阶段区间可对应，未要求改变chunk数
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
  - 10
  - 11
  - 12
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
  - 10
  - 11
  - 12
  review_status: reviewed
  limitations:
  - Split-K、Split-KV与排序merge的数学合并不同，不能直接替换算法
  - 本轮只有来源推导，无段数最优值或收益承诺
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 此S只描述当前可核验形态与必要口径，不以Action可行性、实验干预或成功收益作前提。具体支持、反证和替代机制判别见对应Problem。
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - Split-K、Split-KV与排序merge的数学合并不同，不能直接替换算法
  - 本轮只有来源推导，无段数最优值或收益承诺
observation:
  object_slots:
  - target
  - stage
  - workload
  - implementation
  rule: 仅根据当前实现联合核验：当前调用的partial写读和merge阶段在全链有效时间或流量中占据较大份额，比较分母已注明；当前chunk数量、每段有效工作和实际partial格式/字节有对应host与kernel引用；同一次全链计时包含主阶段、partial写读、同步、merge和最终输出；各阶段区间可对应，未要求改变chunk数
  comparison_basis: 比较只使用当前parent实现的已记录窗口/合法shape、源码工作量模型或可追溯的目标校准；注明有效域、dtype、平台、计时及计数分母。拟议Action的执行、可行性、收益和排除全部替代机制均不作为观察前提。
  unknown_when:
  - target/stage/workload/implementation身份或当前原始引用缺失时保持unknown
  - 现象所需字段、单位、统计分母、源码地址/任务域或已注明必要参照缺失时保持unknown
  - 三个当前观察分量全部true才true，任一经当前依据确认false则false，其余unknown；未执行候选Action或可选实验不构成缺项
  interpretation_boundary: 本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。
  required_components:
  - id: symptom.profile.chunk_merge_overhead.component_1
    description: 当前调用的partial写读和merge阶段在全链有效时间或流量中占据较大份额，比较分母已注明
  - id: symptom.profile.chunk_merge_overhead.component_2
    description: 当前chunk数量、每段有效工作和实际partial格式/字节有对应host与kernel引用
  - id: symptom.profile.chunk_merge_overhead.component_3
    description: 同一次全链计时包含主阶段、partial写读、同步、merge和最终输出；各阶段区间可对应，未要求改变chunk数
---

# partial 写读和合并时间主导增长

## 当前观察对象与槽位

- target：被分段的归约/KV/K域及其partial、合并阶段
- stage：host分段数量决策；各核partial生产；workspace写读与最终merge
- workload：绑定shape、dtype、layout、feature与有效元素域，不跨workload借证据
- implementation：绑定当前parent源码、host/tiling/kernel、编译配置或artifact身份

## 当前实现的复合观察

- 当前调用的partial写读和merge阶段在全链有效时间或流量中占据较大份额，比较分母已注明
- 当前chunk数量、每段有效工作和实际partial格式/字节有对应host与kernel引用
- 同一次全链计时包含主阶段、partial写读、同步、merge和最终输出；各阶段区间可对应，未要求改变chunk数

all-of只组合上述当前事实：全真才真，任一有依据的假则假，其余未知。未执行拟议动作不导致本S未知。

## 单位与必要比较

- raw：采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
- derived：比值与差值需注明分子分母、时间窗口、平台上限来源
- effective_bytes：B，按有效元素×dtype字节宽；padding、重复读写、协议字节另列
- duration：引用目标后端实际时间单位；换算统一到s后才计算B/s，cycle需同平台频率来源
- counts：指令/任务/repeat/槽位是计数；比值保留明确分子分母和窗口，不能混用AIC/AIV或单核/全调用
- source_model：shape/stride/count以元素或字节显式标注；容量和地址按所用API单位核对
- mechanism_metric：chunk数、partial B、主阶段s、同步s、merge s；总节省减全部额外成本。

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

原种子：partial 写读和合并时间主导增长；原learning={"gain": 1}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_fa_pipe [source_statement]

arch22 FA文档联合评估tile、AIC/AIV核数、buffer深度、workspace与局部/跨核同步，并比较Split-KV节省路径和归并成本。

来源索引：2, 3, 4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_shape [source_statement]

FA形态设计用任务数、可用核数、KV分段开销与变长任务成本选择切分和负载均衡，核数要求由平台查询。

来源索引：5, 6。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_merge [source_statement]

两级归并文档区分核内独立归并与跨核轮次，核内group不需要全核同步，跨核每轮末尾才有全局依赖。

来源索引：7, 8。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_sk_tiling [code_fact]

StreamK tiling实现对K长度、M/N任务和平台核数做能力检查，并单独计算workspace；阈值属于该实现。

来源索引：9, 10。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_sk_sched [code_fact]

StreamK调度器由M/N/K分块计算总任务和尾块形状，并限制启动核数；这只说明源码调度结构。

来源索引：11, 12。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### observation_component_1 [mechanism_inference]

当前调用的partial写读和merge阶段在全链有效时间或流量中占据较大份额，比较分母已注明

来源索引：2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_2 [mechanism_inference]

当前chunk数量、每段有效工作和实际partial格式/字节有对应host与kernel引用

来源索引：2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### observation_component_3 [mechanism_inference]

同一次全链计时包含主阶段、partial写读、同步、merge和最终输出；各阶段区间可对应，未要求改变chunk数

来源索引：2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12。限制：当前观察定义，非本任务已观测事实；extractor仍unimplemented；候选Action及可选实验不属于必要分量

### interpretation_boundary [mechanism_inference]

本S只定义当前实现的观察形态、范围和口径；source不自动推出profile，profile不自动确立Problem。候选Action可行性由原A硬前提核验，干预实验及其正反结果属于Problem检查/后继证据，不决定本S当前是否成立。

来源索引：2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12。限制：Split-K、Split-KV与排序merge的数学合并不同，不能直接替换算法；本轮只有来源推导，无段数最优值或收益承诺
