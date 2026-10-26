# resize_bilinear：R2静态复核

R1未实施、未编译、未测量；父本仍为原种子。

按20case解析scale_factor到真实outH/outW，逐输出列枚举w0/w1集合并算span与unique数；整2倍下采样源pair不重叠，跨输出reuse不成立；8倍上采样case5共享源区显著，复用策略须分组。源行边界clamp使h0==h1或w0==w1允许读复用却不允许删四项运算：0*Inf/NaN仍影响结果。若API/精度不满足，只先外提oh相关坐标且仍用原ResizeOne算术，不声称Vector方案已实现。

同Action继续的依据是新增全矩阵公式/地址边界复核，性能预测仍not_tested。源代码逻辑工作预测获得静态支持，不等于优化后机器指令已验证。

条件后继：固定(nc,oh)后按Wtile∈{64,128,256}输出列分片；用原FP32 ResizeCoord直接算每个ow的w0/w1/dw，禁止累加scale递推。读入所需两源行的有界区间，按索引从UB取a/b/c/d，再批量执行原a*ah*aw+b*ah*dw+c*dh*aw+d*dh*dw的乘加顺序和最终Cast，不启FMA。强下采样若连续源span大于4*Wtile则用保守索引fallback或仅搬稀疏需要点；上采样保留两源行窗口。容量2*A(span*s)+至少A(7*4*Wtile)+输出raw+索引表+Tmp+reserve≤UB。所有20case分组执行，输出连续片归单核。

实际UB、SDK接口及原oracle全量正确性齐备后可进入隔离实施；本轮没有C3。

完整语义条件修正：ResizeCoord索引域和四项插值表达式可由源码恢复，但手写half/BF16解码的次正规数/NaN处理与目标Cast、Vector乘加舍入/融合、正负零和Inf传播的全域等价尚未核验。完整constraint.semantic_equivalence保持unknown，不由clamp/地址证明推成true。 数学映射另记为source.element_mapping_equivalence=true；Vector方案继续作为条件方案。
