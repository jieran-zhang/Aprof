# strided_slice R1当前源码事实与方案

Host将masks归一化为outputShape/sourceStep/sourceBase；kernel每输出做2*outputRank次除模并Raw单元素GM拷贝。输出64字节对齐分核，必须保留物理独占边界。所有原case正stride，负stride仍走原fallback。

基于归一化metadata合并最长连续尾段：跳过size1轴，要求最后有效axis step=1，继续合轴条件sourceStep[d]=当前run长度。每核仍持有原64B边界输出区间，与run交集切段；每段起点只解码一次，用DataCopyPad按有效字节搬入单独UB槽并搬出同宽位模式。T∈{256,1024,4096}元素，U=2*Align32(T*itemBytes)+API_reserved≤availableUB；不补读GM、不跨不连续行空洞。run=1、负stride、未支持API保留原逐元素路径。

11个case存在100至1048576等长度连续段，批量搬运同时去掉逐元素拷贝和段内rank解码；地址外提对其余9case有价值但保留每元素Scalar访存，作为最强替代。

输入快照含完整host/tiling/kernel、原20case、定义及oracle。所有数值为源码/公式，非profiling；基线assumed。

所有原case均保留：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
优化适用case：2,7,10,11,13,14,16,17,18,19,20
其余原case走明确fallback，同样属于完整后续正确性/性能域。

语义审查：沿用host masks归一化，输出位模式逐位相同；连续段内地址等差1，边界按原64字节owner切断。

逐项实施条件依据：
constraint.semantic_equivalence：归一化sourceBase/Step不变，连续run内source(root+k)=source(root)+k；按同宽Raw搬运全部有效元素且排除补齐区，原负stride/不支持域保留fallback。
constraint.layout_semantics：没有axis置换或dtype转换；仅把同一owner的连续地址段批量表达，输出位置与输入位模式逐一对应；跨行空洞终止合轴。

源码复合观察分量：
row gap例case2 sourceStep=[2048,1], outputShape=[2047,2047]，跨行地址非连续；全连续case只使用该Action的连续段批量表达，不据此声称每case均非连续瓶颈。
ComputeStridedSliceTiling归一化各mask，输出地址为sourceBase+Σcoord*sourceStep；完整20case重算表保存step与最大地址。
baseline无DataCopy结构体；每次Raw指针加载/存储为itemBytes，blockLength为元素，分核按64/itemBytes对齐；未来DMA字段合法性独立unknown。
