# case-14 transpose：无硬件两轮自主分析

选定 `action.reorder_contiguous_access`，R1/R2均为conditional_plan。R1未生成候选源码，R2只补静态证据；性能not_measured。原20case全部纳入成本与回归范围，特化适用case=1,2,3,4,5,6,7,8,9,10,11,12,13,14,17,18,19；其余保留原fallback。

目标910C/A3→dav-2201只表示任务声明的目标适用域，依据platform-basis.json；不是硬件探测。实际SKU/可见核/可用UB/SDK/API支持均未伪造。

## R1具体方案

以bitwise搬运设计三组：case1/14保留连续末轴128/127，按suffix一次DataCopyPad；2D置换case2/3/4/5/7/8/9/11/17/18/19与case13的batched二维采用M×N矩形UB tile（候选16×16、32×32），连续输入行→片内位保持转置→连续输出行。int64按两个uint32通道同时保持8字节元素配对，不做数值Cast。复杂perm case6/10/12可合相邻轴再比较矩形；15/16/20保留通用索引fallback。预算2*A(tileM*tileN*s)+索引表+Tmp+reserve≤UB；逻辑矩形无交不代表DMA物理写独占，现为output_ownership unknown。

## 机会比较

- action.reorder_contiguous_access（selected，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,17,18,19）：二维矩形转置降低跨stride逐元素GM访问，连续suffix可直接块拷；新增局部重排与UB资源。
- action.vectorize_scalar_loop（deferred，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：只对逐元素循环做Vector gather仍可能保留离散GM访问，先把数据通路规则化更直接。
- action.hoist_invariant_control（deferred，case 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20）：混合基数递增消除大部分每元素除模，能覆盖复杂perm但仍每元素GM搬运；作为fallback后继。

## 全20case源码成本

以下为逻辑字节/源码操作计数，不是HBM实测，也不能换算为时延。完整shape、dtype、分发与其他成本列见R1-source-costs.json。

| case | dtype | 输出元素数 | 逻辑GM读写字节 | 结构差异 |
|---|---|---:|---:|---|
| 1 | float16 | 134217728 | 536870912 | suffix=128; scalar除模=1073741824 |
| 2 | float32 | 4194304 | 33554432 | suffix=1; scalar除模=16777216 |
| 3 | bfloat16 | 16777216 | 67108864 | suffix=1; scalar除模=67108864 |
| 4 | int32 | 67108864 | 536870912 | suffix=1; scalar除模=268435456 |
| 5 | int64 | 33554432 | 536870912 | suffix=1; scalar除模=134217728 |
| 6 | int16 | 1179648 | 4718592 | suffix=1; scalar除模=9437184 |
| 7 | float16 | 1046529 | 4186116 | suffix=1; scalar除模=4186116 |
| 8 | float32 | 1030189 | 8241512 | suffix=1; scalar除模=4120756 |
| 9 | bfloat16 | 1181953 | 4727812 | suffix=1; scalar除模=4727812 |
| 10 | int32 | 49691433 | 397531464 | suffix=1; scalar除模=298148598 |
| 11 | float16 | 1051137 | 4204548 | suffix=1; scalar除模=4204548 |
| 12 | float32 | 1092273 | 8738184 | suffix=1; scalar除模=8738184 |
| 13 | bfloat16 | 917504 | 3670016 | suffix=1; scalar除模=7340032 |
| 14 | float32 | 908558 | 7268464 | suffix=127; scalar除模=7268464 |
| 15 | float16 | 10912759 | 43651036 | suffix=1; scalar除模=109127590 |
| 16 | int64 | 3042039 | 48672624 | suffix=1; scalar除模=30420390 |
| 17 | float32 | 1049088 | 8392704 | suffix=1; scalar除模=4196352 |
| 18 | bfloat16 | 2089215 | 8356860 | suffix=1; scalar除模=8356860 |
| 19 | int8 | 2093567 | 4187134 | suffix=1; scalar除模=8374268 |
| 20 | float16 | 2094078 | 8376312 | suffix=1; scalar除模=12564468 |

## R2新增静态证据与条件后继

20case样本验证逆映射与perm双射，连续suffix仅case1/14（128/127元素）；case13保持batch前缀可降14个256×256转置。case6可视作B=2的9×65536转置，case10可视作133221×373，case12为B=3的91×4001；能合轴不代表小C专用Gather API适用。int64/NaN原始位必须保留。先实施通用矩形和suffix，若32×32转换temp超预算退16×16而非缩dtype。

