---
schema_version: aprof.diagnosis-record/v1
id: action.vectorize_tail
kind: action
version: 1.1.0
status: active
title: 让尾块使用有界向量路径
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
  - 88
  - 88
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:1946b5dcbbe8891830ae578b4b6ad08f97b1cfa2439fb33d9b48c4d5fa87ed75
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/pipeline-parallel-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  lines:
  - 75
  - 75
  sha256: sha256:bced4edd582c450d50baacc8a22abd061d79b2c3fa956142cc7329356afec6f1
  excerpt_sha256: sha256:d1fb57e98d01b845fa43b0258b378b466a0823b16cfe2b0b72a85050baf3eb2a
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 5
  - 7
  sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
  excerpt_sha256: sha256:9fdf79fde327ec40103f1244c9c79ee4afac5860645886bc8ca27129f5ded562
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 64
  - 112
  sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
  excerpt_sha256: sha256:8348896087faf9bd588de56b5e1df00baa68d475f1afab6f8e8276e1f9cc60be
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  original_path: ops/ascendc-performance-best-practices/references/elementwise/vector_efficiency_design.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 150
  - 172
  sha256: sha256:103bb67af7b9bc8316403167dbfd6e57da2a757dd0bfbc8af03336378051b13e
  excerpt_sha256: sha256:e5e66d6dfee5187142cfec46bffa5d0f200431651a54f2df298a34412ae93434
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 18
  - 41
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:1199fc0f5fab91a1a2c7ab2de685bfebaf9ddaed6d8bfffadbaa66093bc4537d
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 64
  - 83
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:602773449d5b443b10cb61459fe62eee44b8ee5c4e245ae469d939934a7b0fa8
- path: skills/ascendc-aprof-diagnosis/sources/cannbot-skills/41377d0a442cd5b1c2356874873a3dda591c6633/ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  original_path: ops/ascendc-tiling-design/references/reduction/ar-fullload.md
  revision: 41377d0a442cd5b1c2356874873a3dda591c6633
  lines:
  - 137
  - 151
  sha256: sha256:a41ac2ff57f181c342d823a1b453bfabfb20c56bf840e31f4dff7232cefdc80a
  excerpt_sha256: sha256:be0ac2913f04e7f4c85dcd7e0a281d6deacf1a8a93e4dc558bae87f67fbfd1f6
- path: skills/ascendc-aprof-diagnosis/sources/asc-devkit/d378849769f9ee610af9d0ac38db2b3b6bed3209/docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  original_path: docs/zh/api/SIMD-API/basic_api/memory_vector_compute/mask_operations/SetVectorMask.md
  revision: d378849769f9ee610af9d0ac38db2b3b6bed3209
  lines:
  - 1
  - 40
  sha256: sha256:0de631e061a2e005d01aaf2efe0076a9e2adb3287edf1d1e96dd515ab919a256
  excerpt_sha256: sha256:d7c691d2216b08e98f944e42db95c3e223e5d1515796094c4fcbaddc8d5e7a8c
learning:
  bias: 0
tags:
- tiling
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 让尾块使用有界向量路径
preconditions:
- fact: symptom.source.tail_slow_path
  state: true
- fact: constraint.valid_lengths
  state: true
- fact: constraint.semantic_equivalence
  state: true
- fact: constraint.capacity
  state: true
invariants:
- 完整语义和精度
- 有效元素覆盖和唯一写回
- 容量、同步与所有权合法
expected_effect: 预期减少该机制的额外成本；具体方案由 C2 比较、C3 实施，统一计时核验。
slots:
- name: target
  kind: object
  description: 相同实现中对齐主体与非对齐尾部的有效元素域
  required: true
- name: stage
  kind: stage
  description: host传入尾长；kernel mask/CopyPad/标量尾分支
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
  text: '原种子：让尾块使用有界向量路径；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。'
  basis: legacy_seed
  source_indexes:
  - 0
  - 1
  review_status: reviewed
  limitations:
  - 旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定
- id: source_vector
  text: Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。
  basis: source_statement
  source_indexes:
  - 2
  - 3
  - 4
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_reduce_full
  text: AR全载文档明确整行连续输入、按A1切核、输入双buffer与scratch容量，以及有效长度与对齐长度的差别。
  basis: source_statement
  source_indexes:
  - 5
  - 6
  - 7
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: source_mask
  text: SetVectorMask为向量执行配置掩码；具体产品和接口形式须以该固定修订及目标SDK核对。
  basis: source_statement
  source_indexes:
  - 8
  review_status: reviewed
  limitations:
  - 仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持
- id: intervention
  text: 用目标支持的向量count、mask或合法padding处理尾部，并保留精确有效长度
  basis: mechanism_inference
  source_indexes: &id001
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  review_status: reviewed
  limitations:
  - Count接口不保证每个API/目标都支持
  - 不能用aligned length代替有效count导致越界或归约污染
