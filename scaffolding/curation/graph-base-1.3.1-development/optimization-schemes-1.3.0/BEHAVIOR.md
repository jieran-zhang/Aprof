# 无工具自主方案回放

输入为原始源码、workload 和静态展开的技能/参考正文；每组两次新上下文。没有提供预选 Problem、Action、Action 数量或必须优化的结论。下列“采用”均指纸面计划采用，并非正式 router 执行、代码实施或性能验收。

| 样例 | 选定方案与 Action | 实际范围及限制 |
| --- | --- | --- |
| [grid_sampler_3d-1](sources/development/runs/grid_sampler_3d-1/answer.md) | 原owner及几何/取数不变，bilinear算术批量Vector，T∈256/512/1024；action.vectorize_scalar_loop | 实际SDK Mul/Add精确alias、Scalar/Vector浮点模式、UB/预留尚未闭合，最终源码与全oracle未执行；回答准确保留conditional_plan。；nearest、几何重算、随机X读取及FP16标量扩位保留；跨c几何状态有注册意图缺口。 |
| [grid_sampler_3d-2](sources/development/runs/grid_sampler_3d-2/answer.md) | 输出owner不变，Scalar生成坐标/样本，Vector按原八项顺序计算bilinear，nearest保留；action.vectorize_scalar_loop | 目标Mul/Add/Cast的浮点/精确alias、SDK与完整UB预留仍须闭合；回答明确conditional_plan，未假称已通过。；nearest、跨c几何重算、Scalar随机取数和输入扩位保留；没有将全正确性覆盖冒称全域优化。 |
| [maximum-1](sources/development/runs/maximum-1/answer.md) | 同形int8的6Cast+float Max改3Cast+half Max，完整int8域精确；action.coalesce_cast | 安装SDK的half Max/转换具体位置与同步、可用UB和隐含预留尚待核验；不是该纸面证明的事实错误。；一般FP16广播与浮点Scalar三元选择的既有API域问题单列；本轮只改同形int8，不夸大全域正确。 |
| [maximum-2](sources/development/runs/maximum-2/answer.md) | 同形int8精确half Max链，保留owner/4096tile，广播为强替代；action.coalesce_cast | SDK half Max/Cast支持和V内依赖、UB隐含预留与最终完整oracle待核验；条件方案范围准确。；通用half广播和浮点三元选择的既有问题未被int8优化掩盖。 |
| [reduction_sum-1](sources/development/runs/reduction_sum-1/answer.md) | 保留现有单核AR全载；基础ReduceSum、增核/流水均作具体成本比较；未提出采用的 Action，保留当前实现 | 若后续重开基础ReduceSum，需scratch、目的地址/布局、三结果打包与意图归属；本次保留选择不要求强行试验。；全部8输出、NaN比较、短输入/未检返回值/比较失败exit0均单列，后继验收不能以原exit0当正确性。 |
| [reduction_sum-2](sources/development/runs/reduction_sum-2/answer.md) | 保留单核AR全载，基础ReduceSum仅作为有具体API缺项的强替代；未提出采用的 Action，保留当前实现 | 保留R0不需强制新增候选。若重开ReduceSum，scratch、目的地址/打包和注册意图仍需明确；这些缺项阻止替代方案直接实施，不否决知识。；输入短文件、未检查ACL返回值、比较失败仍exit0等限制已明确，未来验收不能只看退出码。 |
| [transpose-1](sources/development/runs/transpose-1/answer.md) | 双端连续轴矩形/条带任务，DMA+原始整数Scalar UB重排，通用回退；action.reorder_contiguous_access | 原始整数DMA支持、Scalar UB访问与DMA交接可见性、实际UB预算未闭合；这是一份有准确公式和映射的条件方案，不是可直接执行候选。；相邻矩形/跨核短行物理写入契约须确认；若需要共同物理owner会返回C2，没有声称逻辑不重叠已证明安全。 |
| [transpose-2](sources/development/runs/transpose-2/answer.md) | 共同连续尾段批量DMA；其余置换保持Raw复制并用混合进位递推地址；action.coalesce_contiguous_transfers、action.hoist_invariant_control | VECIN TBuf→GM DataCopyPad方向/位置/类型及非对齐写出契约、可用UB、最终递推地址尚待闭合；回答没有把这些缺项藏在ready里。；其余18case仍Scalar离散GM复制，矩形保位转置API路线待补；未宣称全部perm均变成DMA转置。 |

