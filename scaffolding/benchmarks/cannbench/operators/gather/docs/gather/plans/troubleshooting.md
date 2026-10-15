# gather troubleshooting

## [Phase 7] 极小输出的过度多核切分

**现象：** case 13 仅 1000 个输出却启动 40 cores，真实 NPU 有 249 个输出保持为零；
错误位置按每核 25 元素的区间聚集，index 全部合法且源数据为有效 ±Inf 位模式。

**根因：** 纯标量随机访存 kernel 对极小工作量按所有 vector cores 过度切分，部分极短
core 区间没有稳定完成。

**解决方案：** block 数改为 `min(cores, ceil(numel/4096))`；case 13 单核执行，正常
大 case 仍使用全部 cores。

**经验：** block 数同时受硬件 core 数和最小有效工作量约束。

**预防：** 新标量 kernel 的 tiling 应保留每核最小工作量并包含小输出真实 NPU case。
