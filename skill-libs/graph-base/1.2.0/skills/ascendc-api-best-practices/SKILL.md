---
name: ascendc-api-best-practices
description: 在 AProf 修改 Ascend C 实现前，依据已安装 SDK 检查搬运、队列、同步、归约与矩阵 API 的约束。
---

# AProf API 检查

读取 [API 与内存约束](references/api-contracts.md)，检查搬运对齐、队列生命周期、事件顺序、repeat/mask 限制以及归约、矩阵边界。只有目标已确认支持时才读取 [RegBase 与 SIMT](../npu-arch/references/regbase-simt.md)。

准确的重载、单位、dtype 和编译宏以目标 SDK 头文件及匹配版本的官方文档为准。把头文件路径、版本或官方 URL 记入候选证据，不套用其他 SDK 的签名；查找方法见本地 `ascendc-docs-search`。
