# maximum：R2静态复核

R1未实施、未编译、未测量；父本仍为原种子。

抽样对齐完整20case的原rank解码与按外轴/连续内轴公式，证明case11/12/13/20的x1偏移等于linear；case12/13/20的x2索引为floor(linear/W)%H。case18源宽8193*sizeof(half)=16386不是32B倍数，不能靠UB padding声称静态Broadcast合法。int64值域虽小也不能授权cast；优先广播分段，比较语义未核验时保持原scalar compare。

同Action继续的依据是新增全矩阵公式/地址边界复核，性能预测仍not_tested。源代码逻辑工作预测获得静态支持，不等于优化后机器指令已验证。

条件后继：保留sameShape已有Vector路径。针对case11的[rows,513]+[1,513]按整行/行片段搬入；case12/13/20沿最后连续轴W=37/256/101分段，一次解码外轴及读取对应单一broadcast值，生成局部副本后按原max语义计算。U∈{256,512,1024,2048}，单槽UB至少3*A(U*s)+转换/比较临时区+R；广播标量区另计A(s)。FP16 case18维持已有row路径可后续保留8193列分段。int64 case5/19保留64bit比较并单独外提地址解码，禁止转float。未知shape继续原fallback，不用case值域改变dtype。

实际UB、SDK接口及原oracle全量正确性齐备后可进入隔离实施；本轮没有C3。
