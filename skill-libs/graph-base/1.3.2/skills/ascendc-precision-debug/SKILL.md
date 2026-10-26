---
name: ascendc-precision-debug
description: 在保持原始参考契约的前提下，定位 AProf 正确性失败并记录首个偏差阶段。
---

# AProf 精度失败排查

冻结失败候选及准确 case/seed、tiling key、dtype/layout、参考 hash、容差和命令。继续优化前先复现首次失败；将错误位置与 tile/core/tail 边界、归约轴对照，覆盖契约允许的有符号/无符号、NaN/Inf、零、极值和非对齐输入。

按 [API 与内存约束](../ascendc-api-best-practices/references/api-contracts.md) 核验有效长度、索引 stride 单位、输出覆盖、初始化、累加 dtype、Cast 舍入与目标 SDK 支持。融合或多遍实现可用小规模中间输出或 SDK 支持的 DumpTensor 二分定位；调试输出不构成性能证据，正式测量前移除插桩。

以原始 reference/checker 为正确性权威，不放宽容差、不删困难 case、不改参考来通过优化。改变归约顺序或 Norm 算法需新并行计划和完整正确性验证。保留明确的 accuracy failure，修复作为关联的新尝试。
