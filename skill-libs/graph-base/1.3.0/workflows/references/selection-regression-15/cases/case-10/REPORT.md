# case-10 sigmoid

R1优先：action.software_pipeline_stages。模式：conditional_plan。未实施、未编译、未测量。

Host展平后按ceil(N/4096)限制有效核数，tile4096。FP32直接Sigmoid，half/bf16先Cast FP32再算再Cast；深度1物理输入/输出槽，CopyIn Compute CopyOut顺序发射。

每核ceil(L/4096)次tile；FP32每tile1次Sigmoid，half/bf16每tile2次Cast+1次Sigmoid；2次DMA；显式UB FP32=8*T，半精度=12*T，另有Sigmoid API临时区未知；GM=2*N*b。



## R1比较

### pipeline：problem.pipeline_serialization / action.software_pipeline_stages

建立2份输入/输出物理槽的预取/消费/排空，FP32 cast工作区不跨tile重叠写；保持Sigmoid与原Cast舍入。

消除上一tile输入/输出槽释放后才可启动下一独立tile的串行限制；元素算术和2*N*b必要流量不变；付出 FP32两槽显式16*T、半精度16*T字节（raw双槽8*T+FP32工作8*T），另加API_tmp/F；事件及首尾控制增多；替代敏感条件：若双槽被迫把T减半且发射/同步成本超过隐藏搬运，较大单槽batch更优

覆盖：float16=partial; float32=partial; bfloat16=partial

残余：单tile与短片没有稳态，Sigmoid内部计算吞吐及Cast成本保留



### batch：problem.vector_api_fragmentation / action.batch_vector_api_calls

保留单槽，T4096扩大到合法更大T以减少Sigmoid/Cast和DMA发射次数。

每核ceil(L/4096)降为ceil(L/T)个API序列；不减少有效Sigmoid/Cast元素数；付出 FP328*T、half12*T显式字节+API_tmp/F；API最大count和长生存期需证明；替代敏感条件：长L、API setup明显且双槽需要缩T时，batch可能更优

覆盖：float16=partial; float32=partial; bfloat16=partial

残余：原4096已非很短调用，进一步减发射可能小；slot依赖未改



## 具体方案

从原连续输出owner提取完整计划，无父计划故不使用P_KEEP。先保持T4096作为待证参数，若2槽与API临时区不闭合再比较减T代价；一tile域保留单槽，不新造Tiling Key。



## R2新增静态证据与复评

新增按符号核数C_available计算循环条件：源useful=ceil(N/4096)，当C_available≥useful，每核L≤4096、无第二tile，因此不能仅由N很大断言重叠；真实核心数未知。R2将多tile作为pipeline有效域条件，补上FP32与half双槽均16*T显式字节的分账；若目标可用核数导致单tile则batch/原路径优先。

回执static-evidence-r2.json包含新增逐case算术账与绑定身份。R1没有候选或patch，因此结构not_implemented、正确性not_tested、测量not_measured；不报告加速比、晋升或R2实施。



## 反事实敏感性probe

反事实固定N=8192，C_available=2得到每核单tile，pipeline无稳态；C_available=1得到两tile可比较重叠。若UB不足双槽T4096而需T2048，API/事件约翻倍，可能反转到单槽。case顺序无影响。

这些是合法形态/资源条件的纸面假设，不是实测case、新分派Key或最优阈值。



## 实际知识咨询及影响

- parallel-planning `skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md`，lines:83-188，sha256:0a602958e66a719ea6d7a959a6d447ac684f2ef53a22fc1fe3dc838bde06edd4。影响：多核分配影响每核tile循环数，不能只按全N断言能流水；适用：full：连续同形一元函数任务骨架；无父计划，不是P_KEEP。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md`，lines:89-207，sha256:44a68a5b982eb4107ad17d4a133a9b4786646609ef41484c0dd68e7533124b01。影响：显式建MTE2→V、V→下一MTE2、V→MTE3、MTE3→下一V，逐槽代次闭合；适用：full：本核独立多tile流水，1tile保持原路径。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md`，lines:90-131，sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1。影响：4096已批量，扩T的收益仅剩发射摊销且增加临时区，作为最强竞争；适用：full：连续count分片边界。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/cast.md`，lines:59-97，sha256:61a09c55c6f9139ee767c6dde221cacfbadca53cbbb483d4ced76d0421c7f464。影响：保留half→float→half及bf16 RINT；它们承担计算精度与输出边界而非冗余Cast；适用：full：拒绝删除当前必要转换。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.pipeline_serialization.md`，lines:271-407，sha256:4cacb553cd1af278ad9d2513e21cd70f968767b0eac3ef28ae42a90eb4e70d74。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.vector_api_fragmentation.md`，lines:258-392，sha256:e5c0882f45cb270a9fd555e570428ba6f942efbb8c888972f3aadb655c09a34a。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；可批处理的Vector工作被拆成大量小count/repeat调用；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.redundant_cast.md`，lines:289-425，sha256:c7f8ace396cc0a0f53f4bc0a5b9f0883cbd8b439d45dce74edc1e4f50b1b326d。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；局部链在相邻阶段反复宽窄往返转换；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。



