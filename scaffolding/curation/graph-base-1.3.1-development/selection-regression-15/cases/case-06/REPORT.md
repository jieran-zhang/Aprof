# case-06 gather

R1优先：action.hoist_invariant_control。模式：conditional_plan。未实施、未编译、未测量。

Host验证同rank/非gather轴上界与index取值；按线性输出分核，逐输出读取index，rank轴除模得到源地址，再按存储位宽读取源/写出。

2*N*d 次除/模；N次index读、N次源读和N次输出写；有效请求N*(2*b+i)字节；B=min(ceil(N/4096),C_available)，无UB分配。



## R1比较

### address：problem.control_metadata_overhead / action.hoist_invariant_control

按最内轴段初始化一次非gather坐标前缀，段内地址递增；gatherIndex*源stride仍逐元素计算，不把index视为共享行索引。

2*N*d 个除模降至至多2*R*d个段起点解码；每元素保留index乘法，非gather尾轴增加一次递增；付出 O(d)坐标状态和段边界控制；无新UB；编译寄存器和spill未知；替代敏感条件：若编译器已强度削减全部除模，或合法尾轴整行UB Gather可摊销整行加载，批量取数更优

覆盖：nonlast_rank2=partial; last_axis=partial; nonlast_highrank=partial; rank1=partial

残余：随机源GM读取、逐元素guard与标量存储保留；rank1减法空间小



### vector：problem.scalar_control_hot_loop / action.vectorize_scalar_loop

尾轴源行能放入UB时搬源行和index片，在UB作按位Gather；非尾轴保留标量源读取，仅批量index和输出，不引入转置workspace。

尾轴把N次标量源load/output store改为片级搬运和UB Gather；非尾轴仍N次源load；付出 UB=A(G*b)+A(T*i)+A(T*b)+A(T*offsetBytes)+Tmp+F；源行按索引片重读，非尾轴转置被暂缓；替代敏感条件：G很大或N很小时整源行加载浪费压倒收益，地址分段更优

覆盖：nonlast_rank2=partial; last_axis=partial; nonlast_highrank=partial; rank1=partial

残余：非尾轴随机访问与精确64位/整数bit-copy API仍需处理



## 具体方案

不改变现有owner边界；每owner按最内轴合法剩余长度切段，首点用原rank公式建立前缀，其后保持索引读取及guard、存储位模式完全一致。先用源码地址序列证明，再核对编译spill；不只缓存字段。



## R2新增静态证据与复评

新增逐case地址几何计算：case20虽尾轴Gather，index前轴为[4,127]而X为[4,255]，前缀必须按X stride保留255；case13 rank1且N=1000，所有source只等于index，段外提前缀收益接近零。于是R2明确rank1保持简单路径，其余保留分段地址方案，优先检验rank3/4/5的除模减少。

回执static-evidence-r2.json包含新增逐case算术账与绑定身份。R1没有候选或patch，因此结构not_implemented、正确性not_tested、测量not_measured；不报告加速比、晋升或R2实施。



## 反事实敏感性probe

反事实把rank1的N由1000放大且G缩到能容纳的连续短源行，UB Gather可复用整行，vector的源行加载成本下降并可能反转优先级；重命名或重排case不会改变rank/G/J判据。

这些是合法形态/资源条件的纸面假设，不是实测case、新分派Key或最优阈值。



## 实际知识咨询及影响

