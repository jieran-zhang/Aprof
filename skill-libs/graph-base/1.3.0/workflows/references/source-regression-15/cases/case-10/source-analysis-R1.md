# sigmoid R1当前源码事实与方案

单物理输入/输出槽，CopyIn-Compute-CopyOut按tile4096顺序。FP32直接Sigmoid，半精度仅在边界各Cast一次并保留FP32中间两个区。必要逻辑GM为2*N*b，显式UB FP32=8*T，half/BF16=12*T；原192KiB注释不能认作目标资源。

保留每元素Sigmoid/Cast与原任务输出区间。对至少2个tile的owner，输入/输出各2个物理槽；队列模板depth仍1，每次Compute先DeQue当前输入，再发下一tile的CopyIn，最多1个未DeQue，随后CopyOut当前；最后drain。FP32中间计算仅半精度需要，Vector按tile顺序复用fpIn/fpOut，必须保持最后读完成再覆盖。T∈{2048,4096,8192}但首选容量允许时维持4096；U=4*Align32(b*T)+(dtype!=fp32 ? 2*Align32(4*T):0)+SigmoidTmp(T)+reserve≤actualUB。0/1tile或容量不足走原单槽。

可保持原T而提供真实双物理槽和预取窗口，直接检验原排程可避免等待；相比只增大tile，未把更大临时区当作必需。cast删除缺等价依据且不会消除必要数学计算。

输入快照含完整host/tiling/kernel、原20case、定义及oracle。所有数值为源码/公式，非profiling；基线assumed。

所有原case均保留：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
优化适用case：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
其余原case走明确fallback，同样属于完整后续正确性/性能域。

语义审查：每元素输出只依赖对应输入；保持Sigmoid API及Cast；跨tile独立，但异步槽完成边需SDK证明。

逐项实施条件依据：
constraint.semantic_equivalence：所有输出y[i]只依赖x[i]，输入输出分配互不别名，无跨tile数学依赖；保留Sigmoid及两次Cast位置，交错发射只影响独立tile顺序。异步存储lifetime另列unknown。

源码复合观察分量：
Process每tile按CopyIn→Compute→CopyOut提交，下次CopyIn在当前CopyOut之后，物理输入/输出各1块。
CopyIn EnQue→Compute DeQue/Free与Compute EnQue→CopyOut DeQue/Free源码明确；尚不推断硬件完成顺序。
循环数为ceil(length(C,c)/4096)，首尾由off/count控制；Sigmoid内部实现未读到当前SDK，因此仅把外层队列顺序作为结构事实，不声称内部完全串行。
