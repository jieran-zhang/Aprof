# 原始路径与自主比较

Host查询核数/UB并以20T(float)或30T(16位)+mask+8192+2048预算最大合法64对齐tile；四输入一输出。float原地复用五队列，16位四输入Cast到A-D后释放raw输入，再A-E工作及输出Cast。SafeSqrt/SafeDiv保留异常数处理，weightDecay按属性分支。

每输出5s字节GM，5次DMA/tile；float无Cast，16位5次Cast。算术及Compare/Select安全链每tile固定发射，weightDecay非零增加2次。UB float=20T+mask+10240，16位=30T+mask+10240。

首选：仅对16位路径比较四个raw输入8T字节arena与FP32 scratch E的4T字节分时共享，CastInputs最后读完成后才把arena当E；A-D与rawOut仍独立。静态分配从30T降为26T，再在64对齐和相同API预留下扩大T。float维持原路径。

理由：Host已按容量取大tile；把五个raw队列改双槽会从30T升40T(float从20T升40T)并迫使缩tile，增加安全链发射。16位raw输入在Cast后死亡，E在CastInputs后首用有明确可分析的非重叠机会，可降低容量而保持数值链。异步完成和arena API仍需闭合。

残余：float全路径保持不变；16位5次Cast、异常数Select链和5sGM不减。若新增barrier阻塞原来跨引擎重叠，则省容量可能不值，需要与单槽原T和双槽Tprime实际比较。

语义保持方案只变分块/存储/排程，必须保留每元素运算和舍入顺序；未实现，不是正确性通过。