## 逐份正文采用记录

这里区分拟采用、用于比较/边界判断、明确未采用。不能将所有出现过的文档计算成采用。完整支持引文和冻结事实在[锁定评分](sources/development/review/grades.json)中。

### grid_sampler_3d-1

原owner及几何/取数不变，bilinear算术批量Vector，T∈256/512/1024

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/indexing/templates/coordinate_neighborhood.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/coordinate_neighborhood.md) | 拟采用 | 采用不共享几何的输出连续块；跨c派生几何需明确注册意图。 |
| [branches/vector-api/recipes/batch.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md) | 拟采用 | 逐tile count Mul/Add发射，保留运算图。 |
| [branches/vector-api/recipes/cast.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/cast.md) | 拟采用 | 保持FP16实际最终CAST_NONE路径。 |
| [branches/precision-boundaries/recipes/numeric.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/numeric.md) | 拟采用 | 保留三乘与八次顺序累加、Inf×0等特殊值，FTZ/FMA待核验。 |
| [branches/memory-transfer/recipes/coalesce.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md) | 拟采用 | FP32输出从Scalarstore改有效块搬出。 |
| [branches/memory-transfer/recipes/strided-pad.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/strided-pad.md) | 比较或边界参考 | 规则DMA不能表达随机X gather，拒绝源窗口自动连续假设。 |
| [branches/tiling-tail/recipes/valid-length.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/tiling-tail/recipes/valid-length.md) | 拟采用 | 尾有效字节不向GM补齐。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 比较或边界参考 | term/acc/样本/权重共同存活，独立分配不做alias。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 比较或边界参考 | 保守单槽完成边，不进行本轮流水变换。 |
| [branches/vector-api/recipes/compare-select-tail.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/compare-select-tail.md) | 本轮未采用 | 坐标clamp向量化会新增比较补齐与8KiB，不夹带。 |
| [branches/scalar-control/recipes/hot-loop-address.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md) | 比较或边界参考 | 地址解码是低资源替代，字段CSE需编译证据。 |

### grid_sampler_3d-2

输出owner不变，Scalar生成坐标/样本，Vector按原八项顺序计算bilinear，nearest保留

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/indexing/templates/coordinate_neighborhood.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/coordinate_neighborhood.md) | 拟采用 | 采用输出连续块、独立几何的分支，拒绝将跨c派生几何复用归入输入驻留。 |
| [families/indexing/templates/gather_output_owned.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/indexing/templates/gather_output_owned.md) | 比较或边界参考 | 只采用输出独占/间接取数原则，不冒称GatherElements完整骨架。 |
| [branches/vector-api/recipes/batch.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md) | 拟采用 | 连续count计算，24Mul+8Add按tile发射。 |
| [branches/vector-api/recipes/cast.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/cast.md) | 拟采用 | 保留实际FP16 CAST_NONE最终边界。 |
| [branches/precision-boundaries/recipes/numeric.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/numeric.md) | 拟采用 | 不预乘权重、不跳零项、不改FMA/累加树。 |
| [branches/memory-transfer/recipes/coalesce.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md) | 拟采用 | FP32结果按连续有效区汇总写回。 |
| [branches/tiling-tail/recipes/valid-length.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/tiling-tail/recipes/valid-length.md) | 拟采用 | 有效元素数、GM有效字节与UB物理跨度分开。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 比较或边界参考 | 单槽保守完成边，未采用流水优化。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 比较或边界参考 | 按独立物理区核算，本轮拒绝别名复用。 |
| [branches/vector-api/recipes/compare-select-tail.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/compare-select-tail.md) | 本轮未采用 | 完整坐标向量化的256B比较域/8KiB临时区增加成本，本轮不并入。 |
| [branches/scalar-control/recipes/hot-loop-address.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md) | 比较或边界参考 | 作为地址分段外提替代。 |

