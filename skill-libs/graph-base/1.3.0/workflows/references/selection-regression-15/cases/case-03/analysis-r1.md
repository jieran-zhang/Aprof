# 原始路径与自主比较

同形x/mask按输出连续切块，两个输入一个输出；x扩位、mask扩位（int8/uint8经half再float），先Mul(x,mask)后Muls(scale)，再输出转换。mask是数值乘数，127/255非布尔。

每输出(2s_x+s_m)字节GM；每tile 3次DMA和5次Vector API，整数mask为6次。UB=(2s_x+s_m+12+2I_intmask)T。

首选：两个输入队列和输出队列使用两物理槽，FP32计算缓冲保持单份；原Mul后Muls顺序及整数mask两段Cast保留。预算(2*(2s_x+s_m)+12+2I_intmask)T+API<=可用UB。

理由：所有输入一次读取，无广播复用，计算链较短而有三路搬运；流水比一味放大tile更直接检验隐藏MTE延迟。T=4096的转换区已较大，放大tile的容量成本须与新增原始槽比较。

残余：整数mask两次Cast、FP32拷贝Muls和必要三路GM保留。后续可在确证目标Cast重载后单独比较转换路径，不按case ID分派。

语义保持方案只变分块/存储/排程，必须保留每元素运算和舍入顺序；未实现，不是正确性通过。
