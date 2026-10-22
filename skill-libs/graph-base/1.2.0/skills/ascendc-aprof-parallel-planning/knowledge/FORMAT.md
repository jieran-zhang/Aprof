# 知识树格式与维护

本树与另一角色知识树共用 [knowledge-record schema](../../../schemas/knowledge-record.schema.json) 的身份、版本、适用域、来源和学习字段，分别版本化。一个条目一个 Markdown，中文正文按需读取。入口 [ROUTER.md](ROUTER.md)，全量初值见 [INITIALIZATION.md](INITIALIZATION.md)，来源及许可见 [NOTICE.md](NOTICE.md)。

| 字段 | 定义 |
| --- | --- |
| schema_version / id / kind / version / status / title | 格式版本、稳定英文 ID、类型、语义版本、active/deprecated、中文标题 |
| scope | platforms/workloads/dtypes；all 只表示检索不限，不证明平台支持 |
| sources | path、original_path、固定 revision、lines 闭区间、文件 sha256、片段 excerpt_sha256；运行不依赖上游仓库 |
| learning / seed_reason / tags | 叶条目初始 learning={}；身份可训练替换；路由权重在 routes 中。理由必须具体 |
| parent | 唯一主归属 ID；仅根 router 为 null |
| references | 同一树内跨分支复用 ID；不形成第二父节点 |
| evidence_status | source_reviewed_not_benchmarked，历史案例另保留原状态/协议 |
| routes | 只在 router 中维护 target、match、exclude、required_evidence、prior_score、fallback、seed_reason |

kind 可为 router、strategy、template、recipe、example。router 子路由覆盖其全部直属条目，父子无环，每条目只有一个主归属。跨分支只通过 references 复用。一个任务可以同时进入多个分支；同分按 ID，默认确定性路由。

match/exclude 条件为 `{field, op, value}`，字段取 attributes，op 为 eq/contains/in；match 全部满足、exclude 没有命中才进入。条件字段缺失不假设匹配。required_evidence 从 facts 取真值；未知/false/proxy 均返回 needs_evidence，不能静默授权执行。

prior_score：3=明确适用且可直接比较；2=条件性资源/成本取舍；1=探索或历史参照；通用 fallback=0，每个 router 恰有一条，仅在没有普通分支匹配时使用。路径分数为各层 prior_score 之和，不能比较不同树的分数或解释为性能收益。

## 叶条目要求

planning 的 template/strategy 给出适用域、算法骨架、任务所有权、归约/同步、容量与成本公式、参数空间、替代方案、fallback、证据状态及关键代码。模板不是完整工程，API/平台能力仍须核实。

optimization 的 recipe 给出适用条件、步骤、关键代码、验证和失败特征，保持 C2 语义与所有权。example 保留原硬件/协议/范围、成功和失败，不迁移性能资格。

## 扩展与训练

新增条目先固定来源、许可证和修改说明；检查现有同义项，选唯一主归属并在父 router 增加路由。平台常数和经验阈值必须带适用条件。执行 `tools/aprofctl knowledge build --root <包> --owner <角色>`，再 validate，审阅生成的 index.json 和初始化报告。

构建产物带全部 Markdown hash、生成器 hash 和 schema hash，相同输入字节产生相同结果。索引包含正文快照，运行时根据命中路径点读；sources 是冻结档案，不是另一套 router。

`aprof.knowledge-override/v1` 绑定 version 和 base_hash；parameters 中 router ID 的值是 `{target_id:新分数}`。只允许覆盖现有非 fallback 路由；值须有限非负；不能覆盖树结构或跨版本使用。内容/结构变更通过新版本构建。本轮只提供加载、校验、路由记录及结果关联，不自动训练。

## 根 router 完整示例

```yaml
schema_version: aprof.knowledge-record/v1
id: planning.root
kind: router
version: 1.0.0
status: active
title: 并行规划知识入口
scope:
  platforms:
  - all
  workloads:
  - all
  dtypes:
  - all
sources:
- path: workflows/migration/archive/skills/ascendc-tiling-design/references/algorithm-families.md
  original_path: skills/ascendc-tiling-design/references/algorithm-families.md
  revision: aprof-1.1.0-pre-governance:sha256:9036a42db1a5c59c0df65aa065346ee5b6e0e951ac7e22f0522b96c8bfb3bd9b
  lines:
  - 1
  - 17
  sha256: sha256:9036a42db1a5c59c0df65aa065346ee5b6e0e951ac7e22f0522b96c8bfb3bd9b
  excerpt_sha256: sha256:9036a42db1a5c59c0df65aa065346ee5b6e0e951ac7e22f0522b96c8bfb3bd9b
learning: {}
tags: []
seed_reason: 内容初始版本；树路由按适用条件采用 3/2/1 排序，fallback 为 0。
parent: null
references: []
evidence_status: source_reviewed_not_benchmarked
routes:
- target: planning.elementwise
  match:
  - field: family
    op: contains
    value: elementwise
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.reduction
  match:
  - field: family
    op: contains
    value: reduction
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.matmul
  match:
  - field: family
    op: contains
    value: matmul
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.under-fusion
  match:
  - field: family
    op: contains
    value: under-fusion
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.flash-attention
  match:
  - field: family
    op: contains
    value: flash-attention
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.sort-topk
  match:
  - field: family
    op: contains
    value: sort-topk
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.layout
  match:
  - field: family
    op: contains
    value: layout
  exclude: []
  required_evidence: []
  prior_score: 3
  fallback: false
  seed_reason: 明确属于该算子族或实现问题，优先比较。
- target: planning.fallback
  match: []
  exclude: []
  required_evidence: []
  prior_score: 0
  fallback: true
  seed_reason: 未知类型保留语义正确的现有方案并补证据。
```

知识区的版本与 owner 在 REGION.json 维护，记录在构建来源 hash 中；变更知识版本时保留已冻结版本，覆盖参数不可跨 hash 使用。
