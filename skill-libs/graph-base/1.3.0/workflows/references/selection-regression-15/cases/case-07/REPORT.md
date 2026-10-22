# case-07 strided_slice

R1优先：action.vectorize_scalar_loop。模式：conditional_plan。未实施、未编译、未测量。

Host解释begin/end/masks为outputShape/sourceStep/sourceBase；按64B写所有权对齐分核。Kernel逐元素rank解码，按位复制，不存在浮点算术。

N个源读+N个输出写，2*N*d次除模及N*d次乘加；有效GM请求2*N*b字节；没有UB数据批量化。



## R1比较

### batch：problem.scalar_control_hot_loop / action.vectorize_scalar_loop

按最内有效轴组织片：s=1用按位DMA，s为小正步长时读s*(T-1)+1连续跨度并用同宽UB Gather压紧；大步长保留原标量路径。

s=1/小s域N次标量读写及rank解码变为R*ceil(E/T)片级调度、UB选取；必要输出N元素不变；付出 跨度读取新增至多(s-1)*N*b输入字节；UB=A((s*(T-1)+1)*b)+A(T*b)+A(T*offsetBytes)+Tmp+F；int64需同宽或两半按位处理API证明；替代敏感条件：s大或短E使span读取放大胜过减少Scalar时，分段地址递增优先

覆盖：small_stride=partial; contiguous_inner=partial; large_gap=unchanged

残余：大步长column保留标量读；负stride与rank8是声明支持但当前矩阵未覆盖；不扩大GM越界读



### address：problem.control_metadata_overhead / action.hoist_invariant_control

每连续输出段保留sourceBase+外轴前缀，内轴用sourceStep增量；所有stride继续按原uint64位模式处理。

2*N*d次除模降为2*R*d；内轴用N次加法代替全rank乘加；付出 O(d)状态，不增加GM请求或UB；段边界和编译spill未知；替代敏感条件：若大部分为s=1且E长，批量复制可减少更多标量数据访问

覆盖：small_stride=partial; contiguous_inner=partial; large_gap=partial

残余：N次标量load/store仍在，长连续行错过DMA机会



## 具体方案

先按host归一化后的outputShape/sourceStep建片而非case ID；去掉size1轴时仍保留base语义。s=1连续搬，已证明API的同宽小stride做UB选取，其余走原地址公式。保持64B owner划分及每owner统一写回；UB/SDK未确认前仅条件方案。



## R2新增静态证据与复评

新增按host规则展开全部mask所得几何：shrink列case15输出2048、源step2048，不能整span加载；new-axis size1的step0可折叠，case16/17/19有长物理连续后缀。R2把case15列读明确保留标量，而size1轴之后连续段可合并；小stride域新增流量按s=2/3/4分别计算，不以统一API覆盖宣称全域已优化。

回执static-evidence-r2.json包含新增逐case算术账与绑定身份。R1没有候选或patch，因此结构not_implemented、正确性not_tested、测量not_measured；不报告加速比、晋升或R2实施。



## 反事实敏感性probe

反事实固定N将内轴s从2变为2048（扩大合法源shape）：batch的额外输入从约N*b升至约2047*N*b，选择反转到address；若s=1且E长则保留batch，不依赖case编号。

这些是合法形态/资源条件的纸面假设，不是实测case、新分派Key或最优阈值。



## 实际知识咨询及影响

- parallel-planning `skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/gather_output_owned.md`，lines:85-126，sha256:76c17821a374cd11f8f73abd6c97ff063e37eccaa4d52f0615a405282fadb43e。影响：采用输出独占与真实source stride原则；Slice没有数据相关index，不采用完整Gather模板；适用：partial：只取owner/stride/bit-copy原则。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/strided-pad.md`，lines:77-138，sha256:dbd61eaa8bb85b89b10ae445f1cff983baaaf8aa7a707b07900c18ac60262403。影响：按有效行长/GM间隙/UB对齐分别定义单位；stride大到跨列不能整span载入；适用：partial：s=1规则连续段可完整表达，小stride压紧另需Gather。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md`，lines:57-107，sha256:136b0642b2359171260588136c3cf909e46b82a62ef99790607771cade27d576。影响：大步长回退仍可按段地址递增，保持negative stride原位模式；适用：full：规则仿射地址且不改变原拷贝次序。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md`，lines:90-131，sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1。影响：普通整数bit-copy不能误用float Select，采用同宽UB取数需具体API证明；适用：partial：批处理控制与容量原则。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.scalar_control_hot_loop.md`，lines:279-414，sha256:fae732465d333ee78d87ed126fd37fad3a2f94aeb4dc78ab02306fe2eaa6c3ec。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；本可按向量表达的元素处理使用逐元素Scalar访存或算术；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.control_metadata_overhead.md`，lines:297-432，sha256:d0abe417c2a011184aa8351d5ca1433d987d7ed3a36eb195b9f912661234a1e4。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；循环不变字段或公共地址前缀在每轮重复加载/计算；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.noncontiguous_access.md`，lines:316-458，sha256:89cd601e45b350d46f05b9f8387abe0e9e91ecbc264e2c6a5e365ddb509b34db。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；切分或遍历轴跨过物理连续内轴；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。



