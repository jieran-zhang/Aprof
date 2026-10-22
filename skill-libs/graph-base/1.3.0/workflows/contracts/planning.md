# planning：算法、并行与分发计划

新任务的[知识采用规则](../references/action-selection.md)允许在 Action 确定前做可行性咨询，给出具体参数域、所有权、代价及缺失的合法性事实。收益未测量不妨碍形成方案。首次提取当前计划与实际改变计划分开报告，不以 P_CHANGE 次数代表搜索广度。

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

生产者：[规划角色](../agents/parallel-planning.md)。消费者：协调者和优化。使用 [公共契约](common.md)，`stage=planning`、`role=parallel-planning`。

## 输入与结果
按[Action 选择规则](../references/action-selection.md)把新增准备工作、数据相关覆盖或数值保护的关键代价回传选择比较；不只确认容量。共同计划与 C1 的唯一所选方案绑定，正文解释同一选择，空候选不以 KEEP 补齐。


后继轮次先读[跨轮摘要](../references/optimization-history.md)，按需展开与计划相关的原始记录。输入引用 preparation、[code-understanding 报告](code-understanding.md)、diagnosis、分析父版本源码、架构证据和可复用旧计划。复用报告中的当前算法、路径、所有权和依赖，仅补查影响本次规划的源码/条件；新 profiling 不触发重做理解。正文必须说明：

- 各 workload group 的算法、独立任务、所有权、归约/同步、workspace 与容量模型。
- 语义和精度不变量、适用元数据域、互斥分发条件与通用 fallback。
- 被拒绝的替代方案及依据，共同计划回应哪些诊断假设和方案成员；联合工作、覆盖和新增代价怎样支持选择。
- 多成员的目标、布局/数值、所有权、同步及资源是否兼容，前置步骤产生什么保证及其兑现顺序。
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
拟复用理解报告/计划及本次变化：

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

## 当前交接 C2（handoff v4）

接收 C1 选定方案及其成员 Action 实例，而非仅 action ID；核对模板hash、目标／阶段、workload和父实现，不借用其他实例的证据。分别调用规划内部 router，形成统一覆盖相关目标的共同计划，记录实际 P、容量/成本比较、任务所有权、通路、workspace、许可自由度及参数单位。独立命中不能简单合并；共享工作只算一次，峰值按共同生命周期和物理别名计算。

P_KEEP 必须引用覆盖所有成员和目标的完整有效 architecture/parallel/dispatch 共同计划及许可自由度；缺计划或unknown不能KEEP。O在C2只记录请求与约束，不能提前锁定recipe或完整P/O组合。提示不能覆写事实性attributes或facts。

新证据建立后继reasoning/C1/C2，不回填旧记录。超出既定算法、owner、归并、同步拓扑、workspace所有权、融合／通路或dispatch域时重新规划。完整规则见[方案与共同计划](../references/optimization-schemes.md)，机制和历史说明见[机制与交接](../references/diagnosis-v4.md)。旧 handoff/v3 保留单实例语义，不混装。

前置步骤可生成后续保证，但需要绑定成员、对象/范围、参数、依赖顺序和预期源码位置；C2 可以条件分析，不能将尚未实现保证写成当前 facts。C3 对最终源码核实，不要求逐步构建中间候选，亦不放宽每个 Action 的实施条件。

## 比较之后的计划核对

C2 消费 C1 的工作量、覆盖和代价比较，把相应量具体化到任务、owner、通路、同步及容量。正文是完整采用、仅部分原则参考还是不适用要明确；Gather 的输出独占原则不能冒充采样/插值完整骨架。若新计算出的工作/资源或未覆盖范围改变原选择理由，应返回新的 C1 比较，不只是为原意图补合法性证明。

已有通用/参数化方案足够时无需新增 dispatch。确需不同算法/硬件域时说明分域依据、fallback 和维护代价；不以 Key 数量、case ID 或已测赢家作为方案目标。语义域缺乏真实边界依据时保留待验证假设。

C2 比较中若已点名具体 API/数值替换，先咨询该叶的语义、尾块、内部 scratch 与同步限制，将其计入方案成本；不能仅引用通用分支后把可查条件统称 unknown。替换是否合法与是否值得选择分开，后续 C3 仍按已确认计划实施。
