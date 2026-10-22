# 原始路径与自主比较

Host将split轴之后的连续积乘半轴得到segment S；输出N=input/2。核按连续输出块切分，每次count=min(remaining,4096,S-inSegment)，x0=out+floor(out/S)*S，x1=x0+S，两个输入片对应一个输出片。Vector执行sigmoid门链，16位三次Cast。

每输出3s字节GM；每段3次DMA；float每段5个算术API，16位另3次Cast。UB float=12T，16位=18T。短S使主循环不是ceil(N/4096)，而每核切开的segment片计数。

首选：先仅在同owner的短segment内组成h行批次，以blockCount/stride搬运x0和x1并批量计算，输出按连续有效行写回；物理行跨度A=align32(S*s)/s须与S分开。长segment维持原路径；不新增Tiling Key，参数由连续性/API和容量决定。

理由：短segment时增加流水仍保持每段三次小DMA和整条Vector发射；规则多行批量可直接减少这类发射。输入不是跨segment连续，不能简单count扩大；需合法strided API或UB行拼接，短行padding成本计入。

残余：长segment原有单槽链仍未优化；短segment中的Exp/Div和3s有效GM仍保留。若多段API因跨度不合法退回逐行搬运，批量Vector仍需独立核算，不能声称DMA必然减少。

语义保持方案只变分块/存储/排程，必须保留每元素运算和舍入顺序；未实现，不是正确性通过。
