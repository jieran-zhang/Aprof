# case-09 gelu

R1优先：action.batch_vector_api_calls。模式：conditional_plan。未实施、未编译、未测量。

Host一维展平，block=min(core,ceil(N/4096))，tile=1024。两种GELU模式均FP32链，none含Erfc与tail修正，tanh含RINT格点；输入/输出队列各一槽，分离FP32临时与5倍Erfc暂存始终分配。

每tile两次DMA及顺序Vector链；none约12次、tanh约15次显式Vector调用（包括进/出转换），仍需核对高阶API内部指令。显式UB=(2*b+32)*T+Align256(ceil(T/8))；T=1024；全扫描GM=2*N*b。



## R1比较

### batch：problem.vector_api_fragmentation / action.batch_vector_api_calls

保留模式和dtype所有数值步骤，扩大合法T使相邻tile同一API用更大count；不给tanh省略RINT，不替换Erfc近似。

每核ceil(L/1024)*V次显式API降为ceil(L/T)*V；元素算术和GM字节不变；付出 显式分配随T增加：(2*b+32)*T+Align256(ceil(T/8))+API_tmp+F≤UB_available；Compare补齐与Select预留并计；替代敏感条件：若API已内部高效批处理且搬运等待占主导，pipeline比扩T更优

覆盖：float16_none=partial; float32_none=partial; bfloat16_none=partial; float16_tanh=partial; float32_tanh=partial; bfloat16_tanh=partial

残余：Erfc/Tanh服务时间和单槽链仍在；容量不足时只能选原T或更小T，不能保证更大T合法



### pipeline：problem.pipeline_serialization / action.software_pipeline_stages

两输入/输出物理槽配首轮预置与排空，FP32工作区串行一次只处理一个tile；独立搬运与Vector尝试重叠。

减少跨tile必须串行等槽的依赖窗口，算术/GM字节不变；潜在隐藏搬运服务时间，未测；付出 再增加2*T*b队列字节及事件；若为双槽缩T则ceil(L/T)和API次数升高；替代敏感条件：当API发射是主要可消除项且扩T空间充足，batch更优

覆盖：float16_none=partial; float32_none=partial; bfloat16_none=partial; float16_tanh=partial; float32_tanh=partial; bfloat16_tanh=partial

残余：复杂GELU计算内部可能主导；Erfc临时区不能随意被下一tile覆盖



## 具体方案

条件范围T为满足原API count/Compare执行域、分核有效长和完整UB预算的正对齐值；先比较T=1024与较大可行T，不预设最优值。P提取原continuous骨架并重建合法计划；不把提取计作并行优化。



## R2新增静态证据与复评

新增静态API/容量复核：none路径CompareScalar按64元素补齐，而输入fi只定义count个有效值，未来扩大T仍要定义实际比较尾域；Select模式2正文要求A2/A3另预留8192B。显式none/tanh均保留5*T*4的erfTmp分配，不能因tanh未使用就自动扣除。R2缩紧合法T域并保持所有原特殊值修正，收益仍未测。

回执static-evidence-r2.json包含新增逐case算术账与绑定身份。R1没有候选或patch，因此结构not_implemented、正确性not_tested、测量not_measured；不报告加速比、晋升或R2实施。



## 反事实敏感性probe

反事实可用UB仅容纳原T总预算而不足较大T：batch减少调用的benefit为0；若仍容纳双槽同T可转pipeline，否则保留原计划并研究物理buffer复用。不能把192KiB注释当设备容量。

这些是合法形态/资源条件的纸面假设，不是实测case、新分派Key或最优阈值。



## 实际知识咨询及影响

- parallel-planning `skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md`，lines:83-188，sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4。影响：提取原连续分核骨架；预算全部静态分配与高阶API tmp，不拿例子容量当真值；适用：full：连续逐元素owner骨架；容量仍条件化。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md`，lines:90-131，sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1。影响：合并相邻tile同一操作用较大count，不合并有依赖的不同GELU算术，不删RINT；适用：full：batch意图与保持每元素运算顺序匹配；count合法性待核。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md`，lines:89-207，sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01。影响：双槽增加队列物理字节，须比较被迫减T的调用放大，不能把num=2叫实测重叠；适用：full：独立输入输出tile流水骨架，事件/API仍需实现核验。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/compare-select-tail.md`，lines:68-115，sha256:e0cf231e0bd3c6f821342c3d96c262230f009a68e19fc86e0136bf75e2885d62。影响：Select模式2有额外8192B预算；比较实际读取的补齐尾域须定义；Compare与CompareScalar重载不能混同；适用：partial：Select临时区与尾域原则；CompareScalar的具体API另核验。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.vector_api_fragmentation.md`，lines:258-392，sha256:e5c0882f45cb270a9fd555e570428ba6f942efbb8c888972f3aadb655c09a34a。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；可批处理的Vector工作被拆成大量小count/repeat调用；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md`，lines:271-407，sha256:4cacb553cd1af278ad9d2513e21cd70f968767b0eac3ef28ae42a90eb4e70d74。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.onchip_capacity_pressure.md`，lines:307-448，sha256:5a891db1219586ba9e282be035c81a632479d37de9b281c3f51156b1a0927a96。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；按dtype、对齐和深度求出的同时存活物理字节接近合法可用容量；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。



