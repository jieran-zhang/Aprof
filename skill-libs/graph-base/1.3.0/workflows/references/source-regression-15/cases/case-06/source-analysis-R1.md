# gather R1当前源码事实与方案

GatherScalar 对每输出读取一个 index 和一个 x 并写一个 y；rank=r 时源码含2*r*N个64位除/模表达式，另有r*N次stride乘加。必要逻辑请求N*(indexBytes+2*xBytes)不等于HBM。主机逐index拒绝越界；kernel另有guard。tiling=ceil(N/C)，C=min(ceil(N/4096),actualAIV)。

保持原每核输出区间和Raw按位拷贝；每核begin只解码一次indexShape坐标，base=Σ(d≠dim)coord[d]*xStride[d]。逐元素用base+index[linear]*xStride[dim]读取；mixed-radix odometer按indexShape进位，以xStride加/减更新base，gather轴不加入base。rank1直接x[index]。只缓存rank、dim及实际使用stride/shape，最多8轴；不引入全量索引表、workspace或UB分配。保留host拒绝/设备guard及各dtype位模式；源shape非gather轴不等长仍用原xStride。

相比仅缓存TilingData字段，这会删除整个每元素rank除模；相比尾轴UB Gather，它覆盖全部20case且不为稀疏随机源做整行/窗口读放大。随机x访问可能仍主导，因此不声称当前瓶颈或收益。

输入快照含完整host/tiling/kernel、原20case、定义及oracle。所有数值为源码/公式，非profiling；基线assumed。

所有原case均保留：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
优化适用case：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
其余原case走明确fallback，同样属于完整后续正确性/性能域。

语义审查：index负值/越界host拒绝，device guard保留；Raw按位，非gather维用X stride。

逐项实施条件依据：
constraint.semantic_equivalence：由坐标解码定义和odometer归纳：每次进位保持base=Σ(d≠dim)coord[d]*xStride[d]；同一index值和原device guard，Raw读写位模式不变。
constraint.control_equivalence：仅把shape/stride/rank/dim等同launch不变值置循环外，linear按原顺序增加；每次进位更新量为已定义X stride，保留无效index分支。
constraint.capacity：本意图不增加UB/L1/GM workspace、DMA或大tensor；至多8个uint64坐标和少量标量。寄存器分配或spill影响性能而非既定UB分配合法性；若编译器拒绝则不能实施。

源码复合观察分量：
kernel的每linear循环含rank次rem%indexShape、rem/indexShape与source stride乘加。
indexShape/xStride/rank/dim由host单次写入后只读；linear/rem变化，公共地址坐标可按进位更新。
host ComputeGatherTiling写struct，经同大小H2D传给kernel原类型指针，字段对应可逐项核对。
