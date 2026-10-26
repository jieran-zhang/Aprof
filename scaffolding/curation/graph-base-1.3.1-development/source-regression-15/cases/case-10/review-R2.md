# sigmoid R2第二次静态复核

20case重算显式UB公式确认双槽在T4096为65536B，不能拿它直接和注释192KiB作容量通过。对1/2/3tile排程审读：prefetch只在当前DeQue后发生，队列未消费上限1；尾t+1先检查域，drain不能遗漏。此为依赖模型复核，不是已证明目标事件实现或实际overlap。

条件后继：获取目标可用UB及SigmoidTmp后保留T4096的双槽候选；SDK生命周期/全部20case正确性通过再看timeline与Task。若增槽并未增加重叠，按同容量域比较单槽T8192；若更短T导致发射增长，保留原T4096单槽。

修订方案：保留每元素Sigmoid/Cast与原任务输出区间。对至少2个tile的owner，输入/输出各2个物理槽；队列模板depth仍1，每次Compute先DeQue当前输入，再发下一tile的CopyIn，最多1个未DeQue，随后CopyOut当前；最后drain。FP32中间计算仅半精度需要，Vector按tile顺序复用fpIn/fpOut，必须保持最后读完成再覆盖。T∈{2048,4096,8192}但首选容量允许时维持4096；U=4*Align32(b*T)+(dtype!=fp32 ? 2*Align32(4*T):0)+SigmoidTmp(T)+reserve≤actualUB。0/1tile或容量不足走原单槽。

未执行候选、构建、native、oracle或性能计时；保留原始父本。