## 真实路由与校验

retrieval-r*.json为完整Problem目录检索；expansion-r*.json与expansion-validation-r*.json为显式正文展开及回放。consultation-r*.json逐实例绑定实际内部router回执。这里没有完整父计划，不声称P_KEEP/O_KEEP；P提取已有骨架不统计为已完成并行优化。

rounds.json是集成入口；validation-r*.json保存runtime decision/C1结果。条件方案不进入C3。



## 完整矩阵分域与数量

| case | 域 | 静态数量（单位见字段） |

|---|---|---|

| 1 | float16 | `{"bytes_per_element": 2, "N": 1048576, "T": 4096, "useful_cores": 256, "explicit_ub_bytes": 49152}` |

| 2 | float32 | `{"bytes_per_element": 4, "N": 4194304, "T": 4096, "useful_cores": 1024, "explicit_ub_bytes": 32768}` |

| 3 | bfloat16 | `{"bytes_per_element": 2, "N": 16777216, "T": 4096, "useful_cores": 4096, "explicit_ub_bytes": 49152}` |

| 4 | float16 | `{"bytes_per_element": 2, "N": 67108864, "T": 4096, "useful_cores": 16384, "explicit_ub_bytes": 49152}` |

| 5 | float32 | `{"bytes_per_element": 4, "N": 67108864, "T": 4096, "useful_cores": 16384, "explicit_ub_bytes": 32768}` |

| 6 | bfloat16 | `{"bytes_per_element": 2, "N": 1046529, "T": 4096, "useful_cores": 256, "explicit_ub_bytes": 49152}` |

| 7 | float16 | `{"bytes_per_element": 2, "N": 1030189, "T": 4096, "useful_cores": 252, "explicit_ub_bytes": 49152}` |

| 8 | float32 | `{"bytes_per_element": 4, "N": 1181953, "T": 4096, "useful_cores": 289, "explicit_ub_bytes": 32768}` |

| 9 | bfloat16 | `{"bytes_per_element": 2, "N": 49691433, "T": 4096, "useful_cores": 12132, "explicit_ub_bytes": 49152}` |

| 10 | float16 | `{"bytes_per_element": 2, "N": 1051137, "T": 4096, "useful_cores": 257, "explicit_ub_bytes": 49152}` |

| 11 | float32 | `{"bytes_per_element": 4, "N": 1092273, "T": 4096, "useful_cores": 267, "explicit_ub_bytes": 32768}` |

| 12 | bfloat16 | `{"bytes_per_element": 2, "N": 1000003, "T": 4096, "useful_cores": 245, "explicit_ub_bytes": 49152}` |

| 13 | float32 | `{"bytes_per_element": 4, "N": 10912759, "T": 4096, "useful_cores": 2665, "explicit_ub_bytes": 32768}` |

| 14 | float16 | `{"bytes_per_element": 2, "N": 3030027, "T": 4096, "useful_cores": 740, "explicit_ub_bytes": 49152}` |

| 15 | float32 | `{"bytes_per_element": 4, "N": 1049088, "T": 4096, "useful_cores": 257, "explicit_ub_bytes": 32768}` |

| 16 | bfloat16 | `{"bytes_per_element": 2, "N": 2089215, "T": 4096, "useful_cores": 511, "explicit_ub_bytes": 49152}` |

| 17 | float16 | `{"bytes_per_element": 2, "N": 2093567, "T": 4096, "useful_cores": 512, "explicit_ub_bytes": 49152}` |

| 18 | float32 | `{"bytes_per_element": 4, "N": 2094078, "T": 4096, "useful_cores": 512, "explicit_ub_bytes": 32768}` |

| 19 | bfloat16 | `{"bytes_per_element": 2, "N": 2089980, "T": 4096, "useful_cores": 511, "explicit_ub_bytes": 49152}` |

| 20 | float32 | `{"bytes_per_element": 4, "N": 10549248, "T": 4096, "useful_cores": 2576, "explicit_ub_bytes": 32768}` |



未覆盖的API合法形态不等于已验证：Gather支持index int8与更高rank；Slice负stride与rank8；Grid外区间reflection/size1；激活函数空/极短输出及目标SDK具体边界都需原合同核验。本文只分析原20case及源码声明域，不更改oracle。
