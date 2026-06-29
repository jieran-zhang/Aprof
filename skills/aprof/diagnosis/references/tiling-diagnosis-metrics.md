# Tiling 问题与 Metric 诊断矩阵

本文用于把 Tiling 常见问题映射到 msprof 可观测字段、派生指标和 NPU 架构参数，帮助在性能采集后快速判断问题是否来自多核切分、UB 切分或 Buffer 规划。

## 证据等级

- **直接**：msprof 字段或硬件查询结果可直接支持判断。
- **派生**：需要由多个字段计算得到，或需要与 shape / TilingData / 代码公式交叉判断。
- **Trace/对比**：仅凭 CSV 不足以确认，需要 timeline、trace、不同 shape 对比或基线实现对比。

## 通用 Metric 集合

### 1. 核利用与负载均衡

| Metric | 计算方式 | 数据来源 | 说明 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 核利用率 | `Block Dim / coreNum` | `OpBasicInfo.csv: Block Dim` + `GetCoreNumAiv/GetCoreNumAic` | Vector 算子用 AIV，Cube 算子用 AIC，Mix 算子需分别看 AIC/AIV 配比 | 直接 |
| 有效核数 | `min(Block Dim, totalTasks 或 totalTiles)` | TilingData + `Block Dim` | 判断是否存在空核、过开核或动态 shape 未更新 usedCoreNum | 派生 |
| 核间耗时不均衡 | `(max(ai*_time) - min(ai*_time)) / max(ai*_time)` | `PipeUtilization.csv` 各核 `aiv_time(us)` / `aic_time(us)` | >10% 需关注，>30% 通常说明切分或 tail 处理有问题 | 派生 |
| 最慢核定位 | `argmax(ai*_time)` + block_id | `PipeUtilization.csv` | 若最后一个 block 明显最慢，优先怀疑 tail 集中或 tile 分配不均 | 派生 |
| 头开销占比 | `(Task Duration - max(ai*_time)) / Task Duration` | `OpBasicInfo.csv` + `PipeUtilization.csv` | 小 shape 或 blockDim 过大时常见，Task Duration 中调度/初始化占比高 | 派生 |

### 2. 搬运粒度与带宽效率

| Metric | 计算方式 | 数据来源 | 说明 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| 单次搬入粒度 | `GM_to_UB_datas(KB) * 1024 / ai*_mte2_instructions` | `Memory.csv` | 单次 <16KB 时，MTE setup 成本容易放大，常见于 tileLength 过小 | 派生 |
| 单次搬出粒度 | `UB_to_GM_datas(KB) * 1024 / ai*_mte3_instructions` | `Memory.csv` | tail 频繁小块写回或拆 tile 过细时会偏小 | 派生 |
| 搬入带宽利用率 | `GM_to_UB_bw_usage_rate(%)` 或 active BW / 理论带宽 | `Memory.csv` / `PipeUtilization.csv` + NPU 架构参数 | 低带宽且 MTE 指令数高，优先怀疑 tile 过小或非连续搬运 | 直接/派生 |
| 搬出带宽利用率 | `UB_to_GM_bw_usage_rate(%)` 或 active BW / 理论带宽 | `Memory.csv` / `PipeUtilization.csv` + NPU 架构参数 | 非对齐写回、tail 小块、workspace 自读自写都可能拉低 | 直接/派生 |
| MTE2 Bound | `ai*_mte2_ratio` 为主导，通常 >50% | `PipeUtilization.csv` | 搬入主导，结合粒度、L2 hit、GM_to_UB 数据量判断根因 | 直接 |
| MTE3 Bound | `ai*_mte3_ratio` 偏高且写回量/指令数异常 | `PipeUtilization.csv` + `Memory.csv` | 输出写回、workspace 往返、tail 小块写回过多 | 直接/派生 |

### 3. 计算、冲突与流水

