# Action 条件分层审查：v0004 → v0005

本次按变换语义逐项审查全部 28 个 Action；旧快照、前提和身份保留。来源范围没有扩大，新增分层属于本次机制归纳。安全/结构条件可由当前源码、host/tiling、API契约和资源公式证明；性能未知不要求先用硬件证明后才允许提出优化。

## 分层原则

- 实施安全：数值/ABI/地址/所有权/依赖/容量/平台API支持等必须满足。
- 结构适用：当前对象和变换域真实匹配，不能从动作名或有利案例推断。
- 性能假设：预期减少哪项工作、作用于哪些case、代价与反例；未知可保留，明确反证应影响优先级。
- 试验价值：候选比较和补证据后形成，不由Action安全ready自动获得。
- R2反馈：绑定R1实际变更与预测，合法性/收益/归因分别更新；不强制换Action。

source、profile、constraint前缀都不是语义分类器。特别是旧source名中的saturation/register_spill/overhead不表示已有对应性能观测。`constraint.compiler_report`原来要求归因资料，不是合法性证明，因此转为性能证据并补可由源码核验的生命周期条件。

## 每项 Action 的适用与预测

| Action | 新硬条件数 | 移为性能/选择线索的旧条件 | 适用说明 |
| --- | ---: | --- | --- |
| `action.align_cache_policy` | 4 | 无；保留结构观察并明确不证明热点 | 目标GlobalTensor的实际访问方向、合法hint与当前平台API支持明确；一次性流和复用流均可比较合法策略，不以名字中的“mismatch”认定错误。 |
| `action.amortize_partial_merge` | 4 | 无；保留结构观察并明确不证明热点 | 存在可归并partial，归约顺序、精度、workspace owner和参与核完整已知；合法chunk数或归并层次由C2确认。 |
| `action.balance_tail_assignment` | 3 | `symptom.profile.per_core_time_imbalanced=true` | 存在可重新归属的尾部任务；重分后完整覆盖、唯一写回、所有权和依赖不变或已由C2重新确认。 |
| `action.batch_vector_api_calls` | 3 | `symptom.profile.vector_granularity_low=true` | 存在可按同一合法Vector API的count/repeat等参数合并表达的调用域；依赖、mask、dtype、stride和目标支持均已验证。 |
| `action.batch_writeback` | 4 | 无；保留结构观察并明确不证明热点 | 同一owner的相邻有效输出可在合法时机同时写回；合并不越过其他核输出、padding或消费者可见性边界。 |
| `action.coalesce_cast` | 4 | 无；保留结构观察并明确不证明热点 | 完整数值契约、每步dtype/舍入/饱和/异常值语义和消费者明确；仅消除可证明等价的转换或移动合法边界。 |
| `action.coalesce_contiguous_transfers` | 3 | `symptom.profile.mte_setup_dominated=true` | 源/目标区间、stride单位、对齐、有效尾长和依赖完成点可证明可用目标API合并；容量与唯一输出保持合法。 |
| `action.decompose_tasks_dynamically` | 4 | `symptom.profile.tasks_below_available_cores=true`<br>`symptom.workload.tiny_or_overhead_limited=false` | 已识别独立任务域或合法partial归并，任务/输出所有权、workspace、精度与同步完整；改变计划的任务数量和核数由C2确认。 |
| `action.dispatch_by_workload` | 4 | 无；保留结构观察并明确不证明热点 | 已支持的shape/dtype/features域及fallback完整，host判别与kernel分支一致，每一新分支分别满足合法性。 |
| `action.fuse_kernel_chain` | 4 | 无；保留结构观察并明确不证明热点 | 生产消费链、所有消费者和完整数学/执行契约已知，融合边界由C2确认；核角色、owner、可见性和容量满足。 |
| `action.hoist_invariant_control` | 4 | 无；保留结构观察并明确不证明热点 | 当前循环域内的表达式确为不变量或可等价递推；ABI、溢出、地址单位、精度、主尾序列和事件关系均保持。 |
| `action.keep_intermediate_onchip` | 3 | `symptom.profile.gm_traffic_amplified=true` | 中间值的生产者、全部消费者、owner、外部可见性及生命周期已知；只有已获C2许可的合法片上边界内可以删除对应GM往返。 |
| `action.narrow_sync_scope` | 4 | `symptom.profile.overlap_low=true` | 真实生产消费依赖、可见性、buffer寿命、参与核及事件拓扑完整；收窄后不存在提前复用、漏等待或死锁。 |
| `action.pad_ub_layout` | 3 | `symptom.profile.ub_conflict_high=true` | 目标API的地址/stride/count及容量合法，布局变换保持数据映射；用于选择padding的bank/group映射必须有当前目标依据。 |
| `action.rebalance_mixed_stages` | 4 | 无；保留结构观察并明确不证明热点 | 同tile的AIC/AIV任务、交接tensor、依赖和owner已知；重分工作/粒度必须满足算术语义及目标核角色。 |
| `action.reduce_memory_traffic` | 3 | `symptom.source.memory_bandwidth_saturation=true` | 已用地址/值依赖证明可消除的输入读取或中间读写，完整语义、必要外部输出与容量合法；无需先满足“大块连续”形态。 |
| `action.reorder_contiguous_access` | 4 | 无；保留结构观察并明确不证明热点 | 当前物理stride与切分轴已知；重排后每个输入/输出逻辑映射、unique owner和API访问域合法。 |
| `action.restructure_broadcast` | 4 | 无；保留结构观察并明确不证明热点 | 已明确对齐shape、广播flag、零stride、输入值复用域及输出映射；目标API和临时区满足数值与容量。 |
| `action.restructure_reduction` | 4 | 无；保留结构观察并明确不证明热点 | 归约轴、归约算子、精度/结合次序许可和owner明确；全载/切分/partial合并分别满足容量和同步。 |
| `action.retain_matrix_tiles` | 4 | 无；保留结构观察并明确不证明热点 | A/B块在复用窗口内地址和值不变，目标L1/L0布局、对齐、容量和事件生命周期合法；流式一侧仍按需更新。 |
| `action.reuse_disjoint_onchip_buffers` | 3 | `symptom.source.ub_live_bytes_near_capacity=true` | 候选buffer的完整生产消费/异步完成生命周期经证明不重叠，alias对齐、地址空间、有效长度及容量合法；并不要求原峰值已接近上限。 |
| `action.reuse_input_tiles` | 4 | 无；保留结构观察并明确不证明热点 | 输入在明确窗口内地址和值不变，消费者、owner、生命周期及目标驻留/缓存路径由C2许可；容量与通路支持有依据。 |
| `action.shorten_scalar_lifetimes` | 3 | `symptom.source.register_spill=true`<br>`constraint.compiler_report=true` | 变量定义/全部使用、别名/取地址/逃逸、编译地址空间和副作用已知；改写后值、可见性及执行依赖保持；不要求先观测到spill。 |
| `action.size_workspace_by_shape` | 4 | 无；保留结构观察并明确不证明热点 | 所有runtime shape、并发slot、kernel索引上界、对齐和框架保留区可证明覆盖；host分配与kernel偏移必须一致。 |
| `action.software_pipeline_stages` | 4 | `symptom.profile.overlap_low=true` | 多个tile/阶段之间存在可重叠的独立工作，producer/consumer事件与buffer生命周期已完整证明；新增深度/序言尾声与容量合法。 |
| `action.stagger_resource_access` | 4 | 无；保留结构观察并明确不证明热点 | 候选发射可在依赖许可的窗口内改相位，资源映射有当前目标依据；改变调度仍满足所有buffer寿命和事件。 |
| `action.vectorize_scalar_loop` | 3 | `symptom.profile.scalar_hot=true` | 当前逐元素数据计算可用目标支持的Vector路径等价表达；数学/异常值/舍入、索引依赖、mask、别名和有效范围合法。 |
| `action.vectorize_tail` | 4 | 无；保留结构观察并明确不证明热点 | 尾部有效元素域、mask/count或padding规则及唯一写回明确，目标dtype/API支持有依据；不得越界读取或覆盖其他owner。 |