## 真实路由与校验

retrieval-r*.json为完整Problem目录检索；expansion-r*.json与expansion-validation-r*.json为显式正文展开及回放。consultation-r*.json逐实例绑定实际内部router回执。这里没有完整父计划，不声称P_KEEP/O_KEEP；P提取已有骨架不统计为已完成并行优化。

rounds.json是集成入口；validation-r*.json保存runtime decision/C1结果。条件方案不进入C3。



## 完整矩阵分域与数量

| case | 域 | 静态数量（单位见字段） |

|---|---|---|

| 1 | small_stride | `{"bytes_per_element": 2, "output_shape": [262144], "source_steps": [2], "base": 0, "N": 262144, "E": 262144, "s": 2}` |

| 2 | contiguous_inner | `{"bytes_per_element": 4, "output_shape": [2047, 2047], "source_steps": [2048, 1], "base": 0, "N": 4190209, "E": 2047, "s": 1}` |

| 3 | small_stride | `{"bytes_per_element": 2, "output_shape": [1024, 1024], "source_steps": [8192, 2], "base": 0, "N": 1048576, "E": 1024, "s": 2}` |

| 4 | small_stride | `{"bytes_per_element": 4, "output_shape": [8191, 4096], "source_steps": [8192, 2], "base": 0, "N": 33550336, "E": 4096, "s": 2}` |

| 5 | small_stride | `{"bytes_per_element": 8, "output_shape": [2048, 4096], "source_steps": [16384, 2], "base": 0, "N": 8388608, "E": 4096, "s": 2}` |

| 6 | small_stride | `{"bytes_per_element": 4, "output_shape": [4096, 2048], "source_steps": [16384, 4], "base": 0, "N": 8388608, "E": 2048, "s": 4}` |

| 7 | contiguous_inner | `{"bytes_per_element": 2, "output_shape": [1022, 1022], "source_steps": [1023, 1], "base": 0, "N": 1044484, "E": 1022, "s": 1}` |

| 8 | small_stride | `{"bytes_per_element": 4, "output_shape": [250, 250], "source_steps": [2042, 2], "base": 0, "N": 62500, "E": 250, "s": 2}` |

| 9 | small_stride | `{"bytes_per_element": 2, "output_shape": [1536, 256], "source_steps": [769, 3], "base": 0, "N": 393216, "E": 256, "s": 3}` |

| 10 | contiguous_inner | `{"bytes_per_element": 4, "output_shape": [100, 100, 100], "source_steps": [136891, 373, 1], "base": 0, "N": 1000000, "E": 100, "s": 1}` |

| 11 | contiguous_inner | `{"bytes_per_element": 2, "output_shape": [1024, 768], "source_steps": [1024, 1], "base": 256, "N": 786432, "E": 768, "s": 1}` |

| 12 | small_stride | `{"bytes_per_element": 4, "output_shape": [1024, 1024], "source_steps": [4096, 2], "base": 0, "N": 1048576, "E": 1024, "s": 2}` |

| 13 | contiguous_inner | `{"bytes_per_element": 2, "output_shape": [1024, 256], "source_steps": [1024, 1], "base": 0, "N": 262144, "E": 256, "s": 1}` |

| 14 | contiguous_inner | `{"bytes_per_element": 2, "output_shape": [1024], "source_steps": [1], "base": 524288, "N": 1024, "E": 1024, "s": 1}` |

| 15 | large_gap | `{"bytes_per_element": 4, "output_shape": [2048], "source_steps": [2048], "base": 1024, "N": 2048, "E": 2048, "s": 2048}` |

| 16 | contiguous_inner | `{"bytes_per_element": 2, "output_shape": [1, 512, 512], "source_steps": [0, 512, 1], "base": 0, "N": 262144, "E": 512, "s": 1}` |

| 17 | contiguous_inner | `{"bytes_per_element": 4, "output_shape": [1024, 1, 1024], "source_steps": [1024, 0, 1], "base": 0, "N": 1048576, "E": 1024, "s": 1}` |

| 18 | contiguous_inner | `{"bytes_per_element": 2, "output_shape": [1024], "source_steps": [1], "base": 524288, "N": 1024, "E": 1024, "s": 1}` |

| 19 | contiguous_inner | `{"bytes_per_element": 4, "output_shape": [1, 512], "source_steps": [0, 1], "base": 131072, "N": 512, "E": 512, "s": 1}` |

| 20 | contiguous_inner | `{"bytes_per_element": 2, "output_shape": [64, 127, 127, 127], "source_steps": [2097152, 16384, 128, 1], "base": 0, "N": 131096512, "E": 127, "s": 1}` |



未覆盖的API合法形态不等于已验证：Gather支持index int8与更高rank；Slice负stride与rank8；Grid外区间reflection/size1；激活函数空/极短输出及目标SDK具体边界都需原合同核验。本文只分析原20case及源码声明域，不更改oracle。
