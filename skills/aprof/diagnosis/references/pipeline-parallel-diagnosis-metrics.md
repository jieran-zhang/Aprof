# 流水并行不足诊断矩阵

本文用于诊断 Ascend C 算子中的流水并行不足问题，包括 CopyIn、Compute、CopyOut 未形成有效流水，DoubleBuffer 未启用或配置不合理，queue 深度不足，同步等待过多，以及 AIC/AIV 或 MTE/VEC 节拍不匹配。

使用时应交叉参考：

- [tiling 诊断矩阵](tiling-diagnosis-metrics.md)：核切分、tileLength、DoubleBuffer、Buffer 规划、workspace slot。
- [数据搬运瓶颈诊断矩阵](data-movement-diagnosis-metrics.md)：MTE2/MTE3、搬运粒度、搬运与计算重叠、MTE wait。

## 证据等级

- **直接**：msprof 字段或运行时参数可直接支持判断。
- **派生**：需要多个字段、shape、TilingData、buffer/queue 配置或代码公式共同判断。
- **Trace/对比**：CSV 不足以确认，需要 timeline、trace、不同配置或代码插桩对比。

## 核心 Metric

### 1. 流水重叠

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| MTE2/Compute 重叠率 | `overlap(MTE2, VEC或CUBE) / min(MTE2_time, Compute_time)` | trace / timeline | 判断 CopyIn 是否被 Compute 掩盖 | Trace |
| Compute/MTE3 重叠率 | `overlap(VEC或CUBE, MTE3) / min(Compute_time, MTE3_time)` | trace / timeline | 判断 CopyOut 是否与 Compute 并行 | Trace |
| CopyIn/Compute/CopyOut 串行度 | timeline 中三阶段顺序执行的比例 | trace / timeline | 判断是否形成三段流水 | Trace |
| 流水效率 | `max(阶段耗时) / Task Duration` 或 `max(pipe_time) / Task Duration` | trace 或 `PipeUtilization.csv` | 越低说明气泡/等待/同步越多；需结合 trace 确认 | 派生/Trace |

### 2. Pipe 利用与气泡

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| VEC 占比 | `aiv_vec_ratio` | `PipeUtilization.csv` | 判断 Compute 是否为主导阶段 | 直接 |
| CUBE 占比 | `aic_cube_ratio` | `PipeUtilization.csv` | MatMul/FA 判断 Cube 阶段是否主导 | 直接 |
| MTE2 占比 | `ai*_mte2_ratio` | `PipeUtilization.csv` | 判断 CopyIn 是否主导 | 直接 |
| MTE3 占比 | `ai*_mte3_ratio` | `PipeUtilization.csv` | 判断 CopyOut 是否主导 | 直接 |
| 流水线气泡 | 多个 pipe 比例均在 30%-50%，无明显主导单元 | `PipeUtilization.csv` + trace | 常见于 DB 未生效、queue 深度不足、同步过强、stage 不均衡 | 派生/Trace |
| 头开销占比 | `(Task Duration - max(ai*_time)) / Task Duration` | `OpBasicInfo.csv` + `PipeUtilization.csv` | 小 shape 或 queue 初始化/同步过多会放大 | 派生 |

### 3. 等待与冲突

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| Vector wait | `aiv_vec_wait_ratio` | `ResourceConflictRatio.csv` | Vector 等待搬运、同步或资源时升高 | 直接 |
| Cube wait | `aic_cube_wait_ratio` | `ResourceConflictRatio.csv` | Cube 等待 VEC、MTE 或跨核同步时升高 | 直接 |
| MTE wait | `ai*_mte2_wait_ratio`、`ai*_mte3_wait_ratio` | `ResourceConflictRatio.csv` | 搬运 pipe 等待 queue、同步或资源时升高 | 直接 |
| MTE conflict | `aiv_vec_mte_cflt_ratio` | `ResourceConflictRatio.csv` | Vector 与 MTE 时序冲突，常见于流水编排不合理 | 直接 |
| Sync 等待占比 | 等待事件、WaitFlag、SyncAll、PipeBarrier 在 timeline 中的耗时占比 | trace / timeline | CSV 难以直接确认同步过多 | Trace |

### 4. Buffer / Queue 配置