| Metric | 计算方式 | 数据来源 | 说明 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| VEC Bound | `aiv_vec_ratio > 50%` 且为最高占比 | `PipeUtilization.csv` | 可能是真计算瓶颈，也可能被 UB bank conflict 放大 | 直接 |
| CUBE Bound | `aic_cube_ratio` 为最高占比 | `PipeUtilization.csv` | MatMul/FA 中需要进一步看理论算力利用率、L0/L1 复用 | 直接 |
| SCALAR Bound | `ai*_scalar_ratio > 30%` | `PipeUtilization.csv` | 常见于小 shape、循环控制复杂、tail 分支过多、TilingData 过大 | 直接 |
| Fixpipe 异常 | `aic_fixpipe_ratio > 15%` | `PipeUtilization.csv` | 常见于 MatMul/FA 的地址或 row stride 未对齐 | 直接 |
| UB 冲突 | `aiv_vec_total_cflt_ratio > 5%` | `ResourceConflictRatio.csv` | >15% 严重；细看 bankgroup/bank/resource/MTE 子项 | 直接 |
| L2 命中率 | `ai*_total_hit_rate(%)` | `L2Cache.csv` | <50% 时关注 CacheMode、数据局部性、跨核重复读 | 直接 |
| DoubleBuffer 重叠率 | MTE2 与 VEC 时间重叠比例 | trace / timeline | CSV 只能看到比例，是否真正重叠需 trace | Trace/对比 |
| 流水线气泡 | 多个 pipe 比例均在 30%-50%，无主导瓶颈 | `PipeUtilization.csv` + trace | 常见于 DB 未生效、stageNum 不够、AIC/AIV 配比不当 | 派生/Trace |

### 4. 架构派生分母

所有容量、核数和理论上限都必须从 `PlatformAscendC` 或运行时平台信息获取，典型值只用于解释：

| 分母 | 获取方式 | 用途 |
| ------ | ---------- | ------ |
| AIV 核数 | `GetCoreNumAiv()` | Elementwise、Broadcast、Reduction、Sort、Transpose 等 Vector 路径的核利用率分母 |
| AIC 核数 | `GetCoreNumAic()` | MatMul、FA、Cube 路径的核利用率分母 |
| UB 容量 | `GetCoreMemSize(CoreMemType::UB)` | UB 总占用、tileLength、chunkRows、bufferNum/stageNum 校验 |
| L1/L0A/L0B/L0C | `GetCoreMemSize(...)` | MatMul/FA 的 L1/L0 分块、K-axis/M-axis/N-axis 分块校验 |
| L2 容量 | `GetCoreMemSize(CoreMemType::L2)` | CacheMode、跨核数据复用、工作集是否可能驻留 |
| BT 容量 | `GetCoreMemSize(CoreMemType::BT)` | MatMul bias / FixPipe 相关 buffer 校验 |
| 频率 | `Current Freq` / `Rated Freq` | DVFS 降频排除，理论耗时计算 |
| 理论带宽 | 平台规格或实测基准 | MTE active BW / 理论带宽，判断是否已接近硬件上限 |
| 理论算力 | Cube/Vector 理论 FLOPS | `aic_cube_fops` / `aiv_vec_fops` 与耗时结合计算利用率 |