## 全部旧前提的去向与理由

### action.align_cache_policy

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.cache_policy_mismatch=true` | safety_conditions | 同一策略用于不同复用模式是结构线索；不表示任何模式必然被缓存拖慢。 |
| `constraint.cache_api=true` | safety_conditions | 当前平台、SDK、读写方向与目标hint必须在API支持域内；枚举存在不等于可用。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：符合复用窗口的缓存策略可能减少目标访问实际等待或替换干扰；也可能降低其他对象命中。

- 列出目标同地址重复次数、复用距离、一次性流字节及当前hint，按工作集/缓存容量来源筛掉无适用性的路径。
- 有编译/访问trace时核对实际设置；后续按对象观察读字节与等待，不以整体低hit自动判定策略错误。

### action.amortize_partial_merge

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.chunk_merge_overhead=true` | safety_conditions | 多chunk、partial格式及归并拓扑是结构事实，“overhead”并非实测时延结论。 |
| `constraint.merge_semantics=true` | safety_conditions | 部分结果表示、合并算子和精度顺序须合法，并保持最终输出唯一所有权。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：减少chunk或分层归并可减少partial读写、发射与等待，但也可能降低并行度并拉长最长核。

- 按shape列出chunk数、每段有效量、partial字节和合并工作量，比较至少有竞争性的可行粒度。
- 判别最长核计算与归并关键路径；没有分阶段timing时保留二者为预测，用静态工作量确定值得试的范围。

