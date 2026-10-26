# foreach_addcdiv_scalar：R2静态复核

R1未实施、未编译、未测量；父本仍为原种子。

逐20case重新计算chunk数与尾长，所有tensor均远大于U，但真实每核循环次数依赖C_available。d=2且U=2048时FP32数据65536B，16bit数据65536B（raw32768+scratch32768）；U=4096需131072B。这个值是候选字节需求，不是设备容量。若所查可用UB不足，先保持U=2048并降d；若timeline已充分重叠则撤回加槽，转向有合法alias依据的scratch复用。

同Action继续的依据是新增全矩阵公式/地址边界复核，性能预测仍not_tested。源代码逻辑工作预测获得静态支持，不等于优化后机器指令已验证。

条件后继：保留TensorList逐tensor、8Mi元素host chunk、每元素Div→Muls→Add及原Cast。核内用U∈{1024,2048,4096}、输入/输出物理槽d∈{1,2}；首轮CopyIn(0)，DeQue后允许CopyIn(1)，按队列契约交错计算与搬出，末轮drain。d=2仅用于本核tileCount≥2且8*A(U*s)+4*A(4U)*(s!=4)+R≤UB_available；单tile保留d=1。不把模板depth和物理num混为一谈。

实际UB、SDK接口及原oracle全量正确性齐备后可进入隔离实施；本轮没有C3。
