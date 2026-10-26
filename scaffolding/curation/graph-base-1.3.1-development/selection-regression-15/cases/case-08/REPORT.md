# case-08 grid_sampler_3d

R1优先：未注册派生几何复用（意图缺口）。模式：collect_evidence。未实施、未编译、未测量。

Host NCDHW/grid[N,S,3]，owner为连续输出；每个输出从grid三元组算坐标/padding/邻域后取1或8个体素，FP32累加；half仅最终Cast与DataCopyPad批量，内层仍Scalar。

N*C*S次几何生成，3*N*C*S次grid元素读；源读上界K*N*C*S（K=1或8）；输出N*C*S；half每1024输出额外一次Cast、一次DataCopyPad与3个PIPE_ALL。



## R1比较

### geometry：临时机制：跨通道派生几何重算 / intent_gap

跨通道块保存派生几何D=H(B(G(n,p)))，每owner独占[n,c0:c1,p0:p1]；先算一次坐标/有效邻点/分轴权重，逐c保留原8项乘法与累加顺序。

几何生成N*C*S降为N*S*ceil(C/Ct)，原grid读取同因子减少；仍有K*N*C*S体素读取上界；付出 D存储A(St*(K*3*8+K*4+maskBytes))；按基坐标差分可缩小但需证明；owner矩形改变task数及输出跨C间隔，私有数组会有spill风险；替代敏感条件：C=1或NS小到task不足、D状态迫使St太小时，独立空间批量vector更优

覆盖：float16_bilinear_nonreflection=partial; float32_bilinear_nonreflection=partial; float16_nearest_nonreflection=partial; float16_nearest_reflection=partial; float32_nearest_nonreflection=partial; float16_bilinear_reflection=partial

残余：体素读取、插值累加、half转换仍逐输出；不把几何复用算成原X数据复用



### vector：problem.scalar_control_hot_loop / action.vectorize_scalar_loop

固定n/c的连续p片批量处理grid转换、坐标与padding，源体素仍按合法地址scalar加载到UB，三线性计算使用FP32向量序列并保持原顺序。

N*C*S次scalar坐标/算术改为片级API，体素间接读取仍最多K*N*C*S；不声称GM vector Gather存在；付出 多份FP32坐标/权重/neighbor区与mask、padding/API tmp；reflection/floor/round-even及NaN需逐API核验；替代敏感条件：C较大且几何支配时geometry更少重复计算；C=1且St大时vector更优

覆盖：float16_bilinear_nonreflection=partial; float32_bilinear_nonreflection=partial; float16_nearest_nonreflection=partial; float16_nearest_reflection=partial; float32_nearest_nonreflection=partial; float16_bilinear_reflection=partial

残余：跨channel重复几何不消除，随机体素读仍在；nearest算术少，收益未知



### rawgrid：problem.insufficient_input_reuse / action.reuse_input_tiles

同owner通道块仅保留原始grid[St,3]，每个channel重新执行当前数值几何，原grid位模式不变。

grid元素读3*N*C*S降至3*N*S*ceil(C/Ct)，几何次数仍N*C*S；付出 原grid驻留3*St*b加输出/FP32/API区；必须改变owner分区、延长原值存活期，不能P_KEEP；替代敏感条件：若派生D存储远大于原grid且几何成本很低，rawgrid可能优于geometry

覆盖：float16_bilinear_nonreflection=partial; float32_bilinear_nonreflection=partial; float16_nearest_nonreflection=partial; float16_nearest_reflection=partial; float32_nearest_nonreflection=partial; float16_bilinear_reflection=partial

残余：原坐标/padding/邻域计算全部保留；L2已有命中则HBM降幅可能很小



## 具体方案

优先研究Ct×St矩形几何复用；G=原GridUnnormalize，B=原padding/reflection，H=原floor/nearest与分轴权重，F=原邻点顺序及FP32累加/最终Cast。C2知识骨架可咨询，但现有注册Action没有派生数值复用意图，提出意图缺口，不把它冒充hoist或reuse_input_tiles；备选是独立空间片vectorize。