没有R1性能结果可支持/否定加速；逻辑映射检查成立，但物理owner裁切新增代价未定，前轮源工作预测为unresolved。R2-static-evidence.json给出每个case检查对象和结果。

## 实际阅读与采用

P/O全树咨询与Action绑定P路由回执均已保存；以下是条件方法采用，未形成正式C2 selection或C3执行。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.noncontiguous_access.md` lines:329-341：二维矩形转置降低跨stride逐元素GM访问，连续suffix可直接块拷；新增局部重排与UB资源。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.scalar_control_hot_loop.md` lines:292-304：只对逐元素循环做Vector gather仍可能保留离散GM访问，先把数据通路规则化更直接。

- diagnosis：`skills/ascendc-aprof-diagnosis/graph/problems/problem.control_metadata_overhead.md` lines:310-322：混合基数递增消除大部分每元素除模，能覆盖复杂perm但仍每元素GM搬运；作为fallback后继。

- parallel-planning：`skills/ascendc-aprof-parallel-planning/knowledge/families/layout/templates/transpose.md` lines:51-69：transpose正文53要求不同owner不因DMA对齐触及同一物理块，故撤回output_ownership=true。采用真实A全局物理块同owner、矩形行段与owner区间求交，尾块须核验有效写许可；原矩形思路保留为条件方案。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md` lines:76-88：transpose仅连续suffix或局部重排后的输出行片可合并；输出行片先裁切至真实物理块owner，不能跨owner补齐写。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md` lines:85-97：transpose批量重排必须保持原始位；count或mask不能保护GM写，且局部位宽重排API与物理写owner分别待核验。

- optimization：`skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md` lines:70-82：外提只减少地址控制，不会自行改善离散GM；复杂perm保留混合基数递增fallback，矩形方案优先解决数据通路。

检索目录28个Problem全量审视后按源码问题展开，不用邻接top-k锁候选；D的每个候选分别绑定自己使用的Problem正文、适用依据与反证。未采用模板无需伪装已实施。

## 不能判断及后续补项

- constraint.capacity：需要UB_available、目标Transpose/Gather临时区以及地址表物理字节。
- constraint.target_api：实际SDK按1/2/4/8字节位宽的局部转置或Gather支持未知；64位需成对32位重排而不是数值转换。
- 性能：片内转置成本、短行DMA和尾处理是否小于原离散GM逐元素开销，特别int8与127列。

源事实、source refs/hash、原矩阵、R1/R2 reasoning/decision、expansion、P/O route、阅读记录均在本目录。C1按handoff/v3 schema与reasoning/decision校验；严格C2缺真实architecture与parallel/dispatch implementation绑定，未伪造。没有C3、计时结果、加速比或训练记录。

路由阶段区别：全树P/O咨询、Action绑定P候选、条件方法采用分别见route-selection-status.json；未生成正式C2 selection或C3 execution。逐项true条件的源码/数学证明见condition-audit.json。

独立复核修正：逻辑矩形无交不能证明不同核的DMA物理写块无交。实际A、GM基址对齐、DataCopyPad尾写粒度/可见性和最终短块不越界均未核验；必须按真实物理块同owner并裁切/汇集输出行段，之后才可将constraint.output_ownership设true。

物理写所有权后继：先核验目标搬出接口的真实物理写粒度A、GM基址对齐、A与元素字节s的整除关系及非对齐尾写契约，A尚未知，不固定成32B或64B。令Q=ceil(totalBytes/A)，按q/r将连续物理块编号分配给核；核c唯一拥有[A*b_c,min(A*(b_c+n_c),totalBytes))。矩形tile只作为计算/搬入分块，每条输出行段须与本核物理字节区间求交后发射；同一物理块即使跨两行也只能由同一核写，必要时该核汇集该块多行片段再单次写回。禁止跨owner补齐写，最后不足A字节只用已验证不越过分配末端的接口或原合法尾路径。API/粒度未证时保留原scalar fallback，不声称矩形DMA就绪。裁切可能重复输入搬运，必须重新计算成本。

R2源工作预测由supported收紧为unresolved；新增物理owner裁切代价尚待闭合，性能仍not_tested。

所有已知constraint.ref.locator现逐谓词定位condition-audit.json的basis字段，并提供原host/tiling/kernel/原oracle精确行引用；无lines:1标题充作证明。
