# SwiGLU：R2静态更新

静态检查每个20case的S与Q；case12 S1,Q1000003意味着原约1000003小段与3000009次DMA（核边界不会增加S1段数），而R1024需要977个批次加核分区尾部，具体核数未探测。case9 S7有133221段，case20 S50有52224段。CPU枚举小R映射是一一对应且无多读；数据量不减，只减少指令组织。S=1的input相邻值交错，R批量不能直接把前R个当x0。

具体条件后继：C2重新规划短S组的整段owner：Q=N/S段，核c分配[q0,q1)，处理R个完整段，R≥2且RS≤T、(5s+12·[s=2])RS+shuffleTmp≤B。一次读x[2qS:2(q+R)S]到packed，再以a[rS+j]=raw[2rS+j], b[rS+j]=raw[2rS+S+j]作UB向量重排；保持原Cast及Muls/Exp/Adds/Div/Mul，最后写y[qS:(q+R)S]。优先S∈{1,7,50}，候选R使RS≈512/1024/2048；其他S及API无法合法高效重排时走原segment路径，所有20case都覆盖。不能用逐元素GetValue实现shuffle冒充高效向量化。

真实架构/SDK上的UB重排、Gather/Deinterleave或合法strided重载、支持dtype、mask/stride单位及Tmp字节未知；已能证明映射和完整段owner，不能借950/3510能力补证。

R1未实现/未测量；只能支持源码结构预测，性能预测全部not_tested。父本仍为原始源码，R2不声明implemented C3或加速比。
