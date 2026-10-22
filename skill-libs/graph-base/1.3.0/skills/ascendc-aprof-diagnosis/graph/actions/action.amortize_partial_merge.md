---
schema_version: aprof.diagnosis-record/v1
id: action.amortize_partial_merge
kind: action
version: 1.2.0
status: active
title: 增大有效 chunk 或采用分层合并
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
  bias: 0
tags:
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 增大有效 chunk 或采用分层合并
preconditions:
- fact: symptom.source.chunk_merge_overhead
  state: true
- fact: constraint.merge_semantics
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 减少chunk或分层归并可减少partial读写、发射与等待，但也可能降低并行度并拉长最长核。 是否作用于关键路径及实际收益由后继验证，不能由Action就绪推出。
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
  text: '原种子：增大有效 chunk 或采用分层合并；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
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
- id: intervention
  text: 按全链关键路径选择chunk数，并比较局部/分层或批量合并
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
- id: costs
  text: 减少并行度，可能重新出现最长核；合并结构变化影响精度、同步拓扑及workspaceowner
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
  - 代价需要绑定具体候选量化，尚无本任务收益
- id: condition_separation
  text: 存在可归并partial，归约顺序、精度、workspace owner和参与核完整已知；合法chunk数或归并层次由C2确认。 多chunk、partial格式及归并拓扑是结构事实，“overhead”并非实测时延结论。
    减少chunk或分层归并可减少partial读写、发射与等待，但也可能降低并行度并拉长最长核。
  basis: mechanism_inference
  source_indexes: []
  review_status: reviewed
  limitations:
  - 本次基于已有模板、包内来源和变换语义的条件分层归纳，不是上游新增性能结论。
  - 性能证据不足不等于变换不安全；实施安全也不证明当前关键路径、收益或试验优先级。
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 比较saved_critical_path与partial_write+sync+read+merge，而非只比较活跃核数；检查局部独立归并是否可在跨核同步前完成；分段仍显著缩短全链关键路径时，不能因存在merge就判过度
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - Split-K、Split-KV与排序merge的数学合并不同，不能直接替换算法
  - 本轮只有来源推导，无段数最优值或收益承诺
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
  effect: 按全链关键路径选择chunk数，并比较局部/分层或批量合并；预期变化仅为prediction：减少不必要分段或批量/分层合并可能降低额外成本但减少并行；这是prediction
  costs:
  - 减少并行度，可能重新出现最长核
  - 合并结构变化影响精度、同步拓扑及workspaceowner
  unknown_policy: 实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 增大有效 chunk 或采用分层合并

## 变换与作用对象

按全链关键路径选择chunk数，并比较局部/分层或批量合并。

被分段的归约/KV/K域及其partial、合并阶段；阶段：host分段数量决策；各核partial生产；workspace写读与最终merge。

## 实例绑定与实施安全条件

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。来源/源码/合法API与资源公式可以证明安全，无需将每项伪装成硬件观测。

存在可归并partial，归约顺序、精度、workspace owner和参与核完整已知；合法chunk数或归并层次由C2确认。

- `symptom.source.chunk_merge_overhead=true`：多chunk、partial格式及归并拓扑是结构事实，“overhead”并非实测时延结论。
- `constraint.merge_semantics=true`：部分结果表示、合并算子和精度顺序须合法，并保持最终输出唯一所有权。
- `constraint.semantic_equivalence=true`：完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。
- `constraint.capacity=true`：按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。

不变量：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

## 性能假设、比较与补证据

多chunk、partial格式及归并拓扑是结构事实，“overhead”并非实测时延结论。

减少chunk或分层归并可减少partial读写、发射与等待，但也可能降低并行度并拉长最长核。

1. 按shape列出chunk数、每段有效量、partial字节和合并工作量，比较至少有竞争性的可行粒度。
2. 判别最长核计算与归并关键路径；没有分阶段timing时保留二者为预测，用静态工作量确定值得试的范围。

已有来源说明该方法，并且当前源码形态、对象、目标API与约束匹配时，即可将其作为有依据的优化候选；不要求先完成严格性能实验。每个unknown只写具体缺失项、决策影响和是否值得补证据。若补充检查不会改变候选选择，就记录预测后进入获授权的试验，不把“信息不完备”当统一否决。反之，安全未知或明确不适用必须阻断实施。

本Action能实施只是准入。选择前应与当前workload的主要字节、逐元素工作、任务/流水机会比较，说明预计改变何种成本、影响哪些case、可能代价及为何优先；不能以容易等价作为唯一理由。R2把R1实际patch与预测逐项对照，区分支持、削弱和无法判断；继续同一Action应有新证据、不同参数或尚未验证的预测，不要求机械换Action。

## 预期效果与代价

按全链关键路径选择chunk数，并比较局部/分层或批量合并；预期变化仅为prediction：减少不必要分段或批量/分层合并可能降低额外成本但减少并行；这是prediction

- 减少并行度，可能重新出现最长核
- 合并结构变化影响精度、同步拓扑及workspaceowner

## 未知与返回规划

实施前逐条满足本版本preconditions与invariants；安全/结构条件缺失则指出具体未证项，C2可继续条件分析，C3不得绕过。性能假设独立记录：来源与当前源码足以支持适用时，可在合法且有试验价值的条件下提出优化，不以尚无严格性能实测一律否决；不把未知写成确认。Action优先级由成本机会比较和补证据决策形成。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- Split-K、Split-KV与排序merge的数学合并不同，不能直接替换算法
- 本轮只有来源推导，无段数最优值或收益承诺

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：增大有效 chunk 或采用分层合并；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

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

### intervention [mechanism_inference]

按全链关键路径选择chunk数，并比较局部/分层或批量合并

来源索引：2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12。限制：Split-K、Split-KV与排序merge的数学合并不同，不能直接替换算法；本轮只有来源推导，无段数最优值或收益承诺

### costs [mechanism_inference]

减少并行度，可能重新出现最长核；合并结构变化影响精度、同步拓扑及workspaceowner

来源索引：2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12。限制：代价需要绑定具体候选量化，尚无本任务收益


### condition_separation [mechanism_inference]

存在可归并partial，归约顺序、精度、workspace owner和参与核完整已知；合法chunk数或归并层次由C2确认。 多chunk、partial格式及归并拓扑是结构事实，“overhead”并非实测时延结论。 减少chunk或分层归并可减少partial读写、发射与等待，但也可能降低并行度并拉长最长核。

本次维护归纳；原来源与许可不变。旧条件逐项去向见包内 `workflows/references/action-condition-policy.json`，v0004前提仅在历史快照继续按原义回放。