## 多核切分问题

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| `blockDim` 过小 | `Block Dim < coreNum` 且 `Task Duration` 高 | 全部 | 核利用率低；`low Block Dim + high Duration` | 增加任务数或减小 tileLength，使 `totalTasks/totalTiles` 能喂满核 | 直接/派生 |
| `blockDim` 过大 | 小 shape 开满核，单核数据量很小 | Elementwise、Broadcast、Reduction、Transpose | 头开销占比高；`ai*_scalar_ratio` 高；单次搬运粒度小 | 小 shape 下减少 usedCoreNum，保证每核至少有足够连续数据 | 派生 |
| totalTiles 少于核数 | tileLength 取太大导致 tile 数不足 | Elementwise、Broadcast、Sort、Transpose | `totalTiles < coreNum`；核利用率低 | 适当减小 tileLength，但需避免 MTE 指令数过高 | 派生 |
| tail 集中到最后一核 | `N % blockDim` 或 `totalTiles % blockDim` 只由尾核承担 | 全部 | 核间耗时不均衡；最慢核为最后 block；tail case 变慢 | 将尾块分散，或按 `tilesPerCore=ceil(totalTiles/blockDim)` 均衡分配 | 派生 |
| 动态 shape 未更新 usedCoreNum | Host Tiling 对不同 shape 复用固定核数 | 全部 | 小 shape 头开销高，大 shape 核利用低；不同 shape 下 `Block Dim` 不随任务数变化 | `usedCoreNum = min(coreNum, totalTasks)` 动态计算 | 派生/对比 |
| 切分维度破坏数据局部性 | 按非连续轴切分，跨核重复读或 stride 搬运 | Broadcast、Reduction、Transpose、MatMul | L2 hit 低；MTE2 时间高；GM_to_UB 数据量超理论必要量 | 优先按连续维或合轴后的任务维切分，减少重复搬入 | 派生 |
| Reduction A 太小但 R 很大未做 Group Reduce | 外层 A 任务不足，R 轴单核串行 | Reduction | 核利用率低；单核 `aiv_time` 长；MTE2/VEC 单核主导 | 当 R 太大且 A 不足以并行时使用 Group Reduce 两阶段合并 | 派生 |
| Sort 归并层级过多 | tileSize 过小，totalTiles 过多 | Sort/TopK | `Task Duration` 随 N 非线性增长；SyncAll/trace 等待多；MTE 指令数高 | 重新计算 tileSize，减少跨核归并轮次，优先核内归并再跨核归并 | Trace/对比 |
| MatMul M×N 切分不足 | `usedCoreNum = ceil(M/singleCoreM)*ceil(N/singleCoreN)` 小于 AIC | MatMul | `Block Dim` 低；`aic_cube_ratio` 不高但 Duration 高 | 调整 `singleCoreM/singleCoreN` 或小 shape 减核，禁止硬编码核数 | 派生 |
| MatMul / GMM AIC:AIV 配比不匹配 | Cube 与 Vector 后处理耗时不匹配 | MatMul、GMM、FA | AIC 或 AIV 侧等待高；流水线气泡；AIC/AIV 时间差大 | 调整 mix kernel 配比或 stage/workspace 份数 | 派生/Trace |
| FA 默认 task 级吃不满核 | `totalTasks << aicNum`，典型 Sq=1 + 大 Sk decode | FlashAttention | 核利用率低；单 task 中 s2 循环很长；MTE/CUBE/VEC 单核时间高 | 评估 split-KV reduce，补 partial workspace 和 cross-core combine | 派生 |
| FA 错把 s2 放入 task 维 | 默认 task 级下跨 task 共享 online softmax 状态 | FlashAttention | 可能性能好但精度错；多核死锁或输出漂移 | 默认模式下 s2 只在 task 内顺序累积；split-KV 必须有 combine | Trace/对比 |

