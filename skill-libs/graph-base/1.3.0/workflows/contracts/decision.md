# decision：推进、性能收尾与交付

新任务必须按 [soft_targets_local_v1](../references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

生产者：[协调者](../agents/coordinator.md)。消费者：下一阶段角色或用户。使用 [公共契约](common.md)，`stage=decision`、`role=coordinator`。

## 输入与必需结果

输入引用本次相关 preparation、diagnosis、planning、candidate、profiling 和既有 decision；仅诊断或仅规划任务不要求不存在的候选/计时结果。

正文填写：

| 字段 | 内容 |
| --- | --- |
| 比较与覆盖 | 实际父版本、原始基线、当前候选，完整/已测/缺少的 case，正确性范围 |
| 决定 | `collect_more`、`revise`、`replan`、`continue`、`stop` 或 `deliver`，附依据 |
| 机器结果 | 已收尾则引用 comparison 与 timing result；未收尾明确 `not_evaluated`，只报告部分反馈 |
| 限制与失败 | 未解决假设、回归、不可用能力、失败/不确定结果和未执行检查 |
| 下一步 | 接收角色、目标、输入/复用引用、剩余预算；停止或交付写明终点 |
| 交付 | 最终源码/补丁、简短中文报告、结果与证据位置、实际成本 |

若输入 candidate 为明确授权的图外实验，原样保留其 unadmitted、授权来源与缺路由原因；工程性能结果不能把它变成合法图候选或训练 episode。

## 何时调用 runtime

只有两侧覆盖完整声明 timing 集、各自完整 correctness 及原始回执齐备，才由协调者构造 `unified-timing-request` 并执行一次：

```bash
tools/aprofctl timing finalize --request <comparison.json> --output <new-result.json>
```

收尾门槛与原始回放见 [统一协议](../../skills/ascendc-aprof-profiling/references/unified-timing.md)。`timing verify` 仅供按需审计，不默认再回放一次。新结果不串接旧 candidate gate / episode finalize。

- accepted/rejected/inconclusive 原样引用，不由 Agent 手填或改写。
- 证据不足或完整覆盖未完成时，记录 not_evaluated 与停止/补齐原因；不能删 case 或重置连续成本起点。
- 过期、环境变化、波动或临界结果需要确认时，按预声明规则用同方法复验并保留全部尝试。
- 性能结果权限为 performance_engineering_only，不自动产生生产 best 或策略奖励。

## 继续与终止

继续迭代时明确选定父版本，引用其正确性、计划及有效采集。失败候选退回上一有效父版本；仅通过正确性的探索父版本与已验收的性能结果分开记录。B 作为下一轮 A 不改写原始文件，也不把跨时段加速比相乘。

decision 可以记录停止、失败或不确定的交付；文档 completed 仅表示决定和交接完整。预算与原始成本连续累计。交付和清理按 [生命周期](../references/workflow-details.md)，有后续回放依赖时先保留证据闭包，再处理 scratch。

## 正文填写模板

```markdown
## 请求
本次要决定的问题、已有阶段、任务目标与剩余预算：

## 结果
实际父版本、原始基线、候选及覆盖：
机器结果引用或 not_evaluated 与原因：
决定、依据、实际成本：
代码/报告/证据交付引用（交付时填写）：

## 缺项与失败
尚缺 case/证据、未解决问题、原始失败或不确定结论：

## 交接建议
下一角色、输入、拟复用对象与有效性依据；或停止/交付说明：
```

## 知识结果关联 C5

收尾后用 `knowledge link-result --root <包> --c1 <C1.json> --c2 <C2.json> --c3 <C3.json> --timing-ref <ref.json>` 关联实际执行与统一计时结果。timing-ref 含 path、sha256、candidate_id、protocol；引用的结果需先通过 timing finalize/verify。

关联记录保存 recommended_actions、selected_actions、executed_actions 与三份 handoff hash，不能从加速结果推断动作因果。新格式不进入旧 episode/reward，当前不自动训练。未计时/图外授权实验保留独立状态，不伪造 route 或通过结果。

link-result 核对 timing-ref 所指结果与请求文件的 hash、候选/协议及 C3 implementation_source_hash。timing-ref.path 相对于该引用文件所在目录（也可为已固定的绝对路径）。此关联不会重复执行已完成的 timing finalize；原始来源真实性仍由该 finalize/按需 verify 负责。

## 当前机制实例的结果限制

临时Problem复用注册Action是受支持的任务内推理，不因缺模板边自动判为unadmitted。按v3交接保存instance身份、最终P/O选择、实际变化和验证引用；明确未注册的新变换仍先提案。结构通过或性能改善不自动证实机制，不自动写入模板图或授予旧episode/reward。案例与提案按新contract分开检查。
