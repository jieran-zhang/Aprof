---
name: ascendc-aprof-coordinator
description: 按明确预算编排 Ascend C 算子优化、诊断或规划，以角色定义和阶段 contract 串联准备、代码理解、诊断、规划、候选、统一计时及交付。
---

# AProf 工作流入口

每轮实施一个[完整优化方案](../../workflows/references/optimization-schemes.md)：单个 Action 足够时直接使用，必要多成员及配套 P/O、Host/Kernel 修改可以共同实施，不要求严格单因素。按[选择规则](../../workflows/references/action-selection.md)核对共同工作变化、覆盖和代价；实施合法不代替价值比较，性能 unknown 不阻断适用知识的假设试验。

新任务必须按 [soft_targets_local_v1](../../workflows/references/execution-policy.md) 执行：耗时仅为软目标，baseline 默认 assumed，新候选完整验证一次，按全输出内容复用；所有运行产物留在 /dev/shm。

完整执行顺序、角色和分支只在 [主 workflow](../../workflows/aprof-performance-workflow.md) 维护。开始任务时读取该文件和 [协调者定义](../../workflows/agents/coordinator.md)；阶段交接使用 [公共契约](../../workflows/contracts/common.md)。

一个协调者维护任务上下文和连续预算，围绕本轮选定方案实现候选。新方案采用 action-decision/v3 与 handoff/v4，旧记录按版本回放。读取当前角色及其 contract，按需调用专业 skill；无需一次加载全部角色或重复生成已有证据。

轮数、达标停止条件和重试范围由用户/外层驱动提供并在 C0 传递；未指定多轮时只完成当前明确方案后报告，accepted 不自动停止。每次修复/重试保留新 attempt 并累计成本，不借换名扩大范围。

在任务根维护[optimization-history.md](../../workflows/references/optimization-history.md)的当前状态、已尝试路线、剩余机会三部分；每轮结果、修复或重规划后更新。所有后继先读摘要再按需展开历史，重新比较残余工作与新增代价，允许继续相同 Action；失败、未测和探索父本不丢弃。摘要不是原始证据、授权或 memory，无硬件反馈保持 not_measured。

任务携带冻结预算 policy 时，按 [阶段预算绑定](../../workflows/references/workflow-details.md#stage-budget-policy) 将其总预算、C0 阶段限和原始 deadline 传入指令、检查与成本记录；不使用历史运行脚本中的固定限时覆盖当前 policy。

C0 按 [准备契约](../../workflows/contracts/preparation.md) 接入原始 oracle；复用上层绑定的能力证据，区分 adapter/环境缺失与实际数值失败。已知共同阻塞且相关依赖未变时返回引用和缺项，不消耗另一整轮预算重复调查。

C0 后、C1 前按 [理解契约](../../workflows/contracts/code-understanding.md) 使用独立 [ascendc-code-understanding](../ascendc-code-understanding/SKILL.md)，可由同一 Agent 或受委派角色完成。一份中文阶段 Markdown 依次解释整体算法/数值语义、实际分派/任务/循环/已有策略、数据所有权/布局/存储/依赖和 910C 行为，关键片段附源码定位。已有适用报告直接复用，供 C1、P/O 与所有后继轮次共用；源码或相关条件变化只更新受影响部分并保存后继，纯新 profiling 不重做。性能缺测不阻断理解，此阶段不预选 Problem、Action 或新的 C2 策略。

解析安装技能的符号链接后定位完整包。角色/contract 定义在 workflows 中，实际阶段文档、代码和原始数据放任务工作区。性能反馈与完整收尾采用 [统一计时协议](../ascendc-aprof-profiling/references/unified-timing.md)，机器判定由本包 runtime 完成。新探索任务在采集前冻结v3声明及中位数稳定性v2、实际复验额度；旧记录按原版本回放。具体异常、窗口和收益判断只按统一计时文档维护。A/B 计时前先准备好baseline 信任前提与候选完整正确性与存储条件，连续采集以避免修复/搬迁消耗比较窗口。

## 机制诊断与方案交接

当前知识流程见[机制与交接](../../workflows/references/diagnosis-v4.md)。协调者核对方案/成员实例、C2共同计划和C3逐成员实际方法；具体实施条件 unknown 可分派条件化 C2 分析，实施前须满足所绑定版本的合法性要求；性能假设 unknown 可由适用的来源知识和当前源码支持试验，不要求先证明收益。临时Problem可复用注册Action，不要求强行补SPA路径。新证据形成后继，P_KEEP 且所有成员 O_KEEP 记 NOOP；性能结果不自动晋升知识。