## UB 切分问题

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| tileLength 过大导致 UB 超容 | 未按 bufferNum、dtype、stageNum、对齐后长度计算 | 全部 | 功能错误、随机精度错；无稳定 CSV 直接指标 | 用 `Σ(bufferBytes × depth) ≤ UB` 校验；超容必须减 tile 或 chunk | 派生/对比 |
| tileLength 过大导致 tileNum 不足 | 追求单 tile 最大化，忽略并行度 | Elementwise、Broadcast、Transpose、Sort | 核利用率低；`totalTiles < coreNum` | 在 UB 容量内选择能铺满核的 tile，不是越大越好 | 派生 |
| tileLength 过小 | 过度保守或为了喂满核而拆太碎 | 全部 | MTE 指令数大；单次搬运粒度 <16KB；`ai*_scalar_ratio` 高 | 增大 tileLength 或合并连续 copy，减少循环和 DMA setup | 派生 |
| 对齐长度与有效长度混用 | `tail`、pad、rowOffset 使用错误 | Reduction、Broadcast、Transpose、MatMul | 精度错或尾块慢；非对齐搬运；Fixpipe/MTE 比例异常 | API count 用有效长度，buffer/offset 用对齐长度；逐项列公式 | 派生/对比 |
| tail 处理低效 | 尾块走标量、逐元素分支或频繁 DataCopyPad | 全部 | tail shape 下 `ai*_scalar_ratio` 高；MTE3 指令数/写回粒度异常 | 让 tail 仍走向量路径，用 mask/DataCopyPad 控制有效 count | 派生/对比 |
| DoubleBuffer 未生效 | `bufNum=2` 但 EnQue/DeQue 或依赖顺序不允许重叠 | 全部 | MTE2/VEC 比例均高但 Duration 未下降；trace 显示串行 | 检查 queue 配对、Sync、跨 tile 依赖，trace 重叠率应明显增加 | Trace |
| Broadcast `ubSplitAxis` 错 | 从外轴切或合轴错误，导致内部 stride 搬运 | Broadcast | MTE2 指令数高；L2 hit 低；核利用不稳定 | 先补维/合轴，再从最内轴向外累乘选择 split axis | 派生 |
| Broadcast NDDMA / UB Broadcast 选错 | DAV_3510 下 NLast 或尾轴对齐条件判断错误 | Broadcast | MTE2 时间高；L2 hit 低；small-rank 与 large-tail shape 差异大 | NLast 且尾轴大优先 UB Broadcast；其它按 dtype/对齐选 NDDMA | 派生/对比 |
| Reduction FullLoad / Split 选错 | R 或 R×A0 是否放入 UB 判断错误 | Reduction | tile 内 MTE2 重复搬入；VEC/MTE 比例随 R 异常增长 | AR/ARA 先判能否 full load，不能时按 ColSplit/RowSplit 跨 chunk 合并 | 派生 |
| Reduction 跨 chunk 合并开销过大 | r chunk 太小或 partial buffer 设计差 | Reduction | MTE2 指令数高；VEC ratio 与 MTE ratio 都高；workspace 往返多 | 增大 r chunk，减少 partial 合并次数，必要时换低延迟归约算法 | 派生 |
| Sort tileSize 未按 tmp 查询 | 手估 Concat/Sort tmp 导致 tile 超容或过小 | Sort/TopK | 超容时功能错；过小时归并层级/MTE 指令多 | `GetConcatTmpSize` / `GetSortTmpSize` 作为公式输入 | 派生/对比 |
| Transpose repeat 超上限 | `tileNA / 16 > 255` | Conversion/Transpose | 运行错误或性能异常；tail shape 对比明显 | `tileNA <= 255*16`，并同时满足 UB 预算和 32 元素对齐 | 派生 |
| Transpose `tileN` 与 `tileNA` 混用 | offset table 或 CopyOut 用错对齐长度 | Conversion/Transpose | tail 输出错；MTE3 写回粒度异常 | offset/table/buffer 用 `tileNA`，有效写回用 `curN` | 派生/对比 |
| MatMul ODD-M / ODD-N 未对齐 | Fixpipe SPLIT_M 或 row stride 约束漏处理 | MatMul、FA | `aic_fixpipe_ratio` 高；ADDR_MISALIGN；尾块性能差 | M 向上取偶，N 对齐到 32B row stride，写回只写有效列 | 直接/派生 |
| FA 常驻 `m × D` UB buffer | O_acc、PV 中间、sum 广播常驻 UB | FlashAttention | 大 D 性能/精度崩；UB 公式超容；shape 扩展失败 | 使用 streaming UB，O_acc 放 GM workspace，chunkRows 随 D 自适应 | 派生/对比 |
| FA V1/V2 chunk 不对称 | 只在某一阶段切 chunk | FlashAttention | 多 s2 或大 D 下周期性错位；trace 显示自读自写段竞争 | 所有 DataCopy 量必须 ≤ 单槽，V1/V2 对称 chunk loop | Trace/对比 |

