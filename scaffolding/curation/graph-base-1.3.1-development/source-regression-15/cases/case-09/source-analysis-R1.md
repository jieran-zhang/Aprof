# gelu R1当前源码事实与方案

所有mode固定T1024；两Raw队列加fi/work/fo三个FP32区、Erfc5*T FP32 scratch以及mask无条件分配。显式UB=(2*b+32)*T+Align256(ceil(T/8))，尚不含API/编译保留；tanh不访问erfTmp/mask。none仍有Erfc和尾部特殊修正；tanh有2^-23网格RINT转换，不是无意义cast。

保留none/tanh定义和全部Cast/尾部修正。在Init按mode分配：none保持原erfTmp/mask；tanh省去两项无用分配。基于mode,dtype合法容量选择T：tanh{1024,2048,4096}，none{1024,2048}，T均64整数倍。tanh U=2*Align32(b*T)+3*Align32(4*T)+APIreserve；none另加Align32(20*T)+Align256(ceil(T/8))。只有U≤actualUB且count API允许才选择较大T，否则原1024分支。直调用实际mode字段/template分支接线，不伪造TILING_KEY_IS。

直接删掉tanh永不使用的20*T+mask静态字节，给更大tile提供可核算空间；相比强行复用none临时区，避免Erfc输入/tmp重叠未证问题。容量节约本身不是加速，收益假设来自同算术较少tile循环/API发射。

输入快照含完整host/tiling/kernel、原20case、定义及oracle。所有数值为源码/公式，非profiling；基线assumed。

所有原case均保留：1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20
优化适用case：4,5,6,8,10,12,14,17,19
其余原case走明确fallback，同样属于完整后续正确性/性能域。

语义审查：mode域穷尽none/tanh；删除tanh永不读的分配而不删除算术；RINT与Erfc负尾处理保留。

逐项实施条件依据：
constraint.semantic_equivalence：mode==tanh路径从未读取erfTmp或mask；删其分配不改变算术，较大T仍逐元素同一指令链，无归约；保持RINT、none尾修正与输出Cast。API计数范围另外待核对。
constraint.dispatch_coverage：host Mode只接收none/tanh，两分支互斥且穷尽；每dtype分别按已核算容量合法域选T，未支持或不满足分支回原T1024。不是按case编号分派。

源码复合观察分量：
ComputeGeluTiling对none/tanh及全部dtype都固定tileElements=1024，Init统一分配Erfc5数组和mask。
host Mode/DType解析→tiling mode/dtype→kernel模板与Compute mode分支的路径明确；每case参数完整列出。
host包括同一gelu_kernel.asc与gelu_tiling.h直接调用，mode enum字段对应。
