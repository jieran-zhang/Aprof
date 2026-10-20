# planning：算法、并行与分发计划

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

生产者：[规划角色](../agents/parallel-planning.md)。消费者：协调者和优化。使用 [公共契约](common.md)，`stage=planning`、`role=parallel-planning`。

## 输入与结果

输入引用 preparation、diagnosis、分析父版本源码、架构证据和可复用旧计划。正文必须说明：

- 各 workload group 的算法、独立任务、所有权、归约/同步、workspace 与容量模型。
- 语义和精度不变量、适用元数据域、互斥分发条件与通用 fallback。
- 被拒绝的替代方案及依据，选定计划回应哪个诊断假设。
- 本次是新计划还是复用；复用依据以及触发重规划的具体变化。

`outputs` 引用现有 schema 的 `architecture_profile`、`parallel_plan`、`dispatch_plan` 和对应校验回执，不在 Markdown 重写整份 JSON。计划引用真实来源，未知容量不能授权依赖该容量的优化。

## 完成条件

可实施计划须绑定相同operator、架构和workload范围并通过结构/容量/分发检查。允许unknown输入的条件化分析请求：输出条件分支、计算依据和缺项即可完成该分析；若请求要求可实施计划而硬条件未满足，返回needs_input。书面计划不证明算法正确或性能收益。

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

## 当前交接 C2（handoff v3）

接收C1 Action实例而非仅action ID；核对模板hash、目标／阶段、workload和父实现，不借用其他实例的证据。调用规划内部router，记录实际选用P、容量／成本比较、任务所有权、通路、workspace、允许自由度及参数单位。

P_KEEP必须引用完整有效architecture/parallel/dispatch计划和适用范围；缺计划或unknown不能KEEP。O在C2只记录请求与约束，不能提前锁定recipe或完整P/O组合。提示不能覆写事实性attributes或facts。

新证据建立后继reasoning/C1/C2，不回填旧记录。超出既定算法、owner、归并、同步拓扑、workspace所有权、融合／通路或dispatch域时重新规划。完整规则见[机制与交接](../references/diagnosis-v4.md)。
