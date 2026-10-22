# 三类节点与边格式

每个节点、每条边一个 Markdown，YAML 安全加载，拒绝重复键。机器规范是 [knowledge-record.schema.json](../../../schemas/knowledge-record.schema.json)。除共同字段外，类型字段如下；正文不为空。新增 ID 稳定后不复用为其他含义。

| 公共字段 | 定义 |
| --- | --- |
| schema_version | aprof.knowledge-record/v1 |
| id / kind / version / status / title | 稳定英文身份、类型、语义版本、active/deprecated、中文标题 |
| scope | platforms/workloads/dtypes 数组；all 表示不限，不代表硬件能力已知 |
| sources | 每项给包内 path、original_path、固定 revision、1-based 闭区间 lines、完整文件 sha256、片段 excerpt_sha256 |
| learning | symptom.gain=1；problem/action.bias=0；edge.weight=1/2/3 |
| tags | 旧问题族等非互斥标签，不参与独立加分 |
| seed_reason | 初始赋值理由；每条边须说明为什么采用该档 |

| 类型 | 专用字段 |
| --- | --- |
| symptom | view；evidence.rule/fields/units/extractor/unknown_when/threshold_scope |
| problem | mechanism；alternatives |
| action | transformation；preconditions[{fact,state}]；invariants；expected_effect |
| edge | from/to；relation=supports/refutes/mitigated_by；conditions[{field,op,value}] |

边只在 edges 的 Markdown 中定义。GRAPH.md、INITIALIZATION.md 和机器快照由构建器生成。节点不得再维护邻接表。一个 symptom 是一种独立特征，不用一个混合源码和 profile 的标题替代两种证据。

## 排序与前提

1/2/3 是专家顺序分数，不是概率、logit 或收益预测。S→P：3 为直接区分或明确反证，2 为有替代解释的关联，1 为低特异性提示。P→A：3 为直接且前提明确的变换，2 为条件性资源/成本取舍，1 为弱依据探索。无来源的关系禁止进入活动图。

每个 problem 的分数是 bias + 已满足 supports 的 weight×gain − 已满足 refutes 的 weight×gain。同一 problem 的同一 evidence_id 只保留绝对值最大的贡献，同强度冲突优先反证，再按边 ID 排序；不把同一观测抄到多个文档后重复加分。unknown 不作 false 或反证。不同机制可以使用同一证据，但不能把其分数解释成独立概率。

动作分数取所有正分机制路径中的 max(problem_score×edge_weight)+action_bias，避免重复机制别名放大动作。前提不参与加分：false→blocked，缺失/unknown/proxy→needs_evidence，全部核验→executable。executable 仅表示可进入候选，不证明正确性或收益。同分按稳定 ID 排序，无随机采样。

scope 和边条件均须满足；平台特有字段不存在时保持未知，不能拿另一个平台分母补齐。旧 2.4～2.8 logit 只在历史/迁移清单保留，不混入新评分。

## 证据输入与输出

`aprof.evidence/v1` 使用 task_id、attributes、facts。attributes 支持 platform、family 数组、dtype 和自定义路由字段。facts 的 key 是 symptom ID 或 constraint ID；已知事实须包含 state、evidence_id、ref{path,sha256,locator}，可带 kind=source_review/profile/workload/derived/proxy。人工审读不等于自动 extractor 已实现。

路由记录 `aprof.knowledge-route/v1` 保留知识版本/hash、上下文 hash、参数覆盖 hash、原始证据、去重贡献、问题/动作排序、缺项和动作全文快照。不能填入旧 RouteDecision 或 candidate_episode。

## 扩展步骤

1. 先保存固定来源及许可，记录原路径、修订、行号和两个 hash。
2. 查已有机制，合并同义项；新建独立特征/变换，附适用域、反证和硬前提。
3. 在边文件逐条赋 1/2/3，并解释；正确性要求移至实现约束。
4. 在任务外维护区运行 `tools/aprofctl knowledge build --root <包> --owner diagnosis`，随后 validate；构建拒绝重复 ID、悬空/非法边、坏 hash 或非法初值。
5. 审阅 GRAPH.md、INITIALIZATION.md 和迁移清单；更新版本并做路由回归。已冻结历史版本不覆盖。

训练覆盖文件格式为 aprof.knowledge-override/v1，含 base_hash、version、parameters{id:{gain/bias/weight:数值}}；只能覆盖已声明字段，值须有限，gain/weight 非负。内容替换需新版本和 hash。当前不自动训练。

### symptom 完整元数据示例

