---
name: ascendc-code-review
description: 在构建前审查隔离的 AProf 候选，检查计划一致性、分发覆盖、内存边界、精度和同步。
---

# AProf 候选静态审查

对照候选、并行计划、分发计划和父源码，检查各分区的输出所有权、覆盖与重叠，以及归约、相等值、NaN、动态 shape、尾块和整数溢出规则。元数据条件必须互斥，或明确拒绝歧义；保留正确的通用回退。不得用 case ID、参考输出或张量值选择基准特化路径。

对修改的重载和流水生命周期读取 [API 约束](../ascendc-api-best-practices/references/api-contracts.md)。计算包含队列深度、临时空间的同时存活 UB/L1/L0/workspace 占用。逐项核验有效搬运长度、分配空间和 stride 单位；本地 padding 不授权越界 GM 读写。检查每个事件、跨核同步的生产者、等待者、消费者，排除依赖环与不对称路径。

3510 目标按 [RegBase 与 SIMT 约束](../npu-arch/references/regbase-simt.md) 检查，不能仅凭产品名启用 API。返回具体文件、行号和证据，或说明已检查范围。静态审查只是 runtime 判定的输入。