- id: costs
  text: 可能增加padding字节和临时buffer；不同dtype/架构API支持及精度路径需逐一核验
  basis: mechanism_inference
  source_indexes: *id001
  review_status: reviewed
  limitations:
  - 代价需要绑定具体候选量化，尚无本任务收益
review:
  state: reviewed_with_limits
  source_credibility: 固定修订的API文档、策略说明或公开代码；新claim独立引用本包来源与行号。旧迁移引用只作为legacy_seed，仓库名不自动等于硬件证明。
  discriminating_power: 分别比较尾元素比例、每核尾分配和同API不同长度；校验padding不进入归约或输出语义，实际写回只覆盖有效域；尾执行只占可忽略时间或差异来自核数/分支变化，不支持尾处理为主因
  observed_frequency: unknown
  gaps:
  - 尚无当前任务同scope的profiling关联或独立硬件复核；所有效果为prediction。
  - Count接口不保证每个API/目标都支持
  - 不能用aligned length代替有效count导致越界或归约污染
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
  effect: 用目标支持的向量count、mask或合法padding处理尾部，并保留精确有效长度；预期变化仅为prediction：目标支持的count/mask向量尾处理可减少API与Scalar工作；这是prediction
  costs:
  - 可能增加padding字节和临时buffer
  - 不同dtype/架构API支持及精度路径需逐一核验
  unknown_policy: 任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。
  replan_triggers:
  - 目标/阶段、owner或有效元素域变化
  - 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
  - 工作量、dtype、平台、容量或profile反证使原干预假设失效
---

# 让尾块使用有界向量路径

## 变换与作用对象

用目标支持的向量count、mask或合法padding处理尾部，并保留精确有效长度。

相同实现中对齐主体与非对齐尾部的有效元素域；阶段：host传入尾长；kernel mask/CopyPad/标量尾分支。

## 实例绑定与原硬前提

实例必须给出精确template_hash、task与parent实现、目标和阶段；参数逐项给单位、来源及有效域，关联已确认C2计划。未知信息不从样例常量或聊天推断。

- target
- stage
- workload
- implementation

- symptom.source.tail_slow_path=true
- constraint.valid_lengths=true
- constraint.semantic_equivalence=true
- constraint.capacity=true

原invariants：完整语义和精度；有效元素覆盖和唯一写回；容量、同步与所有权合法。

## 预期效果与代价

用目标支持的向量count、mask或合法padding处理尾部，并保留精确有效长度；预期变化仅为prediction：目标支持的count/mask向量尾处理可减少API与Scalar工作；这是prediction

- 可能增加padding字节和临时buffer
- 不同dtype/架构API支持及精度路径需逐一核验

## 未知与返回规划

任一硬前提缺失、unknown或proxy则needs_evidence；明确不满足则blocked。C2可比较条件方案，C3须完成全部原前提及invariants核验。

- 目标/阶段、owner或有效元素域变化
- 算法、归并/同步拓扑、workspace owner、融合、通路或dispatch域超出已确认C2计划自由度
- 工作量、dtype、平台、容量或profile反证使原干预假设失效

## 平台与workload限制

- Count接口不保证每个API/目标都支持
- 不能用aligned length代替有效count导致越界或归约污染

## 逐项主张与依据

### legacy_seed [legacy_seed]

原种子：让尾块使用有界向量路径；原learning={"bias": 0}；独立可核验证据匹配增益为 1；机制与动作不加先验偏置。

来源索引：0, 1。限制：旧值仅供历史审计与旧快照回放，不是本轮可靠性、概率或收益标定

### source_vector [source_statement]

Vector效率文档区分repeat/mask控制、归约指令路径和中间GM往返，count接口与尾处理必须符合API约束。

来源索引：2, 3, 4。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_reduce_full [source_statement]

AR全载文档明确整行连续输入、按A1切核、输入双buffer与scratch容量，以及有效长度与对齐长度的差别。

来源索引：5, 6, 7。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### source_mask [source_statement]

SetVectorMask为向量执行配置掩码；具体产品和接口形式须以该固定修订及目标SDK核对。

来源索引：8。限制：仅陈述该固定修订来源内容；不证明当前任务实现、性能或目标硬件支持

### intervention [mechanism_inference]

用目标支持的向量count、mask或合法padding处理尾部，并保留精确有效长度

来源索引：2, 3, 4, 5, 6, 7, 8。限制：Count接口不保证每个API/目标都支持；不能用aligned length代替有效count导致越界或归约污染

### costs [mechanism_inference]

可能增加padding字节和临时buffer；不同dtype/架构API支持及精度路径需逐一核验

来源索引：2, 3, 4, 5, 6, 7, 8。限制：代价需要绑定具体候选量化，尚无本任务收益