### maximum-1

同形int8的6Cast+float Max改3Cast+half Max，完整int8域精确

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/elementwise/templates/continuous.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md) | 拟采用 | 原连续owner、tile、物理槽及转换区按字节计。 |
| [families/elementwise/templates/broadcast.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/broadcast.md) | 比较或边界参考 | 比较广播替代，不能padding后伪造axis=0原shape合法性。 |
| [families/elementwise/fallback.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/fallback.md) | 比较或边界参考 | 保留原路径不等于已验证fallback。 |
| [branches/vector-api/recipes/cast.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/cast.md) | 拟采用 | 用完整int8域的half精确表示删除3条转换，不推广BF16/int64。 |
| [branches/precision-boundaries/recipes/numeric.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/numeric.md) | 拟采用 | 整数精确域与浮点NaN/Max/三元选择区分。 |
| [branches/vector-api/recipes/compare-select-tail.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/compare-select-tail.md) | 比较或边界参考 | 广播替代成本含256B比较域、predicate与8KiB临时区，本轮未采用。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 比较或边界参考 | 三个half区独立，不申报物理alias节省。 |
| [branches/tiling-tail/recipes/valid-length.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/tiling-tail/recipes/valid-length.md) | 拟采用 | 有效count与对齐分配分开。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 本轮未采用 | 不将节省空间自动用于双缓冲。 |
| [branches/scalar-control/recipes/hot-loop-address.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md) | 比较或边界参考 | int64线性索引/广播段解码替代，保留精确比较。 |

### maximum-2

同形int8精确half Max链，保留owner/4096tile，广播为强替代

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/elementwise/templates/continuous.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/continuous.md) | 拟采用 | 按原owner、tile和真实转换区资源建立计划。 |
| [families/elementwise/templates/broadcast.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/elementwise/templates/broadcast.md) | 比较或边界参考 | 连续短行/广播原形状与展开域进入替代成本。 |
| [branches/vector-api/recipes/cast.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/cast.md) | 拟采用 | 完整int8域精确half表示，保留两次扩位与一次缩位。 |
| [branches/precision-boundaries/recipes/numeric.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/numeric.md) | 拟采用 | 三元选择/Max、NaN与数值替换分开。 |
| [branches/vector-api/recipes/compare-select-tail.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/compare-select-tail.md) | 比较或边界参考 | FP32比较补齐、predicate、Select 8KiB影响广播替代。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 比较或边界参考 | 独立half区，不将逻辑生存期自动转为物理复用。 |
| [branches/tiling-tail/recipes/valid-length.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/tiling-tail/recipes/valid-length.md) | 拟采用 | 有效count和GM字节、物理对齐分开。 |
| [branches/precision-boundaries/recipes/bounds.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/bounds.md) | 拟采用 | 空owner不调用，尾count/地址范围闭合。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 本轮未采用 | 本轮不叠加无必要依赖的双物理槽。 |

### reduction_sum-1

保留现有单核AR全载；基础ReduceSum、增核/流水均作具体成本比较

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/reduction/templates/fullload.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/reduction/templates/fullload.md) | 拟采用 | 当前AR全载h=3、容量及有效/对齐长度原则。 |
| [families/reduction/templates/split.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/reduction/templates/split.md) | 本轮未采用 | 短R的partial/merge新增成本阻止本轮采用。 |
| [branches/memory-transfer/recipes/coalesce.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md) | 比较或边界参考 | 当前读/写各一次，不能再登记合并收益。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 本轮未采用 | 没有next tile，不为流水制造分块。 |
| [branches/precision-boundaries/recipes/numeric.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/numeric.md) | 拟采用 | 保留原FP32数值/归约范围，不外推生成小整数域。 |
| [branches/precision-boundaries/recipes/bounds.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/bounds.md) | 拟采用 | 保持8个可见输出和5个padding零。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 比较或边界参考 | Sum时各区有用途，不能按逻辑生存期伪造物理复用。 |
| [branches/scalar-control/recipes/tilingdata-access.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/tilingdata-access.md) | 本轮未采用 | 按值5字段无热循环，不套GM字段缓存。 |

