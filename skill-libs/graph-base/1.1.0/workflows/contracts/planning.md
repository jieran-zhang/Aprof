# planning：算法、并行与分发计划

生产者：[规划角色](../agents/parallel-planning.md)。消费者：协调者和优化。使用 [公共契约](common.md)，`stage=planning`、`role=parallel-planning`。

## 输入与结果

输入引用 preparation、diagnosis、分析父版本源码、架构证据和可复用旧计划。正文必须说明：

- 各 workload group 的算法、独立任务、所有权、归约/同步、workspace 与容量模型。
- 语义和精度不变量、适用元数据域、互斥分发条件与通用 fallback。
- 被拒绝的替代方案及依据，选定计划回应哪个诊断假设。
- 本次是新计划还是复用；复用依据以及触发重规划的具体变化。

`outputs` 引用现有 schema 的 `architecture_profile`、`parallel_plan`、`dispatch_plan` 和对应校验回执，不在 Markdown 重写整份 JSON。计划引用真实来源，未知容量不能授权依赖该容量的优化。

## 完成条件

计划绑定相同 operator、架构和 workload 范围，结构/容量/分发检查通过；未知关键条件返回 needs_input。书面计划不证明算法正确或性能收益。

普通 tile、buffer、搬运、流水优化可直接复用有效计划，不必重新启动规划角色。协调者把旧 planning 文档作为下次输入，记录复用理由。每个候选仍要重绑 dispatch 的实现源码，区分 `plan_basis_source_hash` 和 `implementation_source_hash`。

改变算法、分解、所有权、归约、同步或 workspace 所有权时，由协调者发起新的 planning 实例。仅规划任务在交付计划后结束；进入候选实现仍需合法路由和执行授权。

## 正文填写模板

```markdown
## 请求
诊断假设、分析父版本、架构/workload、目标与预算：
拟复用计划及本次变化：

## 结果
各 group 选定方案与 fallback：
语义/精度不变量和容量结论：
替代方案、选择依据：
architecture/parallel/dispatch 及校验回执引用：
计划复用条件、重规划条件与成本：

## 缺项与失败
未验证资源、能力、元数据域或失败检查：

## 交接建议
供优化使用的 group/key/entry、计划和源码身份引用：
```

## v0003 交接记录 C2

`outputs.knowledge_handoff` 引用 `aprof.handoff/v2`、stage=C2，parent_hash 绑定 C1 的规范 JSON 内容 hash。route 为规划树路由记录，包含树版本/hash、路径及模板全文快照。selected_entries 只列实际采用条目；selected_actions 引用 C1 中的 ID，并在 artifacts 引用 C1/action 快照。parameters 写实例值与单位，alternatives 写方案、容量/成本比较和拒绝原因，implementation_freedom 明确可调整范围。

继续引用原 architecture_profile、parallel_plan、dispatch_plan，不向它们的严格 schema 偷加字段。只有算法/所有权/归约/同步等变化才重规划；普通参数变化按自由度处理。优化角色依赖 C2 和其产物即可工作，不需读规划内部知识目录。