### action.balance_tail_assignment

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.profile.per_core_time_imbalanced=true` | performance_hypotheses | 每核时间差说明试验可能有价值，不是重分合法任务的实施安全条件；须与尾部映射共同解释。 |
| `symptom.source.tail_concentrated=true` | safety_conditions | 尾任务集中在少量核是任务映射事实，不自动等于核时长不均。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：均摊尾任务可能缩短最长核，但额外调度、较差局部性或主任务不均可抵消。

- 从host分配式和kernel索引推导每核主/尾有效量、任务成本类别和空核，避免按元素数假定所有任务等价。
- 若实际不均来自数据依赖、非尾任务或cache，选择对应替代机制；无per-core时间不妨碍基于明确尾负载差提出试验。

### action.batch_vector_api_calls

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.profile.vector_granularity_low=true` | performance_hypotheses | 低Vector粒度是性能判别证据，合法合批可由调用结构和API契约独立证明。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

新增 `constraint.vector_batch_compatibility=true`：针对已绑定实现、对象/阶段、workload和目标SDK，拟合并的Vector调用能用该API允许的count/repeat/stride/mask表示，并保持调用间数据依赖和数值语义。

- 引用各调用点、操作种类、dtype、地址空间与每次有效元素域，列出拟合并前后元素映射。
- 核对当前平台/SDK支持、count/repeat上限、blk/repeat stride单位、mask和对齐。
- 逐项检查跨调用读写依赖、alias、舍入和异常值；若需要中间结果或改变数值顺序，不属于直接合批。
- 由新活跃区和深度计算容量；其余semantic_equivalence与capacity仍独立核验。

未知仅限：具体API/目标SDK支持或有效域无法定位。；调用间别名/依赖、数值路径或参数上限仍未确认。。

性能预测：合法合批可能减少Vector/Scalar发射与循环控制，未必减少必要算术或内存量。

- 从调用点列出单次有效元素、总调用次数、依赖/stride和API上限，推导可合并次数与新UB峰值。
- 若已是大count或后端已合并，收益依据减弱；把减少的调用数作为可验证预测，不要求先测到低粒度。

