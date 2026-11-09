# 本地知识索引

只读取能解决当前疑问的资料。这些提炼内容随 AProf 发布；NOTICE 中的来源链接用于追溯，不是运行时外部技能依赖。

| 疑问 | 本地资料 |
| --- | --- |
| SoC/ISA、A2/A3、可用核/内存与证据可信度 | 平台证据（同名参考，非历史原件：[platform-evidence.md](../../../../../../skills/npu-arch/references/platform-evidence.md)） |
| RegBase、SIMT、CV 路径变化和 SDK 特性 | 3510 执行约束（同名参考，非历史原件：[regbase-simt.md](../../../../../../skills/npu-arch/references/regbase-simt.md)） |
| 搬运对齐/尾块、buffer/event、repeat/mask、Cast/Reduce/MatMul/Sort | API 约束（同名参考，非历史原件：[api-contracts.md](../../../../../../skills/ascendc-api-best-practices/references/api-contracts.md)） |
| MTE 设置/带宽、Scalar/Vector 热循环、双缓冲、驻留、流水间隙 | [执行机制](../../ascendc-perf-optimize/references/execution-mechanisms.md) |
| Norm/Reduction、Sort/TopK、MatMul/GMM、FA/Softmax 分解 | [算法族](../../ascendc-tiling-design/references/algorithm-families.md) |
| 元数据条件、tiling key、真实 Host/Kernel 分发和 fallback | [Tiling 分发](../../ascendc-tiling-design/references/tiling-dispatch.md) |

记录所读路径、实际内容 hash、目的和对应候选/计划。参考资料提供机制或约束，不能替代当前 source/workload/profile 证据；准确 API 仍不确定时，按本地 `ascendc-docs-search` 检查已安装 SDK 与匹配版本的官方文档。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../../../sources/document-originals/01d497c69b0fb8af56ff552c7eb8a20c5c7248aa6782a47182eba0e65b41b17b.txt)。
