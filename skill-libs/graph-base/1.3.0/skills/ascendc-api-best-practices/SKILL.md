---
name: ascendc-api-best-practices
description: 在 AProf 代码理解及实现修改时，依据已安装 SDK 检查搬运、队列、同步、归约与矩阵 API 的语义和约束。
---

# AProf API 检查

code-understanding 角色按需用本技能核对影响整体算法、数据布局、存储和依赖的关键 API；核对结果融入同一理解报告，不另建 API 碎片表。

读取 [API 与内存约束](references/api-contracts.md)，检查搬运对齐、队列生命周期、事件顺序、repeat/mask 限制以及归约、矩阵边界。只有目标已确认支持时才读取 [RegBase 与 SIMT](../npu-arch/references/regbase-simt.md)。

准确的重载、单位、dtype 和编译宏以目标 SDK 头文件及匹配版本的官方文档为准。把头文件路径、版本或官方 URL 记入候选证据，不套用其他 SDK 的签名；查找方法见本地 `ascendc-docs-search`。