### action.batch_writeback

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.fragmented_writeback=true` | safety_conditions | 多个小写回的区间和生产完成边界可由源码确认；fragmented不直接说明主瓶颈。 |
| `constraint.output_ownership=true` | safety_conditions | 全部有效输出由合法owner恰好写回，合并不覆盖其他owner或padding外域。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：合并写回可减少发射数，实际有效输出字节不变；缓冲滞留可能反而延长关键路径。

- 列出每次输出地址/有效长度/完成点，并计算合并窗口需要额外存活的字节。
- 比较写回发射节省与buffer释放/消费者延迟；没有MTE计数时仍可据明显碎片结构提出试验。

### action.coalesce_cast

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.redundant_cast=true` | safety_conditions | 宽窄往返Cast是结构事实，不说明Cast冗余或可以直接删除。 |
| `constraint.precision=true` | safety_conditions | Cast/中间dtype变化须保持已授权数值与异常值契约，不以可能加速放宽精度。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：合法减少转换可能减少指令与临时区，但更宽中间值、不同指令路径或寄存器压力可抵消。

- 逐段展开表达式的dtype与round mode，用原oracle范围证明可删除边界，不把精度容忍当任意重排许可。
- 比较转换调用次数、临时区峰值及预计新增宽类型工作；数值安全不明时只做分析，不实施。

### action.coalesce_contiguous_transfers

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.profile.mte_setup_dominated=true` | performance_hypotheses | 发射成本主导是待验证机制；相邻搬运是否可合并由地址、依赖和API范围证明。 |
| `symptom.source.inner_loop_copy=true` | safety_conditions | 循环内多次Copy是结构线索，必须另外检查相邻性，不能把任何内循环搬运都合并。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：合并可减少发射数；若原路径已充分流水或带宽占主导，时间收益可能小，UB峰值可能增加。

- 由地址式求每次有效字节和调用次数，证明合并后读写映射等价；结合固定来源API限制决定count/stride方案。
- 区分“小搬运发射成本”与“总必要字节”预测；缺MTE setup计数不禁止已有合法连续段的实验。

### action.decompose_tasks_dynamically

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.profile.tasks_below_available_cores=true` | performance_hypotheses | 任务/可用核关系帮助判断并行机会，不能代替任务所有权或证明增加核数的收益。 |
| `symptom.source.fixed_or_undersubscribed_tasking=true` | safety_conditions | 固定或未充分扩展任务是host/kernel映射事实；可用核数多不代表多核一定有收益。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |
| `symptom.workload.tiny_or_overhead_limited=false` | performance_hypotheses | 原期望false完整保留；这是多核调度成本的选择假设，不是任务重分的语义安全条件。 |
| `constraint.task_ownership=true` | safety_conditions | 重分后的任务、输出和partial归并owner完整、无重叠遗漏且同步可证明。 |

性能预测：增加合法任务可能减少最长核工作；tiny/overhead-limited为true时也可能更差，必须比较调度/归并成本而非禁止安全试验。

- 按合法任务域算每核工作、空核、partial字节和merge量，优先排除明显由额外调度吞噬工作量的方案。
- 原tiny_or_overhead_limited期望false保留为性能选择假设；状态未知时用工作量模型比较，不能伪填false。

### action.dispatch_by_workload

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.dynamic_shape_mismatch=true` | safety_conditions | 相同核数/tile跨shape使用是结构事实，不推出必须特化；分段依据应绑定实际成本模型。 |
| `constraint.dispatch_coverage=true` | safety_conditions | 每个支持的shape/dtype/feature都命中唯一合法路径或明确fallback；边界不可漏测漏实现。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：若不同区间受不同工作量/容量/调度成本控制，分组策略可改善相应case；额外分支也可能无益。

- 按case形态比较每核任务、tile数、尾比例、UB峰值及算法工作量，说明划分阈值来源与单位。
- 区间边界和fallback必须覆盖全域；用已有知识与源码差异选择值得试的分支，未测阈值标成参数候选而非通用常数。

### action.fuse_kernel_chain

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.missing_kernel_fusion=true` | safety_conditions | 独立launch和GM中间连接是结构事实，不说明融合后一定消除GM或更快。 |
| `constraint.fusion_boundary=true` | safety_conditions | 融合不跨越必须保持的可见性、核角色、外部消费者或同步契约；改变边界须回C2。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：合法组合可能减少launch或部分中间读写；如果融合仍经workspace交接，不能宣称消除GM流量。