### reduction_sum-2

保留单核AR全载，基础ReduceSum仅作为有具体API缺项的强替代

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/reduction/templates/fullload.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/reduction/templates/fullload.md) | 拟采用 | 解释当前AR全载h=3；容量包含输入/输出/scratch及预留。 |
| [families/reduction/templates/split.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/reduction/templates/split.md) | 本轮未采用 | R=32的partial/merge新增工作不支持本轮采用。 |
| [families/reduction/fallback.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/reduction/fallback.md) | 比较或边界参考 | 未经验证父entry不冒称已验证fallback。 |
| [branches/memory-transfer/recipes/coalesce.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md) | 比较或边界参考 | 确认输入输出已各一次，无可再次登记的合并收益。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 本轮未采用 | 单tile无独立next tile，拒绝为流水制造片段。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 比较或边界参考 | Sum时输入/输出/scratch均参与，不可未经alias证明重叠。 |
| [branches/scalar-control/recipes/tilingdata-access.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/tilingdata-access.md) | 本轮未采用 | 20B按值tiling无用户热循环，不套GM指针外提。 |
| [branches/precision-boundaries/recipes/numeric.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/numeric.md) | 拟采用 | 生成整数域不外推任意FP32/特殊值。 |
| [branches/precision-boundaries/recipes/bounds.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/bounds.md) | 拟采用 | 全部8个物理输出及padding约束保留。 |

### transpose-1

双端连续轴矩形/条带任务，DMA+原始整数Scalar UB重排，通用回退

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/layout/templates/transpose.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/layout/templates/transpose.md) | 拟采用 | 选择输出owner与双端连续轴矩形，合法合轴、高rank保留外轴映射。 |
| [families/layout/fallback.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/layout/fallback.md) | 比较或边界参考 | 保留一般Raw映射，不把未经验证父实现叫正确fallback。 |
| [branches/memory-transfer/recipes/coalesce.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md) | 拟采用 | 连续条带可直接批量复制。 |
| [branches/memory-transfer/recipes/strided-pad.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/strided-pad.md) | 拟采用 | GM字节间隙、UB32B块间隙与固定pitch公式。 |
| [branches/tiling-tail/recipes/valid-length.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/tiling-tail/recipes/valid-length.md) | 拟采用 | 有效va/vb与物理Lx/Ly不混用。 |
| [branches/precision-boundaries/recipes/bounds.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/bounds.md) | 拟采用 | 字段窄化/最后GM地址及尾部检查。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 比较或边界参考 | 局部置换期间双区同时存活，不取max。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 比较或边界参考 | 初版浅单槽，不宣称预取/流水收益。 |
| [branches/scalar-control/recipes/hot-loop-address.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md) | 比较或边界参考 | 输出计数器S2作为无UB替代。 |
| [branches/precision-boundaries/recipes/numeric.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/numeric.md) | 拟采用 | 按原始整数lane/字节复制，不做浮点算术转换。 |
| [branches/vector-api/recipes/batch.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/vector-api/recipes/batch.md) | 本轮未采用 | count/mask信息不能外推为通用Vector转置能力。 |

### transpose-2

共同连续尾段批量DMA；其余置换保持Raw复制并用混合进位递推地址