## Buffer 规划问题

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| bufferNum / stageNum 估少 | dtype 升精度、融合后处理、tmp buffer 未计入 | Elementwise、Broadcast、Reduction、MatMul | UB 超容导致精度错；不同 dtype 性能断崖 | 按存活期列 buffer 清单，stageNum 随输入路数/融合分支变化 | 派生 |
| UB 静态偏移重叠 | 手写 offset，未按对齐后大小推进 | MatMul、FA、Transpose | 精度随机错；某些 tile 或 task 周期性失败 | 所有 offset 用 aligned size，增加容量公式审查 | 派生/对比 |
| UB bank conflict | 多个 LocalTensor 起始地址或 stride 不合理 | Vector-heavy 全部 | `aiv_vec_total_cflt_ratio`、bank/bankgroup 子项高 | 调整 UB 地址分配、padding、repeatStride/blockStride | 直接 |
| MTE 与 VEC 资源冲突 | DB 或 pipeline 编排让搬运和计算抢资源 | 全部 | `aiv_vec_mte_cflt_ratio` 高；MTE wait / VEC wait 高 | 错开 MTE2/MTE3 与 Vector 操作时序 | 直接/Trace |
| L1 容量漏验 | 假设 L1 总量都可用，忽略 A1/B1 端口或 rotation slots | MatMul、FA | 大 D 或大 K 精度错；CUBE/MTE1 比例异常 | 用 L1_A/L1_B 预算和 rotation depth 校验单槽 Nd2Nz 量 | 派生/对比 |
| L0A/L0B/L0C 容量漏验 | K/M/N 基本块超过 L0 容量 | MatMul、FA | CUBE 利用不稳定；大 shape 失败；可能运行错误 | 校验 `m*K_BASE`、`K_BASE*n`、`m*n` 分别不超过 L0 容量 | 派生 |
| L2 Cache 策略不适配 | 重复读数据未缓存，或一次性数据污染 L2 | Broadcast、MatMul、FA、Reduction | `ai*_total_hit_rate < 50%`；MTE2 高 | 根据复用程度设置 CacheMode，优化数据访问顺序 | 直接/派生 |
| workspace 槽语义混用 | handshake/self-ref/task-state 共用 slot 常量 | FA、复杂 mix kernel | 多 s2、多 task 时精度漂移；trace race | 三类 slot 分别用 loop/task 计数器和独立槽数取模 | Trace/对比 |
| workspace 按最大 shape 静态预留 | `Sk_max`、最大 N 或最大 batch 预留 | FA、Sort、Reduction | 内存占用异常；小 shape 性能受影响 | workspace size 按运行时 shape 计算返回 | 派生 |
| Sync / PipeBarrier 过多 | 用全局 barrier 替代精确 HardEvent | MatMul、FA、复杂流水 | 多 pipe 均低利用；流水线气泡；trace 中等待多 | 列出 barrier 契约位置，冗余率过高需删除 | Trace |
| TilingData 过大或字段冗余 | 大量运行期不变量放入 TilingData | 小 shape 全部 | `ai*_scalar_ratio` 高；头开销占比高 | 缩小 TilingData，常量或 Host 侧可推导字段不下发 | 派生 |

## 按算子族诊断重点

### Elementwise

高频问题集中在线性切分、对齐和升精度 buffer：

- `blockDim` 应由 `totalElements`、最小每核数据量和 AIV 核数共同决定。核利用率低说明 tile 太大或核数固定；头开销高说明小 shape 开核过多。
- `tileLength` 过小会表现为 `ai*_mte2_instructions` / `ai*_mte3_instructions` 高、单次搬运粒度小、`ai*_scalar_ratio` 上升。
- FP16/BF16 加减链路若升精度到 FP32，UB bufferNum 必须计入 Cast 输入/输出和 FP32 中间 buffer，否则容易超容。
- 对齐优先看 256B/Vector repeat 口径；tail 应继续走向量 API 的有效 count，而不是标量逐元素处理。

### Broadcast

高频问题集中在合轴、`ubSplitAxis` 和广播方式选择：

- 合轴错误会让 Kernel 循环维度膨胀，通常表现为 scalar 占比高、MTE 指令数高。
- `ubSplitAxis` 应从最内轴向外累乘选择；若切到非连续外轴，MTE2 比例高且 L2 hit 可能偏低。
- DAV_3510 上 NDDMA 与 UB Broadcast 选错时，shape 对比差异明显。NLast 且尾轴大时 NDDMA 反复读可能刷 dcache，优先关注 L2 hit、MTE2 时间和 active bandwidth。
- 当 `blockNum < coreNum` 时，可以缩小 `maxElemNum` 重算 `ubFormer/ubOuter`，但要同步观察单次搬运粒度，避免过度拆小。

### Reduction

高频问题集中在 AR/ARA 分支、有效长度与对齐长度、跨 chunk 合并：

- AR/ARA 首先判断 full load 能否成立。选错会导致重复搬入或 UB 超容。
- `rLength` 用于 DataCopyPad blockLen 和 Reduce API count；`rLengthAlign` 用于 UB rowOffset 和 buffer 分配。混用通常先表现为尾块精度错，其次是非对齐搬运效率差。
- A 很小、R 很大时，单纯按 A 分核会吃不满核。核利用率低且单核执行长，应评估 Group Reduce。
- RowSplit/ColSplit 的 chunk 过小会拉高 MTE 指令数和 partial 合并开销；需要在 UB 容量和合并次数之间取平衡。

### Sort / TopK

高频问题集中在 tileSize、tmp buffer 和归并层级：

