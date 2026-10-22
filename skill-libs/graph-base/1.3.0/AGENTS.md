---
name: aprof-performance-workflow
description: AProf workflow 宿主入口；由协调者按角色定义和阶段 contract 推进优化、诊断或规划。
mode: all
skills:
  - ascendc-aprof-coordinator
agents:
  - aprof-coordinator
permission:
  bash: ask
  external_directory: ask
---

# AProf 工作流入口

从 [主 workflow](workflows/aprof-performance-workflow.md) 开始，由 [协调者](workflows/agents/coordinator.md) 组织调用。角色定义统一位于 workflows/agents，阶段交接遵循 [公共契约](workflows/contracts/common.md)。

本文件只承担宿主发现与入口，流程、角色和 contract 以 workflows 为唯一维护位置。C0 准备后先完成或复用 code-understanding，再进入 diagnosis；同一 Agent 可以承担多个角色，也可以按现有授权委派。

专业操作使用对应 skill；预算、执行范围、原始证据和当前统一计时规则按 workflow 传递。已授权工作不重复询问许可；本次用户限制优先于默认流程。任务数据保存在任务私有工作区。