```yaml
schema_version: aprof.knowledge-record/v1
id: symptom.profile.broadcast_strategy_mismatch
kind: symptom
version: 1.0.0
status: active
title: 广播重复读或标量开销随广播轴放大
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
  - 90
  - 90
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:5b45f68f39db91d205aded22104d3541a355e714ce07a82e0d80a5fc1c059e36
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 68
  - 68
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:57f549afbd96c61a5daf7debee3ab166f2051707846c0b79e023e902b0d05dab
learning:
  gain: 1
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
view: profile
evidence:
  rule: 广播重复读或标量开销随广播轴放大
  fields:
  - 'source: broadcast axes / strides'
  - read_main_memory_datas
  - ai*_scalar_ratio
  units:
    raw: 采用实际后端原单位；字段名为来源族，通配符和视图须映射实际版本字段
    derived: 比值与差值需注明分子分母、时间窗口、平台上限来源
  extractor: unimplemented
  unknown_when: 对应源码、字段、区间、平台分母或工作量模型缺失时保持 unknown。
  threshold_scope: 来源中的经验阈值仅在原平台与 workload 成立；本轮没有校准通用阈值。
```

正文解释证据/机制/变换/关系，补充适用限制和反证；不得把跨角色模板重复放在这里。

### problem 完整元数据示例

```yaml
schema_version: aprof.knowledge-record/v1
id: problem.broadcast_strategy_mismatch
kind: problem
version: 1.0.0
status: active
title: 广播方案与连续性或复用不匹配
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
  - 90
  - 90
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:5b45f68f39db91d205aded22104d3541a355e714ce07a82e0d80a5fc1c059e36
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 68
  - 68
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:57f549afbd96c61a5daf7debee3ab166f2051707846c0b79e023e902b0d05dab
learning:
  bias: 0
tags:
- api_algorithm
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
mechanism: 广播方案与连续性或复用不匹配
alternatives:
- 工作量或计数器口径受限
- 相邻搬运/流水/并行机制
```

正文解释证据/机制/变换/关系，补充适用限制和反证；不得把跨角色模板重复放在这里。

### action 完整元数据示例

```yaml
schema_version: aprof.knowledge-record/v1
id: action.align_cache_policy
kind: action
version: 1.0.0
status: active
title: 按访问复用需求调整缓存策略
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 67
  - 67
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:6bbbe4fffe0c34b26ad3f4f5488e25af22b614c4d7d59f6092358fa8848ed539
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/onchip-memory-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  lines:
  - 68
  - 68
  sha256: sha256:8d9fb7fb09995999b68b59bb166ce51eb6d3cb9e7f5240dc2cf7d5156d7361e1
  excerpt_sha256: sha256:ade63739a7235448f04bfb37b4019442d94518f4bd0674423aa24011707d4d64
learning:
  bias: 0
tags:
- onchip_memory
seed_reason: 独立可核验证据匹配增益为 1；机制与动作不加先验偏置。
transformation: 按访问复用需求调整缓存策略
preconditions:
- fact: symptom.source.cache_policy_mismatch
  state: true
- fact: constraint.cache_api
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
```

正文解释证据/机制/变换/关系，补充适用限制和反证；不得把跨角色模板重复放在这里。

### edge 完整元数据示例

```yaml
schema_version: aprof.knowledge-record/v1
id: edge.action.broadcast_strategy_mismatch
kind: edge
version: 1.0.0
status: active
title: problem.broadcast_strategy_mismatch → action.restructure_broadcast
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
  - 90
  - 90
  sha256: sha256:886061117d25c4db2c617f5b8a899911a3e57502fb8a4136eda024dcf6e20bb5
  excerpt_sha256: sha256:5b45f68f39db91d205aded22104d3541a355e714ce07a82e0d80a5fc1c059e36
- path: workflows/migration/archive/skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  original_path: skills/ascendc-aprof-diagnosis/references/api-algorithm-diagnosis-metrics.md
  revision: aprof-1.1.0-pre-governance:sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  lines:
  - 68
  - 68
  sha256: sha256:9c1fc5b3c90ba93734ca1e2ff7e074b3091bd506ffdd457165e46f80fdb9a214
  excerpt_sha256: sha256:57f549afbd96c61a5daf7debee3ab166f2051707846c0b79e023e902b0d05dab
learning:
  weight: 2
tags: []
seed_reason: 2 分：广播重排需要比较连续性、输入复用和 UB 临时区成本，不能仅凭 axis 选固定模板。
relation: mitigated_by
from: problem.broadcast_strategy_mismatch
to: action.restructure_broadcast
conditions: []
```

正文解释证据/机制/变换/关系，补充适用限制和反证；不得把跨角色模板重复放在这里。

证据输入 aprof.evidence/v1 必须带 source_context_ref{path,sha256}，关联本次 C0/Context 文件。route.context_snapshot 保留完整 facts、attributes 和原 Context 引用，context_hash 对应该快照的规范 JSON hash；下游据此恢复路由条件，不依赖聊天记录。C1/C2 可用 candidate_id=null 表示任务级共享；C3 必须绑定真实候选 ID。

知识区的版本与 owner 在 REGION.json 维护，记录在构建来源 hash 中；变更知识版本时保留已冻结版本，覆盖参数不可跨 hash 使用。
