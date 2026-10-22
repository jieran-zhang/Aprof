# ApplyAdamW：R2静态更新

新增容量核算确认不能保留原ubFormer直接翻倍输入槽：FP32由20T变36T，低精度由30T变38T。原host按接近可用UB选T，因此必须重算T，比较缩水tile产生的额外循环与潜在重叠。解析shape纠正matrix note：case4实际4096²=16777216而非note67M，case5实际4096×8192=33554432而非note268M。SafeSqrt仍需原v_hat直到GE恢复、SafeDiv仍需分母到最后Select，不能合并这些活区。

具体条件后继：保留host对齐512的blockFormer与输出owner，四路输入队列各配置2物理槽，输出1槽，低精度5个FP32 compute buffer仍1套。T=64k，系数float32=36、half/bf16=38；alpha*T+ceil(ceil(T/8)/256)*256+8192+2048≤B，并保留copy字段上限2097151/s。在当前tile DeQue/读入计算前后为下一tile独立槽预取，队列最大未DeQue数受SDK深度约束，逐代完成后回收。保持SafeSqrt、SafeDiv、weightDecay条件、bias与输出RoundMode全部不变；单tile回退原槽数。

B实际值、目标两槽队列约束和Select内部预留是否仍需8192尚未硬件/SDK确认；8192+2048来自原host源码而非已验证910C资源。

R1未实现/未测量；只能支持源码结构预测，性能预测全部not_tested。父本仍为原始源码，R2不声明implemented C3或加速比。