- 画当前与拟议阶段DAG、owner和交接层级，分别计launch数、必要中间字节及活跃峰值。
- 比较组合、数据驻留、流水重叠三种效应；跨平台专用通路以包内对应资料和当前SDK为准。

### action.hoist_invariant_control

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.control_metadata_overhead=true` | safety_conditions | 重复字段/索引/分支是源码层次数事实，不能证明编译后仍重复，更不能据“overhead”认定热点。 |
| `constraint.control_equivalence=true` | safety_conditions | 不变量/地址递推/首主尾拆分保持原访问与事件序列，处理零/单tile、整数溢出、分支副作用和精度。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：只有编译后仍保留的重复load/控制被减少且作用于关键路径时才可能加速；增加活跃寄存器、代码体积或CSE已完成时可能无益。

- 先数实际循环次数、重复表达式依赖、相对必要Vector/搬运工作；小固定字段缓存与主要字节/逐元素工作量比较后再排优先级。
- 反汇编/编译报告可判别CSE、重复load和spill；不可得时明确预测与反例，不以源码容易等价就优先，也不因未证明热点一律否决。

### action.keep_intermediate_onchip

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.gm_intermediate_roundtrip=true` | safety_conditions | GM中间写读是地址和生命周期事实；必须核验外部消费者，不能把总GM放大归因到该tensor。 |
| `symptom.profile.gm_traffic_amplified=true` | performance_hypotheses | GM流量放大用于机制归因；是否可删除特定中间读写取决于消费者可见性、生命周期和容量。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：合法驻留可去掉对应中间写读，但UB/L1占用、tile缩小或spill可抵消；实际外部流量减少需后续确认。

- 按目标tensor逐次列写读地址、唯一/重复字节和消费者，算驻留峰值与可能挤掉的buffer/tile容量。
- 比较保留、重算与GM交接方案；无GM放大计数时可凭精确冗余往返与容量模型提出试验。

### action.narrow_sync_scope

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.sync_inside_tile_loop=true` | safety_conditions | tile循环内大范围同步是静态调用事实；该等待可能完全必要或本就不在关键路径。 |
| `symptom.profile.overlap_low=true` | performance_hypotheses | 低重叠是性能假设/判别依据，依赖及生命周期正确才是重排的实施安全条件。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |
| `constraint.dependency_lifetime=true` | safety_conditions | 所有producer/consumer、异步完成、释放/覆盖/复用边界真实合法；不能把等待可能慢当成可删依赖。 |

性能预测：精确收窄同步可能去掉无关等待并增加合法重叠；事件管理增加或原等待不关键时不一定有收益。

- 从Set/Wait或队列绘制逐buffer依赖图和参与者，逐条指出原同步保护的边及拟保留边。
- 有trace再验证减少的等待是否暴露关键路径；无trace时用依赖图证明安全并提出等待预测，不能凭overlap低删除依赖。

### action.pad_ub_layout

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.profile.ub_conflict_high=true` | performance_hypotheses | 实测UB冲突用于验证目标映射假设；布局合法与容量边界可以源码及API资料证明。 |
| `symptom.source.ub_stride_conflict_risk=true` | safety_conditions | UB地址映射落入潜在冲突集合是目标相关结构事实，不等于已发生高冲突。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：在真实并发及目标映射匹配时padding可能减少资源冲突；额外字节/转置和缩小tile可能抵消。

- 按真实src/dst起址、dtype、blk/repeat stride求映射并核对目标资料；几何未知时不能借其他架构常数定padding。
- 比较候选最小padding字节及UB峰值；冲突计数只用于验证假设，不作为合法布局改动的统一前置门槛。