- parallel-planning `skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/gather_output_owned.md`，lines:85-126，sha256:76c17821a374cd11f8f73abd6c97ff063e37eccaa4d52f0615a405282fadb43e。影响：非gather轴长度可能不等，不能直接用P/Q当X跨度；保留按输出owner与尾轴/非尾轴不同成本；适用：partial：该模板完整Gather语义匹配，当前只采用scalar/尾轴方案，拒绝未预算的transpose workspace。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md`，lines:57-107，sha256:136b0642b2359171260588136c3cf909e46b82a62ef99790607771cade27d576。影响：把公共前缀放到最小段外层并保留原访问序列，不只复制tiling大结构；适用：full：规则最内轴段地址控制；动态index部分不外提。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md`，lines:90-131，sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1。影响：批量vector仍需同宽offset和API范围，不能以连续输出推断连续source；适用：partial：UB侧批量原则；不提供通用GM Gather。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.control_metadata_overhead.md`，lines:297-432，sha256:d0abe417c2a011184aa8351d5ca1433d987d7ed3a36eb195b9f912661234a1e4。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；循环不变字段或公共地址前缀在每轮重复加载/计算；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.scalar_control_hot_loop.md`，lines:279-414，sha256:fae732465d333ee78d87ed126fd37fad3a2f94aeb4dc78ab02306fe2eaa6c3ec。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；本可按向量表达的元素处理使用逐元素Scalar访存或算术；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.noncontiguous_access.md`，lines:316-458，sha256:89cd601e45b350d46f05b9f8387abe0e9e91ecbc264e2c6a5e365ddb509b34db。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；切分或遍历轴跨过物理连续内轴；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。



## 真实路由与校验

retrieval-r*.json为完整Problem目录检索；expansion-r*.json与expansion-validation-r*.json为显式正文展开及回放。consultation-r*.json逐实例绑定实际内部router回执。这里没有完整父计划，不声称P_KEEP/O_KEEP；P提取已有骨架不统计为已完成并行优化。

rounds.json是集成入口；validation-r*.json保存runtime decision/C1结果。条件方案不进入C3。



## 完整矩阵分域与数量

| case | 域 | 静态数量（单位见字段） |

|---|---|---|

| 1 | nonlast_rank2 | `{"bytes_per_element": 2, "N": 524288, "rank": 2, "dim": 0, "inner": 1024, "source_shape": [1024, 1024], "index_shape": [512, 1024], "index_bytes": 4}` |

| 2 | nonlast_rank2 | `{"bytes_per_element": 4, "N": 2097152, "rank": 2, "dim": 0, "inner": 2048, "source_shape": [2048, 2048], "index_shape": [1024, 2048], "index_bytes": 8}` |

| 3 | nonlast_rank2 | `{"bytes_per_element": 2, "N": 8388608, "rank": 2, "dim": 0, "inner": 4096, "source_shape": [4096, 4096], "index_shape": [2048, 4096], "index_bytes": 4}` |

| 4 | nonlast_rank2 | `{"bytes_per_element": 4, "N": 33554432, "rank": 2, "dim": 0, "inner": 8192, "source_shape": [8192, 8192], "index_shape": [4096, 8192], "index_bytes": 4}` |

| 5 | nonlast_rank2 | `{"bytes_per_element": 8, "N": 16777216, "rank": 2, "dim": 0, "inner": 4096, "source_shape": [4096, 4096], "index_shape": [4096, 4096], "index_bytes": 8}` |

| 6 | nonlast_rank2 | `{"bytes_per_element": 1, "N": 67108864, "rank": 2, "dim": 0, "inner": 8192, "source_shape": [16384, 8192], "index_shape": [8192, 8192], "index_bytes": 4}` |

| 7 | last_axis | `{"bytes_per_element": 2, "N": 522753, "rank": 2, "dim": 1, "inner": 1023, "source_shape": [1023, 1023], "index_shape": [511, 1023], "index_bytes": 8}` |

| 8 | nonlast_rank2 | `{"bytes_per_element": 4, "N": 515605, "rank": 2, "dim": 0, "inner": 1021, "source_shape": [1009, 1021], "index_shape": [505, 1021], "index_bytes": 4}` |

| 9 | nonlast_rank2 | `{"bytes_per_element": 2, "N": 591361, "rank": 2, "dim": 0, "inner": 769, "source_shape": [1537, 769], "index_shape": [769, 769], "index_bytes": 8}` |

| 10 | nonlast_highrank | `{"bytes_per_element": 2, "N": 24777271, "rank": 3, "dim": 1, "inner": 373, "source_shape": [363, 367, 373], "index_shape": [181, 367, 373], "index_bytes": 4}` |

| 11 | nonlast_rank2 | `{"bytes_per_element": 4, "N": 525312, "rank": 2, "dim": 0, "inner": 513, "source_shape": [2049, 513], "index_shape": [1024, 513], "index_bytes": 8}` |

| 12 | nonlast_highrank | `{"bytes_per_element": 2, "N": 728182, "rank": 4, "dim": 1, "inner": 4001, "source_shape": [3, 7, 13, 4001], "index_shape": [2, 7, 13, 4001], "index_bytes": 4}` |

| 13 | rank1 | `{"bytes_per_element": 4, "N": 1000, "rank": 1, "dim": 0, "inner": 1000, "source_shape": [1000003], "index_shape": [1000], "index_bytes": 8}` |

| 14 | nonlast_highrank | `{"bytes_per_element": 2, "N": 6944483, "rank": 5, "dim": 1, "inner": 67, "source_shape": [11, 13, 17, 67, 67], "index_shape": [7, 13, 17, 67, 67], "index_bytes": 4}` |

| 15 | nonlast_highrank | `{"bytes_per_element": 4, "N": 2028026, "rank": 5, "dim": 1, "inner": 1013, "source_shape": [3, 7, 11, 13, 1013], "index_shape": [2, 7, 11, 13, 1013], "index_bytes": 8}` |

| 16 | nonlast_rank2 | `{"bytes_per_element": 2, "N": 524544, "rank": 2, "dim": 0, "inner": 2049, "source_shape": [512, 2049], "index_shape": [256, 2049], "index_bytes": 4}` |

| 17 | nonlast_rank2 | `{"bytes_per_element": 2, "N": 1040511, "rank": 2, "dim": 0, "inner": 8193, "source_shape": [255, 8193], "index_shape": [127, 8193], "index_bytes": 8}` |

| 18 | nonlast_rank2 | `{"bytes_per_element": 4, "N": 1046528, "rank": 2, "dim": 0, "inner": 511, "source_shape": [4097, 511], "index_shape": [2048, 511], "index_bytes": 4}` |

| 19 | nonlast_highrank | `{"bytes_per_element": 2, "N": 1044990, "rank": 3, "dim": 1, "inner": 2049, "source_shape": [2, 511, 2049], "index_shape": [2, 255, 2049], "index_bytes": 8}` |

| 20 | last_axis | `{"bytes_per_element": 4, "N": 1040892, "rank": 3, "dim": 2, "inner": 2049, "source_shape": [4, 255, 2049], "index_shape": [4, 127, 2049], "index_bytes": 4}` |



未覆盖的API合法形态不等于已验证：Gather支持index int8与更高rank；Slice负stride与rank8；Grid外区间reflection/size1；激活函数空/极短输出及目标SDK具体边界都需原合同核验。本文只分析原20case及源码声明域，不更改oracle。
