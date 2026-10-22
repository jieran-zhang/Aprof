# diagnosis：诊断与补证据请求

生产者：[诊断角色](../agents/diagnosis.md)。消费者：协调者、规划和采集。外层使用 [公共契约](common.md)，`stage=diagnosis`、`role=diagnosis`。

## 输入

引用 preparation、实际分析父版本源码、workload、架构和已有计时/机制证据。补证据后重新诊断时，再引用上一次 diagnosis 与新的 profiling 文档。完整优化会话的基线准备不能被诊断阶段重新生成。

## 必需结果

每个假设使用稳定的本任务内 ID，并填写：

| 字段 | 内容 |
| --- | --- |
| 源码与观测 | 源码位置、实际 workload、原始字段/单位或 trace 引用；区分事实、派生值与推测 |
| 假设 | 可能机制、预期影响、适用 case；少量候选中选本轮主假设 |
| 支持与反证 | 支持证据、替代解释、什么结果会推翻假设 |
| 未知项 | 缺失视图、未实现 extractor、无法确认的谓词 |
| 补采需求 | 关联假设、指标/单位、case 与实现、所需后端/视图、已有数据是否可复用 |
| 下一步 | 推荐进入规划、沿现有计划优化、先补证据或停止；明确合法图路由的证据状态 |

历史机器结构保持原义；当前图使用下述版本化知识交接。需要 profile 谓词的动作必须先补足证据；未实现 extractor 保持未知。当前诊断不能凭“预期会更快”认定机制成立。

## 完成与交接

分析请求完成但仍有不影响下一步的未知项，可以 completed，并明确允许的下一步。必须补证据才能选择合法动作时用 needs_input，协调者调用 profiling 的 `mechanism` 请求，再把采集结果交回诊断的新实例。

仅诊断任务可在交付诊断后结束。已有证据支持明确意图时，不因存在“采集角色”就强制采 PMU。

## 正文填写模板

```markdown
## 请求
分析对象/父版本、输入证据、目标与预算：

## 结果
事实与 workload 边界：
主假设 ID、机制、源码位置和适用 case：
支持证据、替代解释与反证条件：
合法路由状态或 NOOP/needs_evidence 原因：
输出引用与实际成本：

## 缺项与失败
未知谓词/缺失视图：
补采请求（假设、指标、单位、case、实现、后端、决策用途）：

## 交接建议
接收角色、下一步和应传入的引用：
```

## v0003 交接记录 C1

`outputs.knowledge_handoff` 引用 `aprof.handoff/v2`、stage=C1；route 为 `aprof.knowledge-route/v1`。必含图版本和 hash、context hash、参数覆盖 hash、全部匹配证据与原始引用、问题/动作排序、支持/反证贡献、缺项和动作状态。actions[].snapshot 保存 action 的正文、前提、不变量、来源与内容 hash；无需下游直接读 diagnosis/graph。

diagnostic_state 为 resolved/unknown/measurement_limited/workload_limited。推荐不等于选定或执行；pending 方向可交 planning 比较，但硬前提未满足不能交给 optimization 实施。必要时补证据生成新的 C1。NOOP、补采、重规划是 coordinator 的 disposition，不是 action 节点。

证据输入 aprof.evidence/v1 必须带 source_context_ref{path,sha256}，关联本次 C0/Context 文件。route.context_snapshot 保留完整 facts、attributes 和原 Context 引用，context_hash 对应该快照的规范 JSON hash；下游据此恢复路由条件，不依赖聊天记录。C1/C2 可用 candidate_id=null 表示任务级共享；C3 必须绑定真实候选 ID。