### action.rebalance_mixed_stages

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.mixed_pipeline_imbalance=true` | safety_conditions | 阶段粒度或工作比例不同是结构观察，不代表阶段时间应相等或已出现不均衡。 |
| `constraint.cross_engine_dependencies=true` | safety_conditions | AIC/AIV角色、跨引擎数据可见性、事件和消费者生命周期必须符合目标支持。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：联合调整tile和后处理粒度可能缩短阶段DAG关键路径；占用、交接与同步开销可能增加。

- 建立每阶段工作量、交接字节、buffer峰值和先后关系，找实际可以重分或改变粒度的范围。
- 比较目标是最长依赖链而非AIC/AIV总时间相等；缺阶段timing仍可按不同比例workload提出有界试验。

### action.reduce_memory_traffic

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.memory_bandwidth_saturation=true` | performance_hypotheses | 该S现有定义仅确认大块连续搬运，并不确认饱和；消除冗余流量还适用于短块/复用路径，不应把此形态硬绑到Action。 |
| `constraint.traffic_reducible=true` | safety_conditions | 能指出具体可消除读写及等价值/消费者关系；仅观察带宽或字节大不能证明可删。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：减少真实必要通路上的冗余字节可能降低传输成本；若只减少逻辑读、cache本已复用或新增计算成为关键路径，收益不确定。

- 明确原始唯一字节、逻辑重复次数、实际通路和可消除区间，避免把逻辑GM字节等同HBM流量。
- 比较驻留/重算/融合新增容量、同步和算术；无饱和证据仍可选择来源支持且当前实现确有可消冗余的方案。

### action.reorder_contiguous_access

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.noncontiguous_access=true` | safety_conditions | 离散地址序列是结构事实；不能仅用stride数值推断吞吐或默认必须转置。 |
| `constraint.layout_semantics=true` | safety_conditions | 遍历/布局改变保持逻辑元素与物理地址一一对应、合法边界和输出owner。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：按连续段组织访问可能减少短搬运或Scalar解码，但额外格式转换、失去复用或任务失衡可抵消。

- 从shape/stride推导最大连续段、段数和输出所有权，比较直搬、strided API或块转置的成本。
- 把不规则Gather索引与规则仿射布局区分；不能以源有连续后缀就覆盖重复目标写入或非法跨界。

### action.restructure_broadcast

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.broadcast_strategy_mismatch=true` | safety_conditions | 现有路径未区分连续轴/重复输入是结构线索，mismatch不是已验证的错误策略。 |
| `constraint.broadcast_semantics=true` | safety_conditions | shape对齐、广播轴、零stride及输入值不变范围明确，输出映射与数值合法。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：重组广播轴或小输入复用可能减少重复读取/展开工作；新索引或UB展开也可能更贵。

- 按每个输入的广播掩码/stride、唯一字节和重复次数计算成本，先选择来源匹配的广播形态。
- 对比GM到UB与UB内部广播位置及API支持；缺PMU不阻止基于明确广播结构的方案分析。

### action.restructure_reduction

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.reduction_strategy_mismatch=true` | safety_conditions | 当前归约形态与策略是结构事实；mismatch名称不证明某种方案必优。 |
| `constraint.reduction_semantics=true` | safety_conditions | 归约算子、初值、有效域及允许的结合/舍入顺序不被未经授权改变。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：按A/R、AR/ARA和容量选择分解可能减少重复读取或最长核，但merge、临时区和精度路径会改变成本。

- 列出A/R及连续性、全载容量、并行任务数和partial字节，对合法候选做工作量比较。
- 数值结合性不许可时直接保留顺序；缺具体阶段时间只影响预测强度，不把合法结构探索判为blocked。

### action.retain_matrix_tiles

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.l1_l0_reuse_deficit=true` | safety_conditions | 多对侧tile中重复装入同块是源码事实，不直接证明额外HBM流量或关键路径。 |
| `constraint.l1_l0_budget=true` | safety_conditions | L1/L0的真实分配、对齐、布局、深度和同时存活峰值分别符合当前目标预算。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：保留复用侧可减少相应层次装载，可能挤压双缓冲、缩小tile或导致更复杂tail。

- 按M/N/K顺序标出每层加载次数、驻留字节、更新与释放点；计算驻留与双缓冲并存峰值。
- 区分GM→L1与L1→L0节省，不把某层次数减少泛化为HBM收益；两种驻留侧均按具体shape比较。