| Metric | 计算方式 | 数据来源 | 用途 | 证据 |
| ------ | ---------- | ---------- | ------ | ------ |
| queue 深度 | `InitBuffer(..., bufNum)` / TQue depth | 代码、TilingData | 判断是否支持 producer/consumer 并行 | 派生 |
| DB 配置有效性 | `bufNum == 2` 且 EnQue/DeQue 成对，前后 tile 无强依赖 | 代码 + trace | 判断 DoubleBuffer 是否真正生效 | Trace/对比 |
| 单槽容量余量 | `单次DataCopy字节数 <= queue单槽字节数` | 代码、TilingData、shape | 溢出会破坏流水；过小会导致频繁搬运 | 派生 |
| stage 份数 | workspace/中间 buffer 轮转份数 | 代码、TilingData | 份数不足会让不同 stage 互等或覆盖 | 派生/Trace |
| slot 语义隔离 | handshake/self-ref/task-state 是否使用独立槽数和取模公式 | 代码 | 混用会导致等待、race 或精度漂移 | Trace/对比 |

## 问题矩阵

| 问题 | 常见触发 | 适用算子族 | 诊断 Metric | 归因与处理 | 证据 |
| ------ | ---------- | ------------ | ------------- | ------------ | ------ |
| CopyIn、Compute、CopyOut 完全串行 | 单 buffer、循环内强同步、前后 tile 有依赖 | 全部 | trace 三阶段不重叠；MTE2/Compute/MTE3 重叠率 <5% | 启用 DB，检查 EnQue/DeQue 和前后 tile 依赖，减少循环内同步 | Trace |
| DoubleBuffer 未启用 | `InitBuffer` 的 `bufNum` 为 1 或未使用 queue | 全部 | queue depth 为 1；trace 无 MTE/Compute 重叠 | 改为双缓冲或多槽 queue，并保证 producer/consumer 可并行 | 派生/Trace |
| DoubleBuffer 配置了但未生效 | `bufNum=2`，但 EnQue/DeQue 配对错误、每轮 Sync、依赖阻塞 | 全部 | trace 串行；MTE2/VEC 比例都高但 Duration 不降 | 检查 queue 生命周期、FreeTensor 时机、同步事件和数据依赖 | Trace |
| queue 深度不足 | 多 stage pipeline 只有 1-2 份 buffer，不能覆盖延迟 | MatMul、GMM、FA、复杂融合 | 流水线气泡；Vector/Cube/MTE wait 高；stage 互等 | 增加 queue/workspace 份数，按 stage 延迟和并行度配置 depth | 派生/Trace |
| queue 单槽太小 | 单次搬运超过单槽或被迫切成很多小 chunk | FA、Reduction、Broadcast、Transpose | MTE 指令数高；单次搬运粒度小；trace 中 CopyIn 频繁 | 调整 tile/chunkRows 或单槽容量，确保单次 DataCopy 不超槽 | 派生 |
| 同步等待过多 | 循环内频繁 SyncAll、WaitFlag、PipeBarrier，或用全局 barrier 替代局部事件 | MatMul、FA、复杂流水 | Sync/Wait 在 trace 中占比高；多个 pipe 利用率不高 | 列出同步契约，只保留必要 HardEvent / cross-core sync | Trace |
| PipeBarrier 过多 | 使用 `PipeBarrier<PIPE_ALL>` 作为保险屏障 | MatMul、FA、复杂融合 | trace 中 pipe drain 多；CUBE/VEC/MTE 都不满 | 用精确 HardEvent 替代，删除同 pipe 顺序操作之间的 barrier | Trace |
| stage 耗时不均衡 | CopyIn、Compute、CopyOut 某一阶段远长于其它阶段 | 全部 | 单个 pipe ratio 主导；流水效率接近最慢阶段 | 优先优化最长 stage；若已达带宽/算力上限，用其它 stage 掩盖 | 直接/派生 |
| 多个 stage 都不满 | 各 pipe ratio 分散在 30%-50%，没有主导瓶颈 | 全部 | 流水线气泡；wait ratio 高；Task Duration 高 | 优先查 DB、queue depth、同步和 stage slot，不急于优化单个 API | 派生/Trace |
| MTE 与 Vector 资源冲突 | 搬运和 Vector API 时序过密，访问同类资源 | Vector-heavy 全部 | `aiv_vec_mte_cflt_ratio` 高；MTE wait / Vector wait 高 | 错开 MTE2/MTE3 与 Vector，调整流水节拍或 API 顺序 | 直接/Trace |
| AIC/AIV 节拍不匹配 | Cube 阶段和 Vector 后处理耗时差异大 | MatMul、GMM、FA | AIC/AIV time 差大；Cube/Vector wait 高；流水气泡 | 调整 mix kernel 配比、stage 份数或把后处理拆/融合 | 派生/Trace |
| workspace 份数不足 | 多 stage 复用同一 GM/UB 段，写后读/读后写互等 | MatMul、GMM、FA | trace 中 stage 等待；slot 相关 case 周期性慢或错 | 增加 workspace 轮转份数，区分 handshake/self-ref/task-state slot | Trace/对比 |
| 小 shape 头开销掩盖流水 | 数据量小，启动、TPipe 初始化、同步成本占比高 | 全部 | 头开销占比高；`ai*_scalar_ratio` 高；pipe 利用率低 | 减少 usedCoreNum、减少 queue/同步复杂度，合并小任务 | 派生 |
| tail 破坏流水节奏 | 尾 tile 走独立分支或小粒度 copy，导致最后阶段变长 | 全部 | 最后 block 慢；tail case trace 中 CopyIn/CopyOut 串行 | 让 tail 复用主流水路径，用有效 count / DataCopyPad 控制边界 | 派生/Trace |

