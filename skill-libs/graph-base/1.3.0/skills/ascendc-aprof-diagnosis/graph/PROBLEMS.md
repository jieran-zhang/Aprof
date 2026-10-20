# Problem轻量目录

目录由模板生成；无邻接命中也扫描候选。适用域match仅用于检索，不证明平台能力。

- [problem.broadcast_strategy_mismatch](problems/problem.broadcast_strategy_mismatch.md)：广播方式没有利用连续内轴或小输入复用 → 重复从GM读取或在UB中反复扩展/Scalar索引 → 额外读流量、展开临时区与控制开销进入关键路径
- [problem.cache_policy_mismatch](problems/problem.cache_policy_mismatch.md)：一次性流量和待复用数据采用不合适的缓存策略或共享工作集超过有效L2 → 缓存填充/替换增加成本，或重复访问未命中 → 额外GM访问或缓存管理影响关键路径
- [problem.chunk_merge_overhead](problems/problem.chunk_merge_overhead.md)：增加分段缩短主阶段关键路径却制造更多partial状态 → 每段额外写回、同步、读回及合并 → 当合并随段数增快，额外成本超过并行节省
- [problem.control_metadata_overhead](problems/problem.control_metadata_overhead.md)：循环不变字段或公共地址前缀在每轮重复加载/计算 → Scalar为同一信息反复执行解引用、乘除或分支 → 指令发射被控制工作占用而拖慢有效流水
- [problem.core_tail_imbalance](problems/problem.core_tail_imbalance.md)：任务数量或单位任务成本在核间不均 → 少量核承担集中尾部、变长或causal工作 → 其他核提前完成/等待，调用时长由最长核决定
- [problem.dynamic_shape_mismatch](problems/problem.dynamic_shape_mismatch.md)：一套核数、tile、buffer或workspace覆盖不同资源主导区间 → 小shape付出不必要固定成本，大shape欠并行或流量/容量不适配 → 不同区间出现不同退化，需要条件化dispatch而非固定最优值
- [problem.excessive_sync_scope](problems/problem.excessive_sync_scope.md)：局部生产消费只需要有限流水或参与核完成 → 实现却等待整个流水或所有核 → 无关工作被阻塞，产生可避免等待并抑制并行
- [problem.fragmented_writeback](problems/problem.fragmented_writeback.md)：已就绪的相邻输出被分成多个小写回 → 输出流水重复支付发射与对齐成本 → 短写回和等待进入尾部关键路径，即使输入搬入已高效仍可能受限
- [problem.insufficient_input_reuse](problems/problem.insufficient_input_reuse.md)：同一地址和内容在复用窗口被重复从GM读入 → 片上或缓存复用机会未被利用 → 重复读增加GM/MTE成本；若进入关键路径则可能拖慢调用
- [problem.l1_l0_reuse_deficit](problems/problem.l1_l0_reuse_deficit.md)：A/B块在多个对侧tile期间地址和值不变 → 该块仍在内循环反复搬入L1或L0，未建立相应驻留 → MTE1/MTE2搬运及Cube等待增加
- [problem.memory_bandwidth_saturation](problems/problem.memory_bandwidth_saturation.md)：有效大块搬运占据关键路径 → 在足够并发与合法对齐下，实际传输速率接近目标平台可达上限 → 进一步增加发射或缓冲不能消除算法必要字节，节省时间需减少可消除流量或增加复用
- [problem.missing_kernel_fusion](problems/problem.missing_kernel_fusion.md)：可组合的相邻子操作用独立kernel和GM中间张量连接 → 每步重复launch与中间写读 → 短链或低算术强度时固定启动和中间流量可能主导
- [problem.mixed_pipeline_imbalance](problems/problem.mixed_pipeline_imbalance.md)：AIC和AIV每tile有效工作、任务粒度或吞吐不匹配 → 较快一侧在真实生产消费边界反复等待较慢一侧 → 可重叠链受较慢阶段和握手频率限制
- [problem.noncontiguous_access](problems/problem.noncontiguous_access.md)：切分或遍历轴跨过物理连续内轴 → 相同有效元素分解成离散事务、短块或额外padding → 发射与实际流量增加使有效字节带宽下降
- [problem.onchip_capacity_pressure](problems/problem.onchip_capacity_pressure.md)：按dtype、对齐和深度求出的同时存活物理字节接近合法可用容量 → 余量不足迫使tile/流水深度收缩或中间结果外溢 → 更短tile、额外搬运或无法建立重叠会增加执行成本
- [problem.pipeline_serialization](problems/problem.pipeline_serialization.md)：不同tile本可独立的搬运与计算使用同buffer或被过早等待阻断 → 生产消费依赖闭环没有留出下一tile预取窗口 → MTE、Vector或Cube顺次忙而其他流水等待
- [problem.reduction_strategy_mismatch](problems/problem.reduction_strategy_mismatch.md)：全载/行列切分/跨核方案未适配R长度、独立A量和容量 → 可能产生欠并行、重复读、过多partial或不合适的广播路径 → 主归约及合并/后变换成本超出可行替代方案
- [problem.redundant_cast](problems/problem.redundant_cast.md)：局部链在相邻阶段反复宽窄往返转换 → 部分转换不承担必须的数值边界或消费者dtype契约 → 额外Cast指令、临时buffer与控制增加成本
- [problem.redundant_gm_round_trip](problems/problem.redundant_gm_round_trip.md)：中间值在本地生产后写GM → 同一owner后续又从GM读回，且没有必须的外部可见性 → 额外写读、发射和依赖等待占据关键路径
- [problem.register_spill](problems/problem.register_spill.md)：动态索引、大对象、取地址或过长生存期增加寄存器分配压力 → 编译器把部分值保存到栈/内存并在热区重载 → 非算法必要LoadStore与依赖增加关键路径
- [problem.scalar_control_hot_loop](problems/problem.scalar_control_hot_loop.md)：本可按向量表达的元素处理使用逐元素Scalar访存或算术 → Scalar重复地址计算与读写并占据指令分发 → 其他流水不能及时获发工作并出现bubble
- [problem.tail_slow_path](problems/problem.tail_slow_path.md)：尾块走逐元素标量、多次小API或重复mask设置 → 相对主体每有效元素需更多控制和发射成本 → 尾占比较高或落在最长核时放大总时延
- [problem.tiny_transfer_setup_amplification](problems/problem.tiny_transfer_setup_amplification.md)：循环把可合并的有效区间分成许多小DataCopy → 每次搬运重复支付参数构造、发射与同步固定成本 → 每指令有效字节偏低，使MTE忙而有效带宽仍低
- [problem.transfer_compute_contention](problems/problem.transfer_compute_contention.md)：搬运和Vector在重叠窗口争用同一片上资源或端口 → 重叠使仲裁/等待增多而非隐藏延迟 → 总时长受共享资源吞吐限制
- [problem.ub_bank_conflict](problems/problem.ub_bank_conflict.md)：并发数据块按目标bank/group几何映射到冲突集合 → 硬件仲裁把部分访问串行化 → 同等有效向量工作需要更多周期
- [problem.underused_task_parallelism](problems/problem.underused_task_parallelism.md)：独立可并行工作未充分分解或启动核数过少 → 有效任务数少于可用同类核且每任务有足够长工作 → 部分核空闲，关键路径仍由少数核串行承担
- [problem.vector_api_fragmentation](problems/problem.vector_api_fragmentation.md)：可批处理的Vector工作被拆成大量小count/repeat调用 → 每次重复mask/repeat和指令发射控制 → 有效lane利用偏低并增加Scalar与Vector固定开销
- [problem.workspace_overallocation](problems/problem.workspace_overallocation.md)：按最大shape、总task数或过量槽数预留workspace而实际只需有限并发槽 → 多余区间可能增加分配/清零/传输或挤压其他算子内存 → 仅当实际触及这些成本时才成为性能机制，纯保留字节是资源风险