### action.reuse_disjoint_onchip_buffers

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.ub_live_bytes_near_capacity=true` | performance_hypotheses | 接近容量上限影响收益与选择，不决定不重叠buffer复用是否合法；安全由生命周期、容量和语义约束负责。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |
| `constraint.dependency_lifetime=true` | safety_conditions | 所有producer/consumer、异步完成、释放/覆盖/复用边界真实合法；不能把等待可能慢当成可删依赖。 |

性能预测：复用可降低物理峰值，并可能使更合适tile或流水深度可行；若释放容量无用途，时延可能不变。

- 画每个buffer的定义、异步消费完成和最后释放区间，按实际深度/对齐计算旧新峰值。
- 明确释放字节将支持哪项计划或减少哪项成本；仅减少分配大小不能自动声称加速。

### action.reuse_input_tiles

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.insufficient_input_reuse=true` | safety_conditions | 重复读取同一切片是结构事实；insufficient名称不自动说明未命中cache或驻留可行。 |
| `constraint.reuse_domain=true` | safety_conditions | 同地址同值的复用窗口、owner和覆盖/更新边界可证明，驻留不能越过输入变化或外部写入。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：驻留或改变tile顺序可减少重复装入；代价是更长存活、较小tile/较少流水buffer，L2提示不保证实际驻留。

- 计算唯一切片字节、重复次数、复用距离、当前缓冲释放点和驻留后峰值，区分UB/L1保留与L2策略。
- 具体选择重复输入、矩阵块或坐标/trig表适用文档；无读流量计数仍可据明确复用结构提出方案，不能把假设当测量。

### action.shorten_scalar_lifetimes

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.register_spill=true` | performance_hypotheses | 该S实际定义是大对象/长生存期等源码风险，非实际spill；安全生命周期改写不以已出现风险或spill为必要条件。 |
| `constraint.compiler_report=true` | performance_hypotheses | 编译报告用于判别spill、栈和活跃量，属于性能/资源归因证据；实施安全改由具体源码生命周期合法性证明，报告存在不能替代该证明。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

新增 `constraint.scalar_lifetime_legality=true`：针对已绑定实现、目标对象和变换窗口，缩短标量/对象存活期后所有使用仍由正确值支配，别名/取地址/逃逸/异步访问及副作用可见性不变。

- 列出定义、全部读写使用、最后使用和控制流分支；重计算使用同一数值语义且不遗漏副作用。
- 检查取地址、引用、指针逃逸、对象成员与调用参数，不把仍被引用或异步消费的对象提前销毁/覆盖。
- 核对存储地址空间、对齐、构造析构或宏展开要求，保持ABI及跨函数执行契约。
- 标出新旧作用域及alias关系，对零/单循环和条件分支的初始化覆盖逐项证明。

未知仅限：使用/别名/逃逸边界不完整或被不可见调用访问。；重计算副作用、数值顺序或对象生命周期契约尚未确认。。

性能预测：缩短活跃范围可能减少寄存器压力或spill，也可能增加重算和指令体积；编译器原本已处理时可能无收益。

- 由源码画定义-最后使用和alias/escape关系，识别可缩短且不改变副作用的窗口并估算活跃量变化。
- 优先用现有编译报告/反汇编判别spill、stack和CSE；不可得时保留可证结构与具体预测，不禁止合法试验，也不认定spill已存在。

### action.size_workspace_by_shape

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.workspace_overallocation=true` | safety_conditions | 按最大shape或过量槽位分配是字节公式观察；不说明设备实际读写了这些额外字节。 |
| `constraint.workspace_ownership=true` | safety_conditions | 按shape和并发slot完整覆盖kernel索引上界、owner、异步生命周期与框架保留区。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：缩减workspace可降低占用；只有触及多余区域或影响资源可用性时才可能改善时延。

- 根据全shape域、异步并发槽和各段owner重算上界，核对边界/零任务及调用间生命周期。
- 区分容量收益和时延收益；若只分配未访问，多轮追求加速时其试验价值应低于直接主要计算/流量机会。

