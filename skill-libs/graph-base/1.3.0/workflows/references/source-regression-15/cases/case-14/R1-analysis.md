# transpose：R1自主静态方案

目标910C/A3按包内平台映射声明dav-2201适用域，不是设备探测。20个原case完整保留。

TransposeScalar每输出rank次除模、1个原始位宽GM读和1个写；没有Vector或UB分块。

perm[rank-1]==rank-1仅case1/14；其他case输入跨stride，矩形能令搬入/搬出分别连续。

host独立x/y分配；oracle按uint8/16/32/64逐位完全相等，NaN payload不能经float转换改变。

源索引Σcoord*inputStride[perm]是合法perm双射；所有candidate tile的逻辑映射可无交；不同核DMA物理写块是否无交仍unknown，不能由独立x/y或逻辑矩形推出免同步许可。

候选比较：

reorder_contiguous_access：二维矩形转置降低跨stride逐元素GM访问，连续suffix可直接块拷；新增局部重排与UB资源。；状态=selected；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,17,18,19

vectorize_scalar_loop：只对逐元素循环做Vector gather仍可能保留离散GM访问，先把数据通路规则化更直接。；状态=deferred；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

hoist_invariant_control：混合基数递增消除大部分每元素除模，能覆盖复杂perm但仍每元素GM搬运；作为fallback后继。；状态=deferred；case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20

选定具体方案：以bitwise搬运设计三组：case1/14保留连续末轴128/127，按suffix一次DataCopyPad；2D置换case2/3/4/5/7/8/9/11/17/18/19与case13的batched二维采用M×N矩形UB tile（候选16×16、32×32），连续输入行→片内位保持转置→连续输出行。int64按两个uint32通道同时保持8字节元素配对，不做数值Cast。复杂perm case6/10/12可合相邻轴再比较矩形；15/16/20保留通用索引fallback。预算2*A(tileM*tileN*s)+索引表+Tmp+reserve≤UB；逻辑矩形可无交，但DMA物理写许可尚未证明；必须采用后述物理块owner裁切方案。

性能待判：片内转置成本、短行DMA和尾处理是否小于原离散GM逐元素开销，特别int8与127列。

合法性缺项：

constraint.capacity：需要UB_available、目标Transpose/Gather临时区以及地址表物理字节。

constraint.target_api：实际SDK按1/2/4/8字节位宽的局部转置或Gather支持未知；64位需成对32位重排而不是数值转换。

停止比较的理由：主体数据通路、控制、复用与数值边界已分开比较；剩余问题需要目标SDK/UB和后续合法实验，不能通过继续阅读推出当前时延。

物理写条件修正：逻辑矩形无交不能证明不同核的DMA物理写块无交。实际A、GM基址对齐、DataCopyPad尾写粒度/可见性和最终短块不越界均未核验；必须按真实物理块同owner并裁切/汇集输出行段，之后才可将constraint.output_ownership设true。

物理写所有权后继：先核验目标搬出接口的真实物理写粒度A、GM基址对齐、A与元素字节s的整除关系及非对齐尾写契约，A尚未知，不固定成32B或64B。令Q=ceil(totalBytes/A)，按q/r将连续物理块编号分配给核；核c唯一拥有[A*b_c,min(A*(b_c+n_c),totalBytes))。矩形tile只作为计算/搬入分块，每条输出行段须与本核物理字节区间求交后发射；同一物理块即使跨两行也只能由同一核写，必要时该核汇集该块多行片段再单次写回。禁止跨owner补齐写，最后不足A字节只用已验证不越过分配末端的接口或原合法尾路径。API/粒度未证时保留原scalar fallback，不声称矩形DMA就绪。裁切可能重复输入搬运，必须重新计算成本。

case7的1023×1023 float16行跨度2046B；若仅举例A=64，则[1984,2048)横跨第0行末62B与第1行首2B，必须归同一owner。A=64仅示例，未声明目标硬件粒度。
