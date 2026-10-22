# apply_rotary_pos_emb：R2静态复核

R1未实施、未编译、未测量；父本仍为原种子。

遍历D=64/128所有维度证partner映射在行内、两次partner回到原维度；half mode两半闭式等价。原源码对每维4个volatile乘积和2个加法（q/k），使Scalar瓶颈假设比单纯字段缓存更具体；原特殊case13 Inf、14 NaN仍不能由CPU地址证明精度。R1不先融合cos复用，因为case13 N=1完全没有跨head复用；BNSD相邻row改变seq，不能把前row trig盲目驻留。

同Action继续的依据是新增全矩阵公式/地址边界复核，性能预测仍not_tested。源代码逻辑工作预测获得静态支持，不等于优化后机器指令已验证。

条件后继：先对half rotary mode按H=D/2两个连续半区使用FP32 Mul/Mul/Add，负半保留sign乘法或经数值审查的Neg，不用FMA；q/k各两半，输出最终Cast保持half CAST_NONE、bf16 CAST_ROUND。按原row owner处理，行批R∈{1,2,4,8}，原5D个FP32元素和低精度5D个raw元素，加双乘积scratch最多4D float：UB≤A(36RD)+I16*A(10RD)+Tmp+reserve。interleaved保持原路径，待SDK确认去交错/重排索引后独立候选。全部20case原路径覆盖。

实际UB、SDK接口及原oracle全量正确性齐备后可进入隔离实施；本轮没有C3。

完整语义条件修正：half-mode partner/row映射和目标算术表达式已经静态证明，但目标Vector Mul/Muls/Add是否保留原volatile FP32逐步舍入、正负零、NaN/Inf传播，以及half CAST_NONE和BF16 CAST_ROUND，尚无完整API/编译语义依据。constraint.semantic_equivalence包含这些条件，故保持unknown；不能用数学映射代替全域等价。 数学映射另记为source.element_mapping_equivalence=true；Vector方案继续作为条件方案。
