---
name: ascendc-aprof-coordinator
description: 按明确预算编排 Ascend C 算子优化、诊断或规划，以角色定义和阶段 contract 串联准备、诊断、规划、候选、统一计时及交付。
---

# AProf 工作流入口

完整执行顺序、角色和分支只在 [主 workflow](../../workflows/aprof-performance-workflow.md) 维护。开始任务时读取该文件和 [协调者定义](../../workflows/agents/coordinator.md)；阶段交接使用 [公共契约](../../workflows/contracts/common.md)。

一个协调者维护任务上下文和连续预算，默认围绕一个假设实现一个候选。读取当前角色及其 contract，按需调用专业 skill；无需一次加载全部角色或重复生成已有证据。

解析安装技能的符号链接后定位完整包。角色/contract 定义在 workflows 中，实际阶段文档、代码和原始数据放任务工作区。性能反馈与完整收尾采用 [统一计时协议](../ascendc-aprof-profiling/references/unified-timing.md)，机器判定由本包 runtime 完成。