## 真实路由与校验

retrieval-r*.json为完整Problem目录检索；expansion-r*.json与expansion-validation-r*.json为显式正文展开及回放。consultation-r*.json逐实例绑定实际内部router回执。这里没有完整父计划，不声称P_KEEP/O_KEEP；P提取已有骨架不统计为已完成并行优化。

rounds.json是集成入口；validation-r*.json保存runtime decision/C1结果。条件方案不进入C3。



## 完整矩阵分域与数量

| case | 域 | 静态数量（单位见字段） |

|---|---|---|

| 1 | float16_none | `{"bytes_per_element": 2, "N": 1048576, "T": 1024, "useful_cores": 256, "explicit_ub_bytes": 37120, "mode": "none"}` |

| 2 | float32_none | `{"bytes_per_element": 4, "N": 4194304, "T": 1024, "useful_cores": 1024, "explicit_ub_bytes": 41216, "mode": "none"}` |

| 3 | bfloat16_none | `{"bytes_per_element": 2, "N": 16777216, "T": 1024, "useful_cores": 4096, "explicit_ub_bytes": 37120, "mode": "none"}` |

| 4 | float16_tanh | `{"bytes_per_element": 2, "N": 67108864, "T": 1024, "useful_cores": 16384, "explicit_ub_bytes": 37120, "mode": "tanh"}` |

| 5 | float32_tanh | `{"bytes_per_element": 4, "N": 67108864, "T": 1024, "useful_cores": 16384, "explicit_ub_bytes": 41216, "mode": "tanh"}` |

| 6 | bfloat16_tanh | `{"bytes_per_element": 2, "N": 1046529, "T": 1024, "useful_cores": 256, "explicit_ub_bytes": 37120, "mode": "tanh"}` |

| 7 | float16_none | `{"bytes_per_element": 2, "N": 1030189, "T": 1024, "useful_cores": 252, "explicit_ub_bytes": 37120, "mode": "none"}` |

| 8 | float32_tanh | `{"bytes_per_element": 4, "N": 1181953, "T": 1024, "useful_cores": 289, "explicit_ub_bytes": 41216, "mode": "tanh"}` |

| 9 | bfloat16_none | `{"bytes_per_element": 2, "N": 49691433, "T": 1024, "useful_cores": 12132, "explicit_ub_bytes": 37120, "mode": "none"}` |

| 10 | float16_tanh | `{"bytes_per_element": 2, "N": 1051137, "T": 1024, "useful_cores": 257, "explicit_ub_bytes": 37120, "mode": "tanh"}` |

| 11 | float32_none | `{"bytes_per_element": 4, "N": 1092273, "T": 1024, "useful_cores": 267, "explicit_ub_bytes": 41216, "mode": "none"}` |

| 12 | bfloat16_tanh | `{"bytes_per_element": 2, "N": 1000003, "T": 1024, "useful_cores": 245, "explicit_ub_bytes": 37120, "mode": "tanh"}` |

| 13 | float32_none | `{"bytes_per_element": 4, "N": 10912759, "T": 1024, "useful_cores": 2665, "explicit_ub_bytes": 41216, "mode": "none"}` |

| 14 | float16_tanh | `{"bytes_per_element": 2, "N": 3030027, "T": 1024, "useful_cores": 740, "explicit_ub_bytes": 37120, "mode": "tanh"}` |

| 15 | float32_none | `{"bytes_per_element": 4, "N": 1049088, "T": 1024, "useful_cores": 257, "explicit_ub_bytes": 41216, "mode": "none"}` |

| 16 | bfloat16_none | `{"bytes_per_element": 2, "N": 2089215, "T": 1024, "useful_cores": 511, "explicit_ub_bytes": 37120, "mode": "none"}` |

| 17 | float16_tanh | `{"bytes_per_element": 2, "N": 2093567, "T": 1024, "useful_cores": 512, "explicit_ub_bytes": 37120, "mode": "tanh"}` |

| 18 | float32_none | `{"bytes_per_element": 4, "N": 2094078, "T": 1024, "useful_cores": 512, "explicit_ub_bytes": 41216, "mode": "none"}` |

| 19 | bfloat16_tanh | `{"bytes_per_element": 2, "N": 2089980, "T": 1024, "useful_cores": 511, "explicit_ub_bytes": 37120, "mode": "tanh"}` |

| 20 | float32_none | `{"bytes_per_element": 4, "N": 10549248, "T": 1024, "useful_cores": 2576, "explicit_ub_bytes": 41216, "mode": "none"}` |



未覆盖的API合法形态不等于已验证：Gather支持index int8与更高rank；Slice负stride与rank8；Grid外区间reflection/size1；激活函数空/极短输出及目标SDK具体边界都需原合同核验。本文只分析原20case及源码声明域，不更改oracle。