## 按算子族诊断重点

### Elementwise / Broadcast

- 常见目标是 GM→UB、Vector、UB→GM 三段流水。
- 若 tile 太小，MTE setup 和 queue 操作会压过计算，DB 收益有限；先参考 [tiling 诊断矩阵](tiling-diagnosis-metrics.md) 调整 tileLength。
- Broadcast 的 NDDMA / UB Broadcast 选择会影响 CopyIn 阶段长度，stage 不均衡时需先确认广播方式。

### Reduction

- RowSplit / ColSplit 有跨 chunk 合并，Compute 与 CopyIn 之间可能存在真实依赖，不一定能完全 DB。
- partial workspace 写回会引入 MTE3 阶段，需检查 CopyOut 是否能与下一轮 CopyIn 或 Compute 交叠。
- Group Reduce 增加并行度的同时会引入跨核同步，需用 trace 确认 SyncAll 成本。

### Sort / TopK

- Sort / MrgSort 的阶段通常包含搬入、UB 内排序、写回和归并同步。
- tileSize 过小会增加流水轮次和 SyncAll 次数，表现为 MTE 和同步等待都高。
- 跨核归并阶段常难与核内排序完全重叠，需要区分算法阶段边界和 queue 配置问题。

### MatMul / GMM

- 重点看 Cube、MTE1、Fixpipe、AIV 后处理之间是否形成节拍。
- AIC/AIV 后处理不匹配时，单纯加 DB 不一定有效，应调整 AIC:AIV 配比或 workspace 份数。
- GMM 分组不均会造成某些核 stage 更长，先看核间 `aic_time/aiv_time` 差异。

### FlashAttention

- FA 类是典型多 stage mix kernel，C1→V1→C2→V2 的依赖方向不能破坏。
- 跨 stage handshake、跨 loop 自读自写、跨 task 状态 slot 必须语义分离。
- V1/V2 chunk loop 不对称、workspace slot 混用、cross-core sync 过强，往往需要 trace 和精度 case 一起确认。

## 快速排查顺序

1. 先看 `PipeUtilization.csv`：判断是单 stage 主导，还是多个 pipe 都不满。
2. 看 `ResourceConflictRatio.csv`：确认 wait ratio 和 `aiv_vec_mte_cflt_ratio`。
3. 用 trace 看 CopyIn、Compute、CopyOut 是否重叠。
4. 检查 DB/queue：`bufNum`、EnQue/DeQue、FreeTensor、单槽容量、queue depth。
5. 检查同步：SyncAll、WaitFlag、CrossCoreWaitFlag、PipeBarrier 是否只出现在契约位置。
6. 检查 stage 份数和 slot 公式：workspace/UB buffer 是否会互等或覆盖。
7. 对小 shape 和 tail case 单独对比，避免把头开销或尾分支误判为整体流水问题。
