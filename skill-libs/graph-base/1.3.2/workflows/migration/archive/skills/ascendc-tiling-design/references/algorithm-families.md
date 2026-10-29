# 并行算法族

执行调优前，按 workload group 从数学等价方案中选择，记录独立任务、每任务工作量、复用、同步、通信/workspace 字节和精度。任务数可大于物理核，但仍受启动与资源限制。

| 算子族 | 计划候选 | 选择与语义约束 |
| --- | --- | --- |
| Elementwise/broadcast | 连续输出分区；保留 broadcast 复用的行/轴分区 | 小工作量可用少任务；每输出一个写者；计入 stride 和广播读取 |
| RMSNorm/GroupNorm/Reduction | 整行所有权/full-load；流式/两遍；拆分归约再合并 | 行够多时整行可免同步；少数长行可考虑拆分。保持累加 dtype、epsilon 位置和轴；Welford 对应方差语义，不能无条件替代 RMS |
| MatMul/GMM | M/N tile；均衡 tile 次序；split-K/StreamK 部分累加 | M/N 任务够多时优先独立 tile，长 K 且任务少才评估额外 workspace/归约；保留 batch/group、转置、bias、累加 dtype |
| Softmax/attention | 行内稳定两遍或在线状态；split KV 后稳定合并 | 合并时重新缩放 max/sum/output；mask、causal、paged 边界决定合法区域；显式 workspace 所有权和最终合并 |
| Sort/TopK/Unique | 独立行/局部排序；多级 merge；语义允许的 radix/partition | 保持 key dtype、稳定性、相等值/索引、NaN 和输出基数；merge 增加流量和同步，不能假定 benchmark 输入有序 |
| Segment/scatter | 输出段所有权；输入分区加 atomic 或分阶段归约 | 碰撞/偏斜影响争用；确定性可能排除 atomic，显式初始化 workspace 和完成 barrier |
| Resample/transpose/gather | 输出所有权与连续写；输入缓存/分块复用；受支持 DMA 布局变换 | 保持坐标舍入、padding/边界和重复索引语义，NDDMA 需目标/API 证据 |

架构改变合法性和成本，不改变算子语义。2201 分别按可见资源规划 AIC/AIV。A3 共用 ISA，但 device/die/topology 和 SKU 资源可不同，不能按封装 die 数乘单设备核数。3510 可考虑 RegBase、非规则索引 SIMT 和新 CV 路径，先核算寄存器/UB/DCache 与 SDK 支持。

算法修改先通过独立正确性，再按 统一协议（同名参考，非历史原件：[unified-timing.md](../../../../../../skills/ascendc-aprof-profiling/references/unified-timing.md)） 计时。tile/buffer/pipeline 候选前冻结所选计划及 hash；保留被拒算法计划，不能混入仅执行调优记录。

> 文档适配说明：本页已修复引用；缺失材料的链接已移除，同名补充参考不代表历史原件。来源及历史回放使用[保留的证据原文](../../../../../../sources/document-originals/9036a42db1a5c59c0df65aa065346ee5b6e0e951ac7e22f0522b96c8bfb3bd9b.txt)。
