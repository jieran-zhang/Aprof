# 原始路径与自主比较

Host连续分块；每tile CopyIn→Compute→CopyOut单槽链。FP32路径Adds拷贝输入，stable softplus、额外Exp负尾修正、Tanh、两次Select与Mul，再Adds拷贝输出；16位Cast进出。Compare对齐64元素。

每输出2s字节GM；每tile 2次DMA和15次Vector API（包含输入/输出Adds或Cast）；mask按256B向上对齐。静态UB=(2s+12)T+align256(ceil(T/8))。

首选：保留所有负尾修正、Compare对齐与舍入，先比较单槽T=2048→4096的连续tile合并，若容量及API上界允许，原任务数不变，减少DMA和整条Vector链的发射次数。T未测最优。

理由：15步Vector链使纯流水不会减少主要计算工作；T翻倍将各长核的DMA及整条链接口发射约减半，且可参数化，不改算法和owner。双槽仍有价值但需要新增槽和事件，待发射/稳态时间证据再比较。

残余：稳定softplus的Exp/Ln/Tanh和两次Select、每输出2sGM均保留；FP32 Adds(identity)可能涉及±0，不能套coalesce_cast直接删除。

语义保持方案只变分块/存储/排程，必须保留每元素运算和舍入顺序；未实现，不是正确性通过。
