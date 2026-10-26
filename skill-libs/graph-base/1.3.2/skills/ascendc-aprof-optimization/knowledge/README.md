# 候选实现知识树 v0002

从 [技术入口](ROUTER.md) 按需读取；[格式](FORMAT.md)、[来源](NOTICE.md) 和 [初值](../../../workflows/references/development-records.md#skills-1-3-2) 说明维护方式。正文提供原理、步骤、关键代码、变量单位和适用边界；上游链接与 sources 仅用于归属和校验，不是使用前提。

## 技术分类

| features 标签 | 内容 | 与 C2 的边界 |
| --- | --- | --- |
| tiling-tail | 既定任务内分块、对齐、有效长度、尾块、分发接线 | 不改已选 group/key/entry 条件和任务所有权 |
| memory-transfer | 连续/跨步搬运、合包、预取和 cache hint | 整体遍历与复用域先由 C2 允许 |
| buffer-lifetime | UB/L1/L0 分配、驻留实现、生命周期、别名、Bank 布局 | 保持资源预算和异步依赖 |
| pipeline-sync | 多缓冲、阶段重叠、事件、槽位回收 | 保持协作与交换拓扑 |
| vector-api | 批量 Vector API、mask/repeat/stride、局部算术 | 数学和舍入契约不变 |
| cube-api | Matmul 配置、MMAD 累加、Fixpipe 输出 | MN/Split-K/StreamK 算法和归约所有权归 C2 |
| scalar-control | 地址、循环、参数读取、常量传播和存活期 | 外提必须在正确的不变域内 |
| fusion-composition | 既定算子组合、epilogue、Cube–Vector tile 交接 | 融合区域、所有者和数据通路由 C2 决定 |
| precision-boundaries | 公共数值、容量边界与有效元素约束 | 不是允许放宽语义的加速技巧 |

features 是数组，一次变换可以组合多个分支，但 C3 只记录实际使用条目。技术分类与算子 family 正交，不把每个算子复制成一份完整技术手册。

## 融合的三个维度

融合决定哪些计算阶段组合；数据通路决定中间张量通过 GM 还是目标允许的片上路径交换；流水决定不同 tile 的重叠。三者应分别说明。A3/2201 的 GM 中转与 950/3510 的片上直通不能互换，融合不保证消除中间 GM 读写。

## 选择与实现

输入为 C2 快照、实例参数、实现自由度及当前源码/架构证据。每个 recipe 包含实现步骤、代码上下文、参数单位、资源与组合条件、失败边界；平台专用 API 明确范围。普通 API include 使用正常 CANN SDK，不引用上游工程私有头文件或下载目录。

unknown/false/proxy 前提不能由模板补成真。C3 改变算法、任务/输出所有权、归约顺序或全局交换方案时请求重规划。本树当前均为来源审读，不把示意片段或上游收益写成目标平台性能资格。
