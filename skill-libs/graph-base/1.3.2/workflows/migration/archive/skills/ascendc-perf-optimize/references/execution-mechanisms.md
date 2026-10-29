# 固定并行计划下的执行机制

使用实际目标档案、workload group、父源码和测量证据。小工作量低利用率先按可达上限解释，只有具体证据才判为实现瓶颈。

| 证据 | 候选方向 | 反证与检查 |
| --- | --- | --- |
| 短 MTE 指令多、带宽低 | 合并连续搬运，批量处理小 scale/bias 表，减少地址设置 | MTE 时间高不证明带宽饱和，比较实际字节与搬运次数 |
| 未变张量反复读 GM | 容量和存活期允许时驻留复用数据 | L2 共享且不保证驻留，计入全部存活缓冲和完整 workload |
| 双缓冲下搬运与计算仍串行 | 分开序幕、稳态、收尾，在消费当前槽前提交下一生产任务 | 两个队列槽不证明重叠，检查 trace 依赖和全部尾块路径 |
| 融合链 Vector 指令多 | 等价融合、减少 Cast/UB 往返；确认 3510 后评估 VF 寄存器驻留 | 保留中间精度和特殊值，检查指令数与寄存器溢出 |
| Scalar 控制主导 | 外提元数据/地址不变量，合法常量索引，减少热循环状态机 | 保留动态 shape，不能固定 benchmark 尺寸或用更贵 Vector 替换每个 Scalar |
| 流水未饱和却有空隙 | 检查等待、任务粒度、缓冲复用与发射顺序 | 更多 buffer/核可能增加开销，依据关键依赖链 |
| 怀疑容量或 bank 冲突 | 算存活区间与对齐字节，调整 padding/layout/复用 | bank 行为依赖架构，padding 增加占用且需证据 |

容量公式为 `sum(aligned live allocation bytes × simultaneously live instances) + scratch + reserved memory`。包含队列深度、阶段缓冲、Cast 中间态、API 临时区和同步 workspace。大 tile 可同时减少循环开销、降低重叠；同一计划和 group 内一次探索一个有界变量。

MatMul 固定分解下，从 L0A/B/C 容量选 baseM/baseN/baseK，从复用和双缓冲选 L1 step，并计入累加精度。Full-load 要求复用侧整个存活期都装得下；ping/pong 与预取需合法生产消费顺序，分别分析 PONG 间隙和收尾。小量化 scale 是独立流量，可能适合合并；改变 M/N 所有权、split-K 或 StreamK 属于并行计划修订。

Softmax/attention 的 running max/sum/output 只由所属任务维护，按声明精度归一化。workspace 用真实 task/split 索引，不能复用 block slot 代替。寄存器或 UB 驻留需与并发缓冲同时容纳，更大 S2 tile 不保证更快。

Sort/reduce 每种 merge/reduction 宽度都验证 scratch 和尾 mask。不能把记忆中的 MrgSort proposal 宽度、repeat 上限或索引打包套到其他 SDK；跨核合并/归约属于算法并行决策。

报告预期指标方向、反证、源码锚点、资源公式、API 来源与首次失败。统一计时（同名参考，非历史原件：[unified-timing.md](../../../../../../skills/ascendc-aprof-profiling/references/unified-timing.md)） 与机制 PMU 分开记录。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../../../sources/document-originals/117f27ba6fb7cd69f3e5c6f32448b052d958a8e70e5c4dad044a34aa47aec071.txt)。