| P/O 文档 | 用途 | 对方案的实际影响 |
| --- | --- | --- |
| [families/layout/templates/transpose.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-parallel-planning/knowledge/families/layout/templates/transpose.md) | 拟采用 | 双端连续性、输出owner、合轴边界决定连续段和通用映射两路。 |
| [branches/memory-transfer/recipes/coalesce.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/coalesce.md) | 拟采用 | 仅共同连续区合并，2/4B DMA视图无数值运算。 |
| [branches/memory-transfer/recipes/strided-pad.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/memory-transfer/recipes/strided-pad.md) | 拟采用 | 有效GM字节与UB对齐跨度分开，case14写508B。 |
| [branches/scalar-control/recipes/hot-loop-address.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/hot-loop-address.md) | 拟采用 | 初始解码与有界进位更新，保留相同元素序列。 |
| [branches/scalar-control/recipes/tilingdata-access.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/scalar-control/recipes/tilingdata-access.md) | 比较或边界参考 | 没有整结构栈拷贝可删，不优先少量字段缓存。 |
| [branches/tiling-tail/recipes/valid-length.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/tiling-tail/recipes/valid-length.md) | 拟采用 | 段长度不得跨连续尾段/owner/tile边界。 |
| [branches/precision-boundaries/recipes/bounds.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/precision-boundaries/recipes/bounds.md) | 拟采用 | 检查最大地址/乘法溢出，无符号回绕不造负stride。 |
| [branches/pipeline-sync/recipes/pipeline.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/pipeline-sync/recipes/pipeline.md) | 比较或边界参考 | 浅单槽完成后复用，本轮不叠加流水变换。 |
| [branches/buffer-lifetime/recipes/reuse.md](../../../../skill-libs/graph-base/1.3.1/skills/ascendc-aprof-optimization/knowledge/branches/buffer-lifetime/recipes/reuse.md) | 本轮未采用 | 原路径无独立临时区可复用，不添加arena。 |

## 对后继摘要的实际回应

另给 GridSampler3D 和 Maximum 第一份回答各做 R2、R3，共四次新请求；输入复用该主体自己的前轮摘要和必要源码/文档，不给“必须换 Action”要求。R2 新增的 128KiB/核仅是外部规划预算。R3 没有新增证据，外部三轮范围结束。

| 后继 | 比较怎样改变 |
| --- | --- |
| [grid_sampler_3d-r2](sources/development/history-runs/grid_sampler_3d-r2/answer.md) | 保留原Action，但把未闭合alias改为18个独立FP32数组的保守条件布局，计算74T/72T+R及1024/1536/2048、双槽预算；几何复用仍保留注册意图缺口与成本。 |
| [grid_sampler_3d-r3](sources/development/history-runs/grid_sampler_3d-r3/answer.md) | 没有强换Action或造新候选，保留R0及条件方案，交付18数组容量、34/35调用表达式模型、几何复用/nearest残余，按外部三轮范围结束。 |
| [maximum-r2](sources/development/history-runs/maximum-r2/answer.md) | 保留int8转换链收缩，以128KiB核算R0 17T与S1 9T及4096/8192/16384参数边界，固定T的6L→3L与放大tile另减L分别计数；广播、双槽、case18驻留重新比较。 |
| [maximum-r3](sources/development/history-runs/maximum-r3/answer.md) | 保留同一Action条件方案和R0，明确不因已投入而自动继续；结束本授权范围且不追加第四轮，资源/GM工作/未测残余持续保留。 |

四份均实际回应所给三部分摘要和新增/未变约束。R2重算预算，R3无新证据时保留R0并按外部范围交付；未发现强换Action、未测当反证或纸面计划变实现的退化。

R2实际继承的GridSampler3D/Maximum首轮摘要分别为818/598字符；R3继承的前轮简短更新与三部分摘要分别为1969/1927字符，没有重新携带完整首轮分析。

这四次静态后继没有真实 patch 或失败/有效计时。相应结构分支由 CPU contract 测试覆盖，不把合成输入报告成硬件反馈闭环。详见[独立后继审阅](sources/development/review/HISTORY.json)。

八份初答均达到冻结五维标准的充分档（80/80）。这次没有旧技能对照，不能据此声称准确率或优化能力提高。资料采用静态充分展开，初答每份输入约17.1万—18.1万token；只检验给定文档后能否实质使用，不检验自主检索效率或日常阅读成本。
