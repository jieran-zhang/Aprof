---
name: ascendc-aprof-coordinator
description: 按明确预算编排 Ascend C 算子优化、诊断或规划，以角色定义和阶段 contract 串联准备、诊断、规划、候选、统一计时及交付。
---

# AProf 工作流入口

完整执行顺序、角色和分支只在 [主 workflow](../../workflows/aprof-performance-workflow.md) 维护。开始任务时读取该文件和 [协调者定义](../../workflows/agents/coordinator.md)；阶段交接使用 [公共契约](../../workflows/contracts/common.md)。

一个协调者维护任务上下文和连续预算，默认围绕一个假设实现一个候选。读取当前角色及其 contract，按需调用专业 skill；无需一次加载全部角色或重复生成已有证据。

任务携带冻结预算 policy 时，按 [阶段预算绑定](../../workflows/references/workflow-details.md#stage-budget-policy) 将其总预算、C0 阶段限和原始 deadline 传入指令、检查与成本记录；不使用历史运行脚本中的固定限时覆盖当前 policy。

C0 按 [准备契约](../../workflows/contracts/preparation.md) 接入原始 oracle；复用上层绑定的能力证据，区分 adapter/环境缺失与实际数值失败。已知共同阻塞且相关依赖未变时返回引用和缺项，不消耗另一整轮预算重复调查。

解析安装技能的符号链接后定位完整包。角色/contract 定义在 workflows 中，实际阶段文档、代码和原始数据放任务工作区。性能反馈与完整收尾采用 [统一计时协议](../ascendc-aprof-profiling/references/unified-timing.md)，机器判定由本包 runtime 完成。新任务在采集前冻结 `bounded_outlier_v1`，具体异常判据只按统一计时文档维护。A/B 计时前先准备好两侧完整正确性与存储条件，连续采集以避免修复/搬迁消耗比较窗口。