### action.software_pipeline_stages

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.profile.overlap_low=true` | performance_hypotheses | 低重叠是性能假设/判别依据，依赖及生命周期正确才是重排的实施安全条件。 |
| `symptom.source.serial_queue_or_event_order=true` | safety_conditions | 当前队列或事件的顺序是结构事实，不说明真实硬件上完全无重叠；高阶API内部流水需单独考虑。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |
| `constraint.dependency_lifetime=true` | safety_conditions | 所有producer/consumer、异步完成、释放/覆盖/复用边界真实合法；不能把等待可能慢当成可删依赖。 |

性能预测：合法预取/计算/写回重排可能缩短稳态关键路径；短任务、单tile、最慢阶段不变或额外buffer成本会限制收益。

- 画原事件DAG并统计tile数、每阶段工作量与buffer峰值，推导至少一个合法重叠窗口和序言/尾声成本。
- 已有trace可验证空洞；无trace时可据明确串行依赖提出试验，不能把double buffer声明等同重叠已发生。

### action.stagger_resource_access

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.transfer_compute_contention=true` | safety_conditions | 同资源访问并存在重叠机会只是潜在竞争结构，不证明已发生资源争用。 |
| `constraint.dependency_lifetime=true` | safety_conditions | 所有producer/consumer、异步完成、释放/覆盖/复用边界真实合法；不能把等待可能慢当成可删依赖。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：错开访问可能降低冲突，也可能损失原有重叠并使总时间增加。

- 根据目标资源映射与实际地址/依赖检查是否真共享资源，比较可调相位窗口及额外等待。
- 没有争用计数时只记录资源竞争预测；资源映射未知先读对应平台文档，不能用其他代际映射补值。

### action.vectorize_scalar_loop

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.profile.scalar_hot=true` | performance_hypotheses | Scalar热点证据提高试验优先级，但不是等价逐元素向量化的安全前提。 |
| `symptom.source.scalar_element_loop=true` | safety_conditions | 逐元素Scalar循环是源码事实，不要求先测到scalar_hot；索引控制与实际数据运算需区分。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：合法向量化可能减少逐元素Scalar处理与发射，但Gather/转换、UB暂存和精度路径可成为新成本。

- 统计每输出标量运算/地址解码及数据复用，读取匹配dtype和形态的Vector/API文档，证明批量路径的精度和mask合法。
- 已有Vector数据运算而仅Scalar控制时不要机械替换；无PMU可从逐元素工作规模提出有来源的试验。

### action.vectorize_tail

| 原前提 | v0005去向 | 审查理由 |
| --- | --- | --- |
| `symptom.source.tail_slow_path=true` | safety_conditions | Scalar或多小API尾处理是结构事实，slow_path名字不表示尾段确为热点。 |
| `constraint.valid_lengths=true` | safety_conditions | 每个主体/尾路径的有效count、mask、对齐及GM写回长度均不越界且完整覆盖。 |
| `constraint.semantic_equivalence=true` | safety_conditions | 完整数学、异常值、精度、地址和值可见性必须满足既有oracle与执行契约；源码证明/API依据可用于分析，后续实施仍需原正确性验证。 |
| `constraint.capacity=true` | safety_conditions | 按当前平台/配置的可用容量与真实对齐、buffer深度和并发存活峰值核算；未知容量上限不能假定足够，也不要求先做性能实验。 |

性能预测：有界Vector尾路径可能减少Scalar/API工作，但尾比例小、额外padding或复杂初始化会限制收益。

- 计算各case尾长/主体比例、每核尾次数和原路径调用数，比较count、mask与padding的合法实现。
- 尾形态覆盖零尾、单元素、近整tile与小shape；缺tail timing只影响效益估计，不阻止源码可证明合法的尾方案。

## 版本与验证边界

policy v0001 绑定冻结v0004来源身份，自v0005起使用；其文件hash由新图来源集合冻结，不能在同一图身份下修改。新Action preconditions严格等于本policy safety_conditions的fact/state投影。每条旧前提在legacy_preconditions和legacy_dispositions完整保留且唯一归类。

两篇Scalar recipe同步区分热点/编译证据、实施安全与试验价值；不是放宽ABI、地址、数值或同步约束。没有新增硬件实验、收益阈值或因果结论。