## R2新增静态证据与复评

新增逐case C与K统计：C在7..256，nearest K=1而bilinear K=8。D若存完整K×三坐标+权重每点nearest至少24B、bilinear224B（mask另计）；所以R2从全C一owner改为有界Ct×St，并建议保存基坐标+分轴差分而非完整8邻域记录，但精度乘法次序必须不变。nearest小K与reflection代价不同，不能统一宣称复用总成本。

回执static-evidence-r2.json包含新增逐case算术账与绑定身份。R1没有候选或patch，因此结构not_implemented、正确性not_tested、测量not_measured；不报告加速比、晋升或R2实施。



## 反事实敏感性probe

反事实C=1且NS足够大：NCS→NS的几何减少为0，geometry失去benefit而保留D/调度代价，转向vector空间片；C大且D容量闭合才保留geometry。此为纸面敏感性不是生产阈值。

这些是合法形态/资源条件的纸面假设，不是实测case、新分派Key或最优阈值。



## 实际知识咨询及影响

- parallel-planning `skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/coordinate_neighborhood.md`，lines:110-183，sha256:5e4f96af8fde45ec3d5ea785c96c2243f211dbeeb93cd28c1f4d7e63bdf036fb。影响：绑定G/B/H/F后比较Ct×St矩形；几何D独立于c但X依赖c；派生复用确有Action意图缺口；适用：partial：任务骨架可采用，具体数值/API/容量尚未闭合。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/input-tile-residency.md`，lines:97-264，sha256:b09805a543555151cb41051cb57cfb967a8b47e68ae5d320820ef661806dc6e8。影响：只把原grid值纳入reuse_input_tiles；保存权重/坐标不是本配方；适用：partial：原grid保留原则可用，需重新确认owner和生命周期。

- optimization `skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md`，lines:90-131，sha256:0cffdf7e3e243d4e81e80b177ef1646ecdb84f5ceeafc922ef85fa58e86f57d1。影响：独立空间片数值批量化仍保持FP32顺序和有效域，不使用950 GM Gather；适用：partial：合法API/舍入路径未验证。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.insufficient_input_reuse.md`，lines:252-381，sha256:ec5efced73cd20f1e1abe65acaae9706903766522aac75837cab2b086ceb25d4。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；同一地址和内容在复用窗口被重复从GM读入；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.scalar_control_hot_loop.md`，lines:279-414，sha256:fae732465d333ee78d87ed126fd37fad3a2f94aeb4dc78ab02306fe2eaa6c3ec。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；本可按向量表达的元素处理使用逐元素Scalar访存或算术；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。

- diagnosis `skills/ascendc-aprof-diagnosis/graph/problems/problem.control_metadata_overhead.md`，lines:297-432，sha256:d0abe417c2a011184aa8351d5ca1433d987d7ed3a36eb195b9f912661234a1e4。影响：采用正文的结构成本链并保留编译器、资源和替代机制限制；循环不变字段或公共地址前缀在每轮重复加载/计算；适用：partial：有当前源码结构支持，未确认目标硬件关键路径。。



## 真实路由与校验

retrieval-r*.json为完整Problem目录检索；expansion-r*.json与expansion-validation-r*.json为显式正文展开及回放。consultation-r*.json逐实例绑定实际内部router回执。这里没有完整父计划，不声称P_KEEP/O_KEEP；P提取已有骨架不统计为已完成并行优化。

rounds.json是集成入口；validation-r*.json保存runtime decision/C1结果。条件方案不进入C3。



## 完整矩阵分域与数量

| case | 域 | 静态数量（单位见字段） |

|---|---|---|

| 1 | float16_bilinear_nonreflection | `{"bytes_per_element": 2, "N": 2, "C": 32, "S": 32768, "K": 8, "padding": "zeros", "align": false}` |

| 2 | float32_bilinear_nonreflection | `{"bytes_per_element": 4, "N": 4, "C": 64, "S": 4096, "K": 8, "padding": "zeros", "align": false}` |

| 3 | float16_nearest_nonreflection | `{"bytes_per_element": 2, "N": 2, "C": 128, "S": 512, "K": 1, "padding": "zeros", "align": true}` |

| 4 | float32_bilinear_nonreflection | `{"bytes_per_element": 4, "N": 4, "C": 64, "S": 32768, "K": 8, "padding": "border", "align": true}` |

| 5 | float16_nearest_reflection | `{"bytes_per_element": 2, "N": 2, "C": 128, "S": 262144, "K": 1, "padding": "reflection", "align": false}` |

| 6 | float32_bilinear_nonreflection | `{"bytes_per_element": 4, "N": 4, "C": 256, "S": 32768, "K": 8, "padding": "border", "align": false}` |

| 7 | float16_bilinear_nonreflection | `{"bytes_per_element": 2, "N": 3, "C": 31, "S": 29791, "K": 8, "padding": "zeros", "align": false}` |

| 8 | float32_nearest_nonreflection | `{"bytes_per_element": 4, "N": 2, "C": 63, "S": 3375, "K": 1, "padding": "zeros", "align": true}` |

| 9 | float16_bilinear_reflection | `{"bytes_per_element": 2, "N": 3, "C": 47, "S": 12167, "K": 8, "padding": "reflection", "align": false}` |

| 10 | float32_bilinear_nonreflection | `{"bytes_per_element": 4, "N": 5, "C": 97, "S": 79507, "K": 8, "padding": "zeros", "align": true}` |

| 11 | float16_bilinear_nonreflection | `{"bytes_per_element": 2, "N": 2, "C": 33, "S": 35937, "K": 8, "padding": "border", "align": true}` |

| 12 | float32_nearest_nonreflection | `{"bytes_per_element": 4, "N": 3, "C": 7, "S": 1547, "K": 1, "padding": "zeros", "align": false}` |

| 13 | float16_bilinear_nonreflection | `{"bytes_per_element": 2, "N": 2, "C": 31, "S": 29791, "K": 8, "padding": "zeros", "align": false}` |

| 14 | float32_bilinear_nonreflection | `{"bytes_per_element": 4, "N": 2, "C": 11, "S": 2431, "K": 8, "padding": "zeros", "align": false}` |

| 15 | float16_nearest_nonreflection | `{"bytes_per_element": 2, "N": 4, "C": 63, "S": 29791, "K": 1, "padding": "zeros", "align": false}` |

| 16 | float32_bilinear_nonreflection | `{"bytes_per_element": 4, "N": 2, "C": 16, "S": 63504, "K": 8, "padding": "zeros", "align": false}` |

| 17 | float16_bilinear_reflection | `{"bytes_per_element": 2, "N": 3, "C": 63, "S": 1016127, "K": 8, "padding": "reflection", "align": true}` |

| 18 | float32_nearest_nonreflection | `{"bytes_per_element": 4, "N": 2, "C": 32, "S": 3375, "K": 1, "padding": "border", "align": true}` |

| 19 | float16_bilinear_nonreflection | `{"bytes_per_element": 2, "N": 4, "C": 31, "S": 29791, "K": 8, "padding": "zeros", "align": true}` |

| 20 | float32_bilinear_nonreflection | `{"bytes_per_element": 4, "N": 2, "C": 63, "S": 504063, "K": 8, "padding": "border", "align": true}` |



未覆盖的API合法形态不等于已验证：Gather支持index int8与更高rank；Slice负stride与rank8；Grid外区间reflection/size1；激活函数空/极短输出及目标SDK具体边界都需原合同核验。本文只分析原20case及源码声明域，不更改oracle。