- tileSize 由 UB、dtype、proposal、index、Concat tmp、Sort tmp 共同决定，tmp size 必须用 API 查询。
- tileSize 过大时 totalTiles 不足，核利用率低；tileSize 过小时 totalTiles 过多，归并层级和 SyncAll 次数增加。
- Pattern B/C 的分界是 `N <= tileSize * coreNum`。超过后应先核内归并再跨核归并，避免每轮跨核归并都 SyncAll。
- 诊断上优先看 Task Duration 随 N 的增长曲线、MTE 指令数、trace 中 SyncAll 等待。

### Conversion / Transpose

当前重点是 small-channel transpose：

- `tileNA` 是 UB 对齐宽度，`curN` 是尾块有效宽度。offset table、buffer、repeats 用 `tileNA`；CopyOut 用 `curN * C`。
- `repeats = tileNA / 16` 不能超过 255，超过时必须下调 `tileN`。
- `blockDim = min(coreNum, totalTiles)`，不要为空核占位。
- 逐像素 DMA 或标量 gather 会表现为 MTE 指令数高、单次搬运粒度小、scalar 占比高。

### MatMul / GMM

高频问题集中在 M×N 切分、AIC/AIV 协同、L1/L0/UB/Fixpipe：

- `usedCoreNum = ceil(M/singleCoreM) * ceil(N/singleCoreN)` 必须动态计算。Block Dim 低但 shape 足够大时，优先检查 singleCoreM/N 是否过大。
- K 轴通常在核内迭代，不作为核间切分维度。若 L1/L0 容量不足，需要 K-axis、M-axis 或 N-axis 分块，而不是简单减少核数。
- ODD-M / ODD-N 未处理时，`aic_fixpipe_ratio` 可能偏高，严重时出现地址未对齐错误。
- 融合后处理的 AIV buffer 数随 stageNum 变化。stageNum 估少会 UB 重叠，估多会 tile 变小、MTE 指令数增加。
- GMM 分组不均会表现为核间耗时差异大，需要看每组 M/N/K 分布与调度策略。

### FlashAttention

高频问题集中在任务维度、streaming UB、workspace slot 和跨核流水：

- 默认 task 级模式下，s2 不进入 taskIdx；s2 在 task 内顺序累积 online softmax 状态。若 Sq=1 且大 Sk 导致 totalTasks 远小于 AIC 核数，再评估 split-KV reduce。
- 任何常驻 UB 的 `m × D` buffer 都是大 D 风险点。应使用 streaming UB，`chunkRows = chunkBufferBytes / (D_align * sizeof(compute_T))` 随 D 自适应。
- V1/V2 的 chunk loop 必须对称，否则多 s2 或大 D 下容易出现周期性 chunk 错位。
- 跨 stage handshake、跨 loop 自读自写、跨 task 状态槽必须分离。CSV 通常看不出 race，需靠多 s2 case、trace 或精度二分确认。
- Mix kernel 的 AIC/AIV 比例不当会造成流水线气泡。诊断时同时看 AIC/AIV 时间、wait ratio、PipeUtilization 和 trace。

### 规划中类别

Random、Convolution、NN 其它类当前没有展开专属 Tiling 模式。诊断时只应用通用矩阵，不补充未经验证的专属规则：

- Random：优先关注状态 buffer、种子分配、核间独立性、tail 写回。
- Convolution：可先借鉴 MatMul 的 L1/L0/UB 容量与核切分诊断，但具体 im2col/window 复用策略需另建模式。
- NN 其它：按其核心子操作拆到 Reduction、Broadcast、Elementwise、MatMul 等已有族后诊断。

## 快速排查顺序

1. 看 `OpBasicInfo.csv`：`Task Duration`、`Block Dim`、`Current Freq` 是否正常。
2. 看 `PipeUtilization.csv`：主瓶颈是 VEC、CUBE、SCALAR、MTE2、MTE3、Fixpipe，还是各项都不高。
3. 算核利用率和核间不均衡：先排除 blockDim、tail、动态 shape 和任务分配问题。
4. 算单次搬运粒度：`datas / instructions`，判断 tileLength 是否过小。
5. 看 `Memory.csv` / `L2Cache.csv`：判断搬运是否接近带宽上限，还是局部性/CacheMode 问题。
6. 看 `ResourceConflictRatio.csv`：若 VEC 高，确认是否被 UB conflict 放大。
7. 对 DB、slot、跨核同步、SyncAll、PipeBarrier 等 CSV 难确认问题，必须追加 trace 或 shape 对比。
